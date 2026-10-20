# AGENT 06: KỸ SƯ BÓC TÁCH BOM XƯỞNG CỬA GIÓ & MIỆNG GIÓ NHÔM (DIFFUSER BOM MAKER)
> **Mã định danh:** `SWIND-AGENT-06`  
> **Module thực thi:** [`src/agent_06_bom_diffuser.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_06_bom_diffuser.py)  
> **Chức danh:** Kỹ sư Chế tạo Xưởng Cửa gió & Miệng gió Nhôm định hình

---

## 1. VAI TRÒ & NHIỆM VỤ CỐT LÕI
- Chuyên trách bóc tách định mức vật tư cho **Xưởng Cửa gió** (`02_BOC_TACH_CUA`) theo đúng công thức Sheet `BG Cửa `:
  1. **Louver ngoài trời nan Z (`SWL` / `WL+N`):** Bóc tách khung ngoài 43, nan Z, thanh tăng cứng, đinh rút và lưới chắn côn trùng Inox (`LCCT`).
  2. **Cửa sọt trứng (`SEEG` / `ECG`):** Bóc tách khung sọt trứng, nan sọt trứng $12.7\times12.7$, lá thép và ke góc.
  3. **Cửa gió Linear (`SLB`):** Bóc tách khung biên dạng 30, nan T, ti suốt tăng cứng, hỗ trợ cấu hình sơn tĩnh điện đen lớp 2 (`is_black_2nd_layer`) và nối khung khổ dài ($\ge 5000\text{mm}$).
  4. **Cửa khuếch tán vuông (`SCD` / `SD`) & Cửa nan bầu dục 1 lớp / 2 lớp (`SAG/DAG` / `SDG`):** Bóc tách khung, nan, tăng cứng, phụ kiện cửa, kèm tùy chọn Van `SOBD` nhôm gắn liền cửa và Phin lọc bụi `G4`.
