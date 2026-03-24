from __future__ import annotations

from app.core.ocr_client import OCRResult
from app.models.ingredient import ConflictSeverity, Ingredient, IngredientAlias, IngredientConflict
from app.models.user import SkinType, User
from app.services.scan_service import ScanService
from app.services.user_profile_service import UserProfileService


class FakeOCRClient:
    def __init__(self, text: str, confidence_score: float) -> None:
        self.text = text
        self.confidence_score = confidence_score

    def extract_text(self, image_bytes: bytes, filename: str | None = None) -> OCRResult:
        return OCRResult(text=self.text, confidence_score=self.confidence_score)


def _create_user(db_session):
    user = User(email="scan-service@example.com", password_hash="hashed")
    db_session.add(user)
    db_session.flush()
    return user


def _create_ingredient(db_session, inci_name: str, alias_name: str | None = None):
    ingredient = Ingredient(inci_name=inci_name, korean_name=inci_name)
    db_session.add(ingredient)
    db_session.flush()

    if alias_name:
        db_session.add(
            IngredientAlias(
                ingredient_id=ingredient.id,
                alias_name=alias_name,
                language="ko",
            )
        )
        db_session.flush()

    return ingredient


def _create_conflict(db_session, ingredient_a, ingredient_b, severity: ConflictSeverity, reason: str):
    ordered = sorted([ingredient_a, ingredient_b], key=lambda item: item.id.int)
    db_session.add(
        IngredientConflict(
            ingredient_a_id=ordered[0].id,
            ingredient_b_id=ordered[1].id,
            severity=severity,
            reason=reason,
        )
    )
    db_session.flush()


def test_scan_service_maps_aliases_and_preserves_raw_text(db_session):
    user = _create_user(db_session)
    niacinamide = _create_ingredient(db_session, "Niacinamide", alias_name="나이아신아마이드")
    retinol = _create_ingredient(db_session, "Retinol")
    _create_conflict(
        db_session,
        niacinamide,
        retinol,
        ConflictSeverity.HIGH,
        "These ingredients should not be combined.",
    )
    UserProfileService().upsert_profile(
        db_session,
        user_id=user.id,
        skin_type=SkinType.SENSITIVE,
        skin_concerns=["redness"],
        notes="scan-validation",
    )

    service = ScanService(FakeOCRClient("나이아신아마이드, Unknown 123, Retinol (0.1%)", 0.95))

    result = service.scan_ingredients(
        db_session,
        user_id=user.id,
        image_bytes=b"fake-image-bytes",
        filename="scan.txt",
    )

    assert result.raw_ocr_text == "나이아신아마이드, Unknown 123, Retinol (0.1%)"
    assert result.fallback is None
    assert [item.normalized_name for item in result.recognized_ingredients] == [
        "Niacinamide",
        "Unknown",
        "Retinol",
    ]
    assert result.recognized_ingredients[0].ingredient_id == niacinamide.id
    assert result.unmapped_ingredients == ["Unknown"]
    assert result.validation is not None
    assert result.validation.is_safe is False
    assert result.validation.severity == ConflictSeverity.HIGH
    assert len(result.validation.conflicts) == 1


def test_scan_service_merges_wrapped_korean_tokens_and_strips_header(db_session):
    user = _create_user(db_session)
    _create_ingredient(db_session, "Water", alias_name="정제수")
    _create_ingredient(db_session, "Arbutin", alias_name="알부틴")
    _create_ingredient(db_session, "Tocopheryl Acetate", alias_name="토코페릴아세테이트")
    _create_ingredient(db_session, "1,2-Hexanediol", alias_name="1,2-헥산디올")
    _create_ingredient(
        db_session,
        "Cetyl PEG/PPG-10/1 Dimethicone",
        alias_name="세틸피이지/피피지-10/1디메치콘",
    )

    service = ScanService(
        FakeOCRClient(
            "[전성분] 정제수, 알부\n틴, 토\n코페릴아세테이트, 1\n,2-헥산디올, 세틸피이지/피피지-10/1디메치콘",
            0.96,
        )
    )

    result = service.scan_ingredients(
        db_session,
        user_id=user.id,
        image_bytes=b"fake-image-bytes",
        filename="wrapped-korean.txt",
    )

    assert [item.raw_name for item in result.recognized_ingredients] == [
        "정제수",
        "알부틴",
        "토코페릴아세테이트",
        "1,2-헥산디올",
        "세틸피이지/피피지-10/1디메치콘",
    ]
    assert [item.normalized_name for item in result.recognized_ingredients] == [
        "Water",
        "Arbutin",
        "Tocopheryl Acetate",
        "1,2-Hexanediol",
        "Cetyl PEG/PPG-10/1 Dimethicone",
    ]
    assert result.unmapped_ingredients == []


def test_scan_service_splits_adjacent_wrapped_aliases_without_delimiter(db_session):
    user = _create_user(db_session)
    _create_ingredient(
        db_session,
        "4-Methylbenzylidene Camphor",
        alias_name="4-메칠벤질리덴캠퍼",
    )
    _create_ingredient(
        db_session,
        "Cetyl PEG/PPG-10/1 Dimethicone",
        alias_name="세틸피이지/피피지-10/1디메치콘",
    )

    service = ScanService(
        FakeOCRClient(
            "[전성분] 4-메칠벤질리덴캠퍼\n세틸피이지/피피지-10/1디메치콘",
            0.94,
        )
    )

    result = service.scan_ingredients(
        db_session,
        user_id=user.id,
        image_bytes=b"fake-image-bytes",
        filename="adjacent-korean.txt",
    )

    assert [item.raw_name for item in result.recognized_ingredients] == [
        "4-메칠벤질리덴캠퍼",
        "세틸피이지/피피지-10/1디메치콘",
    ]
    assert [item.normalized_name for item in result.recognized_ingredients] == [
        "4-Methylbenzylidene Camphor",
        "Cetyl PEG/PPG-10/1 Dimethicone",
    ]
    assert result.unmapped_ingredients == []


def test_scan_service_returns_fallback_for_low_confidence(db_session):
    user = _create_user(db_session)
    _create_ingredient(db_session, "Niacinamide")

    service = ScanService(FakeOCRClient("Niacinamide", 0.42))

    result = service.scan_ingredients(
        db_session,
        user_id=user.id,
        image_bytes=b"fake-image-bytes",
        filename="scan.txt",
    )

    assert result.fallback is not None
    assert result.fallback.requires_manual_input is True
    assert result.confidence_score == 0.42
    assert result.recognized_ingredients[0].normalized_name == "Niacinamide"
