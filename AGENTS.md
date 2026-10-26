# HỆ THỐNG MULTI-AGENT DỰ TOÁN BÓC TÁCH SWIND (HVAC ESTIMATION MAS - AGENT 00..09)

## ⚡ QUY TẮC TỐC ĐỘ TỐI ĐA KHI CHẠY BÁO GIÁ (FAST-PATH EXECUTION — ĐỌC ĐẦU TIÊN)

1. **Hệ thống báo giá tự động Swind (`src/swind_master_runner.py` và chuỗi `agent_01..08.py`) ĐÃ HOÀN CHỈNH 100%.**
2. **Khi người dùng yêu cầu *"Chạy báo giá dự án..."*, *"Tính giá file..."*, *"Lập báo giá..."*:**
   - **TUYỆT ĐỐI KHÔNG** dùng `read_file` hay `grep` để đọc lại mã nguồn `src/swind_master_runner.py` hay `src/agent_01..08.py` để "nắm cấu trúc hệ thống" trước khi chạy (chỉ đọc code khi có yêu cầu sửa lỗi/thêm tính năng).
   - **CHẠY NGAY LẬP TỨC** câu lệnh CLI sau bằng `run_command`:
     ```bash
     ./venv/bin/python src/swind_master_runner.py "<đường_dẫn_file_BOQ>" --non-interactive --auto-accept [các_cờ_tùy_chọn]
     ```
     *(Hoặc `python3 src/swind_master_runner.py ...` — script đã tự động kích hoạt `./venv/bin/python`).*
   - **TUYỆT ĐỐI KHÔNG** viết thêm script Python phụ để mở lại file `_BAO_GIA.xlsx` đọc giá sau khi chạy xong! `src/swind_master_runner.py` đã tự động in trực tiếp **BẢNG TỔNG HỢP GIÁ TRỊ BÁO GIÁ DỰ ÁN** (Số dòng, Trước VAT, VAT 8%, Tổng sau VAT) và đường dẫn **File Báo Giá Cuối Cùng** ở định dạng Markdown ngay trên màn hình console.
   - **QUY TẮC XUẤT BÁO CÁO CHO NGƯỜI DÙNG:**
     1. **Chỉ liệt kê duy nhất File Báo Giá Cuối Cùng** (`<Project_Name>_BAO_GIA.xlsx`), tuyệt đối không liệt kê hàng loạt các file báo giá thành phần hay file dự toán nội bộ trung gian.
     2. **Về giá trị: Chỉ in Bảng Tổng Hợp** (theo các sheet/phân khu và Tổng cộng toàn dự án), **bỏ Bảng kết quả báo giá chi tiết** từng mặt hàng.

### Bảng tham số CLI đầy đủ của `src/swind_master_runner.py`:
- `--non-interactive`: **(Bắt buộc khi AI chạy)** Chạy tự động hoàn toàn (Headless mode), không chờ nhập từ bàn phím.
- `--auto-accept`: **(Bắt buộc khi AI chạy)** Tự động đồng ý gợi ý phân loại mặt hàng của Agent 02.
- `--sheets "Sheet1,Sheet2"`: Chỉ định danh sách Sheet kỹ thuật cần xử lý (ngăn cách bằng dấu phẩy). Mặc định: Tự động dò tất cả Sheet kỹ thuật HVAC.
- `--only-cua-van`: Chỉ lọc và báo giá **Cửa gió & Van gió** (`CUA_GIO`, `VAN_GIO`), loại bỏ Ống gió và Hàng thương mại mua ngoài.
- `--motor-brand <BELIMO|KLB|HONEYWELL>`: Chỉ định hãng động cơ van theo yêu cầu (Mặc định: `BELIMO` nếu BOQ không ghi rõ).
- `--mfd-model <1.01|1.02|1.03|1.04|1.05>`: Chỉ định mã đốt van MFD theo yêu cầu (`1.01`: Belimo BFN24 EI120, `1.02`: Belimo FSLF24V EI90 [Mặc định], `1.03`: KLB 5Nm EI90, `1.04`: Honeywell MS4609 EI60, `1.05`: Belimo BFN24 EI120).
- `--dual-options`: Tính đồng thời 2 phương án Đơn cánh và Đa cánh (Mặc định: Báo giá chuẩn theo BOQ).
- `--merge-sheets`: Gộp tất cả các sheet vào 1 file duy nhất (Mặc định: Tách riêng từng sheet).
- `--allow-ei`: Cờ tương thích cho phép áp giá chống cháy EI (Mặc định Swind tự động nhận diện EI theo BOQ).

---

## 1. PHÂN TÁCH 2 QUY TRÌNH & DANH SÁCH 10 AGENT (`AGENT 00` $\to$ `AGENT 09`)

### A. QUY TRÌNH A — QUẢN TRỊ MASTER DATA (CHẠY 1 LẦN DUY NHẤT HOẶC KHI CÓ YÊU CẦU CẬP NHẬT GIÁ)

| Agent ID | Tên gọi chuẩn | Module Thực thi | Chế độ Kích hoạt | Vai trò & Nhiệm vụ Đơn lẻ (Single Responsibility) | File Đặc tả Vai trò |
| :---: | :--- | :--- | :---: | :--- | :--- |
| **Agent 00** | **Data Miner (One-Time)** | [`src/agent_00_data_miner.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_00_data_miner.py) | **Chạy 1 lần duy nhất** | Giải mã 17 sheets của file `BẢNG TÍNH GIÁ SWIND chuẩn 2026.xls` (phá merge 5 lớp) $\to$ Kết xuất bộ file `Master Data` tĩnh (`master_database_tech.json`, `master_database_price.json`, `master_bom_rules.json`, `subtype_rules.json`, `accessory_rules.json`, `financial_policy.json`). | [agent_00_data_miner_role.md](file:///Users/hoangan/work/PCCC/swind/.agents/roles/agent_00_data_miner_role.md) |
| **Agent 09** | **Price Learner (On-Demand)** | [`src/agent_09_price_learner.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_09_price_learner.py) / [`src/tool_price_updater.py`](file:///Users/hoangan/work/PCCC/swind/src/tool_price_updater.py) | **Chỉ chạy khi có yêu cầu update giá** | Cập nhật đơn giá mặt hàng mới hoặc điều chỉnh giá vật tư theo yêu cầu khách hàng/người dùng vào kho `data/master_data/prices/` theo cơ chế Append-only Audit. | [agent_09_price_learner_role.md](file:///Users/hoangan/work/PCCC/swind/.agents/roles/agent_09_price_learner_role.md) |

---

### B. QUY TRÌNH B — LẬP BÁO GIÁ DỰ ÁN TỪ BOQ KHÁCH HÀNG (`AGENT 01` $\to$ `AGENT 08`)

> **Luồng chạy hàng ngày cho mọi dự án mới:** Chỉ nhận file **BOQ của khách hàng** $\to$ Phân tích $\to$ Tính định mức BOM $\to$ Áp giá theo bộ file `Master Data` đã có sẵn (`data/master_data/*.json`). Tuyệt đối không giải mã lại file Bảng tính chuẩn `.xls`.

| Agent ID | Tên gọi chuẩn | Module Thực thi | Vai trò & Nhiệm vụ Đơn lẻ (Single Responsibility) | File Đặc tả Vai trò |
| :---: | :--- | :--- | :--- | :--- |
| **Orchestrator** | **Master Orchestrator** | [`src/swind_master_runner.py`](file:///Users/hoangan/work/PCCC/swind/src/swind_master_runner.py) | Điều phối tuần tự luồng báo giá dự án từ `Agent 01` đến `Agent 08` dựa trên bộ `Master Data` có sẵn, xuất file `_BAO_GIA.xlsx` và in trực tiếp bảng kết quả báo giá ra màn hình console. | [orchestrator_role.md](file:///Users/hoangan/work/PCCC/swind/.agents/roles/orchestrator_role.md) |
| **Agent 01** | **BOQ Extractor & Spec Resolver** | [`src/agent_01_boq_extractor.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_01_boq_extractor.py) | Nhận file BOQ khách hàng, tự động dò Sheet HVAC, phá merge BOQ, ghép ngữ cảnh cha-con và **giải mã tập trung 1 lần duy nhất (`resolved_spec`)** toàn bộ thông số kỹ thuật (`Model`, `A1, A2, B1, B2`, `Modul`, `L`, `Độ dày`, `OBD/LCCT/Filter`). | [agent_01_boq_extractor_role.md](file:///Users/hoangan/work/PCCC/swind/.agents/roles/agent_01_boq_extractor_role.md) |
| **Agent 02** | **BOQ Reviewer (HITL)** | [`src/agent_02_boq_reviewer.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_02_boq_reviewer.py) | Rà soát mặt hàng lạ (`KHAC`), gợi ý phân nhóm ngữ nghĩa và lưu từ khóa theo cơ chế **Two-Tier Learning** (`boq_keyword_learning.json` & `pending_approval_queue.json`). | [agent_02_boq_reviewer_role.md](file:///Users/hoangan/work/PCCC/swind/.agents/roles/agent_02_boq_reviewer_role.md) |
| **Agent 03** | **Input Auditor (4-Axis)** | [`src/agent_03_input_auditor.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_03_input_auditor.py) | Kiểm toán BOQ đầu vào 4 trục: Số lượng, Hình học + **cảnh báo gõ nhầm kích thước lẻ** (như `110x350`), Bẫy ĐVT (`m2` vs `Cái`), PCCC (`EI`) $\to$ Xuất `INPUT_AUDIT_REPORT.json`. | [agent_03_input_auditor_role.md](file:///Users/hoangan/work/PCCC/swind/.agents/roles/agent_03_input_auditor_role.md) |
| **Agent 04** | **Ductwork BOM Maker** | [`src/agent_04_bom_duct.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_04_bom_duct.py) | Bóc tách định mức **Xưởng Ống gió, Phụ kiện ống, Khớp nối mềm Canvas & Hộp/Vách tiêu âm** (`01_BOC_TACH_ONG`) dựa theo định mức trong `master_bom_rules.json`. | [agent_04_bom_duct_role.md](file:///Users/hoangan/work/PCCC/swind/.agents/roles/agent_04_bom_duct_role.md) |
| **Agent 05** | **Damper & PCCC BOM Maker** | [`src/agent_05_bom_damper.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_05_bom_damper.py) | Bóc tách định mức **Xưởng Van gió & Van PCCC EI** (`VCD`, `NRD`, `MD`, `FD`, `MFD` đơn cánh `FSLF24V` & đa cánh `BFN 24`) (`03_BOC_TACH_VAN`) dựa theo định mức & đơn giá trong `Master Data` có sẵn. | [agent_05_bom_damper_role.md](file:///Users/hoangan/work/PCCC/swind/.agents/roles/agent_05_bom_damper_role.md) |
| **Agent 06** | **Diffuser & Grille BOM Maker** | [`src/agent_06_bom_diffuser.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_06_bom_diffuser.py) | Bóc tách định mức **Xưởng Cửa gió & Miệng gió nhôm định hình** (`SWL`, `SEEG`, `SLB`, `SCD`, `SAG/DAG`, `SOBD`, `LCCT`, `Filter G4`) (`02_BOC_TACH_CUA`) dựa theo định mức & đơn giá trong `Master Data` có sẵn. | [agent_06_bom_diffuser_role.md](file:///Users/hoangan/work/PCCC/swind/.agents/roles/agent_06_bom_diffuser_role.md) |
| **Agent 07** | **Excel Publisher (9 Sheets)** | [`src/agent_07_excel_builder.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_07_excel_builder.py) | Áp giá từ `Master Data` có sẵn và xuất bản Workbook Dự toán **9 Sheets** (liên kết công thức sống 100%). | [agent_07_excel_builder_role.md](file:///Users/hoangan/work/PCCC/swind/.agents/roles/agent_07_excel_builder_role.md) |
| **Agent 08** | **Independent QA Checker** | [`src/agent_08_qa_checker.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_08_qa_checker.py) | Kiểm toán độc lập 3 tầng trên Workbook Excel (Mã vật tư, Thứ nguyên định mức, Công thức sống) $\to$ Cấp chứng chỉ `QA_PASSED`. | [agent_08_qa_checker_role.md](file:///Users/hoangan/work/PCCC/swind/.agents/roles/agent_08_qa_checker_role.md) |
