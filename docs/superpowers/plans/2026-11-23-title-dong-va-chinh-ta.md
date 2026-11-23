# Phân vai Title / Dòng + TY-05 sai dấu — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bắt lỗi sai dấu ở cụm từ khóa chính (TY-05) và một bộ quyết định Title ↔ Dòng duy nhất: Loại 4 và Title-không-rõ thì hỏi lại thay vì đoán lặng lẽ.

**Architecture:** `typo_normalizer.detect_accent_typos` sinh sự kiện `DOAN` (dùng lại luồng tô vàng / hàng chờ duyệt hiện có). Module mới `title_row_resolver.py` + `title_row_rules.json` phân vai Title / Dòng và trả quyết định. Parser gọi resolver sau khi đã xác định `category`. Quyết định hỏi lại được ghi vào `skip_reasons` với lý do mới, runner tô vàng và in `[HỎI LẠI USER]`. Cờ `--title-wins` chuyển thành override `title=1`.

**Tech Stack:** Python 3 (venv), unittest, openpyxl.

**Spec:** `docs/superpowers/specs/2026-11-23-title-dong-va-chinh-ta-design.md`

## Global Constraints

- Chỉ tạo chuỗi so khớp, không ghi lại BOQ. Cột / dòng ẩn bỏ qua như hiện tại.
- Rule nằm trong JSON (`id`, `nguon`, `ly_do`, `vi_du_dung`, `vi_du_sai`), không thêm `if/elif` mới cho từng ca vào parser.
- Hỏi lại = tô vàng Sheet `BG` + `[HỎI LẠI USER]` ở Kiểm soát cuối; **không chặn**, không mã thoát 2.
- Dòng có đơn giá đối tác trong BOQ: giữ nguyên hành vi hiện tại (không ép bỏ).
- Không commit (User tự đẩy git).

## Review Focus

1. Dòng hợp lệ có mã ký hiệu / vị trí (`CG-01 600x300`, `Tầng 3: 600x300`, `Loại A 600x300`, `1200x150+F`) không được rơi vào Loại 4 → test `test_chi_kt_variants`.
2. Chữ đúng khác nghĩa không bị TY-05 đổi (`ống luồn`) → test `test_ty05_giu_dau`.
3. Dòng đã có loại riêng (giá đỡ, bộ nguồn, ống nước DN) dưới Title cửa / van vẫn theo dòng (quy tắc 1a, 3c) → test `test_du_loai_commercial`.
4. Title rỗng / "SẢN PHẨM" → không có quyết định mới → test `test_no_title`.
5. Dòng bảng phụ (`is_side_table`) không nhận sự kiện của bảng chính — giữ `tag_typo_events` như cũ.

---

### Task 1: TY-05 — bắt sai dấu cụm từ khóa chính

**Files:**
- Modify: `data/master_data/typo_rules.json` (thêm rule `TY-05_SAI_DAU` với `cum_chinh`, `vi_du_dung`, `vi_du_sai`)
- Modify: `src/typo_normalizer.py` (`load_rules` đăng ký khóa `TY-05`; hàm mới)
- Modify: `src/swind_boq_parser.py:~331-338` (gọi TY-05 cho chữ dòng + Title; truyền `typo_events` vào `sec_lower`)
- Test: `tests/test_swind_typo_rules.py`

**Interfaces:**
- Produces: `detect_accent_typos(text: str) -> list[dict]` → sự kiện `{"loai": "DOAN", "goc": <span gốc lower>, "sua": <cụm chính>, "ung_vien": [<cụm chính>], "rule": "TY-05"}`.

- [ ] Test: `test_ty05_cua_gio` (`"của gió kèm hộp gió"` → 1 sự kiện goc `của gió`, sua `cửa gió`); `test_ty05_gio_huyen` (`"cửa giò hồi"` → sua `cửa gió`); `test_ty05_ong_gio` (`"ông gió"` → `ống gió`); `test_ty05_dung_khong_bao` (`"cửa gió"` → []); `test_ty05_khong_dau_de_ty02` (`"cua gio"` → []); `test_ty05_giu_dau` (`"ống luồn"` → []).
- [ ] Chạy test → FAIL (chưa có hàm).
- [ ] Cài đặt: duyệt từng cụm chính, so trên chuỗi bỏ dấu (`_fold`), bỏ qua nếu span == cụm, span hoàn toàn không dấu, hoặc có chữ thuộc `TY-02.giu_dau`. Mục `của gió` đã có trong TY-01 → TY-05 không sinh lại (chạy sau `apply_dictionary`, như `detect_code_typos`).
- [ ] Parser: `typo_events += detect_accent_typos(f"{row_own_txt} {current_section}")`; `sec_lower = normalize_for_match(..., "title", typo_events)`.
- [ ] Chạy `./venv/bin/python -m unittest tests.test_swind_typo_rules` → PASS.

### Task 2: `title_row_resolver` — phân vai và quyết định

**Files:**
- Create: `data/master_data/title_row_rules.json` (`TR-01` từ khóa loại hàng bổ sung, `TR-02` từ thông số / phụ kiện, `TR-03` chữ bỏ qua khi xét `CHI_KT`: từ vị trí + mẫu mã ký hiệu, `TR-04` bảng quyết định)
- Create: `src/title_row_resolver.py`
- Test: `tests/test_swind_title_row_rules.py`

**Interfaces:**
- Produces:
  - `title_role(title_lower: str, product_kws: Iterable[str]) -> str` ∈ `{"NONE","LOAI_HANG","PHU_KIEN","HANG_MUC"}` (`""` hoặc `"sản phẩm"` → `NONE`).
  - `row_role(own_text_lower: str, product_kws: Iterable[str]) -> str` ∈ `{"DU_LOAI","CHI_KT","KHONG_NHAN_RA"}`.
  - `decide(t_role: str, r_role: str, category: str, title_wins: bool=False) -> str|None` → `"TITLE_ROW_ASK"` (Loại 4), `"TITLE_UNCLEAR"` (`CHI_KT` dưới Title `PHU_KIEN`/`HANG_MUC`), hoặc `None` (giữ như hiện tại). Chỉ trả khác `None` khi `category` ∈ `{"CUA_GIO","VAN_GIO","ONG_GIO","TIEU_AM","CANVAS","ONG_MEM"}`; `title_wins=True` → `None`.
  - `product_keywords(manufacturable_catalog, commercial_catalog) -> set[str]` (keywords catalog ∪ `TR-01`).
- [ ] Test (mỗi ô bảng §4 spec ≥ 1 ví dụ đúng + 1 sai): `test_title_roles` (`"cửa gió kèm hộp gió kích thước:"`→LOAI_HANG, `"hệ thống điều hòa"`→HANG_MUC, `"kèm obd, lưới chắn côn trùng"`→PHU_KIEN, `""`→NONE); `test_chi_kt_variants` (`"800x250"`, `"1200x150+f"`, `"cg-01 600x300"`, `"tầng 3: 600x300"`, `"loại a 600x300"` → CHI_KT); `test_khong_nhan_ra` (`"abc xyz 600x300"` → KHONG_NHAN_RA); `test_du_loai_commercial` (`"giá đỡ 600x300"` → DU_LOAI); `test_decide_matrix` (LOAI_HANG+KHONG_NHAN_RA+CUA_GIO → TITLE_ROW_ASK; cùng + title_wins → None; HANG_MUC+CHI_KT+ONG_GIO → TITLE_UNCLEAR; HANG_MUC+CHI_KT+KHAC → None; LOAI_HANG+CHI_KT → None; LOAI_HANG+DU_LOAI → None); `test_no_title`.
- [ ] Chạy → FAIL. Cài đặt. Chạy → PASS.

### Task 3: Nối vào parser + runner + cờ `--title-wins`

**Files:**
- Modify: `src/swind_boq_parser.py` (giữ `own_cell_name` trước khi ghép Title ở dòng ~216; tính quyết định sau khối phân loại ~498; trước khối combo ~761: quyết định ≠ None và không có đơn giá đối tác → `skipped_rows` + `skip_reasons[r]["reason"]` = quyết định, kèm `"title": current_section`, `continue`)
- Modify: `src/swind_master_runner.py` (coverage ~1257: 2 lý do mới → `flag_rows` + danh sách `title_row_ask`; gate ~1915: `[HỎI LẠI USER]`; argparse `--title-wins "Sheet!R,R;Sheet2!R"` → `row_overrides[(sheet,row)]["title"]="1"`; `need_reparse` gồm khóa `title`)
- Test: `tests/test_swind_title_row_rules.py` (`test_parser_loai4_end_to_end` dựng BOQ nhỏ bằng openpyxl ở thư mục tạm: Title `Cửa gió` + dòng `abc xyz 600x300` → nằm trong `skip_reasons` lý do `TITLE_ROW_ASK`; với `row_overrides={(sheet,r):{"title":"1"}}` → thành item CUA_GIO)

Chữ tô vàng (bản chốt):
- `TITLE_ROW_ASK`: `⚠️ HỎI LẠI: dòng không rõ loại hàng, Title là '<Title>' — báo theo Title? (--title-wins "<Sheet>!<dòng>")`
- `TITLE_UNCLEAR`: `⚠️ HỎI LẠI: dòng chỉ ghi kích thước nhưng Title '<Title>' không ghi loại hàng — chưa báo giá`

- [ ] Viết test → FAIL → cài đặt → PASS.

### Task 4: Hồi quy + tài liệu

- [ ] `./venv/bin/python -m unittest discover -s tests -p "test_swind_*.py"` → OK.
- [ ] `./venv/bin/python src/swind_item_inspector.py --self-test` → chỉ còn 27 lệch có sẵn (diện tích tối thiểu 0.5).
- [ ] E2E mặc định + `--include-duct`; mỗi file `DIFF` / `FAIL` / dòng hỏi lại mới phải giải thích. Ca dương tính giả → mở rộng `TR-03` / `TR-01` trong JSON, không sửa code.
- [ ] Chạy lại `Ống thông gió` với tuỳ chọn đã chốt, so tổng (1,846,232,800đ).
- [ ] Cập nhật AGENTS.md (1a: bảng 4 loại + `--title-wins`; 2c: TY-05; bảng CLI), `--refresh-index`.
