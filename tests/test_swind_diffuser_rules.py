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
        self.assertIn("600x600", item.get("size_limit_flag", ""))

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


if __name__ == "__main__":
    unittest.main()
