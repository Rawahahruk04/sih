"""The index engine must never see its own validation target.

An index that was fitted, calibrated, or even filtered against DGCA figures is
not validated by a comparison to DGCA — it is being marked against its own
homework. `aipi/models.py` states this isolation in a docstring; this file
asserts it, because a comment does not survive a refactor and a test does.

Two independent checks, because they fail differently:

  * **Import-graph**: nothing under `aipi.index` or `aipi.cleaning` may import
    `aipi.validation` or reference `DgcaReference`. Catches the accidental
    convenience import.
  * **Executable-code scan**: no identifier or string LITERAL in those packages
    may name the DGCA table. Catches a hand-rolled query that no import would
    reveal.

What is deliberately NOT forbidden
-----------------------------------
Prose in comments and docstrings explaining that base-period WEIGHTS derive from
DGCA passenger traffic. That is not contamination and the distinction matters:

  * DGCA *passenger volumes* -> base-period quantity q_r0 -> a fixed weight.
    This is ordinary CPI practice; every CPI weights its basket from an external
    expenditure survey, and a fixed scalar cannot leak the target's subsequent
    movements into the index.
  * DGCA *fare series* -> the index's prices. THIS would be circular, because the
    validation compares movements and the index would already contain them.

The first is fine and documented; the second is what these tests forbid. Note the
residual dependency honestly: `expenditure_weights` accepts a `base_avg_fare`
which MAY be sourced from DGCA. That is a base-period level only, held fixed, so
it does not transmit DGCA's month-to-month movement — but it is a dependency, and
`aipi.validation.backtest` should keep stating which months it was drawn from.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

PACKAGE_ROOT = Path(__file__).resolve().parent.parent / "aipi"

#: Packages that compute the index. None of them may know DGCA exists.
INDEX_SIDE = ("index", "cleaning")

#: Modules and names that would indicate contamination.
FORBIDDEN_IMPORTS = ("aipi.validation", "dgca_reference")
FORBIDDEN_NAMES = ("DgcaReference",)


def _python_files(package: str) -> list[Path]:
    return sorted((PACKAGE_ROOT / package).rglob("*.py"))


def _imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found.update(f"{node.module}.{a.name}" for a in node.names)
    return found


@pytest.mark.parametrize("package", INDEX_SIDE)
def test_index_side_never_imports_validation(package: str) -> None:
    offenders: list[str] = []
    for path in _python_files(package):
        imports = _imported_modules(path)
        for imported in imports:
            if any(bad in imported for bad in FORBIDDEN_IMPORTS):
                offenders.append(f"{path.name} imports {imported}")
            if any(imported.endswith(name) for name in FORBIDDEN_NAMES):
                offenders.append(f"{path.name} imports {imported}")
    assert not offenders, (
        "The index engine imported its own validation target. A DGCA-aware index "
        "cannot be validated against DGCA:\n  " + "\n  ".join(offenders)
    )


def _docstring_nodes(tree: ast.AST) -> set[int]:
    """id() of every string node that is a docstring, so prose can be excluded."""
    out: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            body = getattr(node, "body", [])
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                out.add(id(body[0].value))
    return out


@pytest.mark.parametrize("package", INDEX_SIDE)
def test_index_side_never_queries_dgca(package: str) -> None:
    """No DGCA identifier or string literal in EXECUTABLE code.

    Comments and docstrings are excluded by design — see the module docstring on
    why DGCA-sourced weights are legitimate while DGCA-sourced fares are not.
    """
    offenders: list[str] = []
    for path in _python_files(package):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        docstrings = _docstring_nodes(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and "dgca" in node.id.lower():
                offenders.append(f"{path.name}:{node.lineno}: name {node.id}")
            elif isinstance(node, ast.Attribute) and "dgca" in node.attr.lower():
                offenders.append(f"{path.name}:{node.lineno}: attribute .{node.attr}")
            elif (
                isinstance(node, ast.Constant)
                and isinstance(node.value, str)
                and id(node) not in docstrings
                and "dgca" in node.value.lower()
            ):
                offenders.append(
                    f"{path.name}:{node.lineno}: string {node.value[:60]!r}"
                )
    assert not offenders, (
        "A module that computes the index references DGCA in executable code — a "
        "query or identifier, not prose. An index that has read its own validation "
        "target is not validated by it:\n  " + "\n  ".join(offenders)
    )


def test_validation_package_is_the_only_dgca_consumer() -> None:
    """Positive control: the isolation is real, not vacuous.

    If nothing anywhere referenced DGCA the tests above would pass trivially, so
    assert the reference genuinely exists on the validation side.
    """
    validation_text = "\n".join(
        p.read_text(encoding="utf-8").lower() for p in _python_files("validation")
    )
    assert "dgca" in validation_text, (
        "No DGCA reference found in aipi/validation — the isolation tests above "
        "would then be passing vacuously."
    )
