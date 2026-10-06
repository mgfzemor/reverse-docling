"""Pydantic models for identities, generation requests and manifest records."""

from __future__ import annotations

import datetime as dt
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .locales import LANGUAGES


class Address(BaseModel):
    street: str | None = None
    building_number: str | None = None
    city: str | None = None
    state: str | None = None
    postcode: str | None = None
    country: str | None = None

    def one_line(self) -> str:
        parts = [f"{self.street or ''} {self.building_number or ''}".strip(), self.city,
                 self.state, self.postcode, self.country]
        return ", ".join(p for p in parts if p)


class Identity(BaseModel):
    """A persona. Any field left empty is filled by Faker for the target language."""

    full_name: str | None = None
    given_name: str | None = None
    family_name: str | None = None
    latin_name: str | None = None  # transliteration, used on travel documents
    gender: Literal["male", "female"] | None = None
    date_of_birth: dt.date | None = None
    place_of_birth: str | None = None
    nationality: str | None = None
    address: Address = Field(default_factory=Address)
    phone: str | None = None
    email: str | None = None
    id_number: str | None = None
    passport_number: str | None = None
    father_name: str | None = None
    mother_name: str | None = None
    employer: str | None = None
    job_title: str | None = None
    iban: str | None = None
    account_number: str | None = None


class IdentitySpec(Identity):
    mode: Literal["manual", "random"] = "random"


class DocumentSelection(BaseModel):
    type: str
    templates: Literal["all"] | list[str] = "all"


class OutputSpec(BaseModel):
    format: Literal["pdf", "images"] = "pdf"
    image_format: Literal["png", "jpg"] = "png"
    dpi: int = Field(150, ge=50, le=600)
    dir: str = "out"


DegradationPreset = Literal["none", "light", "medium", "heavy"]


class DegradationSpec(BaseModel):
    preset: DegradationPreset = "none"
    probability: float = Field(1.0, ge=0.0, le=1.0)
    # Explicit overrides; each value is a [min, max] range sampled per page.
    overrides: dict[str, tuple[float, float]] = Field(default_factory=dict)


class GenerationRequest(BaseModel):
    seed: int = 0
    identity: IdentitySpec = Field(default_factory=IdentitySpec)
    count_per_combination: int = Field(1, ge=1, le=10_000)
    documents: list[DocumentSelection]
    languages: list[str] = Field(default_factory=lambda: ["en"])
    output: OutputSpec = Field(default_factory=OutputSpec)
    degradation: DegradationSpec = Field(default_factory=DegradationSpec)
    specimen_watermark: bool = False

    @field_validator("languages")
    @classmethod
    def _known_languages(cls, v: list[str]) -> list[str]:
        unknown = [code for code in v if code not in LANGUAGES]
        if unknown:
            raise ValueError(f"Unknown languages {unknown}. Available: {list(LANGUAGES)}")
        return v


class ManifestRecord(BaseModel):
    id: str
    doc_type: str
    template: str
    language: str
    files: list[str]
    pages: int
    seed: int
    identity_id: str
    identity: dict[str, Any]
    fields: dict[str, Any]
    degradation: list[dict[str, Any]] | None = None
