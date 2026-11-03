# Gom công thức tính giá về một chỗ — `src/swind_pricing.py`

*Ngày: 2026-11-03 · Người chốt hướng: User (Hoang An) · Trạng thái: chờ duyệt*

## 1. Mục đích & lý do

Một số quy tắc tính giá đang được viết lặp ở nhiều agent/script. Khi Kỹ thuật đổi một con số (đơn giá OBD, ngưỡng mô-men, giá lưới, VAT…) phải nhớ sửa nhiều nơi; quên một chỗ → ghi chú nói một đằng, giá tính một nẻo, hoặc cùng một phụ kiện có hai giá. Mục tiêu: **mỗi quy tắc tính giá chỉ nằm ở một chỗ**, số liệu nằm trong Master Data JSON, các agent chỉ gọi vào.

## 2. Mục tiêu / Không làm / Thất bại nếu

**Mục tiêu**
- Tạo module dùng chung `src/swind_pricing.py` chứa các hàm tính giá thuần (không đọc BOQ, không ghi file).
- Gom 6 điểm lặp đã khảo sát (mục 4) về module này hoặc về Master Data JSON.
- Xoá các file thừa không còn ai gọi.

**Không làm**
- Không đổi công thức nghiệp vụ ngoài những chỗ buộc phải chọn một bên (mục 5).
- Không đụng bộ nhận diện (`*_classifier.py`, `scope_filter.py`) trừ việc `damper_classifier` dùng chung hàm mô-men.
- Không commit/push (User tự đẩy git — AGENTS.md).

**Thất bại nếu**
- Có dòng đổi giá vượt ngưỡng (mục 6) mà User không được báo.
- E2E có file rơi vào `FAIL` hoặc vi phạm bất biến.
- Cờ `--motor-price` / `--mprd-motor-price` / `--md-shaft-only` / `--mfd-model` cho kết quả khác trước.

## 3. Cách tiếp cận (đã chọn: Cách 1)

| Cách | Mô tả | Đánh đổi | Kết luận |
|---|---|---|---|
| **1. Module riêng `swind_pricing.py`** | Hàm thuần dùng chung; hằng số trong `pricing_constants.json`, rule mô-men đọc từ `damper_rules.json` | Thêm 1 file, phải cập nhật `03_FORMULA_INDEX.md` / `--locate` | **User chọn** — một chỗ duy nhất, test riêng, agent không phụ thuộc chéo, cùng kiểu với `damper_classifier` / `scope_filter` |
| 2. Gộp vào module có sẵn | `excel_round` → `swind_utils`, mô-men → `damper_classifier`, Agent 06 import OBD từ Agent 05 | Agent 06 phụ thuộc Agent 05; classifier gánh việc chọn mã giá | Loại |
| 3. Công thức bằng JSON | Biểu thức trong cấu hình | Quá phức tạp, khó debug | Loại |

## 4. Phạm vi gom (theo thứ tự thực hiện)

Mỗi bước là một lần sửa độc lập, chạy kiểm thử (mục 7) và đối chiếu giá từng dòng (mục 6) trước khi sang bước sau.

### Bước 1 — Làm tròn & giá trị mặc định
- `swind_pricing.excel_round(value, ndigits=0)`: lấy bản của Agent 04 (có `+1e-9`, xử lý số âm đối xứng), trả `int` khi `ndigits <= 0` *(như Agent 05/06 hiện tại — bên gọi đang dùng kết quả như số nguyên)*.
- Xoá `excel_round` ở `agent_04_bom_duct.py:9`, `_excel_round` ở `agent_05_bom_damper.py:17`, `agent_06_bom_diffuser.py:5`; thay bằng import.
- `swind_pricing.mfg_markup()` đọc `master_bom_rules.json` (giữ mặc định 1.593 ở **một** chỗ). Giá vật tư dự phòng (`MAT-ALU-KHUNG-OBD` 133000, `MAT-DOOR-ACCESSORY` 15000, `MAT-FILTER-G4` 220000…) gom vào một hàm `mat_price(mat_id)` với bảng dự phòng duy nhất.

### Bước 2 — Động cơ van (mô-men + mã theo hãng)
- `swind_pricing.select_actuator(kind, brand, w_mod, h_mod, is_single_blade, mfd_model, mfd_mode) -> (mat_id, ten_hien_thi, nm)` với `kind ∈ {MD, MPRD, MFD}`. Mô-men lấy từ `damper_classifier.actuator_torque()` (rule `VG-11` trong `damper_rules.json`) — bỏ ngưỡng viết cứng `1000 / 0.8 / 1.8` trong `agent_05_bom_damper.py:380-407`.
- Bảng mã động cơ theo hãng `ACTUATOR_IDS = {"BELIMO": {...}, "KLB": {...}, "HONEYWELL": {...}, "MPRD": {...}}` đặt một chỗ trong `swind_pricing`; `swind_master_runner.py:1533-1551` (`--motor-price`, `--mprd-motor-price`) dùng bảng này thay danh sách viết tay.
- Agent 05 `_append_actuator_or_mechanism` gọi `select_actuator`; phần cầu chì FD, đối trọng, tay gạt, `--md-shaft-only` giữ nguyên trong Agent 05.
- Ghi chú van (`damper_classifier.build_model_note`) lấy mô-men từ **cùng** kết quả → ghi chú và giá không thể lệch.

### Bước 3 — OBD
- `swind_pricing.calc_obd(w_mm, h_mm, mult=1.0) -> {target_sell, frame_kg, blade_kg, acc_bo}`: thay `agent_05_bom_damper.py:141-160` (OBD rời, `mult=1`) và `agent_06_bom_diffuser.py:596-608` (OBD kèm cửa, `mult = obd_mult` — Agent 06 vẫn tự tính `obd_mult` SLB 2 lớp).
- Hằng số chuyển vào `pricing_constants.json` mục mới `obd`, **giữ nguyên số hiện tại**: `khung_kg_m: 0.158`, `nan_kg_m: 0.10`, `buoc_nan_m: 0.04`, `phu_kien_moi_nan: 1500`, `phu_kien_co_dinh: 5000`, `he_so: 1.15`. Giá nhôm vẫn đọc `diffuser_rules.aluminum_selling_price_per_kg`.

### Bước 4 — Lưới / LCCT / Lọc G4
- `swind_pricing.mesh_price(w_mm, h_mm, loai)` với `loai ∈ {"luoi", "lcct"}` → `K("cua.luoi_m2")` / `K("cua.luoi_chan_con_trung_m2")`; `swind_pricing.filter_g4_price(w_mm, h_mm)` → `K("cua.loc_g4_m2")`. Quy ước làm tròn đặt trong hàm (một chỗ).
- Thay 6 chỗ: `agent_06:109, 126, 203, 570, 583`, `agent_04:572, 956`.
- **Thay đổi giá có chủ đích:** ống/cút kèm LCCT ở Agent 04 (`duct_classifier.has_mesh_on_rect`, Model `+ LCCT`) đổi từ `luoi_m2` 150k → `luoi_chan_con_trung_m2` 200k/m². Lưới thường trên cửa giữ `luoi_m2`.

### Bước 5 — VAT ở Agent 10
- `agent_10_old_quote_carrier.py:580, 870` đọc `get_quotation_profile()["vat_rate"]` và `vat_label()` thay `0.08` / chữ `"8%"` viết cứng.

### Bước 6 — Xoá file thừa
- Xoá: `agent_03_price_learner.py`, `agent_00_5_boq_reviewer.py`, `swind_agent_0_ingestion.py`, `run_estimation_pipeline.py`, `tool_boq_learning.py` (đã kiểm: không file nào import; `run_estimation_pipeline.py` còn ghi vào `data/projects/` trái quy tắc đầu ra). Trước khi xoá: `grep` lại toàn repo (kể cả `.agents/`, `docs/`, `README.md`) và sửa tham chiếu tài liệu.
- Giữ: cặp `swind_excel_builder` ↔ `agent_07`, `swind_checker` ↔ `agent_08`, `extract_master_data` ↔ `agent_00` (agent mới đang gọi file cũ — chỉ là tên, không có logic song song). Ghi lại trong báo cáo cuối để xử lý đợt sau nếu User muốn.

## 5. Quy tắc khi hai nơi đang cho kết quả khác nhau

**Giá trị trong Master Data JSON thắng** (`pricing_constants.json`, `damper_rules.json`) — đó là nơi Kỹ thuật sửa giá qua `--constant`. Các trường hợp đã biết:

| Điểm | Hiện tại | Sau khi gom |
|---|---|---|
| Mô-men MD/MPRD | JSON `VG-11` (ghi chú) và code Agent 05 (giá) — hiện trùng số | Chỉ JSON |
| Lưới trên ống/cút có `+ LCCT` | 150k/m² (`luoi_m2`) | 200k/m² (`luoi_chan_con_trung_m2`) |
| Làm tròn | Agent 04 có `+1e-9`, Agent 05/06 không | Bản có `+1e-9` |
| VAT Agent 10 | `0.08` viết cứng | `financial_policy.json` |
| Ghi chú mô-men van MD **KLB** | Ghi chú theo diện tích (5/10/20Nm), giá luôn mã VIWECO 10Nm | **Ghi chú theo mã thật đã tính giá** (10Nm) — *quyết định của AI, xem mục 9* |

## 6. Đối chiếu giá từng dòng & ngưỡng cảnh báo (User chốt: thử ngưỡng gợi ý)

Baseline E2E hiện chỉ lưu **tổng tiền + số dòng / sheet**, không đủ để áp ngưỡng từng dòng. Bổ sung:

- `swind_e2e_regression.py --line-snapshot <file.json>`: sau khi chạy mỗi BOQ trong `input/`, đọc Sheet `BG` của file báo giá, lưu mỗi dòng có KL: `(file, sheet, dòng BOQ, Model, ĐVT, KL, đơn giá, thành tiền)`. Chạy cho cả chế độ mặc định và `--include-duct`.
- `swind_e2e_regression.py --line-diff <truoc.json> <sau.json>`: so khớp theo `(file, sheet, dòng BOQ)`, phân loại:
  - **Lớn** (in `⚠️`, User duyệt từng dòng): một dòng lệch đơn giá **> 2% hoặc > 50.000đ**, hoặc tổng một sheet lệch **> 0,5%**, hoặc dòng xuất hiện / biến mất / đổi Model.
  - **Nhỏ**: ghi vào báo cáo, không hỏi.
- Snapshot "trước" chụp **một lần** trên code hiện tại trước Bước 1; sau mỗi bước so với snapshot của bước trước để biết bước nào gây lệch.
- Báo cáo: `output/_pricing_consolidation/DIFF_<buoc>.md` (không commit — chứa dữ liệu dự án khách) gồm bảng lệch lớn, bảng lệch nhỏ, lý do theo bước. Tóm tắt gửi User trong hội thoại.
- Khi User duyệt: cập nhật cả 2 baseline E2E (`--save-baseline`) và baseline self-test.

## 7. Kiểm thử mỗi bước

1. Trước Bước 1: chạy toàn bộ kiểm thử, ghi trạng thái gốc (file nào đang `DIFF` / `INV-OK` từ trước thì không tính cho đợt này).
2. Unit test mới `tests/test_swind_pricing.py`: `excel_round` (x.5, số âm, `ndigits` âm, sai số dấu phẩy động `2.675`), `calc_obd` khớp số cũ cho 3 kích thước, `select_actuator` cho mọi hãng × kích thước biên (999/1000mm, 0.8/1.8 m²) × MPRD/MFD, `mesh_price` / `filter_g4_price`.
3. Sau mỗi bước: `swind_item_inspector.py --self-test`, `python -m unittest discover -s tests -p "test_swind_*.py"`, `swind_e2e_regression.py` (mặc định + `--include-duct`), `--line-snapshot` + `--line-diff`.
4. Kiểm riêng các cờ: chạy 1 BOQ có van MD + MPRD + MFD với `--motor-price`, `--mprd-motor-price`, `--md-shaft-only`, `--motor-brand HONEYWELL|KLB`, `--mfd-model 1.01..1.05` trước/sau — kết quả phải trùng (Bước 2).
5. Cuối đợt: `swind_item_inspector.py --refresh-index`; cập nhật `AGENTS.md` (bảng agent thêm dòng `swind_pricing`), `.agents/rules/03_FORMULA_INDEX.md`, `agent_05/06` role docs; ghi nguồn + ngày cạnh mỗi hằng số mới trong JSON.

## 8. Ràng buộc

- Tuân thủ quy trình sửa rule mục 7 AGENTS.md: `git log -S` trước khi đụng rule, ghi lý do + nguồn cạnh thay đổi.
- E2E ghi đè file học (`swind_experience_db`, `format_learning_db`) — không sửa các file này trong lúc E2E chạy.
- `swind_pricing` chỉ phụ thuộc `swind_utils` và `damper_classifier`; không agent nào được import chéo agent khác để lấy công thức giá.

## 9. Quyết định AI tự đưa ra (User kiểm khi đọc)

1. Ghi chú mô-men van MD hãng KLB theo mã giá thật (10Nm) thay vì theo diện tích — vì chỉ có một mã KLB MD trong bảng giá; chỉ đổi chữ ghi chú, không đổi giá.
2. `select_actuator` bao luôn MFD (không chỉ MD/MPRD) để bảng mã theo hãng của `--motor-price` sinh từ cùng một nguồn.
3. Hằng số OBD giữ nguyên giá trị hiện tại, chỉ dời chỗ.
4. Báo cáo lệch đặt trong `output/` (không commit) vì chứa tên dự án và giá khách.
5. Ba cặp file cũ/mới (`swind_excel_builder`, `swind_checker`, `extract_master_data`) để nguyên đợt này.

## 10. Để người triển khai tự quyết

Tên hàm/tham số chi tiết, cách tổ chức nội bộ `swind_pricing.py`, định dạng JSON snapshot, cách hiển thị bảng lệch — miễn đáp ứng mục 4–7.
