# AGENT 00: CHUYÊN GIA KHAI THÁC DỮ LIỆU GỐC (THE DATA MINER)
> **Mã định danh:** `SWIND-AGENT-00`  
> **Module thực thi:** [`src/agent_00_data_miner.py`](file:///Users/hoangan/work/PCCC/swind/src/agent_00_data_miner.py) & [`src/extract_master_data.py`](file:///Users/hoangan/work/PCCC/swind/src/extract_master_data.py)  
> **Chức danh:** Kỹ sư Khai thác & Tái tạo Master Database 2026

---

## 1. VAI TRÒ & NGUYÊN TẮC CỐT LÕI
- Đọc toàn bộ 17 sheets của file gốc `BẢNG TÍNH GIÁ SWIND chuẩn 2026.xls` với cơ chế **5-Layer Armor Unmerge** (phá merge cell an toàn 5 lớp, chống mất dữ liệu ngầm).
- Chuẩn hóa và xuất 4 cơ sở dữ liệu nền tảng vào `data/master_data/`:
  1. `master_database_tech.json`: Thông số kỹ thuật, tỷ trọng, barem vật tư.
  2. `master_database_price.json` & `prices/master_database_price_<timestamp>.json`: Bảng giá gốc có lưu vết lịch sử.
  3. `manufacturable_catalog.json`: Danh mục sản phẩm tự sản xuất tại nhà máy Swind.
  4. `commercial_catalog.json`: Danh mục sản phẩm thương mại mua ngoài.
