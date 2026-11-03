# BẢNG KIỂM KÊ RULE PHẠM VI BÁO GIÁ (việc C3 — 2026-11-03)

Nguồn dữ liệu sống: [`data/master_data/scope_rules.json`](../data/master_data/scope_rules.json) · Bộ chạy: `src/scope_filter.py` · Vai trò: `.agents/roles/scope_filter_role.md` · Test: `tests/test_swind_scope_rules.py`.

## 1. Các rule (bản tóm tắt — chi tiết từ khóa, nguồn, ví dụ ở JSON)

| id | Rule | Nơi gọi | Nguồn |
|---|---|---|---|
| PV-01 | Ống nước / chữa cháy / ống đồng / cáp điện / bộ nguồn van / van nước DN → thương mại | parser | bd1d662; 1e5672d; 7cdc069 (User) |
| PV-02 | Tên bắt đầu thiết bị / phụ trợ / giá đỡ → thương mại | parser | bd1d662; dde7498; giá đỡ User 03/11 |
| PV-03 | Kẹp bích / ty treo / bu lông → thương mại | parser | bd1d662 |
| PV-04 | Không báo theo nhóm / ống không KT / Zét thiếu E; có giá đối tác → giữ | parser | bd1d662; eeebc61 (User) |
| PV-05 | Cửa / Van / Canvas không KT → không báo, thông báo | parser + Kiểm soát cuối | User 03/11 |
| PV-06 | Cửa tròn EAD → thương mại | parser | bd1d662 |
| PV-07 | Dòng cửa chỉ gồm hộp → hộp gió + hỏi lại | parser + runner | User 03/11 |
| PV-08 | Ống không KT là kẹp bích / hộp → thương mại | parser | bd1d662 |
| PV-09 | Mặc định không báo ống gió / canvas + chụp thông hơi / ống mềm theo cờ | runner | 29/10; 590365b; User 03/11 |
| PV-10 | Ống kèm LCCT / G4 → báo phần LCCT / G4; ống ghi sản phẩm Swind khác → hỏi lại | runner | 7cdc069 (User) |
| PV-11 | Từ khóa Full-BOQ Coverage Audit | runner | bd1d662; dde7498 |
| PV-12 | **Mới:** mã `IS` đứng đầu Tên + kích thước → LCCT; `mprd` → van | parser + `diffuser_rules.json` (cờ lưới) + `manufacturable_catalog.json` | User 03/11 |
| PV-13 | **Mới:** cảnh báo kiểm chứng đọc BOQ ở sheet có báo giá → hỏi lại (không chặn) | runner (Kiểm soát cuối) | User 03/11 |

## 2. Kiểm chứng tương đương (trước khi thêm PV-12 / PV-13)
So code sau C2 (bản sao chưa commit): 520 lần chạy runner (52 BOQ × mặc định / `--include-duct` / `--include-canvas` / `--include-flex-duct` / `--only-cua-van`) — log & Kiểm soát cuối, `INPUT_COVERAGE_REPORT.json`, sheet BG → 0 lệch (1 dòng log *"Đã nhận diện format từ kinh nghiệm"* khác do nhật ký học định dạng dùng chung, không do code).

## 3. Giải trình E2E sau khi thêm PV-12 / PV-13
Mặc định & `--include-duct` lệch đúng 1 file, cùng số:
- **BOQ_ANH_KHACH_01**: 26 → 34 dòng, +12.782.600 — R20–22 `IS 850x250 / 800x350 / 1200x350` và R24–25 `AL IS-1000x800 / 1000x500` → LCCT (42.500 → 160.000); R27–29 `AG MPRD-1200×900 / 1200x500 / 1200×350-E160` → van xả áp động cơ M-PRD Belimo (4.376.300 / 4.043.800 / 3.920.000).
- PV-13: 52 BOQ không có cảnh báo kiểm chứng nên không đổi; giả lập 1 cảnh báo trên `xin giá 2110` → Kiểm soát cuối in `⚠️ [HỎI LẠI USER] Kiểm chứng đọc BOQ (PV-13) — sheet 'Sheet1' ...`.

## 4. Còn lưu ý (chưa sửa)
- BOQ_ANH_KHACH_01 bóc từ ảnh: chữ `E160` / `E130` là OCR của `EI60` / `EI30` → hiện chưa hiểu là EI (van MPRD báo không bọc). 4 ô ghép 2 mặt hàng (R31, R34, R35, R36) chỉ báo mặt hàng đầu.
