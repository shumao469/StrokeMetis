import hashlib
from pathlib import Path
import tempfile
import unittest

from strokemetis_audit import audit_region, verify_manifest


class ManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.payload = self.root / "toy.txt"
        self.payload.write_bytes(b"synthetic\n")
        self.record = {"path": "toy.txt", "bytes": self.payload.stat().st_size,
                       "sha256": hashlib.sha256(self.payload.read_bytes()).hexdigest()}

    def verify(self, *records):
        return verify_manifest(self.root, {"files": list(records)})

    def test_intact_file(self):
        self.assertTrue(self.verify(self.record)["passed"])

    def test_same_size_edit_is_detected(self):
        self.payload.write_bytes(b"Synthetic\n")
        self.assertEqual(self.verify(self.record)["failures"][0]["reason"], "sha256_mismatch")

    def test_missing_file(self):
        self.assertEqual(self.verify(dict(self.record, path="missing.txt"))["failures"][0]["reason"],
                         "missing_or_not_file")

    def test_bad_manifest_paths(self):
        for name in ("../toy.txt", "./toy.txt", "/toy.txt", "Z:/toy.txt", "a\\toy.txt", "a//toy.txt"):
            with self.subTest(name=name), self.assertRaises(ValueError):
                self.verify(dict(self.record, path=name))

    def test_empty_duplicate_and_invalid_metadata(self):
        for records in ([], [self.record, self.record], [dict(self.record, bytes=True)],
                        [dict(self.record, sha256="bad")]):
            with self.subTest(records=records), self.assertRaises(ValueError):
                self.verify(*records)


class RegionalTests(unittest.TestCase):
    def test_all_declared_high_inclusive_threshold(self):
        result = audit_region(["a", "b"], [{"setting": "b", "status": "eligible", "h4": .8},
                                          {"setting": "a", "status": "eligible", "h4": .95}])
        self.assertTrue(result["stable_across_declared_grid"])
        self.assertFalse(result["independent_causality_certified"])

    def test_accounting_does_not_convert_missing_to_zero(self):
        result = audit_region(list("abcdef"), [
            {"setting": "a", "status": "eligible", "h4": .92},
            {"setting": "b", "status": "eligible", "h4": 0},
            {"setting": "c", "status": "unmatched"},
            {"setting": "d", "status": "capacity_limited"},
            {"setting": "e", "status": "not_evaluable"},
        ])
        self.assertEqual(set(result["counts"].values()), {1})
        self.assertFalse(result["stable_across_declared_grid"])

    def test_all_high_except_one_absent_does_not_pass(self):
        result = audit_region(["a", "b"], [{"setting": "a", "status": "eligible", "h4": .99}])
        self.assertEqual(result["counts"]["missing"], 1)
        self.assertFalse(result["stable_across_declared_grid"])

    def test_duplicate_unexpected_and_invalid_rows_fail(self):
        row = {"setting": "a", "status": "eligible", "h4": .99}
        for rows in ([row, row], [dict(row, setting="b")], [dict(row, h4=1.1)],
                     [dict(row, h4=float("nan"))], [dict(row, h4=True)],
                     [dict(row, status="unmatched")]):
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                audit_region(["a"], rows)
        with self.assertRaises(ValueError):
            audit_region(["a", "a"], [])


if __name__ == "__main__":
    unittest.main()
