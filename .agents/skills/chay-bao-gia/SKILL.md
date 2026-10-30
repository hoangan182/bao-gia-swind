---
name: chay-bao-gia
description: Chạy nhanh báo giá dự án Swind từ file BOQ Excel bằng swind_master_runner.py mà không cần đọc lại source code hay viết script đọc lại file Excel xuất ra. Kích hoạt ngay khi người dùng yêu cầu chạy báo giá hoặc tính giá dự án.
---

# Quy Trình Chạy Nhanh Báo Giá Dự Án Swind (Fast-Path Quotation Skill)

Hệ thống báo giá tự động Swind (`src/swind_master_runner.py` và chuỗi `agent_01..08.py`) **đã hoàn chỉnh 100%**.

## 1. Nguyên Tắc Tốc Độ Tối Đa
1. **KHÔNG đọc lại code** (`src/swind_master_runner.py`, `src/agent_01..08.py`) trước khi chạy.
2. **CHẠY NGAY LẬP TỨC** câu lệnh CLI dưới đây với `run_command`.
3. **KHÔNG viết script Python phụ** để đọc lại file báo giá sau khi chạy xong, vì `src/swind_master_runner.py` đã in sẵn **BÁO CÁO ĐỘ PHỦ BOQ (`Full-BOQ Coverage Audit`)**, **BẢNG TỔNG HỢP GIÁ TRỊ BÁO GIÁ DỰ ÁN** và **File Báo Giá Cuối Cùng** ra màn hình console ở định dạng Markdown.
4. **Kiểm tra chống sót dòng & kế thừa Title cha (`Full-BOQ Coverage Audit`):**
   - Luôn kiểm tra kết quả `[Agent 01 - Full-BOQ Coverage Audit]` trên console để đảm bảo 100% các dòng Title cha đã truyền thông số (`OBD`, `lưới chắn chim/LCCT`, `lọc G4`, `EI`, `độ dày`...) xuống dòng item con và **0 dòng có khối lượng/kích thước bị bỏ sót** (`⚠️ [CẢNH BÁO SÓT DÒNG]`). Nếu dự án mới phát sinh cấu trúc/từ khóa lạ gây sót dòng, phải xử lý triệt để trước khi trả kết quả.
5. **Khi báo cáo cho người dùng:**
   - **Chỉ liệt kê duy nhất File Báo Giá Cuối Cùng** (`output/<Project_Name>/<Original_File_Name>.xlsx`), không liệt kê các file thành phần trong thư mục.
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
- `--motor-price <số_tiền_VNĐ>`: Rẽ nhánh áp đơn giá gốc động cơ tùy chỉnh riêng cho dự án đang chạy (VD: `--motor-price 2300000`), giữ nguyên Master Data chuẩn.
- `--mfd-model <1.01|1.02|1.03|1.04|1.05>`: Ép mã đốt van MFD theo yêu cầu (mặc định `1.02`).
- `--dual-options`: Xuất đồng thời 2 phương án Đơn cánh và Đa cánh.
- `--merge-sheets`: Gộp tất cả các sheet vào 1 file dự toán duy nhất.
- `--include-canvas`: Báo giá cả Khớp nối mềm / Canvas (Mặc định: Swind **KHÔNG** báo giá canvas).
- `--include-duct`: Cho phép báo giá **Ống gió & phụ kiện ống (`ONG_GIO`)** (Mặc định: Hệ thống **KHÔNG** báo giá ống gió, chỉ báo khi User yêu cầu rõ). `--duct-formula og_mb|both` tự động bật cờ này.
- `--strict`: Không xuất file báo giá nếu còn lỗi chặn (dòng có KL chưa có giá, sheet bóc tách lỗi, QA_REJECTED). Mặc định: vẫn xuất file nhưng in `⛔ BẢN NHÁP — CHƯA HOÀN CHỈNH` và trả mã thoát `2`.
- `--override "<Dòng>:k=v,...;..."`: Ghi đè nhanh theo dòng BOQ (`w,h,d,l,thickness,qty,ref_price,skip`). BOQ nhiều sheet bắt buộc ghi tên sheet: `--override "Tên Sheet!7:w=600,h=600"`.
- `--duct-formula <mpq|og_mb|both>`: Bộ công thức ống gió (`mpq` mặc định = BG PKV chuẩn; `og_mb` = diện tích m² theo ÔG MB; `both` = xuất cả 2, bản m² có hậu tố `_THEO_M2_OG_MB`).
