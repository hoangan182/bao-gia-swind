"""
Bánh cóc từ khóa loại hàng (Việc 4, 2026-11-25; siết ở Task C cùng ngày): từ khóa nhận diện loại hàng chỉ ghi trong JSON rule,
không mọc lại trong code.

Cách đếm: mỗi file src/*.py ngoài EXEMPT, đếm số lần mỗi từ trong KEYWORDS xuất hiện BÊN TRONG token chuỗi Python
(tokenize.STRING + FSTRING_MIDDLE của f-string, Python 3.12+). Bỏ docstring (chuỗi là câu lệnh đầu của module / class / hàm) và chú thích.
- PHÂN BIỆT HOA/THƯỜNG (không lower): code nhận diện luôn so trên chuỗi đã .lower(); chữ HOA trong code là nhãn hiển thị / mã Model / mat_id
  ("CỬA GIÓ", "SDG+O", "MAT-ACTUATOR-...-MPRD") — hạ chữ thường làm tổng 196 → 399+ gần như toàn chữ hiển thị.
- RANH GIỚI TỪ: regex (?<!\\w)từ(?!\\w) — `has_obd` / `is_louver` (tên biến, khóa dict) KHÔNG đếm; "obd" / "có obd" đếm.
Số đếm từng file chỉ được GIẢM so với tests/fixtures/keyword_guard_baseline.json. File mới không có trong baseline = 0.
--init chỉ để TẠO baseline lần đầu / sau khi đổi cách đếm (không kiểm tra tăng) — KHÔNG dùng để hấp thụ từ khóa mới.
Giảm xong chạy: ./venv/bin/python tests/test_swind_keyword_guard.py --update (từ chối nếu có số đếm tăng).

Số đếm còn lại hợp lệ (baseline Task C, tổng 237 theo từ vựng mới; 157 theo từ vựng + cách đếm cũ) — HIỂN THỊ = ghi chú BOM / BG,
nhãn, console, help CLI; KHÓA = khóa dict / tên cờ / khóa hằng số giá; NHẬN DIỆN còn lại = đã khảo sát, chủ ý giữ:
- swind_master_runner.py 60: ~45 HIỂN THỊ (thông báo console `--duct-only` / ống gió / canvas / MPRD, help argparse, tên linh kiện hộp) +
  KHÓA (tên cờ `--include-canvas`) + tên bộ lọc cảnh báo kết quả
- agent_04_bom_duct.py 34: ~20 ghi chú / trace BOM, 9 khóa `ong.canvas.*` / "lcct", tên giả "Hộp tiêu âm"; canvas chống cháy giữ
  (2 danh sách khác nhau, chờ User chốt)
- agent_06_bom_diffuser.py 26: tên linh kiện BOM (sọt trứng, khuếch tán, tháo lắp, bầu dục, phin lọc bụi G4, ke góc cửa gió)
- agent_05_bom_damper.py 24: khóa bảng giá van `nrd` / `vcd` (subtype dict) + tên linh kiện BOM
- swind_boq_parser.py 19: regex bảng phụ (side table, Reader — NO-GO, cần E2E toàn bộ) + tên mã cửa / van dò cột Model
  + CÒN LẠI LÀ LOGIC NHẬN DIỆN (khảo sát 2026-11-25 xếp "tùy chọn GO, rủi ro vừa", cố ý chưa chuyển vì danh sách khác
  `dong_ghi_khuech_tan`): `is_makeup_air_z` (loại trừ), `is_ktc_diffuser`, tiền tố van / cửa, danh sách tên phụ kiện
  (côn / chân rẽ / hộp gió). KHÔNG coi là chữ hiển thị — dọn tiếp ở đợt sau, xem docs/superpowers/plans/2026-11-25-5-khao-sat-tu-khoa.md
- agent_00b_input_normalizer.py 19: cảnh báo cấu trúc BOQ (đếm dòng giống ống / cửa) — không quyết định báo giá
- swind_pricing.py 16: 5 tên động cơ + khóa hằng số giá `obd.*` / "lcct" + thông báo lỗi
- agent_01b_image_boq_reader.py 9, swind_universal_extractor.py 5: luồng phụ (sửa lỗi OCR, nhãn phụ kiện)
- agent_03_input_auditor.py 6: cảnh báo PCCC (`chặn lửa`, MFD) — chỉ cảnh báo
- agent_10_old_quote_carrier.py 6: nhãn nhóm FAMILY_LABEL; swind_utils.py 6: regex mã Model dò cột (Reader core)
- agent_01_boq_extractor.py 3, scope_filter.py 3 (lý do hiển thị `duct_swind_ask_reason`), swind_excel_builder.py 1 (regex dòng con BG)
EXEMPT còn lại: classifier / bảng rule (diffuser, damper, duct, typo, title_row, rule_dsl), default_policy + decision_trace (nhãn hiển thị),
công cụ kiểm (inspector, e2e, pattern_lab), data miner. category_classifier.py và scope_filter.py ĐÃ BỎ khỏi EXEMPT (Task C).
"""
import ast
import io
import json
import os
import re
import sys
import tokenize
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
BASELINE = os.path.join(ROOT, "tests", "fixtures", "keyword_guard_baseline.json")

# Từ vựng loại hàng (chữ thường, phân biệt hoa/thường — code nhận diện luôn so trên chuỗi đã .lower()).
KEYWORDS = [
    # cửa gió / louver (từ vựng gốc Việc 4)
    "khuếch tán", "louver", "lưới chắn", "cửa gió", "miệng gió", "ống gió", "tháo lắp", "nan z", "bầu dục", "sọt trứng",
    "chặn lửa", "xả áp", "tiêu âm", "canvas", "ventcap", "lcct", "obd",
    # cửa gió: kiểu nan / tên tiếng Anh / viết sai thường gặp (Task C, 2026-11-25)
    "nan thẳng", "cửa chớp", "eggcrate", "diffuser", "grille", "damper", "insect screen", "luover", "louvre",
    # van gió: tên + mã van (không thêm mã 2-3 chữ trần như fd / md / prd — nhiễu)
    "van gió", "van chặn", "ngăn cháy", "mfd", "msfd", "mfsd", "mprd", "vcd", "nrd",
    # phụ kiện ống gió (không thêm 'côn' / 'tê' / 'co' trần — nhiễu)
    "cút", "chân rẽ", "chạc", "bịt đầu", "hộp gió", "côn thu",
    # lọc
    "lọc g4", "lọc bụi", "lọc thô", "phin lọc",
    # khớp nối mềm / chụp thông hơi
    "khớp nối", "nối mềm", "ống mềm", "chụp thông",
]
# Ranh giới từ: 'has_obd' / 'is_louver' (tên biến, khóa dict) không đếm; "obd" / 'có obd' đếm.
_KW_RX = {k: re.compile(r"(?<!\w)" + re.escape(k) + r"(?!\w)") for k in KEYWORDS}
# Không đếm: classifier / bảng rule / công cụ kiểm / nhãn hiển thị. category_classifier.py + scope_filter.py ĐÃ BỎ khỏi
# danh sách (Task C) — hai file này phải đếm được và chỉ còn tên khóa JSON / thông báo.
EXEMPT = {"diffuser_classifier.py", "damper_classifier.py", "duct_classifier.py", "typo_normalizer.py",
          "title_row_resolver.py", "rule_dsl.py", "swind_item_inspector.py", "swind_e2e_regression.py",
          "swind_pattern_lab.py", "agent_00_data_miner.py", "extract_master_data.py", "default_policy.py",
          "decision_trace.py"}


def _docstring_positions(tree):
    pos = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = node.body
            if body and isinstance(body[0], ast.Expr) and isinstance(getattr(body[0], "value", None), ast.Constant) \
                    and isinstance(body[0].value.value, str):
                pos.add((body[0].value.lineno, body[0].value.col_offset))
    return pos


def count_file(path):
    with open(path, "r", encoding="utf-8") as f:
        text = f.read()
    doc = _docstring_positions(ast.parse(text))
    counts = {k: 0 for k in KEYWORDS}
    kinds = {tokenize.STRING, getattr(tokenize, "FSTRING_MIDDLE", tokenize.STRING)}
    for tok in tokenize.generate_tokens(io.StringIO(text).readline):
        if tok.type not in kinds or tok.start in doc:
            continue
        for k in KEYWORDS:
            counts[k] += len(_KW_RX[k].findall(tok.string))
    return {k: v for k, v in counts.items() if v}


def count_all():
    out = {}
    for fn in sorted(os.listdir(SRC)):
        if fn.endswith(".py") and fn not in EXEMPT:
            c = count_file(os.path.join(SRC, fn))
            if c:
                out[fn] = c
    return out


def load_baseline():
    with open(BASELINE, "r", encoding="utf-8") as f:
        return json.load(f)


def _diff(cur, base):
    """Trả (tăng, giảm) — mỗi phần tử (file, từ, cũ, mới)."""
    up, down = [], []
    for fn in set(cur) | set(base):
        for k in set(cur.get(fn, {})) | set(base.get(fn, {})):
            a, b = base.get(fn, {}).get(k, 0), cur.get(fn, {}).get(k, 0)
            if b > a:
                up.append((fn, k, a, b))
            elif b < a:
                down.append((fn, k, a, b))
    return sorted(up), sorted(down)


class KeywordGuardTest(unittest.TestCase):
    def test_counts_not_increase(self):
        up, _ = _diff(count_all(), load_baseline())
        msg = "\n".join(f"{f}: '{k}' tăng {a} → {b}. Chuyển vào category_rules.json / scope_rules.json" for f, k, a, b in up)
        self.assertEqual(up, [], msg)

    def test_new_file_counted(self):
        base = load_baseline()
        self.assertNotIn("__file_moi__.py", base)
        up, _ = _diff({"__file_moi__.py": {"louver": 1}}, base)
        self.assertEqual(up, [("__file_moi__.py", "louver", 0, 1)])

    def test_fstring_counted(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "x.py")
            with open(p, "w", encoding="utf-8") as f:
                f.write('y = f"có louver {x} và lcct"\n')
            self.assertEqual(count_file(p), {"louver": 1, "lcct": 1})

    def test_word_boundary_not_identifier(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "x.py")
            with open(p, "w", encoding="utf-8") as f:
                f.write('d = {"has_obd": 1, "is_louver": 2}\ny = "có obd" + "obd" + "vcd/nrd" + "MAT-VCD"\n')
            self.assertEqual(count_file(p), {"obd": 2, "vcd": 1, "nrd": 1})

    def test_case_sensitive(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "x.py")
            with open(p, "w", encoding="utf-8") as f:
                f.write('a = "Louver LCCT CỬA GIÓ"\nb = "louver lcct"\n')
            self.assertEqual(count_file(p), {"louver": 1, "lcct": 1})  # chữ hoa = nhãn hiển thị, không đếm

    def test_docstring_and_comment_excluded(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "x.py")
            with open(p, "w", encoding="utf-8") as f:
                f.write('def f():\n    """louver"""\n    # lcct\n    return 1\n')
            self.assertEqual(count_file(p), {})

    def test_exempt_list(self):
        for fn in ("category_classifier.py", "scope_filter.py"):
            self.assertNotIn(fn, EXEMPT)
        for fn in ("default_policy.py", "decision_trace.py", "diffuser_classifier.py"):
            self.assertIn(fn, EXEMPT)

    def test_baseline_tight(self):
        _, down = _diff(count_all(), load_baseline())
        msg = "\n".join(f"{f}: '{k}' giảm {a} → {b}" for f, k, a, b in down)
        self.assertEqual(down, [], msg + "\nChạy: ./venv/bin/python tests/test_swind_keyword_guard.py --update")


def init_baseline():
    with open(BASELINE, "w", encoding="utf-8") as f:
        json.dump(count_all(), f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print("Đã tạo", BASELINE)
    return 0


def update_baseline():
    cur = count_all()
    up, _ = _diff(cur, load_baseline() if os.path.exists(BASELINE) else {})
    if up:
        for f, k, a, b in up:
            print(f"TỪ CHỐI: {f}: '{k}' tăng {a} → {b}")
        return 1
    with open(BASELINE, "w", encoding="utf-8") as f:
        json.dump(cur, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write("\n")
    print("Đã ghi", BASELINE)
    return 0


if __name__ == "__main__":
    if "--init" in sys.argv:
        sys.exit(init_baseline())
    if "--update" in sys.argv:
        sys.exit(update_baseline())
    unittest.main()
