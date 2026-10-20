# AGENT 09: CHUYÊN VIÊN HỌC GIÁ VẬT TƯ THƯƠNG MẠI (COMMERCIAL PRICE LEARNER)
> **Mã định danh:** `SWIND-AGENT-09`  
> **Module thực thi:** [`src/agent_09_price_learner.py`](file:///Users/hoangan/work/swind/src/agent_09_price_learner.py)  
> **Chức danh:** Chuyên viên Học Giá Thương mại & Lưu vết Kiểm toán (Append-Only Price Learner)

---

## 1. VAI TRÒ & NHIỆM VỤ CỐT LÕI
- Quét Sheet `06_BANG_GIA_VAT_TU_AP_DUNG` sau khi Kỹ sư dự toán điền đơn giá cho các mặt hàng thương mại/phát sinh mới (`> 0`).
- Tự động cập nhật danh mục kỹ thuật vào `data/master_data/master_commercial_tech.json`.
- Thực thi cơ chế **Append-Only Price Audit**: Tuyệt đối không ghi đè mất lịch sử giá cũ; luôn tạo phiên bản file mới kèm timestamp tại `data/master_data/prices/master_commercial_price_<timestamp>.json`.
