"""Schemas for the shared workspace files."""

import json
from pathlib import Path

import jsonschema
import pytest

SCHEMA_DIR = Path(__file__).parent.parent / "schemas"


def test_workspace_source_manifest_schema_accepts_custom_metadata():
    schema = json.loads((SCHEMA_DIR / "source-manifest.schema.json").read_text(encoding="utf-8"))
    manifest = {
        "schema_version": "1.0",
        "imports": [
            {
                "sha256": "0" * 64,
                "original_name": "synthetic-notes.txt",
                "stored_path": "sources/2026-09-08-synthetic-notes.txt",
                "imported_at": "2026-09-08T12:00:00Z",
                "custom": {"synthetic_label": "demo"},
            }
        ],
        "external_references": [
            {
                "path": "Z:/synthetic-project",
                "label": "Synthetic read-only project",
                "custom": {"access": "read-only"},
            }
        ],
        "custom": {"synthetic_scenario": "phase-3-demo"},
    }
    jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(manifest)


@pytest.mark.parametrize(
    "stored_path",
    [
        "/sources/notes.txt",
        "C:/sources/notes.txt",
        "sources/../notes.txt",
        "sources/nested/../../notes.txt",
        "sources\\notes.txt",
        "inbox/notes.txt",
    ],
)
def test_workspace_source_manifest_rejects_nonportable_or_escaping_path(stored_path):
    schema = json.loads((SCHEMA_DIR / "source-manifest.schema.json").read_text(encoding="utf-8"))
    manifest = {
        "schema_version": "1.0",
        "imports": [
            {
                "sha256": "0" * 64,
                "original_name": "notes.txt",
                "stored_path": stored_path,
                "imported_at": "2026-09-08T12:00:00Z",
            }
        ],
        "custom": {},
    }
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.Draft202012Validator(schema, format_checker=jsonschema.FormatChecker()).validate(manifest)


def test_application_checks_example_validates():
    example = json.loads(
        (Path(__file__).parent / "fixtures" / "application-checks.json").read_text(encoding="utf-8")
    )
    schema = json.loads((SCHEMA_DIR / "application-checks.schema.json").read_text(encoding="utf-8"))
    jsonschema.validate(example, schema)
