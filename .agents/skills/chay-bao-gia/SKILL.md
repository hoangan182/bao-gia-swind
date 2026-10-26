---
name: chay-bao-gia
description: Chạy nhanh báo giá dự án Swind từ file BOQ Excel bằng swind_master_runner.py mà không cần đọc lại source code hay viết script đọc lại file Excel xuất ra. Kích hoạt ngay khi người dùng yêu cầu chạy báo giá hoặc tính giá dự án.
---

# Quy Trình Chạy Nhanh Báo Giá Dự Án Swind (Fast-Path Quotation Skill)

Hệ thống báo giá tự động Swind (`src/swind_master_runner.py` và chuỗi `agent_01..08.py`) **đã hoàn chỉnh 100%**.

## 1. Nguyên Tắc Tốc Độ Tối Đa
1. **KHÔNG đọc lại code** (`src/swind_master_runner.py`, `src/agent_01..08.py`) trước khi chạy.
2. **CHẠY NGAY LẬP TỨC** câu lệnh CLI dưới đây với `run_command`.
3. **KHÔNG viết script Python phụ** để đọc lại file `_BAO_GIA.xlsx` sau khi chạy xong, vì `src/swind_master_runner.py` đã in sẵn **BẢNG TỔNG HỢP GIÁ TRỊ BÁO GIÁ DỰ ÁN** và **File Báo Giá Cuối Cùng** ra màn hình console ở định dạng Markdown.
4. **Khi báo cáo cho người dùng:**
   - **Chỉ liệt kê duy nhất File Báo Giá Cuối Cùng** (`<Project_Name>_BAO_GIA.xlsx`), không liệt kê các file thành phần trong thư mục.
   - **Chỉ in Bảng Tổng Hợp Giá Trị**, bỏ Bảng kết quả báo giá chi tiết.

## 2. Câu Lệnh Thực Thi Chuẩn

```bash
./venv/bin/python src/swind_master_runner.py "<đường_dẫn_file_BOQ>" --non-interactive --auto-accept [các_cờ_tùy_chọn]
```

### Các cờ tham số tùy chọn:
- `--non-interactive --auto-accept`: Luôn truyền 2 cờ này khi chạy tự động.
- `--sheets "Sheet1,Sheet2"`: Chỉ chạy các sheet chỉ định (mặc định tự động dò mọi sheet HVAC).
- `--only-cua-van`: Chỉ báo giá Cửa gió & Van gió (loại bỏ Ống gió và Hàng thương mại).
- `--motor-brand <BELIMO|KLB|HONEYWELL>`: Ép hãng động cơ van theo yêu cầu (mặc định `BELIMO`).
- `--mfd-model <1.01|1.02|1.03|1.04|1.05>`: Ép mã đốt van MFD theo yêu cầu (mặc định `1.02`).
- `--dual-options`: Xuất đồng thời 2 phương án Đơn cánh và Đa cánh.
- `--merge-sheets`: Gộp tất cả các sheet vào 1 file dự toán duy nhất.
- `--allow-ei`: Cờ tương thích cho phép áp giá chống cháy EI.
