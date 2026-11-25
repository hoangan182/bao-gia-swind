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

    def test_pv04_m2_duct_not_skipped(self):
        # User chốt 2026-11-13 (Luxora): ống / PK ống ghi tổng m² không KT → giữ cho Agent 04 tính đơn giá m² (OG-15/17)
        self.assertFalse(sf.should_skip_row("ONG_GIO", 0, 0, 0, "ống gió tôn tráng kẽm dày 0.58mm", None, False, False, unit="m2"))
        self.assertFalse(sf.should_skip_row("ONG_GIO", 0, 0, 0, "phụ kiện ống gió dày 0.75mm", None, False, False, unit="m²"))
        # ĐVT khác m² (cái / m) không KT → vẫn bỏ như cũ; tiêu âm / canvas không đổi
        self.assertTrue(sf.should_skip_row("ONG_GIO", 0, 0, 0, "cút 90", None, False, False, unit="cái"))
        self.assertTrue(sf.should_skip_row("ONG_GIO", 0, 0, 0, "ống gió", None, False, False))
        self.assertTrue(sf.should_skip_row("TIEU_AM", 0, 0, 0, "tiêu âm", None, False, False, unit="m2"))

    def test_pv05_to_pv08_after_dims(self):
        self.assertEqual(sf.adjust_category_after_dims("VAN_GIO", 0, 0, 0, "van fd", "van fd", "", "cái", False), ("THUONG_MAI", True))
        self.assertEqual(sf.adjust_category_after_dims("CUA_GIO", 0, 0, 200, "ead d200", "ead d200", "", "cái", False), ("THUONG_MAI", False))
        ex = self.R["PV-07"]["vi_du"][0]
        row = f"{ex['ten']} {ex['ghi_chu']}"
        self.assertEqual(sf.adjust_category_after_dims("CUA_GIO", 450, 450, 0, row.lower(), row.lower(), row, "cái", False), ("ONG_GIO", False))
        self.assertEqual(sf.adjust_category_after_dims("ONG_GIO", 0, 0, 0, "kẹp bích", "kẹp bích", "", "cái", False), ("THUONG_MAI", False))
        self.assertEqual(sf.adjust_category_after_dims("CUA_GIO", 600, 300, 0, "cửa", "cửa", "", "cái", True), ("THUONG_MAI", False))
        # PV-05 mở rộng (User chốt 2026-11-11): thiếu 1 cạnh / Louver chỉ ghi D -> không báo, chỉ ghi chú; van tròn D vẫn báo
        self.assertEqual(sf.adjust_category_after_dims("CUA_GIO", 600, 0, 0, "cửa gió 600", "cửa gió 600", "", "cái", False), ("THUONG_MAI", True))
        lv = "louver kèm lưới chắn côn trùng d503"
        # Louver tròn D503 có cách báo riêng (diffuser_rules louver_tron = 3 x Louver vuông) -> không coi là thiếu KT
        self.assertEqual(sf.adjust_category_after_dims("CUA_GIO", 503, 503, 503, lv, lv, "", "cái", False), ("CUA_GIO", False))
        self.assertEqual(sf.adjust_category_after_dims("VAN_GIO", 200, 200, 200, "van chặn lửa d200", "van chặn lửa d200", "", "cái", False), ("VAN_GIO", False))
        self.assertEqual(sf.adjust_category_after_dims("ONG_GIO", 500, 0, 0, "ống gió", "ống gió", "", "cái", False), ("ONG_GIO", False))
        vcd = "van điều chỉnh lưu lượng gió vcd kích thước: d100"  # Fezix 'BG SWIND' R110: W=100, H trống, tên D100 = van tròn
        self.assertEqual(sf.adjust_category_after_dims("VAN_GIO", 100, 0, 0, vcd, vcd, "", "cái", False), ("VAN_GIO", False))

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

    def test_pv16_fan_connection_transition(self):
        for v in self.R["PV-16"]["vi_du"]:
            self.assertEqual(sf.is_fan_connection_transition(v["ten"]), v["ket_qua"], v["ten"])

    def test_pv17_duct_insulation(self):
        for v in self.R["PV-17"]["vi_du"]:
            self.assertEqual(sf.is_duct_insulation(v["ten"]), v["ket_qua"], v["ten"])

    def test_pv15_glued_damper_code(self):
        for ex in self.R["PV-15"]["vi_du"]:
            with self.subTest(ten=ex["ten"]):
                self.assertEqual(sf.is_glued_damper_code(ex["ten"].lower()), ex["ket_qua"])

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


class ScopeNameHelpersTest(unittest.TestCase):
    """Helper từ khóa chuyển từ runner sang scope_filter (Việc 4, 2026-11-25) — tiền tố / regex đọc từ PV-11."""

    def test_main_noun(self):
        self.assertEqual(sf.main_noun("Cung cấp và lắp đặt ống gió 600x400"), "ống gió 600x400")
        self.assertEqual(sf.main_noun("Ống gió 600x400"), "ống gió 600x400")

    def test_is_duct_like_name(self):
        self.assertTrue(sf.is_duct_like_name("Cung cấp và lắp đặt ống gió 600x400"))
        self.assertFalse(sf.is_duct_like_name("Cửa gió 600x400"))

    def test_is_canvas_like_name(self):
        self.assertTrue(sf.is_canvas_like_name("Gia công, lắp đặt flexible connection"))
        self.assertFalse(sf.is_canvas_like_name("Ống gió 600x400"))

    def test_is_swind_product_name(self):
        kws = list(sf.coverage_lists()["SWIND_SCOPE_KWS"])
        self.assertTrue(sf.is_swind_product_name("Van chặn lửa 400x300", kws))
        self.assertFalse(sf.is_swind_product_name("Giá đỡ van chặn lửa", kws))

    def test_is_insect_screen_name(self):
        self.assertTrue(sf.is_insect_screen_name("louver kèm lcct 600x400"))
        self.assertTrue(sf.is_insect_screen_name("lưới chắn côn trùng 300x300"))
        self.assertFalse(sf.is_insect_screen_name("cửa gió 300x300"))


    def test_is_lcct_m2_title(self):
        """Task A (2026-11-25): Title 'LCCT ... kích thước:' ĐVT m2 có KL → báo LCCT theo m² (parser). Key RIÊNG
        PV-11 tu_khoa_lcct_theo_m2 — có 'insect screen' (không gộp vào tu_khoa_luoi_chan_con_trung: đổi Coverage Audit)."""
        cfg = sf.load_rules()["PV-11"]["tu_khoa_lcct_theo_m2"]
        for key in ("tu_khoa", "nguon", "ly_do", "vi_du_dung", "vi_du_sai"):
            self.assertTrue(cfg.get(key), f"tu_khoa_lcct_theo_m2 thiếu '{key}'")
        self.assertEqual(sorted(cfg["tu_khoa"]), sorted(["lưới chắn côn trùng", "lcct", "insect screen"]))
        self.assertNotIn("insect screen", sf.load_rules()["PV-11"]["tu_khoa_luoi_chan_con_trung"])
        for t in cfg["vi_du_dung"] + ["Insect screen kích thước:", "Lưới chắn côn trùng kích thước"]:
            self.assertTrue(sf.is_lcct_m2_title(t.lower()), t)
        for t in cfg["vi_du_sai"] + ["Cửa gió kích thước:", "Lưới chắn chim kích thước:"]:
            self.assertFalse(sf.is_lcct_m2_title(t.lower()), t)



class RunnerScopeFlagListsTest(unittest.TestCase):
    """Task B bước 1 (dọn sạch sau Việc 4, 2026-11-25): danh sách từ khóa theo cờ chuyển từ swind_master_runner sang
    PV-11 / PV-18. Giá trị mong đợi = hành vi literal cũ trong runner (ghim trước khi chuyển)."""

    def test_audit_scope_keywords_by_flags(self):
        cov = sf.coverage_lists()
        full, cv = cov["SWIND_SCOPE_KWS"], cov["SWIND_SCOPE_CUA_VAN_KWS"]
        self.assertEqual(sf.audit_scope_keywords(False, True, True), full)
        self.assertEqual(sf.audit_scope_keywords(True, True, True), cv)
        self.assertEqual(sf.audit_scope_keywords(False, False, True), tuple(k for k in full if k != "ống gió"))
        self.assertEqual(sf.audit_scope_keywords(False, True, False), tuple(k for k in full if k not in ("nối mềm", "canvas")))
        self.assertEqual(sf.audit_scope_keywords(False, False, False),
                         tuple(k for k in full if k not in ("ống gió", "nối mềm", "canvas")))
        self.assertEqual(sf.audit_scope_keywords(True, False, False), cv)

    def test_is_main_cv_name(self):
        for t in ("louver kèm lưới chắn côn trùng d503", "luover kèm lcct", "louvre + lcct", "cửa chớp kèm lcct",
                  "cửa gió kèm lcct", "miệng gió kèm lcct", "van gió kèm lcct", "van kèm lcct"):
            self.assertTrue(sf.is_main_cv_name(t), t)
        for t in ("lcct 600x400", "lưới chắn côn trùng", "vanh lcct", "khung van"):
            self.assertFalse(sf.is_main_cv_name(t), t)

    def test_is_cua_van_only_excluded(self):
        for t in ("ống chờ 300x300", "ống lồng d200", "ống nối mềm", "canvas mềm ei60", "khớp nối mềm",
                  "fire sleeve 300x300", "flexible duct d200"):
            self.assertTrue(sf.is_cua_van_only_excluded(t), t)
        for t in ("cửa gió 600x600", "van mfd 400x400", "ống gió 400x400"):
            self.assertFalse(sf.is_cua_van_only_excluded(t), t)

    def test_pv18_examples(self):
        for ex in self.R()["PV-18"]["vi_du"]:
            with self.subTest(ten=ex["ten"], title=ex.get("title_con", "")):
                self.assertEqual(sf.is_straight_fire_duct_row(ex["ten"], ex.get("title_con", "")), ex["ket_qua"])

    def test_pv18_straight_only_literal_behaviour(self):
        """Cờ --fire-duct-only --duct-straight-only (1 dự án, E2E không chạy): giữ nguyên chuỗi con 'tê' / 'co '."""
        f = sf.is_straight_fire_duct_row
        self.assertTrue(f("400x300", "ống gió thẳng tôn dày 1.0mm:"))
        self.assertTrue(f("ống gió 300x300", ""))
        self.assertTrue(f("ống gió 300x300", "phụ kiện:"))
        self.assertFalse(f("cút 90 độ 400x300", "ống gió thẳng:"))
        self.assertFalse(f("500x300", "phụ kiện:"))
        self.assertFalse(f("ống gió 600x400 kèm co 45", ""))
        self.assertFalse(f("ống gió tên a 300x300", ""))
        for kw in ("côn", "chân rẽ", "chạc", "z chuyển", "hộp", "chuyển tiết diện", "bịt", "măng xông"):
            self.assertFalse(f(f"ống gió {kw} 300x300", ""), kw)
        self.assertFalse(f("400x300", ""))

    @staticmethod
    def R():
        return sf.load_rules()


class ParserDetectionConfigTest(unittest.TestCase):
    """Task A (2026-11-25): danh sách nhận diện của parser đọc từ subtype_rules.json COMBO_AND_DETECTION_RULES,
    không còn fallback / phần cộng cứng trong swind_boq_parser.py."""

    @classmethod
    def setUpClass(cls):
        from swind_utils import get_subtype_rules
        cls.C = get_subtype_rules()["COMBO_AND_DETECTION_RULES"]
        with open(os.path.join(SRC, "swind_boq_parser.py"), encoding="utf-8") as f:
            cls.SRC_TXT = f.read()

    def test_missing_qty_cv_keywords_has_cua_chop(self):
        kws = self.C["missing_qty_cv_keywords"]
        self.assertIn("cửa chớp", kws)
        self.assertIn("chớp nhôm", kws)
        self.assertNotIn('("cửa chớp", "chớp nhôm")', self.SRC_TXT)

    def test_no_dead_fallbacks_in_parser(self):
        import re
        for key in ("missing_qty_cv_keywords", "missing_qty_cv_regex", "single_dim_damper_regex", "combo_diffuser_regex",
                    "combo_damper_regex", "hvac_sheet_keywords", "combo_category_list_title_regex",
                    "combo_own_diffuser_prefix_regex", "ktc_regex"):
            self.assertIn(key, self.C, key)
            self.assertIsNone(re.search(r'combo_cfg\.get\("%s",' % key, self.SRC_TXT), f"{key}: còn fallback trong parser")

    def test_category_list_title_regex(self):
        import re
        rx = self.C["combo_category_list_title_regex"]
        for t in ("van, miệng gió", "cửa gió / van gió", "van gió và cửa gió", "miệng gió & van"):
            self.assertTrue(re.match(rx, t), t)
        for t in ("van gió", "cửa gió cấp, van", "van chặn lửa"):
            self.assertFalse(re.match(rx, t), t)

    def test_own_diffuser_prefix_regex(self):
        import re
        rx = self.C["combo_own_diffuser_prefix_regex"]
        for t in ("cửa gió nan thẳng, kèm hộp gió, obd", "  miệng gió 600x300", "louver 1000x500", "grille 300x300",
                  "luover 600x600", "diffuser 600x600"):
            self.assertTrue(re.match(rx, t), t)
        for t in ("van mfd 600x400", "hộp gió kèm cửa", "600x300 cửa gió"):
            self.assertFalse(re.match(rx, t), t)


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
