# Việc 4 — Gom quyết định loại hàng về classifier + test chặn từ khóa — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Quyết định *loại hàng* (CUA_GIO / VAN_GIO / ONG_GIO / CANVAS / TIEU_AM / ONG_MEM / THUONG_MAI / KHAC) chỉ nằm ở một chỗ: bảng rule `category_rules.json` + `category_classifier.py`. Từ khóa loại hàng không được mọc thêm trong parser / runner / utils.

**Architecture:** Bộ điều kiện JSON của `diffuser_classifier._Ctx` tách thành `src/rule_dsl.py` dùng chung. Chuỗi khoảng 160 dòng if/elif trong `SwindBOQParser.parse_sheet` (`swind_boq_parser.py:362-523`) được chép **đúng thứ tự** thành các rule `LH-xx`. Một bản ghi đầu vào/kết quả của parser cũ trên toàn bộ mẫu dòng (pattern lab) làm chuẩn: classifier mới phải cho kết quả giống 100%. Sau đó một test "bánh cóc" đếm từ khóa loại hàng trong từng file code: số đếm chỉ được giảm.

**Tech Stack:** Python 3 (venv), unittest, SQLite (pattern lab sẵn có).

**Spec:** `docs/superpowers/plans/2026-11-24-00-tong-quan-4-viec.md` (mục Việc 4) + trang đánh giá (đề xuất C, D).

## Global Constraints

- **Refactor thuần:** bản ghi chuẩn khớp 100%; `swind_pattern_lab.py --check` = 0 mẫu đổi; E2E toàn bộ 2 chế độ không `DIFF`.
- Mỗi rule `LH-xx` có `id`, `nguon` (commit / ngày / dự án lấy từ chú thích code đang có), `ly_do`, `vi_du_dung`; rule có ví dụ sai trong chú thích thì thêm `vi_du_sai`.
- Bản ghi chuẩn chứa chữ BOQ khách → lưu ở `output/_pattern_lab/` (không commit). Ví dụ trong JSON chỉ lấy chữ đã có sẵn trong chú thích code.
- Hàm vị từ gọi từ JSON phải nằm trong danh sách trắng `PREDICATES` (không `eval`, không import động theo chuỗi tuỳ ý).
- AI không commit.

## Review Focus

1. Thứ tự rule sai làm đổi kết quả ở dòng hiếm (VD Title "Cổ bạt chống rung quạt" + Tên "Chan re W350x150") → bắt bằng bản ghi chuẩn toàn bộ mẫu, không chỉ ví dụ tay → `test_golden_capture_matches` (skip nếu chưa có `output/_pattern_lab/category_golden.jsonl`).
2. Từ khóa học máy (`learned_keywords`) phải thắng mọi rule như hiện tại → rule `LH-01` + test `test_learned_wins`.
3. Từ khóa ngắn khớp nhầm chữ con (`'ống'` trong `'chống cháy'`) → điều kiện `tu_khoa` dùng `scope_filter.match_keyword`, không dùng `in` → test `test_match_keyword_boundary`.
4. Bảng phụ (`_is_side_table`) và chế độ parse lại do `--override` đi qua cùng classifier → chạy E2E các file canh gác có bảng phụ (danh sách trong `canary_report.md`).
5. File mới thêm vào `src/` có từ khóa loại hàng → test bánh cóc báo lỗi với hướng dẫn "chuyển vào category_rules.json / scope_rules.json" → `test_new_file_counted`.

---

### Task 1: Tách bộ điều kiện JSON thành `rule_dsl.py`

**Files:**
- Create: `src/rule_dsl.py`
- Modify: `src/diffuser_classifier.py` (`_Ctx` thành lớp con / dùng `RuleContext`; giữ nguyên tên `_Ctx` để test cũ chạy)
- Test: `tests/test_swind_rule_dsl.py`; `tests/test_swind_diffuser_rules.py` chạy lại không sửa

**Interfaces:**
- Produces:
  - `class RuleContext(rules: dict, groups: dict[str, list[str]] | None = None, predicates: dict[str, Callable[[str], bool]] | None = None)` với `.text: dict`, `.flags: dict`, `.num: dict`, `.hits: set[str]` (Việc 2), `.ok(cond) -> bool`, `.words(items) -> list[str]`.
  - Điều kiện có sẵn giữ nguyên cú pháp (`tat_ca`, `mot_trong`, `khong`, `tu_khoa`+`trong`+`tru`, `regex`, `so_sanh`, `thuoc`, cờ `"x"` / `"!x"`). Thêm 2 loại: `{"bat_dau": [..], "trong": "<biến>"}` (startswith) và `{"ham": "<tên trong PREDICATES>", "trong": "<biến>"}`.
  - Tham số `khop_bien: true` trên `tu_khoa` → so bằng `scope_filter.match_keyword` thay vì `in`.

- [ ] **Step 1: Viết test** cho từng loại điều kiện (mỗi loại 1 ca đúng + 1 ca sai) và `test_unknown_predicate_raises` (`{"ham": "os.system"}` → `ValueError`).
- [ ] **Step 2: Chạy** → FAIL.
- [ ] **Step 3: Viết `rule_dsl.py`**, chuyển logic `ok` / `words` / `operand` / `nums` từ `diffuser_classifier._Ctx`; `_Ctx` giữ phần riêng của cửa (`group` đọc `combo_cfg`, `pick_text`).
- [ ] **Step 4: Chạy** `test_swind_rule_dsl.py` + `test_swind_diffuser_rules.py` → PASS; `swind_pattern_lab.py --check` → 0 mẫu đổi.

---

### Task 2: Ghi bản ghi chuẩn từ parser hiện tại

**Files:**
- Modify: `src/swind_boq_parser.py` (cuối chuỗi xác định `category`, ngay trước dòng `# Trích xuất kích thước`, khoảng dòng 525)
- Create: `scripts/capture_category_golden.sh`

**Interfaces:**
- Produces: `output/_pattern_lab/category_golden.jsonl`, mỗi dòng `{"texts": {"ten", "day_du", "title", "ghi_chu", "model", "raw_name"}, "flags": {"is_plumbing", "is_hvac_prd"}, "category": str}`. Task 3 đọc file này.

- [ ] **Step 1: Thêm điểm ghi**: khi biến môi trường `SWIND_CATEGORY_CAPTURE` có giá trị, nối 1 dòng JSON vào đường dẫn đó (giá trị `ten = name_lower`, `day_du = full_name_lower`, `title = sec_lower`, `ghi_chu = note_boq`, `model = model_str`, `raw_name = raw_name_str`). Không có biến → không làm gì.
- [ ] **Step 2: Script**: xoá file cũ, `SWIND_CATEGORY_CAPTURE=output/_pattern_lab/category_golden.jsonl ./venv/bin/python src/swind_pattern_lab.py --check`, rồi in số dòng + phân bố `category`.
- [ ] **Step 3: Chạy script.** Expected: vài nghìn dòng; phân bố có đủ 8 nhóm.

---

### Task 3: `category_rules.json` + `category_classifier.py`, thay chuỗi if/elif trong parser

**Files:**
- Create: `data/master_data/category_rules.json`
- Create: `src/category_classifier.py`
- Modify: `src/swind_boq_parser.py:362-523` (thay toàn bộ chuỗi bằng 1 lệnh gọi; xoá điểm ghi của Task 2)
- Modify: `src/decision_trace.py` lời gọi trong parser: dùng `rule_id`, `nguon`, `chac` của classifier thay cho `cat_rule` tạm (Việc 2)
- Modify: `data/master_data/default_rules.json` (MD-04 `ap_cho`: `PARSER-5-TITLE` → id rule fallback-theo-Title mới)
- Create: `.agents/roles/category_classifier_role.md` (theo khuôn `diffuser_classifier_role.md`)
- Test: `tests/test_swind_category_rules.py`

**Interfaces:**
- Consumes: `rule_dsl.RuleContext`, `category_golden.jsonl`.
- Produces:
  - `load_rules(path: str | None = None) -> dict`
  - `classify(texts: dict[str, str], flags: dict[str, bool], catalogs: dict, learned: dict[str, str], rules: dict | None = None) -> dict` → `{"category": str, "rule_id": str, "nguon": list[str], "chac": bool}`. `catalogs = {"manufacturable": [...], "commercial": [...]}` đúng như `SwindBOQParser._load_catalogs` đang nạp.
  - `PREDICATES`: `is_standalone_coarse_filter`, `scope_filter.is_commercial_by_name`, `is_fan_connection_transition`, `is_duct_insulation`, `is_insect_screen_code`, `is_louver_code`, `is_glued_damper_code`, `is_auxiliary_material`, `duct_classifier.is_ventcap_name`.
  - Kết quả rule: `"ket_qua": "<NHÓM>"`, hoặc `"ket_qua": {"danh_muc": "SX" | "TM", "nhom_tru": [...], "trong": "<biến>"}` (tra catalog theo `mapping_category`, giữ quy tắc bỏ qua `VALVE_WATER` / `PIPE_COPPER` hiện có thành trường `bo_qua_khi` của rule). Mục `chuan_hoa` cuối bảng: `PHU_KIEN_ONG→ONG_GIO`, `KHOP_NOI_MEM|CHUP_THONG_HOI→CANVAS`, ventcap → `CANVAS`.
  - Mỗi rule có `nguon_chu` ∈ `TEN | TITLE | GHI_CHU | HOC_MAY` và `chac` (mặc định `true`; rule bước 5 chỉ nhờ Title = `false`).

Cách chép: đi từ trên xuống dòng 362 → 523, mỗi `if category == "KHAC" and ...` / `elif` thành 1 rule theo đúng thứ tự; chú thích ngay trên dòng code → `ly_do` + `nguon`; chữ ví dụ trong chú thích → `vi_du_dung`.

- [ ] **Step 1: Viết test**

```python
def test_every_rule_has_source_and_examples(self): ...
def test_rule_examples(self):        # chạy mọi vi_du_dung / vi_du_sai qua classify
def test_learned_wins(self):         # learned {"cửa gió 600x300": "VAN_GIO"} → VAN_GIO, rule LH-01, nguon ["HOC_MAY"]
def test_match_keyword_boundary(self):  # ten "van chống cháy 600x400" không thành ONG_GIO
def test_golden_capture_matches(self):  # mọi dòng category_golden.jsonl: classify(...)["category"] == dòng["category"]; in 20 dòng lệch đầu tiên
```
- [ ] **Step 2: Chạy** → FAIL.
- [ ] **Step 3: Viết JSON + module**, lặp đến khi `test_golden_capture_matches` khớp 100%.
- [ ] **Step 4: Thay chuỗi trong parser** bằng `res = category_classifier.classify(...)`; `category = res["category"]`.
- [ ] **Step 5: Kiểm thử chuẩn + E2E toàn bộ 2 chế độ** → 0 mẫu đổi, không DIFF. `swind_item_inspector.py --refresh-index`.

---

### Task 4: Test bánh cóc từ khóa + chuyển helper từ khóa khỏi runner

**Files:**
- Create: `tests/test_swind_keyword_guard.py`
- Create: `tests/fixtures/keyword_guard_baseline.json` (số đếm hiện tại từng file)
- Modify: `src/scope_filter.py` (nhận `is_canvas_like_name`, `is_duct_like_name`, `main_noun`, `is_swind_product_name`; tiền tố đọc từ `scope_rules.json`, khóa mới `tien_to_canvas`, `tien_to_ong`, `tien_to_ngoai_pham_vi`)
- Modify: `src/swind_master_runner.py:1161-1183` (xoá 4 hàm, gọi `scope_filter.*`; dòng 1267 `"lcct" in nm_l or "lưới chắn côn trùng" in nm_l` → `scope_filter.is_insect_screen_name(nm_l)`)
- Modify: `tests/test_swind_scope_rules.py` (ví dụ cho 4 hàm chuyển sang)

**Interfaces:**
- Produces:
  - `KEYWORDS = ["khuếch tán", "louver", "lưới chắn", "cửa gió", "miệng gió", "ống gió", "tháo lắp", "nan z", "bầu dục", "sọt trứng", "chặn lửa", "xả áp", "tiêu âm", "canvas", "ventcap", "lcct", "obd"]` — đếm số lần mỗi từ xuất hiện **bên trong chuỗi ký tự Python** (dùng `tokenize`, chỉ token `STRING`, bỏ docstring và chú thích).
  - `EXEMPT = {"diffuser_classifier.py", "damper_classifier.py", "duct_classifier.py", "category_classifier.py", "scope_filter.py", "typo_normalizer.py", "title_row_resolver.py", "rule_dsl.py", "swind_item_inspector.py", "swind_e2e_regression.py", "swind_pattern_lab.py", "agent_00_data_miner.py", "extract_master_data.py"}`.
  - `scope_filter.main_noun(name: str) -> str`, `is_canvas_like_name(name: str) -> bool`, `is_duct_like_name(name: str) -> bool`, `is_swind_product_name(name: str, scope_kws: list[str]) -> bool`, `is_insect_screen_name(name: str) -> bool`.

- [ ] **Step 1: Viết test bánh cóc**

```python
def test_counts_not_increase(self):   # mỗi file src/*.py ngoài EXEMPT: đếm <= baseline; vượt → fail kèm "<file>: '<từ>' tăng A → B. Chuyển vào category_rules.json / scope_rules.json"
def test_new_file_counted(self):      # file không có trong baseline → baseline coi là 0
def test_baseline_tight(self):        # đếm < baseline → fail nhắc chạy: ./venv/bin/python tests/test_swind_keyword_guard.py --update (chỉ cho giảm)
```
Tuỳ chọn `--update` khi chạy trực tiếp file test: ghi lại baseline, từ chối nếu có số đếm tăng.

- [ ] **Step 2: Sinh baseline** (`--update`) → test PASS.
- [ ] **Step 3: Viết test cho 4 hàm** trong `test_swind_scope_rules.py` (ví dụ lấy từ cách runner đang dùng: `"Cung cấp và lắp đặt ống gió 600x400"` → `is_duct_like_name` True; `"Gia công, lắp đặt canvas"` → `is_canvas_like_name` True) → FAIL.
- [ ] **Step 4: Chuyển hàm vào `scope_filter`**, sửa runner → test PASS.
- [ ] **Step 5: Chạy `--update`** → baseline của `swind_master_runner.py` giảm. Kiểm thử chuẩn + E2E toàn bộ → không DIFF.
- [ ] **Step 6: Tài liệu**: thêm dòng "Agent 01 · Loại hàng" vào bảng `.agents/rules/06_BAN_DO_AGENT.md` (hoặc AGENTS.md nếu Việc 1 chưa làm); thêm vào mục sửa rule của AGENTS.md: "Từ khóa loại hàng chỉ ghi trong JSON; `test_swind_keyword_guard` chặn thêm vào code". Báo User danh sách file để commit.

**Việc tiếp theo (ngoài kế hoạch này):** mỗi lần sửa rule có chạm parser / runner / utils, chuyển thêm một cụm từ khóa còn lại vào JSON và chạy `--update` để hạ baseline. Mục tiêu cho từng file ngoài `EXEMPT`: số đếm về 0.
