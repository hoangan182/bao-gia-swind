"""
Test bộ KIỂM BẤT BIẾN của E2E (src/swind_e2e_regression.py) — User chốt 2026-11-03: "Bỏ mặc định đạt, phải có cơ chế kiểm thử".
Mọi file BOQ (kể cả chưa có baseline) phải qua các bất biến này; test bảo đảm bộ kiểm bắt đúng lỗi và không báo nhầm.
Chạy: ./venv/bin/python -m unittest discover -s tests -p "test_swind_*.py"
"""
import os
import sys
import tempfile
import unittest

import openpyxl

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import swind_e2e_regression as e2e  # noqa: E402


def _res(**kw):
    base = {"traceback": False, "tail": [], "sheets": {"S": {"count": 1, "sub_total": 1}}, "unpriced_rows": 0,
            "qa_rejected": 0, "omission_warnings": 0, "row_issues": [], "blocked": False,
            "duct_only_stop": False, "price_not_increasing": 0}
    base.update(kw)
    return base


def _bg_file(rows, title="BG"):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = title
    ws.cell(11, 2, "Danh mục sản phẩm")
    ws.cell(11, 3, "Model")
    for i, (name, model) in enumerate(rows, start=16):
        ws.cell(i, 2, name)
        ws.cell(i, 3, model)
    fd, path = tempfile.mkstemp(suffix=".xlsx")
    os.close(fd)
    wb.save(path)
    return path


class InvariantTest(unittest.TestCase):
    def test_clean_result_passes(self):
        self.assertEqual(e2e.check_invariants(_res()), ([], []))

    def test_each_blocking_issue_fails(self):
        for kw in ({"traceback": True}, {"sheets": {}}, {"unpriced_rows": 2}, {"qa_rejected": 1}, {"omission_warnings": 1},
                   {"row_issues": ["x"]}):
            with self.subTest(kw=kw):
                self.assertTrue(e2e.check_invariants(_res(**kw))[0])

    def test_duct_only_stop_is_expected(self):
        # BOQ chỉ có ống gió ở chế độ mặc định: runner dừng ⛔ là đúng quy tắc 4
        self.assertEqual(e2e.check_invariants(_res(sheets={}, duct_only_stop=True))[0], [])

    def test_warnings_do_not_fail(self):
        fails, warns = e2e.check_invariants(_res(blocked=True, price_not_increasing=1))
        self.assertEqual(fails, [])
        self.assertEqual(len(warns), 2)


class BgRowCheckTest(unittest.TestCase):
    def _issues(self, rows, title="BG"):
        path = _bg_file(rows, title)
        try:
            return e2e._check_bg_rows(path)
        finally:
            os.remove(path)

    def test_van_bundled_with_grille_is_caught(self):
        # Lỗi Fezix 2026-11-03: Title 'Van, miệng gió' làm van FD bị ghép 'SDG + ...'
        self.assertEqual(len(self._issues([("Van chặn lửa FD kích thước: 200x200", "SDG + SWIND-2.01- E-FD-EI120")])), 1)

    def test_grille_with_only_damper_code_is_caught(self):
        self.assertEqual(len(self._issues([("Cửa gió hồi 400x400", "SWIND-1.02-MFD-EI90")])), 1)

    def test_valid_rows_pass(self):
        rows = [
            ("Van chặn lửa FD 200x200", "SWIND-2.01- E-FD-EI120"),
            ("Van 1 chiều NRD 200x200", "NRD"),
            ("Miệng hút gió EAG+OBD 200x200", "ECG+O"),
            ("Louver 500x250 + LCCT + G4", "WL+N+F"),
            ("Louver cấp bù kèm van MFD 800x400", "WL + SWIND-1.02-MFD-EI90"),
            ("Cửa sổ cấp bù gió khi có cháy 1.5m2", "SWIND-1.02-MFD-EI90"),  # rule cố ý: cửa sổ cấp bù = MFD
            ("AL 600x300", "WL"),
        ]
        self.assertEqual(self._issues(rows), [])

    def test_customer_sheet_without_system_header_is_ignored(self):
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "BG SWIND"
        ws.cell(16, 2, "Van chặn lửa FD 200x200")
        ws.cell(16, 3, "SDG + FD")
        fd, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        wb.save(path)
        try:
            self.assertEqual(e2e._check_bg_rows(path), [])
        finally:
            os.remove(path)


if __name__ == "__main__":
    unittest.main()
