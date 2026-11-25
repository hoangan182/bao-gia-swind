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
        "motor_brand_override": ex.get("hang_dong_co", ""),  # = cờ --motor-brand
    }
    if dmc.is_linear_motor_text(item):  # runner đặt cờ này theo từng dòng (Kỹ thuật chốt 2026-11-17)
        item["motor_linear"] = True
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
        rows = [("Van FD và NRD KT: 300x200", "VAN_GIO", "FD + NRD"),   # Minh Triết R240 (FD không ghi EI → FD thường, User chốt 2026-11-13)
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



def _classify_res(ex):
    """Chạy ví dụ qua Agent01.resolve_item_spec, trả dict kết quả đầy đủ của damper_classifier.classify."""
    got = {}
    orig = dmc.classify

    def _spy(*a, **k):
        res = orig(*a, **k)
        got.setdefault("res", res)
        return res

    dmc.classify = _spy
    try:
        _run_example(ex)
    finally:
        dmc.classify = orig
    return got["res"]


class DamperProvenanceTest(unittest.TestCase):
    """Bảng 'đã hiểu thế nào' (2026-11-24): classify trả thêm nguồn chữ, trail ghi VG-02-MAC-DINH khi dùng mặc định."""

    def test_vg02_default(self):
        res = _classify_res({"ten": "Van 600x400", "kt": [600, 400]})
        self.assertIn("VG-02-MAC-DINH", res["trail"])
        self.assertEqual(res["damper_type"], "VCD")
        self.assertEqual(res["nguon"], ["MAC_DINH"])

    def test_vg01_model(self):
        res = _classify_res({"ten": "Van 600x400", "kt": [600, 400], "model_cot": "MFD"})
        self.assertIn("VG-01", res["trail"])
        self.assertEqual(res["nguon"], ["MODEL"])

    def test_vg02_ten(self):
        res = _classify_res({"ten": "Van chặn lửa FD 600x400", "kt": [600, 400]})
        self.assertNotIn("VG-02-MAC-DINH", res["trail"])
        self.assertIn("TEN", res["nguon"])



def _old_damper_conflict(sub_s, nb_l, note_prio):
    """Bản chép NGUYÊN VĂN biểu thức cũ trong swind_master_runner (trước Task B), category VAN_GIO."""
    if not note_prio and nb_l and sub_s in ("NRD", "PRD", "MPRD", "VCD"):
        if any(k in nb_l for k in ("mfd", "smd", "van ngăn cháy", "van chặn lửa", "bọc chống cháy", "bọc tấm mgo", "tấm chống cháy mgo")):
            return True
    elif nb_l and sub_s in ("MFD", "MSFD", "MFSD") and "van fd" in nb_l and not any(k in nb_l for k in ("mfd", "động cơ", "on/off", "on-off")):
        return True
    return False


class DamperNameNoteConflictTest(unittest.TestCase):
    """Task B bước 3 (2026-11-25): bộ dò xung đột Tên – Ghi chú van gió → damper_rules.json `xung_dot_ten_ghi_chu`."""

    SUB = ["NRD", "PRD", "MPRD", "VCD", "MFD", "MSFD", "MFSD", "MD", "FD", ""]
    GHI_CHU = ["", "van chặn lửa", "mfd", "smd", "van ngăn cháy", "bọc chống cháy", "bọc tấm mgo", "tấm chống cháy mgo",
               "van ei60", "van fd", "van fd ei60", "van fd kèm động cơ", "van fd on/off", "van fd on-off", "van fd mfd",
               "tấm mgo", "van fd bọc chống cháy"]

    def test_rule_table(self):
        cfg = dmc.load_rules()["_all"]["xung_dot_ten_ghi_chu"]
        for key in ("mo_ta", "nguon", "ly_do", "quy_tac"):
            self.assertTrue(cfg.get(key), key)
        for r in cfg["quy_tac"]:
            self.assertTrue(r.get("id") and r.get("loai_van") and r.get("ghi_chu_co"), r)
            self.assertTrue(r.get("nguon") and r.get("ly_do"), r["id"])
            for ex in r["vi_du_dung"]:
                self.assertEqual(dmc.name_note_conflict(ex["loai"], ex["ghi_chu"]), r["id"], ex)

    def test_equals_old_expression_full_grid(self):
        for sub in self.SUB:
            for nb in self.GHI_CHU:
                for prio in (False, True):
                    with self.subTest(sub=sub, ghi_chu=nb, prio=prio):
                        self.assertEqual(bool(dmc.name_note_conflict(sub, nb, prio)), _old_damper_conflict(sub, nb, prio))




class DamperTraceDefaultTest(unittest.TestCase):
    """Bảng 'đã hiểu thế nào' (vá cuối 2026-11-24): cờ mặc định / rule loại van."""

    def test_note_mode_default_path(self):
        _, item = _run_example({"ten": "Van 600x400", "ghi_chu": "lắp đặt theo bản vẽ", "kt": [600, 400],
                                "spec_priority": "note"})
        self.assertEqual(item["spec_priority"], "note")
        R = dmc.load_rules()
        _, _, trail = dmc.classify_type(item, get_subtype_rules(), "van 600x400", "van 600x400", R)
        self.assertIn("VG-02-MAC-DINH", trail)

    def test_upgrade_not_default_unit(self):
        # VG-03/04/05 nâng cấp mặc định VCD -> _type_sources không trả MAC_DINH
        R = dmc.load_rules()
        src = dmc._type_sources(R, {}, get_subtype_rules(), "", "", ["VG-02", "VG-02-MAC-DINH", "VG-04"])
        self.assertNotEqual(src, ["MAC_DINH"])

    def test_motor_row_rule_is_type_rule(self):
        spec, item = _run_example({"ten": "Van dập lửa motor 600x400", "kt": [600, 400]})
        k = next(d for d in item["decisions"] if d["truong"] == "kieu") if item.get("decisions") else None
        if k:
            self.assertIn(k["rule"], ("VG-01", "VG-02A", "VG-02", "VG-03", "VG-04", "VG-05"))
            self.assertTrue(k["chac"])


if __name__ == "__main__":
    unittest.main()
