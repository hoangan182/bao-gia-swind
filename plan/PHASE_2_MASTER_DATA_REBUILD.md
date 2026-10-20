# KẾ HOẠCH NÂNG CẤP MASTER DATA (PHASE 2 - ROOT CAUSE REBUILD)

## 1. Vấn Đề Hiện Tại
Hệ thống Swind bị "mù" trước các hạng mục BOQ phổ biến (Canvas, Van 1 chiều, Tiêu âm, Quạt, Bảo ôn...) do bộ não `master_database_tech.json` được sinh ra từ một script bóc tách dữ liệu không hoàn chỉnh. Nó đã bỏ qua phần lớn các sheet cấu thành giá trong file `BẢNG TÍNH GIÁ SWIND  chuẩn 2026.xls` (gồm 17 sheets).

## 2. Mục Tiêu Tái Cấu Trúc
Tái thiết lập Master Data đảm bảo độ phủ 100% so với file Excel gốc:
1. **Raw Material DB:** Cập nhật đủ Vải bạt chống cháy, Bông Rockwool, Đinh ghim tiêu âm, Bảo ôn, Keo, v.v.
2. **Manufacturable Products List:** Đưa vào Database danh sách "Những sản phẩm xưởng CÓ THỂ tự gia công" (Ống gió, Van 1 chiều, Cửa gió, Khớp nối mềm Canvas, Vách ngăn tiêu âm).
3. **Commercial/Trade DB:** Danh mục các mặt hàng thương mại bắt buộc phải mua ngoài (Quạt, Máy lạnh, PAU, FCU, Bơm).

## 3. Các Bước Triển Khai (Action Plan)

### Bước 1: Viết Agent 00 - The Data Miner
- **Nhiệm vụ:** Đọc file `BẢNG TÍNH GIÁ SWIND  chuẩn 2026.xls` bằng `pandas`.
- **Target Sheets:**
  - `BG VAN ` & `VT van`: Bóc Van 1 chiều, Môtơ, Lò xo, Trục.
  - `BG TIEU AM` & `VT tiêu âm`: Bóc tỷ trọng Bông, Vải thủy tinh, Tôn đục lỗ.
  - `BG canvas, ventcap`: Bóc định mức vải bạt, nẹp tôn.
  - `bảo ôn`: Bóc Superlon, Armaflex, Băng keo.
- **Output:** Ghi đè file `master_database_tech.json` với cấu trúc JSON đa chiều, có phân tầng rõ rệt giữa: Hàng Sản Xuất và Hàng Thương Mại.

### Bước 2: Nâng cấp `SwindBOMEngine`
Dịch ngược các công thức từ các Sheet nói trên thành hàm Python:
- `calculate_canvas_bom(chu_vi, do_dai)`
- `calculate_acoustic_partition_bom(dien_tich, do_day)`
- Tích hợp Van 1 chiều (NRD) vào hàm `calculate_damper_bom`.

### Bước 3: Đấu nối vào Pipeline
- Cập nhật `swind_boq_parser.py` để tra cứu danh mục "Sản phẩm sản xuất được" từ Master Data động, thay vì dùng if-else hardcode `quạt, ống đồng...`.

## 4. Người thực hiện & Timeline
- Multi-Agent AI (Antigravity).
- Execute immediately.
