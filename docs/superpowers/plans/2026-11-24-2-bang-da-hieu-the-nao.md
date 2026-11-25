# Việc 2 — Bảng "đã hiểu thế nào" + nguồn từng quyết định — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mỗi dòng báo giá mang theo bản ghi "hệ thống hiểu dòng này là gì, dựa vào chữ nào ở đâu, có phải mặc định không". Runner in bảng rút gọn các dòng cần người xem; inspector giải thích được một dòng mà không cần đọc mã nguồn.

**Architecture:** Module mới `src/decision_trace.py` ghi quyết định vào `item["decisions"]`. Các classifier hiện đã tính `rule_id` / `trail` nhưng Agent 01 đang bỏ đi; kế hoạch giữ lại và bổ sung *nguồn chữ* (Tên / Ghi chú / Title / Model / cờ User / học máy / mặc định). Parser ghi nguồn của quyết định loại hàng ở mức thô (Việc 4 sẽ thay bằng id rule chính xác). Runner ghi `DECISION_TRACE.json` + `DECISION_REVIEW.md` vào `internal_estimation/` và in tối đa 15 dòng cần xem. **Không đổi Model, giá hay số dòng nào.**

**Tech Stack:** Python 3 (venv), unittest.

**Spec:** `docs/superpowers/plans/2026-11-24-00-tong-quan-4-viec.md` (mục Việc 2) + trang đánh giá (đề xuất A).

## Global Constraints

- Không đổi kết quả báo giá: `swind_pattern_lab.py --check` = 0 mẫu đổi; E2E không `DIFF`.
- Không chặn, không đổi mã thoát. Thêm 1 dòng `ℹ️` ở Kiểm soát cuối, không thêm `⚠️`.
- `item["decisions"]` không được ghi vào Sheet BG gửi khách.
- Giá trị nguồn chỉ thuộc `SOURCES = ("TEN", "GHI_CHU", "TITLE", "MODEL", "CO_USER", "HOC_MAY", "MAC_DINH")`.
- AI không commit.

## Review Focus

1. Dòng combo (Cửa + Van) gọi `resolve_item_spec` đệ quy cho phần van (`agent_01_boq_extractor.py:262`) → quyết định của phần van không được ghi đè quyết định của dòng cha → test `test_combo_keeps_parent_decisions`.
2. `resolve_item_spec` được gọi lại nhiều lần cho cùng 1 dòng (excel builder gọi lại khi thiếu `resolved_spec`) → `record` thay thế theo `field`, không nhân đôi → test `test_record_replaces_same_field`.
3. Dòng KL = 0 hoặc bị lọc phạm vi → không vào bảng cần xem → test `test_review_skips_zero_qty`.
4. BOQ nhiều sheet → bảng ghi đúng tên sheet + số dòng gốc (`source_sheet`, `source_row`) → kiểm trong test `test_review_rows_shape`.
5. Item thiếu `decisions` (đường gọi khác như `swind_boq_doctor`) → các hàm báo cáo không crash → test `test_missing_decisions_ok`.

---

### Task 1: Module `decision_trace.py`

**Files:**
- Create: `src/decision_trace.py`
- Test: `tests/test_swind_decision_trace.py`

**Interfaces:**
- Produces:
  - `SOURCES: tuple[str, ...]` (giá trị ở Global Constraints)
  - `TEXT_SOURCE: dict[str, str]` — tên biến văn bản trong classifier → nguồn: `title_low→TITLE`, `note_boq_low→GHI_CHU`, `note_model_low→GHI_CHU`, `raw_name_low→TEN`, `primary_diff_search→TEN`, `ten_model→TEN`, `raw_search→TEN`, `full_search→TITLE`, `combined_search→TITLE`, `unaccent_search→TITLE`, `blade_search→TEN`.
  - `record(item: dict, field: str, value: str, source: str | list[str], rule: str, sure: bool = True) -> None` — `field` ∈ `{"loai_hang", "kieu", "model"}`; thay bản ghi cùng `field`; `source` list được khử trùng lặp, giữ thứ tự.
  - `review_rows(all_items: list[dict]) -> list[dict]` — dòng `qty > 0`, không nằm trong `skip` có ít nhất 1 quyết định `MAC_DINH` hoặc `sure=False`. Phần tử: `{"sheet", "row", "raw_name", "decisions": [...]}`.
  - `console_lines(all_items: list[dict], limit: int = 15) -> list[str]`
  - `write_report(all_items: list[dict], out_dir: str) -> tuple[str, str]` → đường dẫn `DECISION_TRACE.json` (mọi dòng có `decisions`), `DECISION_REVIEW.md` (chỉ `review_rows`, dạng bảng: Dòng | BOQ ghi | Hiểu là | Căn cứ | Độ chắc).
  - `explain(item: dict) -> str` — nhiều dòng, VD `loai_hang = CUA_GIO  ← TEN (PARSER-TEN)`.

- [ ] **Step 1: Viết test**

```python
def test_record_replaces_same_field(self):
    it = {}
    dt.record(it, "kieu", "BD", "TEN", "CG-07")
    dt.record(it, "kieu", "T", ["TITLE", "TITLE"], "CG-08B")
    self.assertEqual(it["decisions"], [{"truong": "kieu", "gia_tri": "T", "nguon": ["TITLE"], "rule": "CG-08B", "chac": True}])
def test_review_skips_zero_qty(self):      # qty 0 + MAC_DINH → không có trong review_rows
def test_review_rows_shape(self):          # 1 dòng sure=False → {"sheet": "S1", "row": 14, "raw_name": ..., "decisions": [...]}
def test_missing_decisions_ok(self):       # review_rows([{"qty": 1}]) == [], explain({}) == ""
def test_write_report(self):               # tempdir → 2 file tồn tại; JSON load được; MD chứa "| R14 |"
def test_unknown_source_rejected(self):    # record(..., "XYZ", ...) → ValueError
```

- [ ] **Step 2: Chạy** `./venv/bin/python -m unittest tests/test_swind_decision_trace.py -v` → FAIL (`ModuleNotFoundError`).
- [ ] **Step 3: Viết `src/decision_trace.py`** theo Interfaces (chỉ thư viện chuẩn).
- [ ] **Step 4: Chạy lại** → 6 PASS.

---

### Task 2: Classifier trả nguồn chữ và dấu mặc định

**Files:**
- Modify: `src/diffuser_classifier.py` (`_Ctx.__init__`, `_Ctx.ok`, `_run_step`, `classify`, `_subtype_lookup`)
- Modify: `src/damper_classifier.py` (`classify_type` nhánh VG-02, `classify`)
- Modify: `src/duct_classifier.py` (`detect_subtype`)
- Test: `tests/test_swind_diffuser_rules.py`, `tests/test_swind_damper_rules.py`, `tests/test_swind_duct_rules.py` (thêm test, không sửa test cũ)

**Interfaces:**
- Consumes: `decision_trace.TEXT_SOURCE`
- Produces:
  - `diffuser_classifier.classify(...)` trả thêm `"nguon": list[str]` và `"mac_dinh": bool`; `rule_id` = `"CG-09-MAC-DINH"` khi CG-09 chọn profile qua `@subtype_rules` mà bảng subtype không khớp từ khóa nào.
  - `damper_classifier.classify(...)` trả thêm `"nguon": list[str]`; `trail` có `"VG-02-MAC-DINH"` khi VG-02 không khớp từ khóa nào và dùng `mac_dinh` (`VCD`).
  - `duct_classifier.detect_subtype(...)` thêm `"OG-MAC-DINH"` vào `trail` khi rule thắng có `"mac_dinh": true` (hiện là `OG-18_ONG_VUONG`).

Cách tính nguồn cửa gió: `_Ctx` thêm `self.hits: set[str]` và `self.flag_src: dict[str, set[str]]`. Trong `ok`, nhánh `tu_khoa` / `regex` khớp → thêm `cond["trong"]` vào `hits`. `_run_step` khi đặt cờ `co` = True → `flag_src[co] = hits đã gom trong lần đánh giá đó`. Nguồn của rule thắng = hợp `flag_src` của các cờ dương được tham chiếu trong `dieu_kien` của rule và của `chon_profile` đã chọn, cộng `hits` trực tiếp của hai điều kiện đó; đổi qua `TEXT_SOURCE`. Rỗng → `["MAC_DINH"]`. Cột Model: biến `note_model_low` chứa cả Model → giữ `GHI_CHU` (chấp nhận thô ở bước này).

Phát hiện "bảng subtype không khớp": gọi `A01.get_subtype(..., default=None)` hai lần như hiện tại; cả hai trả `None` → mặc định. Giá trị trả về giữ nguyên `"BD"` / `VCD`.

- [ ] **Step 1: Viết test**

```python
# diffuser
def test_nguon_title(self):   # Tên "600x600", Title "Cửa gió khuếch tán" → rule CG-08B, "TITLE" in nguon, mac_dinh False
def test_nguon_ten(self):     # Tên "Cửa gió nan Z 800x400" → CG-06, nguon == ["TEN"]
def test_default_profile(self):  # Tên "Cửa gió 600x300", không Title/Ghi chú → rule_id "CG-09-MAC-DINH", mac_dinh True, model bắt đầu "SDG"
# damper
def test_vg02_default(self):  # Tên "Van 600x400" (Title rỗng) → "VG-02-MAC-DINH" in trail, damper_type "VCD"
def test_vg01_model(self):    # Model "MFD" → nguon == ["MODEL"]
# duct
def test_og_default(self):    # detect_subtype("ống gió 600x400", 600, 400, trail=t) → "OG-MAC-DINH" in t
```
Dựng `item` theo cách các test hiện có trong từng file đang dựng (dùng lại helper sẵn có trong file test).

- [ ] **Step 2: Chạy 3 file test** → các test mới FAIL, test cũ PASS.
- [ ] **Step 3: Sửa 3 classifier** theo Interfaces. Không đổi `model`, `note`, `profile_type`, `damper_type`, `subtype` trả về.
- [ ] **Step 4: Chạy 3 file test** → tất cả PASS. Chạy `swind_pattern_lab.py --check` → 0 mẫu đổi.

---

### Task 3: Ghi quyết định ở parser (loại hàng) và Agent 01 (kiểu, Model)

**Files:**
- Modify: `src/swind_boq_parser.py:362-523` (chuỗi xác định `category` trong `parse_sheet`)
- Modify: `src/agent_01_boq_extractor.py` (`_resolve_damper_spec`, `_resolve_diffuser_spec`, `_resolve_duct_spec`, `resolve_item_spec`)
- Test: `tests/test_swind_decision_trace.py` (thêm lớp `PipelineTest`)

**Interfaces:**
- Consumes: `decision_trace.record`, kết quả Task 2.
- Produces: mọi item ra khỏi `Agent01_BOQExtractor.enrich_all_items` có `item["decisions"]` gồm `loai_hang` + `kieu` (+ `model` với CUA_GIO/VAN_GIO). Id rule loại hàng tạm thời: `PARSER-HOC-MAY`, `PARSER-TEN`, `PARSER-TITLE`, `PARSER-5-TEN`, `PARSER-5-TITLE` (Việc 3 và 4 tham chiếu đúng các id này).

Parser: thêm biến `cat_rule = "PARSER-TEN"` cạnh `category = "KHAC"` (dòng 362). Gán lại ở đúng 4 chỗ: nhánh `learned_keywords` → `PARSER-HOC-MAY` (nguồn `HOC_MAY`); nhánh `any(k in sec_lower ...)` → CUA_GIO và hai vòng lặp trên `full_name_lower` → `PARSER-TITLE` (nguồn `TITLE`); bước 5 `has_duct` → `PARSER-5-TEN`; bước 5 chỉ nhờ `sec_lower` → `PARSER-5-TITLE` (nguồn `TITLE`, `sure=False`). Khi dựng item, gọi `decision_trace.record(item, "loai_hang", category, nguồn, cat_rule, sure)`.

Agent 01: sau mỗi lệnh gọi classifier, ghi `kieu` (profile / damper_type / subtype) với `rule` = `rule_id` hoặc phần tử cuối của `trail`, `source` = `cls_res["nguon"]`, `sure = not mac_dinh`; ghi `model` = model cuối cùng trong `resolved_spec` với cùng rule. Dòng van tách từ combo (`dmp_item`) là item tạm → không chép `decisions` của nó vào item cha.

- [ ] **Step 1: Viết test**

```python
def test_pipeline_records(self):
    # Dựng workbook RAM: Title "CỬA GIÓ" ; dòng "600x300" ; dòng "Van 600x400" ; dòng "Cửa gió nan Z 800x400"
    # SwindBOQParser(wb=...).parse_sheet + Agent01_BOQExtractor.enrich_all_items
    # dòng 1: loai_hang rule PARSER-TITLE ; dòng 2: kieu rule VG-02-MAC-DINH chac False ; dòng 3: kieu CG-06 nguon ["TEN"]
def test_combo_keeps_parent_decisions(self):  # "Cửa gió 600x300 + MFD" → decisions loai_hang == CUA_GIO, không có bản ghi loai_hang VAN_GIO
```
Dựng workbook theo cách `tests/test_swind_title_row_rules.py` đang dựng (openpyxl `Workbook()` trong RAM).

- [ ] **Step 2: Chạy** → FAIL.
- [ ] **Step 3: Sửa parser và Agent 01** theo Interfaces.
- [ ] **Step 4: Chạy test** → PASS. Chạy kiểm thử chuẩn (file tổng quan) → `--check` 0 mẫu đổi, E2E không DIFF.

---

### Task 4: Runner xuất báo cáo, inspector giải thích

**Files:**
- Modify: `src/swind_master_runner.py` (trong `run_master_pipeline`, ngay trước `gate = evaluate_quotation_gate(` ở khoảng dòng 1836)
- Modify: `src/swind_item_inspector.py` (đường in kết quả cho 1 mặt hàng)
- Test: `tests/test_swind_decision_trace.py` (thêm `test_runner_writes_report` chạy runner trên 1 file nhỏ trong `input/`, `SWIND_NO_LEARNING_WRITE=1`, skip nếu thư mục `input/` trống)

**Interfaces:**
- Consumes: `decision_trace.write_report`, `console_lines`, `explain`.

- [ ] **Step 1: Viết test** — sau khi chạy runner: `output/<Project>/internal_estimation/DECISION_TRACE.json` tồn tại, mỗi phần tử có khóa `decisions`; stdout chứa `[ĐÃ HIỂU THẾ NÀO]`.
- [ ] **Step 2: Chạy** → FAIL.
- [ ] **Step 3: Runner**: gọi `write_report(all_items, internal_dir)`; in tiêu đề `📋 [ĐÃ HIỂU THẾ NÀO] N dòng cần xem (mặc định / chưa chắc) — chi tiết: <đường dẫn DECISION_REVIEW.md>` rồi `console_lines(all_items)`. Thêm vào `gate["info"]` 1 dòng `Bảng đã hiểu thế nào: <đường dẫn>`. Inspector: in `decision_trace.explain(item)` dưới phần kết quả hiện có của mỗi mặt hàng.
- [ ] **Step 4: Chạy test + kiểm thử chuẩn + E2E toàn bộ** → PASS, không DIFF.
- [ ] **Step 5: Thử tay** trên 1 BOQ thật User chọn: đọc `DECISION_REVIEW.md`, đếm số dòng cần xem. Báo User con số này. Nếu > 30% số dòng báo giá thì nguồn chữ đang quá thô: ghi lại để Việc 3 lọc theo `default_rules.json`.
- [ ] **Step 6: Cập nhật tài liệu**: thêm dòng "Bảng đã hiểu thế nào" vào `.agents/rules/05_CLI_VA_KIEM_THU.md` (hoặc AGENTS.md nếu Việc 1 chưa làm); `swind_item_inspector.py --refresh-index`. Báo User danh sách file để commit.
