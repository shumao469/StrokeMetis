"""Read-only package integrity and prespecified regional-evidence auditing."""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
import re
import sys


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON field: {key}")
        result[key] = value
    return result


def _read_json(path):
    with Path(path).open(encoding="utf-8-sig") as stream:
        return json.load(stream, object_pairs_hook=_unique_object)


def _relative_path(value):
    if not isinstance(value, str) or not value or "\\" in value or "\x00" in value:
        raise ValueError("manifest paths must be nonempty relative POSIX paths")
    path = PurePosixPath(value)
    if (path.is_absolute() or PureWindowsPath(value).drive or ":" in value
            or any(part in {"", ".", ".."} for part in value.split("/"))):
        raise ValueError("manifest path must not be absolute, ambiguous or escaping")
    return path


def verify_manifest(root, manifest):
    """Verify only explicitly listed files; no write, download or science check."""
    root = Path(root).resolve(strict=True)
    if not root.is_dir():
        raise ValueError("bundle root must be a directory")
    records = manifest.get("files") if isinstance(manifest, dict) else None
    if not isinstance(records, list) or not records:
        raise ValueError("manifest must declare a nonempty files list")

    targets = []
    seen = set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("each manifest record must be an object")
        relative = _relative_path(record.get("path"))
        target = (root / relative).resolve()
        size, checksum = record.get("bytes"), record.get("sha256")
        if not target.is_relative_to(root):
            raise ValueError("manifest target resolves outside bundle root")
        if target in seen:
            raise ValueError("duplicate resolved file in manifest")
        seen.add(target)
        if type(size) is not int or size < 0:
            raise ValueError("manifest bytes must be a nonnegative integer")
        if not isinstance(checksum, str) or not re.fullmatch(r"[0-9a-fA-F]{64}", checksum):
            raise ValueError("manifest SHA-256 must contain exactly 64 hex digits")
        targets.append((relative.as_posix(), target, size, checksum.lower()))

    failures = []
    for name, target, size, checksum in targets:
        if not target.is_file():
            failures.append({"path": name, "reason": "missing_or_not_file"})
        elif target.stat().st_size != size:
            failures.append({"path": name, "reason": "size_mismatch"})
        else:
            with target.open("rb") as stream:
                actual = hashlib.file_digest(stream, "sha256").hexdigest()
            if actual != checksum:
                failures.append({"path": name, "reason": "sha256_mismatch"})
    return {"files_checked": len(targets), "passed": not failures, "failures": failures,
            "scope": "listed file integrity only"}


def _probability(value, label):
    if (isinstance(value, bool) or not isinstance(value, (int, float))
            or not 0 <= value <= 1 or not math.isfinite(value)):
        raise ValueError(f"{label} must be a finite number between 0 and 1")
    return float(value)


def audit_region(expected_settings, rows, *, threshold=0.8):
    """Classify a single signal pair against a declared grid, without fitting."""
    threshold = _probability(threshold, "threshold")
    if (not isinstance(expected_settings, list) or not expected_settings
            or any(not isinstance(key, str) or not key.strip() for key in expected_settings)):
        raise ValueError("expected_settings must be a nonempty list of nonblank strings")
    expected = set(expected_settings)
    if len(expected) != len(expected_settings):
        raise ValueError("duplicate expected setting")
    if not isinstance(rows, list):
        raise ValueError("rows must be a list")

    observed = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("each regional row must be an object")
        key = row.get("setting")
        if not isinstance(key, str) or key not in expected:
            raise ValueError("row setting was not prespecified")
        if key in observed:
            raise ValueError("duplicate observed setting")
        status = row.get("status")
        if status == "eligible":
            h4 = _probability(row.get("h4"), "eligible H4")
            status = "eligible_high" if h4 >= threshold else "eligible_low"
        elif status not in ("unmatched", "capacity_limited", "not_evaluable"):
            raise ValueError("unknown regional row status")
        elif row.get("h4") is not None:
            raise ValueError("ineligible rows must not supply an inferential H4")
        observed[key] = status

    settings = [{"setting": key, "category": observed.get(key, "missing")}
                for key in expected_settings]
    counted = Counter(row["category"] for row in settings)
    counts = {state: counted[state] for state in
              ("eligible_high", "eligible_low", "missing", "unmatched",
               "capacity_limited", "not_evaluable")}
    return {"expected_count": len(expected), "threshold": threshold,
            "counts": counts, "settings": settings,
            "stable_across_declared_grid": counts["eligible_high"] == len(expected),
            "independent_causality_certified": False}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    verify = commands.add_parser("verify", help="check a local file manifest")
    verify.add_argument("root", type=Path)
    verify.add_argument("--manifest", type=Path, help="default: ROOT/MANIFEST_SHA256.json")
    region = commands.add_parser("region", help="audit one local signal-pair grid")
    region.add_argument("input", type=Path)
    args = parser.parse_args(argv)
    try:
        if args.command == "verify":
            result = verify_manifest(args.root, _read_json(
                args.manifest if args.manifest is not None else args.root / "MANIFEST_SHA256.json"))
            exit_code = 0 if result["passed"] else 1
        else:
            data = _read_json(args.input)
            if not isinstance(data, dict):
                raise ValueError("regional input must be an object")
            result = audit_region(data.get("expected_settings"), data.get("rows"),
                                  threshold=data.get("threshold", 0.8))
            exit_code = 0
        print(json.dumps(result, indent=2, allow_nan=False))
        return exit_code
    except (OSError, ValueError, RuntimeError) as error:
        print(f"StrokeMetis audit: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
