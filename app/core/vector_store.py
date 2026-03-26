from __future__ import annotations

from dataclasses import dataclass
from functools import cached_property
from pathlib import Path
import re
from typing import Protocol

TOKEN_PATTERN = re.compile(r"[0-9A-Za-z가-힣]+")
SECTION_PRIORITY = {
    "효능": 6,
    "작용 원리": 5,
    "주의사항": 4,
    "추천 피부 타입": 3,
    "비추천/주의 피부 타입": 2,
    "사용 팁": 1,
}
DEFAULT_KNOWLEDGE_BASE_DIR = Path(__file__).resolve().parents[2] / "knowledge_base" / "ingredients"


@dataclass(slots=True)
class RetrievedChunk:
    document_id: str
    ingredient_name: str
    section: str
    content: str
    source_path: str


class VectorStore(Protocol):
    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filter_ingredient: str | None = None,
    ) -> list[RetrievedChunk]:
        ...


class LocalKnowledgeBaseVectorStore:
    def __init__(self, *, knowledge_base_dir: Path | None = None) -> None:
        self.knowledge_base_dir = knowledge_base_dir or DEFAULT_KNOWLEDGE_BASE_DIR

    @cached_property
    def _chunks(self) -> tuple[RetrievedChunk, ...]:
        return tuple(self._load_chunks())

    def search(
        self,
        query: str,
        *,
        top_k: int = 5,
        filter_ingredient: str | None = None,
    ) -> list[RetrievedChunk]:
        query_tokens = set(self._tokenize(query))
        normalized_filter = self._normalize_text(filter_ingredient or "")

        scored: list[tuple[int, RetrievedChunk]] = []
        for chunk in self._chunks:
            if normalized_filter and not self._matches_ingredient_filter(chunk, normalized_filter):
                continue

            score = SECTION_PRIORITY.get(chunk.section, 0)
            haystack_tokens = set(
                self._tokenize(f"{chunk.ingredient_name} {chunk.section} {chunk.content} {chunk.document_id}")
            )
            score += len(query_tokens & haystack_tokens) * 5
            if normalized_filter and self._matches_ingredient_filter(chunk, normalized_filter):
                score += 50
            if score <= 0:
                continue
            scored.append((score, chunk))

        scored.sort(
            key=lambda item: (
                -item[0],
                item[1].ingredient_name.lower(),
                item[1].section,
                item[1].source_path,
            )
        )
        return [chunk for _, chunk in scored[:top_k]]

    def _load_chunks(self) -> list[RetrievedChunk]:
        if not self.knowledge_base_dir.exists():
            return []

        chunks: list[RetrievedChunk] = []
        for path in sorted(self.knowledge_base_dir.glob("*.md")):
            if path.name in {"README.md", "_template.md"}:
                continue
            title, sections = self._parse_document(path)
            relative_source = str(path.relative_to(path.parents[2]))
            for section, content in sections:
                if not content:
                    continue
                chunks.append(
                    RetrievedChunk(
                        document_id=path.stem,
                        ingredient_name=title,
                        section=section,
                        content=content,
                        source_path=relative_source,
                    )
                )
        return chunks

    def _parse_document(self, path: Path) -> tuple[str, list[tuple[str, str]]]:
        lines = path.read_text(encoding="utf-8").splitlines()
        title = path.stem.replace("-", " ").title()
        sections: list[tuple[str, str]] = []
        current_section: str | None = None
        buffer: list[str] = []

        for line in lines:
            stripped = line.strip()
            if stripped.startswith("# ") and title == path.stem.replace("-", " ").title():
                title = stripped[2:].strip()
                continue
            if stripped.startswith("## "):
                if current_section is not None:
                    sections.append((current_section, self._normalize_section_content(buffer)))
                current_section = stripped[3:].strip()
                buffer = []
                continue
            if current_section is not None:
                buffer.append(stripped)

        if current_section is not None:
            sections.append((current_section, self._normalize_section_content(buffer)))
        return title, sections

    def _normalize_section_content(self, lines: list[str]) -> str:
        parts: list[str] = []
        for line in lines:
            if not line:
                continue
            if line.startswith("- "):
                parts.append(line[2:].strip())
            else:
                parts.append(line)
        return " ".join(part for part in parts if part).strip()

    def _matches_ingredient_filter(self, chunk: RetrievedChunk, normalized_filter: str) -> bool:
        candidate_names = {
            self._normalize_text(chunk.ingredient_name),
            self._normalize_text(chunk.document_id.replace("-", " ")),
        }
        return normalized_filter in candidate_names

    def _tokenize(self, text: str) -> list[str]:
        return TOKEN_PATTERN.findall(text.lower())

    def _normalize_text(self, text: str) -> str:
        return " ".join(self._tokenize(text))


def get_vector_store() -> VectorStore:
    return LocalKnowledgeBaseVectorStore()
