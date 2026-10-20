# KẾ HOẠCH TRIỂN KHAI VẤN ĐỀ 2: CHUẨN HÓA THỨ NGUYÊN BÓC TÁCH BOM ỐNG GIÓ (UNIT NORMALIZATION)

## 1. MỤC TIÊU VÀ BỐI CẢNH
Trong dự toán cơ điện (HVAC), ống gió được chào thầu theo nhiều đơn vị tính (ĐVT) khác nhau:
- **ĐVT `m²` (Mét vuông bề mặt):** Chiếm đa số (>80% khối lượng hồ sơ thầu, ví dụ 2633.4 m² tôn 0.75mm trong dự án Haus Dalat).
- **ĐVT `m` / `md` (Mét dài tuyến ống):** Cho các tuyến ống nhánh, máng tôn, ống hộp.
- **ĐVT `cái` / `đoạn` / `bộ`:** Cho các ống gió gia công đơn chiếc theo quy cách cố định (W x H x L).
- **ĐVT `lô`:** Cho vật tư phụ, phụ kiện liên kết trọn gói.

**Lỗi nghiêm trọng hiện tại:**
Hàm `calculate_duct_bom` trong `swind_bom_engine.py` luôn tính toán trọng lượng cho **1 đoạn ống đơn lẻ dài 1.12m** (~12–15 kg/cái). Khi liên kết vào Excel:
`Tổng nhu cầu tôn (kg) = Định mức 1 SP (kg) * Số lượng BOQ (m²)`
Hệ thống đã ngộ nhận 2633.4 m² như thể là 2633.4 cái ống 1.12m, khiến khối lượng tôn cuộn bị nhân đội lên **gần gấp 2.4 lần** so với định mức thực tế!

Mục tiêu của Vấn đề 2 là thiết kế lại cơ chế bóc tách BOM ống gió thích ứng đa thứ nguyên, đảm bảo tính toán khối lượng phôi tôn chính xác 100% theo tiêu chuẩn chế tạo cơ điện.

---

## 2. NGUYÊN TẮC TÍNH TOÁN THEO THỨ NGUYÊN (ENGINEERING LOGIC)

### 2.1. ĐVT là `m²` (Mét vuông)
- **Định mức (Col G):** Trọng lượng tôn phôi cần thiết để làm ra **1 m² ống gió thành phẩm**.
- **Công thức:**
  $$\text{Định mức (kg/m²)} = 1.0 \text{ m²} \times (7.85 \times \text{Độ dày mm}) \times K_{\text{phôi}} \times K_{\text{hao hụt}}$$
  Trong đó:
  - $K_{\text{phôi}} = 1.08$: Hệ số diện tích phôi bù mép mí Pittsburgh (30mm) và bích TDF (35mm x 2).
  - $K_{\text{hao hụt}} = 1.05$: Hệ số hao hụt cắt gọt đầu mẩu tôn cuộn.
  - Ví dụ tôn 0.75mm: $1.0 \times (7.85 \times 0.75) \times 1.08 \times 1.05 \approx 6.674\text{ kg/m²}$.
- **Tổng nhu cầu trong Excel:** $\text{Định mức} \times \text{Số lượng } m²$.

### 2.2. ĐVT là `m` / `md` (Mét dài)
- **Định mức (Col G):** Trọng lượng tôn trên **1 mét dài**.
- **Công thức:**
  $$\text{Chu vi ống (m)} = \frac{2 \times (W + H) + 30}{1000}$$
  $$\text{Định mức (kg/m)} = \text{Chu vi phôi} \times 1.0\text{ m} \times (7.85 \times \text{Độ dày}) \times 1.05$$
  *(Nếu $W, H$ chưa rõ trong BOQ, lấy kích thước tương đương chuẩn).*

### 2.3. ĐVT là `cái` / `đoạn` (Piece)
- **Định mức (Col G):** Trọng lượng tôn cho **1 cây ống hoàn chỉnh dài L mm**.
- **Công thức:**
  $$\text{Diện tích phôi} = \frac{2 \times (W + H) + 30}{1000} \times \frac{L + 70}{1000}$$
  $$\text{Định mức (kg/cái)} = \text{Diện tích phôi} \times (7.85 \times \text{Độ dày}) \times K_{\text{hao hụt}}$$

### 2.4. ĐVT là `lô` (Lump sum)
- Chuyển thành cấu kiện trọn gói, số lượng 1.0 Lô, không ép buộc bóc tách diện tích tôn 500x500.

---

## 3. CÁC BƯỚC THỰC THI CHI TIẾT

- [x] **Bước 2.1:** Nâng cấp `SwindBOQParser` (trong `src/swind_boq_parser.py`):
  - Bổ sung Regex trích xuất độ dày (`thickness`) tự động từ tên sản phẩm (ví dụ: "Tole 0.75mm", "tôn 0.58mm", "zam 1.5mm") khi cột độ dày trong Excel trống hoặc mặc định.
- [x] **Bước 2.2:** Nâng cấp `SwindBOMEngine.calculate_duct_bom` (trong `src/swind_bom_engine.py`):
  - Hỗ trợ tham số `unit`, `specified_thickness`.
  - Phân nhánh tính toán định mức chuẩn xác theo 4 trường hợp thứ nguyên (`m²`, `m`, `cái`, `lô`).
- [x] **Bước 2.3:** Cập nhật `src/swind_master_runner.py` và `src/run_estimation_pipeline.py`:
  - Truyền `unit=unit` và `specified_thickness=thk` vào `calculate_duct_bom`.
- [x] **Bước 2.4:** Chạy kiểm thử End-to-End với `Haus_Dalat_BOQ_MEP (NCC).xlsx`.
- [x] **Bước 2.5:** Đánh giá kết quả kiểm thử:
  - 24 dòng ống gió `m²` tính chuẩn xác: Tôn 0.75mm định mức 6.68 kg/m², Tôn 0.95mm định mức 8.46 kg/m², Tôn 1.15mm định mức 10.24 kg/m².
  - 15 dòng máng tôn zam `m` (mét dài) tính chuẩn xác theo chu vi thực tế mặt cắt (từ 14.95 kg/m đến 51.99 kg/m).
  - Loại bỏ hoàn toàn lỗi nhân đội 2.4 lần khối lượng tôn. Chứng chỉ QA_PASSED 100%.
