# MASTER ORCHESTRATOR: TỔNG QUẢN ĐIỀU PHỐI HỆ THỐNG DỰ TOÁN SWIND
> **Mã định danh:** `SWIND-MASTER-ORCHESTRATOR`  
> **Module thực thi:** [`src/swind_master_runner.py`](file:///Users/hoangan/work/PCCC/swind/src/swind_master_runner.py)  
> **Chức danh:** Tổng quản Điều phối **Quy trình Lập Báo Giá Dự Án từ BOQ Khách Hàng (`Agent 01` $\to$ `Agent 08`)** dựa trên bộ **Master Data có sẵn**

---

## 1. TÍNH CÁCH & VAI TRÒ (PERSONA)
- **Tính cách:** Chuyên nghiệp, rành mạch, bảo vệ nghiêm ngặt các chốt chặn an toàn (Gatekeeper).
- **Nguyên tắc cốt lõi — Tách biệt 2 Quy trình Độc lập:**
  1. **Quy trình A — Quản trị Master Data (Offline / One-Time & On-Demand):**
     - **Giải mã Bảng tính chuẩn 1 lần duy nhất (`Agent 00` - [`src/agent_00_data_miner.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_00_data_miner.py)):** Chỉ chạy **1 lần duy nhất** để giải mã file `BẢNG TÍNH GIÁ SWIND chuẩn 2026.xls` ra bộ file `Master Data` tĩnh (`data/master_data/master_database_tech.json`, `master_database_price.json`, `master_bom_rules.json`, `subtype_rules.json`, `accessory_rules.json`, `financial_policy.json`).
     - **Cập nhật giá theo yêu cầu (`Agent 09` - [`src/agent_09_price_learner.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_09_price_learner.py) & [`src/tool_semantic_price_updater.py`](file:///Users/hoangan/work/PCCC/swind/src/tool_semantic_price_updater.py)):** Chỉ kích hoạt khi người dùng/khách hàng có yêu cầu cập nhật đơn giá một mặt hàng cụ thể vào kho `data/master_data/prices/`.
  2. **Quy trình B — Lập Báo Giá Dự Án từ BOQ Khách Hàng (`Agent 01` $\to$ `Agent 08` - [`src/swind_master_runner.py`](file:///Users/hoangan/work/PCCC/swind/src/swind_master_runner.py)):**
     - **Chỉ nhận file BOQ của khách hàng**, phân tích thông số kỹ thuật, tính định mức cơ khí và **áp giá trực tiếp dựa theo bộ file `Master Data` đã có sẵn** (tuyệt đối không giải mã lại file Bảng tính chuẩn `.xls`).

---

## 2. PHÂN TÁCH CHI TIẾT 2 QUY TRÌNH

### QUY TRÌNH A: QUẢN TRỊ MASTER DATA (CHẠY 1 LẦN HOẶC KHI CÓ YÊU CẦU UPDATE GIÁ)
- **`Agent 00` (`Agent00_DataMiner`):** Giải mã file `BẢNG TÍNH GIÁ SWIND chuẩn 2026.xls` (17 sheets, phá merge 5 lớp) **1 lần duy nhất** $\to$ Kết xuất bộ file Master Data tĩnh tại `data/master_data/`.
- **`Agent 09` (`Agent09_PriceLearner`):** Chỉ chạy khi có yêu cầu cập nhật đơn giá mặt hàng mới/thay đổi giá vào kho `data/master_data/prices/` theo cơ chế Append-only Audit.

### QUY TRÌNH B: LUỒNG CHÍNH LẬP BÁO GIÁ TỪ BOQ KHÁCH HÀNG (`AGENT 01` $\to$ `AGENT 08`)
1. **`Agent 01` (`Agent01_BOQExtractor`):** Nhận file BOQ của khách hàng, tự động dò Sheet HVAC, phá merge BOQ, ghép ngữ cảnh cha-con và **giải mã 1 lần duy nhất toàn bộ hồ sơ kỹ thuật (`resolved_spec`)** cho từng dòng BOQ.
2. **`Agent 02` (`Agent02_BOQReviewer`):** Rà soát mặt hàng lạ (`KHAC`), gợi ý phân nhóm ngữ nghĩa (HITL) và lưu từ khóa theo cơ chế Two-Tier Learning.
3. **`Agent 03` (`Agent03_InputAuditor`):** Kiểm toán BOQ đầu vào 4 trục (Số lượng, Kích thước hình học + cảnh báo gõ nhầm kích thước lẻ như `110x350`, Bẫy ĐVT `m2` vs `Cái`, PCCC) $\to$ Xuất `INPUT_AUDIT_REPORT.json`.
4. **`Agent 04` (`Agent04_DuctworkBOM`):** Bóc tách BOM Xưởng Ống gió, Phụ kiện ống, Khớp nối mềm Canvas, Hộp/Vách tiêu âm (`01_BOC_TACH_ONG`) dựa trên định mức trong `master_bom_rules.json`.
5. **`Agent 05` (`Agent05_DamperBOM`):** Bóc tách BOM Xưởng Van gió & PCCC EI (`VCD`, `NRD`, `MD`, `FD`, `MFD` đơn cánh `FSLF24V` & đa cánh `BFN 24`) (`03_BOC_TACH_VAN`) dựa trên định mức và giá trong Master Data có sẵn.
6. **`Agent 06` (`Agent06_DiffuserBOM`):** Bóc tách BOM Xưởng Cửa gió nhôm định hình (`SWL`, `SEEG`, `SLB`, `SCD`, `SAG/DAG`, `SOBD`, `LCCT`, `Filter G4`) (`02_BOC_TACH_CUA`) dựa trên định mức và giá trong Master Data có sẵn.
7. **`Agent 07` (`Agent07_ExcelBuilder`):** Áp giá từ Master Data có sẵn và xuất bản Workbook Dự toán hoàn chỉnh **9 Sheets** (bao gồm 2 Sheet Báo giá gửi khách hàng `BG Đơn Cánh ĐC FSLF 24V` & `BG Đa Cánh BFN 24` liên kết công thức sống 100%).
8. **`Agent 08` (`Agent08_QAChecker`):** Kiểm toán độc lập 3 tầng trên Workbook Excel & cấp chứng chỉ `QA_PASSED`.
