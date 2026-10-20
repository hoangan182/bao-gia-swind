# KẾ HOẠCH TRIỂN KHAI VẤN ĐỀ 3: CHUẨN HÓA MÃ VẬT TƯ TIẾNG VIỆT & CHỐNG TRÙNG MÃ (VIETNAMESE SLUGIFIER)

## 1. MỤC TIÊU VÀ BỐI CẢNH
Hiện tại, khi bóc tách các mặt hàng mới hoặc hàng thương mại từ BOQ, hệ thống dùng hàm Regex thô:
`re.sub(r'[^a-zA-Z0-9]', '_', name.strip().upper())[:25]`

**Hậu quả:**
1. Toàn bộ chữ cái tiếng Việt có dấu (`à, á, ả, ã, ạ, ă, â, đ, è, é, ê, ô, ơ, ư...`) bị thay thế bằng dấu gạch dưới `_`.
   - *"Quạt hướng trục CEF-B2-Z1"* $\rightarrow$ `QU_T_H__NG_TR_C_CEF_B2_Z1`
   - *"Lưới bảo vệ"* $\rightarrow$ `L__I_B_O_V_`
   - *"Cắt đục, đóng lưới trám trét"* $\rightarrow$ `CHI_PH__C_T___C____NG_L__`
   Người dùng mở bảng giá (Sheet 06) không thể nhận diện được mặt hàng để định giá.
2. Việc cắt ngắn thô bạo `[:15]` hoặc `[:25]` ký tự dễ gây **xung đột mã (collision)** giữa các sản phẩm có cùng phần đầu.

Mục tiêu của Vấn đề 3 là xây dựng bộ chuyển đổi ký tự tiếng Việt chuẩn (Vietnamese Slugifier), loại bỏ hoàn toàn mã rác ký tự, bảo toàn ngữ nghĩa tên gọi cho con người đọc hiểu, và đảm bảo tính duy nhất tuyệt đối của mã `MAT_ID`.

---

## 2. NGUYÊN TẮC THIẾT KẾ BỘ SLUGIFIER

### 2.1. Bảng ánh xạ ký tự tiếng Việt toàn diện (Diacritics Mapping)
- Ánh xạ đầy đủ bảng mã Unicode (cả bảng mã dựng sẵn Composed và tổ hợp Decomposed) sang bảng chữ cái ASCII không dấu:
  - `a, à, á, ả, ã, ạ, ă, ắ, ằ, ẳ, ẵ, ặ, â, ấn, ầ, ẩ, ẫ, ậ` $\rightarrow$ `A`
  - `d, đ` $\rightarrow$ `D`
  - `e, è, é, ẻ, ẽ, ẹ, ê, ế, ề, ể, ễ, ệ` $\rightarrow$ `E`
  - `i, ì, í, ỉ, ĩ, ị` $\rightarrow$ `I`
  - `o, ò, ó, ỏ, õ, ọ, ô, ố, ồ, ổ, ỗ, ộ, ơ, ớ, ờ, ở, ỡ, ợ` $\rightarrow$ `O`
  - `u, ù, ú, ủ, ũ, ụ, ư, ứ, ừ, ử, ữ, ự` $\rightarrow$ `U`
  - `y, ỳ, ý, ỷ, ỹ, ỵ` $\rightarrow$ `Y`

### 2.2. Quy tắc định dạng mã `MAT_ID`
1. Thay thế các ký tự đặc biệt, dấu cách, dấu phẩy thành dấu gạch dưới `_`.
2. Gộp các dấu gạch dưới liên tiếp (`___`) thành 1 dấu gạch dưới duy nhất `_`.
3. Giữ độ dài tối đa hợp lý (ví dụ: 45 ký tự) nhưng bảo toàn trọn vẹn từ ngữ.
4. Chống trùng lặp (Collision Prevention): Nếu tên dài hơn giới hạn cắt, tự động gắn hậu tố băm ngắn (hash 4 ký tự) ở cuối để đảm bảo hai mặt hàng khác nhau không bao giờ bị trùng mã.

---

## 3. CÁC BƯỚC THỰC THI CHI TIẾT

- [x] **Bước 3.1:** Xây dựng module tiện ích `src/swind_utils.py` chứa hàm `vietnamese_slugify(text, max_len=45, add_hash=True)`.
- [x] **Bước 3.2:** Tích hợp hàm `vietnamese_slugify` vào:
  - `src/swind_master_runner.py` (tại các điểm sinh mã `MAT_ID` cho hàng thương mại, ống mềm, phụ kiện).
  - `src/run_estimation_pipeline.py`.
  - `src/agent_03_price_learner.py`.
- [x] **Bước 3.3:** Dọn dẹp và chuẩn hóa lại các mã rác cũ trong `data/master_data/master_commercial_tech.json` và `master_commercial_price_*.json` (chuyển `MAT-KHAC-L__I_B_O_V_` thành `MAT-KHAC-LUOI_BAO_VE`).
- [x] **Bước 3.4:** Chạy kiểm thử End-to-End với Master Runner và kiểm tra Sheet 05/06: 100% mã sinh ra đều rõ ràng, sáng sủa, không còn ký tự rác.
- [x] **Bước 3.5:** Đánh giá kết quả: Cấp chứng chỉ QA_PASSED 100%. Tất cả các mã thương mại và phụ kiện đều có ID chuẩn ngữ nghĩa tiếng Việt không dấu kèm hash chống trùng mã.
