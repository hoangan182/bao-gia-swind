# TỔNG QUAN & HƯỚNG DẪN BẢNG TÍNH GIÁ SWIND CHUẨN 2026
> **File gốc:** `BẢNG TÍNH GIÁ SWIND  chuẩn 2026.xls`  
> **Đơn vị áp dụng:** SWIND / SLAND (Tiền thân liên kết cơ khí Starduct / Ngôi Sao Châu Á)  
> **Ngành hàng:** Sản xuất & Gia công Hệ thống Thông gió - Điều hòa không khí (HVAC Ductwork & Air Distribution)  
> **Mục tiêu tài liệu:** Tài liệu tóm tắt toàn diện này giúp người đọc chỉ cần duyệt qua là nắm bắt trọn vẹn mục đích, kiến trúc dữ liệu, công thức định mức, mối quan hệ giữa các sheet và quy trình báo giá mà không cần mở toàn bộ file gốc phức tạp.

---

## I. MỤC ĐÍCH CỐT LÕI CỦA FILE EXCEL

File `BẢNG TÍNH GIÁ SWIND  chuẩn 2026.xls` là **Hệ thống Định mức Dự toán Chi phí & Báo giá Xuất xưởng Chuẩn (Cost Estimation & Master Quotation Engine)** của SWIND. File phục vụ 3 mục đích chiến lược:

1. **Quản lý biến phí đầu vào & định phí vận hành**: Quản lý giá phôi tôn cuộn (Phương Nam, Hoa Sen, BlueScope, Posco-Dongbu, VNSteel, Inox), phôi nhôm định hình, động cơ điện van gió (Nenutec Thụy Sỹ), phụ kiện cách âm - cách nhiệt - chống cháy, cùng chi phí cố định (nhà xưởng, nhân công, điện nước văn phòng).
2. **Chuẩn hóa công thức định mức & quy chuẩn kỹ thuật HVAC**: Tự động tính diện tích khai triển phôi thép/nhôm, tự động áp chuẩn độ dày tôn theo kích thước danh định (chuẩn SMACNA / DW144 / TCVN 5687), tính toán hệ số hao hụt vật liệu và đơn giá nhân công theo độ dày.
3. **Bộ công cụ lập báo giá thương mại tự động**: Xuất báo giá hoàn chỉnh cho 6 nhóm sản phẩm cơ điện cốt lõi:
   - Ống gió vuông (nẹp C, bích TDC, bọc chống cháy EI, tiêu âm).
   - Ống gió tròn xoắn và phụ kiện tròn.
   - Các loại van gió (VCD tay gạt/trục vít, NRD 1 chiều, FD cầu chì chống cháy, MD động cơ điện, PRD xả áp).
   - Cửa gió nhôm sơn tĩnh điện (nan T, nan bầu dục 1-2 lớp, Louver nan Z, cửa khe SLD, van OBD).
   - Hộp tiêu âm âm thanh (tiêu âm vuông 0-1-2 vách, tiêu âm tròn).
   - Phụ kiện đường ống: Khớp nối mềm canvas (thường/chống cháy), Vent cap inox 304, Ống gió mềm nhôm có/không bảo ôn.

---

## II. SƠ ĐỒ KIẾN TRÚC DỮ LIỆU (MÔ HÌNH 4 TẦNG)

Dữ liệu trong file được tổ chức xuyên suốt theo 4 tầng logic chặt chẽ:

```
[ TẦNG 1: DỮ LIỆU ĐẦU VÀO & CHI PHÍ ]
   ├── Vat tu tôn (Giá tôn kg/m2 các hãng)
   ├── VT van (Motor Nenutec, cầu chì Elsie)
   ├── VT tiêu âm (Bông khoáng, bông thủy tinh, vải TT)
   └── Chi phí cố định xưởng & nhôm thanh (Sheet 'BG Cửa')
             │
             ▼
[ TẦNG 2: ĐƠN GIÁ CƠ BẢN THEO M2 ]
   └── Đơn giá theo m2 & Sheet1
       (Giá tôn x Hao hụt + Nhân công + Vật tư phụ = Đơn giá Public/m2)
             │
             ▼
[ TẦNG 3: CÔNG THỨC HÌNH HỌC & ĐỊNH MỨC PHỤ KIỆN ]
   ├── BG PKV (Tính diện tích khai triển & đơn giá phụ kiện vuông)
   ├── TINH VT PK TRON (Công thức tính phụ kiện tròn xoắn)
   └── BG PKT (Bảng tra đơn giá phụ kiện tròn theo đường kính chuẩn)
             │
             ▼
[ TẦNG 4: THÀNH PHẨM & FORM BÁO GIÁ XUẤT XƯỞNG ]
   ├── BG VAN (Van tay gạt, trục vít, FD, MD motor, 1 chiều, xả áp)
   ├── BG Cửa & BG Cửa (rút gọn) (Cửa nan T, bầu dục, Louver, Slot, OBD)
   ├── BG TIEU AM (Tiêu âm tròn, tiêu âm vuông 0-1-2 vách)
   ├── BG canvas, ventcap (Nối mềm canvas, chụp thông hơi inox 304)
   └── bảo ôn (Ống gió mềm nhôm có/không bảo ôn)
```

---

## III. CHI TIẾT NỘI DUNG 17 SHEETS TRONG FILE

| STT | Tên Sheet | Kích thước | Phân loại | Mục đích & Nội dung cốt lõi |
|:---:|:---|:---:|:---:|:---|
| 1 | **BG VAN** | 177r x 56c | Form Báo giá | Bảng giá chi tiết tất cả các loại van gió tròn và van vuông. Phân chia van vuông theo số cánh chuyển động (1, 2, 3, 4, 5 cánh; loại 1 thân, 2 thân, 4 thân khi W, H > 1000mm hoặc > 2000mm). Bao gồm: Van tay gạt, trục vít, 1 chiều NRD, van chặn lửa cầu chì FD, van động cơ điện On/Off & Modulating, van tràn áp PRD. |
| 2 | **Sheet3** | 0r x 0c | Trống | Sheet trắng dự phòng. |
| 3 | **BG Cửa** | 321r x 49c | Tính giá & Báo giá | Bảng tính chi tiết & báo giá cửa gió nhôm định hình sơn tĩnh điện. Tích hợp bảng chi phí xưởng/văn phòng hàng tháng, đơn giá nhôm phôi (nan BD, nan T, khung BD, khung Z, nan/khung OBD). Danh mục: Cửa khuếch tán nan dập liền SKD, cửa khe SLD, nan T cố định SLB-F, nan bầu dục 1 lớp SAG, 2 lớp DAG, nan Z lấy gió ngoài Louver SWL-F, van OBD nhôm, cửa hoa văn nghệ thuật. |
| 4 | **BG Cửa (rút gọn)** | 184r x 49c | Form Báo giá | Bản tinh gọn của sheet `BG Cửa`, chỉ giữ lại các cột thông số danh định chính và giá bán đã cộng biên độ lợi nhuận, thuận tiện gửi cho khách hàng hoặc kinh doanh tra nhanh. |
| 5 | **BG PKV** | 113r x 28c | Bảng tính định mức | Công thức hình học tính diện tích tôn phôi ($S1, S2, S3, S4, S_{tổng}$) cho toàn bộ phụ kiện ống vuông: Côn thu (US), Chân rẽ (SU), Chuyển vuông-tròn (V-T), Cút $90^\circ, 60^\circ, 45^\circ$ (BS), Chạc Y, Tê, Bịt đầu, Hộp gió (thân hộp + cổ tròn). Tự động gán độ dày tôn theo kích thước và tính giá nẹp C, bích TDC, bọc EI 30, dán mút tiêu âm. |
| 6 | **Sheet2** | 0r x 0c | Trống | Sheet trắng dự phòng. |
| 7 | **TINH VT PK TRON** | 133r x 27c | Bảng tính định mức | Công thức tính toán vật tư và diện tích phôi phụ kiện tròn: Ống xoắn tròn (SR), măng xông nối, van tròn, cút tròn ghép phân đoạn xoay, Tê tròn (R-BS), đai cùm treo ống. Tích hợp quy tắc nhân hệ số bù đơn giá nhỏ. |
| 8 | **BG PKT** | 30r x 18c | Bảng giá tra nhanh | Bảng tra đơn giá thành phẩm phụ kiện tròn chuẩn hóa theo đường kính danh định từ $D100 \to D1000$ cho các cấp độ dày tôn ($0.58, 0.75, 0.95$ mm). Bao gồm ống xoắn, măng xông, cút tròn, tê tròn. |
| 9 | **Đơn giá theo m2** | 97r x 29c | Bảng giá gốc (Master) | **Sheet trái tim của hệ thống định mức**. Tính toán đơn giá Public/m2 cho ống và phụ kiện của 6 dòng vật liệu: Tôn Phương Nam, Tôn Hoa Sen, Tôn BlueScope, Tôn Dongbu-Posco, Inox 304/430, Tôn Thăng Long VNSteel. Tách biệt rõ ràng Phần I (Ống tròn) và Phần II (Ống vuông). |
| 10 | **BG TIEU AM** | 154r x 25c | Form Báo giá | Bảng giá hộp tiêu âm đường ống gió. Gồm tiêu âm tròn (kích thước phủ bì $D1$ và lòng trong $D2$) và tiêu âm vuông (loại không vách, loại có 1 vách tiêu âm ở giữa, loại có 2 vách tiêu âm song song). Chi tiết định mức vỏ tôn, tôn lỗ 0.5, bông thủy tinh $60\text{ kg/m}^3$, vải thủy tinh, nẹp V gia cường và nhân công. |
| 11 | **BG canvas, ventcap** | 33r x 22c | Form Báo giá | Bảng giá khớp nối mềm bạt canvas (loại thường, loại bạt chống cháy) chia theo cấu trúc Tôn 45/75 + Bạt 100/150 + Tôn 45/75; và bảng giá Vent cap (chụp thông hơi ngoài trời chống chim/chuột, model SFX-S bằng inox SUS 304 từ DN50 đến DN300). |
| 12 | **Vat tu tôn** | 33r x 43c | Cơ sở dữ liệu vật tư | Bảng tra cứu giá nguyên liệu tôn cuộn nhập kho: Khổ tôn ($1200\text{ mm}, 1530\text{ mm}$), tỷ trọng ($\text{kg/m}$ dài, $\text{kg/m}^2$), đơn giá theo kg, đơn giá theo mét dài và đơn giá theo $\text{m}^2$ của Dongbu, VNSteel, Phương Nam, Hoa Sen. |
| 13 | **VT van** | 52r x 7c | Cơ sở dữ liệu vật tư | Báo giá gốc thiết bị lắp ráp van: Động cơ van điện NENUTEC (Thụy Sỹ) dòng đóng mở On/Off 220VAC (NACA 2-05, NACA 2-10, NACA 2-20, NACA 2-40), bộ điều khiển NTC 831, động cơ tuyến tính Modulating (NACM 1.2-05), motor lò xo phản hồi hút khói, cầu chì nhiệt ELSIE USA ($165^\circ\text{F} \approx 74^\circ\text{C}$). |
| 14 | **VT tiêu âm** | 45r x 7c | Cơ sở dữ liệu vật tư | Báo giá bông thủy tinh Glasswool và bông khoáng Rockwool: Phân loại theo chiều dày ($50\text{ mm}$), khổ cuộn ($1.2\text{m}$), tỷ trọng ($12, 24, 32, 60\text{ kg/m}^3$), loại có phủ màng nhôm/bạc hoặc không bạc. |
| 15 | **BG VAN CU** | 175r x 34c | Lưu trữ lịch sử | Bảng giá van Starduct năm 2015 của Công ty Ngôi Sao Châu Á. Dùng để đối chiếu lịch sử giá và kiểm tra cấu trúc mã sản phẩm cũ. |
| 16 | **Sheet1** | 93r x 8c | Bảng tham chiếu | Phiên bản rút gọn hiển thị đơn giá Public của sheet `Đơn giá theo m2` (chỉ hiển thị cột giá Ống và Phụ kiện theo độ dày tôn). |
| 17 | **bảo ôn** | 29r x 15c | Form Báo giá | Bảng báo giá các loại ống gió mềm nhôm nhún (Flexible Duct) đường kính từ $D100 \to D350$: Loại không bọc bảo ôn và loại có bọc bông thủy tinh cách nhiệt. |

---

## IV. CÔNG THỨC & CÁC QUY TẮC ĐỊNH MỨC QUAN TRỌNG

### 1. Công thức cấu thành Đơn giá m² (Sheet `Đơn giá theo m2`)
$$\text{Đơn giá Public (VNĐ/m}^2\text{)} = (\text{Đơn giá phôi tôn} \times \text{Hệ số hao hụt}) + \text{Đơn giá nhân công} + \text{Vật tư phụ}$$

* **Hệ số hao hụt tôn tiêu chuẩn:**
  - Ống gió vuông: $1.10$ (10% phế liệu cắt bích, góc ghép).
  - Phụ kiện ống vuông: $1.30$ (30% hao hụt do đường cong khai triển).
  - Ống xoắn tròn: $1.19875 \approx 1.20$ (hao hụt mép cuộn kép seam).
  - Phụ kiện tròn: $1.35$ (35% phế liệu khi cắt phân đoạn).
* **Đơn giá nhân công sản xuất (theo độ dày tôn):**
  - Tôn $0.48 - 0.58\text{ mm}$: $\approx 46,636\text{ VNĐ/m}^2$
  - Tôn $0.75\text{ mm}$: $\approx 54,218\text{ VNĐ/m}^2$
  - Tôn $0.95\text{ mm}$: $\approx 58,864\text{ VNĐ/m}^2$
  - Tôn $1.15\text{ mm}$: $\approx 61,091\text{ VNĐ/m}^2$
  - Tôn $1.48 - 1.50\text{ mm}$: $\approx 70,200\text{ VNĐ/m}^2$
* **Chi phí vật tư phụ (silicone, vít, ke góc bích, bulong, ty treo):**
  - Ống tròn: $10,000\text{ VNĐ/m}^2$
  - Ống vuông: $15,500\text{ VNĐ/m}^2$

### 2. Tiêu chuẩn chọn độ dày tôn theo kích thước (Sheet `BG PKV`)
Hệ thống tự động tham chiếu độ dày tôn theo cạnh lớn nhất của tiết diện ống:
- Cạnh $\le 400\text{ mm}$: Tôn dày **$0.48\text{ mm}$**
- Cạnh $401 - 700\text{ mm}$: Tôn dày **$0.58\text{ mm}$**
- Cạnh $701 - 999\text{ mm}$: Tôn dày **$0.75\text{ mm}$**
- Cạnh $1000 - 1499\text{ mm}$: Tôn dày **$0.95\text{ mm}$**
- Cạnh $\ge 1500\text{ mm}$: Tôn dày **$1.15\text{ mm}$**

### 3. Quy tắc bù giá phụ kiện kích thước nhỏ (Sheet `BG PKV`, `TINH VT PK TRON`)
Các chi tiết nhỏ tốn công pha cắt và căn chỉnh thủ công cao hơn nhiều so với giá trị vật tư, do đó được nhân hệ số điều chỉnh lũy tiến:
- Đơn giá thành phẩm $< 100,000\text{ VNĐ/cái}$ $\to$ **Nhân hệ số $1.15$** (+15%)
- Đơn giá thành phẩm $< 50,000\text{ VNĐ/cái}$ $\to$ **Nhân hệ số $1.25$** (+25%)
- Đơn giá thành phẩm $< 30,000\text{ VNĐ/cái}$ $\to$ **Nhân hệ số $1.50$** (+50%)

### 4. Quy tắc phân cấp van gió cơ khí (Sheet `BG VAN`)
- **Theo chiều cao ($H$):**
  - $100 < H \le 200\text{ mm}$: Van 1 cánh.
  - $250 < H \le 400\text{ mm}$: Van 2 cánh (liên động bánh răng nhôm).
  - $450 < H \le 600\text{ mm}$: Van 3 cánh.
  - $650 < H \le 800\text{ mm}$: Van 4 cánh.
  - $H = 1000\text{ mm}$: Van 5 cánh.
- **Theo bề rộng phủ bì ($W$):**
  - $W \le 1000\text{ mm}$: Van vuông 1 thân.
  - $1000 < W \le 2000\text{ mm}$: Van vuông 2 thân ghép liền.
  - $W > 2000\text{ mm}$ hoặc $H > 2000\text{ mm}$: Van vuông 4 thân module.
- **Tùy chọn phụ trội van:**
  - Van chặn lửa dùng motor có gắn cảm biến nhiệt/khói: Cộng thêm **$300,000\text{ VNĐ}$** so với van dùng motor On/Off thông thường.

---

## V. QUY TRÌNH 4 BƯỚC SỬ DỤNG FILE ĐỂ LẬP BÁO GIÁ

Khi có một bảng yêu cầu báo giá dự án (BOQ) mới:

1. **Bước 1: Cập nhật biến phí đầu vào (nếu có biến động thị trường)**
   - Mở sheet `Vat tu tôn` cập nhật giá cuộn tôn nếu nhà máy thép điều chỉnh giá.
   - Mở sheet `VT van`, `VT tiêu âm` cập nhật giá động cơ Nenutec hoặc bông thủy tinh.
   - Giá $\text{m}^2$ tại sheet `Đơn giá theo m2` sẽ tự động nhảy số theo công thức.
2. **Bước 2: Tra cứu / Tính toán phụ kiện đặc thù**
   - Nếu dự án có phụ kiện ống vuông phi tiêu chuẩn: Nhập thông số $B1, H1, B2, H2, L$ vào sheet `BG PKV` để lấy giá nẹp C hoặc bích TDC.
   - Nếu có phụ kiện tròn: Nhập đường kính $D$ vào sheet `TINH VT PK TRON` hoặc tra trực tiếp trong sheet `BG PKT`.
3. **Bước 3: Lấy đơn giá van, cửa gió, tiêu âm**
   - Với van gió: Tra theo mã model và kích cỡ trong sheet `BG VAN`.
   - Với cửa gió: Tra bảng `BG Cửa (rút gọn)` theo kích cỡ cổ (neck size) hoặc mặt (face size).
   - Với hộp tiêu âm, nối mềm canvas, ống mềm: Lấy tại các sheet tương ứng (`BG TIEU AM`, `BG canvas, ventcap`, `bảo ôn`).
4. **Bước 4: Xuất báo giá dự án**
   - Tổng hợp số lượng và đơn giá vào form mẫu báo giá thương mại (tương tự như file dự án Bana Hill đính kèm trong cùng thư mục).

---
*Tài liệu tóm tắt được lập tự động từ cấu trúc phân tích dữ liệu thực tế của file `BẢNG TÍNH GIÁ SWIND  chuẩn 2026.xls`.*
