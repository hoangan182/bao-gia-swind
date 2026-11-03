# KẾ HOẠCH TÁCH AGENT ĐỌC BOQ & GỠ "RULE CHỒNG RULE"

Ngày lập: 2026-11-02. Nguồn: phản hồi Kỹ thuật về 3 dự án BDKSCT (OGIO / VGEI / VGCG).

## 1. Vấn đề gốc

| # | Lỗi đã gặp | Nguyên nhân gốc |
|---|---|---|
| 1 | VGCG đọc nhầm cột ẩn `KL CĐT` thay vì `KL ECB` | Có **2 bộ dò header độc lập**: `swind_utils.detect_boq_header` (có rule bỏ cột/dòng ẩn) và `agent_00b_input_normalizer._scan_header_area` (viết lại từ đầu, không có rule đó). Rule bỏ cột ẩn chỉ nằm trong code, không có văn bản rule chung. |
| 2 | Chèn tiêu đề giả `Ống gió tôn dày 0.58mm` lên đầu mọi dòng | Agent 00B được thiết kế để "bổ sung section header" giúp parser nhận ống gió. Agent 00B **không có file vai trò** trong `.agents/roles/` và không có trong bảng Agent của `AGENTS.md` → nằm ngoài rule `00_STRICT_DATA_EXTRACTION` (không tự suy diễn). |
| 3 | Ngoại lệ "cửa thổi khuếch tán → SDG" | Thêm 26/10 (commit b5bf9c1, đợt MKS BP05a) bằng cách khóa theo **cụm từ trong tên** thay vì dùng cơ chế `--spec-priority note` (BOQ mẫu ECB ghi `nan bầu dục 1 lớp lõi` ở Ghi chú). Áp lan sang cả cửa vuông → sai cổ 450→300. |
| 4 | "Cấp bù" → SDG+O kể cả khi tên ghi Louver / nan Z | Rule 2 (tăng áp/hút khói/cấp bù kèm OBD) xét trước nhánh louver, không kiểm tra Tên đã ghi rõ kiểu nan. |
| 5 | Không cảnh báo Tên vs Ghi chú | Bộ cảnh báo chỉ bắt vài cặp từ khóa (sọt trứng, nan Z); thiếu `nan bầu dục / nan thẳng`. |

Điểm chung: `_resolve_diffuser_spec` (~500 dòng) là chuỗi `if/elif` mà mỗi lần sửa lại chèn thêm điều kiện, không ghi lý do → sửa chỗ này vỡ chỗ khác.

## 2. Kiến trúc đề xuất

1. **Một bộ đọc duy nhất (Reader core)** trong `swind_utils`: `visible_rows(ws)`, `visible_cols(ws)`, `detect_boq_header(ws)`. Mọi agent (00B, 01, 01B, 07, 10) bắt buộc gọi qua đây — cấm tự dò header/cột.
2. **Agent 00B chỉ được phân tích & ánh xạ cột, KHÔNG viết lại nội dung**: bỏ chèn tiêu đề giả; nếu parser thiếu ngữ cảnh ống gió thì truyền cờ `duct_context=True` cho parser thay vì chèn chữ. Độ dày ống không có trong BOQ → tra `get_standard_thickness` + gắn cờ `⚠️ độ dày theo tiêu chuẩn` (không bịa 0.58).
3. **Tách agent nhận diện theo loại hàng**, mỗi agent 1 file rule + 1 bảng ưu tiên tường minh:
   - `diffuser_classifier` (Cửa gió): bảng thứ tự ưu tiên dạng dữ liệu (JSON) thay cho chuỗi `elif`; mỗi rule có `id`, `nguon` (ngày/dự án/người chốt), `ly_do`, `vi_du_dung`, `vi_du_sai`.
   - `damper_classifier` (Van), `duct_classifier` (Ống/phụ kiện), `scope_filter` (phạm vi báo giá: ống, canvas, thương mại, phần Swind trong dòng ống).
4. **Bộ test theo rule**: mỗi rule có ≥1 dòng BOQ mẫu trong `tests/` (tên + ghi chú + kết quả mong đợi). Sửa rule bắt buộc chạy lại toàn bộ; thêm rule bắt buộc thêm mẫu.
5. **Quy trình sửa rule** (ghi vào AGENTS.md): trước khi sửa → `git log -S` tìm nguồn gốc rule + dự án gây ra → rẽ nhánh theo điều kiện, chỉ xóa khi rule đã được xác nhận sai → ghi lý do vào bảng rule.

## 3. Thứ tự thực hiện (hội thoại riêng)

1. Viết file vai trò `agent_00b_input_normalizer_role.md`, đăng ký vào `AGENTS.md`; chuyển Agent 00B sang dùng Reader core.
2. Bỏ chèn tiêu đề giả; kiểm tra lại 5 dự án đang đi qua 00B: CAND, CC17, `2 KL ĐH TG`, `NV- DỰ ÁN NHIÊN LIỆU`, `14. Ống thông gió - Minh Triết` (chạy E2E cả 2 baseline mặc định và `--include-duct`).
3. Trích bảng rule cửa gió ra JSON + test mẫu, giữ nguyên kết quả E2E hiện tại rồi mới đổi.
4. Lặp lại cho van, ống, phạm vi.

## 4. Tiến độ

**2026-11-03 — Xong bước 1 & 2:**
- Agent 00B chỉ đọc: bỏ `StructureNormalizer` / `ValidationGate` (viết lại BOQ, chèn tiêu đề giả), bỏ bộ dò header riêng → dùng Reader core. Vai trò: `.agents/roles/agent_00b_input_normalizer_role.md`; đăng ký trong `AGENTS.md`.
- Reader core `swind_utils`: `hidden_col_letters` (tính cả dải cột ẩn nhóm `B:E` — trước đây `detect_boq_header` chỉ thấy cột đầu dải), `hidden_row_indices`, `visible_rows`, `visible_cols`.
- Không thêm cờ `duct_context`: đối chiếu 5 dự án, parser đọc file gốc đã nhận đủ dòng ống — chưa có case cần.
- E2E mặc định lệch 4 file, đều là sửa đúng: NV (đọc lại cột Spec `EAL kèm LCCT` / Model `Kèm OBD`), TG (Title cha `kèm LCCT` / `kèm OBD` được kế thừa), MKS BP05a (bỏ cột ẩn `AN`/`Z` trong dải ẩn, đọc cột Remark hiển thị `AU`), CAND DHKK (giữ giá đối tác hàng thương mại theo rule chung — User duyệt, bản 11,8 tỷ cũ là do Kỹ thuật yêu cầu bỏ giá đối tác riêng CAND). Đã cập nhật baseline mặc định.
- Rule mới (User chốt 2026-11-03): Ghi chú liệt kê ≥ 2 hộp (`BOX CẤP ... / BOX HỒI ...`) trên 1 dòng → đơn giá = tổng các hộp, ghi chú nêu đủ, không thêm dòng (`Agent04._calc_multi_plenum_boxes`).
- Baseline `e2e_baseline_include_duct.json` đã lệch 32 file từ trước đợt này (chưa cập nhật sau các đợt sửa rule trước) — chưa lưu lại, chờ User rà.

**Còn lại:** bước 3 (bảng rule cửa gió JSON) & 4 — mỗi bước một hội thoại riêng.
