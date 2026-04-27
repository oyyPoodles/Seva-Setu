"""
SevaSetu — Gemma 4 Local Inference Service
Provides zero-cost, offline-capable AI as Tier-2 fallback when Gemini API
is unavailable (circuit breaker open) or during network outages.

Architecture:
  Tier 1: Gemini API (cloud, best quality, has cost)
  Tier 2: Gemma 4 local (this service — zero cost, near-Gemini quality)
  Tier 3: Keyword rules (deterministic, zero cost, minimal quality)

Gemma 4 is loaded lazily on first use to avoid startup overhead.
Model: google/gemma-4-it (instruction-tuned, 4B params)

Capabilities mirrored from GeminiService:
  - extract_need()     → Structured need extraction from unstructured text
  - generate_dispatch_brief() → Volunteer dispatch messages
  - analyze_feedback() → Feedback scoring signals
  - validate_match()   → Match quality assessment
"""

import json
import logging
import time
import asyncio
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

# Gemma prompt templates — structured to match Gemini output schemas exactly
_EXTRACT_PROMPT = """\
<start_of_turn>user
You are a humanitarian need classifier for India. Extract structured information from this community report.

Report: "{text}"

Return ONLY valid JSON with these exact fields:
{{
  "title": "short descriptive title (max 100 chars, in English)",
  "description": "detailed description in English",
  "need_type": "one of: HEALTHCARE, EDUCATION, WATER_SANITATION, SHELTER, FOOD, INFRASTRUCTURE, LIVELIHOOD",
  "urgency": 0.0 to 1.0,
  "required_skills": ["skill1", "skill2"],
  "location_hint": "location mentioned or null",
  "affected_count": number or null,
  "original_language": "language code"
}}
<end_of_turn>
<start_of_turn>model
"""

_DISPATCH_PROMPT = """\
<start_of_turn>user
Generate a brief dispatch message for a volunteer.
Need: {title}
Details: {desc}
Volunteer: {vol_name} | Skills: {skills} | Location: {location} | Match: {score:.0%}
Write 2-3 sentences: what the situation is, what they should do, safety notes. Under 200 chars.
<end_of_turn>
<start_of_turn>model
"""

_VALIDATE_PROMPT = """\
<start_of_turn>user
Validate this volunteer-need match for humanitarian response in India.
Need: {title} | Type: {need_type} | Skills needed: {need_skills} | Urgency: {urgency:.2f}
Volunteer skills: {vol_skills} | Reliability: {reliability:.2f} | Has vehicle: {vehicle}
Score breakdown: {scores}

Return ONLY valid JSON:
{{
  "validation": "Valid" | "Weak" | "Poor",
  "confidence": 0.0 to 1.0,
  "overall_rationale": "2-3 sentences explaining verdict",
  "algorithm_flags": ["any concerns"],
  "source": "gemma-4-local"
}}
<end_of_turn>
<start_of_turn>model
"""

_FEEDBACK_PROMPT = """\
<start_of_turn>user
Extract scoring signals from this volunteer feedback for a humanitarian assignment.
Feedback: "{feedback}"

Return ONLY valid JSON:
{{
  "skill_match_accurate": true/false,
  "response_time_ok": true/false,
  "volunteer_helpful": true/false,
  "need_resolved": true/false,
  "issues": ["issue1"] or [],
  "sentiment_score": -1.0 to 1.0,
  "source": "gemma-4-local"
}}
<end_of_turn>
<start_of_turn>model
"""


class GemmaService:
    """
    Gemma 4 local inference — zero-cost, offline-capable AI tier.
    Loaded lazily on first request to avoid startup latency.
    """

    MODEL_ID = "google/gemma-4-it"
    MAX_NEW_TOKENS = 512
    TEMPERATURE = 0.3  # Low temperature for structured output

    def __init__(self):
        self._pipeline = None
        self._tokenizer = None
        self._model = None
        self._available = False
        self._load_attempted = False
        logger.info("ℹ️ GemmaService created (lazy load — model loads on first use)")

    def _try_load(self) -> bool:
        """
        Attempt to load Gemma 4 model. Called lazily on first use.
        Returns True if successful.
        """
        if self._load_attempted:
            return self._available

        self._load_attempted = True
        logger.info("🔄 Loading Gemma 4 model (first use — this may take 30-60s)...")

        try:
            import torch
            from transformers import AutoTokenizer, AutoModelForCausalLM, pipeline

            device = "cuda" if torch.cuda.is_available() else "cpu"
            dtype = torch.bfloat16 if device == "cuda" else torch.float32

            self._tokenizer = AutoTokenizer.from_pretrained(self.MODEL_ID)
            self._model = AutoModelForCausalLM.from_pretrained(
                self.MODEL_ID,
                torch_dtype=dtype,
                device_map="auto" if device == "cuda" else None,
                low_cpu_mem_usage=True,
            )

            self._pipeline = pipeline(
                "text-generation",
                model=self._model,
                tokenizer=self._tokenizer,
                max_new_tokens=self.MAX_NEW_TOKENS,
                temperature=self.TEMPERATURE,
                do_sample=True,
                return_full_text=False,
            )

            self._available = True
            logger.info(
                f"✅ Gemma 4 loaded successfully on {device} "
                f"({'GPU' if device == 'cuda' else 'CPU — inference will be slower'})"
            )
            return True

        except ImportError:
            logger.warning(
                "⚠️ Gemma 4 unavailable: 'transformers' and 'torch' not installed. "
                "Install with: pip install transformers torch accelerate"
            )
        except Exception as e:
            logger.error(f"❌ Gemma 4 load failed: {e}")

        self._available = False
        return False

    @property
    def is_available(self) -> bool:
        if self._load_attempted:
            return self._available
        return self._try_load()

    def _infer(self, prompt: str) -> str:
        """Run synchronous local inference."""
        if not self._available:
            return ""
        try:
            outputs = self._pipeline(prompt)
            return outputs[0]["generated_text"].strip()
        except Exception as e:
            logger.error(f"Gemma inference error: {e}")
            return ""

    def _parse_json(self, text: str) -> Optional[Dict]:
        """Extract and parse JSON from model output."""
        # Strip markdown fences if present
        if "```" in text:
            text = text.split("```")[1]
            if text.startswith("json"):
                text = text[4:]
        text = text.strip()
        try:
            return json.loads(text)
        except Exception:
            # Find JSON object in text
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                try:
                    return json.loads(text[start:end])
                except Exception:
                    pass
        logger.warning(f"Gemma JSON parse failed: {text[:100]}")
        return None

    # ─── Need Extraction ─────────────────────────────────────

    async def extract_need(self, raw_text: str) -> Optional[Dict[str, Any]]:
        """
        Extract structured need from unstructured text using Gemma 4.
        Returns None if extraction fails (caller uses keyword fallback).
        """
        if not self.is_available:
            return None

        prompt = _EXTRACT_PROMPT.format(text=raw_text[:2000])
        start = time.time()

        result_text = await asyncio.to_thread(self._infer, prompt)
        latency = int((time.time() - start) * 1000)

        parsed = self._parse_json(result_text)
        if parsed:
            parsed["source"] = "gemma-4-local"
            logger.info(f"🟢 Gemma extract: {parsed.get('need_type')} | {latency}ms")
            return parsed

        logger.warning("Gemma extraction returned unparseable output")
        return None

    # ─── Dispatch Brief ──────────────────────────────────────

    async def generate_dispatch_brief(
        self,
        title: str,
        desc: str,
        vol_name: str,
        skills: List[str],
        location: str,
        score: float,
    ) -> Optional[str]:
        """Generate dispatch brief for a volunteer using Gemma 4."""
        if not self.is_available:
            return None

        prompt = _DISPATCH_PROMPT.format(
            title=title, desc=desc[:300], vol_name=vol_name,
            skills=", ".join(skills[:3]), location=location, score=score,
        )
        start = time.time()
        result = await asyncio.to_thread(self._infer, prompt)
        latency = int((time.time() - start) * 1000)

        if result:
            logger.info(f"🟢 Gemma dispatch brief | {latency}ms")
            return result[:300]
        return None

    # ─── Match Validation ────────────────────────────────────

    async def validate_match(
        self,
        title: str,
        need_type: str,
        need_skills: List[str],
        urgency: float,
        vol_skills: List[str],
        reliability: float,
        has_vehicle: bool,
        score_breakdown: Dict[str, float],
    ) -> Optional[Dict[str, Any]]:
        """Validate a volunteer-need match using Gemma 4."""
        if not self.is_available:
            return None

        prompt = _VALIDATE_PROMPT.format(
            title=title, need_type=need_type,
            need_skills=", ".join(need_skills) or "none",
            urgency=urgency,
            vol_skills=", ".join(vol_skills) or "none",
            reliability=reliability,
            vehicle="yes" if has_vehicle else "no",
            scores=json.dumps({k: round(v, 2) for k, v in score_breakdown.items()}),
        )
        start = time.time()
        result_text = await asyncio.to_thread(self._infer, prompt)
        latency = int((time.time() - start) * 1000)

        parsed = self._parse_json(result_text)
        if parsed:
            parsed["source"] = "gemma-4-local"
            parsed["latency_ms"] = latency
            logger.info(f"🟢 Gemma validation: {parsed.get('validation')} | {latency}ms")
            return parsed
        return None

    # ─── Feedback Analysis ───────────────────────────────────

    async def analyze_feedback(self, feedback_text: str) -> Optional[Dict[str, Any]]:
        """Extract scoring signals from assignment feedback using Gemma 4."""
        if not self.is_available:
            return None

        prompt = _FEEDBACK_PROMPT.format(feedback=feedback_text[:1000])
        start = time.time()
        result_text = await asyncio.to_thread(self._infer, prompt)
        latency = int((time.time() - start) * 1000)

        parsed = self._parse_json(result_text)
        if parsed:
            parsed["source"] = "gemma-4-local"
            logger.info(f"🟢 Gemma feedback analysis | {latency}ms")
            return parsed
        return None


# Singleton — lazy loaded
gemma_service = GemmaService()
