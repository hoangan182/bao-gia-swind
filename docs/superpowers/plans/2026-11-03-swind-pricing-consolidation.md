# Gom công thức tính giá về `swind_pricing.py` — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mỗi quy tắc tính giá (làm tròn, động cơ van, OBD, lưới/LCCT/G4, VAT) chỉ nằm ở một chỗ — module `src/swind_pricing.py` + Master Data JSON — và mọi lệch giá do việc gom được đo từng dòng, phân loại theo ngưỡng.

**Architecture:** Thêm module hàm thuần `src/swind_pricing.py` (chỉ phụ thuộc `swind_utils` và `damper_classifier`). Agent 04/05/06, runner và Agent 10 gọi vào thay vì tự tính. Trước khi sửa, bổ sung công cụ chụp giá từng dòng Sheet `BG` vào `swind_e2e_regression.py` để so trước/sau mỗi bước.

**Tech Stack:** Python 3 (`./venv/bin/python`), `unittest`, `openpyxl`, JSON Master Data.

**Spec:** `docs/superpowers/specs/2026-11-03-swind-pricing-consolidation-design.md`

## Global Constraints

- **Không `git commit` / `git push`** — AGENTS.md: "AI không tự commit/push — User tự đẩy git". Mỗi task kết thúc bằng *Checkpoint*: báo User, User tự commit.
- Ngưỡng **lệch lớn** (User chốt "thử ngưỡng gợi ý"): một dòng lệch đơn giá **> 2% hoặc > 50.000đ**, hoặc tổng một sheet lệch **> 0,5%**, hoặc dòng xuất hiện / biến mất / đổi Model hoặc Tên. Lệch lớn → dừng, in `⚠️`, User duyệt. Lệch nhỏ → chỉ ghi báo cáo.
- Khi hai nơi cho kết quả khác nhau: **giá trị trong Master Data JSON thắng** (`pricing_constants.json`, `damper_rules.json`).
- `swind_pricing` chỉ import `swind_utils` và `damper_classifier`; không agent nào import chéo agent khác để lấy công thức giá.
- Báo cáo lệch & snapshot: `output/_pricing_consolidation/` (không commit — chứa dữ liệu khách).
- Mọi hằng số mới trong JSON kèm nguồn: `"_nguon": "dời từ code agent_05/06 — 2026-11-03, không đổi số"`.
- Không sửa `swind_experience_db.json` / `format_learning_db.json` trong lúc E2E chạy.
- Lệnh kiểm thử chuẩn của mỗi task (gọi là **BỘ KIỂM**):
  ```bash
  ./venv/bin/python src/swind_item_inspector.py --self-test
  ./venv/bin/python -m unittest discover -s tests -p "test_swind_*.py"
  ./venv/bin/python src/swind_e2e_regression.py --line-snapshot output/_pricing_consolidation/snap_<N>_default.json
  ./venv/bin/python src/swind_e2e_regression.py --runner-args "--include-duct" --baseline data/master_data/e2e_baseline_include_duct.json --line-snapshot output/_pricing_consolidation/snap_<N>_duct.json
  ./venv/bin/python src/swind_e2e_regression.py --line-diff output/_pricing_consolidation/snap_<N-1>_default.json output/_pricing_consolidation/snap_<N>_default.json --report output/_pricing_consolidation/DIFF_<N>_default.md
  ./venv/bin/python src/swind_e2e_regression.py --line-diff output/_pricing_consolidation/snap_<N-1>_duct.json output/_pricing_consolidation/snap_<N>_duct.json --report output/_pricing_consolidation/DIFF_<N>_duct.md
  ```
  Đạt khi: self-test & unit PASS; E2E không có file `FAIL` mới so với Task 2; `--line-diff` in `0 lệch lớn` **hoặc** mọi lệch lớn đều thuộc danh sách "lệch có chủ đích" của task đó.

## Review Focus

1. **Cờ dự án về động cơ** (`--motor-price`, `--mprd-motor-price`, `--md-shaft-only`, `--motor-brand`, `--mfd-model`) phải cho đúng mã & giá như trước → test `test_actuator_ids_cover_every_selected_id` (Task 4) + chạy so cờ ở Task 4 Step 7.
2. **Kích thước biên mô-men** (cạnh modul 999/1000mm, diện tích 0.8/1.8 m²) — ngưỡng `≤` vs `<` dễ lệch khi chuyển sang JSON → `test_select_actuator_boundaries` (Task 4).
3. **Làm tròn số âm & sai số dấu phẩy động** (`-2.5`, `1.005`) — hai bản cũ cho kết quả khác nhau → `test_excel_round_matches_agent04` (Task 3).
4. **Cửa/van không có kích thước** (`w=0` / `None`) — OBD rời dùng mặc định 200mm → `test_calc_obd_defaults_missing_size` (Task 5).
5. **BG có dòng thêm/bớt giữa hai lần chạy** (khớp theo vị trí dòng sẽ trượt) → `test_line_diff_detects_name_shift` (Task 1).

---

## File Structure

| File | Trách nhiệm |
|---|---|
| `src/swind_pricing.py` *(mới)* | Hàm giá thuần: `excel_round`, `mfg_markup`, `mat_price`, `ACTUATOR_IDS`, `select_actuator`, `calc_obd`, `mesh_price`, `filter_g4_price` |
| `tests/test_swind_pricing.py` *(mới)* | Unit test module trên |
| `tests/test_swind_line_diff.py` *(mới)* | Unit test phân loại lệch dòng |
| `src/swind_e2e_regression.py` | Thêm `--line-snapshot`, `--line-diff`, `--report` |
| `src/agent_04_bom_duct.py`, `agent_05_bom_damper.py`, `agent_06_bom_diffuser.py` | Bỏ công thức lặp, gọi `swind_pricing` |
| `src/damper_classifier.py` | Ghi chú mô-men KLB theo mã đã tính giá |
| `src/swind_master_runner.py:1530-1557` | Dùng `ACTUATOR_IDS` |
| `src/agent_10_old_quote_carrier.py:580,870` | VAT từ policy |
| `data/master_data/pricing_constants.json` | Thêm mục `obd` |
| Xoá 5 file thừa; cập nhật `AGENTS.md`, `.agents/rules/03_FORMULA_INDEX.md`, role docs Agent 05/06 |

---

### Task 1: Công cụ chụp & so giá từng dòng Sheet `BG`

**Files:**
- Modify: `src/swind_e2e_regression.py` (`run_one` ~L107, `main` ~L143)
- Test: `tests/test_swind_line_diff.py`

**Interfaces:**
- Produces:
  - `read_bg_lines(xlsx_path: str) -> list[dict]` — mỗi dòng có Đơn giá > 0 trên mọi sheet báo giá (header `Danh mục sản phẩm` | `Model` như `_check_bg_rows`): `{"sheet", "row", "name", "model", "unit", "qty", "price", "amount"}`. Cột: B=Tên, C=Model, L=Đơn vị, M=Số lượng, N=Đơn giá; `amount = qty * price` (cột O là công thức, không đọc).
  - `classify_line_diff(before: dict, after: dict) -> dict` — `before/after` dạng `{file: [line, ...]}`; trả `{"major": [...], "minor": [...], "sheet_totals": [...]}`. Khớp dòng theo `(file, sheet, row)`; Tên khác nhau ở cùng khoá → major `"đổi dòng"`.
  - CLI: `--line-snapshot <path>` (ghi `{file: lines}` sau khi chạy), `--line-diff <before> <after>` (không chạy runner), `--report <md>`.

- [ ] **Step 1: Viết test thất bại**

```python
from swind_e2e_regression import classify_line_diff

def L(row, price, name="Van MD 600x400", model="MD", qty=1, sheet="BG"):
    return {"sheet": sheet, "row": row, "name": name, "model": model, "unit": "Cái", "qty": qty, "price": price, "amount": qty * price}

class LineDiff(unittest.TestCase):
    def test_small_change_is_minor(self):
        r = classify_line_diff({"a.xlsx": [L(12, 1_000_000)]}, {"a.xlsx": [L(12, 1_010_000)]})
        self.assertEqual(len(r["major"]), 0); self.assertEqual(len(r["minor"]), 1)
    def test_over_2_percent_is_major(self):
        r = classify_line_diff({"a.xlsx": [L(12, 1_000_000)]}, {"a.xlsx": [L(12, 1_030_000)]})
        self.assertEqual(len(r["major"]), 1)
    def test_over_50k_is_major_even_under_2_percent(self):
        r = classify_line_diff({"a.xlsx": [L(12, 10_000_000)]}, {"a.xlsx": [L(12, 10_060_000)]})
        self.assertEqual(len(r["major"]), 1)
    def test_model_change_is_major(self):
        r = classify_line_diff({"a.xlsx": [L(12, 100)]}, {"a.xlsx": [L(12, 100, model="MD + EI")]})
        self.assertEqual(len(r["major"]), 1)
    def test_line_diff_detects_name_shift(self):
        r = classify_line_diff({"a.xlsx": [L(12, 100, name="Cửa A")]}, {"a.xlsx": [L(12, 100, name="Cửa B")]})
        self.assertEqual(r["major"][0]["ly_do"], "đổi dòng")
    def test_missing_line_is_major(self):
        r = classify_line_diff({"a.xlsx": [L(12, 100), L(13, 100)]}, {"a.xlsx": [L(12, 100)]})
        self.assertEqual(len(r["major"]), 1)
    def test_sheet_total_over_half_percent_is_major(self):
        before = {"a.xlsx": [L(r, 1_000_000) for r in range(10, 20)]}
        after = {"a.xlsx": [L(r, 1_010_000) for r in range(10, 20)]}   # mỗi dòng +1% (nhỏ), tổng +1%
        r = classify_line_diff(before, after)
        self.assertEqual(len(r["major"]), 0); self.assertEqual(len(r["sheet_totals"]), 1)
        self.assertTrue(r["sheet_totals"][0]["major"])
```

- [ ] **Step 2:** `./venv/bin/python -m unittest tests.test_swind_line_diff -v` → FAIL `ImportError: cannot import name 'classify_line_diff'`.
- [ ] **Step 3:** Cài `classify_line_diff` với hằng số module `LINE_PCT = 0.02`, `LINE_VND = 50_000`, `SHEET_PCT = 0.005` (một dòng major nếu `abs(Δ) > LINE_VND or abs(Δ)/before > LINE_PCT`; mỗi phần tử `major/minor` có `file, sheet, row, name, model_truoc, model_sau, gia_truoc, gia_sau, ly_do`; `sheet_totals` chỉ chứa sheet có lệch, mỗi phần tử có `major: bool`). Cài `read_bg_lines` (`openpyxl`, `data_only=False`, bỏ ô Đơn giá là công thức/không phải số). Trong `run_one` lấy thêm `res["bg_lines"] = read_bg_lines(...)` khi có file đầu ra (trước khi thư mục tạm bị xoá). Thêm 3 cờ CLI; `--line-diff` in tóm tắt `N lệch lớn / M lệch nhỏ / K sheet lệch tổng > 0,5%` rồi thoát mã `1` nếu có lệch lớn; `--report` ghi Markdown gồm 3 bảng (lệch lớn, tổng sheet, lệch nhỏ).
- [ ] **Step 4:** Chạy lại test Step 2 → PASS.
- [ ] **Step 5:** Kiểm thật trên 1 file: `./venv/bin/python src/swind_e2e_regression.py --filter "<tên 1 BOQ nhỏ trong input/>" --line-snapshot output/_pricing_consolidation/_thu.json` rồi `--line-diff output/_pricing_consolidation/_thu.json output/_pricing_consolidation/_thu.json` → in `0 lệch lớn / 0 lệch nhỏ`, mã thoát 0; xoá `_thu.json`.
- [ ] **Step 6: Checkpoint** — báo User, User tự commit.

---

### Task 2: Chụp mốc gốc (chưa sửa code tính giá)

**Files:** không sửa code. Tạo `output/_pricing_consolidation/snap_0_default.json`, `snap_0_duct.json`, `GOC.md`.

**Interfaces:**
- Consumes: CLI Task 1.
- Produces: snapshot mốc `snap_0_*` mà Task 3 so với.

- [ ] **Step 1:** Chạy self-test + unit (2 lệnh đầu BỘ KIỂM). Ghi kết quả vào `GOC.md`. Nếu đã có test đỏ từ trước → ghi tên, **không sửa**, báo User.
- [ ] **Step 2:** Chạy 2 lệnh E2E của BỘ KIỂM với `<N>=0`. Ghi vào `GOC.md` danh sách file đang `DIFF` / `FAIL` / `INV-OK` (đây là trạng thái gốc — không tính cho đợt này).
- [ ] **Step 3: Checkpoint** — gửi User tóm tắt `GOC.md`.

---

### Task 3: `swind_pricing` — làm tròn, hệ số lợi nhuận, giá vật tư dự phòng

**Files:**
- Create: `src/swind_pricing.py`, `tests/test_swind_pricing.py`
- Modify: `src/agent_04_bom_duct.py:9-22` (xoá `excel_round`, import từ `swind_pricing` dưới cùng tên), `src/agent_05_bom_damper.py:17-~30` và `src/agent_06_bom_diffuser.py:5-~18` (xoá `_excel_round`, `from swind_pricing import excel_round as _excel_round`); thay `float(...get("mfg_markup_factor", 1.593))` (agent_05:74,154; agent_06:33) bằng `mfg_markup(...)`; thay `mat_price_map.get("<MAT>", <số>)` trong 3 agent bằng `mat_price("<MAT>")`.

**Interfaces:**
- Produces:
  - `excel_round(value: float | None, ndigits: int = 0) -> int | float` — thuật toán của Agent 04 (`floor(x+0.5+1e-9)` cho dương, `ceil(x-0.5-1e-9)` cho âm); `None`/`0` → `0`; trả `int` khi `ndigits <= 0`, `float` khi `> 0`.
  - `mfg_markup(group: str) -> float` — `group ∈ {"damper_rules", "diffuser_rules", "duct_rules"}`, đọc `get_master_bom_rules()[group]["mfg_markup_factor"]`, mặc định `1.593`.
  - `mat_price(mat_id: str) -> float` — `get_master_price_map()` rồi bảng dự phòng `_FALLBACK_MAT_PRICES` (gom **mọi** cặp `mat_id → số` đang viết cứng trong `.get(...)` của 3 agent; nếu cùng mã có 2 số dự phòng khác nhau → lấy số trong Master Data hiện tại, ghi vào báo cáo).

- [ ] **Step 1: Viết test thất bại**

```python
from swind_pricing import excel_round, mfg_markup, mat_price

class ExcelRound(unittest.TestCase):
    def test_excel_round_matches_agent04(self):
        for v, n, exp in [(2.675, 2, 2.68), (1234.5, 0, 1235), (-2.5, 0, -3), (12500, -3, 13000), (1.005, 2, 1.01), (None, 0, 0)]:
            self.assertEqual(excel_round(v, n), exp)
    def test_int_when_ndigits_not_positive(self):
        self.assertIsInstance(excel_round(1234.4, 0), int); self.assertIsInstance(excel_round(12345, -3), int)

class Defaults(unittest.TestCase):
    def test_mfg_markup(self):
        self.assertAlmostEqual(mfg_markup("damper_rules"), 1.593); self.assertAlmostEqual(mfg_markup("diffuser_rules"), 1.593)
    def test_mat_price_unknown_uses_fallback_table(self):
        self.assertGreater(mat_price("MAT-ALU-KHUNG-OBD"), 0)
        self.assertEqual(mat_price("MAT-KHONG-TON-TAI"), 0.0)
```

- [ ] **Step 2:** `./venv/bin/python -m unittest tests.test_swind_pricing -v` → FAIL `ModuleNotFoundError: swind_pricing`.
- [ ] **Step 3:** Cài `src/swind_pricing.py` với 3 hàm trên; thay thế trong 3 agent như mục Files. Kiểm không còn định nghĩa trùng: `grep -nE "def _?excel_round|mfg_markup_factor\", *1\.593" src/agent_0[456]*.py` → không in gì.
- [ ] **Step 4:** Chạy lại test Step 2 → PASS.
- [ ] **Step 5:** Chạy BỘ KIỂM với `<N>=1`. Lệch có chủ đích của task: chỉ lệch ±1 bậc làm tròn (thường minor). Lệch lớn → dừng, báo User.
- [ ] **Step 6: Checkpoint** — gửi User tóm tắt `DIFF_1_*.md`.

---

### Task 4: Động cơ van — `select_actuator` + `ACTUATOR_IDS`

**Files:**
- Modify: `src/swind_pricing.py`, `src/agent_05_bom_damper.py:371-~460` (`_append_actuator_or_mechanism`: nhánh `is_md` và `is_mfd` gọi `select_actuator`; cầu chì FD, đối trọng, tay gạt, `md_shaft_only` giữ nguyên), `src/swind_master_runner.py:1530-1557`, `src/damper_classifier.py:~255-275` (`build_model_note`)
- Test: `tests/test_swind_pricing.py`

**Interfaces:**
- Consumes: `damper_classifier.actuator_torque(brand, w_mod, h_mod) -> (nm: str, model_honeywell: str | None)` (rule `VG-11`).
- Produces:
  - `ACTUATOR_IDS: dict[str, frozenset[str]]` — khoá `"BELIMO"`, `"KLB"`, `"HONEYWELL"`, `"MPRD"`; nội dung đúng như 4 danh sách hiện có ở runner L1533-1535 và L1551 (`MPRD` = 3 mã MPRD; `BELIMO` vẫn chứa 3 mã MPRD như hiện nay để `--motor-price` không đổi hành vi).
  - `select_actuator(kind: str, brand: str, w_mod: float, h_mod: float, *, is_single_blade: bool = False, mfd_model: str | None = None, mfd_mode: str | None = None) -> tuple[str, str, str | None]` → `(mat_id, ten_hien_thi, nm)`; `kind ∈ {"MD", "MPRD", "MFD"}`; `nm` dạng `"10Nm"`, `None` cho MFD. Tên hiển thị giữ **nguyên chữ** hiện tại ở agent_05 L380-444. MD: KLB → `MAT-ACTUATOR-SWIND-VIWECO`, `"10Nm"` cố định; Honeywell/Belimo/MPRD → mô-men từ `actuator_torque` rồi map sang mã `-5NM/-10NM/-20NM` (MPRD 10Nm = `MAT-ACTUATOR-BELIMO-MPRD`). MFD: thứ tự ưu tiên y như agent_05 L431-444.

- [ ] **Step 1: Viết test thất bại**

```python
from swind_pricing import select_actuator, ACTUATOR_IDS

class Actuator(unittest.TestCase):
    def test_select_actuator_boundaries(self):
        cases = [
            ("MD", "BELIMO", 999, 999, "MAT-ACTUATOR-BELIMO-5NM", "5Nm"),
            ("MD", "BELIMO", 1000, 500, "MAT-ACTUATOR-BELIMO-10NM", "10Nm"),
            ("MD", "BELIMO", 1500, 1200, "MAT-ACTUATOR-BELIMO-10NM", "10Nm"),   # 1.8 m² đúng ngưỡng
            ("MD", "BELIMO", 1500, 1201, "MAT-ACTUATOR-BELIMO-20NM", "20Nm"),
            ("MD", "HONEYWELL", 1000, 800, "MAT-ACTUATOR-HONEYWELL-5NM", "5Nm"),  # 0.8 m² đúng ngưỡng
            ("MD", "HONEYWELL", 1000, 801, "MAT-ACTUATOR-HONEYWELL-10NM", "10Nm"),
            ("MD", "KLB", 400, 400, "MAT-ACTUATOR-SWIND-VIWECO", "10Nm"),
            ("MPRD", "BELIMO", 999, 999, "MAT-ACTUATOR-BELIMO-MPRD-5NM", "5Nm"),
            ("MPRD", "BELIMO", 1000, 500, "MAT-ACTUATOR-BELIMO-MPRD", "10Nm"),
        ]
        for kind, brand, w, h, mat, nm in cases:
            got = select_actuator(kind, brand, w, h)
            self.assertEqual((got[0], got[2]), (mat, nm), (kind, brand, w, h))
    def test_mfd_models(self):
        self.assertEqual(select_actuator("MFD", "BELIMO", 600, 400, is_single_blade=True)[0], "MAT-ACTUATOR-BELIMO-FSLF24")
        self.assertEqual(select_actuator("MFD", "BELIMO", 600, 400, mfd_model="1.01")[0], "MAT-ACTUATOR-BELIMO-BFN24")
        self.assertEqual(select_actuator("MFD", "BELIMO", 600, 400, mfd_model="1.03")[0], "MAT-ACTUATOR-KLB-V6006FS500S")
        self.assertEqual(select_actuator("MFD", "BELIMO", 600, 400, mfd_model="1.04")[0], "MAT-ACTUATOR-HONEYWELL")
        self.assertEqual(select_actuator("MFD", "BELIMO", 1200, 800)[0], "MAT-ACTUATOR-BELIMO-BFN24")
    def test_actuator_ids_cover_every_selected_id(self):
        allowed = set().union(*ACTUATOR_IDS.values())
        for kind in ("MD", "MPRD", "MFD"):
            for brand in ("BELIMO", "KLB", "HONEYWELL"):
                for w, h in [(400, 400), (1000, 800), (1500, 1500)]:
                    for m in (None, "1.01", "1.02", "1.03", "1.04", "1.05"):
                        self.assertIn(select_actuator(kind, brand, w, h, mfd_model=m)[0], allowed)
```

*(Trước khi chạy: xác nhận các ngưỡng trên khớp `damper_rules.json` VG-11 — `≤ s_max`. Nếu hành vi cũ ở agent_05 khác JSON ở biên → JSON thắng, ghi vào báo cáo task.)*

- [ ] **Step 2:** `./venv/bin/python -m unittest tests.test_swind_pricing.Actuator -v` → FAIL `ImportError`.
- [ ] **Step 3:** Cài `ACTUATOR_IDS`, `select_actuator`. Agent 05 gọi nó (bỏ ngưỡng `1000 / 0.8 / 1.8` viết cứng — `grep -n "1\.8\|0\.8\|< 1000" src/agent_05_bom_damper.py` không còn trong `_append_actuator_or_mechanism`). Runner: `target_act_ids = ACTUATOR_IDS.get(mb_up, ACTUATOR_IDS["BELIMO"])`, `mprd_ids = ACTUATOR_IDS["MPRD"]`.
- [ ] **Step 4:** `damper_classifier.build_model_note`: khi `motor_brand == "KLB"` và van MD (không MPRD), mô-men trong ghi chú lấy từ `swind_pricing.select_actuator("MD", "KLB", ...)[2]` (`"10Nm"`) thay vì `actuator_torque`. Import trong thân hàm để tránh vòng import (`swind_pricing` import `damper_classifier`). Thêm 1 ví dụ vào `damper_rules.json` VG-11 (`vi_du_dung`: van MD 400x400, hãng KLB → ghi chú chứa `10Nm`, `nguon`: "2026-11-03 gom giá — ghi chú theo mã tính giá") và chạy `./venv/bin/python -m unittest tests.test_swind_damper_rules -v` → PASS.
- [ ] **Step 5:** Chạy lại test Step 2 → PASS.
- [ ] **Step 6:** Chạy BỘ KIỂM với `<N>=2`. Lệch có chủ đích: không có lệch giá; chỉ ghi chú van MD KLB đổi chữ mô-men.
- [ ] **Step 7: So cờ động cơ trước/sau** — chọn 1 BOQ trong `input/` có van MD + MFD (tìm bằng `swind_item_inspector.py --audit-boq <file> --filter MFD`). Với `git stash` code Task 4 và sau khi bỏ stash, chạy cùng file với lần lượt: `--motor-price 2300000`, `--mprd-motor-price 4000000`, `--md-shaft-only`, `--motor-brand HONEYWELL`, `--motor-brand KLB`, `--mfd-model 1.01`, `--mfd-model 1.04`; so Bảng Tổng Hợp. Đạt khi trùng tổng tiền từng sheet (trừ chữ ghi chú KLB).
- [ ] **Step 8: Checkpoint** — báo User.

---

### Task 5: OBD — `calc_obd`

**Files:**
- Modify: `src/swind_pricing.py`, `data/master_data/pricing_constants.json` (thêm mục `obd`), `src/agent_05_bom_damper.py:141-160`, `src/agent_06_bom_diffuser.py:596-608`
- Test: `tests/test_swind_pricing.py`

**Interfaces:**
- Consumes: `excel_round`, `mfg_markup`, `mat_price` (Task 3).
- Produces: `calc_obd(w_mm: float | None, h_mm: float | None, mult: float = 1.0, markup_group: str = "diffuser_rules") -> dict` với khoá `target_sell: int`, `frame_kg: float`, `blade_kg: float`, `acc_bo: float`. `w/h` rỗng hoặc 0 → 200. Hằng số đọc qua `K("obd.<khoá>", <số cũ>)`.
- JSON mới trong `pricing_constants.json`: `"obd": {"_nguon": "dời từ agent_05:141 / agent_06:596 — 2026-11-03, không đổi số", "khung_kg_m": 0.158, "nan_kg_m": 0.10, "buoc_nan_m": 0.04, "phu_kien_moi_nan": 1500, "phu_kien_co_dinh": 5000, "he_so": 1.15}`.
- Agent 05 dùng `markup_group="damper_rules"`, Agent 06 `"diffuser_rules"` (giữ như hiện tại; cả hai đang = 1.593).

- [ ] **Step 1: Viết test thất bại** (số đo từ code hiện tại ngày 2026-11-03)

```python
from swind_pricing import calc_obd

class Obd(unittest.TestCase):
    def test_calc_obd_matches_current_code(self):
        for (w, h), (frame, blade, acc) in {
            (200, 200): (0.115033, 0.091007, 0.600395),
            (600, 400): (0.288713, 0.54819, 1.326061),
            (1200, 800): (0.576058, 2.187561, 2.405305),
        }.items():
            r = calc_obd(w, h, markup_group="damper_rules")
            self.assertAlmostEqual(r["frame_kg"], frame, places=5)
            self.assertAlmostEqual(r["blade_kg"], blade, places=5)
            self.assertAlmostEqual(r["acc_bo"], acc, places=5)
    def test_calc_obd_defaults_missing_size(self):
        self.assertEqual(calc_obd(None, 0)["target_sell"], calc_obd(200, 200)["target_sell"])
    def test_mult_scales_target(self):
        self.assertGreater(calc_obd(600, 400, mult=1.5)["target_sell"], calc_obd(600, 400)["target_sell"])
```

- [ ] **Step 2:** `./venv/bin/python -m unittest tests.test_swind_pricing.Obd -v` → FAIL `ImportError`.
- [ ] **Step 3:** Cài `calc_obd`; thêm mục `obd` vào JSON; Agent 05 `_calc_obd_damper` và nhánh `has_obd` của Agent 06 chỉ còn gọi `calc_obd` và dựng `components` (giữ nguyên `sub_key`, `name`, `mat_id`, `note`). Kiểm: `grep -n "0\.158" src/*.py` → chỉ còn trong `swind_pricing.py` (giá trị mặc định của `K`).
- [ ] **Step 4:** Chạy lại test Step 2 → PASS.
- [ ] **Step 5:** BỘ KIỂM với `<N>=3`. Lệch có chủ đích: không có.
- [ ] **Step 6: Checkpoint** — báo User.

---

### Task 6: Lưới / LCCT / Lọc G4

**Files:**
- Modify: `src/swind_pricing.py`, `src/agent_06_bom_diffuser.py:109,127,203,570,584`, `src/agent_04_bom_duct.py:572,956`
- Test: `tests/test_swind_pricing.py`

**Interfaces:**
- Consumes: `excel_round` (Task 3).
- Produces:
  - `mesh_price(w_mm: float, h_mm: float, loai: str) -> int` — `loai="lcct"`: `w*h/1e6 * K("cua.luoi_chan_con_trung_m2", 200000)`, làm tròn `0`; `loai="luoi"`: `* K("cua.luoi_m2", 150000)`, làm tròn `-3`. `loai` khác → `ValueError`.
  - `filter_g4_price(w_mm: float, h_mm: float) -> int` — `* K("cua.loc_g4_m2", 200000)`, làm tròn `-3`.
- Áp dụng: agent_06 `_calc_profile_lcct` (L109) → `mesh_price(...,"lcct")`; L203 và L570 → `"luoi"`; L127 và L584 → `filter_g4_price`. Agent 04 L572 và L956 (`has_mesh_on_rect`, Model `+ LCCT`) → `mesh_price(...,"lcct")` — **thay đổi giá có chủ đích 150k → 200k/m²**; thêm comment `# 2026-11-03 gom giá: LCCT trên ống theo luoi_chan_con_trung_m2 (JSON thắng) — spec mục 5`.

- [ ] **Step 1: Viết test thất bại**

```python
from swind_pricing import mesh_price, filter_g4_price

class Mesh(unittest.TestCase):
    def test_lcct_uses_insect_screen_price(self):
        self.assertEqual(mesh_price(1000, 1000, "lcct"), 200000)
        self.assertEqual(mesh_price(333, 333, "lcct"), 22178)       # 0.110889 m² × 200000, làm tròn đồng
    def test_luoi_rounds_to_thousand(self):
        self.assertEqual(mesh_price(1000, 1000, "luoi"), 150000)
        self.assertEqual(mesh_price(333, 333, "luoi"), 17000)       # 16633 → 17000
    def test_filter_g4(self):
        self.assertEqual(filter_g4_price(600, 600), 72000)
    def test_unknown_type(self):
        with self.assertRaises(ValueError):
            mesh_price(100, 100, "chim")
```

- [ ] **Step 2:** `./venv/bin/python -m unittest tests.test_swind_pricing.Mesh -v` → FAIL `ImportError`.
- [ ] **Step 3:** Cài 2 hàm, thay 7 chỗ. Kiểm: `grep -nE "K\(\"cua\.(luoi|loc_g4)" src/agent_0[46]*.py` → không in gì.
- [ ] **Step 4:** Chạy lại test Step 2 → PASS.
- [ ] **Step 5:** BỘ KIỂM với `<N>=4`. Lệch có chủ đích: dòng ống/cút có Model `+ LCCT` tăng giá (chỉ ở bản `--include-duct` và dòng ống kèm LCCT). Mọi lệch lớn khác → dừng, báo User.
- [ ] **Step 6: Checkpoint** — báo User, **liệt kê riêng các dòng ống + LCCT đổi giá** để User duyệt.

---

### Task 7: VAT ở Agent 10

**Files:** Modify `src/agent_10_old_quote_carrier.py:580-581, 870-881`

**Interfaces:**
- Consumes: `swind_utils.get_quotation_profile()["vat_rate"]`, `swind_utils.vat_label()`.

- [ ] **Step 1:** Thay công thức `=ROUND(O{r}*0.08, 0)` bằng `=ROUND(O{r}*{rate}, 0)`, nhãn `"VAT 8%"` / `"(including VAT 8%)"` / bảng console bằng `vat_label()`, `round(total * 0.08)` bằng `round(total * rate)`. Kiểm: `grep -n "0\.08\|8%" src/agent_10_old_quote_carrier.py` → không in gì.
- [ ] **Step 2:** Chạy Agent 10 `--dry-run` trên 1 cặp BOQ + BG cũ có sẵn trong `input/` (nếu không có cặp nào → bỏ bước này, ghi vào báo cáo). Đạt khi bảng tổng hợp in `VAT 8%` và số tiền trùng lần chạy trước khi sửa.
- [ ] **Step 3:** Self-test + unit (2 lệnh đầu BỘ KIỂM) → PASS. *(Không cần E2E: Agent 10 không nằm trong luồng E2E.)*
- [ ] **Step 4: Checkpoint** — báo User.

---

### Task 8: Xoá file thừa, cập nhật tài liệu, chốt baseline

**Files:**
- Delete: `src/agent_03_price_learner.py`, `src/agent_00_5_boq_reviewer.py`, `src/swind_agent_0_ingestion.py`, `src/run_estimation_pipeline.py`, `src/tool_boq_learning.py`
- Modify: `AGENTS.md` (bảng Quy trình B: thêm dòng `Agent 01 · Giá dùng chung` → `src/swind_pricing.py`, nêu các hàm và quy tắc "JSON thắng"), `.agents/rules/03_FORMULA_INDEX.md` (qua `--refresh-index`), `.agents/roles/agent_05_bom_damper_role.md`, `.agents/roles/agent_06_bom_diffuser_role.md` (trỏ OBD/lưới/động cơ sang `swind_pricing`), mọi tài liệu còn nhắc 5 file bị xoá.

- [ ] **Step 1:** `grep -rn "agent_03_price_learner\|agent_00_5_boq_reviewer\|swind_agent_0_ingestion\|run_estimation_pipeline\|tool_boq_learning" --include="*.py" --include="*.md" --include="*.json" . | grep -v "^./output\|^./venv"` — mọi kết quả ngoài chính 5 file đó phải được sửa/xoá tham chiếu; nếu có **code** (không phải tài liệu) đang gọi → dừng, báo User.
- [ ] **Step 2:** Xoá 5 file; sửa tài liệu theo mục Files.
- [ ] **Step 3:** `./venv/bin/python src/swind_item_inspector.py --refresh-index`; `./venv/bin/python src/swind_item_inspector.py --locate "OBD"` → trỏ tới `swind_pricing.py:calc_obd`.
- [ ] **Step 4:** BỘ KIỂM với `<N>=5`, so với `snap_4_*` → 0 lệch (xoá file không đổi giá).
- [ ] **Step 5:** Gộp báo cáo: `--line-diff snap_0_* snap_5_* --report output/_pricing_consolidation/TONG_KET_<mode>.md`. Gửi User: số dòng lệch lớn đã duyệt, số dòng lệch nhỏ, tổng tiền từng dự án trước/sau.
- [ ] **Step 6:** **Chỉ khi User duyệt** báo cáo tổng kết: `swind_item_inspector.py --save-baseline`, `swind_e2e_regression.py --save-baseline`, `swind_e2e_regression.py --runner-args "--include-duct" --baseline data/master_data/e2e_baseline_include_duct.json --save-baseline`. Chạy lại BỘ KIỂM (bỏ 2 lệnh `--line-diff`) → mọi file `OK` hoặc `INV-OK`.
- [ ] **Step 7:** Chạy git kiểm trước push của AGENTS.md (lệnh `git diff --cached ... | grep ...`) sau khi User `git add` → không in dòng nào. **Checkpoint cuối** — User tự commit/push.
