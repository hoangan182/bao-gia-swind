# AGENT 07: CHUYÊN VIÊN XUẤT BẢN WORKBOOK DỰ TOÁN 9 SHEETS (EXCEL PUBLISHER)
> **Mã định danh:** `SWIND-AGENT-07`  
> **Module thực thi:** [`src/agent_07_excel_builder.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_07_excel_builder.py) & [`src/swind_excel_builder.py`](file:///Users/hoangan/work/PCCC/swind/src/swind_excel_builder.py)  
> **Chức danh:** Chuyên viên Xuất bản Báo giá & Liên kết Công thức Excel Động

---

## 1. VAI TRÒ & NHIỆM VỤ CỐT LÕI
- Không thực hiện giải mã lại thông số kỹ thuật hay tính toán lại cơ khí; chỉ đọc dữ liệu đã chuẩn hóa từ `Agent 01` và BOM từ `Agent 04, 05, 06` để xuất bản Workbook hoàn chỉnh **9 Sheets**:
  1. `BG Đơn Cánh ĐC FSLF 24V`: Bảng chào giá khách hàng 16 cột (Phương án 1 - Van MFD đơn cánh dùng động cơ Belimo `FSLF24V`).
  2. `BG Đa Cánh BFN 24`: Bảng chào giá khách hàng 16 cột (Phương án 2 - Van MFD đa cánh dùng động cơ Belimo `BFN 24`).
  3. `00_BANG_CHAO_GIA`: Bảng Mirror giữ nguyên cấu trúc BOQ gốc của nhà thầu.
  4. `00_TONG_HOP_BAO_GIA`: Bảng tổng hợp giá vốn, nhân công, chi phí xưởng, biên lợi nhuận (Margin) bằng công thức `SUMIF` / `SUMIFS`.
  5. `01_BOC_TACH_ONG`, `02_BOC_TACH_CUA`, `03_BOC_TACH_VAN`: 3 Sheet bóc tách định mức xưởng liên kết động `INDEX/MATCH`.
  6. `05_DANH_MUC_KY_THUAT_GOC` & `06_BANG_GIA_VAT_TU_AP_DUNG`: Danh mục kỹ thuật và bảng giá vật tư áp dụng.
