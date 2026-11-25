# Việc 3 — Mặc định lặng lẽ → hỏi lại — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Không còn dòng nào bị báo nhầm loại hàng mà không có cảnh báo. Mọi lần hệ thống phải dùng mặc định đều được xử lý theo một bảng chính sách: giữ (đã chốt), báo kèm hỏi, hoặc không báo kèm hỏi.

**Architecture:** Bảng mới `data/master_data/default_rules.json` (mã `MD-xx`) ánh xạ id rule mặc định do Việc 2 ghi (`CG-09-MAC-DINH`, `VG-02-MAC-DINH`, `OG-MAC-DINH`, `PARSER-5-TITLE`) sang cách xử lý. Module `src/default_policy.py` đọc `item["decisions"]` và trả cách xử lý. `BAO_VA_HOI` → báo giá + tô vàng BG + `[HỎI LẠI USER]`; `KHONG_BAO_VA_HOI` → parser đưa vào `skip_reasons` (cùng đường `TITLE_UNCLEAR`). User duyệt bằng 2 khóa `--override` mới: `ok=1` (xác nhận mặc định) và `loai=<mã>` (chỉ định loại).

**Tech Stack:** Python 3 (venv), unittest, openpyxl.

**Spec:** `docs/superpowers/plans/2026-11-24-00-tong-quan-4-viec.md` (mục Việc 3 + "Quyết định cần User chốt").

## Global Constraints

- ~~Chờ User chốt~~ **ĐÃ CHỐT 2026-11-24:** mặc định chưa chốt → `BAO_VA_HOI` (báo giá + tô vàng).

### Bàn giao từ Việc 2 (đã làm 2026-11-25 — đọc trước khi code)
- `default_policy.policy` khớp theo **`d["rule"] == ap_cho`**, KHÔNG lọc trước bằng `"MAC_DINH" in nguon`: `PARSER-5-TITLE` được ghi `nguon ["TITLE"]`, `chac False` (không có MAC_DINH) → lọc theo nguồn thì MD-04 không bao giờ chạy.
- Cửa gió: id mặc định nằm ở `decisions[].rule` = `CG-09-MAC-DINH` (Agent 01 lấy từ khóa `rule_quyet_dinh` của classifier; `rule_id` classifier giữ nguyên `CG-09_DU_PHONG`). Đọc `item["decisions"]`, không đọc output classifier.
- Van: `VG-02-MAC-DINH` chỉ còn là mặc định khi VG-03/04/05 không nâng loại (đã sửa ở đợt cuối Việc 2).
- Ống tiêu âm theo Title (OG-19) KHÔNG còn ghi `OG-MAC-DINH` (đã sửa ở Việc 2) → MD-03 không cần ngoại lệ tiêu âm.
- Task 3 (parser ~dòng 822, sau `title_row_resolver.decide`): lúc này `item["decisions"]` **chưa tồn tại** (parser ghi `loai_hang` sau `items.append`, ~dòng 1008). Dùng biến cục bộ `cat_rule` + `category` (đã qua PV-05..08), hoặc chuyển chỗ ghi lên sớm hơn.
- MD-04 kiểm thêm `gia_tri == "ONG_GIO"`: giá trị ghi là loại cuối (sau PV-05..08, PHU_KIEN_ONG→ONG_GIO, Ventcap→CANVAS) nhưng `rule` là bước parser chạy đầu.
- Loại hàng đổi sau parser có id riêng: `AGENT02-GOI-Y` (HOC_MAY, chac False), `AGENT02-HOC-MAY`, `AGENT02-USER` (CO_USER), `CO-LINED-DUCT-AS-DUCT`, `AGENT01-LOAI-DOI` (MAC_DINH, chac False). Cân nhắc thêm MD-xx cho `AGENT02-GOI-Y` (gợi ý từ khóa tự động) và `AGENT01-LOAI-DOI`.
- Tiêu chí "không đổi giá" dùng được: `swind_e2e_regression.py --line-snapshot` / `--line-diff` (baseline E2E và self-test hiện lệch sẵn).
- Mặc định đã chốt (`GIU`) không tô vàng, không in Kiểm soát cuối, không đổi giá.
- Không chặn, không đổi mã thoát (giống quy tắc 1c).
- Dòng có đơn giá đối tác trong BOQ: giữ nguyên hành vi hiện tại, không đưa vào `KHONG_BAO_VA_HOI`.
- Mỗi rule `MD-xx` có `id`, `ap_cho`, `xu_ly`, `nguon`, `ly_do`, `vi_du_dung`.
- AI không commit.

## Review Focus

1. "Ống gió 600x400" (`OG-18`) là cách viết bình thường → không được tô vàng → rule MD-03 có `tru_khi_ten_co: ["ống"]`, test `test_og_default_with_ong_word_kept`.
2. `ok=1` cho dòng không có mặc định → không lỗi, không đổi gì → test `test_ok_without_default`.
3. `loai=MD` trên dòng cửa gió → classifier cửa đọc cột Model như thường; không ép thành van → test `test_loai_on_diffuser`.
4. BOQ ống gió chạy không `--include-duct` → `PARSER-5-TITLE` dòng ống vốn bị bỏ → không thêm `⚠️` mới → test `test_duct_default_off_no_new_warning`.
5. Dòng KL = 0 → không tô vàng, không in → dùng chung điều kiện `qty > 0` như `typo_normalizer.gate_lines`.

---

### Task 1: Bảng chính sách + `default_policy.py`

**Files:**
- Create: `data/master_data/default_rules.json`
- Create: `src/default_policy.py`
- Test: `tests/test_swind_default_rules.py`

Nội dung bảng (giá trị chốt):

| id | ap_cho | xu_ly | nguon |
|---|---|---|---|
| MD-01 | `CG-09-MAC-DINH` | `GIU` | AGENTS.md 4a-0b, User chốt 2026-11-24 (cửa không ghi kiểu → SDG) |
| MD-02 | `VG-02-MAC-DINH` | `BAO_VA_HOI` | Việc 3, 2026-11-24 (van không nhận ra loại → đang báo VCD) |
| MD-03 | `OG-MAC-DINH` | `BAO_VA_HOI`, `tru_khi_ten_co: ["ống", "duct"]` | Việc 3 (dòng không ghi "ống" mà thành ống vuông) |
| MD-04 | `PARSER-5-TITLE` | `KHONG_BAO_VA_HOI` | cùng logic TITLE_UNCLEAR, User chốt 2026-11-23 |

**Interfaces:**
- Consumes: `item["decisions"]` (Việc 2: phần tử `{"truong", "gia_tri", "nguon", "rule", "chac"}`).
- Produces:
  - `load_rules(path: str | None = None) -> dict`
  - `policy(item: dict) -> dict | None` → `{"id": "MD-02", "xu_ly": "BAO_VA_HOI", "truong": "kieu", "gia_tri": "VCD"}` cho quyết định mặc định đầu tiên khớp `ap_cho`; `None` khi `item.get("default_confirmed")`, khi `xu_ly == "GIU"`, hoặc khi `raw_name` chứa từ trong `tru_khi_ten_co`.
  - `bg_flag(item: dict) -> str | None` → `"⚠️ ĐÃ HIỂU THEO MẶC ĐỊNH: <gia_tri> (BOQ không ghi rõ loại) — xin xác nhận (--override \"<sheet>!<row>:ok=1\" hoặc loai=<mã>)"` khi `BAO_VA_HOI`.
  - `gate_lines(all_items: list[dict], limit: int = 10) -> list[str]` → 1 dòng `[HỎI LẠI USER] N dòng báo theo MẶC ĐỊNH ...: R14 'Van 600x400'=VCD; ...` (chỉ `BAO_VA_HOI`, `qty > 0`).

- [ ] **Step 1: Viết test**

```python
def test_every_rule_has_source_and_examples(self): ...      # như test_swind_title_row_rules
def test_vg02_default_asks(self):
    it = {"raw_name": "Van 600x400", "qty": 2, "source_sheet": "S", "source_row": 9,
          "decisions": [{"truong": "kieu", "gia_tri": "VCD", "nguon": ["MAC_DINH"], "rule": "VG-02-MAC-DINH", "chac": False}]}
    self.assertEqual(dp.policy(it)["id"], "MD-02")
    self.assertIn("ĐÃ HIỂU THEO MẶC ĐỊNH: VCD", dp.bg_flag(it))
def test_cg09_kept(self):                       # rule CG-09-MAC-DINH → policy None, bg_flag None
def test_og_default_with_ong_word_kept(self):   # raw_name "Ống gió 600x400", rule OG-MAC-DINH → None
def test_confirmed(self):                       # default_confirmed True → None
def test_ok_without_default(self):              # decisions không có MAC_DINH + default_confirmed → None, không lỗi
def test_gate_lines_zero_qty(self):             # qty 0 → []
```

- [ ] **Step 2: Chạy** `./venv/bin/python -m unittest tests/test_swind_default_rules.py -v` → FAIL.
- [ ] **Step 3: Viết JSON + module.**
- [ ] **Step 4: Chạy** → PASS.

---

### Task 2: Báo kèm hỏi — tô vàng BG + Kiểm soát cuối

**Files:**
- Modify: `src/swind_excel_builder.py` (`_write_quoted_row`, chuỗi `flag = " | ".join(...)` ở khoảng dòng 611: thêm `default_policy.bg_flag(item)`)
- Modify: `src/swind_master_runner.py` (`evaluate_quotation_gate`: `confirm.extend(default_policy.gate_lines(all_items))` ngay sau `typo_normalizer.gate_lines`)
- Modify: `src/decision_trace.py` (`review_rows`: bỏ quyết định có `policy` = `GIU` khỏi bảng cần xem; vẫn giữ trong JSON)
- Test: `tests/test_swind_default_rules.py` (thêm `test_bg_flag_written`: dựng 1 item van mặc định, gọi `SwindExcelBuilder.build_quotation_sheets`, đọc lại ô Ghi chú dòng đó có chuỗi `ĐÃ HIỂU THEO MẶC ĐỊNH`, ô được tô vàng giống dòng lỗi gõ)

- [ ] **Step 1: Viết test** → **Step 2:** FAIL → **Step 3:** sửa 3 file → **Step 4:** PASS.
- [ ] **Step 5: Kiểm thử chuẩn.** Được phép: E2E `DIFF` chỉ ở *ghi chú* các dòng MD-02 / MD-03, tổng tiền và số dòng không đổi. Liệt kê các dòng mới tô vàng theo từng file để User duyệt (lấy từ `--check` report).

---

### Task 3: Không báo kèm hỏi — loại hàng chỉ nhờ Title

**Files:**
- Modify: `src/swind_boq_parser.py` (sau khi gọi `title_row_resolver.decide`, khoảng dòng 810: nếu `default_policy` cho quyết định `loai_hang` trả `KHONG_BAO_VA_HOI` và dòng không có đơn giá đối tác → ghi `skip_reasons` với `reason = "CATEGORY_DEFAULT_ASK"`, cùng cấu trúc bản ghi `TITLE_UNCLEAR`)
- Modify: `src/swind_master_runner.py` (khối dựng `flag_rows` khoảng dòng 1271–1285: thêm `CATEGORY_DEFAULT_ASK` → `"⚠️ HỎI LẠI: dòng chỉ được xếp loại hàng nhờ Title '<ttl>' — chưa báo giá (--override \"<sheet>!<r>:ok=1\")"`; `evaluate_quotation_gate`: gộp vào dòng `[HỎI LẠI USER]` của `title_row_ask`)
- Test: `tests/test_swind_default_rules.py` (`test_parser_title_only_asks`: Title "Thông gió", dòng "800x400" chạy với `include_duct` → `skip_reasons` có `CATEGORY_DEFAULT_ASK`; `test_duct_default_off_no_new_warning`: cùng BOQ không `include_duct` → không có `CATEGORY_DEFAULT_ASK`)

- [ ] **Step 1–4: test → FAIL → sửa → PASS.**
- [ ] **Step 5: Kiểm thử chuẩn.** Được phép: chế độ `duct` giảm số dòng ở các file có dòng `PARSER-5-TITLE`; liệt kê từng dòng cho User duyệt trước khi lưu baseline.

---

### Task 4: Khóa `--override` `ok=1` và `loai=<mã>`

**Files:**
- Modify: `src/swind_boq_parser.py` (khối áp `row_ov` khoảng dòng 678–697: `ok` → `item["default_confirmed"] = True`; `loai` → nối mã vào `item["model"]` để VG-01 / classifier cửa đọc như cột Model)
- Modify: `src/swind_master_runner.py` (`need_reparse` khoảng dòng 1462: thêm `"ok" in v or "loai" in v`; chuỗi help của `--override`)
- Modify: `src/default_policy.py` (`policy`: `default_confirmed` → `None`), `src/decision_trace.py` (dòng có `default_confirmed` ghi thêm nguồn `CO_USER`)
- Test: `tests/test_swind_default_rules.py` (`test_override_ok`: dòng van mặc định + `ok=1` → không tô vàng, giá không đổi; `test_override_loai`: `loai=MD` → `damper_type == "MD"`, trail có `VG-01`; `test_loai_on_diffuser`: dòng "Cửa gió 600x300" + `loai=SD` → model bắt đầu bằng `SD`)

- [ ] **Step 1–4: test → FAIL → sửa → PASS.**
- [ ] **Step 5: E2E toàn bộ** (cả 2 chế độ). Báo User: số dòng mới tô vàng / mới bị giữ lại theo từng file, kèm lệnh `--override` mẫu.
- [ ] **Step 6: Tài liệu**: thêm vào mục "Bắt buộc hỏi lại User" của AGENTS.md 1 dòng: `[HỎI LẠI USER] ... MẶC ĐỊNH` → liệt kê dòng, User trả lời bằng `ok=1` / `loai=<mã>`. Chi tiết MD-xx vào `.agents/rules/04_QUY_TAC_NGHIEP_VU.md`. Sau khi User duyệt: `swind_e2e_regression.py --save-baseline`, `swind_pattern_lab.py --set-baseline`. Báo User danh sách file để commit.

**Duy trì về sau:** gặp mặc định mới → thêm `MD-xx` vào JSON (mặc định `BAO_VA_HOI`); chỉ chuyển sang `GIU` khi User chốt, ghi `nguon` ngày + dự án.
