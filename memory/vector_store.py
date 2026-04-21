"""
memory/vector_store.py – Conversation & task memory using FAISS or ChromaDB.
Stores embeddings of past interactions for context-aware responses.
"""
from __future__ import annotations
import json
from pathlib import Path
from typing import List, Dict, Any
from config import settings
from utils.logger import get_logger
from utils.models import ConversationTurn

logger = get_logger("memory.vector_store")


class MemoryStore:
    """
    Lightweight vector memory with FAISS (default) or ChromaDB backend.
    Falls back to in-memory list if neither is installed.
    """

    def __init__(self) -> None:
        self._backend = settings.vector_store
        self._docs: List[str] = []         # raw text store (fallback)
        self._meta: List[Dict] = []        # metadata for each doc
        self._index = None                  # FAISS index
        self._collection = None             # ChromaDB collection
        self._embeddings = None             # Embedding model
        self._init_backend()

    # ── Initialisation ────────────────────────────────────────────────────────

    def _init_backend(self) -> None:
        if self._backend == "faiss":
            self._init_faiss()
        elif self._backend == "chroma":
            self._init_chroma()
        else:
            logger.warning(f"Unknown backend '{self._backend}'; using in-memory list")

    def _init_faiss(self) -> None:
        try:
            import faiss
            import numpy as np
            self._faiss = faiss
            self._np = np
            self._dim = 1536  # text-embedding-3-small dimension
            self._index = faiss.IndexFlatL2(self._dim)
            logger.info("FAISS memory initialised (dim=1536)")
        except ImportError:
            logger.warning("FAISS not installed; using in-memory fallback")
            self._index = None

    def _init_chroma(self) -> None:
        try:
            import chromadb
            client = chromadb.PersistentClient(path=settings.chroma_persist_dir)
            self._collection = client.get_or_create_collection("conversations")
            logger.info(f"ChromaDB initialised at {settings.chroma_persist_dir}")
        except ImportError:
            logger.warning("ChromaDB not installed; using in-memory fallback")
            self._collection = None

    def _get_embedding(self, text: str) -> List[float]:
        """Get embedding vector for text using OpenAI API."""
        try:
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key)
            response = client.embeddings.create(
                input=text,
                model=settings.embedding_model
            )
            return response.data[0].embedding
        except Exception as e:
            logger.warning(f"Embedding failed ({e}); using zero vector")
            return [0.0] * 1536

    # ── Store ─────────────────────────────────────────────────────────────────

    def add_turn(self, turn: ConversationTurn) -> None:
        """Store a conversation turn in memory."""
        doc_text = f"User: {turn.user_message}\nAssistant: {turn.assistant_response}"
        meta = {
            "turn_id": turn.turn_id,
            "timestamp": turn.timestamp.isoformat(),
            "task_plan_id": turn.task_plan_id or "",
        }

        self._docs.append(doc_text)
        self._meta.append(meta)

        if self._collection is not None:
            # ChromaDB: generate embedding and store
            embedding = self._get_embedding(doc_text)
            self._collection.add(
                documents=[doc_text],
                embeddings=[embedding],
                metadatas=[meta],
                ids=[turn.turn_id],
            )
        elif self._index is not None:
            # FAISS: generate embedding and add to index
            embedding = self._get_embedding(doc_text)
            vec = self._np.array([embedding], dtype="float32")
            self._index.add(vec)

        logger.info(f"Stored memory turn {turn.turn_id}")

    def add_text(self, text: str, metadata: Dict[str, Any] | None = None) -> None:
        """Store arbitrary text (e.g., task results) in memory."""
        self._docs.append(text)
        self._meta.append(metadata or {})

    # ── Retrieve ──────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int = 3) -> List[Dict[str, Any]]:
        """
        Retrieve top-k most relevant memory entries for a query.

        Returns:
            List of dicts with 'text' and 'metadata' keys
        """
        if not self._docs:
            return []

        if self._collection is not None:
            return self._search_chroma(query, top_k)
        elif self._index is not None and self._index.ntotal > 0:
            return self._search_faiss(query, top_k)
        else:
            return self._search_fallback(query, top_k)

    def _search_chroma(self, query: str, top_k: int) -> List[Dict]:
        embedding = self._get_embedding(query)
        results = self._collection.query(
            query_embeddings=[embedding],
            n_results=min(top_k, len(self._docs)),
        )
        return [
            {"text": doc, "metadata": meta}
            for doc, meta in zip(
                results["documents"][0], results["metadatas"][0]
            )
        ]

    def _search_faiss(self, query: str, top_k: int) -> List[Dict]:
        embedding = self._get_embedding(query)
        vec = self._np.array([embedding], dtype="float32")
        k = min(top_k, self._index.ntotal)
        _, indices = self._index.search(vec, k)
        return [
            {"text": self._docs[i], "metadata": self._meta[i]}
            for i in indices[0] if 0 <= i < len(self._docs)
        ]

    def _search_fallback(self, query: str, top_k: int) -> List[Dict]:
        """Keyword overlap fallback when no vector backend is available."""
        query_words = set(query.lower().split())
        scored = []
        for text, meta in zip(self._docs, self._meta):
            overlap = len(query_words & set(text.lower().split()))
            scored.append((overlap, text, meta))
        scored.sort(reverse=True)
        return [{"text": t, "metadata": m} for _, t, m in scored[:top_k]]

    def get_context_string(self, query: str, top_k: int = 3) -> str:
        """Return a formatted string of relevant past context."""
        results = self.search(query, top_k)
        if not results:
            return "No relevant context found."
        lines = ["Relevant past context:"]
        for i, r in enumerate(results, 1):
            lines.append(f"[{i}] {r['text'][:200]}")
        return "\n".join(lines)


# Module-level singleton
memory = MemoryStore()
