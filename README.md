# StrokeMetis audit snapshot

**Stroke Metabolomics Evidence Triangulation and Identification System**

This small, read-only snapshot checks artifact integrity and accounts for
prespecified regional evidence. It does not download data, run or recover the
scientific workflow, fit models, reproduce the full study, or predict individual
stroke risk. It introduces no new statistical estimator.

## Quickstart

Python 3.11 or later; standard library only. From the repository root:

```sh
python -B -m unittest discover -s tests -v
python -B strokemetis_audit.py --help
```

To verify a local bundle, use:

```sh
python -B strokemetis_audit.py verify /path/to/bundle
```

The default input is `MANIFEST_SHA256.json` inside that bundle; override it
with `--manifest`. Its `files` list must contain at least one record, each
with a relative POSIX `path`, an integer `bytes` and a 64-digit hex
`sha256`. This verifies listed bytes, not data rights, scientific results,
extra files, or whether the manifest itself is authentic.

To audit one signal pair, save this **synthetic** example as `toy-grid.json`:

```json
{
  "expected_settings": ["setting-a", "setting-b", "setting-c"],
  "threshold": 0.8,
  "rows": [
    {"setting": "setting-a", "status": "eligible", "h4": 0.91},
    {"setting": "setting-b", "status": "capacity_limited"}
  ]
}
```

```sh
python -B strokemetis_audit.py region toy-grid.json
```

Declare the complete grid and threshold before viewing outcomes. Setting IDs
may encode a window, model and prior combination. Supply at most one row per
setting. Use `eligible`, `unmatched`, `capacity_limited` or
`not_evaluable`; only eligible rows provide an inferential H4. An absent
setting is `missing`, not H4=0. The example is not stable because one setting
is capacity-limited and another is missing.

The stability flag requires every declared setting to be eligible and at or
above threshold. It neither determines eligibility upstream nor certifies a
mechanism, independent replication, lipid-independent causation, or clinical
utility. Exit codes: `0` for a completed audit (read its result), `1` for
a manifest with a file mismatch, and `2` for invalid input or an I/O error.

## Data and reuse

No study data, frozen study results, third-party code, figures, or credentials
are included. Tests use synthetic fixtures only. See [Data and method
sources](DATA_SOURCES.md) for upstream provenance. No project-wide reuse
license is stated in this snapshot; no upstream data rights are granted here.
