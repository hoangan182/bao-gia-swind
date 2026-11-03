# Tổng hợp thay đổi hệ thống báo giá Swind — ngày 2026-11-03

> **Mục đích file này:** tài liệu đầu vào để brainstorming với Claude ở một hệ thống báo giá khác, xem phần nào đáng áp dụng.
> Hệ thống nguồn: bóc tách BOQ điều hòa thông gió (HVAC) → báo giá Excel, kiến trúc multi-agent (Python + JSON master data).
> Mỗi mục có 3 phần: **Vấn đề → Giải pháp → Khả năng tái dùng**. Phần đặc thù ngành HVAC được đánh dấu `[ĐẶC THÙ]`, phần dùng được cho hệ thống bất kỳ đánh dấu `[CHUNG]`.

---

## 0. Bức tranh tổng thể trong ngày

Một ngày làm việc xoay quanh một chủ đề: **chuyển logic nhận diện "rải rác trong code `if/elif`" sang "bảng rule tường minh trong JSON + bộ chạy mỏng + test ví dụ"**, đồng thời tách tầng đọc file khỏi tầng hiểu nội dung, và thêm các lớp kiểm chứng/cảnh báo để hệ thống không tự đoán ngầm.

| # | Hạng mục | Commit / trạng thái |
|---|---|---|
| 1 | Rule bóc tách theo phản hồi kỹ thuật (Z thiếu độ lệch, van gõ nhầm MDF, `--override skip`) | `7ebdc48` |
| 2 | Agent đọc BOQ chỉ-đọc + Reader core dùng chung + rule nhiều hộp trong Ghi chú | `eeebc61` |
| 3 | Việc A: bộ kiểm chứng độc lập tầng đọc cấu trúc (`StructureVerifier`) | `f31a9d4` |
| 4 | Việc B: bảng rule **Cửa gió** (`diffuser_rules.json`) + sửa 4 lỗi phát hiện khi kiểm kê | `f31a9d4`, `7eec9e0` |
| 5 | Việc C1: bảng rule **Van gió** (`damper_rules.json`) | `7eec9e0`, `195d4c8` |
| 6 | Việc C2: bảng rule **Ống gió** (`duct_rules.json`) | `7eec9e0`, `195d4c8` |
| 7 | Việc C3: bảng rule **Phạm vi báo giá** (`scope_rules.json`) | `7eec9e0`, `195d4c8` |
| 8 | E2E regression: kiểm bất biến + trạng thái `OK / INV-OK / DIFF / FAIL` + danh sách loại trừ | `7eec9e0`, `195d4c8` |
| 9 | **Typo Normalizer** (chuẩn hóa lỗi chính tả BOQ, học qua hàng chờ duyệt) | **chưa commit** (working tree) |
| 10 | Giải trình lệch baseline `--include-duct` (32 file tồn đọng) | `7eec9e0` |

---

## 1. [CHUNG] Tách tầng ĐỌC file khỏi tầng HIỂU nội dung

### Vấn đề
Agent đầu vào (00B) từng **viết lại file BOQ gốc** cho "chuẩn": tạo file `_NORMALIZED`, chèn tiêu đề giả (VD "Ống gió tôn dày 0.58mm"), đổi cột số lượng, làm mất cột Spec/Model, lệch số dòng khi `--override`. Mỗi lần "chuẩn hóa" lại sinh thêm lỗi. Ngoài ra có nhiều bộ dò header/cột ẩn riêng lẻ, mỗi nơi một kiểu.

### Giải pháp
- Agent 00B **chỉ phân tích và cảnh báo, không bao giờ ghi lại file**. Luôn trả về file gốc.
- **Reader core** (một module dùng chung): `detect_boq_header`, `hidden_col_letters`, `hidden_row_indices`, `visible_rows`, `visible_cols`. Rule "bỏ cột/dòng ẩn" chỉ tồn tại ở **một chỗ**.
- Sửa lỗi thật tìm được trong quá trình: dải cột ẩn kiểu `B:E` trước đây chỉ nhận cột đầu → một dự án đọc nhầm cột ẩn làm Ghi chú, cột khác làm Đơn giá.
- Nguyên tắc cứng: **cấm chèn/bịa nội dung vào dữ liệu khách**.

### Tái dùng
Rất cao cho mọi hệ thống nhận file khách: *một* bộ đọc, *không* sửa dữ liệu nguồn, mọi chuẩn hóa chỉ sinh "chuỗi dùng để so khớp" nằm trong bộ nhớ.

---

## 2. [CHUNG] Bộ kiểm chứng độc lập (`StructureVerifier`) — Việc A

### Vấn đề
Reader core là điểm đọc duy nhất → nếu chọn nhầm cột số lượng thì **mọi** dự án sai theo mà không ai biết (ví dụ cột `TỔNG` bị chọn thay cho `KL ECB`).

### Giải pháp
Không thêm bộ đọc thứ 2 (sẽ lệch nhau và phải chọn bên nào đúng). Thay vào đó thêm một bước **kiểm chứng, chỉ cảnh báo, không sửa kết quả**:
1. Đếm thô trên file gốc: các cột hiển thị có số > 0 dưới header (số dòng có số, tổng giá trị, tiêu đề cột).
2. So với những gì parser chọn: cột SL, số dòng có khối lượng, tổng khối lượng.
3. In `⚠️ [KIỂM CHỨNG ĐỌC BOQ]` khi: parser dùng cột/dòng ẩn; có cột SL ứng viên khác nhiều dòng số hơn hẳn; cột KL rõ ràng lệch giá trị; có dòng KL mà không được bóc.
4. Đưa vào cổng kiểm soát cuối dưới dạng **hỏi lại User, không chặn** (rule `PV-13`).

Kết quả đo: 0 cảnh báo giả trên 52 file thật; giả lập 3 lỗi cũ (CC17, MKS, BDCC09) đều bị bắt. Có 5 unit test dựng workbook tay.

### Tái dùng
Mẫu "**đọc 1 lần + kiểm chứng độc lập bằng cách đếm thô**" áp dụng cho bất kỳ pipeline nhập liệu từ Excel/CSV/PDF của khách.

---

## 3. [CHUNG] Bảng rule tường minh thay cho `if/elif` — Việc B, C1, C2, C3

### Vấn đề
Hàm phân loại mặt hàng dài hàng trăm dòng `if/elif` (riêng cửa gió ~370 dòng). Rule chồng rule, không biết rule nào sinh ra từ dự án nào, sửa 1 chỗ vỡ chỗ khác, không thể duyệt từng quyết định với người dùng/kỹ thuật.

### Giải pháp — khuôn chung cho 4 bộ phân loại

| Bộ | File rule | Bộ chạy | Id rule |
|---|---|---|---|
| Cửa gió | `diffuser_rules.json` | `diffuser_classifier.py` | `CG-01..CG-09` (+ `CG-05` Title cha) |
| Van gió | `damper_rules.json` | `damper_classifier.py` | `VG-01..VG-13` (+ `VG-02A`) |
| Ống gió | `duct_rules.json` | `duct_classifier.py` | `OG-01..OG-24` |
| Phạm vi | `scope_rules.json` | `scope_filter.py` | `PV-01..PV-14` |

Mỗi rule trong JSON bắt buộc có:
- `id`, `ten`
- `nguon` — **ai chốt, ngày nào, dự án nào sinh ra** (truy được bằng `git log -S`)
- `ly_do` — vì sao rule này tồn tại
- `vi_du_dung` / `vi_du_sai` — ví dụ lấy từ BOQ thật, **chạy thành test tự động** (`tests/test_swind_*_rules.py`)
- Thứ tự ưu tiên tường minh: rule đầu tiên khớp thắng.

Quy tắc làm việc: sửa từ khóa/ngưỡng/mẫu → sửa JSON; đổi cấu trúc bước → sửa đúng một hàm theo id rule; **không viết nhánh riêng cho 1 dự án**.

### Cách chứng minh "chuyển đổi không đổi hành vi" (đáng học nhất)
Không tin vào đọc code. Với mỗi bộ rule:
- Lấy code cũ bằng `git worktree` (code cũ **hoàn chỉnh**, không trộn với file đã sửa).
- Phát lại **toàn bộ lời gọi thực** ghi từ 52 BOQ thật (VD cửa gió: 3.850 lần gọi; van: 46.575 lần gọi × 5 biến thể cờ) cộng **ca ngẫu nhiên hàng chục nghìn** (45.000 / 20.000 + 100.000 / 75.000 ca) → so từng trường kết quả → **0 lệch**.
- Với phạm vi (C3): 520 lần chạy runner (52 BOQ × 5 tổ hợp cờ), so log, kiểm soát cuối, coverage, sheet báo giá → 0 lệch.
- **Tách bước:** chuyển tương đương 100% *trước*, rồi mới sửa lỗi phát hiện được (tách riêng, có giải trình E2E từng file lệch).

### Phát hiện khi kiểm kê (đã sửa sau khi User duyệt)
Việc lập bảng buộc phải đọc từng rule nên lộ ra lỗi cũ:
- Cửa gió (4 lỗi): dòng chỉ lấy hộp gió, cột STT, Title cha ghi đè sai loại hàng, v.v.
- Van gió (4 lỗi): dòng chỉ ghi kích thước phải theo Ghi chú, tách combo theo chữ "và", `miệng gio` / mã `AAG` là cửa gió, van MD có EI thì phải bọc.
- Ống gió (4 lỗi): chụp thông gió → Ventcap, giá đỡ → hàng thương mại, *flexible connection* → canvas.
- Kiểm kê cho User duyệt nằm ở `plan/BANG_RULE_*.md` (dạng bảng người đọc được, không cần đọc code).

### Tái dùng
Rất cao. Đây là phần giá trị nhất để mang sang: **(1) bảng rule JSON có nguồn + lý do + ví dụ, (2) test tương đương bằng replay dữ liệu thật vs worktree cũ, (3) tách "chuyển cấu trúc" khỏi "sửa hành vi".**

---

## 4. [CHUNG] Nguyên tắc kế thừa từ Title cha: THÔNG SỐ khác LOẠI HÀNG `[ĐẶC THÙ một phần]`

### Vấn đề
Dòng con trong BOQ thường chỉ ghi kích thước, thông số nằm ở dòng tiêu đề (Title) cha. Kế thừa "mù" gây sai: Title `HÚT KHÓI HÀNH LANG` + dòng con ghi `Cửa nan Z` bị phân thành cửa gió thường thay vì louver.

### Giải pháp (User duyệt 2026-11-03)
- **Thông số / phụ kiện** (OBD, LCCT, lọc G4, EI, độ dày, chức năng hệ tăng áp/hút khói) → **kế thừa** từ Title xuống dòng con.
- **Loại hàng** mà chính dòng ghi rõ (Tên / Ghi chú / Model) → **dòng thắng Title**.
- Dòng chỉ ghi kích thước, không ghi loại → theo Title.
- Có ví dụ cho từng nhánh trong rule `CG-05` và `VG-02A`.

### Tái dùng
Mọi BOQ dạng cây (hạng mục cha → con) đều gặp: nên chốt rõ "trường nào kế thừa, trường nào dòng tự quyết".

---

## 5. [CHUNG] Typo Normalizer — chuẩn hóa lỗi chính tả có học dần (CHƯA COMMIT)

File mới: `src/typo_normalizer.py` (269 dòng), `data/master_data/typo_rules.json`, `tests/test_swind_typo_rules.py` (458 dòng), spec `docs/superpowers/specs/2026-11-03-typo-normalizer-design.md`, plan `docs/superpowers/plans/2026-11-03-typo-normalizer.md`, vai trò `.agents/roles/typo_normalizer_role.md`.

### Vấn đề
BOQ khách viết không dấu, sai dấu, đảo chữ mã (`ODB` thay `OBD`, `MDF` thay `MFD`) → nhận diện sai loại hàng → sai giá. Các bản vá cũ nằm rải rác (hàm `_match_text`, `.replace('ồ','ố')` cứng trong code, `sua_go_nham` trong rule van, từ khóa lỗi nhét thẳng vào danh sách cửa gió) → một lỗi phải khai ở nhiều nơi, xử lý không đồng nhất.

### Thiết kế — 4 lớp trong `typo_rules.json`
| Rule | Việc |
|---|---|
| `TY-01` | Từ điển lỗi **đã duyệt**, theo phạm vi áp (`ten`, `title`, `full`, `combo`, `van`, `agent01`) |
| `TY-02` | Khôi phục dấu theo từ vựng (chỉ chữ không dấu, cụm ≥ 2 chữ, trùng duy nhất một cụm chuẩn); danh sách cặp dễ nhầm giữ dấu (`hộp/hợp`, `côn/con`) |
| `TY-03` | Từ vựng chuẩn tự gom từ các file rule khác + danh sách loại trừ (mã riêng của khách như `EAG`, `PAG`, `SEG`, `FSD` không bị coi là lỗi gõ) |
| `TY-04` | **Đoán** mã viết tắt gõ sai kiểu đảo 2 chữ / lặp thừa chữ, theo ngữ cảnh dòng + Title cha |

### Hành vi đã chốt với User (3 mức)
1. Lỗi đã có trong từ điển → sửa lặng lẽ, không hỏi, không đánh dấu.
2. Lỗi mới **đoán được** theo ngữ cảnh → vẫn báo giá theo mã đoán; **tô vàng dòng trên sheet báo giá** (`⚠️ ĐÃ HIỂU: ODB = OBD — xin xác nhận`) + `⚠️ [ĐÃ ĐOÁN — XÁC NHẬN]` ở kiểm soát cuối (không chặn); vào hàng chờ duyệt.
3. **Không đoán được** (≥ 2 cách hiểu hoặc thiếu ngữ cảnh) → đọc đúng chữ khách viết, tô vàng `⚠️ CHƯA RÕ`, `⚠️ [HỎI LẠI USER]`.

### Vòng học
Agent 02 có thêm loại đề xuất `TYPO` trong hàng chờ: `--approve-pending` duyệt → ghi vào `TY-01`; User từ chối → ghi vào danh sách loại trừ (không nghi lại); trả lời dòng "chưa rõ" bằng `--add-typo "<sai>=<đúng>"`. Công cụ quét nhanh chỉ-đọc: `swind_item_inspector.py --typo-scan "<file>"`.

### Phản mục tiêu (dù chạy được vẫn coi là hỏng)
- Ghi đè nội dung BOQ (chuẩn hóa chỉ áp vào chuỗi so khớp; cột Tên trên sheet báo giá giữ nguyên chữ khách).
- Đoán lẫn giữa các mã khác 1 chữ (`MD/FD/MFD`) khi ngữ cảnh không phân định.
- Bỏ dấu làm gộp nghĩa.
- Tự ghi vào từ điển sống khi chưa được duyệt.
- **Không dùng LLM để đoán** (không tất định, tốn phí, phá baseline E2E) — đã cân nhắc và loại.

### Điểm tích hợp (để biết hệ thống phải đụng chỗ nào)
Parser (thay `_match_text` / `.replace`), Agent 01 (`raw_search`/`full_search`), `diffuser_classifier`, `damper_classifier.fix_typos` (thành lớp mỏng gọi normalizer), bộ xuất Excel (tô vàng + ghi chú), runner (kiểm soát cuối), file E2E (sao lưu/khôi phục `typo_rules.json` vì file này có thể được ghi khi duyệt).

### Tái dùng
Cao. Ý tưởng cốt lõi dùng được ở mọi hệ thống nhận dữ liệu khách gõ tay: **từ điển đã duyệt + đoán có kiểm soát + đánh dấu thấy được + học qua hàng chờ người duyệt**, không dùng LLM trong đường chạy tất định.

---

## 6. [CHUNG] Cổng kiểm soát cuối: phân tầng "chặn" / "hỏi lại" / "thông báo"

Triết lý nhất quán được áp dụng trong ngày: **không tự đoán ngầm, không chặn quá tay**.

| Mức | Biểu hiện | Khi nào |
|---|---|---|
| Chặn (`⛔`, mã thoát 2) | Báo giá chưa hoàn chỉnh | Sheet bóc tách lỗi, hàng sản xuất có KL mà giá = 0, lỗi đầu vào nghiêm trọng |
| Hỏi lại User (`⚠️ [HỎI LẠI USER]`, không chặn) | AI bắt buộc liệt kê cho User | Spec xung đột Tên vs Ghi chú, FD thường thay vì EI120, kiểm chứng đọc BOQ lệch, mã gõ sai chưa rõ, hộp gió Ghi chú khác Tên |
| Thông báo (`⚠️ [THÔNG BÁO USER]`) | Liệt kê khi trả kết quả | Dòng cửa/van **không có kích thước** → không báo giá (giữ giá đối tác nếu có, nếu không tô vàng), trước đây là lỗi chặn nay hạ xuống thông báo |
| Đã đoán — xác nhận | Báo giá vẫn ra, tô vàng | Typo đoán được (mục 5) |

Cơ chế dùng chung: **tô vàng ô trên sheet báo giá + ghi chú lý do** (cùng khuôn cho thiếu kích thước và typo), để người nhận báo giá thấy ngay dòng cần xác nhận.

---

## 7. [CHUNG] E2E regression: không còn "mặc định đạt"

### Vấn đề
Baseline cũ lưu kết quả cũ (có thể sai) và coi giống baseline = đúng. Dự án mới không có baseline → không được kiểm gì. Baseline `--include-duct` lệch 32 file từ trước mà không ai biết lệch vì sao.

### Giải pháp (User chốt 2026-11-03)
- **Mọi file** trong `input/` đều qua **kiểm bất biến** trước rồi mới so baseline: không crash, có bảng tổng hợp, không dòng có KL thiếu giá, không `QA_REJECTED`, không `CẢNH BÁO SÓT DÒNG`, Model không trái loại hàng của Tên (VD van bị ghép mã cửa `SDG + ...`).
- 4 trạng thái: `OK` (khớp baseline đã duyệt), `INV-OK` (chưa có baseline duyệt, chỉ đạt bất biến), `DIFF`, `FAIL`.
- Danh sách loại trừ `data/master_data/e2e_excluded_files.json` cho dự án mà baseline cũ được biết là sai; `--save-baseline` không lưu file không qua bất biến hay file bị loại.
- Baseline làm giàu dần bằng dự án mới đã duyệt (`--filter "<tên>" --save-baseline`). Test bộ kiểm: `tests/test_swind_e2e_invariants.py`.
- **Giải trình baseline tồn đọng:** `plan/GIAI_TRINH_BASELINE_INCLUDE_DUCT.md` truy từng file lệch về đúng commit gây ra bằng cách chạy E2E ở từng commit (worktree riêng). Phát hiện cả "nhiễu môi trường" (1 file lệch rồi tự về đúng).

### Bẫy vận hành đã gặp (ghi lại để tránh)
- Từng lỡ chạy runner ghi đè vào `output/` thật → luôn đặt `SWIND_OUTPUT_DIR` sang thư mục tạm khi thử nghiệm.
- Đừng sửa `src/` khi E2E đang chạy nền (runner chạy subprocess từng file, sẽ nạp code mới giữa chừng).
- So sánh cũ/mới phải dùng code cũ **hoàn chỉnh** (worktree), không phải runner mới + rule cũ.
- Unit test không được ghi vào file dữ liệu sống (từ điển học…); trỏ đường dẫn sang thư mục tạm.
- E2E có thể làm bẩn các file học → sao lưu và khôi phục sau khi chạy.

---

## 8. [ĐẶC THÙ HVAC] Các rule nghiệp vụ mới chốt trong ngày

Để Claude bên kia nhận diện được nếu hệ thống đích có sản phẩm tương tự; còn không thì bỏ qua.

| Chủ đề | Rule |
|---|---|
| Chữ Z / Zét thiếu độ lệch E | Không áp độ lệch mặc định; để trống giá + tô vàng cảnh báo (giữ giá nếu BOQ đã có) |
| Gõ nhầm `van MDF` | Hiểu là MFD (nay nằm ở `TY-01`) |
| Cột Mã SP/Model | Chỉ bổ sung loại van khi Tên chưa ghi loại (Tên "Van chặn lửa MFD" + Mã SP "FD - EI" = **1** van, không phải combo) |
| `--override skip=1` | Áp cho mọi dòng, kể cả dòng đã bóc tách và có giá |
| Ghi chú liệt kê ≥ 2 hộp | 1 dòng, đơn giá = tổng các hộp, ghi chú nêu đủ |
| Hộp gió: Ghi chú 1 hộp khác kích thước Tên | Tính theo Ghi chú + hỏi lại User (`OG-21`) |
| Dòng "chỉ gồm hộp, không gồm cửa gió" | Không báo cửa; xếp vào hộp gió (mặc định không báo + hỏi lại) |
| Giá đỡ / quang treo / ty treo | Hàng thương mại, không kế thừa nhóm từ Title |
| Bộ chuyển đổi nguồn cho van | Hàng thương mại, không báo, không hỏi |
| Chụp thông hơi / Ventcap | Mặc định không báo (cùng nhóm canvas, cờ `--include-canvas`) |
| *Flexible connection* | = khớp nối mềm (canvas) |
| Van MD có EI | Báo thêm bọc tấm KSH 10mm (`VG-08`) |
| Mã `IS` trước kích thước | Lưới chắn côn trùng LCCT; `MPRD` → van xả áp động cơ (`PV-12`) |
| Mã `AL` trước kích thước | Louver nan Z `WL` (`PV-14`); `AL IS-…` vẫn là LCCT |
| Dòng ống/cút kèm LCCT/lọc G4 | Không bỏ cả dòng: vẫn báo phần LCCT/lọc theo kích thước dòng |
| Van "và" van (VD `Van FD và NRD`) | Tách thành 2 van |
| `miệng gio` thiếu dấu / mã `AAG` | Cửa gió |
| Dòng cửa/van không có kích thước | Không báo giá, tô vàng, không chặn |

---

## 9. Trạng thái kiểm thử & việc còn dở

- Ghi nhận trong kế hoạch: self-test **53/53**; unit **39/39** sau C2 (chưa ghi lại số sau khi thêm test typo); E2E mặc định & `--include-duct` không lệch so với ảnh chụp trước khi sửa ở các bước chuyển đổi; các file lệch do sửa lỗi có giải trình từng file.
- **Typo Normalizer chưa commit** — cần chạy lại self-test, unit và E2E 2 chế độ trước khi chốt (spec ghi "chờ duyệt").
- **Còn lại:** rà 32 file lệch tồn đọng của baseline `--include-duct` rồi lưu lại; chọn mức độ cho cảnh báo `StructureVerifier` (hiện: hỏi lại, không chặn).
- Baseline mặc định: C1 và cửa gió đã lưu; C3 (file `BOQ_ANH_KHACH_01` +8 dòng) đang chờ User duyệt lưu.

---

## 10. Gợi ý câu hỏi brainstorming cho hệ thống đích

Thứ tự ưu tiên theo giá trị / chi phí (đánh giá của người tổng hợp):

1. **Có điểm nào nhận diện/phân loại đang là chuỗi `if/elif` dài không?** Chuyển sang bảng rule có `nguon / ly_do / vi_du` + test replay vs worktree cũ (mục 3). Đây là phần có lợi nhất, độc lập với ngành.
2. **Bộ đọc file đầu vào có đang "sửa" dữ liệu khách không?** Nếu có, tách thành đọc-chỉ + kiểm chứng độc lập (mục 1, 2).
3. **Có cơ chế phân tầng chặn / hỏi lại / thông báo chưa?** Hay mọi thứ đều chặn hoặc đều im lặng (mục 6)?
4. **Dữ liệu khách có lỗi chính tả/gõ mã không?** Từ điển đã duyệt + đoán có kiểm soát + hàng chờ duyệt (mục 5); xác định rõ phản mục tiêu (không ghi đè dữ liệu khách, không LLM trong đường tất định).
5. **E2E hiện có bao nhiêu file "tự động đạt" vì chưa có baseline?** Kiểm bất biến + trạng thái `INV-OK` (mục 7).
6. **Kế thừa thông số từ tiêu đề cha:** đã chốt trường nào kế thừa, trường nào dòng tự quyết chưa (mục 4)?
7. Cách vận hành: mỗi bước chuyển cấu trúc làm trong 1 hội thoại riêng, có file bàn giao (`plan/BAN_GIAO_*.md`) ghi quyết định đã chốt + bẫy đã gặp, để phiên sau không hỏi lại.

---

## Phụ lục — Danh sách file chính liên quan

**Code:** `src/typo_normalizer.py`, `src/diffuser_classifier.py`, `src/damper_classifier.py`, `src/duct_classifier.py`, `src/scope_filter.py`, `src/agent_00b_input_normalizer.py`, `src/swind_utils.py` (Reader core), `src/swind_boq_parser.py`, `src/agent_01_boq_extractor.py`, `src/agent_02_boq_reviewer.py`, `src/swind_excel_builder.py`, `src/swind_master_runner.py`, `src/swind_e2e_regression.py`, `src/swind_item_inspector.py`.

**Master data:** `data/master_data/{typo,diffuser,damper,duct,scope}_rules.json`, `e2e_excluded_files.json`, `e2e_regression_baseline.json`.

**Test:** `tests/test_swind_{typo,diffuser,damper,duct,scope}_rules.py`, `test_swind_e2e_invariants.py`, `test_swind_core.py`.

**Tài liệu:** `plan/KE_HOACH_TACH_AGENT_DOC_BOQ.md`, `plan/BAN_GIAO_TACH_AGENT_DOC_BOQ.md`, `plan/BANG_RULE_{CUA_GIO,VAN_GIO,ONG_GIO,PHAM_VI}.md`, `plan/GIAI_TRINH_BASELINE_INCLUDE_DUCT.md`, `docs/superpowers/specs/2026-11-03-typo-normalizer-design.md`, `.agents/roles/*_role.md`, `AGENTS.md`.
