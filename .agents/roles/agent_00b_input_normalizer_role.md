# AGENT 00B: PHÂN TÍCH CẤU TRÚC BOQ ĐẦU VÀO (INPUT ANALYZER — CHỈ ĐỌC)
> **Mã định danh:** `SWIND-AGENT-00B`
> **Module thực thi:** [`src/agent_00b_input_normalizer.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_00b_input_normalizer.py)
> **Vị trí trong luồng:** chạy trước Agent 01 trong `swind_master_runner.py`.
> **Kế hoạch gốc:** [KE_HOACH_TACH_AGENT_DOC_BOQ.md](file:///Users/hoangan/work/PCCC/swind/plan/KE_HOACH_TACH_AGENT_DOC_BOQ.md)

---

## 1. VAI TRÒ
- Mở file BOQ **một lần**, phân tích cấu trúc từng sheet kỹ thuật (dòng header, ánh xạ cột, số dòng dữ liệu, tỷ lệ dòng có KL, công ty lập BOQ, phiếu đặt hàng nhiều đợt `Lần N`).
- Chạy thử `SwindBOQParser` trên file gốc để đo mức nhận diện, in **cảnh báo** cho sheet có cấu trúc lạ (nhiều dòng ống/phụ kiện nhưng parser nhận được ít, tỷ lệ KL>0 thấp, không thấy header...).
- Chia sẻ workbook đã mở (`self.wb`) cho Agent 01 để không mở file 2 lần.
- Ghi kinh nghiệm định dạng vào `format_learning_db.json`.

## 2. QUY TẮC BẮT BUỘC
1. **CHỈ ĐỌC — KHÔNG VIẾT LẠI NỘI DUNG BOQ.** Agent 00B luôn trả lại **file gốc**; không tạo file `_NORMALIZED.xlsx`, không chèn dòng/tiêu đề, không đổi tên hàng, không đánh lại số dòng, không bỏ cột.
   - Lý do (Kỹ thuật phản hồi BDKSCT, 2026-11-02): bản cũ chèn tiêu đề giả `Ống gió tôn dày 0.58mm` lên đầu mọi dòng → bảo ôn ống nước `Cách nhiệt ống D60 dày 10mm` (CAND) bị tính thành ống gió tôn, cửa gió bị gán độ dày 0.58; bản chuẩn hóa còn đổi cột SL `KL ECB` → `TỔNG` (CC17 `DG-CAN HO`, 626 → 154), làm mất cột Spec và lệch số dòng của `--override` (Agent 10 phải đi đường vòng).
   - Đối chiếu 5 dự án từng bị chuẩn hóa (CAND, CC17, `2 KL ĐH TG`, `NV- DỰ ÁN NHIÊN LIỆU`, `14. Ống thông gió - Minh Triết`): parser đọc file gốc cho kết quả bằng hoặc đúng hơn bản chuẩn hóa ở mọi sheet.
2. **Cấm tự dò header / cột / dòng ẩn.** Mọi phép đọc cấu trúc gọi qua **Reader core** trong `swind_utils`: `detect_boq_header(ws)`, `hidden_col_letters(ws)`, `hidden_row_indices(ws)`, `visible_rows(ws, ...)`, `visible_cols(ws, ...)`. Rule bỏ cột/dòng ẩn (trừ cột `Tổng KL`) chỉ nằm ở một chỗ đó.
3. **Không bịa dữ liệu.** Độ dày ống không có trong BOQ → để trống; Agent 04 tra `get_standard_thickness` theo cạnh lớn (không gán cứng 0.58).
4. Thiếu ngữ cảnh mà parser không tự nhận ra được → **in cảnh báo cho User**, không sửa file. Nếu sau này cần bổ sung ngữ cảnh (VD dòng ống gió không có Title), truyền tham số cho parser (VD `duct_context=True`), không chèn chữ vào BOQ.

## 2B. BỘ KIỂM CHỨNG ĐỘC LẬP TẦNG ĐỌC CẤU TRÚC (`StructureVerifier`, 2026-11-03)
Reader core là điểm đọc duy nhất → chọn nhầm cột/dòng là mọi dự án sai theo. `StructureVerifier` **không phải bộ đọc thứ 2 và không sửa kết quả**: đếm thô trên file gốc (mọi cột có số > 0 ở dòng hiển thị có tên hàng: số dòng, tổng, tiêu đề, ẩn/hiện) rồi so với cột/dòng parser đã chọn. In `⚠️ [KIỂM CHỨNG ĐỌC BOQ]` khi:
1. Parser đọc cột vai trò (Tên/SL/ĐVT/Spec/KT/Ghi chú...) đang **bị ẩn** (trừ cột SL ép theo khu `_forced_qty_col`), hoặc bóc dòng đang bị ẩn.
   - (1b, 2026-11-03) Cột kích thước W/H/L hoặc SL **trùng cột STT** — bắt lỗi BG01_SLAND / Haus_Dalat `DHKK`: mã hạng mục `A1 | HỆ THỐNG ...` bị Reader core hiểu là cột kích thước A1 (đã sửa trong `detect_boq_header`: dòng con có chữ dài ở cột Tên mà không có từ khóa tiêu đề thì dừng dò tiêu đề phụ; không nhận cột STT làm cột kích thước).
2. Có cột tiêu đề SL/KL/Khối lượng/Q'ty/Tổng **hiển thị** khác có số ở **≥ 2 lần và hơn ≥ 5 dòng** so với cột parser chọn (bỏ qua phiếu đặt hàng `Lần N` / `Tổng KL`).
3. Có cột tiêu đề KL/SL **rõ ràng** mang giá trị **khác** cột parser chọn ở ≥ 50% (tối thiểu 2) dòng đã bóc — bắt lỗi CC17 `DG-CAN HO` chọn `TỔNG` (77) thay `KL ECB` (313). Cột chỉ ghi `Tổng` (cộng nhóm) không dùng làm chuẩn so.
4. ≥ 5 dòng (và ≥ 20%) có tên + SL > 0 ở cột parser chọn mà parser không bóc, cũng không ghi lý do bỏ.
- Bỏ khỏi nhãn cột: số thứ tự cột `(13)`, tiêu đề bảng trải ngang (`BẢNG ...`, `BIỂU ...`), cột STT. Loại cột tiền/tiến độ/hệ số/hao hụt/m²/tồn kho/kỳ trước/1 tầng.
- Ngưỡng nằm ở hằng số lớp `StructureVerifier` (`MORE_ROWS_*`, `CONFLICT_*`, `UNACCOUNTED_*`). Đo lúc tạo: **0 cảnh báo trên 52 file `input/`**; giả lập lỗi cũ (CC17 chọn `TỔNG`/`CODE`, MKS chọn cột khu ẩn `AP`/`AQ`, BDCC09 chọn cột ẩn `T`) đều bị bắt. Test: `StructureVerifierTest` trong `tests/test_swind_core.py`.
- Kết quả trong report: `report["verification"][sheet]` (cột SL, nhãn, số dòng/tổng thô, số dòng/tổng đã bóc, các cột ứng viên) và `report["verify_warnings"]`.

## 3. ĐẦU RA
- `(đường_dẫn_file_gốc, report)`; `report["action"] = "analysis-only"`, `report["warnings"]` liệt kê cảnh báo theo sheet.
- Có cảnh báo → runner ghi `output/<Project>/internal_estimation/INPUT_NORMALIZATION_REPORT.json`.

## 4. LỊCH SỬ
- 2026-10-26 (`b5bf9c1`): tạo Agent 00B kèm bộ chuẩn hóa `StructureNormalizer` (viết lại sheet sang mẫu Swind, chèn section header) và `ValidationGate`.
- 2026-11-03: thêm `StructureVerifier` (mục 2B, việc A bàn giao tách agent).
- 2026-11-03: gỡ phần viết lại (xem Quy tắc 1), bỏ bộ dò header riêng `_scan_header_area` → dùng Reader core. Code cũ tra lại bằng `git show b5bf9c1:src/agent_00b_input_normalizer.py`.
