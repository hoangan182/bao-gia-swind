---
trigger: always_on
priority: highest
description: Fast-path execution protocol for running Swind BOQ quotations without reading source code or writing post-run Excel reader scripts
---

# QUY TẮC CHẠY BÁO GIÁ TỐC ĐỘ CAO (FAST-PATH QUOTATION EXECUTION)

## 1. Nguyên Tắc "Chạy Ngay — Không Đọc Lại Code" (Zero Code-Reading Overhead)
- Hệ thống báo giá tự động Swind (`src/swind_master_runner.py` và chuỗi `agent_01..08.py`) **ĐÃ HOÀN CHỈNH 100%**.
- Khi bắt đầu phiên trò chuyện mới hoặc khi người dùng yêu cầu *"Chạy báo giá dự án..."*, *"Tính giá file..."*, *"Lập báo giá..."*:
  1. **TUYỆT ĐỐI KHÔNG** dùng `read_file` hay `grep` để đọc mã nguồn `src/swind_master_runner.py` hay `src/agent_01..08.py` để "tìm hiểu cấu trúc hệ thống" trước khi chạy (trừ khi người dùng yêu cầu sửa lỗi hoặc thay đổi logic code).
  2. **CHỈ CẦN XÁC ĐỊNH FILE BOQ VÀ CHẠY NGAY LẬP TỨC** câu lệnh CLI dưới đây bằng `run_command`.
  3. **TUYỆT ĐỐI KHÔNG** viết thêm script Python phụ để mở lại file `_BAO_GIA.xlsx` đọc giá sau khi chạy xong! `src/swind_master_runner.py` đã tự động in trực tiếp **BẢNG TỔNG HỢP GIÁ TRỊ BÁO GIÁ DỰ ÁN** (Số dòng, Trước VAT, VAT 8%, Tổng sau VAT 8%) và **File Báo Giá Cuối Cùng** ra màn hình console ở định dạng Markdown.
  4. **QUY TẮC BÁO CÁO KẾT QUẢ CHO NGƯỜI DÙNG (BẮT BUỘC):**
     - **Chỉ liệt kê duy nhất File Báo Giá Cuối Cùng** (`data/projects/<Project_Name>/<Project_Name>_BAO_GIA.xlsx`). Không liệt kê các file báo giá thành phần từng sheet/tháp hay file dự toán nội bộ trung gian (vì đã có sẵn trong thư mục dự án).
     - **Chỉ in Bảng Tổng Hợp Giá Trị Báo Giá**, **BỎ Bảng kết quả báo giá chi tiết** từng mặt hàng.

## 2. Câu Lệnh Thực Thi Chuẩn & Đầy Đủ Tham Số CLI

```bash
./venv/bin/python src/swind_master_runner.py "<đường_dẫn_file_BOQ>" --non-interactive --auto-accept [các_cờ_tùy_chọn]
```
*(Ghi chú: Có thể gọi bằng `./venv/bin/python src/swind_master_runner.py`, `python3 src/swind_master_runner.py`, hoặc `./run` — script tự động chuyển sang `./venv/bin/python`).*

### Danh sách các cờ tham số (CLI Flags):
- `--non-interactive`: **(Bắt buộc khi AI chạy)** Chạy tự động hoàn toàn (Headless mode), không dừng chờ nhập phím.
- `--auto-accept`: **(Bắt buộc khi AI chạy)** Tự động đồng ý các gợi ý phân loại mặt hàng của Agent 02.
- `--sheets "Sheet1,Sheet2"`: Chỉ định danh sách tên Sheet cần xử lý (ngăn cách bằng dấu phẩy). Mặc định: Tự động dò tất cả Sheet kỹ thuật HVAC.
- `--only-cua-van`: Chỉ lọc và báo giá **Cửa gió & Van gió** (`CUA_GIO`, `VAN_GIO`), loại bỏ Ống gió và Hàng thương mại mua ngoài.
- `--motor-brand <BELIMO|KLB|HONEYWELL>`: Chỉ định hãng động cơ van theo yêu cầu (Mặc định: `BELIMO` nếu BOQ không ghi rõ).
- `--mfd-model <1.01|1.02|1.03|1.04|1.05>`: Chỉ định mã đốt van MFD theo yêu cầu:
  - `1.01`: `SWIND-1.01-MFD-EI120` (Belimo BFN24, BCTN 4751)
  - `1.02`: `SWIND-1.02-MFD-EI90` (Belimo FSLF24V, BCTN 4752 — **Mặc định**)
  - `1.03`: `SWIND-1.03-MFD-EI90` (KLB 5Nm, BCTN 4651)
  - `1.04`: `SWIND-1.04-MFD-EI60` (Honeywell MS4609, BCTN 1515)
  - `1.05`: `SWIND-1.05-MFD-EI120` (Belimo BFN24, BCTN 2390)
- `--dual-options`: Xuất đồng thời 2 phương án so sánh van (`BG Đơn Cánh ĐC FSLF 24V` và `BG Đa Cánh BFN 24`). Mặc định: Chỉ xuất 1 bảng chuẩn theo BOQ (`BẢNG BÁO GIÁ TIÊU CHUẨN`).
- `--merge-sheets`: Gộp tất cả các sheet vào 1 file dự toán duy nhất (Mặc định: Tách riêng từng sheet ra từng file độc lập).
- `--allow-ei`: Cờ tương thích cho phép áp giá chống cháy EI (Mặc định Swind tự động nhận diện EI theo BOQ).

## 3. Đường Dẫn File Xuất Chuẩn
- **File báo giá gửi khách hàng (`_BAO_GIA.xlsx`):** `data/projects/<Project_Name>/<Project_Name>_BAO_GIA.xlsx` (hoặc `<Project_Name>_<Sheet_Slug>_BAO_GIA.xlsx` và `<Project_Name>_BAO_GIA_TONG_HOP.xlsx` nếu có nhiều sheet).
- **File dự toán nội bộ 9 sheets (`_ESTIMATION.xlsx`):** `data/projects/<Project_Name>/internal_estimation/`.
