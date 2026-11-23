"""Agent 10 — ghép giá báo giá cũ (2026-11-23, dự án 261123_HH3_RFQ: combo VCD+FD, cấp EI, hộp gió,
dòng đánh số cột, khoá dòng, nhóm hỏi, kho ghi nhớ, CLI --plan-json / --decisions)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

import openpyxl

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
sys.path.insert(0, os.path.join(ROOT, "src"))

import agent_10_old_quote_carrier as a10  # noqa: E402
from agent_10_old_quote_carrier import build_signature, combo_family, ei_level, load_boq_rows, match_row  # noqa: E402

_ROW = [100]


def _item(name, spec="", model="", unit="Cái", qty=1):
    _ROW[0] += 1
    return {"row": _ROW[0], "name": name, "spec": spec, "model": model, "unit": unit, "qty": qty, "is_item": True}


def _entry(name, note="", model="", price=100000, sheet="BG", row=10, prio=0, qty=1):
    sig = build_signature(name, note, model)
    sig["family_priced"] = a10.priced_family(sig)
    return {"sheet": sheet, "row": row, "prio": prio, "name": name, "note": note, "model": model, "remark": note,
            "price": price, "qty": qty, "sig": sig}


class SignatureTest(unittest.TestCase):
    def test_combo_family(self):
        self.assertEqual(combo_family("Van điều chỉnh lưu lượng (VCD) + van ngăn lửa (FD) 200x150"), "VCD+FD")
        self.assertEqual(combo_family("Louver + lưới chắn côn trùng + van ngăn cháy FD 1000x400"), "LOUVER+FD")
        self.assertEqual(combo_family("Louver + lưới chắn côn trùng + van ngăn cháy điều khiển bằng động cơ (MFD) 800x400"),
                         "LOUVER+MFD")
        self.assertIsNone(combo_family("Van ngăn lửa (FD) cầu chì nhiệt 200x150, chịu lửa EI30"))
        self.assertIsNone(combo_family("Louver + lưới chắn côn trùng 1000x300"))

    def test_ei_level(self):
        self.assertEqual(ei_level("SWIND-1.05- MFD-EI120"), 120)
        self.assertEqual(ei_level("giới hạn chịu lửa EI 60"), 60)
        self.assertIsNone(ei_level("Van 1 chiều"))

    def test_combo_not_matched_to_single_valve(self):
        m = match_row(_item("Van điều chỉnh lưu lượng (VCD) + van ngăn lửa (FD) 200x150"),
                      [_entry("Van ngăn lửa (FD): 200x150", model="SWIND-2.01- E-FD-EI120")])
        self.assertEqual(m["status"], "NEW")

    def test_combo_old_model_fd_still_combo(self):
        m = match_row(_item("Louver + lưới chắn côn trùng + van ngăn cháy FD 800x400, chịu lửa EI120"),
                      [_entry("Louver + Luới chắn côn trùng + Van ngăn cháy (FD) : 800x400", model="SWIND-2.01- E-FD-EI120")])
        self.assertEqual(m["status"], "EXACT")

    def test_ei_mismatch_is_review(self):
        m = match_row(_item("Van ngăn lửa (FD) cầu chì nhiệt 600x300, chịu lửa EI30"),
                      [_entry("Van ngăn lửa (FD): 600x300", model="SWIND-2.01- E-FD-EI120")])
        self.assertEqual(m["status"], "REVIEW")
        self.assertIn("ei", m["flags"])

    def test_ei_from_spec_and_model(self):
        it = _item("Van ngăn lửa điều khiển bằng động cơ (MFD) 800x800", spec="giới hạn chịu lửa EI120")
        m = match_row(it, [_entry("MFD 800x800", model="SWIND-1.05- MFD-EI120")])
        self.assertEqual(m["status"], "EXACT")

    def test_box_mismatch_is_review(self):
        m = match_row(_item("Louver lấy gió tươi + lưới chắn côn trùng 300x150"),
                      [_entry("Louver lấy gió tươi 300x150 + Hộp gió + LCCT", note="WL+N+ hộp gió")])
        self.assertEqual(m["status"], "REVIEW")
        self.assertIn("box", m["flags"])

    def test_numbering_row_skipped(self):
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "boq.xlsx")
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.append(["Stt/No.", "Mô tả/Description", "Spec - Yêu cầu kỹ thuật", "Đv/ Unit", "Khối lượng\nQ.ty"])
            ws.append(["1", "2", "3", "4", "5"])
            ws.append([1, "Van điều chỉnh lưu lượng gió (VCD) D100", "", "Cái", 5])
            wb.save(p)
            _, rows = load_boq_rows(p)
        names = [r["name"] for r in rows]
        self.assertNotIn("2", names)
        self.assertIn("Van điều chỉnh lưu lượng gió (VCD) D100", names)


def _it(row, name, unit="Cái"):
    return {"row": row, "name": name, "spec": "", "model": "", "unit": unit, "qty": 1, "is_item": True}


class OldHeaderTest(unittest.TestCase):
    def test_model_in_second_header_row(self):
        """BG Swind: 'Model' nằm ở dòng tiêu đề thứ 2 (dưới 'Danh mục sản phẩm') — trước đây bị bỏ qua nên cột Model BG trống
        (User hỏi 2026-11-23, dự án 261123_HH3_RFQ)."""
        with tempfile.TemporaryDirectory() as d:
            p = os.path.join(d, "bg.xlsx")
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "BG"
            ws.append(["STT", "Danh mục sản phẩm", None, "Thương hiệu", "Kích thước (mm)", None, None, None, "Modul", "L", "Độ dày",
                       "Đơn vị", "Số lượng", "Đơn giá", "Thành tiền", "Ghi chú"])
            ws.append([None, None, "Model", "Thương hiệu", "A1", "A2", "B1", "B2"])
            ws.append([1, "Louver 1000x300, bọc lưới chắn côn trùng", "WL+N", "SWIND", 1000, 300, 950, 250, None, None, None,
                       "Cái", 2, 468000, None, "louver nan Z +LCCT"])
            wb.save(p)
            e = a10.load_old_quote(p, ["BG"])[0]
        self.assertEqual(e["model"], "WL+N")
        self.assertEqual(e["remark"], "louver nan Z +LCCT")


class GroupingTest(unittest.TestCase):
    def test_keys_stable_on_insert_and_duplicates(self):
        a = [_it(10, "Van VCD D100"), _it(11, "Louver 300x150"), _it(12, "Louver 300x150")]
        b = [_it(10, "Van VCD D100"), _it(11, "Cửa mới 500x500"), _it(12, "Louver 300x150"), _it(13, "Louver 300x150")]
        ka, kb = a10.row_keys(a), a10.row_keys(b)
        self.assertEqual(ka[10], kb[10])
        self.assertEqual(ka[11], kb[12])
        self.assertEqual(ka[12], kb[13])
        self.assertTrue(ka[11].endswith("#1"))
        self.assertTrue(ka[12].endswith("#2"))

    def test_key_ignores_spec_text(self):
        x, y = _it(10, "Van VCD D100"), _it(10, "Van VCD D100")
        x["spec"], y["spec"] = "KL theo khu: L1 5", "KL theo khu: L1 9"
        self.assertEqual(a10.row_keys([x])[10], a10.row_keys([y])[10])

    def test_classify_groups(self):
        self.assertEqual(a10.classify({"status": "EXACT", "flags": set()})[:2], ("khop", "carry"))
        self.assertEqual(a10.classify({"status": "REVIEW", "flags": {"ei", "box"}})[:2], ("khac_ei", "ask"))
        self.assertEqual(a10.classify({"status": "REVIEW", "flags": {"box"}})[:2], ("khac_hop", "ask"))
        self.assertEqual(a10.classify({"status": "EXACT", "flags": {"multi"}})[:2], ("nhieu_gia", "ask"))
        self.assertEqual(a10.classify({"status": "CONVERTED", "flags": set()})[:2], ("combo_doi_loai", "new"))
        self.assertEqual(a10.classify({"status": "NEW", "flags": set()})[:2], ("khong_co", "new"))

    def test_classify_profile_same_code_carries(self):
        e = _entry("EAG 250x250 + OBD", model="SDG+O")
        m = {"status": "REVIEW", "flags": {"profile"}, "entry": e}
        it = {"sig": build_signature("EAG 250x250 + OBD", "", "")}
        self.assertEqual(a10.classify(m, it)[:2], ("kieu_nan", "carry"))
        it2 = {"sig": build_signature("Miệng gió dạng nan 250x250 + OBD", "", "")}
        self.assertEqual(a10.classify(m, it2)[:2], ("kieu_nan", "ask"))

    def test_pick_entry_multi_price(self):
        e1 = _entry("FD 200x150", model="E-FD-EI120", price=930348, sheet="L2", row=209, prio=2, qty=1)
        e2 = _entry("FD 200x150", model="E-FD-EI120", price=1111348, sheet="L1", row=116, prio=1, qty=37)
        e3 = _entry("FD 200x150", model="E-FD-EI120", price=1111348, sheet="L2", row=116, prio=2, qty=37)
        chosen, reason = a10.pick_entry({"candidates": [e1, e3, e2], "entry": e1})
        self.assertIs(chosen, e2)  # sheet ưu tiên (prio nhỏ) trước
        self.assertIn("930,348", reason)
        self.assertIn("1,111,348", reason)

    def test_suggest_mfd_from_old_models(self):
        ms = [{"entry": {"model": "SWIND-1.05- MFD-EI120", "sheet": "BG Than", "row": 85, "note": "", "remark": "BELIMO"}},
              {"entry": {"model": "SWIND-1.05- MFD-EI120", "sheet": "BG Than", "row": 84, "note": "", "remark": ""}}]
        opt = a10.suggest_options(ms)
        self.assertEqual(opt["mfd_model"]["value"], "1.05")
        self.assertIn("BG Than!85", opt["mfd_model"]["evidence"])
        self.assertEqual(opt["motor_brand"]["value"], "BELIMO")
        self.assertNotIn("mfd_model", a10.suggest_options([{"entry": {"model": "VCD", "sheet": "x", "row": 1, "note": "", "remark": ""}}]))

    def test_suggest_project_key(self):
        self.assertEqual(a10.suggest_project_key("x/261123_HH3_RFQ_Cua_gio.xlsx"), "HH3_RFQ_Cua_gio")


SCRIPT = os.path.join(ROOT, "src", "agent_10_old_quote_carrier.py")
PY = sys.executable


class CliTest(unittest.TestCase):
    """CLI --plan-json / --decisions trên BOQ + BG cũ tự dựng (không gọi runner)."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.mem_dir = os.path.join(d, "mem")
        os.makedirs(self.mem_dir)
        self.old = os.path.join(d, "bg_cu.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "BG"
        ws.append(["STT", "Danh mục sản phẩm", "Model", "Thương hiệu", "Kích thước (mm)", None, None, None, "Modul", "L",
                   "Độ dày", "Đơn vị", "Số lượng", "Đơn giá", "Thành tiền", "Ghi chú"])
        ws.append([1, "Van ngăn lửa (FD): 600x300", "SWIND-2.01- E-FD-EI120", "SWIND", 600, 300, None, None, None, None, None, "Cái", 5, 2262085])
        ws.append([2, "Louver lấy gió tươi 300x150 + Hộp gió + LCCT", None, "SWIND", 300, 150, None, None, None, None, None, "Cái", 9, 140700,
                   None, "WL+N+ hộp gió"])
        ws.append([3, "Van 1 chiều (NRD): 400x200", "NRD", "SWIND", 400, 200, None, None, None, None, None, "Cái", 1, 188000])
        wb.save(self.old)
        self.boq = os.path.join(d, "261123_TEST_RFQ.xlsx")
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "RFQ"
        ws.append(["Stt/No.", "Mô tả/Description", "Spec - Yêu cầu kỹ thuật", "Đv/ Unit", "Khối lượng\nQ.ty"])
        ws.append(["1", "2", "3", "4", "5"])
        for i, n in enumerate(["Van ngăn lửa (FD) 600x300, chịu lửa EI30",
                               "Van điều chỉnh lưu lượng (VCD) + van ngăn lửa (FD) 200x150",
                               "Louver lấy gió tươi + lưới chắn côn trùng 300x150",
                               "Van gió 1 chiều (NRD) 400x200",
                               "Van gió 1 chiều (NRD) 900x900"], 1):
            ws.append([i, n, "", "Cái", 2])
        wb.save(self.boq)
        self.plan = os.path.join(d, "plan.json")

    def tearDown(self):
        self.tmp.cleanup()

    def _cli(self, *extra):
        cmd = [PY, SCRIPT, self.boq, "--old-quote", self.old, "--old-sheets", "BG", "--project-key", "TEST",
               "--memory-dir", self.mem_dir] + list(extra)
        p = subprocess.run(cmd, capture_output=True, text=True, cwd=ROOT)
        return p.returncode, p.stdout + p.stderr

    def _run_plan(self):
        rc, out = self._cli("--plan-json", self.plan)
        with open(self.plan, encoding="utf-8") as f:
            return rc, json.load(f), out

    def test_plan_json_groups_and_no_runner(self):
        rc, plan, out = self._run_plan()
        self.assertEqual(rc, 0, out)
        g = {r["name"]: (r["group"], r["decided_by"]) for r in plan["rows"]}
        self.assertEqual(g["Van ngăn lửa (FD) 600x300, chịu lửa EI30"], ("khac_ei", None))
        self.assertEqual(g["Van điều chỉnh lưu lượng (VCD) + van ngăn lửa (FD) 200x150"], ("khong_co", "auto"))
        self.assertEqual(g["Louver lấy gió tươi + lưới chắn côn trùng 300x150"], ("khac_hop", None))
        self.assertEqual(g["Van gió 1 chiều (NRD) 400x200"], ("khop", "auto"))
        self.assertEqual(len(plan["rows"]), 5)
        self.assertEqual(plan["project_key"], "TEST")
        self.assertNotIn("SWIND báo giá mới", out)  # không chạy runner
        self.assertEqual(os.listdir(self.mem_dir), [])  # plan không ghi kho

    def test_plan_applies_memory(self):
        _, plan, _ = self._run_plan()
        key = next(r["key"] for r in plan["rows"] if r["group"] == "khac_ei")
        with open(os.path.join(self.mem_dir, "TEST.json"), "w", encoding="utf-8") as f:
            json.dump({"old_quote": plan["old_quote"], "rows": {key: {"action": "new"}}}, f)
        _, plan2, _ = self._run_plan()
        row = next(r for r in plan2["rows"] if r["key"] == key)
        self.assertEqual(row["decided_by"], "memory")
        self.assertTrue(plan2["memory"]["exists"])

    def test_missing_decision_exits_3(self):
        dec = os.path.join(self.tmp.name, "dec.json")
        with open(dec, "w", encoding="utf-8") as f:
            json.dump({"rows": {}}, f)
        rc, out = self._cli("--decisions", dec)
        self.assertEqual(rc, 3, out)
        self.assertIn("THIẾU QUYẾT ĐỊNH", out)

    def test_decisions_run_has_no_legacy_ask_banner(self):
        """Chạy qua --decisions: không in banner '⚠️ [HỎI LẠI USER] ... CHƯA tự nhặt giá' của luồng cờ cũ (trợ lý đọc log sẽ hiểu nhầm)."""
        _, plan, _ = self._run_plan()
        dec = os.path.join(self.tmp.name, "dec.json")
        with open(dec, "w", encoding="utf-8") as f:
            json.dump({"rows": {r["key"]: {"action": "new"} for r in plan["rows"] if r["decided_by"] is None}}, f)
        rc, out = self._cli("--decisions", dec, "--dry-run")
        self.assertEqual(rc, 0, out)
        self.assertNotIn("HỎI LẠI USER", out)
        self.assertIn("[--decisions]", out)

    def test_no_old_sheets_writes_sheet_summary(self):
        p = subprocess.run([PY, SCRIPT, self.boq, "--old-quote", self.old, "--plan-json", self.plan, "--memory-dir", self.mem_dir],
                           capture_output=True, text=True, cwd=ROOT)
        self.assertEqual(p.returncode, 1)
        with open(self.plan, encoding="utf-8") as f:
            info = json.load(f)
        self.assertEqual(info["sheet_summary"], [{"sheet": "BG", "priced_rows": 3}])
        self.assertEqual(info["project_key_suggestion"], "TEST_RFQ")


if __name__ == "__main__":
    unittest.main()
