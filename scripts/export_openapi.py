"""Dump the OpenAPI schema to openapi.json.

The frontend consumes this to codegen a typed client instead of hand-writing
fetch calls. Committing the generated file means a contract change shows up as a
reviewable diff rather than as a runtime surprise in someone else's branch.

    python -m scripts.export_openapi
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from aipi.api.main import create_app

OUT = Path("openapi.json")


def main() -> int:
    schema = create_app().openapi()
    OUT.write_text(json.dumps(schema, indent=2, sort_keys=True), encoding="utf-8")
    paths = sorted(schema.get("paths", {}))
    print(f"wrote {OUT} with {len(paths)} paths:")
    for p in paths:
        print(f"  {p}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
