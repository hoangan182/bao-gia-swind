# QUY TRÌNH THỰC THI NGHIÊM NGẶT THEO CƠ CHẾ CỔNG KIỂM SOÁT (STRICT GATEKEEPER WORKFLOW - TÁCH BIỆT 2 QUY TRÌNH)

Để đảm bảo hệ thống Multi-Agent Swind vận hành minh bạch, chính xác và không trùng lặp logic, toàn bộ kiến trúc được **tách biệt thành 2 quy trình độc lập**:
1. **Quy trình A — Quản trị Master Data (Offline / One-Time & On-Demand):** Giải mã file `BẢNG TÍNH GIÁ SWIND chuẩn 2026.xls` **chỉ làm 1 lần duy nhất** để tạo bộ file `Master Data` tĩnh (`Agent 00`), trừ khi có yêu cầu của khách hàng/người dùng cập nhật giá một mặt hàng nào đó (`Agent 09` / `tool_price_updater.py`).
2. **Quy trình B — Lập Báo Giá Dự Án từ BOQ Khách Hàng (`Agent 01` $\to$ `Agent 08`):** Chỉ nhận file **BOQ của khách hàng**, phân tích kỹ thuật, bóc tách BOM và **áp giá trực tiếp dựa theo bộ file `Master Data` đã có sẵn**.

---

## 🔒 QUY TRÌNH A (ĐỘC LẬP): QUẢN TRỊ MASTER DATA (`AGENT 00` & `AGENT 09`)
- **Giải mã Bảng tính chuẩn 1 lần duy nhất (`Agent 00` - [`src/agent_00_data_miner.py`](file:///Users/hoangan/work/swind/src/agent_00_data_miner.py)):**
  - Chỉ chạy **1 lần duy nhất** khi thiết lập hệ thống để quét 17 sheets của file `BẢNG TÍNH GIÁ SWIND chuẩn 2026.xls` (phá merge cell an toàn 5 lớp) và kết xuất bộ file `Master Data` chuẩn tại `data/master_data/` (`master_database_tech.json`, `master_database_price.json`, `master_bom_rules.json`, `subtype_rules.json`, `accessory_rules.json`, `financial_policy.json`).
- **Cập nhật giá theo yêu cầu (`Agent 09` - [`src/agent_09_price_learner.py`](file:///Users/hoangan/work/swind/src/agent_09_price_learner.py) / [`src/tool_price_updater.py`](file:///Users/hoangan/work/swind/src/tool_price_updater.py)):**
  - Chỉ kích hoạt khi người dùng/khách hàng có yêu cầu cập nhật đơn giá một mặt hàng mới hoặc thay đổi giá vật tư trong Sheet `06_BANG_GIA_VAT_TU_AP_DUNG` vào kho `data/master_data/prices/` theo cơ chế Append-only Audit.

---

## 🚀 QUY TRÌNH B (LUỒNG CHÍNH): LẬP BÁO GIÁ TỪ BOQ KHÁCH HÀNG (`AGENT 01` $\to$ `AGENT 08`)

### 🛑 GATE 1: NHẬN FILE BOQ KHÁCH HÀNG, RÀ SOÁT NGỮ NGHĨA & KIỂM TOÁN ĐẦU VÀO (`AGENT 01, 02, 03`)
- **Bước 1.1 (`Agent 01` - [`src/agent_01_boq_extractor.py`](file:///Users/hoangan/work/swind/src/agent_01_boq_extractor.py)):**
  - Nhận file BOQ của khách hàng, tự động nhận diện Sheet kỹ thuật HVAC, phá merge BOQ đầu vào, ghép ngữ cảnh dòng cha-con và giải mã tập trung 1 lần duy nhất hồ sơ kỹ thuật (`resolved_spec`).
- **Bước 1.2 (`Agent 02` - [`src/agent_02_boq_reviewer.py`](file:///Users/hoangan/work/swind/src/agent_02_boq_reviewer.py)):**
  - Rà soát mặt hàng lạ (`KHAC`), gợi ý phân loại ngữ nghĩa (HITL) và lưu từ khóa theo cơ chế **Two-Tier Learning** (`boq_keyword_learning.json` & `pending_approval_queue.json`).
- **Bước 1.3 (`Agent 03` - [`src/agent_03_input_auditor.py`](file:///Users/hoangan/work/swind/src/agent_03_input_auditor.py)):**
  - Kiểm toán 4 trục kỹ thuật đầu vào:
    1. Số lượng hợp lệ ($>0$).
    2. Kích thước hình học & **cảnh báo gõ nhầm kích thước lẻ** (ví dụ `110x350` thay vì `1100x350`).
    3. Bẫy đơn vị tính (`m2` vs `Cái/Bộ`).
    4. Tiêu chuẩn PCCC (`EI60/90/120`, cầu chì $72^\circ\text{C}$).
  - Xuất biên bản `INPUT_AUDIT_REPORT.json`.

---

### 🛑 GATE 2: CHẾ TẠO BOM 3 XƯỞNG & ÁP GIÁ TỪ MASTER DATA CÓ SẴN (`AGENT 04, 05, 06, 07`)
- **Bước 2.1 (3 Xưởng BOM Cơ khí — Đọc định mức & giá từ `Master Data` có sẵn):**
  - **`Agent 04` ([`src/agent_04_bom_duct.py`](file:///Users/hoangan/work/swind/src/agent_04_bom_duct.py)):** Bóc tách Xưởng Ống gió, Phụ kiện Box tôn, Khớp nối mềm Canvas, Hộp/Vách tiêu âm (`01_BOC_TACH_ONG`).
  - **`Agent 05` ([`src/agent_05_bom_damper.py`](file:///Users/hoangan/work/swind/src/agent_05_bom_damper.py)):** Bóc tách Xưởng Van gió & PCCC EI (`VCD`, `NRD`, `MD`, `FD`, `MFD` đơn cánh `FSLF24V` & đa cánh `BFN 24`) (`03_BOC_TACH_VAN`).
  - **`Agent 06` ([`src/agent_06_bom_diffuser.py`](file:///Users/hoangan/work/swind/src/agent_06_bom_diffuser.py)):** Bóc tách Xưởng Cửa gió nhôm định hình (`SWL`, `SEEG`, `SLB`, `SCD`, `SAG/DAG`, `SOBD`, `LCCT`, `Filter G4`) (`02_BOC_TACH_CUA`).
- **Bước 2.2 (`Agent 07` - [`src/agent_07_excel_builder.py`](file:///Users/hoangan/work/swind/src/agent_07_excel_builder.py)):**
  - Áp giá trực tiếp từ bộ file `Master Data` đã có sẵn và xuất bản Workbook Dự toán **9 Sheets** với 100% công thức sống, bao gồm 2 Sheet Báo giá gửi khách hàng (`BG Đơn Cánh ĐC FSLF 24V` và `BG Đa Cánh BFN 24`).

---

### 🛑 GATE 3: KIỂM TOÁN ĐỘC LẬP 3 TẦNG (`AGENT 08`)
- **Bước 3.1 (`Agent 08` - [`src/agent_08_qa_checker.py`](file:///Users/hoangan/work/swind/src/agent_08_qa_checker.py)):**
  - Kiểm toán độc lập 3 tầng trên Workbook Excel (Mã vật tư `MAT_ID`, Định mức $>0$, Công thức liên kết `SUMIF`/`INDEX-MATCH`).
  - Cấp chứng chỉ `QA_PASSED` và xuất `QA_Audit_Report_<timestamp>.json` & `FINAL_QUOTATION_AUDIT_REPORT.json`.
