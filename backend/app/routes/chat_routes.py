"""
SevaSetu — Chat Routes
WebSocket endpoint for Ask SevaSetu feature.
"""

import json
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.db_models import Need
from app.services.gemini_service import gemini_service
from app.services.embedding_service import embedding_service

logger = logging.getLogger(__name__)
router = APIRouter()

@router.websocket("/ws/chat")
async def chat_websocket(websocket: WebSocket):
    await websocket.accept()
    logger.info("Chat WebSocket connected")
    
    try:
        while True:
            data = await websocket.receive_text()
            try:
                payload = json.loads(data)
                query = payload.get("text", "")
            except Exception:
                query = data

            if not query.strip():
                continue

            await websocket.send_text(json.dumps({"type": "status", "msg": "Analyzing query..."}))

            # 1. Embed query
            query_emb = embedding_service.encode(query)

            # 2. Vector search against active needs
            await websocket.send_text(json.dumps({"type": "status", "msg": "Searching context..."}))
            
            async with AsyncSessionLocal() as session:
                res = await session.execute(select(Need).where(Need.status.in_(["new", "matched", "in_progress"])))
                needs = res.scalars().all()

            ranked = []
            for n in needs:
                if n.embedding is not None and len(n.embedding) > 0:
                    score = embedding_service.cosine_similarity(query_emb, list(n.embedding))
                    ranked.append((score, n))
            
            ranked.sort(key=lambda x: x[0], reverse=True)
            top_needs = [n for s, n in ranked[:5] if s > 0.3]

            context_str = "\n".join([
                f"- Need [{n.id}]: {n.title}\n  Status: {n.status} | Urgency: {n.urgency_current:.2f} | "
                f"Location: {n.location_name or 'Unknown'} | Type: {n.need_type or 'GENERAL'} | "
                f"Affected: {n.affected_count or 'Unknown'} people"
                for n in top_needs
            ])

            await websocket.send_text(json.dumps({"type": "status", "msg": "Generating response..."}))

            # 3. Ask Gemini via the proper service (respects circuit breaker + model selection)
            if not gemini_service.is_available:
                logger.warning("Chat: Gemini unavailable (circuit open or no key) — using fallback")
                if top_needs:
                    response = (
                        f"AI brain is currently offline. Here\'s what I found:\n\n{context_str}\n\n"
                        "For full AI analysis, check that GEMINI_API_KEY is set and the backend is healthy."
                    )
                else:
                    response = "No relevant active needs found for your query, and AI analysis is currently offline."
            else:
                prompt = f"""You are 'Ask SevaSetu', an AI assistant helping NGO coordinators manage humanitarian needs across India.
Answer the user's question concisely based ONLY on the provided need context.
If the answer isn't in the context, say so clearly. Be helpful and specific.

Active Needs Context:
{context_str or "No active needs relevant to this query."}

User question: {query}

Provide a clear, actionable answer in 2-4 sentences. Reference specific needs by title when relevant."""
                try:
                    import asyncio, re
                    reply = await asyncio.to_thread(gemini_service._model.generate_content, prompt)
                    response = reply.text
                    gemini_service._record_success()
                except Exception as e:
                    err_str = str(e)
                    if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str or "quota" in err_str.lower():
                        wait_match = re.search(r'retry_delay.*?seconds.*?(\d+)', err_str, re.DOTALL)
                        wait_s = min(int(wait_match.group(1)) if wait_match else 30, 60)
                        is_daily = "PerDay" in err_str or "per_day" in err_str.lower()
                        quota_msg: str | None = None
                        if is_daily:
                            logger.warning("Chat: Gemini DAILY quota exhausted — resets at midnight UTC")
                            quota_msg = (
                                "⚠️ Gemini AI daily quota exhausted (20 req/day free tier). "
                                "Resets at midnight UTC (5:30 AM IST).\n"
                                "To fix permanently: get a new key at https://aistudio.google.com/app/apikey\n\n"
                                "Meanwhile, here's what I found:\n"
                            )
                        else:
                            logger.warning(f"Chat: Gemini rate limited — waiting {wait_s}s then retrying")
                            await websocket.send_text(json.dumps({"type": "status", "msg": f"AI rate limited — retrying in {wait_s}s..."}))
                            await asyncio.sleep(wait_s)
                            try:
                                reply = await asyncio.to_thread(gemini_service._model.generate_content, prompt)
                                response = reply.text
                                gemini_service._record_success()
                            except Exception as e2:
                                gemini_service._record_failure(e2)
                                logger.error(f"Chat retry also failed: {e2}")
                                quota_msg = "AI temporarily unavailable. Context found:\n"
                        if quota_msg is not None:
                            response = (quota_msg + context_str) if top_needs else "AI quota exceeded. Try again later."
                    else:
                        gemini_service._record_failure(e)
                        logger.error(f"Chat generation failed: {e}")
                        response = f"AI temporarily unavailable. Context found:\n\n{context_str}" if top_needs else "I'm having trouble connecting to my AI brain right now. Please try again."


            # 4. Send reply with citations
            citations = [{"id": str(n.id), "title": n.title} for n in top_needs]
            await websocket.send_text(json.dumps({"type": "reply", "text": response, "citations": citations}))

    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.close()
        except Exception:
            pass
