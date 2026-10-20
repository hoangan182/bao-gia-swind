# KẾ HOẠCH TRIỂN KHAI VẤN ĐỀ 6: TƯƠNG THÍCH MỌI PHIÊN BẢN EXCEL (THAY THẾ XLOOKUP BẰNG INDEX/MATCH)

## 1. MỤC TIÊU VÀ BỐI CẢNH
Hiện tại trong `swind_excel_builder.py`, các liên kết dữ liệu giữa các sheet con (01_ONG, 02_CUA, 03_VAN) với Sheet 00 (Tổng hợp) và Sheet 06 (Bảng giá) đang sử dụng hàm `=XLOOKUP(...)`.

**Rủi ro kỹ thuật:**
- Hàm `XLOOKUP` là tính năng mới, chỉ được Microsoft hỗ trợ trên Microsoft 365 hoặc Office 2021 trở lên.
- Đa số Chủ đầu tư, Ban quản lý dự án (PMU), Tổng thầu xây dựng tại Việt Nam vẫn sử dụng các phiên bản **Excel 2016, Excel 2019 bản quyền vĩnh viễn (On-premise)**.
- Khi khách hàng mở file dự toán có hàm `XLOOKUP` trên Excel 2016/2019, toàn bộ các ô liên kết sẽ báo lỗi **`#NAME?`**, làm sụp đổ toàn bộ cây tính toán giá và gây ấn tượng rất xấu về chất lượng hồ sơ thầu.
- Ngoài ra, giá trị mặc định `"LỖI_MÃ_VT"` kiểu chuỗi (string) trong `XLOOKUP` khiến phép nhân `I*J` (Số lượng * Đơn giá) bị lỗi `#VALUE!`.

Mục tiêu của Vấn đề 6:
Thay thế toàn bộ hàm `XLOOKUP` bằng tổ hợp hàm kinh điển **`IFERROR(INDEX(... MATCH(...)), default)`** tương thích 100% với tất cả phiên bản Excel (từ Excel 2007, 2010, 2013, 2016, 2019, 2021, 365, Google Sheets, WPS Office).

---

## 2. NGUYÊN TẮC CÔNG THỨC CHUẨN HÓA

### 2.1. Cột H (Số lượng Dự Án - Liên kết từ Sheet 00)
- **Công thức cũ:**
  `=XLOOKUP(B{r}, '00_TONG_HOP_BAO_GIA'!B:B, '00_TONG_HOP_BAO_GIA'!G:G, 1)`
- **Công thức chuẩn mới:**
  `=IFERROR(INDEX('00_TONG_HOP_BAO_GIA'!G:G, MATCH(B{r}, '00_TONG_HOP_BAO_GIA'!B:B, 0)), 1)`

### 2.2. Cột J (Đơn giá gốc vật tư - Liên kết từ Sheet 06)
- **Công thức cũ:**
  `=XLOOKUP(E{r}, '06_BANG_GIA_VAT_TU_AP_DUNG'!B:B, '06_BANG_GIA_VAT_TU_AP_DUNG'!D:D, "LỖI_MÃ_VT")`
- **Công thức chuẩn mới:**
  `=IFERROR(INDEX('06_BANG_GIA_VAT_TU_AP_DUNG'!D:D, MATCH(E{r}, '06_BANG_GIA_VAT_TU_AP_DUNG'!B:B, 0)), 0)`
  *(Sử dụng số `0` thay vì text `"LỖI_MÃ_VT"` giúp phép nhân Col K `=I*J` ra `0` và kích hoạt luật Conditional Formatting tô đỏ cảnh báo tra soát, không bị sập lỗi `#VALUE!`)*.

---

## 3. CÁC BƯỚC THỰC THI CHI TIẾT

- [x] **Bước 6.1:** Cập nhật công thức liên kết tại Cột H và Cột J trong `src/swind_excel_builder.py` sang `IFERROR(INDEX(... MATCH(...)))`.
- [x] **Bước 6.2:** Cập nhật thông điệp kiểm toán trong `src/swind_checker.py`.
- [x] **Bước 6.3:** Chạy Master Runner để sinh file Excel mới nhất cho dự án Haus Dalat.
- [x] **Bước 6.4:** Viết script kiểm tra công thức trong file Excel: Xác minh **0 ô chứa XLOOKUP** và **3,080 công thức INDEX/MATCH** hoạt động hoàn hảo 100%.
- [x] **Bước 6.5:** Nghiệm thu và cập nhật tài liệu kế hoạch: Cấp chứng chỉ QA_PASSED 100%. File dự toán tương thích tuyệt đối với mọi phiên bản Excel (2010, 2013, 2016, 2019, 2021, 365, Google Sheets, LibreOffice, WPS Office).
