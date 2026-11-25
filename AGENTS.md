# HỆ THỐNG BÁO GIÁ SWIND (HVAC MAS — AGENT 00..10) — BẢN GỌN

Chi tiết nguyên văn mọi rule: mục 6. File này chỉ giữ điều AI cần trong mọi phiên.

## 1. Chạy báo giá (fast-path)
- Hệ thống `src/swind_master_runner.py` + `agent_01..08` đã hoàn chỉnh. User nói *"Chạy báo giá / Tính giá / Lập báo giá..."* → **chạy ngay**, KHÔNG đọc code trước (chỉ đọc khi sửa lỗi / thêm tính năng):
  ```bash
  ./venv/bin/python src/swind_master_runner.py "<file_BOQ>" --non-interactive --auto-accept [cờ]
  ```
- KHÔNG viết script phụ đọc lại file báo giá: console đã in Coverage Audit, Bảng Tổng Hợp (Số dòng, Trước VAT, VAT 8%, Sau VAT), `[KIỂM SOÁT CUỐI]`, đường dẫn file.
- BOQ `.xls`: runner không đọc được → chuyển `.xlsx` (xlrd, giữ cột/dòng ẩn, merge) vào scratchpad, cùng tên, rồi chạy.
- Báo User: **chỉ File Báo Giá Cuối Cùng** `output/<Project>/<tên file gốc>.xlsx` (Sheet BOQ gốc + Sheet `BG`) và **chỉ Bảng Tổng Hợp** (theo sheet + tổng dự án); không liệt kê file thành phần / dự toán nội bộ, không bảng chi tiết từng mặt hàng.
- Cờ hay dùng: `--include-duct`, `--duct-only`, `--duct-uplift N`, `--include-box`, `--motor-brand`, `--motor-price`, `--mfd-model`, `--spec-priority name|note`, `--override "Sheet!dòng:k=v"`, `--sheets`, `--price-zero-qty`, `--strict`. Đủ cờ: [05_CLI_VA_KIEM_THU.md](.agents/rules/05_CLI_VA_KIEM_THU.md).
- Nhặt giá từ báo giá cũ (chỉ khi User yêu cầu rõ): skill `bao-gia-tu-bg-cu` / Agent 10 (xem 05). Báo cáo User bằng **Bảng tổng hợp Agent 10** (giá cũ + báo mới), KHÔNG dùng bảng runner (chỉ phần báo mới). Nhóm *Cần xác nhận* / *BG cũ đã đổi loại* / dòng nhiều đơn giá → AI bắt buộc hỏi User.
- Báo cáo dòng bị lọc: `output/<Project>/internal_estimation/INPUT_COVERAGE_REPORT.json`.

## 2. Mặc định đã chốt — KHÔNG hỏi lại
- Không báo Ống gió & phụ kiện (`--include-duct`), canvas / khớp nối mềm / chụp thông hơi Ventcap (`--include-canvas`), ống mềm (`--include-flex-duct`). Ống / cút kèm LCCT / lọc G4 → vẫn báo phần LCCT / lọc (OG-22).
- Động cơ van: luôn **1.02 Belimo**, kể cả BOQ ghi KLB / Honeywell / Kepler; chỉ đổi khi User chỉ định cờ. Không ghi *tuyến tính* → ON/OFF thường.
- Cột / dòng ẩn: bỏ qua, không báo, không hỏi (dòng ẩn copy nguyên văn sang `BG`, giữ ẩn).
- FD không ghi EI → FD thường tôn mạ kẽm không bọc; FD ghi EI → EI120 có bọc.
- Cửa vuông không ghi kiểu khuếch tán → **SDG** (không phải SD). Hộp gió chỉ cộng giá khi `--include-box`.
- Giá đỡ / ty treo, bộ nguồn van, van/lọc Y ống nước (DN/PN) → thương mại, không báo, không tô vàng. Lọc G4 rời → báo như hàng Swind.
- Lỗi chính tả đã duyệt (TY-01) / BOQ không dấu (TY-02) → sửa lặng lẽ.

## 3. Bắt buộc hỏi lại User khi console in
| Dấu hiệu console | AI làm | Lệnh duyệt |
|---|---|---|
| `⛔ BÁO GIÁ CHƯA HOÀN CHỈNH` (mã thoát 2: sheet lỗi, QA_REJECTED, KL có mà giá 0) | Liệt kê, hỏi; không báo tổng như bản hoàn chỉnh | sửa rồi chạy lại |
| (1c.) `TITLE_ROW_ASK` Loại 4 / Title không rõ loại hàng — tô vàng `⚠️ HỎI LẠI` | Liệt kê dòng, hỏi có báo theo Title? | `--title-wins "Sheet!dòng,..."` |
| (2b.) `⚠️ [KIỂM CHỨNG ĐỌC BOQ]` / PV-13 | Báo sheet, cột SL parser chọn vs cột nghi đúng; xác nhận trước khi chốt | `--override` |
| (2c.) `[ĐÃ ĐOÁN — XÁC NHẬN]` (TY-03/TY-04, sai dấu cụm chính TY-05) / `CHƯA RÕ` | Liệt kê dòng tô vàng | `agent_02_boq_reviewer.py --approve-pending` / `--add-typo "sai=đúng"` |
| (3.) Ghi chú / Spec khác Cột Tên (khác nan, khác van, EI trên van cơ) — trừ hãng động cơ | Liệt kê, hỏi theo Tên hay Ghi chú | `--spec-priority name\|note` |
| (4.) Ống kèm sản phẩm Swind khác / Ghi chú phủ định (PV-10) | Hỏi lại | — |
| (4.) Hộp gió Ghi chú 1 hộp khác KT Tên (OG-21) | Hỏi (đang tính theo Ghi chú) | — |
| (4c.) FD vừa ghi EI vừa *thường / không bọc* (VG-09) | Hỏi (đang báo EI có bọc) | — |
| (4c-0.) Dòng chỉ lấy hộp, không gồm cửa | Hỏi (mặc định không báo) | `--include-duct` báo phần hộp |
| `[HỎI LẠI USER] ... MẶC ĐỊNH` (MD-02/04/05/06) | Liệt kê dòng tô vàng (đang báo theo mặc định) | `--override "<sheet>!<dòng>:ok=1"` / `loai=<mã>` |
| `⚠️ [THÔNG BÁO USER]` Cửa/Van thiếu kích thước (PV-05) | Liệt kê (mã `S2`, `R3` → xin bảng tra) | `--override "Sheet!dòng:w=..,h=.."` |
| `⚠️ [CẢNH BÁO SÓT DÒNG]` / chưa kế thừa Title | Kiểm tra, sửa rule bóc tách | mục 5 |
| `⚠️` khác (KT giả định, KT lẻ, giá không tăng theo KT...) | Nêu rõ khi trả kết quả | — |

## 4. Git
- Được commit: `src/`, `tests/`, `scripts/`, `data/master_data/*.json`, `MASTER_DATA_*.xlsx`, `prices/`, bảng tính chuẩn `.xls`, `AGENTS.md`, `.agents/`, `docs/`, `plan/`.
- KHÔNG commit: `input/`, `input picture/`, `Phan hoi cua khach/`, BOQ ở thư mục gốc, `output/`, `data/projects/`, `Copy of *.xlsx`, `*_ESTIMATION.xlsx`.
- Kiểm trước push (phải không in dòng nào):
  `git -c core.quotePath=false diff --cached --name-only --diff-filter=ACMR | grep -E '^(input|output|data/projects|input picture|Phan hoi cua khach)/|^[^/]+\.(xlsx|xlsm|numbers|pdf)$|\.(xlsx|xlsm)$' | grep -vE '^data/master_data/MASTER_DATA_[A-Z]+\.xlsx$'`
- AI **không tự commit / push** — User tự đẩy.

## 5. Sửa rule / công thức
- Không đọc cả file lớn: `./venv/bin/python src/swind_item_inspector.py --locate "<chủ đề>"` + tọa độ hàm trong [03_FORMULA_INDEX.md](.agents/rules/03_FORMULA_INDEX.md); soi 1 mặt hàng: `swind_item_inspector.py "<mô tả>"`, quét file: `--audit-boq`.
- Rule nhận diện nằm trong JSON `data/master_data/*_rules.json` (diffuser / damper / duct / scope / typo / title_row / category): sửa JSON kèm `nguon`, `ly_do`, ví dụ — **không thêm if/elif vào code**. Hằng số giá: `pricing_constants.json`; công thức giá dùng chung: `src/swind_pricing.py`.
- Trước khi sửa rule: `git log -S "<đoạn code>"` + tìm dự án gốc trong `input/` → rẽ nhánh theo điều kiện, không xóa thẳng rule cũ; đọc BOQ chỉ qua Reader core `swind_utils`.
- Kiểm thử: `swind_item_inspector.py --self-test`; `swind_pattern_lab.py --check` (~3s) rồi `swind_e2e_regression.py --modes default,duct --files-from output/_pattern_lab/e2e_files.txt` (file ảnh hưởng + canh gác); unit `./venv/bin/python -m unittest discover -s tests -p "test_swind_*.py"`; sau sửa code `--refresh-index`. Sửa đọc cấu trúc BOQ → E2E toàn bộ. Chi tiết: 05.
- Từ khóa loại hàng chỉ ghi trong JSON; `tests/test_swind_keyword_guard.py` chặn thêm vào code (`--update` chỉ cho giảm).

## 6. Đọc thêm khi cần
| File | Nội dung |
|---|---|
| [04_QUY_TAC_NGHIEP_VU.md](.agents/rules/04_QUY_TAC_NGHIEP_VU.md) | Toàn văn rule nghiệp vụ (Title/dòng, ống, cửa, van, EI, Kiểm soát cuối, đầu ra) |
| [05_CLI_VA_KIEM_THU.md](.agents/rules/05_CLI_VA_KIEM_THU.md) | Đủ cờ runner, Agent 10, inspector, kiểm thử E2E / pattern lab, baseline |
| [06_BAN_DO_AGENT.md](.agents/rules/06_BAN_DO_AGENT.md) | Bảng Agent 00..09, classifier, file JSON rule, file role |
| [03_FORMULA_INDEX.md](.agents/rules/03_FORMULA_INDEX.md) | Tọa độ hàm công thức trong agent 01/04/05/06 |
