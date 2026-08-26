"""Provenance: the fingerprint must be stable, sensitive to methodology, and derived."""

from __future__ import annotations

from datetime import UTC, datetime

from aipi.config import Settings
from aipi.provenance import (
    build_pipeline_run,
    config_hash,
    methodology_fingerprint,
    resolve_git_sha,
)


def test_config_hash_is_stable_across_calls() -> None:
    s = Settings()
    assert config_hash(s) == config_hash(s)


def test_config_hash_changes_with_methodology() -> None:
    a = Settings(geks_window_days=25)
    b = Settings(geks_window_days=28)
    # Change a parameter that moves the number -> the fingerprint must move too,
    # or a revision could never be explained by "the methodology changed".
    assert config_hash(a) != config_hash(b)


def test_config_hash_ignores_non_methodology_settings() -> None:
    a = Settings(database_url="postgresql+psycopg://a:a@h1/db")
    b = Settings(database_url="postgresql+psycopg://b:b@h2/db")
    # The DB URL does not change the index; identical methodology must hash identically
    # regardless of deployment.
    assert config_hash(a) == config_hash(b)


def test_fingerprint_includes_basket() -> None:
    fp = methodology_fingerprint(Settings())
    assert "basket" in fp
    assert fp["basket"]["brand_family"] == "SAVER"
    assert set(fp) >= {"base_period_days", "geks_window_days", "mad_trim_k", "basket"}


def test_env_var_overrides_git_sha(monkeypatch) -> None:
    monkeypatch.setenv("AIPI_GIT_SHA", "deadbeefcafe")
    assert resolve_git_sha() == "deadbeefcafe"


def test_run_id_is_deterministic() -> None:
    ts = datetime(2026, 8, 26, tzinfo=UTC)
    a = build_pipeline_run(input_row_count=100, index_eligible_rows=80, created_at=ts)
    b = build_pipeline_run(input_row_count=100, index_eligible_rows=80, created_at=ts)
    # Same code + config + input count -> same run_id. A re-run that should be
    # identical must be addressable as the same run.
    assert a.run_id == b.run_id


def test_run_id_changes_with_input_size() -> None:
    ts = datetime(2026, 8, 26, tzinfo=UTC)
    a = build_pipeline_run(input_row_count=100, index_eligible_rows=80, created_at=ts)
    b = build_pipeline_run(input_row_count=200, index_eligible_rows=80, created_at=ts)
    assert a.run_id != b.run_id
