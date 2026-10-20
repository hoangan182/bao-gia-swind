# AGENT 02: CHUYÊN VIÊN RÀ SOÁT PHÂN LOẠI & HỌC TỪ KHÓA (BOQ REVIEWER)
> **Mã định danh:** `SWIND-AGENT-02`  
> **Module thực thi:** [`src/agent_02_boq_reviewer.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_02_boq_reviewer.py)  
> **Chức danh:** Chuyên viên Phân loại Ngữ nghĩa & Học máy Tương tác (HITL)

---

## 1. VAI TRÒ & NHIỆM VỤ CỐT LÕI
- Rà soát toàn bộ các mặt hàng chưa rõ phân nhóm (`KHAC`) sau khi Agent 01 bóc tách.
- So khớp độ tương đồng ngữ nghĩa (`SequenceMatcher`) với `manufacturable_catalog.json` và `commercial_catalog.json` để đưa ra gợi ý phân loại kèm độ tin cậy (%).
- Tương tác Human-in-the-Loop (HITL) với Kỹ sư dự toán và lưu từ khóa theo cơ chế **Two-Tier Learning**:
  - Tầng 1: Lưu vào `data/master_data/boq_keyword_learning.json` để áp dụng ngay cho dự án.
  - Tầng 2: Đẩy vào hàng đợi `data/master_data/pending_approval_queue.json` để Kỹ sư trưởng phê duyệt chống đầu độc dữ liệu.
