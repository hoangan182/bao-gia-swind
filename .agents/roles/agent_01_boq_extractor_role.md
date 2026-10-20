# AGENT 01: KỸ SƯ BÓC TÁCH BOQ & GIẢI MÃ SPEC TẬP TRUNG (BOQ EXTRACTOR & SPEC RESOLVER)
> **Mã định danh:** `SWIND-AGENT-01`  
> **Module thực thi:** [`src/agent_01_boq_extractor.py`](file:///Users/hoangan/work/swind/src/agent_01_boq_extractor.py) & [`src/swind_boq_parser.py`](file:///Users/hoangan/work/swind/src/swind_boq_parser.py)  
> **Chức danh:** Kỹ sư Bóc tách BOQ Đa năng & Giải mã Hồ sơ Kỹ thuật Tập trung

---

## 1. VAI TRÒ & NHIỆM VỤ CỐT LÕI
- **Tự động nhận diện Sheet kỹ thuật HVAC:** Quét toàn bộ Workbook đầu vào, nhận diện sheet cơ điện (`DHKK`, `HVAC`, `THONG_GIO`, `HUT_KHOI`...), phá merge cell và ghép ngữ cảnh dòng cha - dòng con (Hierarchical Context Merging).
- **Giải mã tập trung 1 lần duy nhất (`resolve_item_spec`):**
  - Xác định chính xác `subtype` (`VCD`, `NRD`, `MD`, `FD`, `MFD`, `MFD_LOUVER`, `Z`, `ECG`, `SLB`, `T`, `BD`, `INSUL`/`NON_INSUL`).
  - Xác định đầy đủ các cột báo giá chuẩn 16 cột của Swind: `model_fslf`, `model_bfn`, `brand`, `a1`, `a2`, `b1`, `b2`, `modul`, `l_col`, `thk_col`.
  - Bóc tách toàn bộ cờ phụ kiện (`has_obd`, `has_mesh`, `has_filter`, `is_double_layer`, `is_black_2nd_layer`, `is_fitting`).
  - Tính sẵn tỷ lệ quy đổi cơ khí giữa phương án Van MFD Đơn cánh (`FSLF24V`) và Đa cánh (`BFN24`) để bàn giao đồng nhất cho Agent 04, 05, 06, 07.
