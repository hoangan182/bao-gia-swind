# KẾ HOẠCH TRIỂN KHAI MASTER RUNNER ĐIỀU PHỐI TỔNG THỂ (SWIND UNIFIED PIPELINE - TÁCH BIỆT 2 QUY TRÌNH)

## 1. MỤC TIÊU VÀ BỐI CẢNH
Tách biệt hoàn toàn hệ thống thành **2 quy trình độc lập**:
- **Quy trình A — Quản trị Master Data (Offline / One-Time & On-Demand):** Việc giải mã file `BẢNG TÍNH GIÁ SWIND chuẩn 2026.xls` **chỉ làm 1 lần duy nhất** bởi **`Agent 00`** (`src/agent_00_data_miner.py`) để sinh ra bộ file `Master Data` tĩnh trong `data/master_data/`. Khi khách hàng/người dùng có yêu cầu cập nhật giá một mặt hàng nào đó, chỉ cần kích hoạt **`Agent 09`** (`src/agent_09_price_learner.py`) hoặc `src/tool_price_updater.py`.
- **Quy trình B — Lập Báo Giá Dự Án từ BOQ Khách Hàng (`Agent 01` $\to$ `Agent 08`):** Đầu não **`src/swind_master_runner.py`** (Master Orchestrator) **chỉ nhận file BOQ của khách hàng**, phân tích kỹ thuật, bóc tách BOM 3 xưởng và **áp giá trực tiếp dựa theo bộ file `Master Data` đã có sẵn**, xuất xưởng Workbook Dự toán **9 Sheets** đạt chuẩn kiểm toán `QA_PASSED`.

---

## 2. KIẾN TRÚC ĐIỀU PHỐI TÁCH BIỆT 2 QUY TRÌNH

### A. QUY TRÌNH A: QUẢN TRỊ MASTER DATA (`AGENT 00` & `AGENT 09`)
1. **`Agent 00` (`src/agent_00_data_miner.py` — Chạy 1 lần duy nhất):** Giải mã file `BẢNG TÍNH GIÁ SWIND chuẩn 2026.xls` (17 sheets, phá merge 5 lớp) $\to$ Xuất bộ `Master Data` tĩnh (`master_database_tech.json`, `master_database_price.json`, `master_bom_rules.json`, `subtype_rules.json`, `accessory_rules.json`, `financial_policy.json`).
2. **`Agent 09` (`src/agent_09_price_learner.py` — Chỉ chạy khi có yêu cầu update giá):** Học đơn giá vật tư mới/cập nhật giá từ Sheet `06_BANG_GIA_VAT_TU_AP_DUNG` theo cơ chế Append-only Audit (`data/master_data/prices/`).

### B. QUY TRÌNH B: LUỒNG CHÍNH BÁO GIÁ TỪ BOQ KHÁCH HÀNG (`AGENT 01` $\to$ `AGENT 08` — `src/swind_master_runner.py`)
1. **`Agent 01` (`src/agent_01_boq_extractor.py`):**
   - Nhận file BOQ của khách hàng, tự động nhận diện Sheet kỹ thuật HVAC (`auto_detect_hvac_sheets()`).
   - Phá merge BOQ, ghép ngữ cảnh cha-con và **giải mã tập trung 1 lần duy nhất (`enrich_all_items` / `resolve_item_spec`)** toàn bộ thông số kỹ thuật (`subtype`, `model_fslf`, `model_bfn`, `brand`, `a1, a2, b1, b2`, `modul`, `l_col`, `thk_col`, `has_obd`, `has_mesh`, `has_filter`, `is_double_layer`, `is_black_2nd_layer`).
2. **`Agent 02` (`src/agent_02_boq_reviewer.py`):**
   - Quét mặt hàng chưa rõ phân nhóm (`KHAC`), gợi ý phân loại theo độ tương đồng ngữ nghĩa (HITL) và lưu từ khóa theo cơ chế **Two-Tier Learning**.
3. **`Agent 03` (`src/agent_03_input_auditor.py`):**
   - Kiểm toán BOQ đầu vào 4 trục + cảnh báo gõ nhầm kích thước lẻ (như `110x350`) $\to$ Xuất `INPUT_AUDIT_REPORT.json`.
4. **`Agent 04`, `Agent 05`, `Agent 06` (3 Xưởng Bóc tách BOM Cơ khí — Đọc từ `Master Data` có sẵn):**
   - `Agent 04` (`src/agent_04_bom_duct.py`): Bóc tách Ống gió, Phụ kiện Box, Canvas, Tiêu âm (`01_BOC_TACH_ONG`).
   - `Agent 05` (`src/agent_05_bom_damper.py`): Bóc tách Van gió (`VCD`, `NRD`, `MD`) & Van PCCC (`FD`, `MFD` đơn cánh `FSLF24V` / đa cánh `BFN 24`) (`03_BOC_TACH_VAN`).
   - `Agent 06` (`src/agent_06_bom_diffuser.py`): Bóc tách Cửa gió nhôm định hình (`SWL`, `SEEG`, `SLB`, `SCD`, `SAG/DAG`, `SOBD`, `LCCT`, `Filter G4`) (`02_BOC_TACH_CUA`).
5. **`Agent 07` (`src/agent_07_excel_builder.py`):**
   - Áp giá trực tiếp từ `Master Data` có sẵn và xuất bản Workbook Dự toán **9 Sheets** (gồm 2 Sheet Báo giá gửi khách hàng `BG Đơn Cánh ĐC FSLF 24V` & `BG Đa Cánh BFN 24` liên kết công thức sống 100%).
6. **`Agent 08` (`src/agent_08_qa_checker.py`):**
   - Kiểm toán độc lập 3 tầng trên Workbook Excel & cấp chứng chỉ `QA_PASSED`.

---

## 3. TRẠNG THÁI THỰC THI & NGHIỆM THU
- [x] Tách biệt hoàn toàn **Quy trình A (Tạo Master Data 1 lần bởi `Agent 00` & Update giá theo yêu cầu bởi `Agent 09`)** và **Quy trình B (Nhận BOQ khách hàng $\to$ Phân tích & Áp giá từ Master Data có sẵn bởi `Agent 01` $\to$ `Agent 08`)**.
- [x] Loại bỏ 100% giá vật tư hardcode trong các Agent Xưởng (`Agent 04, 05, 06`); toàn bộ đơn giá và quy tắc định mức được nạp từ `data/master_data/*.json`.
- [x] Kiểm thử End-to-End trên dự án `Haus_Dalat` (287 hạng mục BOQ, 1.647 linh kiện BOM): Đạt `QA_PASSED` trong **~5.2 giây**, độ lệch tổng giá trị báo giá **$-0.07\%$** (`BFN 24`) và **$-0.59\%$** (`FSLF 24V`).
