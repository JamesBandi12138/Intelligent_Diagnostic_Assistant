from __future__ import annotations

from dataclasses import dataclass

from common.config import settings


@dataclass
class KnowledgeHit:
    title: str
    content: str
    score: float


class MilvusKnowledgeStore:
    def __init__(self) -> None:
        self.enabled = settings.MILVUS_ENABLED
        self.collection_name = settings.MILVUS_COLLECTION
        self.uri = settings.MILVUS_URI
        self.token = settings.MILVUS_TOKEN

    def search(self, query: str, top_k: int = 3) -> list[KnowledgeHit]:
        if not self.enabled:
            return []

        try:
            from pymilvus import MilvusClient
        except Exception:
            return []

        try:
            client = MilvusClient(uri=self.uri, token=self.token or None)
            _ = client
        except Exception:
            return []

        return []


knowledge_store = MilvusKnowledgeStore()

