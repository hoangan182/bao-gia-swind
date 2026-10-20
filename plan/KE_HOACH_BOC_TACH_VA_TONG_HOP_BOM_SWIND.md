# KẾ HOẠCH TỔNG HỢP, BÓC TÁCH DỮ LIỆU & XÂY DỰNG HỆ THỐNG TÍNH GIÁ TỰ ĐỘNG SWIND
> **Mã tài liệu:** `SOP-SWIND-ESTIMATION-01`  
> **Căn cứ dữ liệu gốc:** File [`BẢNG TÍNH GIÁ SWIND  chuẩn 2026.xls`](file:///Users/hoangan/work/swind/BA%CC%89NG%20TI%CC%81NH%20GIA%CC%81%20SWIND%20%20chua%CC%82%CC%89n%202026.xls) và hồ sơ mẫu [`Copy of BG01.2_SLAND_NAMVIET- CỬA GIÓ VAN GIÓ TIÊU ÂM_BANA HILL H1- 08062026 VER4- van đa cánh BFN.xlsx`](file:///Users/hoangan/work/swind/Copy%20of%20BG01.2_SLAND_NAMVIET-%20CU%CC%9B%CC%89A%20GIO%CC%81%20VAN%20GIO%CC%81%20TIE%CC%82U%20A%CC%82M_BANA%20HILL%20H1-%2008062026%20VER4-%20van%20%C4%91a%20ca%CC%81nh%20BFN.xlsx)  
> **Mục tiêu:** Bản kế hoạch tác nghiệp và đặc tả kỹ thuật này đóng vai trò kim chỉ nam (Single Source of Truth). Khi có yêu cầu bóc tách đơn hàng hoặc nâng cấp phần mềm, **người dùng và AI Agent chỉ cần đọc tài liệu này để triển khai chính xác 100%**.

---

## PHẦN I: TỔNG QUAN & BÀI TOÁN CẦN GIẢI QUYẾT

### 1. Thực trạng & Thách thức
* **Khách hàng đưa đầu vào rất sơ sài:** Thông thường chỉ có tên sản phẩm và khối lượng thô (Ví dụ: *"5.000 m² ống gió tôn"*, *"20 cái van VCD 600x300"*, *"50 bộ cửa gió 600x600"*).
* **Bảng tính cũ rời rạc:** File Excel gốc phân tán thành 17 sheet, nhiều số liệu hardcode, công thức nằm rải rác giữa giá m², giá van, giá nhôm và vật tư tiêu âm.
* **Nguy cơ sai lệch giá thành:** Nếu tính vo theo m² hoặc theo cái mà không phân rã cấu thành vật tư (BOM), nhà máy sẽ chịu rủi ro lỗ nặng hoặc chào giá quá cao làm mất thầu.

### 2. Giải pháp: Hệ thống Phân rã Tham số tự động (Parametric Auto-BOM Engine)
Chuyển đổi toàn bộ quy trình tính toán sang mô hình 3 lớp:
1. **Lớp 1: Khách hàng đưa kích thước danh nghĩa ($W \times H \times L$) và số lượng.**
2. **Lớp 2: Hệ thống tự động phân rã ra từng chi tiết cấu thành (BOM), tính khối lượng/số lượng vật tư theo công thức kỹ thuật và nhân với đơn giá vật tư gốc.**
3. **Lớp 3: Tự động cộng gộp (Rollup) thành Giá vốn (COGS) $\to$ Cộng định phí xưởng $\to$ Cộng biên độ lợi nhuận $\to$ Xuất báo giá.**

---

## PHẦN II: QUY TRÌNH PHỐI HỢP: USER LÀM GÌ vs PHẦN MỀM / AGENT LÀM GÌ

Quy trình khép kín gồm 5 bước phối hợp nhịp nhàng giữa con người và hệ thống tự động:

```
[ USER ]                      [ AGENT 1 (MAKER) ]                    [ AGENT 2 (CHECKER) ]
   │                                   │                                      │
   ├─► BƯỚC 1: Nạp BOQ thô             │                                      │
   │                                   ├─► BƯỚC 2: Trích xuất & Phân rã BOM   │
   │                                   │   (Áp công thức & Sinh Báo giá nháp) │
   │◄──[ GATE 1: User duyệt ngoại lệ ]─┤                                      │
   │                                   │                                      │
   │                                   ├──(Chuyển giao File Nháp)────────────►│
   │                                   │                                      ├─► BƯỚC 3: Kiểm toán QA Chéo
   │                                   │                                      │   (Đọc & dò lỗi độc lập)
   │                                   │◄──[ GATE 2: Fail -> Maker làm lại ]──┤
   │                                   │                                      │
   │◄──[ GATE 3: Báo cáo QA Pass ]─────┴──────────────────────────────────────┤
   │                                                                          │
   ├─► BƯỚC 4: Phê duyệt cuối & Chốt                                          │
   │                                                                          │
   │                              [ AGENT 1 (MAKER) ]                         │
   │                                   │                                      │
   │                                   ├─► BƯỚC 5: Xuất Báo cáo Final & Ghi Log
   ▼                                   ▼                                      ▼
```

### 1. Chi tiết: User làm gì?
* **Bước 1 (Nhập liệu):** Nạp danh mục sản phẩm từ bảng BOQ thô. Thiết lập các thông số biên (Margin, thương hiệu vật tư).
* **Gate 1 (Duyệt ngoại lệ):** Quyết định hướng xử lý đối với các món hàng Lạ (Cảnh báo Đỏ/Vàng) do Agent 1 trình lên.
* **Gate 3 (Phê duyệt kết quả QA):** Sau khi nhận được Báo cáo Kiểm toán sạch (Pass) từ Agent 2, User xem lướt Báo giá cuối cùng và chốt ký duyệt.

### 2. Chi tiết: Agent 1 (Maker - Đóng vai Kỹ sư Dự toán)
* **Nhiệm vụ 1 (Regex & Trích xuất):** Quét cột mô tả thô của khách, bóc tách thông số $W, H, L, D$.
* **Nhiệm vụ 2 (Trình Gate 1):** Dừng lại để xin ý kiến User nếu gặp hàng ngoại lệ (Tuyệt đối không chạy tiếp nếu User chưa chốt).
* **Nhiệm vụ 3 (Phân rã BOM & Sinh Draft):** Chạy công thức tính khối lượng phôi, lấy đơn giá từ bảng Master Data, sinh ra bản tính nháp (`BaoGia_Draft.xlsx`).
* **Nhiệm vụ 4 (Giao QA):** Bàn giao bản nháp cho Agent 2 và chờ Agent 2 rà lỗi (Gate 2). Phải sửa lại nếu bị Agent 2 bắt lỗi.
* **Nhiệm vụ 5 (Kết xuất & Ghi Log):** Sau khi User chốt (Gate 3), xuất file PDF/Excel bản Final (Báo giá & Lệnh sản xuất) và tự động ghi chú kinh nghiệm vào `TU_DIEN_KINH_NGHIEM_SWIND.md`.

### 3. Chi tiết: Agent 2 (Checker - Đóng vai Kế toán / QA)
* **Nhiệm vụ 1 (Đối chiếu Độc lập - Cross-Check):** Nhận bản `BaoGia_Draft.xlsx` từ Agent 1. Đọc lại BOQ gốc của khách để đối chiếu.
* **Nhiệm vụ 2 (Dò tìm Lỗi):**
  - **Kiểm tra tính vẹn toàn:** Tổng số lượng/số dòng có khớp nguyên bản không? (Chống rớt dòng).
  - **Kiểm tra Toán học:** Giá vốn có $> 0$ không? Tổng tiền có khớp Margin cam kết không?
  - **Kiểm tra Logic Kỹ thuật:** VD van $1200\times600$ mà Maker tính ra 1 cánh là sai luật, ống $2000\text{mm}$ mà dùng tôn $0.58$ là sai luật.
* **Gate 2 (Phản hồi Maker):** Nếu phát hiện lỗi $\to$ Lập danh sách lỗi, yêu cầu Agent 1 tính lại. Vòng lặp này chạy ngầm cho đến khi sạch lỗi.
* **Gate 3 (Báo cáo User):** Khi bản tính đã chuẩn 100%, Agent 2 trình bày Báo cáo QA: *"Bản Draft đã check chéo, khớp 100% đầu vào, lãi gộp 22%, đúng chuẩn kỹ thuật. Xin mời Sếp ký duyệt!"*

---

## PHẦN III: BẢNG TỔNG HỢP CHI TIẾT CẤU THÀNH SẢN PHẨM (MASTER BOM MATRIX)

Trong file gốc [`BẢNG TÍNH GIÁ SWIND  chuẩn 2026.xls`](file:///Users/hoangan/work/swind/BA%CC%89NG%20TI%CC%81NH%20GIA%CC%81%20SWIND%20%20chua%CC%82%CC%89n%202026.xls), toàn bộ hệ thống sản phẩm được chia thành **6 nhóm sản phẩm lớn** với cây vật tư cấu thành như sau:

---

### NHÓM 1: CỬA GIÓ & MIỆNG GIÓ NHÔM (7 Dòng sản phẩm)
*Áp dụng cho: Cửa nan bầu dục 1 lớp (SAG), 2 lớp (DAG), nan T (SLB-F), Louver nan Z chống mưa (SWL-F), Cửa khuếch tán vuông (SKD), Cửa khe (SLD), Van cửa gió (OBD).*

```
1 CÁI CỬA GIÓ NHÔM
├── 1. Khung nhôm bao ngoài (Profile nhôm định hình)
├── 2. Nan nhôm cánh gió (Profile nan T, nan bầu dục, nan Z)
├── 3. Suốt liên kết D8 (Trục nhôm tròn định vị nan)
├── 4. Phụ kiện liên kết (Ke góc nhôm, lò xo gài, đinh rút nhôm)
├── 5. Sơn tĩnh điện hoàn thiện (Bột sơn Polyester cao cấp)
├── 6. (Tùy chọn) Lưới chắn: Lưới lọc bụi nylon HOẶC Lưới côn trùng Inox 304
└── 7. (Tùy chọn) Van điều chỉnh lưu lượng OBD nhôm đi kèm phía sau
```

| Cấu phần cấu thành | Chất liệu / Quy cách phôi | ĐVT | Công thức tính định mức / 1 sản phẩm |
|:---|:---|:---:|:---|
| **1. Khung nhôm** | Nhôm đùn thanh mã SH8070, CK028, EUS-01 | kg | $$M_{\text{khung}} = 2 \times (W + H) \times \text{Tỉ trọng khung (kg/m)} \times 1.05\text{ (cắt góc)}$$<br>*(Tỉ trọng: $0.20 - 0.247\text{ kg/m}$)* |
| **2. Nan nhôm** | Nhôm đùn mã SH8032, SHL0027, EUS-02 | kg | • Số nan: $N = \text{ROUNDUP}\left(\frac{H - \text{khung}}{\text{Bước nan}}\right) + 1$<br>• $M_{\text{nan}} = N \times W \times \text{Tỉ trọng nan (kg/m)}$<br>*(Cửa DAG 2 lớp: $M_{\text{nan}} \times 2$)* |
| **3. Suốt giữ nan D8** | Nhôm tròn $\varnothing 8\text{ mm}$ | kg | $M_{\text{suốt}} = \text{Số suốt} \times H \times 0.07\text{ kg/m}$ *(Cửa rộng $>600$ cần 2–3 thanh)* |
| **4. Ke góc & Đinh rút** | Ke nhôm định hình dập $+ 8$ đinh rút | Bộ | Cố định 1 bộ/cửa ($4$ ke góc, $8-12$ đinh rút) |
| **5. Sơn tĩnh điện** | Bột sơn Polyester sấy nhiệt ($200^\circ\text{C}$) | $\text{m}^2$ | $S_{\text{sơn}} \approx 2.5 \times (W \times H) \times 10^{-6}$ |
| **6. Lưới lọc (Tùy chọn)** | Lưới nylon viền nhôm / Lưới inox | $\text{m}^2$ | $S_{\text{lưới}} = W \times H \times 10^{-6}$ |
| **7. Nhân công gia công** | Cắt nhôm, xâu nan, bấm góc, bắn đinh, đóng gói | Cái | Định mức theo chu vi và số nan |

---

### NHÓM 2: VAN GIÓ CƠ KHÍ & ĐIỀU KHIỂN (6 Dòng sản phẩm)
*Áp dụng cho: Van VCD tay gạt, VCD trục vít, Van 1 chiều NRD, Van chặn lửa FD, Van động cơ điện MD (On/Off & Tuyến tính), Van xả áp PRD.*

```
1 CÁI VAN GIÓ
├── 1. Thân vỏ van (Tôn mạ kẽm chấn bích liền)
├── 2. Cánh van (Tôn chấn gập tăng cứng V-blade hoặc nhôm)
├── 3. Trục van (Thép vuông 10x10 hoặc tròn D10/D12 mạ kẽm)
├── 4. Bạc lót trục (Bạc đồng thau hoặc bạc nhựa chịu nhiệt)
├── 5. Hệ thống bánh răng liên động (Bánh răng nhôm ăn khớp)
├── 6. Bộ cơ cấu chấp hành (Tay gạt / Trục vít / Cầu chì / Motor Nenutec)
├── 7. Gioăng làm kín mép cánh (Cao su EPDM hoặc Inox chịu nhiệt)
└── 8. Bulong, đinh tán, nhân công căn chỉnh khe hở khí
```

| Cấu phần cấu thành | Chất liệu / Quy cách phôi | ĐVT | Công thức tính định mức / 1 sản phẩm |
|:---|:---|:---:|:---|
| **1. Vỏ thân van** | Tôn mạ kẽm dày $0.75 - 1.15\text{ mm}$ | kg | $S_{\text{vỏ}} = 2 \times (W + H) \times L \times 1.15\text{ (bích)}$<br>$M_{\text{vỏ}} = S_{\text{vỏ}} \times \text{Độ dày} \times 7.85$ |
| **2. Cánh van** | Tôn mạ kẽm $0.75 - 0.95\text{ mm}$ | kg | • Số cánh: $N = \text{Tra theo } H$ ($H \le 200 \to 1; H \le 400 \to 2; H \le 600 \to 3; H \le 800 \to 4; H \ge 1000 \to 5$)<br>• Khối lượng $= N \times W \times \text{Bản cánh} \times \text{Độ dày} \times 7.85$ |
| **3. Trục quay van** | Thép tròn đặc $\varnothing 10$ hoặc $\varnothing 12\text{ mm}$ | mét | $L_{\text{trục}} = N \times (W + 60\text{ mm})$ |
| **4. Bạc đỡ trục** | Bạc đồng tự bôi trơn $\varnothing 10/\varnothing 12$ | Cái | $\text{Số lượng} = 2 \times N\text{ (cánh)}$ (2 bên vách thân) |
| **5. Bánh răng liên động** | Nhôm đúc chịu mài mòn | Cặp | $\text{Số bánh răng} = N\text{ (cánh)}$ (ăn khớp xoay ngược chiều) |
| **6. Bộ điều khiển** | Chọn 1 trong 4 loại cơ cấu | Bộ | 1 bộ duy nhất trên 1 thân van (Tay gạt / Trục vít / Cầu chì nhiệt Elsie / Motor Nenutec) |
| **7. Nhân công cơ khí** | Chấn tôn, dập lỗ vách, lắp bạc, căn chỉnh khe hở | Cái | Định mức bậc thợ cơ khí theo số cánh (1 cánh đến 5 cánh) |

---

### NHÓM 3: HỘP TIÊU ÂM ĐƯỜNG ỐNG (3 Dòng sản phẩm)
*Áp dụng cho: Tiêu âm tròn, Tiêu âm vuông không vách, Tiêu âm vuông 1–2 vách.*

```
1 BỘ TIÊU ÂM
├── 1. Vỏ ngoài tiêu âm (Tôn mạ kẽm dày 0.75 - 1.15 mm)
├── 2. Vỏ trong & Vách tiêu âm (Tôn mạ kẽm soi lỗ D3-D5mm dày 0.5 mm)
├── 3. Lõi hút âm (Bông thủy tinh Glasswool / Bông khoáng Rockwool 60 kg/m3)
├── 4. Lớp bảo vệ chống bay bụi (Vải thủy tinh chống cháy bọc quanh bông)
├── 5. Khung xương giữ vách (Thép hình mạ kẽm V30 / V40)
└── 6. Nhân công nhồi bông, tán đinh, bọc vải, chấn gấp tôn lỗ
```

| Cấu phần cấu thành | Chất liệu / Quy cách phôi | ĐVT | Công thức tính định mức / 1 sản phẩm |
|:---|:---|:---:|:---|
| **1. Vỏ ngoài tôn** | Tôn mạ kẽm dày $0.75 - 1.15\text{ mm}$ | $\text{m}^2$ | $S_{\text{ngoài}} = 2 \times (W_1 + H_1) \times L_1 \times 1.1$ |
| **2. Tôn lỗ tiêu âm** | Tôn mạ kẽm đột lỗ $0.5\text{ mm}$ (lỗ $\varnothing 3 - 5\text{mm}$) | $\text{m}^2$ | • Không vách: $S = 2 \times (W_2 + H_2) \times L_2$<br>• Có 1 vách giữa: $S + 2 \times (H_2 \times L_2)$<br>• Có 2 vách giữa: $S + 4 \times (H_2 \times L_2)$ |
| **3. Bông tiêu âm** | Bông thủy tinh / Rockwool **$60\text{ kg/m}^3$**, dày $50\text{ mm}$ | $\text{m}^2$ | $\text{Diện tích bông} = \text{Diện tích các khoang nhồi bông} \times \text{Độ dày}$ |
| **4. Vải thủy tinh** | Vải sợi thủy tinh dệt chống cháy | $\text{m}^2$ | $S_{\text{vải}} = \text{Diện tích toàn bộ bề mặt bông tiếp xúc tôn lỗ}$ |
| **5. Nẹp thép V** | Thép góc V30 / V40 mạ kẽm | mét | Định hình khung xương vách tiêu âm chống rung |
| **6. Nhân công hoàn thiện** | Cắt bông, bọc vải, tán đinh tôn lỗ, chấn bích | Bộ | Công gấp 2.5 lần so với sản xuất ống gió thường |

---

### NHÓM 4: ỐNG GIÓ VUÔNG & PHỤ KIỆN (10 Dòng sản phẩm)
*Áp dụng cho: Ống thẳng, Cút $90^\circ/60^\circ/45^\circ$, Côn thu, Chân rẽ, Chuyển vuông-tròn (V-T), Chạc 3 (Y), Tê, Nắp bịt đầu, Hộp gió.*

| Sản phẩm | Cấu phần cấu thành | ĐVT | Công thức tính định mức phôi |
|:---|:---|:---:|:---|
| **Ống thẳng** | Tôn mạ kẽm + Bích (TDC/Nẹp C) | $\text{m}^2$ | $S = 2 \times (B_1 + H_1) \times L \times 10^{-6} \times \text{Hao hụt (1.10)}$ |
| **Côn thu (US)** | Tôn mạ kẽm (4 mặt hình thang $S_1, S_2, S_3, S_4$) | $\text{m}^2$ | $S = [B_1+B_2+H_1+H_2] \times \sqrt{L^2 + \Delta^2} \times 10^{-6} \times 1.30$ |
| **Cút vuông (BS)** | Tôn mạ kẽm (2 má cút cong $+ 2$ lưng bụng) | $\text{m}^2$ | Khai triển theo bán kính cong $R$: $S_{\text{tổng}} \times 1.35$ |
| **Chuyển V-T** | Tôn mạ kẽm (chuyển chữ nhật sang tròn $D$) | $\text{m}^2$ | Khai triển 4 tam giác phẳng $+ 4$ góc côn nón tròn $\times 1.35$ |
| **Hộp gió** | Tôn thân hộp $+ \text{Cổ tròn } D + \text{Mút PE}$ | $\text{m}^2$ | • $S_{\text{thân}} = [B \times H + 2L(B+H)] \times 10^{-6}$<br>• $S_{\text{cổ}} = \text{Số cổ} \times (\pi \times D \times 0.15)$<br>• Mút PE Foam dày 10mm $= (S_{\text{thân}} + S_{\text{cổ}}) \times 1.15$ |

---

### NHÓM 5: ỐNG TRÒN XOẮN & PHỤ KIỆN TRÒN (6 Dòng sản phẩm)
*Áp dụng cho: Ống xoắn tròn (SR), Măng xông nối, Cút tròn phân đoạn, Tê tròn, Đai cùm treo, Van tròn.*

| Sản phẩm | Cấu phần cấu thành | ĐVT | Công thức tính định mức phôi |
|:---|:---|:---:|:---|
| **Ống xoắn tròn** | Dải tôn mạ kẽm cuộn xoắn mí seam kép | mét / $\text{m}^2$ | $S = \pi \times D \times L \times 10^{-6} \times \text{Hao hụt seam (1.19875)}$ |
| **Măng xông** | Tôn mạ kẽm cuộn tròn có gân chặn | Cái | $S = \pi \times D \times L_{\text{măng xông (100-150mm)}} \times 1.25$ |
| **Cút tròn xoay** | 3 hoặc 4 phân đoạn tròn cắt góc ghép mí | Cái | $S = \text{Tổng diện tích các phân đoạn phôi} \times 1.35$ |
| **Cùm treo ống** | Thép la mạ kẽm dập gân $+ 2$ bộ bulong M8 | Cái | $\text{Chu vi } \pi \times (D + 10) + \text{Tai bẻ 60mm}$ |

---

### NHÓM 6: KHỚP NỐI MỀM & PHỤ TRỢ (3 Dòng sản phẩm)
*Áp dụng cho: Khớp nối mềm Canvas, Vent cap inox ngoài trời, Ống gió mềm nhôm.*

| Sản phẩm | Cấu phần cấu thành | ĐVT | Công thức tính định mức phôi |
|:---|:---|:---:|:---|
| **Nối mềm Canvas** | 2 dải tôn mạ kẽm ép seam chặt dải bạt ở giữa | $\text{m}^2$ | Chu vi $2(W+H)$ hoặc $\pi D \times \text{Bản bạt (Tôn 45 + Bạt 100/150 + Tôn 45)}$<br>*(Bạt thường hoặc Bạt sợi thủy tinh chống cháy)* |
| **Vent cap SUS304** | Thân hình nón inox $304 +$ lưới chắn chim | Cái | Tra theo kích thước danh định ($DN50 \to DN300$) |
| **Ống gió mềm** | Lá nhôm nhún xoắn gân thép $+ \text{Bông TT cách nhiệt}$ | mét | Tra theo $D100 \to D350$ (Loại trần hoặc Loại bọc bông bảo ôn có bạc) |

---

## PHẦN IV: BẢNG TỔNG KHO VẬT TƯ GỐC (MASTER MATERIAL INVENTORY)

Để hệ thống vận hành tự động, toàn bộ đơn giá vật tư phải được quản lý tập trung tại **1 Bảng duy nhất** gồm 4 nhóm chính:

```
BẢNG TỔNG KHO VẬT TƯ GỐC (MASTER_DATA)
├── 1. TÔN CUỘN (Tôn Hoa Sen, Phương Nam, BlueScope, Posco, Inox 304/430 từ 0.48 -> 1.5mm)
├── 2. NHÔM THANH ĐỊNH HÌNH (Nan BD, Nan T, Nan Z, Khung BD, Khung Z, Khung/Nan OBD)
├── 3. LINH KIỆN CƠ KHÍ & ĐỘNG CƠ (Bạc trục, Bánh răng nhôm, Tay gạt, Trục D10, Cầu chì Elsie, Motor Nenutec)
└── 4. VẬT LIỆU TIÊU ÂM, CÁCH NHIỆT & SƠN (Bông TT 60kg, Vải thủy tinh, Tôn lỗ 0.5, Mút PE, Sơn bột)
```

Khi thị trường biến động (ví dụ: giá tôn tăng $1,000\text{ đ/kg}$ hoặc giá nhôm tăng), **chỉ cần sửa 1 ô duy nhất trong Bảng Master Data**, toàn bộ hàng ngàn mã sản phẩm phía sau sẽ tự động cập nhật giá mới ngay lập tức.

---

## PHẦN V: KẾ HOẠCH TRIỂN KHAI 4 GIAI ĐOẠN (ACTION PLAN)

| Giai đoạn | Nhiệm vụ chính | Sản phẩm đầu ra | Người phụ trách |
|:---|:---|:---|:---|
| **Giai đoạn 1** *(Tuần 1)* | **Chuẩn hóa Master Database:** Thu thập và chuẩn hóa toàn bộ đơn giá vật tư gốc của Swind vào 1 bảng duy nhất. | File cấu hình `master_materials_db.json` hoặc Sheet `MASTER_DATA`. | Kỹ sư Dự toán + Agent |
| **Giai đoạn 2** *(Tuần 2)* | **Lập trình Động cơ Phân rã BOM:** Xây dựng script/công thức tự động tính khối lượng linh kiện từ $W, H, L$. | Python Engine / Module Excel Macro tính tự động. | AI Agent |
| **Giai đoạn 3** *(Tuần 3)* | **Thiết kế Template Báo cáo:** Thiết kế chuẩn form Báo giá khách hàng và form Lệnh sản xuất xuất xưởng. | 2 mẫu biểu chuẩn `Template_BaoGia.xlsx` và `Template_LenhSanXuat.xlsx`. | Kỹ sư Bán hàng + Quản đốc |
| **Giai đoạn 4** *(Tuần 4)* | **Test thử nghiệm với BOQ Bà Nà Hill:** Nạp toàn bộ file mẫu Bana Hill H1 để kiểm tra độ chính xác đối chiếu với file chốt thực tế. | Báo cáo đối soát sai số $(< 1\%)$ và ban hành quy trình chuẩn (SOP). | Toàn đội ngũ |

---

## PHẦN VI: HƯỚNG DẪN THỰC THI DÀNH CHO AI AGENT KHI NHẬN LỆNH MỚI

Khi nhận lệnh bóc tách BOQ mới, hệ thống tự động triển khai theo **Quy trình Maker-Checker (Cổng chặn - Gate Control)**:

1. **BƯỚC 1 - Khởi tạo Agent 1 (Maker):** Agent đọc nạp logic file SOP này và `TU_DIEN_KINH_NGHIEM_SWIND.md`.
2. **BƯỚC 2 - Quét ngoại lệ (Tới Gate 1):** Agent 1 phân loại danh mục. Nếu gặp Cảnh báo Đỏ/Vàng, DỪNG LẠI trình User phê duyệt (Gate 1).
3. **BƯỚC 3 - Tính toán bản Nháp:** Agent 1 chạy ngầm công thức BOM, tính chi phí và đóng gói bản `BaoGia_Draft.xlsx`.
4. **BƯỚC 4 - Khởi tạo Agent 2 (Checker) làm bài Test (Gate 2):** 
   - Hệ thống sinh ra Sub-Agent 2.
   - Agent 2 kiểm toán độc lập bản Draft (Dò số lượng dòng, check logic độ dày tôn, tính chéo giá vốn/lãi).
   - Nếu lỗi: Trả về Agent 1 làm lại (Vòng lặp kín).
5. **BƯỚC 5 - Báo cáo QA (Gate 3):** Agent 2 thông qua Gate 2, gửi Báo cáo QA sạch sẽ cho User duyệt bước cuối (Gate 3).
6. **BƯỚC 6 - Kết xuất & Đóng gói:** User gõ "OK", Agent 1 sinh 2 file Excel Final (Thương mại + Lệnh sản xuất) và ghi Log kinh nghiệm vào Từ Điển. Quy trình kết thúc.
