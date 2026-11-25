# CATEGORY CLASSIFIER: QUYẾT ĐỊNH LOẠI HÀNG THEO BẢNG RULE (`CUA_GIO` / `VAN_GIO` / `ONG_GIO` / `THUONG_MAI` ...)
> **Mã định danh:** `SWIND-CATEGORY-CLASSIFIER`
> **Module thực thi:** [`src/category_classifier.py`](file:///Users/hoangan/work/PCCC/swind/src/category_classifier.py)
> **Bảng rule (nguồn dữ liệu duy nhất):** [`data/master_data/category_rules.json`](file:///Users/hoangan/work/PCCC/swind/data/master_data/category_rules.json)
> **Vị trí trong luồng:** được `SwindBOQParser.parse_sheet` gọi 1 lần cho mỗi dòng BOQ (sau chuẩn hoá chính tả, trước trích kích thước). Kết quả ghi vào `item["decisions"]` trường `loai_hang` (rule = id `LH-xx`).
> **Kế hoạch gốc:** [2026-11-24-4-gom-logic-ve-classifier.md](file:///Users/hoangan/work/PCCC/swind/docs/superpowers/plans/2026-11-24-4-gom-logic-ve-classifier.md) Task 3

---

## 1. VAI TRÒ
- **Chỉ quyết định nhóm loại hàng** của 1 dòng: Học máy → hàng hệ khác → trường hợp đặc thù (lọc G4, cửa sổ cấp bù, hộp, phụ kiện ống đầu dòng, cửa/van theo mã) → catalog sản xuất / thương mại / ống gió theo Tên rồi Title → fallback bước 5. Trả `{"category", "rule_id", "nguon", "chac"}`.
- **Không** đọc file BOQ, không trích kích thước, không đổi loại sau khi có kích thước (PV-05..08 vẫn ở `scope_filter.adjust_category_after_dims`), không chọn Model (việc của `diffuser_classifier` / `damper_classifier` / `duct_classifier`).
- Cờ `is_plumbing_item` / `is_hvac_prd` do `scope_filter` tính (PV-01) rồi truyền vào; catalog nạp như `SwindBOQParser._load_catalogs`; từ điển học máy là `boq_keyword_learning.json`.

## 2. CẤU TRÚC BẢNG RULE
| Khối | Nội dung |
|---|---|
| `bien` / `co` | Biến văn bản (`name_lower`, `full_name_lower`, `sec_lower`, `name_str`, `note_lower`, `note_model_lower`, `raw_name_lower`) và cờ (`is_plumbing_item`, `is_hvac_prd`, `name_has_title`, `co_ghi_chu_model`, `title_khac_ten`). |
| `nhom_tu_khoa` | Nhóm từ khóa dùng chung (`@cua_dac_thu`). |
| `quy_tac` | Rule theo thứ tự `LH-01..LH-26`. Mỗi rule: `id`, `ten`, `khoi`, `khi` (điều kiện), `ket_qua`, `nguon_chu`, `chac`, `nguon`, `ly_do`, `vi_du_dung`, `vi_du_sai`. |
| `loc_tho_dung_rieng` | Tiền tố lọc thô + regex lọc tinh của LH-05 (`is_standalone_coarse_filter` đọc từ đây). |
| `khong_khop` | `LH-KHAC`: không rule nào khớp → `KHAC`, `chac` false. |
| `chuan_hoa` | Sau cùng: `PHU_KIEN_ONG→ONG_GIO`, `KHOP_NOI_MEM|CHUP_THONG_HOI→CANVAS`, `CUA_GIO` ghi Ventcap → `CANVAS` (OG-01). Không đổi rule quyết định. |

**Ngữ nghĩa chạy** (giữ y hệt chuỗi `if/elif` cũ):
- Rule chỉ xét khi loại hàng còn `KHAC`; rule khớp sau cùng là rule quyết định.
- `khoi`: khi 1 rule khớp, các rule còn lại cùng khối bị bỏ (`BUOC_1_4` = Học máy / hệ khác / bước 2-4; `BUOC_5` = fallback). Nhờ vậy Học máy trả `KHAC` vẫn bỏ bước 2-4 nhưng bước 5 vẫn chạy.
- `ket_qua`: `"<NHÓM>"`; `{"hoc_may": "<biến>"}` (không có trong từ điển → rule coi như không khớp); hoặc tra catalog `{"danh_muc": "SX"|"TM", "trong", "chi_ma"|"chi_nhom"|"nhom_tru", "gan", "bo_qua_khi": [{"ma"|"nhom", "khi"}]}` — từ khóa catalog so theo ranh giới từ (`scope_filter.match_keyword`), mục đầu tiên khớp thắng (thứ tự catalog).
- `nguon_chu`: `TEN` / `TITLE` / `GHI_CHU` / `HOC_MAY` / `TEN_HOAC_TITLE` (= `TITLE` khi dòng chỉ kích thước đã ghép Title vào tên — cờ `name_has_title` — vì chữ "tên" lúc đó là chữ Title).
- `chac` kết quả = `chac` của rule VÀ loại ≠ `KHAC`. `LH-26` (ống gió chỉ nhờ Title) `chac: false` → `default_rules.json` MD-04 tô vàng + hỏi lại.

Cú pháp điều kiện: `rule_dsl.RuleContext` (`tat_ca` / `mot_trong` / `khong` / `tu_khoa` (+`trong`, `tru`, `khop_bien`) / `regex` / `bat_dau` / `ham` / `so_sanh` / `thuoc`, cờ `"x"` / `"!x"`), cộng điều kiện riêng `{"tra_danh_muc": <spec catalog>}`. Hàm `ham` chỉ lấy trong danh sách trắng `PREDICATES` của module.

Thứ tự hiện tại: `LH-01/02` Học máy → `LH-03` hệ khác (PV-01) → `LH-04` cửa sổ cấp bù → `LH-05` lọc G4 → `LH-06` thiết bị / giá đỡ / nối quạt / bảo ôn (PV-02/16/17) → `LH-07` van nước / ống đồng → `LH-08` hộp → `LH-09` phụ kiện ống đầu dòng → `LH-10` ống / Z có ký hiệu → `LH-11` cửa đặc thù (Tên / Ghi chú) → `LH-12` Tên ghi cửa / miệng gió → `LH-13` Title cửa gió → `LH-14/15/16` mã IS / AL / van liền KT → `LH-17/18/19` catalog sản xuất (Tên / Ghi chú+Model / Title) → `LH-20/21` catalog thương mại (Tên / Title) → `LH-22/23` ống gió catalog (Tên / Title) → `LH-24` vật tư phụ (PV-03) → `LH-25` bước 5 chữ dòng → `LH-26` bước 5 chỉ nhờ Title → `LH-KHAC`.

## 3. QUY TẮC SỬA RULE (`.agents/rules/05_CLI_VA_KIEM_THU.md` mục 7)
1. **Sửa trong JSON, không thêm `if/elif` vào parser.** Cú pháp chưa đủ → thêm điều kiện chung nhỏ nhất vào `rule_dsl.py` (kèm test) hoặc hàm vào `PREDICATES`, không viết nhánh riêng cho 1 dự án.
2. Trước khi sửa: `git log -S "<từ khóa>"` tìm commit / dự án sinh ra rule (đã ghi ở `nguon`). Rẽ nhánh giữ case cũ; chỉ xóa khi rule được xác nhận sai.
3. Ghi `nguon` (ngày / dự án / người chốt) và `ly_do`. Case từng sai → `vi_du_sai`.
4. Mỗi rule ≥ 1 `vi_du_dung` (`ten`, `title`, `ghi_chu`, `model`, `co`, `hoc_may`, `loai`, tuỳ chọn `rule`); ví dụ tự đặt ghi `(tổng hợp)`.
5. Đổi id `LH-26` → sửa cả `default_rules.json` MD-04 `ap_cho`.
6. Chạy: `./venv/bin/python -m unittest tests/test_swind_category_rules.py` + `swind_pattern_lab.py --check` + self-test + unit + E2E 2 chế độ; file nào lệch phải giải thích được. `tests/test_swind_category_rules.py::test_golden_capture_matches` so với `output/_pattern_lab/category_golden.jsonl` (git-ignored) chỉ là **bằng chứng chuyển đổi một lần** (Việc 4, 2026-11-25; mã ghi đã xóa, không dựng lại được): khi CHỦ ĐÍCH sửa `category_rules.json` / catalog làm golden lệch → kiểm các dòng lệch đúng là dòng định đổi rồi **xóa** `output/_pattern_lab/category_golden.jsonl`. Lưới an toàn lâu dài = `vi_du_dung` / `vi_du_sai` + `swind_pattern_lab.py --check`.

## 4. LỊCH SỬ
- Đến 2026-11-24: quyết định loại hàng là chuỗi `if/elif` ~170 dòng trong `SwindBOQParser.parse_sheet` (id ghi vết tạm `PARSER-HOC-MAY` / `PARSER-TEN` / `PARSER-TITLE` / `PARSER-5-TEN` / `PARSER-5-TITLE`, Việc 2).
- 2026-11-25 (Việc 4 Task 3): trích ra bảng JSON + `category_classifier`. Kiểm chứng tương đương: 13.772 dòng ghi từ toàn bộ `input/` (Task 2) khớp 100% loại hàng và (nguồn, chắc); `swind_pattern_lab --check` 0 mẫu đổi; giá từng dòng toàn bộ `input/` 2 chế độ không đổi. `PARSER-5-TITLE` → `LH-26`.
