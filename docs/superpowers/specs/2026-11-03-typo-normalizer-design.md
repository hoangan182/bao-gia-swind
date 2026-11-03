# Thiết kế: Bộ chuẩn hóa lỗi chính tả BOQ dùng chung (`typo_normalizer`)

- Ngày: 2026-11-03 · Người yêu cầu: User (Hoang An) · Trạng thái: chờ duyệt

## 1. Mục đích & lý do

BOQ khách thường viết sai chính tả: không dấu, nhầm dấu, đảo chữ mã (`ODB` thay `OBD`, `MDF` thay `MFD`) → bộ nhận diện hiểu sai loại hàng / phụ kiện → sai giá.

Hiện các bản vá nằm rải rác, mỗi nơi một kiểu (rule chồng rule):

| Chỗ vá hiện có | Nội dung |
|---|---|
| `src/swind_boq_parser.py::_match_text` | `miệng/cửa/mặt gio` → `gió`; `_` → khoảng trắng |
| `src/swind_boq_parser.py:293` | `.replace('ồ', 'ố')` cứng trong code (commit 1805d82, 2026-10-20) |
| `damper_rules.json` → `VG-13.sua_go_nham` | `van mdf` → `van mfd` |
| `diffuser_rules.json` | từ khóa lỗi nhét thẳng vào danh sách (`"cửa gió hôi"`), một số rule so trên `unaccent_search` |
| `diffuser_classifier` quy tắc 4a | so khớp tháo lắp trên chuỗi không dấu |

Mục tiêu: **một chỗ duy nhất** xử lý lỗi chính tả cho mọi bộ nhận diện (cửa / van / ống / phạm vi), và **tự lớn dần** qua việc User duyệt lỗi mới.

## 2. Hành vi đã chốt với User

1. Lỗi **đã có trong từ điển** → sửa, không hỏi.
2. Lỗi **mới** → hệ thống **đoán nếu ngữ cảnh đủ** (User chốt 2026-11-03); đoán xong vẫn ra báo giá, dòng đó báo `⚠️ [ĐÃ ĐOÁN — XÁC NHẬN]` ở Kiểm soát cuối (không chặn) và vào hàng chờ duyệt.
2a. **Dòng đã đoán được đánh dấu trên Sheet `BG`** (User chốt 2026-11-03): tô vàng ô Tên + ghi chú dạng `⚠️ ĐÃ HIỂU: ODB = OBD — xin xác nhận`, cùng khuôn đánh dấu với dòng thiếu kích thước (quy tắc 1b Kiểm soát cuối). Dòng `HỎI LẠI USER` cũng được đánh dấu tương tự (`⚠️ CHƯA RÕ: <chữ gốc>`). Lỗi đã có trong từ điển **không** đánh dấu.
3. **Không đoán được** (≥ 2 cách hiểu hợp ngữ cảnh, hoặc ngữ cảnh không đủ) → `⚠️ [HỎI LẠI USER]`, dòng được đọc **đúng như khách viết**.
4. Lỗi được User duyệt → lưu vào từ điển, lần sau sửa thẳng (mục 1).

## 3. Mục tiêu / Không làm / Phản mục tiêu

**Mục tiêu**
- Gom toàn bộ bản vá cũ về 1 file rule + 1 module.
- So khớp không dấu ở tầng chung, có danh sách cặp dễ nhầm phải giữ dấu.
- Phát hiện chữ nghi gõ sai gần với từ vựng Swind, đoán theo ngữ cảnh, đưa vào hàng chờ duyệt.

**Không làm**
- Không dùng LLM / AI để đoán (không ổn định, khó so baseline E2E — đã loại khi chọn hướng).
- Không sửa chính tả cột tiếng Anh `DESCRIPTION` ngoài các **mã viết tắt** (OBD, MFD, LCCT…).
- Không đổi công thức tính giá.

**Phản mục tiêu (dù chạy được vẫn coi là hỏng)**
- **Ghi đè / viết lại nội dung BOQ.** Chuẩn hóa chỉ áp vào *chuỗi dùng để so khớp*; file BOQ, cột Tên trên Sheet `BG` giữ nguyên chữ khách viết (đúng quy tắc Reader core, mục 7 AGENTS.md).
- Đoán lẫn giữa các mã van khác 1 chữ (`MD` / `FD` / `MFD`) khi ngữ cảnh không phân định → phải hỏi.
- Bỏ dấu làm gộp nghĩa: `hộp` (hộp gió) ≠ `hợp` (*tích hợp* — đang dùng để tách combo `VG-13.regex_tach`), `côn` ≠ `con`.
- Tự ghi vào từ điển sống khi chưa duyệt.
- E2E lệch ở bước 1 (bước chỉ di chuyển bản vá cũ).

## 4. Các hướng đã cân nhắc

| Hướng | Nội dung | Đánh đổi | Kết quả |
|---|---|---|---|
| **A. Bộ chuẩn hóa dùng chung** | 1 module + 1 file rule chạy trước mọi bộ phân loại; 3 lớp: từ điển → không dấu có bảo vệ → đoán theo ngữ cảnh | Sửa 1 chỗ cho mọi nơi; nhưng đụng đầu vào của mọi bộ phân loại → phải làm theo bước và chạy E2E kỹ | **User chọn** |
| B. Mỗi bộ phân loại tự có bảng lỗi | Mở rộng `damper/diffuser/duct_rules.json` | Ít rủi ro hồi quy trước mắt; nhưng 1 lỗi khai 3 nơi, xử lý không đồng nhất — chính là nguyên nhân hiện trạng | Loại |
| C. LLM đoán | Gửi dòng BOQ cho mô hình ngôn ngữ | Linh hoạt; nhưng không tất định, tốn phí, phá E2E baseline, trái hướng rule tường minh | Loại |

## 5. Thiết kế (hướng A)

### 5.1 Thành phần

- **`data/master_data/typo_rules.json`** — bảng rule theo đúng khuôn các file rule khác (`id`, `nguon`, `ly_do`, `vi_du_dung`, `vi_du_sai`):
  - `TY-01 tu_dien`: danh sách cặp `[mẫu_regex, thay_thế]` đã duyệt, kèm phạm vi áp (`ma` = mã viết tắt, `tu` = từ tiếng Việt). Khởi tạo bằng các bản vá ở mục 1.
  - `TY-02 giu_dau`: cặp từ dễ nhầm khi bỏ dấu, phải so có dấu (`hộp/hợp`, `côn/con`, … — danh sách ban đầu do builder rà từ các file rule hiện có, User bổ sung dần).
  - `TY-03 tu_vung`: nguồn từ vựng chuẩn để phát hiện lỗi mới — **tự gom** từ từ khóa trong `diffuser_rules.json`, `damper_rules.json`, `duct_rules.json`, `scope_rules.json`, mã trong `manufacturable_catalog.json`; file này chỉ chứa phần bổ sung / loại trừ (tên hãng, mã dự án…).
  - `TY-04 doan`: ngưỡng & điều kiện đoán (mục 5.3).
- **`src/typo_normalizer.py`** — module thuần (không đọc/ghi Excel), API đề xuất:
  - `normalize_for_match(text, ctx) -> (text_match, events)` — trả chuỗi để so khớp + danh sách sự kiện `{loai: TU_DIEN|DOAN|HOI_LAI, goc, sua, ly_do}`.
  - `restore_accents(text)` — **khôi phục dấu** theo từ vựng (cập nhật khi lập kế hoạch): cụm ≥ 2 chữ trong text mà bỏ dấu trùng một cụm từ vựng Swind duy nhất (`cua gio hoi`, `cửa giò`) → thay bằng cụm có dấu chuẩn (`cửa gió hồi`). Cách này giữ nguyên toàn bộ từ khóa có dấu trong các file rule hiện có (không phải chuyển bộ phân loại sang so không dấu). Chữ trong `TY-02 giu_dau` không bị thay; chữ đơn lẻ không khôi phục. `unaccent_search` / so khớp tháo lắp hiện có giữ nguyên.
- **Agent 02** — thêm loại đề xuất `TYPO` vào `pending_approval_queue.json` (`raw_name` = chữ gốc, `proposed_id` = chữ sửa, `project`, `context`); `--approve-pending` duyệt → ghi vào `typo_rules.json → TY-01`. Không tạo cơ chế học mới.

### 5.2 Điểm gắn vào luồng

- Gọi trong `SwindBOQParser.parse_sheet` tại chỗ đang dùng `_match_text` / `fix_typos` (dòng ~293–294, ~658, ~667) và tại nơi Agent 01 dựng `raw_search` / `full_search` trước `_resolve_damper_spec` / `_resolve_diffuser_spec`.
- `_match_text`, `.replace('ồ','ố')`, `damper_classifier.fix_typos` trở thành lớp mỏng gọi `typo_normalizer` (giữ tên hàm để không vỡ chỗ gọi), rồi xóa dần khi đã chuyển hết.
- Áp lên: Tên, Ghi chú, Model/Mã SP, Spec, Title cha. Cột `DESCRIPTION` tiếng Anh: chỉ lớp mã viết tắt.
- Sự kiện `DOAN` / `HOI_LAI` gắn vào item → runner in ở `[KIỂM SOÁT CUỐI]`, ghi vào `INPUT_COVERAGE_REPORT.json`, và bước xuất Sheet `BG` tô vàng + ghi chú dòng đó (mục 2a), dùng lại cơ chế tô vàng của dòng thiếu kích thước. Cột Tên vẫn giữ nguyên chữ khách viết; ghi chú chỉ thêm vào, không thay.

### 5.3 Quy tắc đoán theo ngữ cảnh

1. **Phát hiện ứng viên:** token (chữ / mã) không có trong từ vựng `TY-03` nhưng gần một mục từ vựng: đảo 2 ký tự liền kề, lệch 1 ký tự (thêm / bớt / thay), hoặc chỉ khác dấu. Bỏ qua số, kích thước, token < 2 ký tự, token trong danh sách loại trừ.
2. **Lọc theo ngữ cảnh:** chỉ giữ ứng viên hợp với dòng — nhóm hàng suy ra từ chính dòng + Title cha (cửa gió / van / ống), có kích thước hay không, các từ đứng cạnh (VD `OBD` hợp dòng cửa gió có kích thước; `MFD` hợp Title *van chặn lửa động cơ*).
3. **Quyết định:** còn **đúng 1** ứng viên → `DOAN` (áp sửa, cảnh báo xác nhận, vào hàng chờ). Còn 0 hoặc ≥ 2 → `HOI_LAI` (đọc nguyên chữ). Mã van trong nhóm `MD/FD/MFD/MFSD/PRD/NRD/VCD` chỉ được đoán khi ngữ cảnh loại hết các mã còn lại.
4. Tất định: cùng đầu vào → cùng kết quả (để E2E so được).

### 5.4 Triển khai theo bước (bắt buộc theo thứ tự)

1. **Bước 1 — Gom bản vá:** tạo module + `TY-01` chứa đúng các bản vá cũ; nối các chỗ gọi cũ vào module. Điều kiện qua: self-test, unit test, E2E **cả 2 baseline (mặc định & `--include-duct`) không lệch**.
2. **Bước 2 — Không dấu có bảo vệ:** bật `fold()` + `TY-02` ở tầng chung, chuyển các `unaccent_search` / so khớp tháo lắp sang dùng nó. File E2E nào lệch phải giải thích được; User duyệt mới `--save-baseline`.
3. **Bước 3 — Phát hiện & đoán:** bật mục 5.3 + loại đề xuất `TYPO` ở Agent 02. Chạy toàn bộ `input/`, liệt kê mọi sự kiện `DOAN` / `HOI_LAI` cho User duyệt (đây cũng là đợt nạp từ điển đầu tiên).

### 5.5 Kiểm thử

- `tests/test_swind_typo_rules.py`: mỗi rule `TY-*` chạy `vi_du_dung` / `vi_du_sai`; ca bắt buộc: `ODB → OBD` trên dòng cửa gió có KT; `MDF` dưới Title van chặn lửa động cơ → `MFD`; `tích hợp` không bị hiểu là `hộp`; mã mơ hồ → `HOI_LAI`; BOQ gốc không bị thay đổi nội dung.
- Self-test 53 mặt hàng, unit test hiện có, E2E 2 baseline; `--refresh-index` cập nhật `03_FORMULA_INDEX.md`.
- Cập nhật AGENTS.md (mục Agent 01 + quy tắc đọc kết quả `ĐÃ ĐOÁN`) và thêm file vai trò `.agents/roles/typo_normalizer_role.md`.

## 6. Phần để builder tự quyết

- Thuật toán khoảng cách cụ thể (Damerau-Levenshtein tự viết hay thư viện sẵn có trong venv), cấu trúc dữ liệu từ vựng, cache.
- Danh sách `TY-02` ban đầu (rà từ các file rule), danh sách loại trừ ban đầu.
- Cách hiển thị chi tiết dòng cảnh báo trên console (theo khuôn các cảnh báo hiện có).

## 7. Quyết định do tôi (Claude) đề xuất, chờ User xem

- Dòng đã đoán **không chặn** báo giá, chỉ cảnh báo ở Kiểm soát cuối (và đánh dấu trên `BG` theo mục 2a — User chốt).
- Ghi chú đánh dấu đặt ở cột Ghi chú của Sheet `BG` (vị trí cụ thể theo khuôn tô vàng hiện có).
- **Khôi phục dấu không đánh dấu trên `BG`** (chỉ ghi báo cáo nội bộ): BOQ viết không dấu toàn bộ sẽ tô vàng cả sheet nếu đánh dấu. Lớp "đoán" ở mục 5.3 áp cho **mã viết tắt** (OBD, MFD, LCCT…); lỗi đánh máy chữ tiếng Việt ngoài dấu (thiếu / thừa chữ cái) chưa đoán ở đợt này — xử lý bằng từ điển khi User gặp.
- Cột `DESCRIPTION` tiếng Anh chỉ sửa mã viết tắt.
- Duyệt lỗi đi qua hàng chờ Agent 02 sẵn có (`--approve-pending`).
- Giữ tên hàm cũ làm lớp mỏng ở bước 1 để E2E không lệch.
