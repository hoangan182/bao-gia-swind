# SCOPE FILTER: PHẠM VI BÁO GIÁ THEO BẢNG RULE (báo / không báo / giữ giá đối tác / hỏi lại User)
> **Mã định danh:** `SWIND-SCOPE-FILTER`
> **Module thực thi:** [`src/scope_filter.py`](file:///Users/hoangan/work/PCCC/swind/src/scope_filter.py)
> **Bảng rule:** [`data/master_data/scope_rules.json`](file:///Users/hoangan/work/PCCC/swind/data/master_data/scope_rules.json) (danh mục từ khóa sản phẩm: `manufacturable_catalog.json` / `commercial_catalog.json`)
> **Vị trí trong luồng:** `SwindBOQParser.parse_sheet` (PV-01..PV-08, PV-12), `swind_master_runner` (PV-09 bỏ theo cờ, PV-10 dòng ống kèm sản phẩm Swind, PV-11 Full-BOQ Coverage Audit, PV-13 Kiểm soát cuối).
> **Kế hoạch gốc:** [KE_HOACH_TACH_AGENT_DOC_BOQ.md](file:///Users/hoangan/work/PCCC/swind/plan/KE_HOACH_TACH_AGENT_DOC_BOQ.md) mục 4 · Bảng kiểm kê: [BANG_RULE_PHAM_VI.md](file:///Users/hoangan/work/PCCC/swind/plan/BANG_RULE_PHAM_VI.md)

---

## 1. VAI TRÒ
- Quyết định **phạm vi**: dòng thuộc hệ khác (ống nước, PCCC nước, điện, thiết bị, giá đỡ...) → thương mại; dòng không báo (thương mại / ống mềm / ống không kích thước / Zét thiếu E) thì bỏ, **trừ khi BOQ có đơn giá đối tác (giữ giá)**; cửa/van thiếu kích thước → không báo + thông báo; dòng chỉ lấy hộp → hộp gió + hỏi lại; mặc định không báo ống gió / canvas / chụp thông hơi / ống mềm theo cờ; dòng ống kèm LCCT / G4 → báo phần LCCT / G4.
- **Không** phân loại chi tiết loại cửa / van / ống (đó là `diffuser_classifier` / `damper_classifier` / `duct_classifier`), không tính giá.

## 2. CÁC RULE
| id | Nội dung |
|---|---|
| PV-01 | Ống nước / chữa cháy / ống đồng / cáp điện / bộ nguồn van / van nước DN → thương mại (van giảm áp / xả áp có KT hoặc tôn / EI / động cơ là van gió) |
| PV-02 | Tên bắt đầu thiết bị / phụ trợ / giá đỡ (kể cả *lắp đặt giá đỡ*) → thương mại, không kế thừa nhóm Title |
| PV-03 | Kẹp bích / ty treo / bu lông → thương mại |
| PV-04 | Nhóm không báo + ống không KT + Zét thiếu E → bỏ; có đơn giá đối tác → giữ dòng |
| PV-05 | Cửa / Van / Canvas không KT → không báo, thông báo User |
| PV-06 | Cửa tròn EAD → thương mại |
| PV-07 | Dòng cửa *chỉ gồm hộp* → hộp gió (ONG_GIO), hỏi lại |
| PV-08 | Ống không KT là kẹp bích / hộp (ĐVT khác m²) → thương mại |
| PV-09 | Mặc định không báo ONG_GIO / CANVAS (+ chụp thông hơi) / ONG_MEM theo cờ; `--only-cua-van` |
| PV-10 | Không báo ống: ống/cút kèm LCCT / G4 → báo phần LCCT / G4; ống ghi sản phẩm Swind khác / phủ định → hỏi lại |
| PV-11 | Danh sách từ khóa Full-BOQ Coverage Audit |
| PV-12 | Mã `IS` đứng đầu Tên ngay trước kích thước → LCCT; `mprd` → van |
| PV-13 | Cảnh báo kiểm chứng đọc BOQ ở sheet có dòng báo giá → `⚠️ [HỎI LẠI USER]` ở Kiểm soát cuối (không chặn) |

## 3. QUY TẮC SỬA RULE (AGENTS.md mục 7)
Sửa từ khóa / regex trong JSON; điều kiện mới → sửa đúng hàm PV-xx trong `scope_filter.py`. Mỗi rule có `nguon`, `ly_do`, `vi_du`. Chạy `tests/test_swind_scope_rules.py` + self-test + unit + E2E 2 chế độ. Thay đổi phạm vi ảnh hưởng số dòng / tổng tiền → so cả `--include-canvas`, `--include-flex-duct`, `--only-cua-van`.

## 4. LỊCH SỬ
- 2026-10-20 → 2026-11-03: rải trong `parse_sheet` và runner.
- 2026-11-03 (việc C3): trích ra `scope_rules.json` + `scope_filter`. Tương đương 100% so code sau C2: 52 BOQ × 5 tổ hợp cờ (mặc định, `--include-duct`, `--include-canvas`, `--include-flex-duct`, `--only-cua-van`) = 520 lần chạy runner, so log / Kiểm soát cuối, `INPUT_COVERAGE_REPORT.json`, sheet BG → 0 lệch. Rule mới (User chốt): PV-12 (`IS` / `mprd`), PV-13 (kiểm chứng đọc BOQ → hỏi lại).
