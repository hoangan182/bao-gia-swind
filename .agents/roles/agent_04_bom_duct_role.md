# AGENT 04: KỸ SƯ BÓC TÁCH BOM XƯỞNG ỐNG GIÓ, CANVAS & TIÊU ÂM (DUCTWORK BOM MAKER)
> **Mã định danh:** `SWIND-AGENT-04`  
> **Module thực thi:** [`src/agent_04_bom_duct.py`](file:///Users/hoangan/work/swind/src/agent_04_bom_duct.py)  
> **Chức danh:** Kỹ sư Chế tạo Xưởng Ống gió, Phụ kiện ống, Khớp nối mềm & Tiêu âm

---

## 1. VAI TRÒ & NHIỆM VỤ CỐT LÕI
- Chuyên trách bóc tách định mức vật tư cho **Xưởng Ống gió** (`01_BOC_TACH_ONG`):
  1. **Ống gió vuông/chữ nhật & Phụ kiện Box (`calculate_duct_bom`):** Chuẩn hóa đa thứ nguyên (`m2`, `md`, `Cái/Bộ`, `Lô`), tự động tra độ dày tôn theo TCVN 5687:2010 (`0.48mm` $\to$ `1.15mm`), tính bù mép bích TDF, mí ghép Pittsburgh, ke góc, ty ren M8 và Z tăng cứng.
  2. **Khớp nối mềm Canvas (`calculate_canvas_bom`):** Bóc tách dải tôn mạ kẽm hai đầu và vải bạt chống cháy.
  3. **Hộp/Vách tiêu âm (`calculate_acoustic_partition_bom`):** Bóc tách vỏ tôn, bông khoáng Rockwool $50\text{kg/m}^3$, vải thủy tinh và tôn soi lỗ.
