# KẾ HOẠCH NÂNG CẤP HỆ THỐNG SWIND - PHASE 3 (AI LEARNING & INTERACTION - AGENT 00..09)

Bản kế hoạch này giải quyết 3 bài toán chiến lược để biến Swind thành một "Hệ thống AI tự học" (Agentic System) với kiến trúc 10 Agent chuẩn hóa (`Agent 00` $\to$ `Agent 09`).

---

## 1. LƯU TRỮ VÀ TÁI SỬ DỤNG GIÁ HÀNG THƯƠNG MẠI (`AGENT 09`)

- **Tách biệt Database:** Lưu trữ độc lập trong thư mục `data/master_data/`:
  - `master_commercial_tech.json` (Lưu thông tin kỹ thuật hàng thương mại).
  - `master_commercial_price.json` & `prices/master_commercial_price_<timestamp>.json` (Lưu lịch sử giá hàng thương mại).
- **Tự động Học giá (`Agent 09` - [`src/agent_09_price_learner.py`](file:///Users/hoangan/work/swind/src/agent_09_price_learner.py)):**
  - Khi User điền đơn giá (`> 0`) vào Sheet `06_BANG_GIA_VAT_TU_AP_DUNG` của file Excel Báo giá, chạy lệnh:
    ```bash
    ./venv/bin/python3 src/agent_09_price_learner.py "<path_to_excel_file>"
    ```
  - `Agent 09` tự động trích xuất các mặt hàng có giá mới và lưu thành phiên bản file mới có gắn timestamp trong `data/master_data/prices/` (cơ chế Append-only Audit, tuyệt đối không ghi đè file lịch sử cũ).

---

## 2. CƠ CHẾ XÁC NHẬN "HUMAN-IN-THE-LOOP" (HITL) CHO BOQ (`AGENT 02`)

- **Module thực thi:** `Agent 02` ([`src/agent_02_boq_reviewer.py`](file:///Users/hoangan/work/swind/src/agent_02_boq_reviewer.py))
- **Cảnh báo & Phân loại:**
  - Tự động phát hiện các mặt hàng rơi vào nhóm `KHAC` và so khớp độ tương đồng ngữ nghĩa với Master Catalog.
  - Hỗ trợ tương tác trực tiếp với User hoặc chạy chế độ `--auto-accept`.
- **Two-Tier Learning (Học máy 2 tầng chống đầu độc dữ liệu):**
  - Tầng 1: Lưu vào `data/master_data/boq_keyword_learning.json` để áp dụng ngay cho dự án.
  - Tầng 2: Ghi nhận vào `data/master_data/pending_approval_queue.json` với trạng thái `PENDING_APPROVAL` để Kỹ sư trưởng phê duyệt.

---

## 3. CẬP NHẬT GIÁ BẰNG NGÔN NGỮ TỰ NHIÊN (`src/tool_price_updater.py`)

- Hỗ trợ tìm kiếm đồng thời (Dual Search) trong cả `master_database_tech.json` (Vật tư sản xuất) và `master_commercial_tech.json` (Vật tư thương mại).
- Mọi cập nhật giá đều tuân thủ cơ chế **Append-only Audit** vào thư mục `data/master_data/prices/`, và `load_master_data()` trong `src/swind_master_runner.py` tự động nạp phiên bản giá có timestamp mới nhất.
