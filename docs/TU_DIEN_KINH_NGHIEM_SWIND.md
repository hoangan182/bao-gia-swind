# TỪ ĐIỂN KINH NGHIỆM & XỬ LÝ NGOẠI LỆ (SWIND)
> **Mục đích:** File này được AI Agent tự động ghi chép lại mỗi khi gặp một ngoại lệ (sản phẩm lạ, kích thước quá khổ) và đã được User phê duyệt cách giải quyết.
> **Nguyên tắc cốt lõi:** Khi Agent gặp lại trường hợp tương tự trong tương lai, Agent sẽ đọc file này để gợi ý (Cảnh báo Vàng), nhưng **BẮT BUỘC PHẢI HỎI LẠI USER** chứ không được tự động áp dụng để tránh sai sót.

---

## 1. Danh sách sản phẩm / Từ khóa từng được định nghĩa (Data Mapping)

| Từ khóa thô (Khách hàng) | Tên chuẩn / Mã nội bộ (Swind) | Chủng loại | Ngày ghi nhận |
| :--- | :--- | :--- | :--- |
| *(Chưa có dữ liệu - Agent sẽ tự động điền vào đây khi phát sinh)* | | | |

---

## 2. Các quy tắc tính toán Phi tiêu chuẩn (Custom BOM Rules)

| Tình huống ngoại lệ | Quy tắc đã từng được áp dụng | Ghi chú / Điều kiện | Ngày ghi nhận |
| :--- | :--- | :--- | :--- |
| *(Ví dụ: Ống gió > 2000mm)* | *(Ví dụ: Chia đôi thành 2 ống, hoặc nhân hệ số 1.5)* | *(Ví dụ: User phê duyệt cho dự án XXX)* | |

---

## 3. Kiến trúc & Thiết kế hệ thống (Architectural Rules)

| Quyết định Kiến trúc | Vấn đề giải quyết | Quy định bắt buộc | Ngày ghi nhận |
| :--- | :--- | :--- | :--- |
| **Tách biệt Master Data: Kỹ Thuật và Giá** | Chống "ô nhiễm dữ liệu" (Data Contamination) khi người dùng cập nhật giá hàng tháng vô tình làm hỏng các hằng số kỹ thuật (barem, hao hụt). Dễ dàng debug lỗi tiền vs lỗi khối lượng. | Bắt buộc tách thành 2 luồng: `Sheet 05` (chứa hằng số kỹ thuật) và `Sheet 06` (chứa Đơn giá). Excel BOM phải dùng `XLOOKUP` trỏ đúng vào 2 sheet này. | 2026-10-10 |

---

## Lịch sử thay đổi (Log)
- **2026-10-10:** Ghi nhận quy tắc Tách biệt Master Data (Kỹ thuật và Giá) theo yêu cầu User để chống ô nhiễm dữ liệu.
- **Tạo mới:** Khởi tạo Từ điển Kinh nghiệm, đảm bảo tính an toàn "Human-in-the-loop".
