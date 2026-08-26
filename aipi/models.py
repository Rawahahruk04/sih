"""Persistence schema (SQLAlchemy 2.0).

This is the production store. The API demo runs on an in-memory snapshot and needs
no database, but the schema is real, because the schema is where two
statistical-agency requirements live that a flat file cannot express:

  1. **Microdata with a correct identity.** `Observation.uq_observation` includes
     `flight_no`. A route/carrier flies ~20 departures a day; a unique key without
     the flight number collides and silently discards real observations. This is the
     §6.2/§8.2 contradiction in the PRD, resolved on the side of not losing data.

  2. **Vintages, not values.** `IndexValue` never overwrites. Republishing a
     (series, date) inserts a new row at `revision + 1` and flips `is_current`; the
     prior vintage is retained. Every published number therefore carries which run,
     which code, and which methodology produced it, and any later revision is a
     diff against a row that still exists — the difference between a statistic and a
     number that changed when you weren't looking.

Nothing here computes an index; the engine does that. This module only records what
was computed, with enough provenance to reproduce or audit it.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class PipelineRunRow(Base):
    """One index computation, with the provenance needed to reproduce it.

    Mirrors `aipi.provenance.PipelineRun`. `run_id` is derived (same code + config +
    inputs -> same id), so a re-run that should be identical collides on the primary
    key rather than creating a spurious second run.
    """

    __tablename__ = "pipeline_run"

    run_id: Mapped[str] = mapped_column(String(16), primary_key=True)
    code_version: Mapped[str] = mapped_column(String(32), nullable=False)
    git_sha: Mapped[str] = mapped_column(String(64), nullable=False)
    config_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    input_row_count: Mapped[int] = mapped_column(Integer, nullable=False)
    index_eligible_rows: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    index_values: Mapped[list[IndexValue]] = relationship(back_populates="run")


class Observation(Base):
    """One accepted, cleaned fare quote — the index microdata.

    Stores the flags the cleaning pipeline produced (`is_soldout`, `is_outlier`,
    `in_index_slot`) rather than a pre-filtered subset, so the index-eligible set can
    be re-derived and audited without re-running collection.
    """

    __tablename__ = "observation"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    capture_date: Mapped[date] = mapped_column(Date, nullable=False)
    capture_ts: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    travel_date: Mapped[date] = mapped_column(Date, nullable=False)
    advance_days: Mapped[int] = mapped_column(Integer, nullable=False)

    route_code: Mapped[str] = mapped_column(String(16), nullable=False)
    origin: Mapped[str] = mapped_column(String(4), nullable=False)
    destination: Mapped[str] = mapped_column(String(4), nullable=False)

    carrier: Mapped[str] = mapped_column(String(4), nullable=False)
    flight_no: Mapped[str] = mapped_column(String(12), nullable=False)
    brand_family: Mapped[str] = mapped_column(String(16), nullable=False)
    booking_class: Mapped[str] = mapped_column(String(4), nullable=False)
    cabin: Mapped[str] = mapped_column(String(16), nullable=False, default="ECONOMY")

    total_fare: Mapped[float | None] = mapped_column(Float, nullable=True)
    base_fare: Mapped[float | None] = mapped_column(Float, nullable=True)
    taxes: Mapped[float | None] = mapped_column(Float, nullable=True)
    # PS 26056 names taxes, user development fee and convenience charges as three
    # separate things. UDF is a FIXED airport charge and convenience is an OTA-only
    # commercial charge, so folding either into `taxes` would make a constant fee
    # look like it inflates with the fare. `fees` is the residual bucket.
    udf_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    convenience_fee: Mapped[float | None] = mapped_column(Float, nullable=True)
    fees: Mapped[float | None] = mapped_column(Float, nullable=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")

    item_key: Mapped[str] = mapped_column(String(64), nullable=False)
    source: Mapped[str] = mapped_column(String(24), nullable=False)
    #: 'real' | 'synthetic'. Queryable lineage, not a README footnote: a consumer
    #: must be able to ask "what fraction of this index is simulated" in SQL.
    data_mode: Mapped[str] = mapped_column(
        String(16), nullable=False, default="real", index=True
    )

    is_soldout: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_outlier: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    in_index_slot: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    split_is_imputed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    pipeline_run_id: Mapped[str | None] = mapped_column(
        ForeignKey("pipeline_run.run_id"), nullable=True
    )

    __table_args__ = (
        # The corrected dedup identity: flight_no is part of what makes two quotes
        # "the same offer". Without it, distinct departures collide.
        UniqueConstraint(
            "capture_date",
            "origin",
            "destination",
            "travel_date",
            "advance_days",
            "carrier",
            "flight_no",
            "brand_family",
            "booking_class",
            name="uq_observation_offer",
        ),
        # Lineage is binary and enforced at the storage layer, so an un-labelled
        # or mistyped row cannot reach a published index even if application code
        # regresses.
        CheckConstraint(
            "data_mode IN ('real', 'synthetic')", name="ck_observation_data_mode"
        ),
        # The decomposition must reconcile to the observed total. Stated as a DB
        # constraint because "the components add up" is an invariant of the data,
        # not a property of whichever code path happened to write the row.
        CheckConstraint(
            "total_fare IS NULL OR base_fare IS NULL OR taxes IS NULL OR "
            "ABS(COALESCE(base_fare,0) + COALESCE(taxes,0) + COALESCE(udf_fee,0) "
            "+ COALESCE(convenience_fee,0) + COALESCE(fees,0) - total_fare) <= 1.0",
            name="ck_observation_components_sum",
        ),
        Index("ix_observation_cell", "route_code", "advance_days", "capture_date"),
        Index("ix_observation_item", "item_key", "capture_date"),
    )


class RouteRow(Base):
    """The priced basket's route dimension. Mirrors `aipi.basket.SAMPLE_ROUTES`.

    Held in the database as well as in code because weights, DGCA reference data
    and the API's route metadata all need to join against it, and a route that
    exists in three places with three spellings is a reconciliation bug waiting
    to happen.
    """

    __tablename__ = "route"

    route_code: Mapped[str] = mapped_column(String(16), primary_key=True)
    origin: Mapped[str] = mapped_column(String(4), nullable=False)
    destination: Mapped[str] = mapped_column(String(4), nullable=False)
    display_name: Mapped[str] = mapped_column(String(64), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class RouteWeight(Base):
    """Base-period expenditure share per route, versioned by base period.

    Weights are NOT a mutable setting. Changing them changes what the index
    measures, so a new weight set is a new `base_period` row rather than an
    UPDATE — the same append-only discipline `IndexValue` uses for values.
    """

    __tablename__ = "route_weight"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    base_period: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    route_code: Mapped[str] = mapped_column(
        ForeignKey("route.route_code"), nullable=False
    )

    #: The DGCA inputs the weight was derived from, retained so the derivation is
    #: auditable rather than a bare number of unknown provenance.
    passengers: Mapped[float] = mapped_column(Float, nullable=False)
    base_avg_fare: Mapped[float] = mapped_column(Float, nullable=False)
    #: p0*q0 / sum(p0*q0). Expenditure share, never passenger share.
    weight: Mapped[float] = mapped_column(Float, nullable=False)

    source_note: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    is_placeholder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("base_period", "route_code", name="uq_route_weight"),
    )


class WindowConfig(Base):
    """Advance-purchase windows as data. Mirrors `aipi.basket.WINDOW_CONFIG`."""

    __tablename__ = "window_config"

    advance_days: Mapped[int] = mapped_column(Integer, primary_key=True)
    #: False for the five PS-mandated windows; True for optional extra coverage.
    is_extended: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    #: Booking-share weight used in window aggregation. Uniform is a documented
    #: fallback, recorded as such rather than assumed.
    booking_weight: Mapped[float | None] = mapped_column(Float, nullable=True)
    note: Mapped[str] = mapped_column(String(128), nullable=False, default="")


class DgcaReference(Base):
    """DGCA published monthly average fares — the EXTERNAL validation target.

    Structurally isolated on purpose. This table is read ONLY by
    `aipi.validation`, never by the index engine, because an index that has seen
    its own validation target is not validated by it. `tests/test_dgca_isolation`
    asserts the separation holds rather than trusting this comment.
    """

    __tablename__ = "dgca_reference"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    period: Mapped[str] = mapped_column(String(7), nullable=False)  # YYYY-MM
    route_code: Mapped[str] = mapped_column(String(16), nullable=False)
    avg_fare: Mapped[float] = mapped_column(Float, nullable=False)
    passengers: Mapped[float | None] = mapped_column(Float, nullable=True)

    source_note: Mapped[str] = mapped_column(String(256), nullable=False, default="")
    is_placeholder: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    __table_args__ = (
        UniqueConstraint("period", "route_code", name="uq_dgca_reference"),
    )


class IndexValue(Base):
    """One published index point, as a vintage. Append-only.

    A "series" is any published line: 'headline', 'headline_dow_adjusted',
    'route:DEL-BOM', or 'leadtime:7'. Keeping them in one table with a `series`
    discriminator means the vintage machinery is written once and every published
    line inherits it.

    `freq` carries the PS-mandated daily/weekly/monthly split. Weekly and monthly
    rows are DERIVED from the daily series by chaining, and carry the same
    `pipeline_run_id`, so the derivation can always be re-checked against the
    daily rows it came from.
    """

    __tablename__ = "index_value"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    series: Mapped[str] = mapped_column(String(48), nullable=False)
    freq: Mapped[str] = mapped_column(String(8), nullable=False, default="daily")
    index_date: Mapped[date] = mapped_column(Date, nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)

    # The statistical accompaniment. A value without these is not publishable.
    n_obs: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    matched_n: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    coverage_pct: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    base_period_start: Mapped[date | None] = mapped_column(Date, nullable=True)
    base_period_end: Mapped[date | None] = mapped_column(Date, nullable=True)

    # Vintage control.
    revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    published_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    pipeline_run_id: Mapped[str] = mapped_column(
        ForeignKey("pipeline_run.run_id"), nullable=False
    )
    run: Mapped[PipelineRunRow] = relationship(back_populates="index_values")

    #: Share of contributing observations that were real (vs synthetic). Stored
    #: per published point so a consumer can filter on lineage without
    #: recomputing it, and so a series that silently drifted from synthetic to
    #: real (or back) is visible in the data itself.
    real_data_share: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)

    __table_args__ = (
        # Each (series, freq, date) may be published many times, but each revision
        # number is unique. This is what makes "revision 2 of 2026-07-01 daily
        # headline" a single, addressable, immutable fact.
        UniqueConstraint(
            "series", "freq", "index_date", "revision", name="uq_index_value_vintage"
        ),
        CheckConstraint(
            "freq IN ('daily', 'weekly', 'monthly')", name="ck_index_value_freq"
        ),
        Index("ix_index_value_current", "series", "freq", "index_date", "is_current"),
    )
