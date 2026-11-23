---
name: bao-gia-tu-bg-cu
description: Dẫn User từng bước báo giá BOQ/RFQ mới theo báo giá cũ — nhặt giá dòng trùng vật tư + kích thước, phần còn lại hệ thống báo mới, nhớ quyết định theo dự án (báo lại chỉ hỏi dòng mới). Kích hoạt khi User yêu cầu copy/nhặt giá từ báo giá cũ sang BOQ mới, hoặc báo lại lần 2, 3 cho dự án đã báo bằng luồng này.
---

# Trợ lý báo giá từ báo giá cũ (User chốt 2026-11-23, dự án 261123_HH3_RFQ)

Máy tính: `src/agent_10_old_quote_carrier.py` (Agent 10). Ghi nhớ: `data/old_quote_memory/<project_key>.json` (không commit).
Trợ lý chạy NGAY TRONG cuộc trò chuyện, hỏi User bằng hộp chọn (tối đa 4 câu/lượt). Không đọc lại source code trước khi chạy.

Biến dùng bên dưới:
`PY=./venv/bin/python`, `A10=src/agent_10_old_quote_carrier.py`, `BOQ=<file BOQ mới>`, `OLD=<file báo giá cũ>`,
`KEY=<mã dự án>`, `PLAN=<scratchpad>/plan_<KEY>.json`, `DEC=<scratchpad>/decisions_<KEY>.json`.
File `.xls` → chuyển `.xlsx` trước (giữ cột ẩn) như quy trình chạy báo giá thường.

## Bước 1 — Dự án & ghi nhớ
1. Chạy `$PY $A10 "$BOQ" --old-quote "$OLD" --plan-json "$PLAN"` (chưa có `--old-sheets`, mã thoát 1 là bình thường).
   Đọc `project_key_suggestion` + `sheet_summary`.
2. Hỏi User xác nhận **mã dự án** (đề xuất `project_key_suggestion`; nếu User nói là dự án đã báo trước, dùng đúng mã cũ — xem `ls data/old_quote_memory/`).

## Bước 2 — Sheet báo giá cũ
- Có ghi nhớ (`data/old_quote_memory/$KEY.json` → `old_quote.sheets`) và cùng file BG cũ → dùng lại, chỉ nhắc 1 dòng *"dùng lại sheet: ..."*.
- Không có → trình `sheet_summary` (tên sheet + số dòng có giá), đề xuất thứ tự ưu tiên (sheet cùng khu/hạng mục với BOQ trước), User chốt.

## Bước 3 — Ghép thử & hỏi theo nhóm
1. `$PY $A10 "$BOQ" --old-quote "$OLD" --old-sheets "<S1>,<S2>" --project-key "$KEY" --plan-json "$PLAN"`
2. Đọc `PLAN.rows`. Chỉ hỏi dòng `decided_by == null`. Báo trước 1 dòng tổng: số dòng `auto` (khớp chắc chắn / không có trong BG cũ) và số dòng `memory` (áp lại từ lần trước, kèm `memory.last_run_at`).
3. Hỏi **từng nhóm** theo thứ tự `kieu_nan` → `khac_hop` → `khac_ei` → `nhieu_gia` (nhóm `combo_doi_loai` mặc định báo mới — chỉ báo cho User biết số dòng). Mỗi câu hỏi:
   - nêu nhóm, số dòng, tối đa 6 ví dụ `Tên BOQ ↔ Tên BG cũ — giá cũ` (lấy từ `candidates`), lý do (`reason`);
   - lựa chọn đầu là đề xuất, ghi "(Đề xuất)": `kieu_nan` cùng mã nan → lấy giá cũ; `khac_hop` / `khac_ei` → hỏi thẳng, nêu rõ giá cũ đang gồm / không gồm hộp, EI BOQ vs EI BG cũ; `nhieu_gia` → giá ở `chosen_ref`;
   - cho phép trả lời cả nhóm hoặc liệt kê dòng ngoại lệ.
   - Dòng có `reason` chứa *"thay đổi so với lần trước"* → hỏi riêng, nói rõ đã đổi gì.
4. Ghi `DEC`:
   ```json
   {"rows": {"<key>": {"action": "carry", "ref": "<Sheet!row>"}, "<key2>": {"action": "new", "neck": false}},
    "options": {"runner_args": ["--mfd-model", "1.05"]}}
   ```
   Chỉ cần ghi dòng User đã trả lời (dòng `auto` / `memory` tự theo kế hoạch; ghi vào `DEC` để đổi ý User). `neck: true` = dòng báo mới hiểu KT là kích thước cổ.

## Bước 4 — Tuỳ chọn phần báo mới
- Đề xuất theo `suggested_options` (VD BG cũ dùng `SWIND-1.05` → `--mfd-model 1.05`; hãng động cơ) để file không lệch model giữa phần giá cũ và phần báo mới; `remembered_options` có sẵn → dùng lại, nhắc 1 dòng.
- Giữ quy tắc AGENTS.md: `--include-duct` / `--duct-uplift N` CHỈ khi User nói rõ; động cơ mặc định Belimo; không tự thêm cờ khác.
- Ghi vào `DEC.options.runner_args`.

## Bước 5 — Chạy thật & rà
1. `$PY $A10 "$BOQ" --old-quote "$OLD" --old-sheets "<S1>,<S2>" --project-key "$KEY" --decisions "$DEC" > <scratchpad>/run_<KEY>.log 2>&1`
2. Mã thoát 3 + `⛔ [THIẾU QUYẾT ĐỊNH]` → hỏi tiếp các khoá thiếu, bổ sung `DEC`, chạy lại.
3. Rà log: `[KIỂM SOÁT CUỐI]`, `⛔`, `⚠️ [HỎI LẠI USER]`, `⚠️ [THÔNG BÁO USER]`, `ĐÃ ĐOÁN`, `KIỂM CHỨNG ĐỌC BOQ`, bảng `[Agent 10] BẢNG TỔNG HỢP`, dòng `💾 [GHI NHỚ]`.
   Có dòng thiếu giá / Model trái loại → báo User, KHÔNG vá bằng `--force-new` / `--accept-review` theo số dòng.

## Bước 6 — Báo kết quả
- Chỉ đưa **File Báo Giá Cuối Cùng** (`output/<Dự án>/<tên BOQ>.xlsx`) + **bảng tổng hợp Agent 10** (giá cũ + báo mới, trước VAT / VAT / sau VAT).
- Liệt kê các dòng Kiểm soát cuối yêu cầu nêu (theo AGENTS.md), các quyết định vừa lưu (số dòng) và tuỳ chọn đã dùng.
- Không in bảng chi tiết từng mặt hàng.

## Lưu ý
- Báo lại lần sau: lặp lại từ Bước 1 với cùng `KEY` — chỉ dòng mới / dòng đổi (KT, phụ kiện, EI, giá BG cũ, file BG cũ) được hỏi.
- Đổi file BG cũ: dòng `new` giữ nguyên, dòng `carry` hỏi lại (kho tự xử lý, nói cho User biết).
- Cờ cũ của Agent 10 (`--accept-review`, `--force-new`...) vẫn dùng được khi chạy tay, nhưng không ghi kho ghi nhớ.
