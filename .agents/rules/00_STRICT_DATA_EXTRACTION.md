---
trigger: always_on
priority: highest
description: Strict Anti-Hardcoding, Source of Truth, and Unmerge Rules
---

# LỆNH BÀI TỐI CAO (HIGHEST PRIORITY RULE)

Đây là quy tắc cao nhất của dự án Swind, áp dụng cho tất cả các Agent và quy trình.

## 1. Anti-Hardcoding (Chống Làm Giả Dữ Liệu)
- **TUYỆT ĐỐI KHÔNG ĐƯỢC** gán cứng (hardcode) dữ liệu vào trong code nếu dữ liệu đó đáng lẽ phải được lấy từ file gốc (Source of Truth).
- **CẤM** hành vi "Ăn gian" (Fake Execution): Cấm tạo ra logic code giả mạo (như lệnh if/else với chuỗi tĩnh, append dictionary cố định) để lấp liếm việc không thể bóc tách dữ liệu phức tạp từ file.
- Mọi dữ liệu (giá cả, kích thước, định mức, danh mục) phải được đọc, trích xuất và xử lý bằng thuật toán (Pandas, xlrd, openpyxl) trực tiếp từ file dữ liệu đầu vào.

## 2. Xử Lý Bảng Tính (Phá Merge Cells)
- Nếu file gốc (Excel) có chứa Merged Cells, bắt buộc phải viết thuật toán để **phá merge** (Unmerge) hoặc fill data (quét `merged_cells` và copy giá trị top-left vào tất cả các ô trong dải) để lấy được ma trận dữ liệu chuẩn nhất. Không được để sót `NaN` hoặc khoảng trắng do lỗi merge.
- Việc đọc cấu trúc file, dù có lộn xộn đến đâu, phải giải quyết bằng thuật toán quét (loop, heuristic search) thay vì gán thủ công từng index.

## 3. Độ Chính Xác Tuyệt Đối
- Dữ liệu thu thập được phải **Tuyệt đối chính xác** so với bản gốc, không tự suy diễn, không làm tròn sai lệch. Nếu không đọc được, hệ thống phải Raise Exception và dừng lại để báo cáo.
