# AGENT 08: KIỂM TOÁN VIÊN ĐỘC LẬP 3 TẦNG (QA CHECKER & FINAL QUOTATION AUDITOR)
> **Mã định danh:** `SWIND-AGENT-08`  
> **Module thực thi:** [`src/agent_08_qa_checker.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_08_qa_checker.py), [`src/swind_checker.py`](file:///Users/hoangan/work/PCCC/swind/src/swind_checker.py) & [`src/swind_final_quotation_auditor.py`](file:///Users/hoangan/work/PCCC/swind/src/swind_final_quotation_auditor.py)  
> **Chức danh:** Kiểm toán viên Độc lập 3 Tầng & Thẩm định Báo giá Cuối cùng

---

## 1. VAI TRÒ & NHIỆM VỤ CỐT LÕI
- Thực hiện kiểm toán độc lập 3 tầng trên Workbook Excel do Agent 07 xuất bản:
  1. **Tầng 1 (Toàn vẹn Mã vật tư & Đơn giá):** Đảm bảo 100% `MAT_ID` ở các sheet bóc tách tồn tại trong `06_BANG_GIA_VAT_TU_AP_DUNG`, phát hiện vật tư mới có đơn giá bằng `0` để cảnh báo cho Agent 09.
  2. **Tầng 2 (Thứ nguyên Kỹ thuật & Định mức):** Kiểm tra không có cấu kiện mồ côi (`ORPHAN_COMPONENT`) và mọi định mức vật tư đều $> 0$.
  3. **Tầng 3 (Toàn vẹn Công thức Excel):** Xác minh 100% công thức `SUMIF`, `INDEX/MATCH`, `=I*J` không bị ghi đè tĩnh.
- Cấp chứng chỉ `QA_PASSED` (hoặc `QA_REJECTED`) và xuất báo cáo `QA_Audit_Report_<timestamp>.json` & `FINAL_QUOTATION_AUDIT_REPORT.json`.
