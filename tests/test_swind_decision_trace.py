"""Test module decision_trace (bảng 'đã hiểu thế nào')."""
import json
import os
import sys
import tempfile
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

import decision_trace as dt  # noqa: E402


class DecisionTraceTest(unittest.TestCase):
    def test_record_replaces_same_field(self):
        it = {}
        dt.record(it, "kieu", "BD", "TEN", "CG-07")
        dt.record(it, "kieu", "T", ["TITLE", "TITLE"], "CG-08B")
        self.assertEqual(it["decisions"], [{"truong": "kieu", "gia_tri": "T", "nguon": ["TITLE"], "rule": "CG-08B", "chac": True}])

    def test_review_skips_zero_qty(self):
        it = {"qty": 0, "source_sheet": "S1", "source_row": 3}
        dt.record(it, "kieu", "VCD", "MAC_DINH", "VG-02-MAC-DINH")
        self.assertEqual(dt.review_rows([it]), [])

    def test_review_rows_shape(self):
        it = {"qty": 2, "source_sheet": "S1", "source_row": 14, "raw_name": "Van 600x400"}
        dt.record(it, "kieu", "VCD", "MAC_DINH", "VG-02-MAC-DINH", sure=False)
        rows = dt.review_rows([it])
        self.assertEqual(rows, [{"sheet": "S1", "row": 14, "raw_name": "Van 600x400", "decisions": it["decisions"]}])
        self.assertIn("R14 [S1]", dt.console_lines([it])[0])

    def test_missing_decisions_ok(self):
        self.assertEqual(dt.review_rows([{"qty": 1}]), [])
        self.assertEqual(dt.explain({}), "")

    def test_write_report(self):
        it = {"qty": 1, "source_sheet": "S1", "source_row": 14, "raw_name": "Van a|b"}
        dt.record(it, "kieu", "VCD", "MAC_DINH", "VG-02")
        with tempfile.TemporaryDirectory() as d:
            out = os.path.join(d, "x", "y")
            j, m = dt.write_report([it, {"qty": 1}], out)
            self.assertTrue(os.path.exists(j) and os.path.exists(m))
            with open(j, encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertEqual(len(data), 1)
            self.assertEqual(data[0]["row"], 14)
            with open(m, encoding="utf-8") as fh:
                self.assertIn("| R14 |", fh.read())

    def test_unknown_source_rejected(self):
        with self.assertRaises(ValueError) as cm:
            dt.record({}, "kieu", "X", "XYZ", "R")
        self.assertIn("XYZ", str(cm.exception))


if __name__ == "__main__":
    unittest.main()


class PipelineTest(unittest.TestCase):
    """Parser ghi loai_hang, Agent 01 ghi kieu + model trên mỗi item (Task 3)."""

    def _run(self, rows):
        import openpyxl
        from swind_boq_parser import SwindBOQParser
        from agent_01_boq_extractor import Agent01_BOQExtractor
        from swind_utils import get_subtype_rules
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
        items = SwindBOQParser(path).parse_sheet("S1")
        Agent01_BOQExtractor.enrich_all_items(items, get_subtype_rules())
        return {it["source_row"]: it for it in items}

    @staticmethod
    def _dec(item, field):
        return next((d for d in item.get("decisions", []) if d["truong"] == field), None)

    def test_pipeline_records(self):
        by_row = self._run([["1", "CỬA GIÓ"], [None, "600x300", "cái", 2],
                            [None, "Van 600x400", "cái", 1], [None, "Cửa gió nan Z 800x400", "cái", 3]])
        r1, r2, r3 = by_row[3], by_row[4], by_row[5]
        d = self._dec(r1, "loai_hang")
        self.assertEqual((d["gia_tri"], d["rule"], d["nguon"]), ("CUA_GIO", "LH-12", ["TITLE"]))
        k2 = self._dec(r2, "kieu")
        self.assertEqual(r2["category"], "VAN_GIO")
        self.assertEqual((k2["rule"], k2["chac"]), ("VG-02-MAC-DINH", False))
        self.assertEqual(self._dec(r2, "loai_hang")["rule"], "LH-17")
        k3 = self._dec(r3, "kieu")
        self.assertEqual((k3["rule"], k3["nguon"]), ("CG-06_LOUVER_NAN_Z", ["TEN"]))
        m3 = self._dec(r3, "model")
        self.assertEqual(m3["gia_tri"], r3["resolved_spec"]["model_std"])
        self.assertEqual(m3["rule"], "CG-06_LOUVER_NAN_Z")
        for it in by_row.values():
            self.assertEqual(self._dec(it, "loai_hang")["gia_tri"], it["category"])
            self.assertIsNotNone(self._dec(it, "kieu"))

    def test_combo_keeps_parent_decisions(self):
        by_row = self._run([["1", "Cửa gió 600x300 + MFD", "cái", 2]])
        it = by_row[2]
        lh = [d for d in it["decisions"] if d["truong"] == "loai_hang"]
        self.assertEqual(len(lh), 1)
        self.assertEqual(lh[0]["gia_tri"], "CUA_GIO")
        self.assertIn("MFD", self._dec(it, "model")["gia_tri"])

    def test_duct_kieu(self):
        by_row = self._run([["1", "Cút 90 độ ống gió 800x400", "cái", 2]])
        it = by_row[2]
        self.assertEqual(self._dec(it, "loai_hang")["gia_tri"], "ONG_GIO")
        k = self._dec(it, "kieu")
        self.assertEqual(k["gia_tri"], it["resolved_spec"]["subtype"])
        self.assertTrue(k["rule"].startswith("OG-"))
        self.assertNotIn("_duct_subtype_trail", it)


class FinalFixTraceTest(unittest.TestCase):
    """Vá cuối: ống tiêu âm theo Title = OG-19 (không mặc định); van không còn gắn rule VG-06..14; record chịu decisions=None."""
    _run = PipelineTest._run
    _dec = staticmethod(PipelineTest._dec)

    def test_silencer_under_tieu_am_title(self):
        by_row = self._run([["1", "ỐNG TIÊU ÂM"], [None, "500x300x1500, tôn dày 0.58mm", "cái", 2]])
        it = by_row[3]
        lh, k = self._dec(it, "loai_hang"), self._dec(it, "kieu")
        self.assertEqual(it["category"], "TIEU_AM")
        self.assertEqual(k["rule"], "OG-19")
        self.assertTrue(k["chac"])
        self.assertEqual(k["nguon"], lh["nguon"])

    def test_record_decisions_none(self):
        it = {"decisions": None}
        dt.record(it, "kieu", "X", "TEN", "R")
        self.assertEqual(len(it["decisions"]), 1)

    def test_damper_motor_row_rule_is_type_rule(self):
        it = self._run([[None, "Van dập lửa motor 600x400", "cái", 1]])[2]
        k = self._dec(it, "kieu")
        self.assertIn(k["rule"], ("VG-01", "VG-02A", "VG-02", "VG-03", "VG-04", "VG-05"))
        self.assertTrue(k["chac"])


class CategoryChangeTraceTest(unittest.TestCase):
    """Fix round 1: đổi loại hàng sau parser phải ghi đúng nguồn / độ chắc (không giữ rule parser cũ)."""

    def test_agent02_auto_accept_is_unsure(self):
        from unittest import mock
        import agent_02_boq_reviewer as a02
        it = {"category": "KHAC", "raw_name": "abc xyz 600x300", "name": "abc xyz 600x300", "qty": 2,
              "source_sheet": "S1", "source_row": 5, "suggested_cat": "CUA_GIO", "suggested_score": 0.8}
        dt.record(it, "loai_hang", "KHAC", "TEN", "LH-KHAC", sure=False)
        with mock.patch.object(a02, "save_learned_keyword") as save:  # không ghi file học thật
            left = a02.apply_suggestions_non_interactive([it], auto_accept=True, project_name="T")
        save.assert_called_once()
        self.assertEqual(left, [])
        self.assertEqual(it["category"], "CUA_GIO")
        lh = [d for d in it["decisions"] if d["truong"] == "loai_hang"]
        self.assertEqual(lh, [{"truong": "loai_hang", "gia_tri": "CUA_GIO", "nguon": ["HOC_MAY"],
                               "rule": "AGENT02-GOI-Y", "chac": False}])
        self.assertEqual([r["row"] for r in dt.review_rows([it])], [5])

    def test_agent01_unrecorded_change_defaults(self):
        from agent_01_boq_extractor import Agent01_BOQExtractor
        from swind_utils import get_subtype_rules
        it = {"category": "THUONG_MAI", "raw_name": "Quạt hút", "name": "Quạt hút", "qty": 1, "w": 0, "h": 0}
        dt.record(it, "loai_hang", "KHAC", "TEN", "LH-KHAC", sure=False)
        Agent01_BOQExtractor.resolve_item_spec(it, get_subtype_rules())
        lh = next(d for d in it["decisions"] if d["truong"] == "loai_hang")
        self.assertEqual((lh["gia_tri"], lh["rule"], lh["nguon"], lh["chac"]),
                         ("THUONG_MAI", "AGENT01-LOAI-DOI", ["MAC_DINH"], False))

    def test_parser_khac_row_unsure(self):
        import openpyxl
        from swind_boq_parser import SwindBOQParser
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "S1"
        ws.append(["STT", "Tên vật tư", "Đơn vị", "Khối lượng", "Đơn giá"])
        ws.append(["1", "Zqwv blorp 600x300", "cái", 2, 100000])  # có giá đối tác → dòng KHAC được giữ (PV-04)
        fd, path = tempfile.mkstemp(suffix=".xlsx")
        os.close(fd)
        wb.save(path)
        self.addCleanup(os.remove, path)
        items = SwindBOQParser(path).parse_sheet("S1")
        khac = [it for it in items if it["category"] == "KHAC"]
        self.assertTrue(khac, [it["category"] for it in items])
        lh = next(d for d in khac[0]["decisions"] if d["truong"] == "loai_hang")
        self.assertEqual((lh["gia_tri"], lh["rule"], lh["chac"]), ("KHAC", "LH-KHAC", False))


class RunnerReportTest(unittest.TestCase):
    def test_runner_writes_report(self):
        import subprocess
        import openpyxl
        with tempfile.TemporaryDirectory() as td:
            boq = os.path.join(td, "_test_decision_trace.xlsx")
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "S1"
            ws.append(["STT", "Tên", "ĐVT", "Khối lượng"])
            ws.append(["", "CỬA GIÓ", "", ""])
            ws.append([1, "600x300", "cái", 2])
            ws.append([2, "Van 600x400", "cái", 1])
            ws.append([3, "Cửa gió nan Z 800x400", "cái", 1])
            wb.save(boq)
            out_root = os.path.join(td, "out")
            env = dict(os.environ, SWIND_NO_LEARNING_WRITE="1", SWIND_OUTPUT_DIR=out_root)
            py = os.path.join(ROOT, "venv", "bin", "python")
            if not os.path.exists(py):
                py = sys.executable
            p = subprocess.run([py, os.path.join(ROOT, "src", "swind_master_runner.py"), boq,
                                "--non-interactive", "--auto-accept"],
                               capture_output=True, text=True, env=env, cwd=ROOT, timeout=300)
            self.assertIn("[ĐÃ HIỂU THẾ NÀO]", p.stdout, p.stdout[-2000:] + p.stderr[-1000:])
            jp = os.path.join(out_root, "_test_decision_trace", "internal_estimation", "DECISION_TRACE.json")
            self.assertTrue(os.path.exists(jp), os.listdir(out_root) if os.path.isdir(out_root) else p.stdout[-1500:])
            with open(jp, encoding="utf-8") as f:
                data = json.load(f)
            self.assertTrue(data)
            for el in data:
                self.assertIn("decisions", el)
            self.assertIn("Bảng đã hiểu thế nào", p.stdout)

    def test_inspector_shows_explanation(self):
        import swind_item_inspector as si
        r = si.inspect_single_item("Van 600x400")
        self.assertIn("decisions", r[0])


class SettledDefaultTraceTest(unittest.TestCase):
    """Việc 3: mặc định đã chốt (GIU trong default_rules.json) không còn nằm trong bảng cần xem; vẫn có trong decisions."""

    def test_giu_default_not_reviewed(self):
        it = {"qty": 2, "source_sheet": "S1", "source_row": 4, "raw_name": "Cửa gió 300x300"}
        dt.record(it, "kieu", "SDG", "MAC_DINH", "CG-09-MAC-DINH", sure=False)
        self.assertEqual(dt.review_rows([it]), [])
        self.assertEqual(it["decisions"][0]["rule"], "CG-09-MAC-DINH")

    def test_giu_plus_unsure_other_still_listed(self):
        it = {"qty": 2, "source_sheet": "S1", "source_row": 4, "raw_name": "x"}
        dt.record(it, "kieu", "SDG", "MAC_DINH", "CG-09-MAC-DINH", sure=False)
        dt.record(it, "loai_hang", "KHAC", "TEN", "LH-KHAC", sure=False)
        self.assertEqual([r["row"] for r in dt.review_rows([it])], [4])
