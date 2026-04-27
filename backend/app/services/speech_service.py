"""
SevaSetu — Speech Service
Google Cloud Speech-to-Text for transcribing audio reports (e.g. from WhatsApp).

Supports:
  - Base64-encoded audio (inline payloads)
  - URL-based audio download (WhatsApp media URLs)
  - Gemini audio fallback when Cloud Speech is not configured

Multilingual: en-IN, hi-IN, mr-IN, ta-IN (auto-detect)
"""

import logging
import base64
import asyncio
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class SpeechService:
    """
    Multi-strategy audio transcription service.

    Priority:
      1. Google Cloud Speech-to-Text (if GOOGLE_APPLICATION_CREDENTIALS set)
      2. Gemini multimodal audio (if GEMINI_API_KEY set)
      3. Graceful skip with descriptive message
    """

    def __init__(self):
        self._cloud_speech_available = False
        self._gemini_available = False

        # Strategy 1: Google Cloud Speech
        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            try:
                from google.cloud import speech  # pyright: ignore
                self.client = speech.SpeechAsyncClient()
                self._cloud_speech_available = True
                logger.info("✅ Google Cloud Speech client initialized")
            except Exception as e:
                logger.warning(f"⚠️ Speech client init failed: {e}")

        # Strategy 2: Gemini multimodal fallback
        if settings.GEMINI_API_KEY and not self._cloud_speech_available:
            self._gemini_available = True
            logger.info("ℹ️ Speech fallback: will use Gemini for audio transcription")

    @property
    def is_available(self) -> bool:
        """Whether any transcription strategy is available."""
        return self._cloud_speech_available or self._gemini_available

    async def transcribe_from_url(self, audio_url: str) -> str:
        """
        Download audio from a URL and transcribe it.
        Used for WhatsApp media URLs.
        """
        audio_bytes = await self._download_audio(audio_url)
        if not audio_bytes:
            return ""

        audio_b64 = base64.b64encode(audio_bytes).decode("utf-8")
        return await self.transcribe(audio_b64)

    async def transcribe(self, audio_content_str: str) -> str:
        """
        Transcribes base64-encoded audio.
        Tries Cloud Speech first, falls back to Gemini multimodal.
        """
        if self._cloud_speech_available:
            return await self._cloud_speech_transcribe(audio_content_str)

        if self._gemini_available:
            return await self._gemini_transcribe(audio_content_str)

        logger.debug("Audio transcription skipped (no Speech-to-Text configured)")
        return ""

    async def _cloud_speech_transcribe(self, audio_content_str: str) -> str:
        """Transcribe using Google Cloud Speech-to-Text."""
        try:
            from google.cloud import speech  # pyright: ignore

            audio = speech.RecognitionAudio(
                content=base64.b64decode(audio_content_str)
            )

            # Auto-detect Hindi/English mixes commonly found in Indian reports
            config = speech.RecognitionConfig(
                encoding=speech.RecognitionConfig.AudioEncoding.OGG_OPUS,
                sample_rate_hertz=16000,
                language_code="en-IN",
                alternative_language_codes=["hi-IN", "mr-IN", "ta-IN"],
            )

            response = await self.client.recognize(config=config, audio=audio)

            transcript = []
            for result in response.results:  # pyright: ignore
                transcript.append(result.alternatives[0].transcript)  # pyright: ignore

            text = " ".join(transcript)
            if text:
                logger.info(
                    f"🎙️ Cloud Speech transcription: '{text[:60]}...' "
                    f"({len(transcript)} segments)"
                )
            return text

        except Exception as e:
            logger.error(f"Cloud Speech transcription failed: {e}")
            # Fall through to Gemini if available
            if self._gemini_available:
                return await self._gemini_transcribe(audio_content_str)
            return ""

    async def _gemini_transcribe(self, audio_content_str: str) -> str:
        """
        Fallback: use Gemini multimodal to transcribe audio.
        Gemini 2.5 Flash supports audio input natively.
        """
        try:
            from app.services.gemini_service import gemini_service

            if not gemini_service.is_available:
                return ""

            import google.generativeai as genai
            import time

            audio_bytes = base64.b64decode(audio_content_str)

            prompt = (
                "Transcribe this audio message exactly as spoken. "
                "The speaker may use Hindi, English, Marathi, Tamil, or a mix. "
                "Return ONLY the transcription text, nothing else."
            )

            start = time.time()
            response = await asyncio.to_thread(
                gemini_service._model.generate_content,
                [
                    prompt,
                    {"mime_type": "audio/ogg", "data": audio_bytes},
                ],
            )
            latency = int((time.time() - start) * 1000)

            text = response.text.strip()
            logger.info(
                f"🎙️ Gemini audio transcription ({latency}ms): '{text[:60]}...'"
            )

            # Log the call for billing
            await gemini_service.log_gemini_call(
                task_type="transcribe",
                latency_ms=latency,
                success=True,
                input_tokens=len(audio_bytes) // 32,  # rough audio token estimate
                output_tokens=len(text) // 4,
            )

            return text

        except Exception as e:
            logger.error(f"Gemini audio transcription failed: {e}")
            return ""

    async def _download_audio(self, url: str) -> Optional[bytes]:
        """Download audio file from a URL (e.g., WhatsApp media URL)."""
        try:
            import httpx

            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.get(url)
                response.raise_for_status()
                logger.info(
                    f"📥 Downloaded audio: {len(response.content)} bytes from {url[:60]}"
                )
                return response.content

        except Exception as e:
            logger.error(f"Audio download failed from {url[:60]}: {e}")
            return None


# Singleton
speech_service = SpeechService()
