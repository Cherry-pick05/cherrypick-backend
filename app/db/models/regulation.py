from datetime import datetime

from sqlalchemy import (
    TIMESTAMP,
    String,
    Text,
    Enum,
    JSON,
    Index,
    func,
    ForeignKey,
    Numeric,
    Date,
    SmallInteger,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.db.types import BIGINT


class RuleSet(Base):
    __tablename__ = "rule_sets"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(Enum("international", "country", "airline", name="rule_scope"))
    code: Mapped[str] = mapped_column(String(64))
    name: Mapped[str] = mapped_column(String(255))
    source_url: Mapped[str | None] = mapped_column(Text)
    source_etag: Mapped[str | None] = mapped_column(String(255))
    imported_at: Mapped[datetime] = mapped_column(TIMESTAMP(timezone=False), server_default=func.now())

    __table_args__ = (Index("uq_ruleset_scope_code", "scope", "code", unique=True),)

    item_rules: Mapped[list["ItemRule"]] = relationship(back_populates="rule_set", cascade="all, delete-orphan")


class ItemRule(Base):
    __tablename__ = "item_rules"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    rule_set_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("rule_sets.id", ondelete="CASCADE"))
    item_name: Mapped[str | None] = mapped_column(String(255))
    item_category: Mapped[str] = mapped_column(String(64))
    severity: Mapped[str] = mapped_column(Enum("info", "warn", "block", name="rule_severity"))
    notes: Mapped[str | None] = mapped_column(Text)

    rule_set: Mapped[RuleSet] = relationship(back_populates="item_rules")
    applicabilities: Mapped[list["Applicability"]] = relationship(back_populates="item_rule", cascade="all, delete-orphan")


class Applicability(Base):
    __tablename__ = "applicability"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    item_rule_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("item_rules.id", ondelete="CASCADE"))
    route_type: Mapped[str | None] = mapped_column(Enum("domestic", "international", name="route_type"))
    region: Mapped[str | None] = mapped_column(String(64))
    cabin_class: Mapped[str | None] = mapped_column(String(32))
    fare_class: Mapped[str | None] = mapped_column(String(32))
    passenger_type: Mapped[str | None] = mapped_column(String(32))
    effective_from: Mapped[datetime | None] = mapped_column(Date)
    effective_until: Mapped[datetime | None] = mapped_column(Date)

    __table_args__ = (
        Index(
            "uq_app_scope",
            "item_rule_id",
            "route_type",
            "region",
            "cabin_class",
            "fare_class",
            "passenger_type",
            "effective_from",
            "effective_until",
            unique=True,
        ),
        Index("idx_app_region", "region"),
        Index("idx_app_cabin", "cabin_class"),
        Index("idx_app_fare", "fare_class"),
    )

    item_rule: Mapped[ItemRule] = relationship(back_populates="applicabilities")
    constraints: Mapped[list["ConstraintsQuant"]] = relationship(
        back_populates="applicability", cascade="all, delete-orphan"
    )


class ConstraintsQuant(Base):
    __tablename__ = "constraints_quant"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    applicability_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("applicability.id", ondelete="CASCADE"))

    max_weight_kg: Mapped[float | None] = mapped_column(Numeric(6, 2))
    per_piece_max_weight_kg: Mapped[float | None] = mapped_column(Numeric(6, 2))
    max_pieces: Mapped[int | None] = mapped_column(SmallInteger)
    max_total_cm: Mapped[int | None] = mapped_column(SmallInteger)
    size_length_cm: Mapped[int | None] = mapped_column(SmallInteger)
    size_width_cm: Mapped[int | None] = mapped_column(SmallInteger)
    size_height_cm: Mapped[int | None] = mapped_column(SmallInteger)

    max_container_ml: Mapped[int | None] = mapped_column(SmallInteger)
    max_total_bag_l: Mapped[float | None] = mapped_column(Numeric(5, 2))
    lithium_ion_max_wh: Mapped[int | None] = mapped_column(SmallInteger)
    lithium_metal_g: Mapped[float | None] = mapped_column(Numeric(6, 2))
    max_weight_per_person_kg: Mapped[float | None] = mapped_column(Numeric(6, 2))

    operator_approval_required: Mapped[bool | None] = mapped_column(SmallInteger)
    carry_on_allowed: Mapped[bool | None] = mapped_column(SmallInteger)
    checked_allowed: Mapped[bool | None] = mapped_column(SmallInteger)
    on_person_allowed: Mapped[bool | None] = mapped_column(SmallInteger)

    ext: Mapped[dict] = mapped_column(JSON, default=dict)

    applicability: Mapped[Applicability] = relationship(back_populates="constraints")
    extras: Mapped[list["ConstraintExtra"]] = relationship(back_populates="constraint", cascade="all, delete-orphan")

    __table_args__ = (
        Index("idx_constr_allow", "carry_on_allowed", "checked_allowed"),
        Index("idx_constr_pieces", "max_pieces"),
        Index("idx_constr_size", "max_total_cm", "size_length_cm", "size_width_cm", "size_height_cm"),
        Index("idx_constr_battery", "lithium_ion_max_wh", "lithium_metal_g"),
        Index("idx_constr_liquid", "max_container_ml", "max_total_bag_l"),
    )


class ConstraintExtra(Base):
    __tablename__ = "constraint_extras"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    constraints_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("constraints_quant.id", ondelete="CASCADE"))
    extra_type: Mapped[str] = mapped_column(Enum("additional_item", "allowed_item", "exception", name="extra_type"))
    label: Mapped[str] = mapped_column(String(64))
    details: Mapped[dict] = mapped_column(JSON, default=dict)

    constraint: Mapped[ConstraintsQuant] = relationship(back_populates="extras")

    __table_args__ = (Index("idx_extra_type", "extra_type", "label"),)


class Taxonomy(Base):
    __tablename__ = "taxonomy"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    canonical_key: Mapped[str] = mapped_column(String(128))
    category: Mapped[str] = mapped_column(String(64))
    display_name: Mapped[str | None] = mapped_column(String(64))
    is_active: Mapped[bool] = mapped_column(SmallInteger, server_default=text("1"))

    __table_args__ = (
        Index("uq_taxo_key", "canonical_key", unique=True),
        Index("idx_taxo_cat", "category"),
    )

    synonyms: Mapped[list["TaxonomySynonym"]] = relationship(back_populates="taxonomy", cascade="all, delete-orphan")


class TaxonomySynonym(Base):
    __tablename__ = "taxonomy_synonym"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    taxonomy_id: Mapped[int] = mapped_column(BIGINT, ForeignKey("taxonomy.id", ondelete="CASCADE"))
    synonym: Mapped[str] = mapped_column(String(128))
    lang: Mapped[str | None] = mapped_column(String(8))
    priority: Mapped[int] = mapped_column(SmallInteger, server_default=text("0"))
    match_type: Mapped[str] = mapped_column(
        Enum("exact", "substring", "regex", name="synonym_match_type"),
        server_default="substring",
    )

    taxonomy: Mapped[Taxonomy] = relationship(back_populates="synonyms")

    __table_args__ = (
        Index("uq_synonym", "synonym", "match_type", unique=True),
        Index("idx_synonym", "synonym"),
    )


class PrecedencePolicy(Base):
    __tablename__ = "precedence_policy"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    policy_json: Mapped[dict] = mapped_column(JSON)

    __table_args__ = (Index("uq_policy_name", "name", unique=True),)


class RegulationMatch(Base):
    __tablename__ = "regulation_matches"

    id: Mapped[int] = mapped_column(BIGINT, primary_key=True, autoincrement=True)
    status: Mapped[str | None] = mapped_column(Enum("allow", "ban", "limited", name="match_status"))
    user_id: Mapped[int | None] = mapped_column(BIGINT, ForeignKey("users.user_id"))
    trip_id: Mapped[int | None] = mapped_column(BIGINT, ForeignKey("trips.trip_id"))
    image_id: Mapped[int | None] = mapped_column(BIGINT, ForeignKey("item_images.image_id"))
    item_rule_id: Mapped[int | None] = mapped_column(BIGINT, ForeignKey("item_rules.id", ondelete="SET NULL"))
    req_id: Mapped[str | None] = mapped_column(String(64))
    raw_label: Mapped[str | None] = mapped_column(String(256))
    norm_label: Mapped[str | None] = mapped_column(String(256))
    canonical_key: Mapped[str | None] = mapped_column(String(64), index=True)
    candidates_json: Mapped[dict | list | None] = mapped_column(JSON)
    details: Mapped[dict | None] = mapped_column(JSON)
    confidence: Mapped[float | None] = mapped_column(Numeric(5, 4))
    decided_by: Mapped[str] = mapped_column(
        Enum(
            "auto",
            "user",
            "llm_classifier",
            "dict_classifier",
            "tiebreak_llm",
            "admin_rule",
            name="match_decider",
        ),
        server_default="auto",
    )
    model_info: Mapped[dict | None] = mapped_column(JSON)
    source: Mapped[str | None] = mapped_column(Enum("detect", "ocr", "manual", name="match_source"))
    created_at: Mapped[datetime | None] = mapped_column(TIMESTAMP)
    matched_at: Mapped[datetime | None] = mapped_column(TIMESTAMP, server_default=func.now())

    __table_args__ = (
        Index("ix_matches_user_trip_time", "user_id", "trip_id", "matched_at"),
        {"sqlite_autoincrement": True},
    )

    bag_items: Mapped[list["BagItem"]] = relationship("BagItem", back_populates="regulation_match")

