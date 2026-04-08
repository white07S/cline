"""Dump the FastAPI app's OpenAPI schema to stdout.

Used by `just openapi` → openapi-typescript → client/src/api/types.gen.ts.
This is the single source of truth for the client's API types.
"""

from __future__ import annotations

import json
import sys

from app.main import create_app


def main() -> None:
    app = create_app()
    schema = app.openapi()
    json.dump(schema, sys.stdout, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
