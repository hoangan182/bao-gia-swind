# Dọn sạch sau Việc 4 — Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development. Steps use checkbox (`- [ ]`) syntax.

**Goal:** (1) Hàng ống nước ("Cụm van PIEV DN..", "Rọ hút bơm DN..") không còn bị báo như van gió; (2) đưa nốt logic NHẬN DIỆN loại hàng còn sót ngoài classifier về JSON; (3) siết test bánh cóc cho đúng mục tiêu.

**Quyết định User 2026-11-25:** (1) hàng nước → KHÔNG báo; (2) cút góc lẻ (38/35 độ) → giữ nguyên báo như cút 90°, không đổi; (3) baseline E2E/self-test cũ → duyệt khi gặp lại, KHÔNG làm trong plan này.

**Spec:** `docs/superpowers/plans/2026-11-24-4-gom-logic-ve-classifier.md` + review tổng Việc 4 (mục "Goal check + next cleanup steps").

## Global Constraints

- Chỉ chuyển logic **NHẬN DIỆN / PHẠM VI** (quyết định loại hàng, báo hay không). **Chữ HIỂN THỊ** (ghi chú BOM / BG, nhãn, thông báo console) KHÔNG chuyển, KHÔNG sửa.
- Giá từng dòng trên toàn bộ `input/` phải khớp snapshot đứng trước task, cả 2 chế độ (`swind_e2e_regression.py --line-snapshot` / `--line-diff`). Ngoại lệ DUY NHẤT: Task 1 (quyết định #1) — chỉ được mất đúng các dòng hàng nước, mọi dòng khác khớp.
- `pattern_lab --check` = 0 mẫu đổi (Task 1: chỉ mẫu hàng nước đổi, liệt kê); self-test = `output/_regression_snapshots/selftest_2026-11-25.txt`.
- Mỗi rule JSON có `nguon` + `ly_do` + ví dụ; test đi kèm. Quy trình sửa rule: `git log -S` tìm nguồn trước khi đổi (AGENTS.md mục 5).
- AI không commit. Không `git stash/checkout`.

## Review Focus

1. Hàng nước giống tên van gió Swind ("van " + DN/PN, "cụm van") — không được loại nhầm van gió thật có kích thước `AxB` (quy tắc 4i: van gió Swind ghi AxB, không ghi DN/PN).
2. Chuyển từ khóa Title (parser) sang JSON không được đổi việc kế thừa thông số Title→dòng (quy tắc 1a).
3. Bộ dò xung đột Tên/Ghi chú (runner) chuyển sang classifier không được đổi danh sách dòng bị hỏi lại User.
4. Siết bánh cóc: so chữ thường làm số đếm tăng — rebaseline MỘT LẦN bằng `--init` sau khi Task 2–5 xong, ghi rõ trong báo cáo.

---

### Task 1: Hàng ống nước không báo (quyết định #1)
**Files:** `data/master_data/scope_rules.json` (PV-01 / PV-11 `khong_phai_hang_swind_sot_dong` — đọc quy tắc 4i trước), `tests/test_swind_scope_rules.py`.
- [ ] Khảo sát: `git log -S"PIEV" -S"Rọ hút" --oneline`; chạy `swind_item_inspector.py --audit-boq` hoặc runner trên `input/KL ống gió.xlsx` (R35–36) và `input/NBT-BG DA luxora…xlsx` (R2576–77) để thấy tên dòng thật.
- [ ] Test trước: các tên thật → `is_non_swind_system_item` (hoặc hàm tương ứng) True; "Van gió 600x400", "Van chặn lửa FD 400x300" → False.
- [ ] Sửa rule trong JSON (thêm từ khóa/mẫu `cụm van … DN`, `rọ hút … DN`), kèm `nguon` "User chốt 2026-11-25".
- [ ] Nghiệm thu: line-diff 2 chế độ chỉ mất đúng các dòng hàng nước; liệt kê file/dòng. Snapshot mới thay chuẩn: `output/_regression_snapshots/lines_2026-11-25_sau_don_default.json` / `_duct.json`.

### Task 2 (read-only): Khảo sát NHẬN DIỆN vs HIỂN THỊ
**Files:** chỉ đọc. Ghi `docs/superpowers/plans/2026-11-25-5-khao-sat-tu-khoa.md` (bảng: file:dòng | chuỗi | NHẬN DIỆN hay HIỂN THỊ | đích đề xuất trong JSON | rủi ro) cho: `swind_master_runner.py` (68), `agent_04_bom_duct.py` (31), `agent_06_bom_diffuser.py` (22), `swind_boq_parser.py` (17), `swind_pricing.py`, `agent_01_boq_extractor.py`, `agent_00b_input_normalizer.py` + các mục review: `is_parent_title_kw` / `is_lcct_name` / `cv_kws` (parser), `is_box_combo` / `is_main_cv` / danh sách loại trừ only-cửa/van / `LINED_DUCT_RX` / bộ dò xung đột Tên-Ghi chú (runner), `FILTER_PREFIXES` / `FINE_FILTER_RX` (category_classifier).

### Task 3: FILTER_PREFIXES / FINE_FILTER_RX → `category_rules.json`
Chỉ khi khảo sát xác nhận là NHẬN DIỆN. Test golden + ví dụ; line-diff 0.

### Task 4: Từ khóa Title/LCCT/cv trong parser → `title_row_rules.json` / `scope_rules.json`
Theo bảng khảo sát; line-diff 0; `test_swind_title_row_rules.py` giữ nguyên.

### Task 5: Runner — `is_box_combo`, `is_main_cv`, loại trừ only-cửa/van, `LINED_DUCT_RX`, bộ dò xung đột → classifier/`scope_filter`
Theo bảng khảo sát; line-diff 0; danh sách dòng "hỏi lại" của Kiểm soát cuối không đổi (so console trước/sau trên 3 file có cảnh báo).

### Task 6: `agent_04_bom_duct.py` (canvas / tiêu âm / ventcap) — chỉ phần NHẬN DIỆN → `duct_rules.json`
Chữ ghi chú BOM giữ nguyên. line-diff 0.

### Task 7: Siết bánh cóc + rebaseline
- [ ] `count_file` đếm trên `tok.string.lower()`; thêm từ vựng van / phụ kiện ống / lọc / khớp nối / chụp (danh sách do khảo sát đề xuất); bỏ `category_classifier.py` / `scope_filter.py` khỏi EXEMPT nếu số đếm ≈ 0 (giữ `default_policy.py` / `decision_trace.py`: nhãn hiển thị).
- [ ] Rebaseline một lần: `--init`, ghi tổng trước/sau trong báo cáo. Số đếm còn lại phải là HIỂN THỊ — liệt kê lý do từng file trong docstring test.
- [ ] Cập nhật AGENTS.md (≤ 8192 B), 03_FORMULA_INDEX (`--refresh-index`), role docs.
