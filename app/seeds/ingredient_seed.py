from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.ingredient import ConflictSeverity, Ingredient, IngredientAlias, IngredientConflict


DATA_DIR = Path(__file__).resolve().parent / "data"


def _load_json(path: Path) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))


def seed_ingredient_domain(session: Session, data_dir: Path | None = None) -> dict[str, int]:
    seed_dir = data_dir or DATA_DIR
    ingredient_rows = _load_json(seed_dir / "ingredients.json")
    alias_rows = _load_json(seed_dir / "ingredient_aliases.json")
    conflict_rows = _load_json(seed_dir / "ingredient_conflicts.json")

    ingredient_map: dict[str, Ingredient] = {}
    created_counts = {
        "ingredients": 0,
        "aliases": 0,
        "conflicts": 0,
    }

    for row in ingredient_rows:
        stmt = select(Ingredient).where(Ingredient.inci_name == row["inci_name"])
        ingredient = session.scalar(stmt)
        if ingredient is None:
            ingredient = Ingredient(**row)
            session.add(ingredient)
            created_counts["ingredients"] += 1
        ingredient_map[row["inci_name"]] = ingredient

    session.flush()

    for row in alias_rows:
        ingredient = ingredient_map[row["ingredient_inci_name"]]
        stmt = select(IngredientAlias).where(
            IngredientAlias.ingredient_id == ingredient.id,
            IngredientAlias.alias_name == row["alias_name"],
        )
        alias = session.scalar(stmt)
        if alias is None:
            session.add(
                IngredientAlias(
                    ingredient_id=ingredient.id,
                    alias_name=row["alias_name"],
                    language=row.get("language", "ko"),
                )
            )
            created_counts["aliases"] += 1

    session.flush()

    for row in conflict_rows:
        ingredient_a = ingredient_map[row["ingredient_a_inci_name"]]
        ingredient_b = ingredient_map[row["ingredient_b_inci_name"]]
        ordered_ids = sorted([ingredient_a.id, ingredient_b.id], key=lambda value: value.int)
        stmt = select(IngredientConflict).where(
            IngredientConflict.ingredient_a_id == ordered_ids[0],
            IngredientConflict.ingredient_b_id == ordered_ids[1],
        )
        conflict = session.scalar(stmt)
        if conflict is None:
            session.add(
                IngredientConflict(
                    ingredient_a_id=ordered_ids[0],
                    ingredient_b_id=ordered_ids[1],
                    severity=ConflictSeverity(row["severity"]),
                    reason=row["reason"],
                )
            )
            created_counts["conflicts"] += 1

    session.commit()
    return created_counts


def main() -> None:
    with SessionLocal() as session:
        counts = seed_ingredient_domain(session)
    print(counts)


if __name__ == "__main__":
    main()
