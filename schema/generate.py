"""Generate the downstream schema artifacts from the canonical Pydantic models.

    uv run python -m schema.generate

Emits:
  * schema/json/docverify.schema.json   — JSON Schema (camelCase, serialization
    view) usable by any language / for request validation.
  * frontend/src/lib/schema.ts          — TypeScript types for the frontend,
    produced from the JSON Schema via `json-schema-to-typescript` (bunx/npx).

The Pydantic models in schema/models.py are the ONLY hand-edited source. Never
edit the generated files; re-run this script instead.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from pydantic.alias_generators import to_camel
from pydantic.json_schema import models_json_schema

from . import ALL_MODELS

ROOT = Path(__file__).resolve().parent.parent
JSON_OUT = ROOT / "schema" / "json" / "docverify.schema.json"
TS_OUT = ROOT / "frontend" / "src" / "lib" / "schema.ts"

_BANNER = "AUTO-GENERATED from schema/models.py by `python -m schema.generate` — do not edit."


def _strip_property_titles(node: object) -> None:
    """Drop the per-property ``title`` Pydantic emits. Without this,
    json-schema-to-typescript hoists every primitive field into its own noisy
    alias (``export type SubScore = number``) instead of inlining it."""
    if isinstance(node, dict):
        node.pop("title", None)
        for value in node.values():
            _strip_property_titles(value)
    elif isinstance(node, list):
        for value in node:
            _strip_property_titles(value)


def _tidy_defs(defs: dict) -> dict:
    """For each object model: make every property required (so the generated TS
    is non-optional — genuinely optional fields are already ``T | null``) and
    strip property-level titles. Enum defs (no ``properties``) are left intact so
    they keep their names."""
    for definition in defs.values():
        props = definition.get("properties")
        if not props:
            continue
        for prop_schema in props.values():
            _strip_property_titles(prop_schema)
        definition["required"] = list(props.keys())
    return defs


def build_json_schema() -> dict:
    """One combined JSON Schema whose root references every top-level model, so
    the TypeScript generator emits a named type for each."""
    _, defs_block = models_json_schema(
        [(m, "serialization") for m in ALL_MODELS],
        by_alias=True,
        ref_template="#/$defs/{model}",
    )
    defs = _tidy_defs(defs_block.get("$defs", {}))
    return {
        "$schema": "http://json-schema.org/draft-07/schema#",
        "$id": "https://docverify/schema/docverify.schema.json",
        "title": "DocVerifySchema",
        "description": _BANNER,
        "type": "object",
        "properties": {
            to_camel(m.__name__[0].lower() + m.__name__[1:]): {"$ref": f"#/$defs/{m.__name__}"}
            for m in ALL_MODELS
        },
        "$defs": defs,
    }


def write_json(schema: dict) -> None:
    JSON_OUT.parent.mkdir(parents=True, exist_ok=True)
    JSON_OUT.write_text(json.dumps(schema, indent=2) + "\n")
    print(f"wrote {JSON_OUT.relative_to(ROOT)}")


def _runner() -> list[str] | None:
    for exe in ("bunx", "npx"):
        if shutil.which(exe):
            return [exe, "--yes", "json-schema-to-typescript"] if exe == "npx" else [exe, "json-schema-to-typescript"]
    return None


def write_typescript() -> bool:
    runner = _runner()
    if runner is None:
        print("! bunx/npx not found — skipped TypeScript generation", file=sys.stderr)
        return False
    TS_OUT.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        *runner,
        str(JSON_OUT),
        "--no-additionalProperties",
        "--bannerComment", f"/* eslint-disable */\n/* {_BANNER} */",
    ]
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        print(proc.stdout, proc.stderr, file=sys.stderr)
        return False
    # json-schema-to-typescript prints the .d.ts to stdout.
    TS_OUT.write_text(proc.stdout)
    print(f"wrote {TS_OUT.relative_to(ROOT)}")
    return True


def main() -> int:
    schema = build_json_schema()
    write_json(schema)
    ok = write_typescript()
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
