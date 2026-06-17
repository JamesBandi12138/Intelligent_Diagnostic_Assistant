from services.knowledge_base.milvus_store import knowledge_store


def test_local_knowledge_store_returns_abdominal_pain_card():
    hits = knowledge_store.search("肚子疼，右下腹更明显", top_k=3)

    assert hits
    assert any("腹痛" in hit.title for hit in hits)
    assert any("红旗" in hit.content or "右下腹" in hit.content for hit in hits)


def test_local_knowledge_store_returns_headache_card():
    hits = knowledge_store.search("头痛两天，担心是不是要紧", top_k=3)

    assert hits
    assert any("头痛" in hit.title for hit in hits)
