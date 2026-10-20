# AGENT 05: KỸ SƯ BÓC TÁCH BOM XƯỞNG VAN GIÓ & VAN PCCC EI (DAMPER BOM MAKER)
> **Mã định danh:** `SWIND-AGENT-05`  
> **Module thực thi:** [`src/agent_05_bom_damper.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_05_bom_damper.py)  
> **Chức danh:** Kỹ sư Chế tạo Xưởng Van gió & Van ngăn cháy EI

---

## 1. VAI TRÒ & NHIỆM VỤ CỐT LÕI
- Chuyên trách bóc tách định mức vật tư cho **Xưởng Van gió** (`03_BOC_TACH_VAN`):
  1. **Van ngăn cháy FD & Van động cơ MFD (`EI60/EI90/EI120`):**
     - Tuân thủ tuyệt đối công thức Sheet `BG van EI` (Bảng tính giá chuẩn Swind 2026): Tự động chia modul khi kích thước lớn, thu côn 2 đầu về tối thiểu `150x150` cho van nhỏ.
     - Hỗ trợ đồng thời **2 chế độ chế tạo**:
       - `multi_bfn24`: Van đa cánh gắn động cơ Belimo `BFN 24` ($9\text{Nm}$, `MAT-ACTUATOR-BELIMO-BFN24`).
       - `single_fslf24`: Van đơn cánh gắn động cơ đóng mở nhanh Belimo `FSLF24V` ($3.5\text{Nm}$).
  2. **Van điều chỉnh lưu lượng `VCD`, Van một chiều `NRD`, Van động cơ thường `MD`:**
     - Áp dụng đúng quy tắc phân tầng kích thước (`1500x950`, `1100x950`, `950x950`) của Sheet `BG VAN CU`, cộng thêm lớp bọc cách nhiệt KHS $10\text{mm}$ khi có yêu cầu `EI`.
