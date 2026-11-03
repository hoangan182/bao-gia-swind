"""
Test bảng rule PHẠM VI BÁO GIÁ (data/master_data/scope_rules.json → src/scope_filter.py).

Mỗi rule phải có nguồn gốc, lý do và ví dụ; các ví dụ chạy qua đúng hàm của rule. Thêm test cấp parser cho các dòng
BOQ thật User chốt (mã IS / MPRD — BOQ_ANH_KHACH_01) và cổng hỏi lại khi kiểm chứng đọc BOQ lệch (PV-13).
Chạy: ./venv/bin/python -m unittest discover -s tests -p "test_swind_*.py"
"""
import os
import sys
import tempfile
import unittest

import openpyxl

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, SRC)

import scope_filter as sf  # noqa: E402


class ScopeRuleTableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.R = sf.load_rules()

    def test_table_structure(self):
        ids = [r["id"] for r in self.R["_all"]["quy_tac"]]
        self.assertEqual(len(ids), len(set(ids)), "id rule bị trùng")
        self.assertEqual(ids, sorted(ids), "rule phải xếp theo id")
        for r in self.R["_all"]["quy_tac"]:
            for key in ("ten", "nguon", "ly_do"):
                self.assertIn(key, r, f"{r['id']}: thiếu '{key}'")
            self.assertTrue(r["nguon"], f"{r['id']}: thiếu nguồn")
            self.assertTrue(r.get("vi_du"), f"{r['id']}: chưa có ví dụ")

    def test_pv01_non_swind_system(self):
        for ex in self.R["PV-01"]["vi_du"]:
            n = ex["ten"].lower()
            with self.subTest(ten=ex["ten"]):
                self.assertEqual(sf.is_non_swind_system_item(n, n, "", ex["ten"], ex["ten"], ""), ex["ket_qua"])

    def test_pv02_pv03_commercial(self):
        for ex in self.R["PV-02"]["vi_du"]:
            with self.subTest(ten=ex["ten"]):
                self.assertEqual(sf.is_commercial_by_name(ex["ten"].lower()), ex["ket_qua"])
        for ex in self.R["PV-03"]["vi_du"]:
            self.assertEqual(sf.is_auxiliary_material(ex["ten"].lower()), ex["ket_qua"])

    def test_pv04_partner_price_keeps_row(self):
        for ex in self.R["PV-04"]["vi_du"]:
            skip = sf.should_skip_row(ex["nhom"], 600, 300, 0, "tủ điện", ex["gia_doi_tac"], False, False)
            self.assertEqual("bo" if skip else "giu", ex["ket_qua"])
        self.assertFalse(sf.should_skip_row("VAN_GIO", 600, 300, 0, "van vcd", None, False, False))
        self.assertTrue(sf.should_skip_row("ONG_MEM", 0, 0, 200, "ống mềm", None, False, False))
        self.assertFalse(sf.should_skip_row("ONG_MEM", 0, 0, 200, "ống mềm", None, True, False))

    def test_pv05_to_pv08_after_dims(self):
        self.assertEqual(sf.adjust_category_after_dims("VAN_GIO", 0, 0, 0, "van fd", "van fd", "", "cái", False), ("THUONG_MAI", True))
        self.assertEqual(sf.adjust_category_after_dims("CUA_GIO", 0, 0, 200, "ead d200", "ead d200", "", "cái", False), ("THUONG_MAI", False))
        ex = self.R["PV-07"]["vi_du"][0]
        row = f"{ex['ten']} {ex['ghi_chu']}"
        self.assertEqual(sf.adjust_category_after_dims("CUA_GIO", 450, 450, 0, row.lower(), row.lower(), row, "cái", False), ("ONG_GIO", False))
        self.assertEqual(sf.adjust_category_after_dims("ONG_GIO", 0, 0, 0, "kẹp bích", "kẹp bích", "", "cái", False), ("THUONG_MAI", False))
        self.assertEqual(sf.adjust_category_after_dims("CUA_GIO", 600, 300, 0, "cửa", "cửa", "", "cái", True), ("THUONG_MAI", False))

    def test_pv12_insect_screen_code(self):
        for ex in self.R["PV-12"]["vi_du"]:
            with self.subTest(ten=ex["ten"]):
                self.assertEqual(sf.is_insect_screen_code(ex["ten"].lower()), ex["ket_qua"])

    def test_pv11_non_swind_omission(self):
        for ex in self.R["PV-11"]["khong_phai_hang_swind_sot_dong"]["vi_du"]:
            with self.subTest(ten=ex["ten"]):
                self.assertEqual(sf.is_non_swind_omission(ex["ten"]), ex["ket_qua"])

    def test_pv14_louver_code(self):
        for ex in self.R["PV-14"]["vi_du"]:
            with self.subTest(ten=ex["ten"]):
                self.assertEqual(sf.is_louver_code(ex["ten"].lower()), ex["ket_qua"])

    def test_pv13_read_check_only_for_quoted_sheets(self):
        warns = {"DG": ["cột SL 'TỔNG' ít dòng hơn 'KL ECB'"], "Bia": ["cột ẩn"]}
        out = sf.read_check_confirms(warns, {"DG"})
        self.assertEqual(len(out), 1)
        self.assertIn("[HỎI LẠI USER]", out[0])
        self.assertIn("'DG'", out[0])
        self.assertEqual(sf.read_check_confirms(warns, set()), [])

    def test_coverage_lists(self):
        cov = sf.coverage_lists()
        self.assertIn("giá đỡ", cov["SWIND_NON_SCOPE_PREFIXES"])
        self.assertIn("flexible connection", cov["CANVAS_NAME_PREFIXES"])


class ScopeParserRowsTest(unittest.TestCase):
    """BOQ_ANH_KHACH_01 (User chốt 2026-11-03): 'IS 850x250', 'AL IS-1000x800' → LCCT; 'AG MPRD-1200x900-E160' → van MPRD."""

    def test_rows(self):
        from swind_boq_parser import SwindBOQParser
        from agent_01_boq_extractor import Agent01_BOQExtractor
        from swind_utils import get_subtype_rules
        rows = [("IS 850x250", "CUA_GIO", "LCCT"), ("AL IS-1000x800", "CUA_GIO", "LCCT"), ("AG MPRD-1200x900-E160", "VAN_GIO", "M-PRD")]
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "boq.xlsx")
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "BOQ"
            ws.append(["STT", "Danh mục vật tư / Quy cách kỹ thuật", "ĐVT", "Khối lượng"])
            for i, (name, _, _) in enumerate(rows, 1):
                ws.append([i, name, "Cái", 1])
            wb.save(p)
            items = SwindBOQParser(p).parse_sheet("BOQ")
        Agent01_BOQExtractor.enrich_all_items(items, get_subtype_rules())
        self.assertEqual([(it["raw_name"], it["category"], it["resolved_spec"]["model_fslf"]) for it in items], rows)


if __name__ == "__main__":
    unittest.main()
