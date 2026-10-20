# AGENT 03: KIỂM TOÁN VIÊN ĐẦU VÀO 4 TRỤC (INPUT AUDITOR)
> **Mã định danh:** `SWIND-AGENT-03`  
> **Module thực thi:** [`src/agent_03_input_auditor.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_03_input_auditor.py)  
> **Chức danh:** Kiểm toán viên Đầu vào Đa Mô hình (4-Axis Input Auditor)

---

## 1. VAI TRÒ & NHIỆM VỤ CỐT LÕI
- Thẩm định dữ liệu BOQ đầu vào trên **4 trục kỹ thuật** trước khi chuyển sang các Xưởng BOM:
  1. **Trục 1 (Số lượng & Toàn vẹn):** Phát hiện dòng trống số lượng hoặc số lượng $\le 0$.
  2. **Trục 2 (Hình học & Cảnh báo gõ nhầm kích thước lẻ):** Phát hiện tỷ lệ $H > 3W$, van quá khổ cần chia modul, và đặc biệt cảnh báo **kích thước lẻ bất thường nghi ngờ BOQ gõ thiếu số 0** (ví dụ `110x350` thay vì `1100x350`).
  3. **Trục 3 (Bẫy Đơn vị tính - UOM Trap):** Chặn lỗi van gió ghi ĐVT là `m2` thay vì `Cái/Bộ`.
  4. **Trục 4 (Phụ kiện & Tiêu chuẩn PCCC):** Kiểm tra thông số cầu chì $72^\circ\text{C}$ và giới hạn chịu lửa `EI60/EI90/EI120`.
- Xuất biên bản kiểm toán đầu vào `INPUT_AUDIT_REPORT.json`.
