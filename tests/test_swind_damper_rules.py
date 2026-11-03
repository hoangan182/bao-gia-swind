"""
Test bảng rule nhận diện VAN GIÓ (data/master_data/damper_rules.json → src/damper_classifier.py).

Mỗi rule phải có nguồn gốc, lý do và ≥ 1 ví dụ; mọi `vi_du_dung` / `vi_du_sai` được chạy qua Agent01.resolve_item_spec
và so loại van / Model / chữ trong ghi chú; `vi_du_combo` chạy bộ tách van của parser. Sửa / thêm rule bắt buộc thêm ví dụ.
Chạy: ./venv/bin/python -m unittest discover -s tests -p "test_swind_*.py"
"""
import os
import sys
import tempfile
import unittest

import openpyxl

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, SRC)

import damper_classifier as dmc  # noqa: E402
from agent_01_boq_extractor import Agent01_BOQExtractor  # noqa: E402
from swind_utils import get_subtype_rules  # noqa: E402


def _run_example(ex):
    """Dựng dòng BOQ VAN_GIO từ ví dụ (Tên + Ghi chú + Title cha + cột Model), trả (resolved_spec, item)."""
    title = ex.get("title", "")
    w, h = ex.get("kt", [0, 0])
    item = {
        "category": "VAN_GIO", "raw_name": ex["ten"], "name": f"{title} {ex['ten']}".strip(),
        "note_boq": ex.get("ghi_chu", ""), "section": title, "model": ex.get("model_cot", ""),
        "w": w, "h": h, "d": ex.get("d", 0), "ei_rating": ex.get("ei", 0),
        "spec_priority": ex.get("spec_priority", "name"),
    }
    spec = Agent01_BOQExtractor.resolve_item_spec(item, get_subtype_rules(), price_map={}, idx=1)
    return spec, item


class DamperRuleTableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = dmc.load_rules()["_all"]
        cls.diff_rx = get_subtype_rules().get("COMBO_AND_DETECTION_RULES", {}).get("combo_diffuser_regex", r'\bcửa\s*gió\b')

    def test_table_structure(self):
        ids = [r["id"] for r in self.data["quy_tac"]]
        self.assertEqual(len(ids), len(set(ids)), "id rule bị trùng")
        self.assertEqual(ids, sorted(ids), "rule phải xếp theo thứ tự chạy VG-01 → VG-xx")
        for r in self.data["quy_tac"]:
            for key in ("ten", "nguon", "ly_do"):
                self.assertTrue(r.get(key), f"{r['id']}: thiếu '{key}'")
            self.assertTrue(r.get("vi_du_dung") or r.get("vi_du_combo"), f"{r['id']}: chưa có ví dụ")

    def _check(self, rid, ex):
        spec, item = _run_example(ex)
        label = f"{rid}: '{ex['ten']}' / Ghi chú '{ex.get('ghi_chu', '')}' / Model '{ex.get('model_cot', '')}'"
        self.assertEqual(spec["subtype"], ex["loai"], f"{label} → loại van")
        self.assertEqual(spec["model_fslf"], ex["model"], f"{label} → Model")
        if ex.get("ghi_chu_khong_chua"):
            self.assertNotIn(ex["ghi_chu_khong_chua"], spec["note_fslf"], f"{label} → ghi chú")
        if ex.get("ghi_chu_chua"):
            self.assertIn(ex["ghi_chu_chua"], spec["note_fslf"], f"{label} → ghi chú")
        if "fd_thuong" in ex:
            self.assertEqual(item.get("fd_non_ei_keyword"), ex["fd_thuong"], f"{label} → cờ hỏi lại FD thường")

    def test_examples(self):
        n = 0
        for r in self.data["quy_tac"]:
            for ex in r.get("vi_du_dung", []) + r.get("vi_du_sai", []):
                with self.subTest(rule=r["id"], ten=ex["ten"]):
                    self._check(r["id"], ex)
                n += 1
        self.assertGreaterEqual(n, 15)

    def test_combo_examples(self):
        for r in self.data["quy_tac"]:
            for ex in r.get("vi_du_combo", []):
                with self.subTest(rule=r["id"], ten=ex["ten"]):
                    got = dmc.detect_dampers(ex["ten"], ex.get("model_cot", ""), None, self.diff_rx)
                    self.assertEqual(got, ex["van"])

    def test_priority_order(self):
        self.assertEqual(dmc.sort_by_priority(["VCD", "NRD", "FD", "MFD"]), ["MFD", "FD", "NRD", "VCD"])

    def test_torque(self):
        self.assertEqual(dmc.actuator_torque("BELIMO", 999, 999)[0], "5Nm")
        self.assertEqual(dmc.actuator_torque("BELIMO", 1000, 400)[0], "10Nm")
        self.assertEqual(dmc.actuator_torque("BELIMO", 1500, 1300)[0], "20Nm")
        self.assertEqual(dmc.actuator_torque("HONEYWELL", 1000, 800), ("5Nm", "CN4605A"))


class DamperParserRowsTest(unittest.TestCase):
    """Dòng BOQ thật User chốt 2026-11-03 (việc C1): parser tách / nhận đúng loại hàng."""

    def test_rows(self):
        from swind_boq_parser import SwindBOQParser
        rows = [("Van FD và NRD KT: 300x200", "VAN_GIO", "SWIND-2.01- E-FD-EI120 + NRD"),   # Minh Triết R240
                ("Miệng gio kèm OBD 400x300", "CUA_GIO", "SDG+O"),                      # BOQ_ANH_KHACH_01 R13
                ("AG_AAG-OBD-400x400-OB", "CUA_GIO", "SDG+O")]                          # BOQ_ANH_KHACH_01 R37
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
        got = [(it["raw_name"], it["category"], it["resolved_spec"]["model_fslf"]) for it in items]
        self.assertEqual(got, rows)


if __name__ == "__main__":
    unittest.main()
