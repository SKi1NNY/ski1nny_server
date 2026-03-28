from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any, Protocol, Sequence

from app.core.config import settings
from app.core.exceptions import ExternalServiceError
from app.core.vector_store import RetrievedChunk

SENTENCE_CLEANUP_PATTERN = re.compile(r"\s+")


@dataclass(slots=True)
class LLMGenerationResult:
    text: str


class LLMClient(Protocol):
    def generate_ingredient_explanation(
        self,
        *,
        ingredient_name: str,
        korean_name: str | None,
        query: str,
        retrieved_chunks: Sequence[RetrievedChunk],
    ) -> LLMGenerationResult:
        ...


class LocalTemplateLLMClient:
    def generate_ingredient_explanation(
        self,
        *,
        ingredient_name: str,
        korean_name: str | None,
        query: str,
        retrieved_chunks: Sequence[RetrievedChunk],
    ) -> LLMGenerationResult:
        del query

        sections = {chunk.section: chunk.content for chunk in retrieved_chunks}
        display_name = ingredient_name
        if korean_name:
            display_name = f"{ingredient_name}({korean_name})"

        sentences: list[str] = []
        efficacy = sections.get("효능")
        if efficacy:
            sentences.append(self._to_sentence(f"{display_name}는 {efficacy}", suffix="입니다"))

        mechanism = sections.get("작용 원리")
        if mechanism:
            sentences.append(self._to_sentence(f"작용 원리로는 {mechanism}", suffix="점이 제시됩니다"))

        caution = sections.get("주의사항")
        if caution:
            sentences.append(self._to_sentence(f"주의사항으로는 {caution}", suffix="내용이 있습니다"))

        recommended = sections.get("추천 피부 타입")
        if recommended:
            sentences.append(self._to_sentence(f"권장 피부 타입은 {recommended}", suffix="정도로 정리됩니다"))

        avoid = sections.get("비추천/주의 피부 타입")
        if avoid:
            sentences.append(self._to_sentence(f"주의가 필요한 피부 상태는 {avoid}", suffix="정도로 볼 수 있습니다"))

        usage_tip = sections.get("사용 팁")
        if usage_tip:
            sentences.append(self._to_sentence(f"사용 팁으로는 {usage_tip}", suffix="방법이 제안됩니다"))

        if not sentences:
            fallback = "검색된 근거 문서에서 설명에 사용할 핵심 문장을 추출하지 못했습니다."
            return LLMGenerationResult(text=fallback)

        return LLMGenerationResult(text=" ".join(sentences))

    def _to_sentence(self, text: str, *, suffix: str) -> str:
        normalized = SENTENCE_CLEANUP_PATTERN.sub(" ", text).strip().rstrip(". ")
        return f"{normalized} {suffix}."


class AnthropicLLMClient:
    def __init__(self, *, client: Any | None = None, model: str | None = None, timeout: float | None = None) -> None:
        self._client = client
        self._model = model or settings.anthropic_model
        self._timeout = timeout or settings.llm_timeout_seconds

    def generate_ingredient_explanation(
        self,
        *,
        ingredient_name: str,
        korean_name: str | None,
        query: str,
        retrieved_chunks: Sequence[RetrievedChunk],
    ) -> LLMGenerationResult:
        client = self._client or self._build_client()
        context = "\n\n".join(
            f"[{chunk.section}] {chunk.content}"
            for chunk in retrieved_chunks
        )
        ingredient_label = ingredient_name if not korean_name else f"{ingredient_name} ({korean_name})"
        prompt = (
            "아래 검색 문서만 근거로 화장품 성분 설명을 한국어로 작성하세요.\n"
            "문서에 없는 내용은 추측하지 마세요.\n"
            "응답은 3~5문장으로 작성하고, 효능과 주의사항을 함께 포함하세요.\n\n"
            f"성분: {ingredient_label}\n"
            f"사용자 질의: {query}\n\n"
            f"문서 근거:\n{context}"
        )
        try:
            response = client.messages.create(
                model=self._model,
                max_tokens=300,
                temperature=0,
                timeout=self._timeout,
                messages=[{"role": "user", "content": prompt}],
            )
        except Exception as exc:
            raise ExternalServiceError(
                "Anthropic LLM request failed.",
                detail={"provider": "anthropic", "model": self._model},
            ) from exc

        text = self._extract_text(response)
        if not text:
            raise ExternalServiceError(
                "Anthropic LLM returned an empty response.",
                detail={"provider": "anthropic", "model": self._model},
            )
        return LLMGenerationResult(text=text)

    def _build_client(self) -> Any:
        if not settings.anthropic_api_key:
            raise ExternalServiceError(
                "Anthropic API key is not configured.",
                detail={"provider": "anthropic"},
            )
        try:
            from anthropic import Anthropic
        except ImportError as exc:  # pragma: no cover - guarded by dependency installation
            raise ExternalServiceError(
                "Anthropic dependencies are not installed.",
                detail={"provider": "anthropic"},
            ) from exc
        return Anthropic(api_key=settings.anthropic_api_key)

    def _extract_text(self, response: Any) -> str:
        parts: list[str] = []
        for item in getattr(response, "content", []) or []:
            text = getattr(item, "text", None)
            if text:
                parts.append(str(text).strip())
        return "\n".join(part for part in parts if part).strip()


def get_llm_client() -> LLMClient:
    if settings.llm_provider == "anthropic":
        return AnthropicLLMClient()
    return LocalTemplateLLMClient()
