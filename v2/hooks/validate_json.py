"""Validate knowledge entry JSON files.

Usage:
    python hooks/validate_json.py <json_file> [json_file2 ...]

Supports single file and glob patterns passed via shell expansion.
Exits with code 0 if all files pass, 1 otherwise.
"""

import json
import re
import sys
from pathlib import Path


REQUIRED_FIELDS: dict[str, type] = {
    "id": str,
    "title": str,
    "source_url": str,
    "summary": str,
    "tags": list,
    "status": str,
}

VALID_STATUSES = {"draft", "review", "published", "archived"}
VALID_AUDIENCES = {"beginner", "intermediate", "advanced"}

ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]+-\d{8}-\d{3}$")
URL_PATTERN = re.compile(r"^https?://\S+$")


def check_id(value: str, errors: list[str]) -> None:
    if not ID_PATTERN.match(value):
        errors.append(
            f"  id '{value}' does not match pattern {{source}}-{{YYYYMMDD}}-{{NNN}} "
            f"(e.g. github-20260317-001)"
        )


def check_url(value: str, errors: list[str]) -> None:
    if not URL_PATTERN.match(value):
        errors.append(f"  source_url '{value}' is not a valid http(s) URL")


def check_tags(value: list, errors: list[str]) -> None:
    if not value:
        errors.append("  tags must have at least 1 item")
    for i, tag in enumerate(value):
        if not isinstance(tag, str):
            errors.append(f"  tags[{i}] is not a string")


def check_summary(value: str, errors: list[str]) -> None:
    if len(value) < 20:
        errors.append(f"  summary is too short ({len(value)} chars, minimum 20)")


def check_status(value: str, errors: list[str]) -> None:
    if value not in VALID_STATUSES:
        valid = ", ".join(sorted(VALID_STATUSES))
        errors.append(f"  status '{value}' is not one of {{{valid}}}")


def validate_file(filepath: Path) -> tuple[int, int]:
    """Validate one JSON file. Returns (pass_count, fail_count)."""
    try:
        raw = filepath.read_text(encoding="utf-8")
    except Exception as exc:
        print(f"\n{filepath}")
        print(f"  FAILED to read file: {exc}")
        return 0, 1

    try:
        records = json.loads(raw)
    except json.JSONDecodeError as exc:
        print(f"\n{filepath}")
        print(f"  FAILED to parse JSON: {exc}")
        return 0, 1

    if not isinstance(records, list):
        records = [records]

    passed = 0
    failed = 0

    for idx, record in enumerate(records):
        errors: list[str] = []

        for field, expected_type in REQUIRED_FIELDS.items():
            if field not in record:
                errors.append(f"  missing required field '{field}'")
            elif not isinstance(record[field], expected_type):
                errors.append(
                    f"  field '{field}' must be {expected_type.__name__}, "
                    f"got {type(record[field]).__name__}"
                )

        if not errors:
            check_id(record["id"], errors)
            check_url(record["source_url"], errors)
            check_tags(record["tags"], errors)
            check_summary(record["summary"], errors)
            check_status(record["status"], errors)

        if "score" in record:
            score = record["score"]
            if not isinstance(score, (int, float)):
                errors.append(
                    f"  field 'score' must be a number, "
                    f"got {type(score).__name__}"
                )
            elif not 1 <= score <= 10:
                errors.append(f"  field 'score' must be between 1 and 10, got {score}")

        if "audience" in record:
            audience = record["audience"]
            if audience not in VALID_AUDIENCES:
                valid = ", ".join(sorted(VALID_AUDIENCES))
                errors.append(
                    f"  field 'audience' must be one of {{{valid}}}, "
                    f"got '{audience}'"
                )

        record_id = record.get("id", f"index={idx}")
        if errors:
            failed += 1
            print(f"\n{filepath}  [{record_id}]  FAILED")
            for err in errors:
                print(err)
        else:
            passed += 1

    return passed, failed


def main() -> None:
    if len(sys.argv) < 2:
        print(f"Usage: {sys.argv[0]} <json_file> [json_file2 ...]")
        sys.exit(1)

    total_passed = 0
    total_failed = 0

    for pattern in sys.argv[1:]:
        p = Path(pattern)
        if p.is_absolute():
            files = [p]
        else:
            files = list(Path.cwd().glob(pattern))
            if not files:
                files = [p]
        for filepath in files:
            if not filepath.is_file():
                print(f"\n{filepath}")
                print(f"  FAILED: file not found")
                total_failed += 1
                continue
            passed, failed = validate_file(filepath)
            total_passed += passed
            total_failed += failed

    total = total_passed + total_failed
    print(f"\n{'='*40}")
    print(f"Summary: {total_passed}/{total} passed, {total_failed}/{total} failed")

    if total_failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
