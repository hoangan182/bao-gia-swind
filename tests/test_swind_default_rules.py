"""Test bảng chính sách mặc định (default_rules.json, src/default_policy.py) — Việc 3, User chốt 2026-11-24."""
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import default_policy as dp  # noqa: E402


def _item(rule, gia_tri="VCD", truong="kieu", name="Van gió", qty=2, row=14, nguon=("MAC_DINH",), **kw):
    it = {"raw_name": name, "qty": qty, "source_sheet": "S", "source_row": row,
          "decisions": [{"truong": truong, "gia_tri": gia_tri, "nguon": list(nguon), "rule": rule, "chac": False}]}
    it.update(kw)
    return it


class RuleTableTest(unittest.TestCase):
    def test_every_rule_has_source_and_examples(self):
        rules = dp.load_rules()["_all"]["quy_tac"]
        self.assertEqual([r["id"] for r in rules], ["MD-01", "MD-02", "MD-03", "MD-04", "MD-05", "MD-06"])
        for r in rules:
            with self.subTest(rule=r["id"]):
                self.assertTrue(r.get("nguon"))
                self.assertTrue(r.get("ly_do"))
                self.assertTrue(r.get("vi_du_dung"))
                self.assertIn(r["xu_ly"], ("GIU", "BAO_VA_HOI"))


class ExamplesTest(unittest.TestCase):
    def test_rule_examples(self):
        for r in dp.load_rules()["_all"]["quy_tac"]:
            for ex in r["vi_du_dung"]:
                with self.subTest(rule=r["id"], ex=ex["mo_ta"]):
                    it = {"qty": 1, "source_sheet": "S", "source_row": 1, "raw_name": "x",
                          "decisions": [{"truong": "kieu", "gia_tri": ex["gia_tri"], "nguon": ex.get("nguon", ["MAC_DINH"]),
                                         "rule": ex["rule"], "chac": False}]}
                    if ex.get("default_confirmed"):
                        it["default_confirmed"] = True
                    if ex.get("category"):
                        it["category"] = ex["category"]
                    p = dp.policy(it)
                    self.assertEqual(p["id"] if p else None, ex["ket_qua"])


class PolicyTest(unittest.TestCase):
    def test_vg02_default_asks(self):
        it = _item("VG-02-MAC-DINH", name="Van 600x400")
        self.assertEqual(dp.policy(it)["id"], "MD-02")
        self.assertIn("ĐÃ HIỂU THEO MẶC ĐỊNH: VCD", dp.bg_flag(it))
        self.assertIn("S!14:ok=1", dp.bg_flag(it))

    def test_partner_price_not_flagged(self):
        it = _item("VG-02-MAC-DINH", name="Van 600x400", override_price=1500000)
        self.assertIsNone(dp.policy(it))
        self.assertIsNone(dp.bg_flag(it))
        self.assertEqual(dp.gate_lines([it]), [])
        # ref_price riêng (cửa/van vẫn do Swind tính giá) → vẫn hỏi
        for kw in ({"ref_price": 1500000}, {"ref_price": 1500000, "override_price": 0}, {"override_price": "abc"}, {"override_price": None}):
            self.assertEqual(dp.policy(_item("VG-02-MAC-DINH", **kw))["id"], "MD-02")

    def test_cg09_kept(self):
        it = _item("CG-09-MAC-DINH", "SDG")
        self.assertIsNone(dp.policy(it))
        self.assertIsNone(dp.bg_flag(it))

    def test_og_default_kept(self):
        it = _item("OG-MAC-DINH", "ONG_VUONG", name="Ống gió 600x400")
        self.assertIsNone(dp.policy(it))

    def test_parser5_title_asks_without_mac_dinh_nguon(self):
        it = _item("LH-26", "ONG_GIO", "loai_hang", nguon=("TITLE",))
        self.assertEqual(dp.policy(it)["id"], "MD-04")

    def test_confirmed(self):
        self.assertIsNone(dp.policy(_item("VG-02-MAC-DINH", default_confirmed=True)))

    def test_no_decisions(self):
        self.assertIsNone(dp.policy({"raw_name": "x", "default_confirmed": True}))
        self.assertIsNone(dp.policy({"raw_name": "x"}))

    def test_first_match_in_order(self):
        it = _item("CG-09-MAC-DINH", "SDG")
        it["decisions"].append({"truong": "kieu", "gia_tri": "VCD", "nguon": [], "rule": "VG-02-MAC-DINH", "chac": False})
        self.assertEqual(dp.policy(it)["id"], "MD-02")


class GateTest(unittest.TestCase):
    def test_gate_lines_zero_qty(self):
        self.assertEqual(dp.gate_lines([_item("VG-02-MAC-DINH", qty=0)]), [])

    def test_gate_lines_summary(self):
        lines = dp.gate_lines([_item("VG-02-MAC-DINH"), _item("CG-09-MAC-DINH", "SDG")])
        self.assertEqual(len(lines), 1)
        self.assertIn("[HỎI LẠI USER] 1 dòng báo theo MẶC ĐỊNH", lines[0])
        self.assertIn("R14 'Van gió'=VCD", lines[0])

    def test_gate_sheet_prefix_and_label(self):
        it = _item("AGENT02-GOI-Y", "ONG_GIO", truong="loai_hang", nguon=("HOC_MAY",))
        self.assertIn("S!R14 'Van gió'=ống gió / phụ kiện ống", dp.gate_lines([it])[0])
        it2 = dict(it); del it2["source_sheet"]
        self.assertIn("R14 'Van gió'", dp.gate_lines([it2])[0])
        self.assertNotIn("ONG_GIO", dp.gate_lines([it])[0])

    def test_bg_flag_zero_qty_none(self):
        self.assertIsNone(dp.bg_flag(_item("VG-02-MAC-DINH", qty=0)))
        self.assertIsNone(dp.bg_flag(_item("VG-02-MAC-DINH", qty="x")))
        self.assertIsNotNone(dp.bg_flag(_item("VG-02-MAC-DINH", qty=1)))

    def test_bg_flag_label_vi(self):
        it = _item("AGENT02-GOI-Y", "VAN_GIO", truong="loai_hang", nguon=("HOC_MAY",))
        self.assertIn("van gió (BOQ", dp.bg_flag(it))
        it = _item("AGENT02-GOI-Y", "LA_LA", truong="loai_hang", nguon=("HOC_MAY",))
        self.assertIn("LA_LA (BOQ", dp.bg_flag(it))

    def test_md04_only_ong_gio(self):
        self.assertEqual(dp.policy(_item("LH-26", "ONG_GIO", truong="loai_hang", nguon=("TITLE",)))["id"], "MD-04")
        self.assertIsNone(dp.policy(_item("LH-26", "VAN_GIO", truong="loai_hang", nguon=("TITLE",))))

    def test_thuong_mai_khac_not_flagged(self):
        for c in ("THUONG_MAI", "KHAC"):
            self.assertIsNone(dp.policy(_item("AGENT02-GOI-Y", "VAN_GIO", truong="loai_hang", category=c)))

    def test_gate_limit(self):
        items = [_item("VG-02-MAC-DINH", row=i) for i in range(5)]
        self.assertEqual(dp.gate_lines(items, limit=2)[0].count("=VCD"), 2)


if __name__ == "__main__":
    unittest.main()


class BgFlagWrittenTest(unittest.TestCase):
    def test_bg_flag_written(self):
        """Dòng van mặc định chưa chốt → BG ghi 'ĐÃ HIỂU THEO MẶC ĐỊNH' ở Ghi chú + tô vàng (cùng cơ chế lỗi gõ)."""
        from swind_excel_builder import SwindExcelBuilder
        spec = {"model_std": "VCD", "model_fslf": "VCD", "model_bfn": "VCD", "brand": "", "a1": "", "a2": "",
                "b1": 600, "b2": 400, "modul": "", "l_col": "", "thk_col": "", "note_std": "", "note_fslf": "", "note_bfn": ""}
        base = {"name": "Van 600x400", "raw_name": "Van 600x400", "unit": "Cái", "qty": 2, "category": "VAN_GIO",
                "section": "S", "source_sheet": "S", "source_row": 14, "resolved_spec": spec}
        flagged = dict(base, decisions=[{"truong": "kieu", "gia_tri": "VCD", "nguon": ["MAC_DINH"],
                                         "rule": "VG-02-MAC-DINH", "chac": False}])
        plain = dict(base, source_row=15, decisions=[])
        b = SwindExcelBuilder()
        b.build_quotation_sheets([flagged, plain])
        ws = b.wb["BG"]
        hit = [r for r, *_ in b.flagged_bg_rows]
        self.assertEqual(len(hit), 1)
        r = hit[0]
        self.assertIn("ĐÃ HIỂU THEO MẶC ĐỊNH", str(ws.cell(r, 16).value))
        self.assertEqual(ws.cell(r, 2).fill.fgColor.rgb[-6:], "FFFF00")
        self.assertNotEqual(ws.cell(r + 1, 2).fill.fgColor.rgb[-6:], "FFFF00")


class OverrideKeysTest(unittest.TestCase):
    """--override "<sheet>!<dòng>:ok=1" (duyệt mặc định) / loai=<mã> (User chỉ loại) — Việc 3 Task 4, 2026-11-25."""

    def _run(self, rows, overrides=None, title="Hệ thống thông gió", header=("STT", "Tên vật tư", "Đơn vị", "Khối lượng")):
        import tempfile
        import openpyxl
        from swind_boq_parser import SwindBOQParser
        from agent_01_boq_extractor import Agent01_BOQExtractor
        from swind_utils import get_subtype_rules
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "S1"
        ws.append(list(header))
        if title:
            ws.append(["A", title])
        for r in rows:
            ws.append(r)
        fd, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        wb.save(path)
        self.addCleanup(os.remove, path)
        p = SwindBOQParser(path)
        if overrides:
            p.row_overrides = overrides
        items = p.parse_sheet("S1")
        Agent01_BOQExtractor.enrich_all_items(items, get_subtype_rules())
        return {it["source_row"]: it for it in items}

    @staticmethod
    def _dec(it, field):
        return next((d for d in it.get("decisions") or [] if d.get("truong") == field), None)

    def test_override_ok(self):
        base = self._run([[1, "Van 600x400", "cái", 2]])[3]
        self.assertIsNotNone(dp.policy(base), base.get("decisions"))  # điều kiện tiền đề: đang báo theo mặc định
        it = self._run([[1, "Van 600x400", "cái", 2]], {("S1", 3): {"ok": "1"}})[3]
        self.assertTrue(it.get("default_confirmed"))
        self.assertIsNone(dp.policy(it))
        self.assertIsNone(dp.bg_flag(it))
        for k in ("model_std", "model_code"):
            self.assertEqual(it["resolved_spec"].get(k), base["resolved_spec"].get(k))
        k = self._dec(it, "kieu")
        self.assertEqual(k["rule"], self._dec(base, "kieu")["rule"])
        self.assertIn("CO_USER", k["nguon"])
        self.assertTrue(k["chac"])
        import decision_trace
        self.assertEqual(decision_trace.review_rows([it]), [])

    def test_override_ok_zero_is_noop(self):
        it = self._run([[1, "Van 600x400", "cái", 2]], {("S1", 3): {"ok": "0"}})[3]
        self.assertFalse(it.get("default_confirmed"))
        self.assertIsNotNone(dp.policy(it))

    def test_override_loai(self):
        it = self._run([[1, "Van 600x400", "cái", 2]], {("S1", 3): {"loai": "MD"}})[3]
        k = self._dec(it, "kieu")
        self.assertEqual(k["gia_tri"], "MD")
        self.assertEqual(k["rule"], "VG-01")
        self.assertIsNone(dp.policy(it))

    def test_loai_replaces_model_column(self):
        # Fix round 1 (review Task 4): loai THAY toàn bộ chữ cột Model (Model 'MFD' / '1.04' + loai=MD → MD, không MFD)
        hdr = ("STT", "Tên vật tư", "Model", "Đơn vị", "Khối lượng")
        for model in ("MFD", "1.04"):
            with self.subTest(model=model):
                rows = [[1, "Van 600x400", model, "cái", 2]]
                base = self._run(rows, header=hdr)[3]
                self.assertEqual(self._dec(base, "kieu")["gia_tri"], "MFD")  # tiền đề: cột Model được parser đọc
                it = self._run(rows, {("S1", 3): {"loai": "MD"}}, header=hdr)[3]
                self.assertEqual(it["model"], "MD")
                k = self._dec(it, "kieu")
                self.assertEqual(k["gia_tri"], "MD")
                self.assertEqual(k["rule"], "VG-01")
                self.assertNotIn("MFD", str(it["resolved_spec"].get("model_std")))

    def test_loai_on_diffuser(self):
        # Cỡ vuông 600x600: khuếch tán SD chỉ có ở cửa vuông 600/450/300 (diffuser_rules.json, AGENTS.md 4a-0b) —
        # 'Cửa gió 600x300' + loai=SD vẫn ra SDG theo rule hiện hành (không đổi rule nghiệp vụ trong Task 4).
        base = self._run([[1, "Cửa gió 600x600", "cái", 2]])[3]
        self.assertTrue(str(base["resolved_spec"]["model_std"]).startswith("SDG"))
        it = self._run([[1, "Cửa gió 600x600", "cái", 2]], {("S1", 3): {"loai": "SD"}})[3]
        m = str(it["resolved_spec"]["model_std"])
        self.assertTrue(m.startswith("SD") and not m.startswith("SDG"), m)

    def test_ok_without_default(self):
        rows = [[1, "Van MD 600x400", "cái", 2]]
        base = self._run(rows)[3]
        it = self._run(rows, {("S1", 3): {"ok": "1"}})[3]
        self.assertIsNone(dp.policy(base))
        self.assertIsNone(dp.policy(it))
        self.assertEqual(it["resolved_spec"].get("model_std"), base["resolved_spec"].get("model_std"))
        self.assertEqual(it["category"], base["category"])
