# Hướng dẫn áp dụng kiểm thử hồi quy nhanh cho hệ thống tính giá MPrice

> Rút ra từ hệ thống báo giá Swind (đợt làm 24/11/2026). Tài liệu mô tả **cách làm** để mang sang MPrice, không phụ thuộc
> code Swind. Ở mỗi bước có ghi file và số liệu Swind để đối chiếu.

---

## 1. Bài toán

Hệ thống tính giá kiểu Swind/MPrice có 3 đặc điểm làm việc kiểm thử khó:

1. **Rule áp cho mọi dự án.** Sửa để đúng ở dự án A có thể làm sai ở dự án B mà không ai đoán trước được.
   Chỉ riêng ngày 24/11, Swind gặp 2 lần: sửa cho dự án TEF thì lộ ra lỗi ở 5 file NOVH; sửa rule
   "khuếch tán" thì đổi 49 dòng ở 13 dự án.
2. **Phải kiểm trên dữ liệu thật** (BOQ khách gửi). Test tự viết không phủ hết cách khách trình bày.
3. **Số file đầu vào tăng mãi** (100 → 1.400 → 14.000). Chạy đủ pipeline cho mọi file sau mỗi lần sửa thì thời gian
   tăng tuyến tính.

| Cách kiểm | Swind, 104 file × 2 chế độ |
|---|---|
| E2E tuần tự (ban đầu) | ~43 phút |
| E2E song song (bước 1) | ~75 giây |
| Theo mẫu dòng + bộ canh gác (bước 2–4) | ~3 giây + ~21 giây |

Ý tưởng cốt lõi: **thời gian kiểm phải tăng theo số MẪU dòng khác nhau, không theo số file.**
Ở Swind, 21.019 dòng hàng của 100 file chỉ có khoảng 2.900 mẫu (14%). Khi thêm file, số mẫu tăng chậm hơn nhiều,
vì cách khách ghi BOQ có giới hạn và lặp lại.

---

## 2. Kiến trúc kiểm thử 5 lớp

```
Lớp 0  Unit test + ví dụ trong rule      (giây)      — mỗi rule tự mang ví dụ đúng / sai
Lớp 1  E2E song song                     (phút)      — chạy đủ pipeline, nhiều tiến trình
Tầng 1 Thư viện mẫu dòng                 (1 lần/file) — đọc mỗi file 1 lần, lưu dòng + ngữ cảnh
Tầng 2 Chạy lại theo mẫu                 (giây)      — mỗi mẫu chạy 1 lần, so ảnh chụp chuẩn
Tầng 3 Bộ file canh gác                  (< 1 phút)  — ít file nhất phủ mọi rule / kết quả / bố cục
(Nền)  E2E toàn bộ định kỳ               (không chờ) — ban đêm / máy cloud
```

---

## 3. Điều kiện tiên quyết (làm trước trên MPrice)

Thiếu điều nào thì các tầng sau sẽ khó làm hoặc cho kết quả sai.

| # | Điều kiện | Vì sao cần | Swind làm thế nào |
|---|---|---|---|
| 3.1 | **Pipeline tất định**: cùng đầu vào thì ra cùng kết quả | Ảnh chụp chuẩn chỉ có nghĩa khi chạy lại không tự đổi | Không dùng thời gian / ngẫu nhiên trong kết quả |
| 3.2 | **Thư mục đầu ra cấu hình được** qua biến môi trường | Chạy kiểm thử không đè file gửi khách; chạy song song không đè nhau | `SWIND_OUTPUT_DIR` |
| 3.3 | **Công tắc tắt ghi "file học"** (từ khóa tự học, nhật ký, hàng chờ duyệt) | Nhiều tiến trình ghi chung 1 file JSON sẽ hỏng file | `SWIND_NO_LEARNING_WRITE=1`, chặn ở đầu mọi hàm ghi |
| 3.4 | **Rule là dữ liệu có ID** (JSON/bảng), không phải chuỗi `if/elif` rải rác | Để biết rule nào kích hoạt, báo rule chưa được kiểm | `diffuser_rules.json` (CG-xx), `duct_rules.json` (OG-xx), `damper_rules.json` (VG-xx) |
| 3.5 | **Bộ phân loại trả về vết rule** đã kích hoạt | Tầng 3 cần biết dòng nào chạm rule nào | `classify()` trả `rule_id` / `trail` |
| 3.6 | **Có điểm vào xử lý được 1 sheet trong RAM** với bố cục cột chỉ định | Tầng 2 dựng sheet ảo, không đọc file | `parse_sheet(..., _override_col_map, _override_header_row)` |
| 3.7 | **Hàm tính giá 1 dòng dùng chung** với luồng chính | Kết quả tầng 2 phản ánh đúng giá thật | `swind_pricing.py` (gom công thức về 1 chỗ) |

---

## 4. Bước 1 — Chạy E2E song song

**Mục tiêu:** dùng hết số nhân CPU. Đây là việc rẻ nhất mà lợi nhiều nhất, nên làm đầu tiên.

Các bước:
1. Mỗi lượt (file × chế độ) chạy pipeline trong **tiến trình con**, với thư mục đầu ra tạm riêng và công tắc tắt ghi file học.
2. Dùng hàng đợi `ThreadPoolExecutor(max_workers = số nhân − 2)`; mỗi luồng gọi `subprocess.run`.
3. **Cho file nặng chạy trước** (sắp theo dung lượng giảm dần), để cuối hàng đợi không còn 1 file lớn chạy một mình.
4. Gom kết quả xong mới in, theo thứ tự tên file, để báo cáo ổn định giữa các lần chạy.
5. **Mỗi chế độ chạy so với baseline riêng** (VD: mặc định ↔ baseline mặc định; có ống gió ↔ baseline ống gió).
   Swind từng so nhầm chế độ ống gió với baseline mặc định, nên lúc nào cũng có khoảng 40 file "lệch" giả.
6. Chụp file học trước khi chạy và khôi phục 1 lần ở cuối, làm lớp an toàn thứ hai.

**Kiểm chứng bắt buộc:** chạy tuần tự và song song trên cùng code; kết quả từng file phải **giống hệt**.

Swind: [src/swind_e2e_regression.py](../src/swind_e2e_regression.py) — `--jobs`, `--modes default,duct`, `--files-from`.
Mặc định hiện tại: toàn bộ file, cả 2 chế độ.

---

## 5. Bước 2 — Tầng 1: Thư viện mẫu dòng

**Mục tiêu:** mỗi file đầu vào chỉ đọc **1 lần**, lưu đủ thông tin để sau này chạy lại từng dòng mà không mở file.

### 5.1 Lưu gì cho mỗi dòng
- Nội dung thô **mọi ô** theo bố cục cột (tên, mô tả/spec, model, ĐVT, KL, kích thước tách cột, độ dày…).
- **Ngữ cảnh**: Title (hạng mục cha) đang áp dụng, Title tầng 2 nếu có.
- **Bố cục cột** của sheet (khóa → vị trí cột, cờ như "phiếu đặt hàng").
- Lưu **cả dòng bị lọc** (ngoài phạm vi, thiếu kích thước…), không chỉ dòng có giá. Sửa rule phạm vi có thể biến dòng
  bị lọc thành dòng có giá, và ngược lại.

### 5.2 Lấy ngữ cảnh thế nào
Thêm **móc** vào parser, chỉ bật khi xây thư viện: ở đầu vòng lặp từng dòng, ghi lại `(Title hiện tại, Title phụ)`;
khi dò xong header, ghi lại `(dòng header, bố cục cột)`. Luồng tính giá thật không bị ảnh hưởng.

### 5.3 Chữ ký mẫu
```
chữ ký = băm( Title chuẩn hóa, Title phụ chuẩn hóa,
              chữ các ô văn bản chuẩn hóa (tên, spec, model, ĐVT, ghi chú...),
              danh sách ô số CÓ giá trị (không lấy giá trị),
              bố cục cột )
chuẩn hóa = chữ thường + Unicode NFC + mọi số → "#" + gộp khoảng trắng
```
Như vậy *"Van chặn lửa 400x300"* và *"Van chặn lửa 600x500"* chung 1 mẫu; còn cùng tên mà khác Title hoặc khác bố cục
cột thì là 2 mẫu khác nhau, vì kết quả có thể khác.

### 5.4 Cập nhật tăng dần
- Nhận diện file bằng **SHA-1 nội dung**: không đổi thì bỏ qua; mới hoặc đổi thì đọc; đã xoá thì loại khỏi thư viện.
- File đọc lỗi lần trước thì **đọc lại** dù mã băm không đổi.
- Đọc song song bằng `ProcessPoolExecutor`.
- Lưu vào SQLite gồm 3 bảng `files`, `rows`, `sheet_feats`, có chỉ mục theo chữ ký.
- **Thư viện chứa dữ liệu khách → không commit** (Swind đặt trong `output/_pattern_lab/`, thư mục đã nằm trong `.gitignore`).

Swind: 100 file → 34.348 dòng → 6.787 mẫu. Đọc lần đầu 9 giây; các lần sau ~0 giây.

---

## 6. Bước 3 — Tầng 2: Chạy lại theo mẫu

**Mục tiêu:** sau khi sửa rule, biết ngay mẫu nào đổi kết quả, ảnh hưởng bao nhiêu dòng và file nào.

### 6.1 Chọn dòng đại diện
Mỗi mẫu lấy tối đa **3 dòng thật** theo cỡ: nhỏ nhất, ở giữa, lớn nhất. Giá phụ thuộc kích thước (bậc giá, ngưỡng
mô-men động cơ, cỡ cố định 600/450/300…), nên 1 dòng/mẫu là không đủ.

### 6.2 Dựng sheet ảo trong RAM
- Gom các dòng đại diện **cùng bố cục cột** vào 1 sheet ảo, khoảng 120 dòng/sheet.
- **Giữ nguyên vị trí cột gốc**, không đánh số lại: parser có nhánh đọc "cột 1" hoặc "cột kề cột Tên".
- Mỗi dòng đại diện gồm 3 dòng: 1 dòng trống ngăn cách, 1 dòng Title đang áp dụng (Title trống thì ghi Title trung tính
  để không kế thừa Title của dòng trước), rồi dòng hàng.
- Dòng 1 ghi **nhãn header thật** ("Tên vật tư", "Đơn vị", "Khối lượng"…). Bộ tự dò header vẫn chạy trước khi bị ghi đè
  bởi bố cục chỉ định, và nhãn lạ làm nó lỗi.
- Gọi parser với bố cục cột chỉ định → bộ phân loại → hàm tính giá 1 dòng.

### 6.3 Dấu vân tay kết quả (để so sánh)
`trạng thái (CÓ GIÁ / BỊ LỌC:lý do), loại hàng, subtype, Model, ghi chú, kích thước mặt/cổ, modul, độ dày, đơn giá, nguồn giá`.
Vết rule được lưu **riêng**, không đưa vào phần so sánh, để không báo "đổi" khi chỉ thứ tự vết thay đổi.

### 6.4 Ảnh chụp và so sánh
- `--set-baseline`: chụp kết quả trên code đã duyệt.
- `--check`: chạy lại rồi so → báo cáo theo mẫu (dòng đại diện, số dòng cùng mẫu, số file, trước → sau)
  và danh sách file bị ảnh hưởng (mọi file chứa mẫu đã đổi, tra qua thư viện).
- Duyệt xong thì `--set-baseline` lại.

### 6.5 Ba kiểm chứng trước khi tin công cụ

| Kiểm chứng | Cách làm | Swind |
|---|---|---|
| **Ổn định** | Chạy `--check` trên code không đổi | 0 thay đổi |
| **Độ khớp** | So kết quả sheet ảo với chạy file thật, từng dòng đại diện | 13.767/13.772 = 99,96% |
| **Bắt được lỗi** (thử đột biến) | Lấy tạm 1 rule cũ từ git (`git checkout <commit> -- <file>`), chạy `--check`, khôi phục | Bắt 30 mẫu / 119 dòng / 17 file trong 3 giây, đúng nhóm mà E2E đầy đủ tìm ra |

Swind: 13.772 dòng đại diện / 6.787 mẫu, khoảng **3 giây**.
[src/swind_pattern_lab.py](../src/swind_pattern_lab.py), [tests/test_swind_pattern_lab.py](../tests/test_swind_pattern_lab.py).

---

## 7. Bước 4 — Tầng 3: Bộ file canh gác

**Mục tiêu:** tầng 2 không bắt được lỗi phụ thuộc **bố cục cả file** (cột ẩn, bảng phụ, KL nằm ở dòng khác, form Excel…).
Cần một nhóm file chạy E2E đầy đủ, **nhỏ nhưng đại diện cho mọi thứ**.

### 7.1 Đặc trưng
- **Vết rule** từng dòng đại diện: bọc các hàm phân loại **ngay trong công cụ kiểm thử** (gán lại thuộc tính module),
  không sửa code agent. Bọc rồi thì ghi `rule_id` / `trail` vào danh sách tạm của dòng đang tính.
- **Loại kết quả**: trạng thái + lý do lọc, loại hàng, gốc Model + từng hậu tố (`+O`, `+N`…), nguồn giá.
  Không tính chữ Model của hàng thương mại (không phải mã sản phẩm, chỉ là nhiễu).
- **Bố cục sheet** (ghi lúc xây thư viện): **có / không từng loại cột**, kích thước tách cột, phiếu đặt hàng,
  cột ẩn, dòng ẩn, bảng phụ, nhiều sheet, Title 2 tầng, KL trống.
- **Không dùng tổ hợp cột chính xác** làm đặc trưng. Số tổ hợp tăng theo số file và kéo bộ canh gác phình theo
  (Swind: 35 file nếu dùng tổ hợp, 19 file nếu dùng có / không từng cột).

### 7.2 Chọn file — phủ tập tham lam
```
còn_lại = toàn bộ đặc trưng
lặp: chọn file f có  |đặc_trưng(f) ∩ còn_lại| / (1 + dung_lượng(f)/1MB)  lớn nhất
     còn_lại -= đặc_trưng(f)
đến khi còn_lại rỗng
```
Đặc trưng của file = hợp đặc trưng các mẫu có trong file + đặc trưng bố cục các sheet. Ưu tiên file nhẹ để chạy nhanh.

### 7.3 Báo chỗ hở
So danh sách rule ID trong bảng rule với các rule thực sự được kích hoạt → in **"rule chưa có file nào kiểm tới"**.
Sửa các rule đó thì bộ kiểm thử không bắt được lỗi, nên cần bổ sung BOQ mẫu khi gặp dự án có loại hàng tương ứng.
Swind hiện có 2 rule như vậy: `CG-01` (cửa kiểm tra), `CG-08A` (khuếch tán tròn).

### 7.4 Ghép vào luồng
`--check` ghi `e2e_files.txt` = file bị ảnh hưởng ∪ bộ canh gác, rồi chạy E2E song song với `--files-from`.

Swind: 19/100 file (21% dung lượng) phủ 141 đặc trưng; E2E 2 chế độ khoảng **21 giây**.

---

## 8. Quy trình theo loại thay đổi

| Thay đổi | Chạy | Thời gian (Swind) |
|---|---|---|
| Rule nhận diện / phân loại / phạm vi, hằng số giá | Unit test → `--check` → E2E `--files-from e2e_files.txt` | ~25 giây |
| Phần **đọc cấu trúc** file (header, cột/dòng ẩn, KL ở dòng khác, bảng phụ) | `--build --force` → E2E bộ canh gác → trước khi chốt: E2E toàn bộ | ~2 phút |
| Form / mẫu Excel đầu ra | Chạy thử 3–5 file, mở bằng Excel/Numbers | < 1 phút |
| Có file đầu vào mới | `--build` (chỉ đọc file mới) | vài giây |
| Định kỳ | E2E toàn bộ chạy nền | không chờ |

Mọi thay đổi được duyệt thì: `--set-baseline` (tầng 2) và lưu baseline E2E cho các file đã duyệt.

---

## 9. Kỷ luật sửa rule (cũng nên áp cho MPrice)

Các nguyên tắc rút ra trong quá trình sửa rule ở Swind:

1. **Truy nguồn trước khi sửa:** `git log -S "<đoạn rule>"` để biết rule sinh ra từ dự án nào, ai chốt. Rẽ nhánh theo
   điều kiện để giữ đúng case cũ; chỉ xoá khi rule đã được xác nhận sai.
2. **Ghi nguồn cạnh rule:** ngày, dự án, dòng, người chốt, ví dụ đúng/sai, ngay trong bảng rule.
3. **Không vá bằng từ khóa phụ.** Rule "cửa vuông có OBD thì phải có chữ *cấp / lạnh / 450* mới là khuếch tán" làm
   chữ "450" khớp luôn với kích thước *450x450*, nên kết quả phụ thuộc con số. Quy tắc đúng: **xếp loại theo việc
   đầu vào có GHI loại hàng hay không**, không ghi thì dùng mặc định an toàn.
4. **Khi chưa rõ quy tắc nghiệp vụ, quét báo giá do người lập** (có cột Model) để lấy căn cứ, đếm tác động trên toàn bộ
   dữ liệu, rồi mới đề xuất.
5. **Dòng tự ghi loại hàng thì thắng Title cha** (Title chỉ cho thông số / phụ kiện kế thừa). Phần lớn lỗi tuần qua của
   Swind thuộc dạng "Title kéo sai loại": ống gió thành cửa gió, cửa gió bị ghép van, ống gió thành hàng thương mại.
6. **Cụm mô tả phạm vi không phải loại hàng:** "bao gồm phụ kiện bích, co tê giảm hướng", "kết nối ống bằng nẹp C" phải
   bị bỏ trước khi dò loại hàng (Swind: `xoa_cum_liet_ke_phu_kien` trong `duct_rules.json`).

---

## 10. Bẫy đã gặp

| Bẫy | Hậu quả | Cách tránh |
|---|---|---|
| Đặt biến môi trường "tắt ghi file học" trong **tiến trình gọi** | Rò sang test chạy cùng tiến trình; 3 test học lỗi gõ hỏng | Chỉ đặt trong `initializer` của pool tiến trình con |
| Chép style ô giữa 2 workbook bằng chỉ số style nội bộ | `IndexError` | Chép từng thành phần: font, fill, border, alignment, number_format |
| Bố cục cột có chỉ số 0 ("không có cột") | `ValueError` khi ghi ô | Lọc vị trí cột < 1 |
| Nhãn header sheet ảo kiểu `NAME`, `UNIT` | Bộ tự dò header lỗi | Dùng nhãn thật của ngôn ngữ đầu vào |
| Đánh số lại cột trên sheet ảo | Kết quả lệch so với file thật | Giữ nguyên vị trí cột gốc |
| `multiprocessing` trên macOS khi script không có `if __name__ == "__main__"` | `BrokenProcessPool` | Luôn đặt khối main |
| So chế độ phụ với baseline mặc định | ~40 "lệch" giả, che mất lệch thật | Mỗi chế độ một baseline |
| Dùng `git stash` để thử đột biến khi file đã được commit | Stash không có gì, thử nghiệm vô nghĩa | Dùng `git checkout <commit_cũ> -- <file>` rồi `git checkout HEAD -- <file>` |
| E2E ghi đè thư mục output thật | Mất file báo giá vừa dựng cho khách | Thư mục đầu ra tạm qua biến môi trường; sau E2E dựng lại file cần gửi |

---

## 11. Checklist áp dụng cho MPrice

**Giai đoạn A — nền móng (làm trước, lợi ngay)**
- [ ] Đầu ra cấu hình qua biến môi trường; công tắc tắt ghi file học / nhật ký.
- [ ] E2E song song theo bước 1; kiểm chứng tuần tự = song song.
- [ ] Baseline riêng cho từng chế độ / bộ cờ chạy.

**Giai đoạn B — rule thành dữ liệu**
- [ ] Rule phân loại chuyển sang bảng có ID, nguồn, ví dụ đúng/sai; unit test đọc ví dụ từ bảng.
- [ ] Bộ phân loại trả về vết rule; hàm tính giá 1 dòng dùng chung với luồng chính.
- [ ] Parser có điểm vào nhận bố cục cột chỉ định và móc ghi ngữ cảnh (Title, bố cục).

**Giai đoạn C — tầng 1 + 2**
- [ ] Thư viện mẫu dòng (SQLite, SHA-1, tăng dần, không commit).
- [ ] Chữ ký mẫu; dòng đại diện nhỏ / vừa / lớn; sheet ảo; dấu vân tay; `--set-baseline` / `--check`.
- [ ] 3 kiểm chứng: ổn định, độ khớp ≥ 99%, thử đột biến bắt được lỗi.

**Giai đoạn D — tầng 3**
- [ ] Bọc bộ phân loại để lấy vết rule; đặc trưng kết quả + bố cục (có / không từng cột).
- [ ] Phủ tập tham lam; báo rule chưa được kiểm; `e2e_files.txt` = ảnh hưởng ∪ canh gác.
- [ ] Ghi quy trình theo loại thay đổi (mục 8) vào tài liệu hướng dẫn của MPrice (tương đương `AGENTS.md`).

**Ước lượng công** (theo kinh nghiệm Swind, khi đã có giai đoạn B): A ~nửa ngày; C ~1 ngày; D ~nửa ngày.
Giai đoạn B tùy mức độ rule đang nằm cứng trong code.

---

## Phụ lục — Tham chiếu Swind

| Thành phần | File |
|---|---|
| E2E song song, nhiều chế độ | `src/swind_e2e_regression.py` |
| Thư viện mẫu dòng / chạy lại / canh gác | `src/swind_pattern_lab.py` |
| Test công cụ | `tests/test_swind_pattern_lab.py` |
| Móc ngữ cảnh trong parser | `src/swind_boq_parser.py` (`record_row_context`, `row_context`, `sheet_layouts`) |
| Công tắc ghi file học | `src/swind_utils.py` → `learning_writes_disabled()` |
| Bảng rule có ID | `data/master_data/*_rules.json` |
| Quy trình trong tài liệu dự án | `AGENTS.md` mục "QUY TẮC TỐC ĐỘ… KIỂM TRA / SỬA / THÊM CÔNG THỨC" |

```bash
# E2E (mặc định: toàn bộ, 2 chế độ, song song)
./venv/bin/python src/swind_e2e_regression.py
# Tầng 1–3
./venv/bin/python src/swind_pattern_lab.py --build
./venv/bin/python src/swind_pattern_lab.py --check
./venv/bin/python src/swind_e2e_regression.py --files-from output/_pattern_lab/e2e_files.txt
./venv/bin/python src/swind_pattern_lab.py --canary
./venv/bin/python src/swind_pattern_lab.py --set-baseline
```
