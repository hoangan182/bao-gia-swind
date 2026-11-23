"""Kho ghi nhớ quyết định theo dự án cho trợ lý 'bao-gia-tu-bg-cu' (2026-11-23, dự án 261123_HH3_RFQ)."""
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from old_quote_memory import apply_memory, load_memory, save_memory  # noqa: E402

OQ = {"path": "bg.xlsx", "mtime": 1}


def _rows(key="K#1"):
    return [{"key": key, "decided_by": None, "reason": ""}]


class ApplyMemoryTest(unittest.TestCase):
    def test_carry_reapplied_when_same_price(self):
        mem = {"old_quote": OQ, "rows": {"K#1": {"action": "carry", "ref": "BG!10", "price_at_decision": 100}}}
        rows = _rows()
        apply_memory(rows, mem, [{"sheet": "BG", "row": 10, "price": 100, "name": "x"}], OQ)
        self.assertEqual(rows[0]["decided_by"], "memory")
        self.assertEqual(rows[0]["decision"]["action"], "carry")

    def test_carry_not_reapplied_when_price_changed(self):
        mem = {"old_quote": OQ, "rows": {"K#1": {"action": "carry", "ref": "BG!10", "price_at_decision": 100}}}
        rows = _rows()
        apply_memory(rows, mem, [{"sheet": "BG", "row": 10, "price": 120, "name": "x"}], OQ)
        self.assertIsNone(rows[0]["decided_by"])
        self.assertIn("giá BG cũ đổi", rows[0]["reason"])

    def test_carry_not_reapplied_when_ref_gone(self):
        mem = {"old_quote": OQ, "rows": {"K#1": {"action": "carry", "ref": "BG!10", "price_at_decision": 100}}}
        rows = _rows()
        apply_memory(rows, mem, [], OQ)
        self.assertIsNone(rows[0]["decided_by"])
        self.assertIn("dòng BG cũ không còn", rows[0]["reason"])

    def test_carry_not_reapplied_when_old_file_changed(self):
        mem = {"old_quote": OQ, "rows": {"K#1": {"action": "carry", "ref": "BG!10", "price_at_decision": 100}}}
        rows = _rows()
        apply_memory(rows, mem, [{"sheet": "BG", "row": 10, "price": 100, "name": "x"}], {"path": "bg2.xlsx", "mtime": 5})
        self.assertIsNone(rows[0]["decided_by"])
        self.assertIn("đổi file BG cũ", rows[0]["reason"])

    def test_new_always_reapplied_even_if_file_changed(self):
        mem = {"old_quote": OQ, "rows": {"K#1": {"action": "new"}}}
        rows = _rows()
        apply_memory(rows, mem, [], {"path": "b.xlsx", "mtime": 2})
        self.assertEqual(rows[0]["decided_by"], "memory")

    def test_unknown_key_untouched(self):
        rows = _rows("OTHER#1")
        apply_memory(rows, {"old_quote": OQ, "rows": {"K#1": {"action": "new"}}}, [], OQ)
        self.assertIsNone(rows[0]["decided_by"])
        self.assertEqual(rows[0]["reason"], "")


class StoreTest(unittest.TestCase):
    def test_missing_file_is_empty(self):
        with tempfile.TemporaryDirectory() as d:
            self.assertEqual(load_memory("HH3", d), {})

    def test_corrupt_file_not_overwritten(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "HH3.json")
            with open(p, "w") as f:
                f.write("{bad")
            mem = load_memory("HH3", d)
            self.assertTrue(mem["_corrupt"])
            save_memory("HH3", mem, {"rows": {}}, {"rows": []}, {}, d)
            with open(p) as f:
                self.assertEqual(f.read(), "{bad")

    def test_roundtrip_keeps_user_decisions_only(self):
        with tempfile.TemporaryDirectory() as d:
            plan = {"boq": "rfq.xlsx", "old_quote": {"path": "bg.xlsx", "mtime": 1, "sheets": ["BG"]},
                    "rows": [{"key": "K#1", "decided_by": "user"}, {"key": "A#1", "decided_by": "auto"}]}
            decisions = {"rows": {"K#1": {"action": "new"}}, "options": {"runner_args": ["--mfd-model", "1.05"]}}
            path = save_memory("HH3", {}, decisions, plan, {"total": 1}, d)
            self.assertTrue(os.path.exists(path))
            mem = load_memory("HH3", d)
            self.assertEqual(mem["options"]["runner_args"], ["--mfd-model", "1.05"])
            self.assertEqual(mem["rows"]["K#1"]["action"], "new")
            self.assertNotIn("A#1", mem["rows"])
            self.assertEqual(mem["old_quote"]["sheets"], ["BG"])
            self.assertEqual(len(mem["runs"]), 1)


if __name__ == "__main__":
    unittest.main()
