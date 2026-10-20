# HỆ THỐNG MULTI-AGENT DỰ TOÁN BÓC TÁCH SWIND (HVAC ESTIMATION MAS - AGENT 00..09)

> Tài liệu này đóng vai trò là bản đồ chỉ dẫn và quy chế kích hoạt cho Hệ thống Multi-Agent của Swind đã được chuẩn hóa đánh số tuần tự từ **`Agent 00` đến `Agent 09`**, và **tách biệt rõ ràng thành 2 quy trình độc lập**:
> 1. **Quy trình A — Quản trị Master Data (Offline / One-Time & On-Demand):** Giải mã file `BẢNG TÍNH GIÁ SWIND chuẩn 2026.xls` **chỉ làm 1 lần duy nhất** để tạo bộ file `Master Data` tĩnh (`Agent 00`), và chỉ cập nhật khi có yêu cầu đổi/thêm giá mặt hàng (`Agent 09` / `tool_price_updater.py`).
> 2. **Quy trình B — Lập Báo Giá Dự Án từ BOQ Khách Hàng (`Agent 01` $\to$ `Agent 08`):** Dưới sự điều phối của **Master Orchestrator** ([`src/swind_master_runner.py`](file:///Users/hoangan/work/swind/src/swind_master_runner.py)), hệ thống **chỉ nhận file BOQ của khách hàng**, phân tích kỹ thuật, bóc tách BOM và **áp giá trực tiếp dựa theo bộ file `Master Data` đã có sẵn**.

---

## 1. PHÂN TÁCH 2 QUY TRÌNH & DANH SÁCH 10 AGENT (`AGENT 00` $\to$ `AGENT 09`)

### A. QUY TRÌNH A — QUẢN TRỊ MASTER DATA (CHẠY 1 LẦN DUY NHẤT HOẶC KHI CÓ YÊU CẦU CẬP NHẬT GIÁ)

| Agent ID | Tên gọi chuẩn | Module Thực thi | Chế độ Kích hoạt | Vai trò & Nhiệm vụ Đơn lẻ (Single Responsibility) | File Đặc tả Vai trò |
| :---: | :--- | :--- | :---: | :--- | :--- |
| **Agent 00** | **Data Miner (One-Time)** | [`src/agent_00_data_miner.py`](file:///Users/hoangan/work/swind/src/agent_00_data_miner.py) | **Chạy 1 lần duy nhất** | Giải mã 17 sheets của file `BẢNG TÍNH GIÁ SWIND chuẩn 2026.xls` (phá merge 5 lớp) $\to$ Kết xuất bộ file `Master Data` tĩnh (`master_database_tech.json`, `master_database_price.json`, `master_bom_rules.json`, `subtype_rules.json`, `accessory_rules.json`, `financial_policy.json`). | [agent_00_data_miner_role.md](file:///Users/hoangan/work/swind/.agents/roles/agent_00_data_miner_role.md) |
| **Agent 09** | **Price Learner (On-Demand)** | [`src/agent_09_price_learner.py`](file:///Users/hoangan/work/swind/src/agent_09_price_learner.py) / [`src/tool_price_updater.py`](file:///Users/hoangan/work/swind/src/tool_price_updater.py) | **Chỉ chạy khi có yêu cầu update giá** | Cập nhật đơn giá mặt hàng mới hoặc điều chỉnh giá vật tư theo yêu cầu khách hàng/người dùng vào kho `data/master_data/prices/` theo cơ chế Append-only Audit. | [agent_09_price_learner_role.md](file:///Users/hoangan/work/swind/.agents/roles/agent_09_price_learner_role.md) |

---

### B. QUY TRÌNH B — LẬP BÁO GIÁ DỰ ÁN TỪ BOQ KHÁCH HÀNG (`AGENT 01` $\to$ `AGENT 08`)

> **Luồng chạy hàng ngày cho mọi dự án mới:** Chỉ nhận file **BOQ của khách hàng** $\to$ Phân tích $\to$ Tính định mức BOM $\to$ Áp giá theo bộ file `Master Data` đã có sẵn (`data/master_data/*.json`). Tuyệt đối không giải mã lại file Bảng tính chuẩn `.xls`.

| Agent ID | Tên gọi chuẩn | Module Thực thi | Vai trò & Nhiệm vụ Đơn lẻ (Single Responsibility) | File Đặc tả Vai trò |
| :---: | :--- | :--- | :--- | :--- |
| **Orchestrator** | **Master Orchestrator** | [`src/swind_master_runner.py`](file:///Users/hoangan/work/swind/src/swind_master_runner.py) | Điều phối tuần tự luồng báo giá dự án từ `Agent 01` đến `Agent 08` dựa trên bộ `Master Data` có sẵn. | [orchestrator_role.md](file:///Users/hoangan/work/swind/.agents/roles/orchestrator_role.md) |
| **Agent 01** | **BOQ Extractor & Spec Resolver** | [`src/agent_01_boq_extractor.py`](file:///Users/hoangan/work/swind/src/agent_01_boq_extractor.py) | Nhận file BOQ khách hàng, tự động dò Sheet HVAC, phá merge BOQ, ghép ngữ cảnh cha-con và **giải mã tập trung 1 lần duy nhất (`resolved_spec`)** toàn bộ thông số kỹ thuật (`Model`, `A1, A2, B1, B2`, `Modul`, `L`, `Độ dày`, `OBD/LCCT/Filter`). | [agent_01_boq_extractor_role.md](file:///Users/hoangan/work/swind/.agents/roles/agent_01_boq_extractor_role.md) |
| **Agent 02** | **BOQ Reviewer (HITL)** | [`src/agent_02_boq_reviewer.py`](file:///Users/hoangan/work/swind/src/agent_02_boq_reviewer.py) | Rà soát mặt hàng lạ (`KHAC`), gợi ý phân nhóm ngữ nghĩa và lưu từ khóa theo cơ chế **Two-Tier Learning** (`boq_keyword_learning.json` & `pending_approval_queue.json`). | [agent_02_boq_reviewer_role.md](file:///Users/hoangan/work/swind/.agents/roles/agent_02_boq_reviewer_role.md) |
| **Agent 03** | **Input Auditor (4-Axis)** | [`src/agent_03_input_auditor.py`](file:///Users/hoangan/work/swind/src/agent_03_input_auditor.py) | Kiểm toán BOQ đầu vào 4 trục: Số lượng, Hình học + **cảnh báo gõ nhầm kích thước lẻ** (như `110x350`), Bẫy ĐVT (`m2` vs `Cái`), PCCC (`EI`) $\to$ Xuất `INPUT_AUDIT_REPORT.json`. | [agent_03_input_auditor_role.md](file:///Users/hoangan/work/swind/.agents/roles/agent_03_input_auditor_role.md) |
| **Agent 04** | **Ductwork BOM Maker** | [`src/agent_04_bom_duct.py`](file:///Users/hoangan/work/swind/src/agent_04_bom_duct.py) | Bóc tách định mức **Xưởng Ống gió, Phụ kiện ống, Khớp nối mềm Canvas & Hộp/Vách tiêu âm** (`01_BOC_TACH_ONG`) dựa theo định mức trong `master_bom_rules.json`. | [agent_04_bom_duct_role.md](file:///Users/hoangan/work/swind/.agents/roles/agent_04_bom_duct_role.md) |
| **Agent 05** | **Damper & PCCC BOM Maker** | [`src/agent_05_bom_damper.py`](file:///Users/hoangan/work/swind/src/agent_05_bom_damper.py) | Bóc tách định mức **Xưởng Van gió & Van PCCC EI** (`VCD`, `NRD`, `MD`, `FD`, `MFD` đơn cánh `FSLF24V` & đa cánh `BFN 24`) (`03_BOC_TACH_VAN`) dựa theo định mức & đơn giá trong `Master Data` có sẵn. | [agent_05_bom_damper_role.md](file:///Users/hoangan/work/swind/.agents/roles/agent_05_bom_damper_role.md) |
| **Agent 06** | **Diffuser & Grille BOM Maker** | [`src/agent_06_bom_diffuser.py`](file:///Users/hoangan/work/swind/src/agent_06_bom_diffuser.py) | Bóc tách định mức **Xưởng Cửa gió & Miệng gió nhôm định hình** (`SWL`, `SEEG`, `SLB`, `SCD`, `SAG/DAG`, `SOBD`, `LCCT`, `Filter G4`) (`02_BOC_TACH_CUA`) dựa theo định mức & đơn giá trong `Master Data` có sẵn. | [agent_06_bom_diffuser_role.md](file:///Users/hoangan/work/swind/.agents/roles/agent_06_bom_diffuser_role.md) |
| **Agent 07** | **Excel Publisher (9 Sheets)** | [`src/agent_07_excel_builder.py`](file:///Users/hoangan/work/swind/src/agent_07_excel_builder.py) | Áp giá từ `Master Data` có sẵn và xuất bản Workbook Dự toán **9 Sheets** (gồm 2 Sheet Báo giá khách hàng `BG Đơn Cánh ĐC FSLF 24V` & `BG Đa Cánh BFN 24` liên kết công thức sống 100%). | [agent_07_excel_builder_role.md](file:///Users/hoangan/work/swind/.agents/roles/agent_07_excel_builder_role.md) |
| **Agent 08** | **Independent QA Checker** | [`src/agent_08_qa_checker.py`](file:///Users/hoangan/work/swind/src/agent_08_qa_checker.py) | Kiểm toán độc lập 3 tầng trên Workbook Excel (Mã vật tư, Thứ nguyên định mức, Công thức sống) $\to$ Cấp chứng chỉ `QA_PASSED`. | [agent_08_qa_checker_role.md](file:///Users/hoangan/work/swind/.agents/roles/agent_08_qa_checker_role.md) |

---

## 2. NGUYÊN TẮC VẬN HÀNH BẤT BIẾN (CORE PROTOCOLS)

1. **Tách Biệt Tuyệt Đối Quy trình Tạo Master Data và Quy trình Báo Giá BOQ:**
   - Giải mã file `BẢNG TÍNH GIÁ SWIND chuẩn 2026.xls` (`Agent 00`) **chỉ thực hiện 1 lần duy nhất** để tạo bộ `Master Data` chuẩn trong `data/master_data/`.
   - Khi lập báo giá dự án mới (`Agent 01` $\to$ `Agent 08`), hệ thống **chỉ nhận file BOQ của khách hàng**, phân tích và tra cứu định mức/đơn giá trực tiếp từ bộ file `Master Data` đã có sẵn (không bao giờ đọc lại file `.xls` chuẩn, không hardcode giá vật tư trong code).
   - Khi khách hàng/người dùng có yêu cầu cập nhật giá một mặt hàng nào đó, chỉ cần kích hoạt `Agent 09` (`agent_09_price_learner.py`) hoặc `tool_price_updater.py` để tạo bản ghi giá mới trong `data/master_data/prices/`.
2. **Giải mã Kỹ thuật Tập trung 1 Lần (Single Source of Truth tại Agent 01):**
   - `Agent 01` giải mã tập trung toàn bộ hồ sơ kỹ thuật (`resolved_spec`) cho mỗi dòng BOQ của khách hàng.
   - Các `Agent 04, 05, 06` (Xưởng BOM) và `Agent 07` (Excel Publisher) sử dụng trực tiếp `resolved_spec`, tuyệt đối không giải mã lặp lại.
3. **Chuyên môn hóa 3 Xưởng Sản xuất (`Agent 04`, `Agent 05`, `Agent 06`):**
   - Tách biệt hoàn toàn định mức cơ khí của 3 xưởng: Ống gió (`Agent 04`), Van gió & PCCC (`Agent 05`), và Cửa gió nhôm (`Agent 06`).
4. **Nguyên tắc Excel-First 9 Sheets với Công thức Sống 100% (`Agent 07` & `Agent 08`):**
   - Xuất đồng thời 2 phương án Báo giá gửi khách hàng (`BG Đơn Cánh ĐC FSLF 24V` và `BG Đa Cánh BFN 24`) liên kết trực tiếp bằng công thức sống và được `Agent 08` kiểm toán độc lập 3 tầng.

---

## 3. TÀI LIỆU QUY CHUẨN ĐI KÈM
- **Kế hoạch Kiến trúc Multi-Agent chuẩn hóa (`Agent 00` – `Agent 09`):** [KE_HOACH_XAY_DUNG_MULTI_AGENT_SWIND.md](file:///Users/hoangan/work/swind/docs/KE_HOACH_XAY_DUNG_MULTI_AGENT_SWIND.md)
- **Kế hoạch Thiết kế Workbook Excel & Master Data:** [KE_HOACH_THIET_KE_EXCEL_BOC_TACH_VA_MASTER_DATA.md](file:///Users/hoangan/work/swind/plan/KE_HOACH_THIET_KE_EXCEL_BOC_TACH_VA_MASTER_DATA.md)
- **Quy trình tổng thể (SOP):** [KE_HOACH_BOC_TACH_VA_TONG_HOP_BOM_SWIND.md](file:///Users/hoangan/work/swind/docs/KE_HOACH_BOC_TACH_VA_TONG_HOP_BOM_SWIND.md)
- **Ghi chú Giả định Hệ thống:** [SYSTEM_ASSUMPTIONS_AND_NOTES.md](file:///Users/hoangan/work/swind/docs/SYSTEM_ASSUMPTIONS_AND_NOTES.md)
- **Từ điển kinh nghiệm & ngoại lệ:** [TU_DIEN_KINH_NGHIEM_SWIND.md](file:///Users/hoangan/work/swind/TU_DIEN_KINH_NGHIEM_SWIND.md)
