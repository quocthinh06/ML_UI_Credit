"""Append-only dataset revisions and prediction runs; no overwrite of audit history."""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    UniqueConstraint,
)

metadata = MetaData()


def now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


datasets = Table(
    "datasets",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("name", String(255), nullable=False),
    Column("created_at", DateTime, default=now, nullable=False),
)
versions = Table(
    "dataset_versions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("dataset_id", ForeignKey("datasets.id"), nullable=False),
    Column("revision", Integer, nullable=False),
    Column("created_at", DateTime, default=now),
    UniqueConstraint("dataset_id", "revision"),
)
records = Table(
    "customer_records",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("version_id", ForeignKey("dataset_versions.id"), nullable=False, index=True),
    Column("customer_id", String(128), nullable=False),
    Column("inputs", JSON, nullable=False),
    UniqueConstraint("version_id", "customer_id"),
)
runs = Table(
    "prediction_runs",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("version_id", ForeignKey("dataset_versions.id"), nullable=False, index=True),
    Column("model_name", String(255), nullable=False),
    Column("model_version", String(128), nullable=False),
    Column("model_hash", String(64), nullable=False),
    Column("thresholds", JSON, nullable=False),
    Column("created_at", DateTime, default=now, nullable=False),
)
predictions = Table(
    "predictions",
    metadata,
    Column("id", Integer, primary_key=True),
    Column("run_id", ForeignKey("prediction_runs.id"), nullable=False, index=True),
    Column("record_id", ForeignKey("customer_records.id"), nullable=False, index=True),
    Column("raw_score", Float, nullable=False),
    Column("probability", Float, nullable=False),
    Column("default_label", Integer, nullable=False),
    Column("risk_level", String(16), nullable=False),
    UniqueConstraint("run_id", "record_id"),
)


def initialize(engine):
    metadata.create_all(engine)
