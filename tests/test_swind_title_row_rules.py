"""Test bảng rule phân vai Title / Dòng (title_row_rules.json, src/title_row_resolver.py) — User chốt 2026-11-23."""
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import title_row_resolver as tr  # noqa: E402

KWS = tr.product_keywords_from_files()


class RuleTableTest(unittest.TestCase):
    def test_every_rule_has_source_and_examples(self):
        for r in tr.load_rules()["_all"]["quy_tac"]:
            with self.subTest(rule=r["id"]):
                self.assertTrue(r.get("nguon"))
                self.assertTrue(r.get("ly_do"))
                self.assertTrue(r.get("vi_du_dung"))

    def test_rule_examples(self):
        R = tr.load_rules()
        for rid in ("TR-01", "TR-02", "TR-03"):
            for ex in R[rid]["vi_du_dung"] + R[rid].get("vi_du_sai", []):
                with self.subTest(rule=rid, ex=ex):
                    if "vai_title" in ex:
                        self.assertEqual(tr.title_role(ex["vao"], KWS), ex["vai_title"])
                    if "vai_dong" in ex:
                        self.assertEqual(tr.row_role(ex["vao"], KWS), ex["vai_dong"])
        for ex in R["TR-04"]["vi_du_dung"] + R["TR-04"]["vi_du_sai"]:
            with self.subTest(rule="TR-04", ex=ex):
                self.assertEqual(tr.decide(ex["title"], ex["dong"], ex["nhom"]), ex["ket_qua"])


class TitleKwRowTest(unittest.TestCase):
    """TR-05 (Task A, 2026-11-25): dòng không KL có chữ loại hàng → Title cha (parser is_parent_title_kw, AGENTS 1a).
    So chuỗi con thuần trên chuỗi .lower() cũ — không chuẩn hoá chính tả / bỏ dấu / ranh giới từ."""

    def test_tr05_data(self):
        r = tr.load_rules()["TR-05"]
        self.assertEqual(r["tu_khoa"], ["cửa", "miệng", "van", "ống", "louver", "luover", "louvre", "grille",
                                         "diffuser", "damper", "khớp nối", "tiêu âm"])
        for ex in r["vi_du_dung"]:
            self.assertTrue(tr.is_title_kw_row(ex["vao"]), ex)
        for ex in r["vi_du_sai"]:
            self.assertFalse(tr.is_title_kw_row(ex["vao"]), ex)

    def test_substring_semantics(self):
        yes = ["hệ thống cửa gió tầng 1", "miệng gió cấp", "vanguard", "chống cháy ei60", "air grilles",
               "khớp nối mềm", "hộp tiêu âm", "fire damper", "louvre", "hệ thống điều hòa"]
        no = ["khu vực b - điều hòa", "tầng 3", "khop noi mem", "tieu am", "phụ kiện"]
        for t in yes:
            self.assertTrue(tr.is_title_kw_row(t), t)
        for t in no:
            self.assertFalse(tr.is_title_kw_row(t), t)


class RolesTest(unittest.TestCase):
    def test_title_roles(self):
        self.assertEqual(tr.title_role("cửa gió kèm hộp gió kích thước:", KWS), "LOAI_HANG")
        self.assertEqual(tr.title_role("hệ thống điều hòa", KWS), "HANG_MUC")
        self.assertEqual(tr.title_role("tầng 3", KWS), "HANG_MUC")
        self.assertEqual(tr.title_role("hệ thống tăng áp cầu thang", KWS), "PHU_KIEN")
        self.assertEqual(tr.title_role("van chặn lửa ei60", KWS), "LOAI_HANG")
        self.assertEqual(tr.title_role("chống cháy ei60", KWS), "PHU_KIEN")  # 'chống' không chứa từ 'ống'

    def test_no_title(self):
        self.assertEqual(tr.title_role("", KWS), "NONE")
        self.assertEqual(tr.title_role("sản phẩm", KWS), "NONE")
        self.assertIsNone(tr.decide("NONE", "CHI_KT", "ONG_GIO"))
        self.assertIsNone(tr.decide("NONE", "KHONG_NHAN_RA", "CUA_GIO"))

    def test_chi_kt_variants(self):
        for t in ("800x250", "1200x150+f", "cg-01 600x300", "tầng 3: 600x300", "loại a 600x300",
                  "ei60 600x300", "d300", "600 x 300 mm", "phòng khách 600x300", "tôn 0.75 600x300"):
            with self.subTest(t=t):
                self.assertIn(tr.row_role(t, KWS), ("CHI_KT", "DU_LOAI"))
        self.assertEqual(tr.row_role("cg-01 600x300", KWS), "CHI_KT")

    def test_note_codes_do_not_make_unknown(self):
        # Ghi chú 'GHCL EI120' (mã riêng của khách) — E2E 2026-11-23, BVT TAHK R200
        self.assertEqual(tr.row_role("2700x800", KWS, "ghcl ei120"), "CHI_KT")
        self.assertEqual(tr.row_role("abc 600x300", KWS, "cửa nan z"), "DU_LOAI")

    def test_khong_nhan_ra(self):
        self.assertEqual(tr.row_role("abc xyz 600x300", KWS), "KHONG_NHAN_RA")

    def test_du_loai_commercial(self):
        self.assertEqual(tr.row_role("giá đỡ 600x300", KWS), "DU_LOAI")
        self.assertEqual(tr.row_role("bộ chuyển đổi nguồn van md", KWS), "DU_LOAI")
        self.assertEqual(tr.row_role("cửa gió hồi 600x300", KWS), "DU_LOAI")

    def test_decide_matrix(self):
        self.assertEqual(tr.decide("LOAI_HANG", "KHONG_NHAN_RA", "CUA_GIO"), "TITLE_ROW_ASK")
        self.assertIsNone(tr.decide("LOAI_HANG", "KHONG_NHAN_RA", "CUA_GIO", title_wins=True))
        self.assertEqual(tr.decide("HANG_MUC", "CHI_KT", "ONG_GIO"), "TITLE_UNCLEAR")
        self.assertEqual(tr.decide("PHU_KIEN", "CHI_KT", "VAN_GIO"), "TITLE_UNCLEAR")
        self.assertIsNone(tr.decide("HANG_MUC", "CHI_KT", "KHAC"))
        self.assertIsNone(tr.decide("LOAI_HANG", "CHI_KT", "CUA_GIO"))
        self.assertIsNone(tr.decide("LOAI_HANG", "DU_LOAI", "CUA_GIO"))
        self.assertIsNone(tr.decide("HANG_MUC", "DU_LOAI", "CUA_GIO"))


class ParserIntegrationTest(unittest.TestCase):
    """Loại 4 qua parser thật: không báo + lý do TITLE_ROW_ASK; --title-wins (override title=1) → báo theo Title."""

    def _boq(self, rows):
        import openpyxl
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "S1"
        ws.append(["STT", "Tên vật tư", "Đơn vị", "Khối lượng"])
        for r in rows:
            ws.append(r)
        fd, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        wb.save(path)
        self.addCleanup(os.remove, path)
        return path

    def _parse(self, path, overrides=None):
        from swind_boq_parser import SwindBOQParser
        p = SwindBOQParser(path)
        if overrides:
            p.row_overrides = overrides
        items = p.parse_sheet("S1")
        return p, items

    def test_parser_loai4_end_to_end(self):
        path = self._boq([["1", "Cửa gió nan bầu dục kích thước:"], [None, "abc xyz 600x300", "cái", 2],
                          [None, "600x300", "cái", 3]])
        p, items = self._parse(path)
        self.assertEqual(p.skip_reasons["S1"][3]["reason"], "TITLE_ROW_ASK")
        self.assertEqual([it["source_row"] for it in items], [4])  # dòng chỉ KT vẫn báo theo Title (Loại 3)
        p2, items2 = self._parse(path, {("S1", 3): {"title": "1"}})
        rows = {it["source_row"]: it["category"] for it in items2}
        self.assertEqual(rows.get(3), "CUA_GIO")

    def test_parser_title_unclear(self):
        path = self._boq([["1", "Hệ thống thông gió"], [None, "600x300", "cái", 2]])
        p, items = self._parse(path)
        reason = (p.skip_reasons.get("S1", {}).get(3) or {}).get("reason")
        cats = [it["category"] for it in items]
        # Hoặc hỏi lại, hoặc không định báo theo nhóm Swind — tuyệt đối không lặng lẽ báo ống gió vuông
        self.assertTrue(reason == "TITLE_UNCLEAR" or "ONG_GIO" not in cats, (reason, cats))


if __name__ == "__main__":
    unittest.main()
