"""
Test phân loại lệch giá từng dòng Sheet BG (src/swind_e2e_regression.py → classify_line_diff).
Ngưỡng lệch lớn (User chốt 2026-11-03): dòng > 2% hoặc > 50.000đ; tổng sheet > 0,5%; dòng thêm/bớt/đổi Model/Tên.
Chạy: ./venv/bin/python -m unittest tests.test_swind_line_diff -v
"""
import os
import sys
import unittest

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, SRC)

from swind_e2e_regression import classify_line_diff  # noqa: E402


def L(row, price, name="Van MD 600x400", model="MD", qty=1, sheet="BG"):
    return {"sheet": sheet, "row": row, "name": name, "model": model, "unit": "Cái", "qty": qty, "price": price, "amount": qty * price}


class LineDiff(unittest.TestCase):
    def test_small_change_is_minor(self):
        r = classify_line_diff({"a.xlsx": [L(12, 1_000_000)]}, {"a.xlsx": [L(12, 1_010_000)]})
        self.assertEqual(len(r["major"]), 0)
        self.assertEqual(len(r["minor"]), 1)

    def test_over_2_percent_is_major(self):
        r = classify_line_diff({"a.xlsx": [L(12, 1_000_000)]}, {"a.xlsx": [L(12, 1_030_000)]})
        self.assertEqual(len(r["major"]), 1)

    def test_over_50k_is_major_even_under_2_percent(self):
        r = classify_line_diff({"a.xlsx": [L(12, 10_000_000)]}, {"a.xlsx": [L(12, 10_060_000)]})
        self.assertEqual(len(r["major"]), 1)

    def test_model_change_is_major(self):
        r = classify_line_diff({"a.xlsx": [L(12, 100)]}, {"a.xlsx": [L(12, 100, model="MD + EI")]})
        self.assertEqual(len(r["major"]), 1)

    def test_line_diff_detects_name_shift(self):
        r = classify_line_diff({"a.xlsx": [L(12, 100, name="Cửa A")]}, {"a.xlsx": [L(12, 100, name="Cửa B")]})
        self.assertEqual(r["major"][0]["ly_do"], "đổi dòng")

    def test_missing_line_is_major(self):
        r = classify_line_diff({"a.xlsx": [L(12, 100), L(13, 100)]}, {"a.xlsx": [L(12, 100)]})
        self.assertEqual(len(r["major"]), 1)

    def test_inserted_line_does_not_shift_following_rows(self):
        names = ["Cửa A", "Cửa B", "Cửa C", "Cửa D"]
        before = {"a.xlsx": [L(10 + i, 100 + i, name=n) for i, n in enumerate(names)]}
        after_names = ["Cửa A", "Cửa B", "LCCT mới", "Cửa C", "Cửa D"]
        after = {"a.xlsx": [L(10 + i, 500 if n == "LCCT mới" else 100 + names.index(n), name=n) for i, n in enumerate(after_names)]}
        r = classify_line_diff(before, after)
        self.assertEqual([x["ly_do"] for x in r["major"]], ["dòng mới"])
        self.assertEqual(r["minor"], [])

    def test_price_change_after_insert_is_still_reported(self):
        before = {"a.xlsx": [L(10, 100, name="A"), L(11, 1_000_000, name="B")]}
        after = {"a.xlsx": [L(10, 100, name="A"), L(11, 50, name="Mới"), L(12, 1_100_000, name="B")]}
        r = classify_line_diff(before, after)
        self.assertEqual(sorted(x["ly_do"] for x in r["major"]), ["dòng mới", "lệch giá"])

    def test_identical_is_clean(self):
        r = classify_line_diff({"a.xlsx": [L(12, 100)]}, {"a.xlsx": [L(12, 100)]})
        self.assertEqual((r["major"], r["minor"], r["sheet_totals"]), ([], [], []))

    def test_sheet_total_over_half_percent_is_major(self):
        before = {"a.xlsx": [L(r, 1_000_000) for r in range(10, 20)]}
        after = {"a.xlsx": [L(r, 1_010_000) for r in range(10, 20)]}
        r = classify_line_diff(before, after)
        self.assertEqual(len(r["major"]), 0)
        self.assertEqual(len(r["sheet_totals"]), 1)
        self.assertTrue(r["sheet_totals"][0]["major"])


if __name__ == "__main__":
    unittest.main()
