# Trợ lý báo giá từ báo giá cũ (dẫn từng bước + ghi nhớ theo dự án) — Thiết kế

Ngày: 2026-11-23 · Nguồn: phiên làm dự án `261123_HH3_RFQ_Cua_gio_Van_gio_Ham_L1_L2_Y1` (BG cũ `BG_SLAND - CTD - 20260429_CO LOA_HH3_MEP_BOQ_SENT_R4. UP`) · User duyệt hướng A.

## 1. Mục đích & lý do

Dự án đã báo giá thường quay lại với BOQ/RFQ mới (gộp khu, thêm khối lượng, báo lần 2, 3...). Yêu cầu chuẩn của User:
*"Dòng cùng vật tư + kích thước → copy giá BG cũ; dòng không trùng → hệ thống báo mới; xuất 1 file gửi khách."*

Agent 10 (`src/agent_10_old_quote_carrier.py`) đã làm phần máy, nhưng phiên HH3 cho thấy AI vẫn phải soi tay và hỏi User từng chỗ:

| Chỗ hở (HH3) | Hậu quả |
| :--- | :--- |
| Dòng đánh số cột RFQ (`1,2,3,4,5`) bị đọc là mặt hàng | Báo "1 dòng thiếu giá" giả (đã vá 2026-11-23) |
| Combo `VCD + FD 200x150` ghép vào giá FD rời | Thiếu phần VCD — AI phải tự phát hiện, `--force-new 64` |
| Không so cấp EI (FD EI30 ↔ giá cũ EI120; MFD) | Ghép "chắc chắn" dù khác chủng loại |
| Giá cũ gồm hộp gió, RFQ không ghi hộp | Ghép "chắc chắn", AI phải tự soi ghi chú để hỏi |
| Phần báo mới dùng MFD mặc định 1.02, phần giá cũ là 1.05 | Cùng 1 file lệch model, phải chạy lại |
| Nhiều giá cũ cho cùng mặt hàng | Lấy theo sheet ưu tiên, không có lý do rõ |
| Quyết định của User truyền bằng **số dòng** (`--force-new 64`) | Báo lần 2 chèn dòng là sai hết; mỗi lần phải hỏi lại từ đầu |

**Mục tiêu:** một trợ lý AI chạy trong cuộc trò chuyện, dẫn User qua từng bước, hỏi theo **nhóm** kèm đề xuất + lý do; **nhớ quyết định theo dự án** — lần báo lại tự áp, chỉ hỏi dòng mới / dòng thay đổi.

## 2. Mục tiêu / Không làm / Thất bại nếu

**Mục tiêu**
- G1. User nói *"báo giá file X theo giá cũ file Y"* → trợ lý tự dẫn: chọn sheet BG cũ → ghép → hỏi từng nhóm → tuỳ chọn chạy → chạy thật → rà → báo kết quả.
- G2. Mọi điểm hở ở bảng §1 được Agent 10 tự phát hiện và đưa vào đúng nhóm hỏi (không phụ thuộc AI soi tay).
- G3. Quyết định lưu theo dự án, khoá theo **nội dung dòng** (không theo số dòng); báo lại chỉ hỏi phần mới.
- G4. Phần báo mới mặc định đồng bộ model/hãng với BG cũ (MFD, động cơ) — đề xuất, User chốt.

**Không làm (lần này)**
- Không đổi rule nhận diện/giá của Agent 01..08 hay runner.
- Không tự commit/push (theo AGENTS.md).
- Không biến thành agent chạy nền (subagent không hỏi User giữa chừng được — đã loại hướng B).
- **So sánh với giá đối thủ: để sau** (User chốt 2026-11-23). Script HH3 tạm ở scratchpad, sẽ tổng quát hoá ở đợt riêng.
- **Ghi nhớ chỉ theo từng dự án** (User chốt 2026-11-23): không có quy tắc mặc định chung; dự án mới luôn được hỏi theo nhóm từ đầu.

**Thất bại nếu** (dù chạy được)
- Trợ lý áp lại quyết định cũ cho một dòng **đã thay đổi** (KT / phụ kiện / EI / giá BG cũ khác) mà không hỏi.
- Dòng ghép giá cũ khác chủng loại (combo, EI, hộp) mà xếp vào "Khớp chắc chắn".
- Hỏi User lại những dòng đã chốt ở lần trước.
- File gửi khách lệch thứ tự RFQ, mất dòng, hoặc tổng tiền khác bảng tổng hợp.

## 3. Ràng buộc

- Runner xoá sạch `output/<Dự án>/` mỗi lần chạy (`archive_previous_output`) → **không lưu ghi nhớ trong `output/<Dự án>/`**.
- Dữ liệu dự án không được commit (AGENTS.md §Git) → kho ghi nhớ phải nằm trong `.gitignore`.
- Mọi đọc BOQ qua Reader core `swind_utils` (bỏ cột/dòng ẩn ở 1 chỗ).
- Quy tắc báo giá hiện hành giữ nguyên (động cơ mặc định Belimo, `--include-duct` chỉ khi User nói, kiểm soát cuối...).
- Skill dự án hiện đặt ở `.agents/skills/` (VD `chay-bao-gia`); Claude Code đọc `.claude/skills/`.

## 4. Các hướng đã cân nhắc

| Hướng | Mô tả | Đánh đổi | Kết luận |
| :--- | :--- | :--- | :--- |
| **A** | Skill dẫn từng bước + nâng cấp Agent 10 (xuất kế hoạch theo nhóm, nhận file quyết định, sửa lỗi ghép, đề xuất tuỳ chọn theo BG cũ, kho ghi nhớ) | Phải sửa code Agent 10, nhưng số liệu chắc & lặp lại được | **Chọn** — Agent 10 chỉ phục vụ đúng luồng này (không module nào khác gọi, chưa có test), sửa không ảnh hưởng luồng chính |
| B | Subagent chạy nền | Không hỏi User giữa chừng → trái mục đích | Loại |
| C | Chỉ viết skill, giữ Agent 10 | Lỗi §1 vẫn còn, AI vá tay mỗi lần, ghi nhớ không có chỗ bám | Loại (User: chỉ chọn C nếu Agent 10 còn nhiệm vụ khác — không có) |

## 5. Thiết kế

### 5.1 Luồng trợ lý (skill `bao-gia-tu-bg-cu`)

Kích hoạt khi User yêu cầu kiểu *"copy/nhặt giá từ báo giá cũ sang BOQ mới, dòng nào chưa có thì báo mới"*.

1. **Xác định dự án & ghi nhớ.** Trợ lý đề xuất mã dự án (từ tên file / tên công trình trong BOQ), hỏi User xác nhận; nếu kho ghi nhớ đã có dự án → nói rõ "đã có N quyết định từ lần báo ngày ..., sẽ áp lại".
2. **Chọn sheet BG cũ.** Agent 10 liệt kê sheet dạng báo giá (+ số dòng có giá, khu/tầng nhận ra); trợ lý đề xuất thứ tự ưu tiên; User chốt (nhớ lại cho lần sau).
3. **Ghép thử** (`--plan-json`). Trợ lý đọc kế hoạch, trình **từng nhóm một** (chỉ nhóm còn dòng chưa có quyết định), mỗi nhóm: số dòng, vài ví dụ, đề xuất + lý do; hỏi bằng hộp chọn. Thứ tự nhóm (§5.3).
4. **Tuỳ chọn chạy phần báo mới.** Trợ lý đề xuất từ `suggested_options` (MFD/động cơ theo BG cũ) + quy tắc hiện hành (ống gió chỉ khi User nói; `--duct-uplift`...). User chốt.
5. **Chạy thật** (`--decisions`). Trợ lý rà console: Kiểm soát cuối, dòng thiếu giá, dòng Model trái loại; có vấn đề → báo User, không tự vá bằng số dòng.
6. **Báo kết quả**: bảng tổng hợp Agent 10 (giá cũ + báo mới) + link file gửi khách + liệt kê dòng cần User biết (theo AGENTS.md). Lưu quyết định vào kho.

Báo lại lần sau: bước 1 tải ghi nhớ → bước 3 chỉ hỏi dòng **mới** hoặc **thay đổi** (§5.4); bước 2/4 dùng lại lựa chọn cũ, chỉ nhắc 1 dòng "dùng lại: sheet ..., MFD 1.05..." để User sửa nếu muốn.

### 5.2 Nâng cấp Agent 10

1. **`--plan-json <file>`** (mở rộng `--dry-run`): ghi JSON
   `{project_key, boq, boq_sheet, old_quote, old_sheets, rows:[{key, boq_row, stt, name, qty, unit, group, proposal, reason, candidates:[{ref, name, model, note, price}], decided_by}], suggested_options:{mfd_model, motor_brand, ...}, sheet_summary:[...]}`.
   `decided_by` = `memory` | `auto` | `null` (cần hỏi).
2. **`--decisions <file>`**: JSON `{rows:{<key>:{action:"carry"|"new", ref?, neck?:bool, note?}}, options:{...}}`. Thay cho `--force-new` / `--accept-review` / `--neck-rows` theo số dòng (các cờ cũ **giữ nguyên** để tương thích).
3. **Khoá dòng ổn định** `key` = chuẩn hoá(Tên) + chữ ký (loại, KT, phụ kiện, EI, hộp) + ĐVT; trùng nhau thì thêm số thứ tự xuất hiện (`#2`). Không chứa số dòng / STT.
4. **Sửa ghép (đưa vào nhóm thay vì "chắc chắn")**:
   - Combo: dòng ghi cả cửa/louver + van, hoặc VCD + FD → loại riêng (`VCD+FD`, `LOUVER+FD`, `LOUVER+MFD`...); chỉ khớp combo cùng loại.
   - Cấp EI: chữ ký FD/MFD/miệng TAHK gồm cấp EI ghi ở BOQ và ở BG cũ (tên/ghi chú/model `EI120`...); khác → nhóm *Khác cấp EI*.
   - Hộp gió: phụ kiện `BOX` (tên / ghi chú / model `hộp gió`) → khác → nhóm *Khác hộp gió*.
   - Dòng đánh số cột: đã vá (`load_boq_rows`, `_is_numbering_row`), thêm test.
5. **`suggested_options`**: đọc cột Model BG cũ ở các dòng đã khớp → mã MFD phổ biến nhất (`SWIND-1.05-...` → `1.05`), hãng động cơ (Belimo/KLB...) nếu nhận ra; kèm số dòng làm bằng chứng.
6. **Nhiều giá cũ**: candidates trả đủ các giá + dòng BG cũ + ghi chú; đề xuất mặc định theo thứ tự: giá cùng cấu hình (hộp/EI) → sheet ưu tiên → giá có tổng KL lớn nhất; lý do ghi vào `reason`.

### 5.3 Nhóm hỏi (thứ tự trình bày)

| Nhóm | Điều kiện | Đề xuất mặc định |
| :--- | :--- | :--- |
| Khớp chắc chắn | cùng loại/KT/phụ kiện/kiểu nan/EI/hộp, 1 giá | Lấy giá cũ (không hỏi, chỉ báo số dòng) |
| Kiểu nan chưa rõ | BOQ hoặc BG cũ không ghi kiểu nan | Lấy giá cũ nếu cùng mã/model nan |
| Khác hộp gió | giá cũ có hộp, BOQ không (hoặc ngược lại) | Hỏi (HH3: User chọn lấy giá cũ) |
| Khác cấp EI | EI BOQ ≠ EI BG cũ | Hỏi; gợi ý theo rule hệ thống (FD có EI → EI120 bọc) |
| Combo / đổi loại | combo khác loại; BG cũ đã đổi loại (FD→MFD) | Báo mới |
| Nhiều giá | ≥2 giá cho cùng mặt hàng | Theo §5.2-6, hỏi xác nhận |
| Không có trong BG cũ | — | Báo mới (không hỏi, kèm gợi ý dòng gần giống) |

### 5.4 Kho ghi nhớ

- Đường dẫn: `data/old_quote_memory/<project_key>.json` — thêm `data/old_quote_memory/` vào `.gitignore`.
- Nội dung: `project_key`, tên hiển thị, `old_quote` (đường dẫn + ngày sửa file + sheet ưu tiên), `options` đã chốt, `rows:{key:{action, ref, price_at_decision, old_sig, decided_at, source_run}}`, `runs:[{at, boq, totals}]`.
- **Áp lại** một quyết định chỉ khi: cùng `key` **và** dòng BG cũ được chọn vẫn tồn tại với cùng giá & chữ ký. Ngược lại → `decided_by=null`, lý do "thay đổi so với lần trước: ..." → hỏi lại.
- BG cũ được thay bằng file khác → hỏi User có giữ quyết định không (mặc định giữ các dòng `new`, hỏi lại các dòng `carry`).
- Ghi kho **sau** khi chạy thật thành công (không ghi khi `--plan-json`).

### 5.5 Vị trí file

- Skill: `.agents/skills/bao-gia-tu-bg-cu/SKILL.md`; Claude Code: `.claude/skills/bao-gia-tu-bg-cu` là symlink tới thư mục trên.
- Code: `src/agent_10_old_quote_carrier.py` (+ có thể tách `src/old_quote_memory.py` cho kho ghi nhớ).
- Test: `tests/test_swind_old_quote_carrier.py` (fixture xlsx tự dựng nhỏ: dòng đánh số cột, combo VCD+FD, FD EI30 vs EI120, giá có hộp, nhiều giá, khoá dòng ổn định khi chèn dòng, áp/không áp ghi nhớ).
- Tài liệu: cập nhật `.agents/roles/agent_10_old_quote_carrier_role.md` + mục *LUỒNG RẼ Agent 10* trong `AGENTS.md`.

## 6. Kiểm chứng

- Unit test mới + `python -m unittest discover -s tests -p "test_swind_*.py"`.
- Chạy lại HH3 bằng trợ lý với các quyết định đã chốt hôm nay → file trùng tổng **16,435,221,594** đ trước VAT (MFD 1.05), không cần `--force-new`; dòng 64 (VCD+FD) tự vào nhóm combo.
- Mô phỏng báo lần 2: chèn 2 dòng mới + sửa KT 1 dòng trong RFQ HH3 → trợ lý chỉ hỏi đúng 3 dòng đó.
- Runner/E2E không đổi (Agent 10 không nằm trong E2E) — chạy `swind_item_inspector.py --self-test` để chắc không đụng luồng chính.

## 7. Để người xây quyết định

Tên hàm/cấu trúc nội bộ, cách tách module, định dạng hiển thị nhóm trong hộp chọn, ngưỡng "vài ví dụ" mỗi nhóm.
