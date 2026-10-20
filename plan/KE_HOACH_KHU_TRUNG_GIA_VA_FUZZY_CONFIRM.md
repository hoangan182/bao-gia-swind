# KẾ HOẠCH TRIỂN KHAI VẤN ĐỀ 5: KHỬ TRÙNG BẢNG GIÁ (DEDUPLICATION) & AN TOÀN FUZZY MATCHING

## 1. MỤC TIÊU VÀ BỐI CẢNH
Hiện tại hệ thống định giá có 2 rủi ro kỹ thuật:
1. **Trùng lặp mã vật tư trong Sheet 06 (Duplicate MAT_ID):**
   Trong `load_master_data()`, giá từ `master_database_price` và `master_commercial_price` được gộp bằng `price.extend(...)`. Nếu một mã vật tư xuất hiện ở cả hai nguồn hoặc được cập nhật nhiều lần, Sheet 06 sẽ có nhiều dòng mang cùng một mã `MAT_ID`. Các hàm tra cứu trong Excel (`XLOOKUP`, `VLOOKUP`, `INDEX/MATCH`) sẽ luôn lấy dòng đầu tiên, dẫn đến việc đơn giá mới nhất bị phớt lờ.
2. **Rủi ro cập nhật sai giá do Fuzzy Matching quá thấp (0.40):**
   Trong `tool_semantic_price_updater.py`, ngưỡng khớp lệnh chat đang là `0.40`. Độ tương đồng giữa "Van gió FD" và "Van gió VCD", hay "Tôn 0.75" và "Tôn 0.95" đều > 0.60. Do đó, câu lệnh cập nhật giá ngắn có thể khớp nhầm sản phẩm và tự động ghi đè giá vào file Audit mà không có bước xác nhận.

Mục tiêu của Vấn đề 5:
- Triển khai cơ chế **Deduplication (Khử trùng lặp)** tuyệt đối cho Sheet 06: Mỗi `MAT_ID` chỉ xuất hiện đúng 1 lần với mức giá mới nhất.
- Nâng ngưỡng tin cậy Fuzzy Match lên $\ge 0.65$ và bổ sung cơ chế xác nhận người dùng (Human Confirmation Gate) trước khi sinh file giá mới.

---

## 2. NGUYÊN TẮC THIẾT KẾ

### 2.1. Khử trùng lặp bảng giá (Price Deduplication Engine)
- Khi nạp dữ liệu giá từ các nguồn (Internal DB, Commercial DB, BOQ Missing items):
  - Sử dụng cơ chế Key-Value Mapping theo `MAT_ID`.
  - Nguồn giá thương mại mới nhất được ưu tiên ghi đè lên giá cũ nếu trùng mã.
  - Mỗi mã vật tư trong Sheet `06_BANG_GIA_VAT_TU_AP_DUNG` là duy nhất 100%.

### 2.2. Siết chặt an toàn cập nhật giá bằng NLP (Semantic Price Guard)
- Ngưỡng tối thiểu: `score >= 0.65` (nếu < 0.65 $\rightarrow$ Từ chối cập nhật và báo không tìm thấy).
- Hiển thị đầy đủ thông tin đối soát:
  - Mã: `[MAT_ID]`
  - Tên vật tư: `[Name]`
  - Đơn giá hiện tại: `[Old_Price] VNĐ` $\rightarrow$ Đơn giá mới: `[New_Price] VNĐ`
  - Độ tin cậy khớp: `[Score %]`
- Bổ sung xác nhận `[Y/N]` trước khi xuất file audit mới vào thư mục `data/master_data/prices/`.

---

## 3. CÁC BƯỚC THỰC THI CHI TIẾT

- [x] **Bước 5.1:** Cập nhật hàm `load_master_data()` và phương thức nạp giá Sheet 06 trong `src/swind_master_runner.py` và `src/run_estimation_pipeline.py` để khử trùng lặp (Deduplicate) theo `MAT_ID`.
- [x] **Bước 5.2:** Nâng cấp `src/tool_semantic_price_updater.py`:
  - Nâng ngưỡng tương đồng tối thiểu từ 0.40 lên 0.65.
  - Bổ sung bước xác nhận người dùng `[Y/N]` trước khi ghi file.
  - Bổ sung metadata ghi vết (thời gian, giá cũ, độ tin cậy).
- [x] **Bước 5.3:** Chạy kiểm thử End-to-End với Master Runner: Xác minh Sheet 06 đạt **Zero duplicates** (483 mã vật tư duy nhất 100%).
- [x] **Bước 5.4:** Chạy thử nghiệm tool cập nhật giá `tool_semantic_price_updater.py`:
  - Từ khóa lạ: Bị từ chối an toàn (< 65%).
  - Từ khóa chuẩn: Hiển thị bảng đối soát đầy đủ và yêu cầu xác nhận trước khi lưu Audit file mới.
- [x] **Bước 5.5:** Nghiệm thu và cập nhật tài liệu kế hoạch: Cấp chứng chỉ QA_PASSED 100%.
