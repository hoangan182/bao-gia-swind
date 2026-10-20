# KẾ HOẠCH XÂY DỰNG HỆ THỐNG MULTI-AGENT CHO SWIND (PHIÊN BẢN v3.1 - TÁCH BIỆT 2 QUY TRÌNH: MASTER DATA & BÁO GIÁ BOQ)
> **Mục tiêu cốt lõi:**
> 1. **Tách biệt hoàn toàn 2 quy trình độc lập:**
>    - **Quy trình A — Quản trị Master Data (Offline / One-Time & On-Demand):** Giải mã file `BẢNG TÍNH GIÁ SWIND chuẩn 2026.xls` **chỉ thực hiện 1 lần duy nhất** (`Agent 00`) để sinh ra bộ file `Master Data` tĩnh (`data/master_data/*.json`), trừ khi có yêu cầu của khách hàng/người dùng cập nhật đơn giá một mặt hàng nào đó (`Agent 09` / `tool_price_updater.py`).
>    - **Quy trình B — Lập Báo Giá Dự Án từ BOQ Khách Hàng (`Agent 01` $\to$ `Agent 08`):** Chỉ nhận file **BOQ của khách hàng**, phân tích thông số kỹ thuật, tính định mức cơ khí và **áp giá trực tiếp dựa theo bộ file `Master Data` đã có sẵn** (tuyệt đối không giải mã lại file Bảng tính chuẩn `.xls`).
> 2. Chuẩn hóa danh pháp từ **`Agent 00` đến `Agent 09`** (loại bỏ hoàn toàn tên phụ `0A`, `0B`, `0.5`, `1A/1B/1C`), mỗi Agent đảm nhiệm đúng 1 vai trò đơn lẻ (Single Responsibility).

---

## PHẦN I: SƠ ĐỒ KIẾN TRÚC TÁCH BIỆT 2 QUY TRÌNH ĐỘC LẬP

```
=====================================================================================
 QUY TRÌNH A: QUẢN TRỊ MASTER DATA (CHẠY 1 LẦN DUY NHẤT HOẶC KHI CẦN UPDATE GIÁ)
=====================================================================================
┌─────────────────────────────────────────┐       ┌─────────────────────────────────┐
│     AGENT 00: DATA MINER (CHẠY 1 LẦN)   │       │  AGENT 09: PRICE LEARNER        │
│  Giải mã 1 lần 'BẢNG TÍNH GIÁ SWIND     │       │  (CHỈ KHI CÓ YÊU CẦU UPDATE GIÁ)│
│  chuẩn 2026.xls' (17 Sheets, Unmerge)   │       │  Cập nhật giá mặt hàng mới/đổi  │
└────────────────────┬────────────────────┘       └────────────────┬────────────────┘
                     │                                             │
                     ▼                                             ▼
      ╔═════════════════════════════════════════════════════════════════════════╗
      ║          KHO MASTER DATA CÓ SẴN (data/master_data/*.json)               ║
      ║  • master_database_tech.json  • master_database_price.json (prices/)    ║
      ║  • master_bom_rules.json      • subtype_rules.json & financial_policy   ║
      ╚══════════════════════════════════════╤══════════════════════════════════╝
                                             │ (Chỉ đọc & Tra cứu trực tiếp)
=============================================│=======================================
 QUY TRÌNH B: LẬP BÁO GIÁ TỪ BOQ KHÁCH HÀNG  │ (LUỒNG CHẠY HÀNG NGÀY: AGENT 01 -> 08)
=============================================▼=======================================
┌───────────────────────────────────────────────────────────────────────────────────┐
│   ĐẦU VÀO: FILE BOQ CỦA KHÁCH HÀNG  ──►  MASTER ORCHESTRATOR (swind_master_runner)│
└──────┬──────────────────┬──────────────────┬──────────────────┬───────────────────┘
       │                  │                  │                  │
       ▼                  ▼                  ▼                  ▼
┌──────────────┐   ┌──────────────┐   ┌──────────────┐   ┌──────────────────────────┐
│   AGENT 01   │   │   AGENT 02   │   │   AGENT 03   │   │    XƯỞNG BOM CƠ KHÍ      │
│ BOQ Extractor├──►│ BOQ Reviewer ├──►│Input Auditor ├──►│ • Agent 04: Ống & Tiêu âm│
│ & Spec       │   │ & Two-Tier   │   │ (Kiểm toán   │   │ • Agent 05: Van & PCCC EI│
│ Resolver     │   │ Learning     │   │  4 Trục BOQ) │   │ • Agent 06: Cửa gió nhôm │
└──────────────┘   └──────────────┘   └──────────────┘   └─────────────┬────────────┘
                                                                       │
       ┌───────────────────────────────────────────────────────────────┘
       ▼
┌──────────────────────────────────────────┐     ┌──────────────────────────────────┐
│                 AGENT 07                 │     │             AGENT 08             │
│ Excel Publisher (Áp giá từ Master Data)  ├────►│ Independent QA Checker           │
│ • Xuất 9 Sheets (BG Đơn Cánh FSLF 24V    │     │ • Kiểm toán 3 tầng độc lập       │
│   & BG Đa Cánh BFN 24 + BOM 00..06)      │     │ • Cấp chứng chỉ QA_PASSED        │
└──────────────────────────────────────────┘     └──────────────────────────────────┘
```

---

## PHẦN II: CHI TIẾT VAI TRÒ TỪNG QUY TRÌNH & TỪNG AGENT

### I. QUY TRÌNH A — QUẢN TRỊ MASTER DATA (`Agent 00` & `Agent 09`)
> **Nguyên tắc:** Không nằm trong luồng chạy báo giá hàng ngày. Chỉ tạo **1 lần duy nhất** ra bộ file `Master Data` chuẩn, hoặc chỉ kích hoạt khi khách hàng/người dùng có yêu cầu cập nhật giá mặt hàng.

* **`Agent 00` (`Agent00_DataMiner` - [`src/agent_00_data_miner.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_00_data_miner.py)) — Chạy 1 lần duy nhất:**
  - Giải mã file Excel gốc `BẢNG TÍNH GIÁ SWIND chuẩn 2026.xls` (17 sheets, phá merge cell 5 lớp) **1 lần duy nhất** để sinh ra bộ file `Master Data` tĩnh trong `data/master_data/`:
    - `master_database_tech.json` & `master_database_price.json`
    - `master_bom_rules.json` (định mức cơ khí, hao hụt, công thức bóc tách cửa/van/ống)
    - `subtype_rules.json`, `accessory_rules.json`, `financial_policy.json`
    - `manufacturable_catalog.json` & `commercial_catalog.json`
* **`Agent 09` (`Agent09_PriceLearner` - [`src/agent_09_price_learner.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_09_price_learner.py)) & [`src/tool_price_updater.py`](file:///Users/hoangan/work/PCCC/swind/src/tool_price_updater.py) — Chạy khi có yêu cầu cập nhật giá:**
  - Khi khách hàng/người dùng yêu cầu cập nhật đơn giá một mặt hàng hoặc bổ sung giá vật tư thương mại mới từ Sheet `06_BANG_GIA_VAT_TU_AP_DUNG`, `Agent 09` cập nhật vào `data/master_data/prices/` theo cơ chế Append-only Audit (lưu vết lịch sử giá, không bao giờ ghi đè mất giá cũ).

---

### II. QUY TRÌNH B — LẬP BÁO GIÁ DỰ ÁN TỪ BOQ KHÁCH HÀNG (`Agent 01` $\to$ `Agent 08`)
> **Nguyên tắc:** Khi có dự án mới, hệ thống **chỉ nhận file BOQ của khách hàng**, phân tích kỹ thuật, bóc tách BOM và **áp giá trực tiếp dựa theo bộ file `Master Data` đã có sẵn**.

#### 1. Nhóm Phân tích & Kiểm toán BOQ Khách hàng (`Agent 01` – `Agent 03`)
* **`Agent 01` (`Agent01_BOQExtractor` - [`src/agent_01_boq_extractor.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_01_boq_extractor.py)):**
  - Nhận file BOQ của khách hàng, tự động nhận diện Sheet kỹ thuật HVAC, phá merge BOQ đầu vào, ghép ngữ cảnh dòng cha-con.
  - **Giải mã tập trung 1 lần duy nhất (`resolve_item_spec`)** toàn bộ thông số kỹ thuật (`subtype`, `model_fslf`, `model_bfn`, `brand`, `a1, a2, b1, b2`, `modul`, `l_col`, `thk_col`, `has_obd`, `has_mesh`, `has_filter`, `is_double_layer`, `is_black_2nd_layer`, `note_fslf`, `note_bfn`) dựa trên `subtype_rules.json` và `Master Data`.
* **`Agent 02` (`Agent02_BOQReviewer` - [`src/agent_02_boq_reviewer.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_02_boq_reviewer.py)):**
  - Rà soát các mặt hàng lạ (`KHAC`), gợi ý phân loại theo độ tương đồng ngữ nghĩa (HITL) và lưu từ khóa theo cơ chế **Two-Tier Learning** (`boq_keyword_learning.json` & `pending_approval_queue.json`).
* **`Agent 03` (`Agent03_InputAuditor` - [`src/agent_03_input_auditor.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_03_input_auditor.py)):**
  - Kiểm toán BOQ đầu vào trên 4 trục: (1) Số lượng hợp lệ, (2) Hình học & **cảnh báo gõ nhầm kích thước lẻ** (như `110x350` nghi gõ thiếu số `0`), (3) Bẫy ĐVT (`m2` vs `Cái`), (4) Tiêu chuẩn PCCC (`EI`). Xuất `INPUT_AUDIT_REPORT.json`.

#### 2. Nhóm 3 Xưởng Bóc tách Định mức Cơ khí (`Agent 04` – `Agent 06`)
Đọc trực tiếp quy tắc định mức từ `master_bom_rules.json` và đơn giá chuẩn từ `master_database_price.json`:
* **`Agent 04` (`Agent04_DuctworkBOM` - [`src/agent_04_bom_duct.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_04_bom_duct.py)):**
  - Xưởng Ống gió vuông/chữ nhật, Phụ kiện Box tôn, Khớp nối mềm Canvas, Hộp/Vách tiêu âm (`01_BOC_TACH_ONG`).
* **`Agent 05` (`Agent05_DamperBOM` - [`src/agent_05_bom_damper.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_05_bom_damper.py)):**
  - Xưởng Van gió (`VCD`, `NRD`, `MD`) & Van PCCC (`FD`, `MFD` chế độ đơn cánh `FSLF24V` và đa cánh `BFN 24`) (`03_BOC_TACH_VAN`).
* **`Agent 06` (`Agent06_DiffuserBOM` - [`src/agent_06_bom_diffuser.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_06_bom_diffuser.py)):**
  - Xưởng Cửa gió & Miệng gió nhôm định hình (`SWL`, `SEEG`, `SLB`, `SCD`, `SAG/DAG`, van `SOBD`, lưới `LCCT`, phin lọc `G4`) (`02_BOC_TACH_CUA`).
* **Facade tương thích ngược ([`src/swind_bom_engine.py`](file:///Users/hoangan/work/PCCC/swind/src/swind_bom_engine.py)):** Điều phối mỏng tới `Agent 04`, `Agent 05`, `Agent 06`.

#### 3. Nhóm Áp Giá Master Data, Xuất bản Excel & Kiểm toán Độc lập (`Agent 07` – `Agent 08`)
* **`Agent 07` (`Agent07_ExcelBuilder` - [`src/agent_07_excel_builder.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_07_excel_builder.py) & [`src/swind_excel_builder.py`](file:///Users/hoangan/work/PCCC/swind/src/swind_excel_builder.py)):**
  - Áp giá trực tiếp từ `Master Data` có sẵn và dựng Workbook Excel **9 Sheets** (bao gồm 2 Sheet Báo giá gửi khách hàng `BG Đơn Cánh ĐC FSLF 24V` và `BG Đa Cánh BFN 24` liên kết công thức sống 100%).
* **`Agent 08` (`Agent08_QAChecker` - [`src/agent_08_qa_checker.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_08_qa_checker.py)):**
  - Kiểm toán độc lập 3 tầng trên Workbook Excel (Mã vật tư `MAT_ID`, Định mức $>0$, Công thức sống `SUMIF`/`INDEX-MATCH`) $\to$ Cấp chứng chỉ `QA_PASSED`.

---

## PHẦN III: BỘ TIÊU CHÍ NGHIỆM THU ĐỊNH LƯỢNG (KPIS & BENCHMARK THỰC TẾ)

| STT | Tiêu chí nghiệm thu | Chỉ số mục tiêu | Kết quả kiểm chứng trên dự án Haus Dalat (287 dòng BOQ) |
| :---: | :--- | :---: | :--- |
| **1** | **Tỷ lệ rớt dòng (Missing Rows)** | **$0\%$** | Điền đầy đủ $287/287$ dòng BOQ vào cả 2 phương án báo giá. |
| **2** | **Độ lệch tổng giá trị báo giá** | **$< 1.0\%$** | **$-0.07\%$** (Phương án Đa cánh `BFN 24`) & **$-0.59\%$** (Phương án Đơn cánh `FSLF 24V`). |
| **3** | **Tốc độ xử lý toàn trình (Quy trình B)** | **$< 15\text{ giây}$** | **$\sim 5.2\text{ giây}$** (Nhận BOQ khách hàng & áp giá từ Master Data có sẵn, không giải mã lại file chuẩn). |
| **4** | **Kiểm toán công thức Excel (Agent 08)** | **$100\%\text{ QA\_PASSED}$** | $0$ lỗi Critical/High, $100\%$ công thức sống liên kết đa chiều. |
