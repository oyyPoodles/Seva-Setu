"""
SevaSetu — Embedding Service
Sentence-BERT embeddings for semantic skill matching via pgvector.
Uses paraphrase-multilingual-MiniLM-L12-v2 (384-dim, 50+ languages).
"""

import logging
import numpy as np
from typing import List, Optional

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()


class EmbeddingService:
    """Generate and compare 384-dim embeddings for semantic matching."""

    def __init__(self):
        self._model = None
        self._available = False

        try:
            from sentence_transformers import SentenceTransformer
            self._model = SentenceTransformer(settings.EMBEDDING_MODEL)
            self._available = True
            logger.info(f"✅ Embedding model loaded: {settings.EMBEDDING_MODEL}")
        except Exception as e:
            logger.warning(f"⚠️ Embedding model load failed: {e}. Using fallback.")

    @property
    def is_available(self) -> bool:
        return self._available

    def encode(self, text: str) -> List[float]:
        """Encode a single text string into a 384-dim embedding vector."""
        if self._available:
            embedding = self._model.encode(text, normalize_embeddings=True)
            return embedding.tolist()
        return self._fallback_encode(text)

    def encode_batch(self, texts: List[str]) -> List[List[float]]:
        """Encode a batch of texts for bulk operations."""
        if self._available:
            embeddings = self._model.encode(texts, normalize_embeddings=True, batch_size=32)
            return [e.tolist() for e in embeddings]
        return [self._fallback_encode(t) for t in texts]

    def encode_skills(self, skills: List[str], context: str = "") -> List[float]:
        """
        Encode a list of skills into a single embedding vector.
        Combines skills with optional context for richer semantics.
        """
        if not skills:
            return [0.0] * settings.EMBEDDING_DIM

        text = f"{context}. Skills: {', '.join(skills)}" if context else ", ".join(skills)
        return self.encode(text)

    @staticmethod
    def cosine_similarity(vec_a: List[float], vec_b: List[float]) -> float:
        """Compute cosine similarity between two vectors."""
        a = np.array(vec_a)
        b = np.array(vec_b)
        dot = np.dot(a, b)
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(dot / (norm_a * norm_b))

    def _fallback_encode(self, text: str) -> List[float]:
        """
        Deterministic hash-based embedding fallback.
        NOT semantically meaningful — only for development/testing.
        """
        import hashlib
        h = hashlib.sha256(text.lower().encode()).digest()
        # Expand hash to 384 dims with a deterministic pattern
        vec = []
        for i in range(settings.EMBEDDING_DIM):
            byte_idx = i % len(h)
            vec.append((h[byte_idx] / 255.0) * 2 - 1)  # normalize to [-1, 1]
        # Normalize to unit length
        arr = np.array(vec)
        norm = np.linalg.norm(arr)
        if norm > 0:
            arr = arr / norm
        return arr.tolist()


# Singleton
embedding_service = EmbeddingService()
