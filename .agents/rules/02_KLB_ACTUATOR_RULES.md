---
trigger: always_on
priority: high
description: Rules for KLB / Viweco Actuators (MFD 1.03 5Nm and MD 10Nm Module Splitting)
---

# QUY TẮC ĐỘNG CƠ KLB / VIWECO (FOXCOM & CÁC DỰ ÁN TƯƠNG ĐƯƠNG)
> Tài liệu chuẩn hóa kiến thức trích xuất từ file báo giá chuẩn: `BG1_SLAND-KDVN_NM FOXCOM BG GD4_25052026.xlsx`

---

## 1. TỔNG QUAN VỀ ĐỘNG CƠ KLB / VIWECO

- **Nhãn hiệu**: **KLB** (hoặc **KLB / VIWECO**).
- **Mã vật tư trong Master Data Swind**:
  - `MAT-ACTUATOR-KLB-V6006FS500S`: `Động cơ chặn lửa ON/OFF KLB (Swin V6006FS500S EI90)`
  - `MAT-ACTUATOR-SWIND-VIWECO`: `Động cơ chặn lửa ON/OFF Swind (Viweco V6006FS500S)`
- **Điện áp hoạt động**: **DC 24V (24VDC)**.
- **Phương thức đóng/mở**: **ON/OFF** (Mở/ngắt điện 2 vị trí).
- **Phạm vi áp dụng**: Áp dụng cho các dự án yêu cầu xuất xứ động cơ KLB / Viweco (như dự án Foxcom giai đoạn 4) thay thế cho động cơ Belimo (Thụy Sỹ).

---

## 2. QUY CÁCH KỸ THUẬT & PHÂN LOẠI THEO LOẠI VAN

### A. Van Ngăn Cháy Chặn Lửa MFD (Motorized Fire Damper)
- **Model chuẩn Swind**: **`SWIND-1.03- MFD-EI90`**
- **Cơ chế cánh**: Cánh đơn (1 lá / Single blade).
- **Tiêu chuẩn kiểm định PCCC**: Sản xuất theo **BCTN số 4651/VLXD-TBMT** (Đốt đạt tiêu chuẩn EI90/EI45).
- **Quy cách động cơ**:
  - Lực xoắn: **5Nm** (Ghi chú: `Gắn kèm động cơ ON-OFF 5Nm, Hãng KLB`).
  - Điện áp: DC 24V.
- **Thân vỏ**: Chiều dài $L = 200$ mm, độ dày tôn $1.15$ mm, 2 đầu bích TDC.
- **Quy tắc chia Modul MFD 1.03**:
  - Kích thước tối đa của 1 modul tiêu chuẩn: **$1500 \times 800$ mm**.
  - **1 Modul (1 động cơ KLB 5Nm)**: $W \le 1500$ mm VÀ $H \le 800$ mm.
    *(Ví dụ thực tế: $700 \times 300$, $1000 \times 350$, $1200 \times 300$, $1200 \times 400$, $1500 \times 300$, $1500 \times 350$)*.
  - **2 Modul (2 động cơ KLB 5Nm)**: Khi $W > 1500$ mm HOẶC $H > 800$ mm.
    *(Ví dụ thực tế: $2000 \times 350$, $2000 \times 400$, $1800 \times 400$, $1050 \times 1200$)*.
- **Mẫu ghi chú báo giá chuẩn**:
  `- Van ngăn cháy động cơ - Tiêu chuẩn EI 90`
  `- 2 đầu bích TDC - Gắn kèm động cơ ON-OFF 5Nm, Hãng KLB`
  `- Sản xuất theo BCTN số 4651/VLXD-TBMT`

---

### B. Van Gió Điều Khiển Điện MD (Motorized Damper)
- **Model chuẩn Swind**: **`MD`**
- **Quy cách động cơ**:
  - Lực xoắn: **10Nm** (Ghi chú: `động cơ KLB/VIWECO 24V -10N`). Lực xoắn 10Nm đảm bảo tải đóng mở cho các van gió kích thước lớn và luồng gió áp suất cao.
  - Điện áp: DC 24V.
- **Thân vỏ**: Chiều dài $L = 200$ mm (hoặc 210 mm), độ dày tôn $1.15$ mm.
- **Quy tắc phân chia Modul & Số lượng Động cơ KLB 10Nm theo Kích thước ($W \times H$)**:

| Phân loại Modul | Số lượng ĐC KLB 10Nm | Điều kiện kích thước ($W \times H$ mm) | Các kích thước thực tế tiêu biểu (Foxcom) | Ghi chú báo giá chuẩn |
| :---: | :---: | :--- | :--- | :--- |
| **1 Modul** | **1 Động cơ** | $W \le 1300$ và $H \le 1500$ | $1000 \times 700$, $1000 \times 1000$, $1000 \times 1500$, $1300 \times 700$, $800 \times 1500$ | `Van MD, động cơ KLB/VIWECO 24v-10N` |
| **2 Modul** | **2 Động cơ** | $1300 < W \le 2600$ (với $H \le 1300$), hoặc $W=3500, H=500$ | $1200 \times 1000$, $1500 \times 1500$, $2000 \times 800$, $2000 \times 1000$, $2000 \times 1300$, $2600 \times 1000$, $3500 \times 500$ | `Van MD chia 2 modul, 2 động cơ KLB/VIWECO 24V -10N` |
| **4 Modul** | **4 Động cơ** | (1) $W \ge 2000$ và $H > 1300$<br>(2) $W \ge 4000$ và $H \le 1500$ | $2000 \times 1500$, $2000 \times 1800$, $2000 \times 2000$, $2300 \times 1500$, $2500 \times 1500$, $2500 \times 1800$, $3000 \times 1500$, $3500 \times 1600$, $4000 \times 1000$, $4000 \times 1500$, $4500 \times 700$, $4500 \times 800$, $4500 \times 900$, $4500 \times 1000$ | `Van MD chia 4 modul, 4 động cơ KLB/VIWECO 24V -10N` |
| **8 Modul** | **8 Động cơ** | Cả $W \ge 4000$ VÀ $H \ge 1500$ | $4000 \times 2000$, $4700 \times 1500$ | `Van MD chia 8 modul, 8 động cơ KLB/VIWECO 24V -10N` |

---

## 3. NGUYÊN TẮC ÁP DỤNG TRONG PIPELINE DỰ TOÁN

1. **Chỉ áp dụng khi User chỉ định** (`--motor-brand KLB` hoặc `--mfd-model 1.03`):
   - Hệ thống KHÔNG tự nhận diện KLB/Viweco từ chữ trong BOQ hay tên dự án nữa — mặc định cố định mã `1.02` - Belimo (quyết định 2026-10-29, không xét lại dự án cũ).
2. **Khi `motor_brand == "KLB"`**:
   - Đối với van **MFD**: Gán model `SWIND-1.03- MFD-EI90`, chọn mã động cơ `MAT-ACTUATOR-KLB-V6006FS500S` (5Nm), ghi chú theo BCTN 4651/VLXD-TBMT.
   - Đối với van **MD**: Gán mã động cơ `MAT-ACTUATOR-SWIND-VIWECO` (10Nm), áp dụng công thức chia modul 1, 2, 4, 8 modul theo bảng trên.
3. **Đơn giá**:
   - Giá của động cơ KLB / Viweco đã được định nghĩa trong Master Database (`master_database_price.json` và `master_database_tech.json`), hệ thống lấy giá trực tiếp từ database mà không cần thêm mới.
