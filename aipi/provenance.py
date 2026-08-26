"""Pipeline provenance: the fingerprint that makes a published number reproducible.

A statistical agency does not publish a value, it publishes a *vintage*: the value
together with enough information to regenerate it exactly and to explain why it
differs from a previous release. Three things pin that down, and they are the whole
of this module:

  * **code version + git SHA** — which code produced it,
  * **config hash** — under which methodology parameters (base period, GEKS window,
    trimming thresholds, basket definition); change any and the number may move, so
    the hash must change with them,
  * **input row count** — how much data went in, so an unexplained fall in coverage
    is visible rather than silent.

`PipelineRun` travels with every published series. Two runs with the same
`config_hash` and `git_sha` on the same inputs must produce identical numbers; if
they do not, that is a bug, and the stamp is what makes the bug detectable.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
from dataclasses import dataclass
from datetime import UTC, datetime

from aipi import __version__
from aipi.basket import BASKET
from aipi.config import Settings, get_settings

#: Only these settings change the number. The database URL and API keys do not, so
#: they are deliberately excluded from the hash — otherwise every deployment would
#: report a different methodology fingerprint for identical methodology.
METHODOLOGY_FIELDS = (
    "base_period_days",
    "geks_window_days",
    "min_matched_items",
    "min_n_for_trim",
    "mad_trim_k",
)


def resolve_git_sha() -> str:
    """Best-effort git SHA: explicit env var first, then the repo, then 'unknown'.

    The env var (`AIPI_GIT_SHA`) is set by CI and by the container build, where no
    `.git` exists. Falling back to `git rev-parse` covers local runs. Returning
    'unknown' rather than raising means provenance degrades gracefully — a run with
    an unknown SHA is still a valid run, it is just less traceable, and that fact is
    itself recorded rather than hidden.
    """
    env_sha = os.environ.get("AIPI_GIT_SHA")
    if env_sha:
        return env_sha.strip()
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            timeout=3,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def methodology_fingerprint(settings: Settings | None = None) -> dict[str, object]:
    """The canonical, order-stable dict that the config hash is computed over."""
    settings = settings or get_settings()
    payload: dict[str, object] = {k: getattr(settings, k) for k in METHODOLOGY_FIELDS}
    # The basket definition is as much a part of the methodology as the numeric
    # parameters: change the routes or the brand family and the index changes.
    payload["basket"] = {
        "brand_family": BASKET.brand_family,
        "advance_windows": list(BASKET.advance_windows),
        "routes": list(BASKET.routes),
        "index_capture_slot_ist": BASKET.index_capture_slot_ist,
        "nonstop_only": BASKET.nonstop_only,
        "exclude_codeshare": BASKET.exclude_codeshare,
    }
    return payload


def config_hash(settings: Settings | None = None) -> str:
    """SHA-256 over the methodology fingerprint. Stable across runs and machines."""
    payload = methodology_fingerprint(settings)
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PipelineRun:
    """Immutable provenance stamp for one index computation."""

    code_version: str
    git_sha: str
    config_hash: str
    input_row_count: int
    index_eligible_rows: int
    created_at: datetime

    @property
    def run_id(self) -> str:
        """Short, deterministic id: same code + config + inputs -> same id.

        Derived rather than random so a re-run that should be identical *is*
        identical, which is exactly the property a revision audit needs.
        """
        material = f"{self.git_sha}:{self.config_hash}:{self.input_row_count}"
        return hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]

    def to_dict(self) -> dict:
        return {
            "run_id": self.run_id,
            "code_version": self.code_version,
            "git_sha": self.git_sha,
            "config_hash": self.config_hash,
            "input_row_count": self.input_row_count,
            "index_eligible_rows": self.index_eligible_rows,
            "created_at": self.created_at.isoformat(),
        }


def build_pipeline_run(
    *,
    input_row_count: int,
    index_eligible_rows: int,
    settings: Settings | None = None,
    created_at: datetime | None = None,
) -> PipelineRun:
    """Assemble the provenance stamp for a run.

    `created_at` is injectable so tests can pin it; production passes nothing and
    gets a UTC timestamp. Everything else is derived from code and configuration,
    not chosen, which is what makes the stamp trustworthy.
    """
    return PipelineRun(
        code_version=__version__,
        git_sha=resolve_git_sha(),
        config_hash=config_hash(settings),
        input_row_count=int(input_row_count),
        index_eligible_rows=int(index_eligible_rows),
        created_at=created_at or datetime.now(UTC),
    )
