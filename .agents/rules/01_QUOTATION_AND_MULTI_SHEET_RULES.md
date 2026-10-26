---
trigger: always_on
priority: high
description: Rules for Damper Quotation Modes (Standard vs Dual Blade Options) and Multi-Sheet BOQ Separation
---

# QUY TẮC BÁO GIÁ VÀ XỬ LÝ SHEET DỰ ÁN (SWIND ESTIMATION RULES)

Tài liệu quy tắc bắt buộc áp dụng cho toàn bộ các Agent (`Agent 01` -> `Agent 09`) và Runner của Swind.

---

## 1. Quy Tắc Báo Giá Đơn Cánh vs Đa Cánh (Damper Blade Quotation Policy)

- **Mặc định (Default Behavior):**
  - Hệ thống tính giá **chuẩn mực theo đúng BOQ khách hàng** (sử dụng vật liệu, mã hiệu, độ dày, động cơ và tiêu chuẩn PCCC theo đúng chỉ định của hồ sơ dự thầu).
  - Xuất bảng chào giá chuẩn **`00_BANG_CHAO_GIA`** (hoặc `BẢNG CHÀO GIÁ`).
  - **TUYỆT ĐỐI KHÔNG** tự động xuất 2 sheet so sánh phương án (`BG Đơn Cánh ĐC FSLF 24V` và `BG Đa Cánh BFN 24`) khi người dùng không yêu cầu.
  - Quy tắc kỹ thuật vật liệu:
    + BOQ ghi loại van nào, model nào thì áp dụng định mức cơ khí và động cơ chính xác cho loại đó.
    + Van động cơ MD, MFD, FD và van chống cháy: Mặc định độ dày tôn 1.15mm (trừ khi BOQ ghi rõ độ dày khác).
    + Van cơ VCD, NRD (1 chiều), PRD (xả áp): Áp dụng dải độ dày $\le$ 600x300 (0.75mm), từ 600x600 -> 600x900 (0.95mm), còn lại (1.15mm).
    + Van FD có tiêu chuẩn chống cháy EI ghi đường kính tròn (`D...`) thì mặc định quy về kích thước vuông tương ứng (`DxD`) và áp mã `SWIND-2.01- E-FD-EI120`.
    + **Lưới lọc G4 rời:** Không báo giá các hạng mục lưới lọc / bộ lọc bụi G4 đứng độc lập (bỏ qua không báo).
    + **Ghi chú Cửa gió kèm lọc bụi:** Khi cửa gió có kèm lưới lọc bụi thì phần Ghi chú bắt buộc ghi là **"Cửa ... kèm lưới lọc bụi thô"** (thay vì "phin lọc bụi" hay "lưới lọc bụi").

- **Khi có yêu cầu rõ ràng (Explicit Dual-Option Request):**
  - Chỉ khi người dùng yêu cầu (ví dụ flag `--dual-options`, `--dual-blade`, hoặc dự án có chỉ định riêng như Haus Dalat), hệ thống mới kích hoạt tính toán so sánh và xuất đồng thời 2 sheet:
    1. `BG Đơn Cánh ĐC FSLF 24V` (phương án van đơn cánh gắn Belimo FSLF24).
    2. `BG Đa Cánh BFN 24` (phương án van đa cánh gắn Belimo BFN24).

---

## 2. Quy Tắc Tách File Theo Từng Sheet BOQ (Multi-Sheet BOQ File Separation)

- **Nguyên tắc cốt lõi:**
  - Khi một file BOQ đầu vào chứa nhiều Sheet kỹ thuật/hạng mục (ví dụ dự án CAND có 4 sheet: `Tăng áp HK A1,2`, `Tang áp HK A3`, `DHKK A3`, ` DHKK tgio A3`):
  - **CẤM gộp tất cả các sheet vào 1 file Excel báo giá duy nhất** (trừ khi người dùng truyền cờ `--merge-sheets`).
  - **BẮT BUỘC TÁCH THÀNH TỪNG FILE BÁO GIÁ ĐỘC LẬP TƯƠNG ỨNG VỚI TỪNG SHEET**:
    + Mỗi sheet tạo ra một file báo giá hoàn chỉnh riêng biệt.
    + Quy ước đặt tên file chuẩn:
      `data/projects/<Project_Name>/<Project_Name>_<Clean_Sheet_Name>_ESTIMATION.xlsx`
      hoặc:
      `data/projects/<Project_Name>/<Clean_Sheet_Name>_ESTIMATION.xlsx`

- **Cấu trúc hoàn chỉnh của mỗi file báo giá riêng từng sheet:**
  Mỗi file Excel độc lập cho 1 sheet phải chứa đầy đủ toàn bộ hệ sinh thái dự toán Swind cho các hạng mục của riêng sheet đó:
  1. `00_BANG_CHAO_GIA` (Bảng chào giá chính thức cho khách hàng của sheet đó)
  2. `00_TONG_HOP_BAO_GIA` (Bảng tổng hợp chi phí giá vốn, nhân công, xưởng, lợi nhuận)
  3. `01_BOC_TACH_ONG` (Bảng bóc tách định mức ống gió của sheet đó)
  4. `02_BOC_TACH_CUA` (Bảng bóc tách định mức cửa gió của sheet đó)
  5. `03_BOC_TACH_VAN` (Bảng bóc tách định mức van gió của sheet đó)
  6. `05_DANH_MUC_KY_THUAT_GOC` (Master Tech Data tham chiếu)
  7. `06_BANG_GIA_VAT_TU_AP_DUNG` (Master Price Data tham chiếu)
  *(Nếu có yêu cầu dual-option mới bổ sung thêm 2 sheet `BG Đơn Cánh ĐC FSLF 24V` và `BG Đa Cánh BFN 24`).*

- **Quy tắc với BOQ gộp nhiều tòa/tầng/phân khu thành các cột khối lượng trên cùng 1 Sheet (ví dụ MKS BP05a: `BASEMENT`, `A TOWER`, `B TOWER`, `LANDSCAPE`):**
  - Tách từng cột khối lượng phân khu thành từng file báo giá riêng biệt tương ứng (`BASEMENT`, `A TOWER`, `B TOWER`, `LANDSCAPE`).
  - Sau đó dùng script `src/swind_merge_quotations.py` gộp 4 file thành phần này thành **1 file báo giá cuối cùng duy nhất** (`<Project_Name>_BAO_GIA.xlsx`) chia thành **4 sheet tương ứng** (`BASEMENT`, `A TOWER`, `B TOWER`, `LANDSCAPE`).

---

## 3. Quy Tắc Xuất Báo Cáo Cho Người Dùng (Output Reporting Policy)

1. **Chỉ liệt kê File Báo Giá Cuối Cùng:** Chỉ đưa link duy nhất file báo giá cuối cùng (`<Project_Name>_BAO_GIA.xlsx`), không liệt kê tất cả các file báo giá thành phần hay file dự toán trung gian đã tạo trong thư mục.
2. **Chỉ in Bảng Tổng Hợp Giá Trị:** Chỉ trình bày **Bảng Tổng Hợp Giá Trị Dự Án** (Số dòng, Trước VAT, VAT 8%, Tổng sau VAT), bỏ bảng kết quả báo giá chi tiết từng dòng.
