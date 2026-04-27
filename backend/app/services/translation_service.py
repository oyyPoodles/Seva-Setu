"""
SevaSetu — Translation Service
Google Cloud Translation API wrapper for multilingual support.

Architecture:
  - If GOOGLE_APPLICATION_CREDENTIALS is set → real Cloud Translation v3
  - If not set → log-only stub (Gemini handles multilingual extraction as fallback)

Usage:
  translated = await translation_service.translate("पानी नहीं आया", target="en")
  detected = await translation_service.detect_language("गाँव में 3 दिन से...")
"""

import logging
from typing import Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class TranslationService:
    """
    Google Cloud Translation API (v3) for translating need reports
    and volunteer communications across Indian languages.

    Degrades gracefully: returns original text when API is unavailable.
    """

    SUPPORTED_INDIAN_LANGUAGES = {
        "hi": "Hindi",
        "bn": "Bengali",
        "te": "Telugu",
        "mr": "Marathi",
        "ta": "Tamil",
        "ur": "Urdu",
        "gu": "Gujarati",
        "kn": "Kannada",
        "ml": "Malayalam",
        "pa": "Punjabi",
        "or": "Odia",
        "as": "Assamese",
        "en": "English",
    }

    def __init__(self):
        self._client = None
        self._project_id = settings.GOOGLE_CLOUD_PROJECT
        self._available = False

        if settings.GOOGLE_APPLICATION_CREDENTIALS:
            try:
                from google.cloud import translate_v3 as translate
                self._client = translate.TranslationServiceAsyncClient()
                self._available = True
                logger.info("✅ Google Cloud Translation client initialized")
            except Exception as e:
                logger.warning(f"⚠️ Translation client init failed: {e}")
        else:
            logger.info("ℹ️ No GOOGLE_APPLICATION_CREDENTIALS — translation disabled")

    @property
    def is_available(self) -> bool:
        return self._available

    async def translate(
        self,
        text: str,
        target_language: str = "en",
        source_language: Optional[str] = None,
    ) -> str:
        """
        Translate text to the target language.
        Returns original text if translation is unavailable.
        """
        if not self._available or not self._client:
            logger.debug(f"Translation skipped (not configured): {text[:50]}...")
            return text

        try:
            from google.cloud import translate_v3 as translate

            parent = f"projects/{self._project_id}/locations/global"

            request = translate.TranslateTextRequest(
                parent=parent,
                contents=[text],
                target_language_code=target_language,
                mime_type="text/plain",
            )

            if source_language:
                request.source_language_code = source_language

            response = await self._client.translate_text(request=request)

            if response.translations:
                translated = response.translations[0].translated_text
                detected = response.translations[0].detected_language_code
                logger.info(
                    f"🌐 Translated ({detected} → {target_language}): "
                    f"'{text[:40]}...' → '{translated[:40]}...'"
                )
                return translated

            return text

        except Exception as e:
            logger.error(f"Translation failed: {e}")
            return text

    async def detect_language(self, text: str) -> str:
        """
        Detect the language of the input text.
        Falls back to 'en' if detection is unavailable.
        """
        if not self._available or not self._client:
            # Use langdetect as fallback
            try:
                from langdetect import detect
                return detect(text)
            except Exception:
                return "en"

        try:
            from google.cloud import translate_v3 as translate

            parent = f"projects/{self._project_id}/locations/global"

            request = translate.DetectLanguageRequest(
                parent=parent,
                content=text,
                mime_type="text/plain",
            )

            response = await self._client.detect_language(request=request)

            if response.languages:
                best = response.languages[0]
                logger.info(
                    f"🌐 Detected language: {best.language_code} "
                    f"(confidence: {best.confidence:.2f})"
                )
                return best.language_code

            return "en"

        except Exception as e:
            logger.error(f"Language detection failed: {e}")
            try:
                from langdetect import detect
                return detect(text)
            except Exception:
                return "en"

    async def translate_batch(
        self,
        texts: list[str],
        target_language: str = "en",
    ) -> list[str]:
        """
        Translate multiple texts in a single API call.
        Returns original texts if translation is unavailable.
        """
        if not self._available or not self._client:
            return texts

        try:
            from google.cloud import translate_v3 as translate

            parent = f"projects/{self._project_id}/locations/global"

            request = translate.TranslateTextRequest(
                parent=parent,
                contents=texts,
                target_language_code=target_language,
                mime_type="text/plain",
            )

            response = await self._client.translate_text(request=request)

            return [t.translated_text for t in response.translations]

        except Exception as e:
            logger.error(f"Batch translation failed: {e}")
            return texts


# Singleton
translation_service = TranslationService()
