from __future__ import annotations

from types import SimpleNamespace
from uuid import uuid4

from app.core.llm_client import LLMGenerationResult
from app.core.vector_store import RetrievedChunk
from app.services.rag_service import NO_KNOWLEDGE_MESSAGE, RAGService


class FakeVectorStore:
    def __init__(self, results: list[RetrievedChunk]) -> None:
        self.results = results
        self.calls: list[dict] = []

    def search(self, query: str, *, top_k: int = 5, filter_ingredient: str | None = None) -> list[RetrievedChunk]:
        self.calls.append(
            {
                "query": query,
                "top_k": top_k,
                "filter_ingredient": filter_ingredient,
            }
        )
        return self.results


class FakeLLMClient:
    def __init__(self, text: str) -> None:
        self.text = text
        self.calls: list[dict] = []

    def generate_ingredient_explanation(
        self,
        *,
        ingredient_name: str,
        korean_name: str | None,
        query: str,
        retrieved_chunks: list[RetrievedChunk],
    ) -> LLMGenerationResult:
        self.calls.append(
            {
                "ingredient_name": ingredient_name,
                "korean_name": korean_name,
                "query": query,
                "retrieved_chunks": retrieved_chunks,
            }
        )
        return LLMGenerationResult(text=self.text)


def test_rag_service_returns_explanation_when_search_results_exist():
    ingredient = SimpleNamespace(
        id=uuid4(),
        inci_name="Niacinamide",
        korean_name="나이아신아마이드",
    )
    retrieved_chunk = RetrievedChunk(
        document_id="niacinamide",
        ingredient_name="Niacinamide",
        section="효능",
        content="피부 장벽 강화에 도움을 준다.",
        source_path="knowledge_base/ingredients/niacinamide.md",
    )
    vector_store = FakeVectorStore([retrieved_chunk])
    llm_client = FakeLLMClient("근거 문서 기반 설명입니다.")

    result = RAGService(vector_store=vector_store, llm_client=llm_client).explain_ingredient(ingredient)

    assert result.is_grounded is True
    assert result.summary == "근거 문서 기반 설명입니다."
    assert result.sources == [retrieved_chunk]
    assert vector_store.calls[0]["filter_ingredient"] == "Niacinamide"
    assert llm_client.calls[0]["ingredient_name"] == "Niacinamide"


def test_rag_service_blocks_generation_when_search_results_are_empty():
    ingredient = SimpleNamespace(
        id=uuid4(),
        inci_name="Unknown Ingredient",
        korean_name=None,
    )
    vector_store = FakeVectorStore([])
    llm_client = FakeLLMClient("should not be used")

    result = RAGService(vector_store=vector_store, llm_client=llm_client).explain_ingredient(ingredient)

    assert result.is_grounded is False
    assert result.summary == NO_KNOWLEDGE_MESSAGE
    assert result.sources == []
    assert llm_client.calls == []
