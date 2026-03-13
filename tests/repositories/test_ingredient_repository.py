from __future__ import annotations

from app.models.ingredient import ConflictSeverity, Ingredient, IngredientAlias, IngredientConflict
from app.repositories.ingredient_repository import IngredientRepository


def _seed_ingredients(db_session):
    niacinamide = Ingredient(
        inci_name="Niacinamide",
        korean_name="나이아신아마이드",
        category="Brightening",
    )
    retinol = Ingredient(
        inci_name="Retinol",
        korean_name="레티놀",
        category="Anti-aging",
    )
    glycolic_acid = Ingredient(
        inci_name="Glycolic Acid",
        korean_name="글리콜릭애씨드",
        category="Exfoliant",
    )
    db_session.add_all([niacinamide, retinol, glycolic_acid])
    db_session.flush()

    db_session.add_all(
        [
            IngredientAlias(
                ingredient_id=niacinamide.id,
                alias_name="나이아신아마이드",
                language="ko",
            ),
            IngredientAlias(
                ingredient_id=retinol.id,
                alias_name="레티놀",
                language="ko",
            ),
        ]
    )
    db_session.add(
        IngredientConflict(
            ingredient_a_id=sorted([glycolic_acid.id, retinol.id], key=lambda value: value.int)[0],
            ingredient_b_id=sorted([glycolic_acid.id, retinol.id], key=lambda value: value.int)[1],
            severity=ConflictSeverity.HIGH,
            reason="테스트용 충돌 데이터",
        )
    )
    db_session.commit()
    return niacinamide, retinol, glycolic_acid


def test_get_by_inci_name_returns_ingredient(db_session):
    repository = IngredientRepository()
    niacinamide, _, _ = _seed_ingredients(db_session)

    found = repository.get_by_inci_name(db_session, "niacinamide")

    assert found is not None
    assert found.id == niacinamide.id


def test_map_aliases_returns_standard_ingredients(db_session):
    repository = IngredientRepository()
    niacinamide, retinol, _ = _seed_ingredients(db_session)

    mappings = repository.map_aliases(db_session, ["나이아신아마이드", "레티놀", "없는성분"])

    assert mappings["나이아신아마이드"].id == niacinamide.id
    assert mappings["레티놀"].id == retinol.id
    assert "없는성분" not in mappings


def test_get_conflicts_for_ingredient_ids_supports_bidirectional_lookup(db_session):
    repository = IngredientRepository()
    _, retinol, glycolic_acid = _seed_ingredients(db_session)

    conflicts = repository.get_conflicts_for_ingredient_ids(
        db_session,
        [retinol.id, glycolic_acid.id],
    )

    assert len(conflicts) == 1
    conflict = conflicts[0]
    assert {conflict.ingredient_a_id, conflict.ingredient_b_id} == {retinol.id, glycolic_acid.id}
    assert conflict.severity is ConflictSeverity.HIGH


def test_search_returns_alias_match_metadata(db_session):
    repository = IngredientRepository()
    niacinamide, _, _ = _seed_ingredients(db_session)

    hits = repository.search(db_session, "나이아신")

    assert len(hits) == 1
    assert hits[0].ingredient.id == niacinamide.id
    assert hits[0].matched_alias == "나이아신아마이드"
