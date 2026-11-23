# Thiết kế: Phân vai Title / Dòng + Bắt lỗi sai dấu BOQ

Ngày: 2026-11-23 · Nguồn: User (dự án Ống thông gió.xls — Title "Của gió kèm hộp gió kích thước:" ra ống gió vuông)

## 1. Vì sao

- BOQ gõ sai chính tả gây sai giá mà **không có cảnh báo**: Title "Của gió kèm hộp gió" → 64 dòng cửa bị báo thành ống gió vuông, Kiểm soát cuối vẫn ✅.
- Quan hệ Title ↔ Dòng đang xử lý bằng chuỗi `if` rải rác trong `swind_boq_parser.py` (≈ dòng 446–498) + `VG-02A` (van) + `CG-05` (cửa). Ca chưa có ngoại lệ thì Title thắng lặng lẽ.

## 2. Mục tiêu / Không làm / Thất bại nếu

**Mục tiêu**
1. Một chỗ duy nhất quyết định Title hay Dòng quyết định loại hàng, theo 4 loại User nêu (bảng §4).
2. Ca không chắc → **tô vàng Sheet `BG` + `⚠️ [HỎI LẠI USER]` ở Kiểm soát cuối**, không đoán lặng lẽ.
3. Bắt được lỗi **sai dấu** ở từ khóa chính (`của gió`, `cửa giò`, `ông gió`...), không chỉ chữ không dấu.

**Không làm**: không đổi công thức giá; không đổi quy tắc kế thừa thông số (OBD / LCCT / G4 / EI / độ dày / tăng áp) đã có; không ghi lại nội dung BOQ.

**Thất bại nếu**: dự án cũ đã duyệt đổi giá mà không giải thích được; hoặc cảnh báo vàng tràn lan (dòng hợp lệ kiểu `CG-01 600x300` bị hỏi lại).

## 3. Cách làm đã chọn

User chốt 2026-11-23: "cứ làm theo hướng đề xuất".

| Phương án | Mô tả | Đánh giá |
|---|---|---|
| **A. Phân vai + bảng quyết định (chọn)** | Module mới `src/title_row_resolver.py` + rule `data/master_data/title_row_rules.json` (mỗi rule có `id`, `nguon`, `ly_do`, `vi_du_dung`, `vi_du_sai` như các bộ phân loại khác). Parser gọi resolver ở các điểm đang dùng `sec_lower` / `full_name_lower` để lấy loại hàng. | Đúng kiến trúc hiện có (diffuser/damper/duct/scope classifier), test được từng ô |
| B. Thêm `if` vào parser cho từng ca | Nhanh | Chính là "rule chồng rule" đang muốn bỏ |
| C. Chỉ thêm cảnh báo, không đổi luồng | Ít rủi ro | Không giải quyết loại 2, không chặn loại 4 |

## 4. Phân vai và bảng quyết định

**Vai của Title** (xét trên chuỗi đã chuẩn hóa chính tả):
- `LOAI_HANG`: chứa từ khóa loại hàng Swind (cửa / miệng gió, louver, van, ống, cút, côn, hộp gió, LCCT, tiêu âm...), lấy từ các bộ phân loại sẵn có.
- `PHU_KIEN`: chỉ có thông số / phụ kiện (OBD, LCCT, G4, EI, độ dày, tăng áp / hút khói), không có loại hàng.
- `HANG_MUC`: không chứa loại hàng: hạng mục / khu vực / hệ thống (`Hệ thống ...`, `Tầng ...`, `Khu vực ...`, `Lắp đặt ...`, `Hệ thống điều hòa`, `Thông gió ...`).

**Vai của Dòng** (chỉ chữ của chính dòng: Tên + Ghi chú + Model):
- `DU_LOAI`: bộ nhận diện ra được loại hàng (kể cả hàng thương mại theo từ khóa rõ ràng: giá đỡ, bộ nguồn, ống nước...).
- `CHI_KT`: sau khi bỏ kích thước, mã ký hiệu ngắn (`CG-01`, `S2`, `+F`), từ chỉ vị trí (tầng, phòng, căn, trục, hành lang...) thì không còn chữ nào.
- `KHONG_NHAN_RA`: còn chữ riêng nhưng không bộ nhận diện nào hiểu.

| Title \ Dòng | `DU_LOAI` | `CHI_KT` | `KHONG_NHAN_RA` |
|---|---|---|---|
| `LOAI_HANG` cùng nhóm | **Loại 1**: ghép bộ (như hiện tại) | **Loại 3**: theo Title | **Loại 4**: **không báo**, tô vàng `⚠️ HỎI LẠI: dòng không rõ, Title là <X> — báo theo Title?` |
| `LOAI_HANG` khác nhóm | Dòng thắng (quy tắc 1a, như hiện tại) | — | (như ô trên) |
| `PHU_KIEN` | Dòng + kế thừa thông số (như hiện tại) | **Hỏi lại**: Title không có loại hàng | Như hiện tại (KHAC → Agent 02) |
| `HANG_MUC` | **Loại 2**: chỉ theo dòng, Title không đóng góp nhóm hàng | **Hỏi lại**: Title không có loại hàng | Như hiện tại (KHAC → Agent 02) |

- **Loại 4 xác nhận**: User duyệt bằng cờ mới `--title-wins "<Sheet>!<dòng>,..."`, khi đó dòng báo theo Title. Không có cờ thì dòng không báo, vẫn tô vàng, Kiểm soát cuối in `⚠️ [HỎI LẠI USER]` (không chặn, không mã thoát 2).
- **Ô "Hỏi lại" của `CHI_KT`**: đây là lưới an toàn cho Title gõ sai mà sửa chính tả không bắt được. Dòng không được tự gán ống gió vuông nữa.

## 5. Bắt lỗi sai dấu (TY-05, thêm vào `typo_rules.json` / `typo_normalizer.py`)

- Danh sách **cụm từ khóa chính** (`cum_chinh`): cửa gió, miệng gió, ống gió, van gió, hộp gió, lưới chắn, côn trùng, tiêu âm, chặn lửa, một chiều, động cơ, khuếch tán, nan bầu dục, sọt trứng, louver...
- Khi một cụm trong Tên / Title / Ghi chú bỏ dấu thì trùng cụm chính, nhưng dấu khác (VD `của gió`, `cửa giò`, `ông gió`) và chữ không nằm trong `giu_dau` → thay trong **chuỗi so khớp**, ghi sự kiện `DOAN` → tô vàng `⚠️ ĐÃ HIỂU: "của gió" = "cửa gió" — xin xác nhận` + `⚠️ [ĐÃ ĐOÁN — XÁC NHẬN]` ở Kiểm soát cuối. Lỗi ở Title thì tô vàng mọi dòng con.
- Duyệt bằng `agent_02_boq_reviewer.py --approve-pending` → ghi vào TY-01 (lần sau sửa lặng lẽ), giống luồng mã gõ sai TY-03/04 hiện có.
- Chạy sau TY-01 / TY-02, trước TY-04. TY-02 (chữ hoàn toàn không dấu) giữ nguyên, sửa lặng lẽ.

## 6. Ràng buộc

- AGENTS.md mục 7: truy nguồn từng nhánh `if` trong parser bị thay (`git log -S`), giữ đúng ca cũ bằng rẽ nhánh. Riêng fallback `sec_lower` chứa `ống gió / thông gió / hút mùi bếp / hút mùi wc` → ONG_GIO phải giữ cho đúng các dự án đã sinh ra nó.
- Cột / dòng ẩn: vẫn bỏ qua, không đưa vào phân vai.
- Kiểm thử: unit test mới `tests/test_swind_title_row_rules.py` (mỗi ô bảng §4 ≥ 1 ví dụ đúng + 1 ví dụ sai), `tests/test_swind_typo_rules.py` thêm TY-05; self-test; E2E 50 dự án × 2 baseline (mặc định & `--include-duct`); mọi file lệch phải giải thích được. Cập nhật `03_FORMULA_INDEX.md` và AGENTS.md (mục 1a, 2c).

## 7. Quyết định của Claude (User kiểm tra lại)

1. Định nghĩa `CHI_KT` cho phép mã ký hiệu ngắn + từ vị trí, để tránh hỏi lại tràn lan.
2. Loại 4 mặc định **không báo + tô vàng** (theo yêu cầu "phải hỏi lại mới được làm"), không chặn xuất file.
3. Title `PHU_KIEN` / `HANG_MUC` + dòng `CHI_KT` → hỏi lại thay vì đoán.
4. TY-05 chỉ áp cho danh sách cụm chính, không áp cho mọi chữ (tránh `ống luồn` ↔ `ống lượn`).

## 8. Để lại cho người làm

Tên hàm, vị trí gọi trong parser, cách truyền sự kiện tô vàng (dùng lại `tag_typo_events` / `bg_flag`), cách đọc cờ `--title-wins` trong runner (theo mẫu `--override`).
