from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class VLMProductResult(BaseModel):
    item_id: str
    original_product_name: str | None = None

    enhanced_title: str
    enhanced_description: str
    enhanced_category: str
    enhanced_subcategory: str
    product_type: str

    enhanced_colors: list[str] = Field(default_factory=list)
    enhanced_materials: list[str] = Field(default_factory=list)
    enhanced_style: str = "unknown"

    key_features: list[str] = Field(default_factory=list)
    visible_evidence: list[str] = Field(default_factory=list)
    catalog_evidence_used: list[str] = Field(
        default_factory=list
    )
    uncertainty_notes: list[str] = Field(
        default_factory=list
    )

    identity_confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    conflict_status: Literal[
        "aligned",
        "catalog_image_conflict",
        "uncertain",
    ]


class VLMValidationResult(BaseModel):
    valid: bool
    review_required: bool
    warnings: list[str] = Field(default_factory=list)


def create_mock_vlm_results() -> list[VLMProductResult]:
    """
    Deterministic results for testing graph behavior.

    This consumes no external LLM/VLM request.
    """

    return [
        VLMProductResult(
            item_id="product_headboard_001",
            original_product_name="Wooden Headboard",
            enhanced_title="Reclaimed Wood Headboard",
            enhanced_description=(
                "A reclaimed wood headboard featuring a natural "
                "wood appearance and a rectangular furniture "
                "profile. The supplied catalogue evidence identifies "
                "king and queen variants. Commercial and dimensional "
                "attributes remain governed by the verified catalogue "
                "record rather than visual inference."
            ),
            enhanced_category="Furniture",
            enhanced_subcategory="Bedroom Furniture",
            product_type="Headboard",
            enhanced_colors=["brown"],
            enhanced_materials=[],
            enhanced_style="rustic",
            key_features=[
                "Rectangular headboard profile",
                "Visible natural wood appearance",
            ],
            visible_evidence=[
                "Large rectangular furniture panel",
                "Brown wood-like surface",
            ],
            catalog_evidence_used=[
                "Wooden Headboard Only",
                "KING and QUEEN variants",
            ],
            uncertainty_notes=[
                "Exact wood species cannot be confirmed visually",
            ],
            identity_confidence=0.93,
            conflict_status="aligned",
        ),
        VLMProductResult(
            item_id="product_sculpture_002",
            original_product_name="Wooden Sculpture",
            enhanced_title="Decorative Pendant",
            enhanced_description=(
                "A small decorative object with a hanging pendant-like "
                "shape. The image suggests an ornamental accessory, "
                "although the verified catalogue identity describes "
                "the item as a wooden sculpture. The conflict requires "
                "human review before the enriched classification can "
                "be accepted."
            ),
            enhanced_category="Jewelry",
            enhanced_subcategory="Pendants",
            product_type="Pendant",
            enhanced_colors=["brown"],
            enhanced_materials=[],
            enhanced_style="decorative",
            key_features=[
                "Pendant-like visual shape",
            ],
            visible_evidence=[
                "Small hanging ornamental form",
            ],
            catalog_evidence_used=[
                "Original product name: Wooden Sculpture",
            ],
            uncertainty_notes=[
                "Visual classification conflicts with catalogue identity",
            ],
            identity_confidence=0.61,
            conflict_status="catalog_image_conflict",
        ),
    ]


def validate_vlm_results(
    results: list[VLMProductResult],
) -> VLMValidationResult:
    warnings: list[str] = []

    if not results:
        return VLMValidationResult(
            valid=False,
            review_required=True,
            warnings=["No VLM results were produced"],
        )

    for result in results:
        if result.conflict_status != "aligned":
            warnings.append(
                f"{result.item_id}: conflict status is "
                f"{result.conflict_status}"
            )

        if result.identity_confidence < 0.80:
            warnings.append(
                f"{result.item_id}: identity confidence "
                f"{result.identity_confidence:.2f} is below 0.80"
            )

        original_name = (
            result.original_product_name or ""
        ).lower()

        predicted_identity = " ".join(
            [
                result.enhanced_title,
                result.enhanced_category,
                result.enhanced_subcategory,
                result.product_type,
            ]
        ).lower()

        if (
            "sculpture" in original_name
            and "jewelry" in predicted_identity
        ):
            warnings.append(
                f"{result.item_id}: possible sculpture-to-jewelry "
                "misclassification"
            )

    # The VLM response is structurally valid even if an identity conflict
    # exists. Business approval still occurs in PIM.
    return VLMValidationResult(
        valid=True,
        review_required=True,
        warnings=warnings,
    )