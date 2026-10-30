# GHI CHÚ CÁC GIẢ ĐỊNH KỸ THUẬT (SYSTEM ASSUMPTIONS - AGENT 00..09)

Tài liệu này lưu trữ toàn bộ các quy tắc kỹ thuật mà Hệ thống Multi-Agent Swind (`Agent 00` $\to$ `Agent 09`) sử dụng để tự động bóc tách thành phần vật tư và lập báo giá (mặc định 1 phương án theo BOQ; 2 phương án đơn/đa cánh khi có `--dual-options`).

## 1. Hệ Thống Van Chặn Lửa & Van Động Cơ (`Agent 05` - `src/agent_05_bom_damper.py`)
- **Chuẩn hóa theo Sheet `BG van EI` & `BG VAN CU` (Bảng tính giá chuẩn 2026):**
  - Tự động chia modul khi kích thước vượt khổ tiêu chuẩn và thu côn 2 đầu về tối thiểu `150x150mm` đối với van kích thước nhỏ.
- **Phương án Báo giá Mặc định vs Báo giá So sánh Đơn/Đa cánh (`Agent 07`):**
  - **Mặc định:** Báo giá chuẩn trực tiếp theo đúng BOQ khách hàng (`00_BANG_CHAO_GIA`), sử dụng đúng vật tư, chủng loại van, động cơ chỉ định.
  - **Khi có yêu cầu:** Mới xuất thêm 2 Sheet so sánh phương án:
    1. **`BG Đơn Cánh ĐC FSLF 24V`:** Phương án van `MFD` đơn cánh gắn động cơ đóng mở nhanh `BELIMO FSLF24V` ($3.5\text{Nm}$, chuẩn EI90).
    2. **`BG Đa Cánh BFN 24`:** Phương án van `MFD` đa cánh gắn động cơ `BELIMO BFN 24` ($9\text{Nm}$, chuẩn EI120).
- **Phân tách File Báo giá theo từng Sheet BOQ:**
  - Đối với dự án có nhiều sheet (ví dụ CAND có 4 sheet), mặc định tách riêng từng sheet thành 1 file báo giá độc lập, không gộp chung vào 1 file duy nhất.
- **Tách biệt Chi phí Động cơ Thương mại (`00_TONG_HOP_BAO_GIA`):**
  - Chi phí động cơ (`ĐỘNG_CƠ_VÀ_CẢM_BIẾN`) được tách riêng bằng công thức `SUMIFS`, không bị cộng chồng 25% nhân công xưởng, 10% chi phí xưởng và 18% lợi nhuận gộp của phần cơ khí chế tạo.

## 2. Hệ Thống Cửa Gió & Miệng Gió Nhôm Định Hình (`Agent 06` - `src/agent_06_bom_diffuser.py`)
- **Chuẩn hóa theo 6 bảng con của Sheet `BG Cửa `:**
  - `SWL` (`WL+N`): Louver nan Z ngoài trời kèm lưới chắn côn trùng Inox 304 (`LCCT`).
  - `SEEG` (`ECG` / `ECG+O`): Cửa nan sọt trứng $12.7\times12.7$.
  - `SLB` (`SLB` / `SLB+O`): Cửa gió Linear nan T (hỗ trợ sơn đen lớp 2 và hệ số nối khung khổ dài $\ge 5000\text{mm}$).
  - `SCD` (`SD` / `SD+O`): Cửa khuếch tán vuông (cổ lùi $150\text{mm}$).
  - `SAG/DAG` (`SDG` / `SDG+O`): Cửa nan bầu dục 1 lớp / 2 lớp.
  - `SOBD`: Van OBD nhôm gắn liền cửa tính theo kích thước cổ $D\times E$.

## 3. Hệ Thống Ống Gió, Khớp Nối Mềm & Tiêu Âm (`Agent 04` - `src/agent_04_bom_duct.py`)
- **Ống gió thẳng:** Hao hụt phôi **5%** (`1.05`), bù mép bích TDF & mí ghép Pittsburgh `1.08`.
- **Phụ kiện ống gió / Box tôn:** Hao hụt phôi **15%** (`1.15`).
- **Hộp/Vách tiêu âm:** Cấu tạo 3 lớp (Vỏ tôn, Tôn soi lỗ `0.38mm`, Bông Rockwool `50kg/m3` bọc vải thủy tinh).

## 4. Kiểm Toán Kích Thước Lẻ & Học Giá Thương Mại (`Agent 03` & `Agent 09`)
- **`Agent 03` (`src/agent_03_input_auditor.py`):** Tự động cảnh báo các dòng BOQ có kích thước lẻ bất thường nghi gõ thiếu số `0` (ví dụ `110x350` thay vì `1100x350`) trong `INPUT_AUDIT_REPORT.json`.
- **`Agent 09` (`src/agent_09_price_learner.py`):** Mọi vật tư mới phát sinh có `Đơn giá = 0` tại Sheet `06_BANG_GIA_VAT_TU_AP_DUNG` sau khi được Kỹ sư điền giá sẽ được học tự động bằng lệnh:
  ```bash
  ./venv/bin/python3 src/agent_09_price_learner.py "<đường_dẫn_file_excel>"
  ```

## 5. Quy Tắc Động Cơ KLB / VIWECO (Dự Án FOXCOM & Các Dự Án Tương Đương)
- **Tổng quan & Xuất xứ:**
  - Nhãn hiệu: `KLB` hoặc `KLB / VIWECO` (mã Master Data: `MAT-ACTUATOR-KLB-V6006FS500S`, `MAT-ACTUATOR-SWIND-VIWECO`).
  - Nguồn điện: `24VDC` (DC 24V), cơ chế hoạt động `ON/OFF`.
- **Van Ngăn Cháy MFD (Model `SWIND-1.03- MFD-EI90`):**
  - Gắn động cơ `ON-OFF 5Nm, Hãng KLB` (BCTN số `4651/VLXD-TBMT`).
  - Giới hạn 1 modul tối đa: `1500x800mm`. Vượt quá kích thước này phải chia thành 2 modul gắn 2 động cơ KLB 5Nm.
- **Van Gió Điều Khiển Điện MD (Model `MD`):**
  - Gắn động cơ `KLB/VIWECO 24V - 10N` (10Nm).
  - Phân chia Modul & số lượng động cơ:
    - `1 Modul` (1 động cơ 10Nm): $W \le 1300\text{mm}$ và $H \le 1500\text{mm}$.
    - `2 Modul` (2 động cơ 10Nm): $1300 < W \le 2600\text{mm}$ (với $H \le 1300\text{mm}$), hoặc $W=3500, H=500$.
    - `4 Modul` (4 động cơ 10Nm): $W \ge 2000\text{mm}$ và $H > 1300\text{mm}$, hoặc $W \ge 4000\text{mm}$ và $H \le 1500\text{mm}$.
    - `8 Modul` (8 động cơ 10Nm): Cả $W \ge 4000\text{mm}$ VÀ $H \ge 1500\text{mm}$ (như $4000\times 2000$, $4700\times 1500$).

## 6. Cấu Tạo Cơ Khí Van Ngăn Cháy PCCC (Theo 06 Hồ Sơ Đốt VIBM - HSKT)
- **Căn cứ 06 BCTN của Viện Vật liệu Xây dựng (VIBM) theo ISO 21925-1:2018:**
  1. `SWIND-1.01-MFD-EI120`: Khổ $1500\times 800\times 200$, Đơn cánh, lõi KHS.HF.M20 (20mm), ĐC Belimo BFN 9Nm.
  2. `SWIND-1.02-MFD-EI90`: Khổ $1500\times 800\times 200$, Đơn cánh, lõi KHS.HF.M16 (16mm), ĐC Belimo FSLF 3.5/9Nm.
  3. `SWIND-1.03-MFD-EI90`: Khổ $1500\times 800\times 200$, Đơn cánh, lõi KHS.HF.M16 (16mm), ĐC KLB CF-5NF 5Nm.
  4. `SWIND-1.04-MFD-EI60`: Khổ $1700\times 1000\times 200$, Đa cánh đa ô (6 ô: 2 khoang $\times$ 3 tầng), vách ngăn hộp kẽm 20x20x1.4 ốp 2 mặt FA10 (40mm), lõi KHS.HF.M16 (16mm), ĐC Honeywell MS4609 9Nm.
  5. `SWIND-1.05-MFD-EI120`: Khổ $1700\times 1000\times 200$, Đa cánh (2 tầng cánh lớn), lõi KHS.HF.M20 (20mm), ĐC Belimo BFN 9Nm.
  6. `SWIND-2.01-E-FD-EI120`: Khổ $1500\times 800\times 200$, Đơn cánh, Cầu chì nhiệt 72-74°C + Hộp lò xo kéo sợi 3.5mm, lõi KHS.HF.M20 (20mm).
- **Cấu tạo chi tiết phục vụ tính BOM & Định giá:**
  - **Thân vỏ van:** Tôn mạ kẽm dày `1.15mm`, bích liền thân TDC cao `35mm`, chiều dài $L=200\text{mm}$, ke góc $31\times 91\times 1.15\text{mm}$. Thân van được bọc `2 lớp tấm chống cháy KHS.FA10 dày 10mm` (1 lớp mặt trong thân, 1 lớp mặt ngoài thân).
  - **Lá cánh van (Sandwich 5 lớp):** 
    - Lớp 1: KHS.FA10 dày 10mm (980 kg/m3).
    - Lớp 2: Tôn mạ kẽm dày 1.15mm.
    - Lớp 3 (Lõi): Tấm cách nhiệt KHS.HF.M16 dày 16mm (EI60/EI90) hoặc KHS.HF.M20 dày 20mm (EI120).
    - Lớp 4: Tôn mạ kẽm dày 1.15mm.
    - Lớp 5: KHS.FA10 dày 10mm (980 kg/m3).
    - 4 cạnh mép cánh bọc keo trương nở Hilti FS-ONE MAX. Bu lông xuyên sandwich M6.
  - **Trục & Bạc:** Trục thép mạ kẽm vuông $10\times 10\text{mm}$ (đầu ra động cơ dài 120mm), Bạc đồng ngoài Ø23, trong Ø17.5.
  - **Vách ngăn chia ô (Van khổ $1700\times 1000$):** Hộp kẽm $20\times 20\times 1.4\text{mm}$ + 2 mặt ốp tấm KHS.FA10 dày 10mm (tổng vách dày 40mm) áp dụng cho mẫu đa ô 1.04. Riêng mẫu 1.05 áp dụng Phương án A (2 cánh suốt dài 1700mm, không dùng vách đứng chia đôi).
  - **Hộp che động cơ:** Tôn dày 0.95mm + tấm KHS.FA10 dày 10mm.
  - **Quy tắc phân chia cánh (Blade division):** Giữ nguyên công thức chuẩn của hệ thống: Đơn cánh khi $H \le 250\text{mm}$ hoặc khi có yêu cầu cụ thể (`single_fslf24`); Đa cánh tính theo hệ số $(H - 5) / 149$.

## 7. Phạm Vi Báo Giá Dự Án CAND (Cửa Gió & Van Gió)
- **Căn cứ yêu cầu thực tế:** File BOQ gốc khách hàng gửi (`Xin giá cửa dự án CAND.xlsx`) chứa trọn gói cơ điện lạnh MEP của cả tòa nhà (gồm máy lạnh Multi, VRV, ống đồng hàng chục km, quạt, ống nước uPVC... trị giá > 200 tỷ VNĐ).
- **Quy tắc phạm vi:** Đối với dự án CAND (và các dự án yêu cầu chỉ báo giá Cửa gió + Van gió qua cờ `--only-cua-van`):
  - **Chỉ chào giá 2 phân nhóm sản xuất:** `CUA_GIO` (Cửa gió, Miệng gió, Louver, Nan Z, LCCT...) và `VAN_GIO` (Van MFD, FD, VCD, NRD, MD, PRD...).
  - **Không chào giá:** `ONG_GIO` (Ống gió tôn, Ống gió chống cháy EI...) và `THUONG_MAI`/`KHAC` (Máy lạnh Multi, VRV, Ống đồng, Cách nhiệt ống gas, Quạt, Tủ điện, Cáp điện...).
  - **Quy tắc bảo toàn 100% dữ liệu gốc BOQ khách hàng (`00_BANG_CHAO_GIA` & File Thống Nhất):** Tuyệt đối KHÔNG xóa, KHÔNG ghi đè giá trị = 0, KHÔNG xóa công thức và KHÔNG thay đổi số liệu của các dòng nằm ngoài phạm vi chào giá của Swind (Quạt thông gió, Máy lạnh VRV/Multi, Ống đồng, Ống tôn, Chi phí khác...). Toàn bộ công thức, khối lượng và đơn giá của khách hàng được giữ nguyên vẹn 100%.
  - **Quy tắc mã hiệu van MFD động cơ KLB:** Khi dự án yêu cầu động cơ KLB, mã hiệu chuẩn bắt buộc là `SWIND-1.03-MFD-EI90` (sản xuất theo BCTN số 4651/VLXD-TBMT), không được gán nhầm sang `SWIND-1.02-MFD-EI90` (vốn là mã van sử dụng động cơ Belimo FSLF theo BCTN số 4752/VLXD-TBMT).

## 8. Kiến Trúc Xuất File Báo Giá Chuẩn BOQ Khách Hàng (Customer-Facing BOQ)
- **Cơ chế tách file:** Mỗi Sheet kỹ thuật trong file BOQ khách hàng gửi (`Xin giá cửa dự án CAND.xlsx`) được xuất thành **1 file Excel báo giá độc lập**:
  - `CAND_TANG_AP_HK_A1_2_BAO_GIA.xlsx` (Sheet: `Tăng áp HK A1,2`)
  - `CAND_TANG_AP_HK_A3_BAO_GIA.xlsx` (Sheet: `Tang áp HK A3`)
  - `CAND_DHKK_A3_BAO_GIA.xlsx` (Sheet: `DHKK A3`)
  - `CAND_DHKK_TGIO_A3_BAO_GIA.xlsx` (Sheet: ` DHKK tgio A3`)
- **Nguyên tắc cấu trúc file gửi khách:**
  - **Giữ nguyên tên file gốc, gồm Sheet BOQ gốc của khách + Sheet `BG` (Bảng chào giá Swind) ở cuối:** Giữ nguyên vẹn 100% biểu mẫu, font chữ, độ rộng cột, hàng tiêu đề và tên sheet của khách hàng. Không chèn thêm các Sheet tính toán nội bộ (`01_BOC_TACH_...`, `Sheet bìa`).
  - **Bảo toàn 100% dữ liệu ngoài phạm vi:** Tất cả các hạng mục Quạt thông gió, Máy lạnh VRV/Multi, Ống gió tôn, Ống nước ngưng, Ống đồng, Chi phí khác... được giữ nguyên vẹn 100% (công thức, số lượng, nhãn hiệu). Các công thức tham chiếu chéo giữa các sheet (như `'DHKK A3'!K8`) được tự động nội suy giá trị để tránh phát sinh lỗi `#REF!` khi mở file độc lập.
  - **Áp giá Cửa gió & Van gió:**
    - Cột 4 (Nhãn hiệu): `SWIND / VIWECO (KLB)` cho Van MFD, `SWIND` cho các Cửa/Van khác.
    - Cột 11 (Đơn giá Vật tư): Giá bán vật tư tính toán (định dạng `#,##0`).
    - Cột 12 (Đơn giá Nhân công): Giá bán nhân công tính toán (định dạng `#,##0`).
    - Cột 13 (VAT Vật tư): `=K{r}*8%`.
    - Cột 14 (VAT Nhân công): `=L{r}*8%`.
    - Cột 15 (Thành tiền Vật tư): `=(K{r}+M{r})*F{r}`.
    - Cột 16 (Thành tiền Nhân công): `=(L{r}+N{r})*F{r}`.
    - Cột 17 (Ghi chú): Model chuẩn `SWIND-1.03-MFD-EI90`, BCTN số `4651/VLXD-TBMT`, Động cơ KLB `V6006FS500S 24V - 5Nm`.
    - Dòng tổng cộng chân trang: `=SUBTOTAL(9, O4:O{r-1})` và `=SUBTOTAL(9, P4:P{r-1})`.
- **Lưu trữ hồ sơ nội bộ:**
  - Toàn bộ file dự toán bóc tách chi tiết (Agent 04, 05, 06, 07) và biên bản kiểm toán độc lập 3 tầng (Agent 08 - QA Checker) được lưu trữ chuyên biệt tại thư mục `data/projects/{PROJECT}/internal_estimation/` để phục vụ công tác kiểm toán kỹ thuật nội bộ, không gửi ra ngoài khách hàng.


