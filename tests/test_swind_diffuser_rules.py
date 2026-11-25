"""
Test bảng rule nhận diện CỬA GIÓ (data/master_data/diffuser_rules.json → src/diffuser_classifier.py).

Mỗi rule trong `thu_tu_uu_tien` phải có nguồn gốc, lý do và ≥ 1 ví dụ đúng; mọi `vi_du_dung` / `vi_du_sai`
được chạy qua Agent01.resolve_item_spec và so Model / B1,B2 / rule kích hoạt. Sửa / thêm rule bắt buộc thêm ví dụ.
Chạy: ./venv/bin/python -m unittest discover -s tests -p "test_swind_*.py"
"""
import os
import sys
import unittest

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, SRC)

import diffuser_classifier as dc  # noqa: E402
from agent_01_boq_extractor import Agent01_BOQExtractor  # noqa: E402
from swind_utils import get_subtype_rules  # noqa: E402


def _run_example(ex):
    """Dựng dòng BOQ từ ví dụ (Tên + Ghi chú + Title cha), trả (resolved_spec, rule_id kích hoạt)."""
    title = ex.get("title", "")
    w, h = ex.get("kt", [0, 0])
    item = {
        "category": "CUA_GIO", "raw_name": ex["ten"], "name": f"{title} {ex['ten']}".strip(),
        "note_boq": ex.get("ghi_chu", ""), "section": title, "model": ex.get("model_cot", ""),
        "w": w, "h": h, "d": ex.get("d", 0), "spec_priority": ex.get("spec_priority", "name"),
    }
    fired = {}
    orig = dc.classify

    def _spy(*a, **k):
        res = orig(*a, **k)
        fired.setdefault("rule_id", res["rule_id"])
        return res

    dc.classify = _spy
    try:
        spec = Agent01_BOQExtractor.resolve_item_spec(item, get_subtype_rules(), price_map={}, idx=1)
    finally:
        dc.classify = orig
    return spec, fired.get("rule_id")


class DiffuserRuleTableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = dc.load_rules()

    def test_table_structure(self):
        rules = self.rules["thu_tu_uu_tien"]
        ids = [r["id"] for r in rules]
        self.assertEqual(len(ids), len(set(ids)), "id rule bị trùng")
        self.assertIs(rules[-1]["dieu_kien"], True, "rule cuối phải là rule dự phòng (dieu_kien = true)")
        for r in rules:
            for key in ("ten", "nguon", "ly_do"):
                self.assertTrue(r.get(key), f"{r['id']}: thiếu '{key}'")
            self.assertTrue(r.get("vi_du_dung"), f"{r['id']}: chưa có ví dụ đúng (vi_du_dung)")
        for st in self.rules["buoc_nhan_dien"]:
            self.assertTrue(any(k in st for k in ("co", "van_ban", "tinh")), f"bước không hợp lệ: {st}")

    def _check(self, rule, ex, kind):
        spec, fired = _run_example(ex)
        label = f"{rule['id']} {kind}: {ex['ten']!r}"
        self.assertEqual(spec["model_fslf"], ex["model"], label)
        self.assertEqual(fired, ex.get("rule", rule["id"]), f"{label} — sai rule kích hoạt")
        if "b" in ex:
            self.assertEqual([spec["b1"], spec["b2"]], ex["b"], f"{label} — sai B1/B2")
        if "he_so_thao_lap" in ex:
            self.assertAlmostEqual(spec["removable_factor"], ex["he_so_thao_lap"], msg=label)
        if "ghi_chu_bg_chua" in ex:
            self.assertIn(ex["ghi_chu_bg_chua"], spec["note_fslf"], label)

    def test_examples(self):
        for rule in self.rules["thu_tu_uu_tien"]:
            for ex in rule.get("vi_du_dung", []):
                with self.subTest(rule=rule["id"], ex=ex["ten"]):
                    self._check(rule, ex, "vi_du_dung")
            for ex in rule.get("vi_du_sai", []):
                with self.subTest(rule=rule["id"], ex=ex["ten"]):
                    self.assertTrue(ex.get("loi_cu"), f"{rule['id']}: vi_du_sai phải ghi 'loi_cu'")
                    self._check(rule, ex, "vi_du_sai")

    def test_name_beats_note_blade(self):
        """Tên 'nan thẳng' vs Ghi chú 'nan Z': mặc định theo Cột Tên, --spec-priority note theo Ghi chú."""
        ex = {"ten": "Cửa gió nan thẳng 800x400", "ghi_chu": "Cửa nan Z", "kt": [800, 400]}
        self.assertEqual(_run_example(ex)[0]["model_fslf"], "SDG")
        self.assertEqual(_run_example(dict(ex, spec_priority="note"))[0]["model_fslf"], "WL")

    def test_ktc_adds_border(self):
        """KTC: cộng 50mm ra kích thước mặt; khuếch tán vuông cổ >= 150 cộng 150mm."""
        spec, _ = _run_example({"ten": "Cửa gió nan bầu dục KTC 400x200", "kt": [400, 200]})
        self.assertEqual((spec["a1"], spec["a2"], spec["b1"], spec["b2"]), (450, 250, 400, 200))
        spec, _ = _run_example({"ten": "Cửa khuếch tán KTC 300x300", "kt": [300, 300]})
        self.assertEqual((spec["a1"], spec["a2"], spec["b1"], spec["b2"]), (450, 450, 300, 300))

    def test_kt_co_note_is_neck_size(self):
        """Ghi chú 'KT cổ' = kích thước cổ → cộng viền ra mặt; 'Cửa gió nan T' = nan thẳng bầu dục SDG
        (User chốt 2026-11-13, GMS TASEOC DBTSCO-3.VGCG R48/R49 'Cửa gió nan T\\nKT cổ')."""
        spec, _ = _run_example({"ten": "Cửa gió nan thẳng 1 lớp, sơn tĩnh điện, kích thước: 1500x200",
                                "ghi_chu": "Cửa gió nan T\nKT cổ", "kt": [1500, 200]})
        self.assertEqual((spec["model_fslf"], spec["a1"], spec["a2"], spec["b1"], spec["b2"]), ("SDG", 1550, 250, 1500, 200))
        spec, _ = _run_example({"ten": "Cửa gió nan thẳng 1 lớp, sơn tĩnh điện, kích thước: 1500x200",
                                "ghi_chu": "Cửa gió nan T\nCó thể tháo lắp\nKèm lọc bụi\nKT cổ", "kt": [1500, 200]})
        self.assertEqual((spec["model_fslf"], spec["a1"], spec["b1"]), ("SDG+F", 1550, 1500))
        spec, _ = _run_example({"ten": "Cửa gió nan thẳng 1 lớp, sơn tĩnh điện kèm van OBD, kích thước: 600x600",
                                "ghi_chu": "Cửa gió nan bầu dục\nKT cổ", "kt": [600, 600]})
        self.assertEqual((spec["model_fslf"], spec["a1"], spec["b1"]), ("SDG+O", 650, 600))
        # Không ghi KT cổ → giữ nguyên là kích thước mặt
        spec, _ = _run_example({"ten": "Cửa gió nan thẳng 1 lớp 1500x200", "ghi_chu": "Cửa gió nan T", "kt": [1500, 200]})
        self.assertEqual((spec["model_fslf"], spec["a1"], spec["b1"]), ("SDG", 1500, 1450))

    def test_ktm_name_beats_ktc_in_spec(self):
        """Tên ghi KTM (kích thước mặt) thắng chữ 'KTC' ở cột Thông số — User chốt 2026-11-13, KL Swind 1."""
        note = "Cửa gió nan bầu dục; TPL: Miệng gió 1 lớp lá KTC, nhôm 1.0mm"
        spec, _ = _run_example({"ten": "KTM 595x595+OBD", "ghi_chu": note, "kt": [595, 595]})
        self.assertEqual((spec["model_fslf"], spec["a1"], spec["a2"], spec["b1"], spec["b2"]), ("SDG+O", 595, 595, 545, 545))
        # Khuếch tán + 'lá KTC' → nan thẳng SDG (User chốt 2026-11-13, KL Swind 1 R20/R21); không 'lá KTC' → khuếch tán SD
        spec, _ = _run_example({"ten": "KTM 595x595 + OBD", "ghi_chu": "Cửa gió khuếch tán; " + note, "kt": [595, 595]})
        self.assertEqual((spec["model_fslf"], spec["a1"], spec["b1"]), ("SDG+O", 595, 545))
        spec, _ = _run_example({"ten": "KTM 595x595 + OBD", "ghi_chu": "Cửa gió khuếch tán", "kt": [595, 595]})
        self.assertEqual((spec["model_fslf"], spec["a1"], spec["b1"]), ("SD+O", 595, 445))
        # 'lá KTC' là kiểu lá (nan thẳng), không phải kích thước cổ → không cộng viền dù Tên không ghi KTM
        spec, _ = _run_example({"ten": "Cửa gió 400x200", "ghi_chu": note, "kt": [400, 200]})
        self.assertEqual((spec["a1"], spec["b1"]), (400, 350))
        # Ghi KTC thật (không phải 'lá KTC') vẫn cộng viền như cũ
        spec, _ = _run_example({"ten": "Cửa gió 400x200", "ghi_chu": "Cửa gió nan bầu dục, KTC", "kt": [400, 200]})
        self.assertEqual((spec["a1"], spec["b1"]), (450, 400))

    def test_diffuser_max_size_flag(self):
        """CG-KT-01: khuếch tán SD > 600x600 → cờ hỏi lại (vẫn báo giá); SDG / SD trong giới hạn không cờ."""
        R = dc.load_rules()
        for g in R["gioi_han_kich_thuoc"]:
            for ex in g["vi_du_dung"] + g["vi_du_sai"]:
                self.assertEqual(bool(dc.size_limit_flag(ex["model"], *ex["kt"], R)), ex["canh_bao"], msg=ex)
        item = {"category": "CUA_GIO", "raw_name": "KTM 595x1195 + OBD", "name": "KTM 595x1195 + OBD",
                "note_boq": "Cửa gió khuếch tán", "section": "", "model": "", "w": 595, "h": 1195, "d": 0}
        Agent01_BOQExtractor.resolve_item_spec(item, get_subtype_rules(), price_map={}, idx=1)
        # User chốt 2026-11-18: khuếch tán chỉ 600/450/300 — 595x1195 không còn là khuếch tán → SDG, không cờ SD
        self.assertTrue(item["resolved_spec"]["model_fslf"].startswith("SDG"), item["resolved_spec"])
        self.assertFalse(item.get("size_limit_flag"))

    def test_round_louver_three_times_square(self):
        """Louver tròn D503 (User chốt 2026-11-11): phần louver = 3 x Louver vuông 503x503, LCCT giữ nguyên."""
        from agent_06_bom_diffuser import Agent06_DiffuserBOM
        spec, _ = _run_example({"ten": "Louver kèm lưới chắn côn trùng D503", "kt": [503, 503], "d": 503})
        self.assertEqual(spec["model_fslf"], "WL+N")
        self.assertAlmostEqual(spec["round_factor"], 3.0)
        self.assertIn("Cửa Louver tròn D503", spec["note_fslf"])
        self.assertNotIn("giá", spec["note_fslf"].lower())  # cách tính giá là nội bộ, không ghi chú gửi khách
        sq, _ = _run_example({"ten": "Louver kèm lưới chắn côn trùng 503x503", "kt": [503, 503]})
        self.assertAlmostEqual(sq.get("round_factor", 1.0), 1.0)

        def qty(rf, mesh):
            bom = Agent06_DiffuserBOM.calculate_diffuser_bom("T", "DIFFUSER", 503, 503, profile_type="Z", has_mesh=mesh, round_factor=rf)
            return {c["sub_key"]: c["calc_qty"] for c in bom["components"]}
        louver_only, with_mesh_x3 = qty(1.0, False), qty(3.0, True)
        for k, v in louver_only.items():
            self.assertAlmostEqual(with_mesh_x3[k], 3 * v, msg=k)  # phần louver x3
        mesh_keys = set(with_mesh_x3) - set(louver_only)
        self.assertTrue(mesh_keys)
        for k in mesh_keys:
            self.assertAlmostEqual(with_mesh_x3[k], qty(1.0, True)[k], msg=k)  # LCCT giữ nguyên



def _classify_res(ex):
    """Dựng dòng CUA_GIO (Tên riêng ở 'name' như parser, Title ở 'section'), chạy qua Agent01.resolve_item_spec,
    trả dict kết quả đầy đủ của diffuser_classifier.classify."""
    w, h = ex.get("kt", [0, 0])
    item = {
        "category": "CUA_GIO", "raw_name": ex["ten"], "name": ex["ten"],
        "note_boq": ex.get("ghi_chu", ""), "section": ex.get("title", ""), "model": ex.get("model_cot", ""),
        "w": w, "h": h, "d": ex.get("d", 0), "spec_priority": "name",
    }
    got = {}
    orig = dc.classify

    def _spy(*a, **k):
        res = orig(*a, **k)
        got.setdefault("res", res)
        return res

    dc.classify = _spy
    try:
        Agent01_BOQExtractor.resolve_item_spec(item, get_subtype_rules(), price_map={}, idx=1)
    finally:
        dc.classify = orig
    return got["res"]


class DiffuserProvenanceTest(unittest.TestCase):
    """Bảng 'đã hiểu thế nào' (2026-11-24): classify trả thêm nguồn chữ + dấu mặc định, không đổi kết quả."""

    def test_nguon_title(self):
        res = _classify_res({"ten": "600x600", "title": "Cửa gió khuếch tán", "kt": [600, 600]})
        self.assertEqual(res["rule_id"].split("_")[0], "CG-08B")
        self.assertIn("TITLE", res["nguon"])
        self.assertFalse(res["mac_dinh"])
        self.assertEqual(res["rule_quyet_dinh"], res["rule_id"])

    def test_nguon_ten(self):
        res = _classify_res({"ten": "Cửa gió nan Z 800x400", "kt": [800, 400]})
        self.assertEqual(res["rule_id"].split("_")[0], "CG-06")
        self.assertEqual(res["nguon"], ["TEN"])
        self.assertFalse(res["mac_dinh"])

    def test_default_profile(self):
        res = _classify_res({"ten": "Cửa gió 600x300", "kt": [600, 300]})
        self.assertEqual(res["rule_quyet_dinh"], "CG-09-MAC-DINH")
        self.assertTrue(res["rule_id"].startswith("CG-09_"), res["rule_id"])  # id rule giữ nguyên (ví dụ JSON / pattern lab)
        self.assertTrue(res["mac_dinh"])
        self.assertEqual(res["nguon"], ["MAC_DINH"])
        self.assertTrue(res["model"].startswith("SDG"), res["model"])



class BoxComboByNameTest(unittest.TestCase):
    """Task B bước 2 (2026-11-25): fallback is_box_combo của runner + swind_item_inspector → diffuser_rules.json
    `hop_gio_theo_ten`, hàm dc.box_combo_by_name. Giá trị = hành vi literal cũ (ghim trước khi chuyển)."""

    def test_rule_has_source_and_examples(self):
        cfg = dc.load_rules()["hop_gio_theo_ten"]
        for key in ("tu_khoa_hop", "tu_khoa_cua", "nguon", "ly_do", "vi_du_dung", "vi_du_sai"):
            self.assertTrue(cfg.get(key), key)
        for t in cfg["vi_du_dung"]:
            self.assertTrue(dc.box_combo_by_name(t), t)
        for t in cfg["vi_du_sai"]:
            self.assertFalse(dc.box_combo_by_name(t), t)

    def test_literal_behaviour(self):
        for hop in ("kèm hộp gió", "kèm hộp", "kèm box", "có hộp gió", "gắn hộp gió"):
            for cua in ("cửa gió", "miệng gió", "cửa cấp", "miệng cấp", "cửa hồi", "miệng hồi"):
                self.assertTrue(dc.box_combo_by_name(f"{cua.upper()} 600x600 {hop.upper()}"), (cua, hop))
        for t in ("Cửa gió 600x600", "Hộp gió 600x600 kèm hộp", "Van gió kèm hộp gió", "Cửa gió có hộp 600x600",
                  "Miệng gió kèm hôp", "", None):
            self.assertFalse(dc.box_combo_by_name(t), t)



def _old_diffuser_conflict(rn_l, nb_l, note_prio):
    """Bản chép NGUYÊN VĂN biểu thức cũ trong swind_master_runner.print_quotation_summary_table (trước Task B) — dùng
    làm chuẩn so cho dc.name_note_conflict."""
    if note_prio or not nb_l:
        return False
    if ("sọt trứng" in nb_l or "eggcrate" in nb_l) and not any(k in rn_l for k in ("sọt trứng", "eggcrate", "ecg")):
        return True
    elif ("nan z" in nb_l or "louver" in nb_l) and any(k in rn_l for k in ("nan thẳng", "bầu dục", "khuếch tán", "sọt trứng", "mag", "sag", "rag", "fag", "eag", "oag")):
        return True
    elif (any(k in nb_l for k in ("bầu dục", "nan thẳng"))
          and any(k in rn_l for k in ("khuếch tán", "sọt trứng", "sọt trưng", "kiểu lưới", "dạng lưới", "nan z", "louver", "slot", "kiểu khe"))
          and not any(k in rn_l for k in ("bầu dục", "nan thẳng"))):
        return True
    return False


class DiffuserNameNoteConflictTest(unittest.TestCase):
    """Task B bước 3 (2026-11-25): bộ dò xung đột Tên – Ghi chú cửa gió → diffuser_rules.json `xung_dot_ten_ghi_chu`."""

    TEN = ["cửa gió nan thẳng 600x300", "cửa gió 600x300", "cửa gió sọt trứng 600x600", "cửa ecg 600x600",
           "miệng hút gió eag+obd kích thước: 200x200", "cửa sọt trứng 600x600", "miệng gió sag 300x300",
           "cửa gió message 600x300", "cửa gió khe slot 1000x150", "cửa gió sọt trưng 600x600", "cửa gió kiểu lưới",
           "cửa gió slot nan thẳng", "cửa gió khuếch tán 4 hướng", "cửa gió dạng lưới bầu dục", "cửa louver nan z",
           "cửa eggcrate", "miệng gió mag", "miệng gió rag", "fag 600x600", "oag 300x300", "cửa gió kiểu khe", "",
           "CỬA GIÓ SỌT TRỨNG", "cua gio sot trung"]
    GHI_CHU = ["", "cửa nan sọt trứng", "eggcrate", "nan sọt trứng louver", "louver nan z", "nan z", "nan thẳng",
               "bầu dục", "nan thẳng bầu dục", "khuếch tán", "cửa nan sọt trứng kèm van obd", "louver bầu dục",
               "NAN Z", "nan thang bau duc"]

    def test_rule_table(self):
        cfg = dc.load_rules()["xung_dot_ten_ghi_chu"]
        for key in ("mo_ta", "nguon", "ly_do", "quy_tac"):
            self.assertTrue(cfg.get(key), key)
        for r in cfg["quy_tac"]:
            self.assertTrue(r.get("id") and r.get("ghi_chu_co"), r)
            self.assertTrue(r.get("nguon") and r.get("ly_do"), r["id"])
            for ex in r["vi_du_dung"]:
                self.assertEqual(dc.name_note_conflict(ex["ten"], ex["ghi_chu"]), r["id"], ex)

    def test_equals_old_expression_full_grid(self):
        for rn in self.TEN:
            for nb in self.GHI_CHU:
                for prio in (False, True):
                    with self.subTest(ten=rn, ghi_chu=nb, prio=prio):
                        self.assertEqual(bool(dc.name_note_conflict(rn, nb, prio)), _old_diffuser_conflict(rn, nb, prio))

    def test_first_matching_rule_wins(self):
        self.assertEqual(dc.name_note_conflict("cửa gió nan thẳng", "sọt trứng louver").split("_")[0], "XD-CG-01")
        self.assertEqual(dc.name_note_conflict("cửa sọt trứng", "sọt trứng louver").split("_")[0], "XD-CG-02")
        self.assertEqual(dc.name_note_conflict("cửa gió kiểu lưới", "nan thẳng").split("_")[0], "XD-CG-03")
        self.assertIsNone(dc.name_note_conflict("cửa gió", "nan z"))


if __name__ == "__main__":
    unittest.main()
