from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.core.llm_client import LLMClient, get_llm_client
from app.core.vector_store import RetrievedChunk, VectorStore, get_vector_store
from app.models.ingredient import Ingredient
from app.schemas.ingredient import IngredientExplainSourceResponse

NO_KNOWLEDGE_MESSAGE = "해당 성분에 대한 정보가 없습니다."


@dataclass(slots=True)
class RAGExplanationResult:
    is_grounded: bool
    summary: str
    sources: list[RetrievedChunk]


class RAGService:
    def __init__(
        self,
        *,
        vector_store: VectorStore | None = None,
        llm_client: LLMClient | None = None,
        top_k: int = 5,
    ) -> None:
        self.vector_store = vector_store or get_vector_store()
        self.llm_client = llm_client or get_llm_client()
        self.top_k = top_k

    def explain_ingredient(self, ingredient: Ingredient) -> RAGExplanationResult:
        query = self._build_query(ingredient)
        retrieved_chunks = self.vector_store.search(
            query,
            top_k=self.top_k,
            filter_ingredient=ingredient.inci_name,
        )
        if not retrieved_chunks:
            return RAGExplanationResult(
                is_grounded=False,
                summary=NO_KNOWLEDGE_MESSAGE,
                sources=[],
            )

        generation = self.llm_client.generate_ingredient_explanation(
            ingredient_name=ingredient.inci_name,
            korean_name=ingredient.korean_name,
            query=query,
            retrieved_chunks=retrieved_chunks,
        )
        return RAGExplanationResult(
            is_grounded=True,
            summary=generation.text,
            sources=retrieved_chunks,
        )

    def build_source_responses(
        self,
        *,
        ingredient_id: UUID,
        sources: list[RetrievedChunk],
    ) -> list[IngredientExplainSourceResponse]:
        unique_sources: dict[tuple[str, str], IngredientExplainSourceResponse] = {}
        for chunk in sources:
            key = (chunk.source_path, chunk.section)
            if key in unique_sources:
                continue
            unique_sources[key] = IngredientExplainSourceResponse(
                ingredient_id=ingredient_id,
                ingredient_name=chunk.ingredient_name,
                source=f"{chunk.source_path}#{chunk.section}",
                excerpt=self._truncate(chunk.content),
            )
        return list(unique_sources.values())

    def _build_query(self, ingredient: Ingredient) -> str:
        parts = [
            ingredient.inci_name,
            ingredient.korean_name or "",
            "효능",
            "작용 원리",
            "주의사항",
            "추천 피부 타입",
        ]
        return " ".join(part.strip() for part in parts if part and part.strip())

    def _truncate(self, text: str, *, limit: int = 220) -> str:
        if len(text) <= limit:
            return text
        return f"{text[: limit - 1].rstrip()}…"
