# KẾ HOẠCH TRIỂN KHAI VẤN ĐỀ 4: TÁCH BẠCH ĐỊNH MỨC TÀI CHÍNH & GIÁ VỐN (FINANCIAL POLICY ENGINE)

## 1. MỤC TIÊU VÀ BỐI CẢNH
Hiện tại, trong `swind_excel_builder.py`, toàn bộ các dòng sản phẩm trong Bảng Tổng hợp báo giá (Sheet 00) đều bị áp cứng cùng một công thức tài chính:
- Chi phí nhân công: Cố định `=K*0.25` (25% giá trị vật tư).
- Chi phí xưởng & hao hụt: Cố định `=K*0.10` (10% giá trị vật tư).
- Biên lợi nhuận (Margin): Cố định `0.18` (18%).

**Bất hợp lý lớn trong thực tế thương thầu:**
- Đối với **Hàng sản xuất cơ khí** (Ống gió, Van gió, Cửa gió, Tiêu âm): Xưởng phải tốn nhân công chấn bích, bắn mí, máy chạy TDF và chi phí mặt bằng nhà xưởng, nên tỷ lệ 25% nhân công + 10% xưởng là hợp lý.
- Đối với **Hàng thương mại mua ngoài** (Quạt thông gió, Động cơ điều khiển van, Ống gió mềm, Lưới bảo vệ): Doanh nghiệp mua đi bán lại nguyên chiếc, hoàn toàn **không tốn 25% nhân công xưởng**.
- Việc đánh đồng 25% nhân công + 10% xưởng lên hàng thương mại khiến đơn giá dự thầu của các thiết bị đắt tiền (như quạt vài chục triệu) bị đội thêm tới 35% chi phí ảo, dẫn đến tổng giá gói thầu quá cao và lập tức bị trượt thầu.

Mục tiêu của Vấn đề 4:
1. Xây dựng file cấu hình chính sách tài chính: `data/master_data/financial_policy.json`.
2. Phân tách rõ ràng 2 nhóm: **Hàng Sản Xuất (Manufacturing)** vs **Hàng Thương Mại (Commercial)**.
3. Cập nhật `swind_excel_builder.py`, `swind_master_runner.py` và `run_estimation_pipeline.py` để công thức tài chính linh hoạt theo từng nhóm mặt hàng.

---

## 2. THIẾT KẾ CƠ CHẾ CHÍNH SÁCH TÀI CHÍNH

### 2.1. Cấu hình `data/master_data/financial_policy.json`
- **Nhóm HÀNG SẢN XUẤT (`ONG_GIO`, `CUA_GIO`, `VAN_GIO`, `CANVAS`, `TIEU_AM`):**
  - `labor_rate`: `0.25` (25% nhân công gia công cơ khí).
  - `overhead_rate`: `0.10` (10% chi phí xưởng, điện năng, khấu hao máy móc).
  - `margin`: `0.18` (18% biên lợi nhuận sản xuất).
- **Nhóm HÀNG THƯƠNG MẠI (`THUONG_MAI`, `ONG_MEM`, `KHAC`):**
  - `labor_rate`: `0.00` (0% nhân công sản xuất).
  - `overhead_rate`: `0.02` (2% chi phí lưu kho, bốc xếp, vận chuyển nội bộ).
  - `margin`: `0.10` (10% biên lợi nhuận thương mại).

### 2.2. Áp dụng vào Sheet Tổng hợp (00_TONG_HOP_BAO_GIA)
- Cột L (Nhân công): `=K{row} * {labor_rate}`
- Cột M (Chi phí xưởng): `=K{row} * {overhead_rate}`
- Cột P (Tỷ lệ Margin): `{margin}`
- Cột N (Tổng giá vốn): `=K{row} + L{row} + M{row}`
- Cột Q (Đơn giá bán): `=O{row} * (1 + P{row})`

---

## 3. CÁC BƯỚC THỰC THI CHI TIẾT

- [x] **Bước 4.1:** Tạo file cấu hình chính sách tài chính `data/master_data/financial_policy.json`.
- [x] **Bước 4.2:** Nâng cấp `SwindExcelBuilder.add_boq_summary_row` trong `src/swind_excel_builder.py` để nhận tham số `labor_rate`, `overhead_rate`, `margin`.
- [x] **Bước 4.3:** Cập nhật hàm nạp cấu hình và áp dụng chính sách tài chính trong:
  - `src/swind_master_runner.py`
  - `src/run_estimation_pipeline.py`
- [x] **Bước 4.4:** Chạy kiểm thử End-to-End với Master Runner trên `Haus_Dalat_BOQ_MEP (NCC).xlsx`.
- [x] **Bước 4.5:** Đánh giá bảng giá chào thầu:
  - Hàng thương mại: Nhân công `=K*0.00` (0%), Chi phí xưởng `=K*0.02` (2%), Margin `10%`. Đơn giá chào thầu hoàn toàn sát thực tế, không còn bị đội 35% chi phí ảo.
  - Hàng sản xuất: Nhân công `=K*0.25` (25%), Chi phí xưởng `=K*0.10` (10%), Margin `18%`. Cấp chứng chỉ QA_PASSED 100%.
