# KẾ HOẠCH THIẾT KẾ WORKBOOK EXCEL BÓC TÁCH VẬT TƯ & DỰ TOÁN BÁO GIÁ SWIND
> **Mã kế hoạch:** `PLAN-SWIND-EXCEL-01`  
> **Thư mục lưu trữ:** `plan/KE_HOACH_THIET_KE_EXCEL_BOC_TACH_VA_MASTER_DATA.md`  
> **Áp dụng cho:** Hệ thống Multi-Agent Bóc tách Dự toán Swind (MAS)  
> **Người thụ hưởng trực tiếp:** Ban Giám Đốc, Kỹ sư Dự toán, Phòng Kinh doanh, Phòng Thu mua (Procurement), Quản đốc Phân xưởng & Khách hàng M&E.

---

## I. BỐI CẢNH & NGUYÊN TẮC CỐT LÕI (CORE PIVOT: EXCEL-FIRST)

### 1. Tại sao không sử dụng JSON cho người dùng cuối?
- **Đặc thù ngành HVAC / Cơ điện:** Các bên liên quan (Chủ đầu tư, Tổng thầu cơ điện, Phòng mua hàng, Xưởng cơ khí) **100% làm việc và giao dịch bằng Microsoft Excel**.
- **Tính minh bạch (No Black-Box):** Khách hàng và kỹ sư cần kiểm tra con số chi tiết: Một chiếc cửa gió $600 \times 600$ giá 250.000 VNĐ tốn bao nhiêu kg nhôm khung, bao nhiêu kg nan, tốn bao nhiêu tiền sơn tĩnh điện. File JSON không thể hiện được trực quan và không cho phép chỉnh sửa nhanh tại chỗ.
- **Vai trò của JSON vs EXCEL trong Hệ thống Multi-Agent:**
  - **JSON:** Là ngôn ngữ giao tiếp ngầm tốc độ cao, siêu chuẩn xác giữa **Maker (Agent 1)** và **Checker (Agent 2)** để chạy máy dò lỗi tự động.
  - **EXCEL:** Là **sản phẩm đầu ra duy nhất (Final Deliverable)** bàn giao cho User cuối tại **Gate 3**, cũng như là giao diện nhập liệu CSDL Vật tư gốc (**Master Data**).

### 2. Nguyên tắc Thiết kế Bất biến (Design Tenets)
1. **Liên kết Công thức Động 100% (Zero Hardcoding):** 
   - Tuyệt đối không copy số tĩnh (paste values) từ các sheet chi tiết lên bảng tổng hợp.
   - Mọi ô thành tiền, khối lượng, đơn giá ở Bảng Tổng Hợp phải được link bằng công thức Excel (`=SUMIFS(...)`, `=XLOOKUP(...)`, `=INDEX/MATCH(...)` hoặc tham chiếu trực tiếp `=Sheet!Cell`).
   - Khi kỹ sư thay đổi giá phôi tôn/nhôm ở bảng vật tư gốc hoặc đổi độ dày trên sheet bóc tách, toàn bộ bảng tổng hợp phải tự động nhảy số theo.
2. **Hệ thống Định danh Mã khóa Duy nhất (Hierarchical ID / Key System):**
   - Mọi dòng sản phẩm, dòng vật tư, dòng phụ kiện đều được gán mã định danh duy nhất theo cấu trúc phân cấp để dễ dàng đối soát, lọc (Filter), tra cứu (Lookup) và truy xuất nguồn gốc hai chiều (Bidirectional Traceability).
3. **Điều hướng Siêu liên kết (Interactive Hyperlinks):**
   - Tại Bảng Tổng Hợp, mỗi dòng sản phẩm đều có link tắt (`=HYPERLINK(...)`) bấm chuột là tự động chuyển ngay đến bảng bóc tách chi tiết của cấu kiện đó ở Sheet con tương ứng.

---

## II. HỆ THỐNG MÃ ĐỊNH DANH (ID / KEY SCHEMA)

Để đảm bảo các sheet liên kết chính xác tuyệt đối không bị trùng lặp hay nhầm dòng, hệ thống áp dụng bộ quy ước mã hóa 3 cấp:

```
[ CẤP 1: ITEM_ID ]  (Dành cho Sản phẩm hoàn chỉnh trên Sheet Tổng Hợp)
   Ví dụ: SW-ITM-001 (Ống gió vuông), SW-ITM-025 (Cửa gió nan T), SW-ITM-040 (Van VCD)
         │
         ├───► [ CẤP 2: SUB_KEY ] (Dành cho Chi tiết cấu kiện bóc tách ở Sheet Con)
         │        Ví dụ: 
         │        - SW-ITM-040-BODY   (Thân vỏ van tôn mạ kẽm)
         │        - SW-ITM-040-BLADE  (Cánh van tôn mạ kẽm)
         │        - SW-ITM-040-GEAR   (Cặp bánh răng truyền động)
         │        - SW-ITM-040-AXLE   (Trục ty thép truyền động)
         │
         └─────► [ CẤP 3: MAT_ID ] (Dành cho Vật tư gốc từ Master Database)
                  Ví dụ: 
                  - MAT-STEEL-0.75-HS (Tôn Hoa Sen dày 0.75mm)
                  - MAT-ALU-KHUNG-T   (Nhôm thanh định hình khung nan T)
                  - MAT-MOTOR-NEN-05  (Động cơ van gió Nenutec Thụy Sỹ 5Nm)
```

| Cấp độ Key | Tên gọi | Định dạng quy ước | Sheet áp dụng | Mục đích sử dụng |
| :---: | :--- | :--- | :--- | :--- |
| **Cấp 1** | `ITEM_ID` | `SW-ITM-XXX` (001, 002...) | `00_TONG_HOP_BAO_GIA` & Cột tham chiếu ở các Sheet Con | Định danh từng sản phẩm độc lập trong danh mục BOQ khách hàng giao. |
| **Cấp 2** | `SUB_KEY` | `[ITEM_ID]-[VẬT_LIỆU]-[CHI TIẾT]` | `01_BOC_TACH_TON`, `02_BOC_TACH_NHOM`, `03_BOC_TACH_VAN`... | Định danh từng thành phần phôi được bóc ra từ cây BOM sản phẩm. |
| **Cấp 3** | `MAT_ID` | `MAT-[NHÓM]-[QUY_CÁCH]-[NHÃN]` | `06_MASTER_DATA_GIA_GOC`, `05_BOM_MUA_HANG` | Tra cứu đơn giá phôi gốc từ nhà cung cấp và tổng hợp vật tư mua hàng. |

---

## III. KIẾN TRÚC WORKBOOK EXCEL DỰ TOÁN BÁO GIÁ (`SWIND_ESTIMATION_WORKBOOK.xlsx`)

File Excel thành phẩm gồm **7 Sheet chức năng** được phân bổ theo luồng bóc tách chuẩn cơ điện:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   SHEET 00: 00_TONG_HOP_BAO_GIA (MASTER SUMMARY)            │
│  - Bảng tổng hợp báo giá hoàn chỉnh trình Ban Giám Đốc / Khách Hàng         │
│  - Chứa cột ITEM_ID duy nhất cho mỗi dòng sản phẩm                          │
│  - Toàn bộ Khối lượng, Đơn giá vật tư đều LINK CÔNG THỨC từ Sheet con 01-04  │
└──────┬──────────────────────┬───────────────────────┬───────────────────────┘
       │                      │                       │
       ▼ (=SUMIF/Link)        ▼ (=SUMIF/Link)         ▼ (=SUMIF/Link)
┌──────────────┐      ┌───────────────┐       ┌────────────────┐
│   SHEET 01   │      │   SHEET 02    │       │    SHEET 03    │
│ BOC_TACH_ONG │      │ BOC_TACH_CUA  │       │  BOC_TACH_VAN  │
│ (Ống & T.Âm) │      │ (Cửa gió nhôm)│       │ (Tròn & Vuông) │
└──────┬───────┘      └───────┬───────┘       └────────┬───────┘
       │                      │                        │
       └──────────────────────┼────────────────────────┘
                              ▼ (=SUMIF theo MAT_ID)
┌─────────────────────────────────────────────────────────────────────────────┐
│                    SHEET 04: 04_BOM_MUA_HANG (PROCUREMENT)                  │
│  - Tổng hợp nhu cầu vật tư: Tấn tôn, Tấn nhôm, Cái động cơ, Mét gioăng      │
│  - Dành cho Quản đốc nhà máy & Phòng Mua hàng lên kế hoạch vật tư           │
└─────────────────────────────┬───────────────────────────────────────────────┘
                              ▼ (=XLOOKUP tra đơn giá gốc)
┌─────────────────────────────────────────────────────────────────────────────┐
│                 SHEET 05: 05_MASTER_DATA_GIA_GOC (PRICE CATALOG)            │
│  - Bảng giá phôi tôn các hãng, giá nhôm thanh, đơn giá sơn, đơn giá motor  │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

### Chi tiết Cấu trúc Từng Sheet:

#### 1. Sheet `00_TONG_HOP_BAO_GIA` (Master Summary)
* **Chức năng:** Trình bày bảng chào giá thương mại, tổng hợp chi phí, giá vốn và thành tiền.
* **Cấu trúc cột:**
  - `A: STT` (1, 2, 3...)
  - `B: ITEM_ID` (`SW-ITM-001`, `SW-ITM-002`...) — **MÃ KHÓA TRUY XUẤT CHÍNH**
  - `C: PHAN_NHOM` (Cửa gió, Van gió, Ống gió tôn, Hộp tiêu âm, Phụ kiện)
  - `D: TEN_SAN_PHAM` (Tên mô tả cấu kiện theo BOQ gốc)
  - `E: MODEL_KIEU_DANG` (Ví dụ: VCD, FD, OBD, Nan T, Bầu dục, Bích TDC, Nẹp C)
  - `F: KICH_THUOC_DANH_DINH` ($W \times H$ hoặc $D$, Cổ $A \times B$, Dài $L$)
  - `G: DVT` (m2 / Cái / Mét / Bộ)
  - `H: SO_LUONG` (Số lượng cần sản xuất)
  - `I: CP_ONG_TIEU_AM` $\to$ **CÔNG THỨC:** `=SUMIF('01_BOC_TACH_ONG'!$B:$B, $B12, '01_BOC_TACH_ONG'!$I:$I)`
  - `J: CP_CUA_GIO` $\to$ **CÔNG THỨC:** `=SUMIF('02_BOC_TACH_CUA'!$B:$B, $B12, '02_BOC_TACH_CUA'!$J:$J)`
  - `K: CP_VAN_GIO` $\to$ **CÔNG THỨC:** `=SUMIF('03_BOC_TACH_VAN'!$B:$B, $B12, '03_BOC_TACH_VAN'!$M:$M)`
  - `L: TONG_CP_VAT_TU_TRUC_TIEP` $\to$ **CÔNG THỨC:** `=SUM(I12:K12) + Phụ liệu khác`
  - `N: CP_NHAN_CONG_SX` (Đơn giá nhân công gia công tiêu chuẩn)
  - `O: CP_CHUNG_NHA_XUONG` (Định phí quản lý xưởng & khấu hao máy móc)
  - `P: GIA_VON_COGS` $\to$ **CÔNG THỨC:** `=M12 + N12 + O12`
  - `Q: HE_SO_MARGIN` (Hệ số lãi định mức, ví dụ: 20%)
  - `R: DON_GIA_CHAO_THAU` $\to$ **CÔNG THỨC:** `=ROUND(P12 * (1 + Q12), -2)`
  - `S: THANH_TIEN` $\to$ **CÔNG THỨC:** `=H12 * R12`
  - `T: LINK_CHI_TIET` $\to$ **HYPERLINK:** Điều hướng đến dòng bóc tách con ở sheet tương ứng.

#### 2. Sheet `01_BOC_TACH_ONG` (Bóc tách Ống gió, Phụ kiện & Tiêu âm)
* **Chức năng:** Bóc tách toàn bộ phần kim loại tấm và vật liệu hấp thụ âm cho cấu kiện đường ống.
* **Cấu trúc cột:**
  - `A: SUB_KEY` (`ONG-001`, `TA-001`...)
  - `B: PARENT_ITEM_ID` (`SW-ITM-001`)
  - `C: TEN_CAU_KIEN` (Ống thẳng, Cút, Hộp tiêu âm, Côn thu...)
  - `D: QUY_CACH_VẬT_LIỆU` (Tôn Phương Nam 0.75mm, Bông khoáng 50kg/m3...)
  - `E: DIEN_TICH_PHOI_M2` (Diện tích khai triển toán học)
  - `F: HE_SO_HAO_HUT` (1.10 - 1.15)
  - `G: TRONG_LUONG_KG` (Tính riêng cho tôn mạ kẽm)
  - `H: DON_GIA_VAT_TU` $\to$ Link từ `05_MASTER_DATA` bằng hàm `XLOOKUP`
  - `I: THANH_TIEN_VẬT_TƯ` $\to$ Trả về Sheet Tổng

#### 3. Sheet `02_BOC_TACH_CUA` (Bóc tách Cửa gió Nhôm định hình)
* **Chức năng:** Trình bày rõ ràng cấu trúc cấu tạo của từng bộ cửa gió (Khung, nan, phụ kiện, sơn).
* **Cấu trúc cột:**
  - `A: SUB_KEY` (`CUA-001`, `CUA-002`...)
  - `B: PARENT_ITEM_ID` (`SW-ITM-025`)
  - `C: CHI_TIET_CAU_THANH` (Khung nhôm, Nan bầu dục, Suốt tăng cứng D8, Lưới lọc bụi...)
  - `D: KICH_THUOC_W_H`
  - `E: SO_LUONG_MET_HOAC_CAI` (Công thức tính số nan, mét khung)
  - `F: KHOI_LUONG_NHOM_KG`
  - `G: DIEN_TICH_SON_M2`
  - `H: DON_GIA_PHOI_VA_SON` $\to$ Link từ `05_MASTER_DATA`
  - `I: THANH_TIEN_VẬT_TƯ` $\to$ Trả về Sheet Tổng

#### 4. Sheet `03_BOC_TACH_VAN` (Bóc tách Van Gió Tròn & Vuông)
* **Chức năng:** Hợp nhất bóc tách cho cả van tròn (danh sách chuẩn) và van vuông (công thức tham số H/W).
* **Cấu trúc cột:**
  - `A: SUB_KEY` (`VAN-001`, `VAN-002`...)
  - `B: PARENT_ITEM_ID` (`SW-ITM-040`)
  - `C: CHUNG_LOAI_VAN` (Van VCD vuông, Van tròn D200, Van FD...)
  - `D: CHI_TIET_CO_KHI` (Thân vỏ tôn, Cánh van, Trục ty thép, Bánh răng chịu nhiệt, Tay gạt, Motor Nenutec)
  - `E: SO_LUONG_CAU_KIEN` (Tự động chia theo chiều cao H $\to$ số cánh, số trục, số cặp bánh răng)
  - `F: KHOI_LUONG_TON_KG` (Đối với phần thân vỏ và cánh)
  - `G: MA_VAT_TU_MAT_ID` (`MAT-MOTOR-NEN-05`, `MAT-GEAR-ALU`...)
  - `H: DON_GIA_LINH_KIEN` $\to$ Link từ `05_MASTER_DATA`
  - `I: THANH_TIEN_VẬT_TƯ` $\to$ Trả về Sheet Tổng

#### 5. Sheet `04_BOM_MUA_HANG` (Procurement & Production Rollup)
* **Chức năng:** Gom toàn bộ nhu cầu vật tư của dự án theo từng mã phôi `MAT_ID`. Phục vụ trực tiếp cho Trưởng phòng Mua hàng (Procurement) lập PO.
* **Cấu trúc bảng:**
  - `A: MAT_ID` (`MAT-STEEL-0.58-PN`, `MAT-ALU-KHUNG-T`, `MAT-MOTOR-NEN-05`...)
  - `B: TEN_VAT_TU_QUY_CACH`
  - `C: DVT_MUA_HANG` (Kg, Mét, Cái, Bộ)
  - `D: TONG_NHU_CAU_DU_AN` $\to$ **CÔNG THỨC:** Sử dụng hàm `=SUMIFS` quét qua các Sheet `01`, `02`, `03` theo `MAT_ID`.
  - `E: HE_SO_DU_PHONG_KHO` (1.02)
  - `F: KHOI_LUONG_DAT_HANG` $\to$ `=D10 * E10`
  - `G: DU_TOAN_NGAN_SACH_MUA_HANG`

#### 6. Sheet `05_MASTER_DATA_GIA_GOC` (Bảng tra Đơn Giá & Định Mức Gốc)
* **Chức năng:** CSDL phôi tôn, phôi nhôm, motor, phụ kiện, nhân công (được số hóa từ file Excel gốc 2026).
* **Cấu trúc:** Cột `MAT_ID` chuẩn làm từ điển cho `XLOOKUP` / `INDEX+MATCH`.

---

## IV. QUY TRÌNH PHỐI HỢP CỦA HỆ THỐNG MULTI-AGENT VỚI WORKBOOK EXCEL

Kiến trúc làm việc của 3 Agent được tinh chỉnh để phục vụ trực tiếp mô hình Excel-First:

```
[User Nạp BOQ File]
       │
       ▼
[AGENT 0: Orchestrator]
  - Quét BOQ thô, Chia lô (Batching 20-50 dòng).
  - Cấp phát dải mã ITEM_ID chuẩn: SW-ITM-001 -> SW-ITM-xxx.
  - Quản lý GATE 1 (Hỏi ngoại lệ Đèn Giao Thông).
       │
       ▼ (Chuyển BOQ sạch đã cấp ID)
[AGENT 1: The Maker]
  - Đọc thông số hình học (W, H, L, D).
  - Chạy thư viện Python swind_bom_engine.py để tính kích thước phôi, số cánh van, mét nan nhôm.
  - Tự động KHỞI TẠO FILE EXCEL WORKBOOK bằng openpyxl:
    * Ghi dữ liệu vào các Sheet con bóc tách (01-04) kèm SUB_KEY và PARENT_ITEM_ID.
    * Ghi Sheet Tổng Hợp (00) và VIẾT CÔNG THỨC LIÊN KẾT ĐỘNG (=SUMIF, =XLOOKUP).
    * Thiết lập định dạng chuyên nghiệp: Border, Number Format (#,##0), Tô màu Header, Hyperlink điều hướng.
       │
       ▼ (Bàn giao Workbook nháp + File JSON Log kiểm toán)
[AGENT 2: The Checker]
  - Kiểm toán độc lập 3 tầng trên file Excel:
    1. Quét lỗi công thức Excel: Tìm kiếm các ô lỗi #REF!, #N/A, #VALUE!, #DIV/0!.
    2. Đối soát toàn vẹn: Đảm bảo số lượng dòng trên Sheet 00 khớp 100% với BOQ gốc.
    3. Thẩm định kỹ thuật: Soi độ dày tôn theo khổ ống, số cánh van theo chiều cao H, suốt tăng cứng nan nhôm.
  - Nếu có lỗi -> Trả Maker sửa lại công thức / tham số (Tối đa 3 lần Gate 2).
  - Nếu hoàn hảo -> Đóng dấu QA_PASSED.
       │
       ▼
[GATE 3: User Nghiệm Thu Cuối]
  - Agent 0 gửi trực tiếp file Excel SWIND_ESTIMATION_WORKBOOK.xlsx cho User.
  - User mở Excel kiểm tra nhanh, chỉnh sửa biên lợi nhuận (Margin) nếu cần và xuất báo giá PDF gửi khách hàng.
```

---

## V. KẾ HOẠCH HÀNH ĐỘNG CHI TIẾT (ACTION ROADMAP)

Kế hoạch triển khai được chia thành **4 giai đoạn cụ thể**:

```
GIAI ĐOẠN 1: CHUẨN HÓA MASTER DATA EXCEL (BƯỚC ĐẦU VÀO)
├── 1.1. Viết script Python trích xuất 17 sheet từ file gốc "BẢNG TÍNH GIÁ SWIND chuẩn 2026.xls".
├── 1.2. Tạo file "MASTER_DATA_SWIND.xlsx" chuẩn hóa:
│        - Sheet Danh mục Tổng hợp có cột MAT_ID chuẩn.
│        - Các sheet con: Tôn cuộn, Phôi nhôm, Motor van gió, Phụ kiện, Tiêu âm.
└── 1.3. Xuất file master_database.json đồng bộ làm cache tốc độ cao cho Agent.

GIAI ĐOẠN 2: PHÁT TRIỂN MODULE PYTHON TẠO FILE EXCEL (CORE ENGINE)
├── 2.1. Hoàn thiện swind_bom_engine.py (Toán học bóc tách quy chuẩn DW144/TCVN 5687).
└── 2.2. Xây dựng swind_excel_builder.py:
         - Sử dụng thư viện openpyxl.
         - Tạo cấu trúc 7 sheet chuẩn.
         - Tự động viết công thức liên kết động (=SUMIF, =XLOOKUP).
         - Áp bộ Style thẩm mỹ: Màu nhận diện Swind (Xanh Navy/Cam), Kẻ viền thanh lịch, Format tiền tệ VNĐ.

GIAI ĐOẠN 3: CẬP NHẬT QUY CHẾ VÀ PROMPTS CỦA 3 AGENT (.agents/roles/)
├── 3.1. Cập nhật orchestrator_role.md: Thêm trách nhiệm cấp phát ITEM_ID và giao file Excel ở Gate 3.
├── 3.2. Cập nhật maker_role.md: Thêm quy định xuất file Excel công thức sống (Zero Hardcoding).
└── 3.3. Cập nhật checker_role.md: Thêm quy trình Audit công thức Excel (#REF!, #N/A) và tính toàn vẹn 2 chiều.

GIAI ĐOẠN 4: TEST TOÀN TRÌNH VỚI DỰ ÁN MẪU BÀ NÀ HILLS
├── 4.1. Nạp file "Copy of BG01.2_SLAND_NAMVIET- CỬA GIÓ VAN GIÓ TIÊU ÂM_BANA HILL H1...".
├── 4.2. Chạy quy trình MAS bóc tách tự động toàn bộ 100+ dòng sản phẩm.
└── 4.3. Bàn giao file Excel hoàn thiện cho User đánh giá và nghiệm thu.
```

---

## VI. BỘ TIÊU CHÍ NGHIỆM THU FILE EXCEL ĐẦU RA (ACCEPTANCE CRITERIA)

| STT | Tiêu chí đánh giá | Chỉ số bắt buộc | Phương thức kiểm tra |
| :---: | :--- | :---: | :--- |
| **1** | **Tỷ lệ công thức liên kết (Live Formula Ratio)** | **$100\%$** | Các cột Khối lượng, Chi phí vật tư, Đơn giá, Thành tiền ở Sheet Tổng Hợp bắt buộc phải chứa dấu `=`, không được gõ số cứng (Hardcode). |
| **2** | **Lỗi công thức Excel (#REF, #N/A, #VALUE)** | **$0$ ô lỗi** | Quét kiểm tra toàn bộ 7 sheets không có bất kỳ ô nào báo lỗi cú pháp hoặc đứt gãy tham chiếu. |
| **3** | **Tính toàn vẹn mã khóa (Key Integrity)** | **$100\%$** | $100\%$ `PARENT_ITEM_ID` ở các sheet con phải tìm thấy chính xác tại cột `ITEM_ID` của Sheet Tổng Hợp. Không có mã mồ côi (Orphan Keys). |
| **4** | **Tính thẩm mỹ & Trải nghiệm người dùng** | **Đạt chuẩn Pro** | Header có màu nhận diện rõ ràng, đóng băng dòng tiêu đề (Freeze Panes), định dạng số có dấu chấm phân cách hàng nghìn (`#,##0`), cột tiền căn phải, mã căn giữa. |
| **5** | **Khả năng tự động cập nhật khi đổi giá phôi** | **Tức thì (Instant)** | Thử thay đổi giá phôi tôn hoặc phôi nhôm tại Sheet `06_MASTER_DATA`, toàn bộ đơn giá và thành tiền tại Sheet Tổng Hợp phải tự động thay đổi chính xác. |
