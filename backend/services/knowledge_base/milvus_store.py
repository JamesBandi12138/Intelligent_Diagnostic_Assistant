from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import json
from pathlib import Path
import re
from collections import Counter

from common.config import settings
from services.knowledge_base.local_cards import KNOWLEDGE_CARDS, KnowledgeCard


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

    def _local_search(self, query: str, top_k: int) -> list[KnowledgeHit]:
        normalized_query = query.strip()
        if not normalized_query:
            return []

        results: list[KnowledgeHit] = []
        for card in KNOWLEDGE_CARDS:
            score = _score_card(card, normalized_query)
            if score <= 0:
                continue
            graph_reference = _build_graph_reference(card)
            content = (
                f"{card.summary} 红旗信号：{'、'.join(card.red_flags)}。"
                f" 优先追问：{'；'.join(card.follow_up_prompts)}。"
                f" 候选科室：{'、'.join(card.department_candidates)}。"
                f"{graph_reference}"
            )
            results.append(KnowledgeHit(title=card.title, content=content, score=score))

        results.sort(key=lambda item: item.score, reverse=True)
        return results[:top_k]

    def search(self, query: str, top_k: int = 3) -> list[KnowledgeHit]:
        local_hits = self._local_search(query, top_k)
        if local_hits or not self.enabled:
            return local_hits

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


def _score_card(card: KnowledgeCard, query: str) -> float:
    lowered_query = query.lower()
    score = 0.0

    for alias in (card.title, *card.aliases):
        if alias and alias.lower() in lowered_query:
            score += 3.0

    query_tokens = [token for token in re.split(r"[\s，。；,;、】【（）()]+", query) if token]
    for token in query_tokens:
        if token in card.summary:
            score += 0.4
        if any(token in red_flag for red_flag in card.red_flags):
            score += 0.6

    return score


@lru_cache(maxsize=1)
def _load_medical_graph_rows() -> list[dict]:
    dataset_path = Path(__file__).resolve().parents[3] / "data" / "QASystemOnMedicalKG" / "data" / "medical.json"
    if not dataset_path.exists():
        return []

    rows: list[dict] = []
    with dataset_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return rows


@lru_cache(maxsize=16)
def _build_graph_reference(card: KnowledgeCard) -> str:
    matched_rows = []
    alias_set = set(card.aliases)
    for row in _load_medical_graph_rows():
        symptoms = row.get("symptom", []) or []
        if any(symptom in alias_set for symptom in symptoms):
            matched_rows.append(row)

    if not matched_rows:
        return ""

    department_names = []
    for row in matched_rows:
        department_names.extend(row.get("cure_department", []) or [])

    top_departments = [name for name, _ in Counter(department_names).most_common(3)]
    department_part = f" 图谱高频科室：{'、'.join(top_departments)}。" if top_departments else ""
    return department_part
