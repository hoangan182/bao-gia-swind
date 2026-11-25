"""
Test bảng rule quyết định LOẠI HÀNG (data/master_data/category_rules.json → src/category_classifier.py).

Việc 4 Task 3 (2026-11-25): chuỗi if/elif ~170 dòng trong SwindBOQParser.parse_sheet thành bảng rule có thứ tự.
Mỗi rule phải có nguồn gốc, lý do và ≥ 1 ví dụ đúng; mọi `vi_du_dung` / `vi_du_sai` chạy qua classify().
Bản ghi chuẩn (golden, Task 2) output/_pattern_lab/category_golden.jsonl: mọi dòng phải ra đúng loại hàng VÀ
đúng (nguồn, chắc) như chuỗi parser cũ (bỏ qua nếu file chưa có — file không commit).
GOLDEN = BẰNG CHỨNG CHUYỂN ĐỔI MỘT LẦN (Việc 4, 2026-11-25), ghi từ chuỗi if/elif cũ (mã ghi đã xóa, không dựng lại được).
Khi CHỦ ĐÍCH sửa category_rules.json hoặc catalog làm golden lệch: kiểm các dòng lệch đúng là dòng định đổi,
rồi XÓA output/_pattern_lab/category_golden.jsonl. Lưới an toàn lâu dài = vi_du_dung / vi_du_sai trong
category_rules.json + `swind_pattern_lab.py --check`.
Chạy: ./venv/bin/python -m unittest discover -s tests -p "test_swind_*.py"
"""
import json
import os
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

import category_classifier as cc  # noqa: E402

GOLDEN = os.path.join(ROOT, "output", "_pattern_lab", "category_golden.jsonl")
NGUON_CHU = {"TEN", "TITLE", "GHI_CHU", "HOC_MAY", "TEN_HOAC_TITLE"}

# Ánh xạ id cũ của chuỗi parser (Việc 2) → (nguồn, chắc) — controller ruling 1
OLD_NGUON = {"PARSER-HOC-MAY": ["HOC_MAY"], "PARSER-TITLE": ["TITLE"], "PARSER-5-TITLE": ["TITLE"],
             "PARSER-TEN": ["TEN"], "PARSER-5-TEN": ["TEN"]}


def _load_catalogs():
    base = os.path.join(ROOT, "data", "master_data")
    with open(os.path.join(base, "commercial_catalog.json"), encoding="utf-8") as f:
        comm = json.load(f)
    with open(os.path.join(base, "manufacturable_catalog.json"), encoding="utf-8") as f:
        mfg = json.load(f)
    return {"manufacturable": mfg, "commercial": comm}


def _example_input(ex):
    """Ví dụ trong bảng rule → (texts, flags, learned). Khoá: ten, title, ghi_chu, model, co (cờ), hoc_may."""
    ten = ex.get("ten", "")
    title = ex.get("title", "")
    name_str = ex.get("name_str", ten)
    full_name_str = f"{title} {name_str}".strip() if title and title.lower() not in name_str.lower() else name_str
    texts = {
        "name_lower": name_str.lower(), "full_name_lower": full_name_str.lower(), "sec_lower": title.lower(),
        "note_boq": ex.get("ghi_chu", ""), "model_str": ex.get("model", ""), "raw_name_str": ten,
        "name_str": name_str, "full_name_str": full_name_str,
    }
    flags = {"is_plumbing_item": False, "is_hvac_prd": False, "name_has_title": name_str != ten}
    flags.update(ex.get("co", {}))
    return texts, flags, dict(ex.get("hoc_may", {}))


class CategoryRuleTableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = cc.load_rules()
        cls.catalogs = _load_catalogs()

    def _classify(self, ex):
        texts, flags, learned = _example_input(ex)
        return cc.classify(texts, flags, self.catalogs, learned, self.rules)

    def test_every_rule_has_source_and_examples(self):
        rules = self.rules["quy_tac"]
        ids = [r["id"] for r in rules] + [self.rules["khong_khop"]["id"]]
        self.assertEqual(len(ids), len(set(ids)), "id rule bị trùng")
        for r in rules + [self.rules["khong_khop"]]:
            for key in ("ten", "nguon", "ly_do"):
                self.assertTrue(r.get(key), f"{r['id']}: thiếu '{key}'")
            self.assertIn(r.get("nguon_chu"), NGUON_CHU, f"{r['id']}: nguon_chu không hợp lệ")
            self.assertIsInstance(r.get("chac", True), bool, f"{r['id']}: chac phải là bool")
            self.assertTrue(r.get("vi_du_dung"), f"{r['id']}: chưa có ví dụ đúng (vi_du_dung)")

    def test_rule_examples(self):
        for r in self.rules["quy_tac"] + [self.rules["khong_khop"]]:
            for ex in r.get("vi_du_dung", []):
                with self.subTest(rule=r["id"], ex=ex.get("ten")):
                    res = self._classify(ex)
                    self.assertEqual(res["rule_id"], ex.get("rule", r["id"]), f"{r['id']} vi_du_dung {ex!r}: sai rule")
                    self.assertEqual(res["category"], ex["loai"], f"{r['id']} vi_du_dung {ex!r}: sai loại")
            for ex in r.get("vi_du_sai", []):
                with self.subTest(rule=r["id"], ex=ex.get("ten")):
                    res = self._classify(ex)
                    self.assertNotEqual(res["rule_id"], r["id"], f"{r['id']} vi_du_sai {ex!r}: rule không được khớp")
                    if "loai" in ex:
                        self.assertEqual(res["category"], ex["loai"], f"{r['id']} vi_du_sai {ex!r}: sai loại")

    def test_learned_wins(self):
        texts, flags, _ = _example_input({"ten": "Cửa gió 600x300"})
        res = cc.classify(texts, flags, self.catalogs, {"cửa gió 600x300": "VAN_GIO"}, self.rules)
        self.assertEqual((res["category"], res["rule_id"], res["nguon"], res["chac"]),
                         ("VAN_GIO", "LH-01", ["HOC_MAY"], True))

    def test_match_keyword_boundary(self):
        res = self._classify({"ten": "Van chống cháy 600x400"})
        self.assertNotEqual(res["category"], "ONG_GIO")

    def test_name_has_title_reports_title(self):
        # Dòng chỉ kích thước đã ghép Title vào tên: rule theo chữ 'tên' thực chất khớp chữ Title → nguồn TITLE
        res = self._classify({"ten": "600x300", "name_str": "Miệng gió cấp 600x300", "title": "Miệng gió cấp"})
        self.assertEqual((res["category"], res["nguon"]), ("CUA_GIO", ["TITLE"]))

    def test_no_match_is_khac_not_sure(self):
        res = self._classify({"ten": "Hạng mục xyz"})
        self.assertEqual((res["category"], res["rule_id"], res["chac"]), ("KHAC", "LH-KHAC", False))

    def test_learned_khac_skips_steps_1_4_but_not_step_5(self):
        # if/elif cũ: Học máy trả KHAC bỏ qua ống nước + bước 2-4 (cùng khối) nhưng bước 5 vẫn chạy
        texts, flags, _ = _example_input({"ten": "Miệng gió 600x300"})
        res = cc.classify(texts, flags, self.catalogs, {"miệng gió 600x300": "KHAC"}, self.rules)
        self.assertEqual((res["category"], res["rule_id"], res["nguon"], res["chac"]), ("KHAC", "LH-01", ["HOC_MAY"], False))
        texts, flags, _ = _example_input({"ten": "Đoạn 600x300", "title": "Ống gió"})
        res = cc.classify(texts, flags, self.catalogs, {"ống gió đoạn 600x300": "KHAC"}, self.rules)
        self.assertEqual((res["category"], res["rule_id"]), ("ONG_GIO", "LH-26"))

    def test_md04_points_to_title_fallback_rule(self):
        import default_policy
        md04 = default_policy.load_rules()["MD-04"]
        r = {x["id"]: x for x in self.rules["quy_tac"]}[md04["ap_cho"]]
        self.assertEqual((r["nguon_chu"], r["chac"], r["khoi"]), ("TITLE", False, "BUOC_5"))

    def test_condition_flags_are_defined(self):
        """Mọi cờ ('x' / '!x') trong điều kiện phải là cờ classify() thật sự định nghĩa (rule_dsl coi '!cờ lạ' là True → gõ sai lặng lẽ)."""
        import re
        with open(os.path.join(SRC, "category_classifier.py"), encoding="utf-8") as f:
            src = f.read()
        block = src[src.index("ctx.flags = {"):src.index("category, rule, done")]
        defined = set(re.findall(r'"(\w+)":', block)) | set(self.rules.get("co", {}))
        self.assertTrue({"is_plumbing_item", "title_khac_ten"} <= defined, defined)
        used = set()

        def walk(node):
            if isinstance(node, str):
                return
            if isinstance(node, list):
                for x in node:
                    walk(x)
            elif isinstance(node, dict):
                for k, v in node.items():
                    if k in ("tat_ca", "mot_trong"):
                        for c in v:
                            if isinstance(c, str):
                                used.add(c.lstrip("!"))
                    elif k == "khong" and isinstance(v, str):
                        used.add(v.lstrip("!"))
                    walk(v)
        for r in self.rules["quy_tac"] + list(self.rules.get("chuan_hoa", [])):
            for key in ("khi", "ket_qua"):
                c = r.get(key)
                if isinstance(c, str) and key == "khi":
                    used.add(c.lstrip("!"))
                walk(c)
        used -= {"true", "false"}
        self.assertEqual(sorted(used - defined), [], "cờ dùng trong category_rules.json nhưng classify() không định nghĩa")
        self.assertTrue(used, "walk không tìm thấy cờ nào — kiểm lại test")

    def test_coarse_filter_lists_in_json(self):
        """Task A (2026-11-25): danh sách tiền tố lọc thô / regex lọc tinh của LH-05 nằm ở category_rules.json."""
        cfg = self.rules["loc_tho_dung_rieng"]
        for key in ("tien_to", "regex_loc_tinh", "nguon", "ly_do", "vi_du_dung", "vi_du_sai"):
            self.assertTrue(cfg.get(key), f"loc_tho_dung_rieng thiếu '{key}'")
        self.assertIn("pre-filter", cfg["tien_to"])
        self.assertFalse(hasattr(cc, "FILTER_PREFIXES"), "FILTER_PREFIXES còn cứng trong code")
        self.assertFalse(hasattr(cc, "FINE_FILTER_RX"), "FINE_FILTER_RX còn cứng trong code")
        for ten in cfg["vi_du_dung"]:
            self.assertTrue(cc.is_standalone_coarse_filter(ten.lower()), ten)
        for ten in cfg["vi_du_sai"]:
            self.assertFalse(cc.is_standalone_coarse_filter(ten.lower()), ten)

    def test_coarse_filter_examples_both_ways(self):
        yes = ["Lọc bụi G4 500x500", "- Cung cấp, lắp đặt lọc bụi G4 500x500", "Pre-filter 600x600",
               "Lắp đặt: phin lọc 400x400", "• Bộ lọc thô 592x592"]
        no = ["Lọc HEPA H13 600x600", "Bộ lọc túi F7", "Lọc than hoạt tính 600x600", "Bộ lọc tĩnh điện",
              "Bộ lọc F5 600x600", "Cửa gió kèm lọc bụi 600x600", "Lọc bag filter 600x600", "Lọc carbon 500x500"]
        for t in yes:
            self.assertTrue(cc.is_standalone_coarse_filter(t.lower()), t)
        for t in no:
            self.assertFalse(cc.is_standalone_coarse_filter(t.lower()), t)

    def test_golden_capture_matches(self):
        if not os.path.exists(GOLDEN):
            self.skipTest(f"chưa có bản ghi chuẩn {GOLDEN} (golden chỉ là bằng chứng chuyển đổi một lần, đã xóa sau lần sửa rule có chủ đích — xem docstring)")
        bad, n = [], 0
        with open(GOLDEN, encoding="utf-8") as f:
            for line in f:
                row = json.loads(line)
                n += 1
                t = row["texts"]
                learned = {}
                if row["learned"]["full"] is not None:
                    learned[t["full_name_lower"]] = row["learned"]["full"]
                if row["learned"]["name"] is not None:
                    learned[t["name_lower"]] = row["learned"]["name"]
                res = cc.classify(t, row["flags"], self.catalogs, learned, self.rules)
                want = (row["category"], OLD_NGUON[row["cat_rule"]],
                        row["cat_rule"] != "PARSER-5-TITLE" and row["category"] != "KHAC")
                got = (res["category"], res["nguon"], res["chac"])
                if got != want:
                    bad.append((t["name_lower"][:60], t["sec_lower"][:40], row["cat_rule"], want, got, res["rule_id"]))
        for b in bad[:20]:
            print("LỆCH:", b)
        self.assertEqual(len(bad), 0, f"{len(bad)}/{n} dòng golden lệch. Golden là bằng chứng chuyển đổi một lần (Việc 4, 2026-11-25): "
                         f"nếu vừa CHỦ ĐÍCH sửa category_rules.json / catalog, kiểm các dòng LỆCH in ở trên đúng là dòng định đổi, "
                         f"rồi xóa {GOLDEN}; lưới an toàn lâu dài = vi_du_dung/vi_du_sai + swind_pattern_lab.py --check")


if __name__ == "__main__":
    unittest.main()
