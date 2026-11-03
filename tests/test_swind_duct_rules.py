"""
Test bảng rule nhận diện ỐNG GIÓ & PHỤ KIỆN (data/master_data/duct_rules.json → src/duct_classifier.py).

Mỗi rule phải có nguồn gốc và ≥ 1 ví dụ; mọi `vi_du_dung` / `vi_du_sai` chạy qua Agent01.resolve_item_spec
(đúng đường báo giá) và so loại phụ kiện / chữ trong Model. OG-21 (hộp trong Ghi chú) kiểm số hộp + cờ hỏi lại User.
Chạy: ./venv/bin/python -m unittest discover -s tests -p "test_swind_*.py"
"""
import os
import sys
import tempfile
import unittest

import openpyxl

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, SRC)

import duct_classifier as dcl  # noqa: E402
from agent_01_boq_extractor import Agent01_BOQExtractor  # noqa: E402
from swind_utils import get_subtype_rules  # noqa: E402


def _resolve(ex):
    w, h = ex.get("kt", [0, 0])
    item = {
        "category": ex.get("nhom", "ONG_GIO"), "raw_name": ex["ten"], "name": ex["ten"], "note_boq": ex.get("ghi_chu", ""),
        "unit": ex.get("dvt", "cái"), "w": w, "h": h, "d": ex.get("d", 0), "w2": ex.get("w2", 0), "h2": ex.get("h2", 0), "qty": 1,
    }
    return Agent01_BOQExtractor.resolve_item_spec(item, get_subtype_rules(), price_map={}, idx=1), item


class DuctRuleTableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.R = dcl.load_rules()

    def test_table_structure(self):
        order = self.R["thu_tu_nhan_dien"]
        ids = [r["id"] for r in order] + [r["id"] for r in self.R["quy_tac_bo_sung"]]
        self.assertEqual(len(ids), len(set(ids)), "id rule bị trùng")
        self.assertTrue(order[-1].get("mac_dinh"), "rule cuối phải là rule mặc định")
        geoms = set(self.R["cu_phap"]["hinh_hoc"])
        for r in order + self.R["quy_tac_bo_sung"]:
            self.assertTrue(r.get("nguon"), f"{r['id']}: thiếu 'nguon'")
            self.assertTrue(r.get("vi_du_dung"), f"{r['id']}: chưa có ví dụ")
            for k in ("hoac_hinh_hoc", "va_hinh_hoc"):
                if k in r:
                    self.assertIn(r[k], geoms, f"{r['id']}: điều kiện hình học lạ")

    def test_examples(self):
        for r in self.R["thu_tu_nhan_dien"] + self.R["quy_tac_bo_sung"]:
            for ex in r.get("vi_du_dung", []) + r.get("vi_du_sai", []):
                if "loai" not in ex:
                    continue
                with self.subTest(rule=r["id"], ten=ex["ten"]):
                    spec, _ = _resolve(ex)
                    self.assertEqual(spec["subtype"] if spec["subtype"] not in ("INSUL", "NON_INSUL") else "FLEX_DUCT", ex["loai"])
                    if ex.get("model_chua"):
                        self.assertIn(ex["model_chua"], spec["model_fslf"])

    def test_note_boxes_and_conflict(self):
        for ex in self.R["_extra"]["OG-21"]["vi_du_dung"]:
            with self.subTest(ten=ex["ten"], ghi_chu=ex["ghi_chu"]):
                self.assertEqual(len(dcl.parse_note_boxes(ex["ghi_chu"])), ex["so_hop"])
                self.assertEqual(bool(dcl.note_box_conflict(ex["ten"], ex["ghi_chu"])), ex["hoi_lai"])
                _, item = _resolve(ex)
                self.assertEqual(bool(item.get("box_note_conflict")), ex["hoi_lai"])

    def test_gate_asks_user_on_box_conflict(self):
        from swind_master_runner import evaluate_quotation_gate
        item = {"source_row": 7, "raw_name": "Hộp gió 700x300 L400", "qty": 2,
                "box_note_conflict": dcl.note_box_conflict("Hộp gió 700x300 L400", "BOX 600x300x300")}
        gate = evaluate_quotation_gate({}, {}, {}, [], all_items=[item])
        self.assertTrue(any("[HỎI LẠI USER]" in c and "OG-21" in c and "R7" in c for c in gate["confirm"]), gate["confirm"])
        self.assertEqual(gate["blocking"], [])

    def test_fire_canvas(self):
        self.assertTrue(dcl.is_fire_canvas("", "khớp nối mềm chống cháy 600x400"))
        self.assertFalse(dcl.is_fire_canvas("CANVAS", "khớp nối mềm 600x400"))


class DuctParserCategoryTest(unittest.TestCase):
    """User chốt 2026-11-03 (việc C2): giá đỡ dưới Title 'Nối mềm' → thương mại; Flexible connection → canvas; chụp thông gió → canvas/ventcap."""

    def test_rows(self):
        from swind_boq_parser import SwindBOQParser
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "boq.xlsx")
            wb = openpyxl.Workbook()
            ws = wb.active
            ws.title = "BOQ"
            ws.append(["STT", "Danh mục vật tư", "ĐVT", "Khối lượng"])
            ws.append([None, "Nối mềm trước và sau quạt:"])
            ws.append([1, "Lắp đặt giá đỡ ống gió kích thước ≤400 bằng thép góc L25x25x3mm,tiren M6", "bộ", 4])  # TAHK R66
            ws.append([2, "Khớp nối mềm 600x400", "cái", 2])
            ws.append([None, "PHỤ KIỆN"])
            ws.append([3, "Flexible connection 600x400", "cái", 2])
            ws.append([4, "Chụp thông gió D110", "cái", 2])  # CAND 'DHKK A3' R272
            wb.save(p)
            parser = SwindBOQParser(p)
            items = parser.parse_sheet("BOQ")
        got = {it["raw_name"].split(" ")[0]: it["category"] for it in items}
        self.assertNotIn("Lắp", got, "giá đỡ là hàng thương mại không giá đối tác → không vào danh sách báo giá")
        self.assertIn(3, parser.skipped_rows.get("BOQ") or set())
        self.assertEqual(got.get("Khớp"), "CANVAS")
        self.assertEqual(got.get("Flexible"), "CANVAS")
        self.assertEqual(got.get("Chụp"), "CANVAS")
        vc = next(it for it in items if it["raw_name"].startswith("Chụp"))
        self.assertEqual(dcl.detect_subtype(vc["raw_name"], d1=float(vc.get("d") or 0)), "VENTCAP")


if __name__ == "__main__":
    unittest.main()
