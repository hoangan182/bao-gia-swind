# BẢNG KIỂM KÊ RULE NHẬN DIỆN ỐNG GIÓ & PHỤ KIỆN (việc C2 — 2026-11-03)

Nguồn dữ liệu sống: [`data/master_data/duct_rules.json`](../data/master_data/duct_rules.json) · Bộ chạy: `src/duct_classifier.py` · Vai trò: `.agents/roles/duct_classifier_role.md` · Test: `tests/test_swind_duct_rules.py`.

## 1. Thứ tự nhận diện (rule đầu tiên khớp thắng; văn bản = Tên + Ghi chú của chính dòng)

| id | Loại | Khớp khi (tóm tắt) | Nguồn |
|---|---|---|---|
| OG-01 | VENTCAP | chụp thông hơi / ventcap / chụp khí / chụp hút | bd1d662 20/10 |
| OG-02 | CANVAS | khớp nối mềm / nối mềm / bạt mềm / canvas / cổ bạt | bd1d662 |
| OG-03 | FLEX_DUCT | ống mềm / flexible — trừ *lắp / nối / ra / chờ ống mềm* và dòng bắt đầu côn / chân rẽ / hộp / cút / tê | bd1d662; b5bf9c1 26/10 |
| OG-04 | SILENCER | tiêu âm / silencer | bd1d662 |
| OG-05 | PLENUM_BOX | hộp gió / box gió / hộp tĩnh áp / plenum | bd1d662 |
| OG-06 | SQUARE_TO_ROUND | vuông tròn / cvt / côn đầu quạt..., hoặc có AxB + D mà chưa có cạnh 2 | bd1d662 |
| OG-07 | END_CAP | bịt đầu / nắp bịt / ống bịt | bd1d662 |
| OG-08 | COUPLING_RT | măng sông / nối ống | bd1d662 |
| OG-09 | WYE | chạc 3 / chạc Y / ống quần / `Y: D200` | bd1d662 |
| OG-10 | TEE | tê / tee | bd1d662 |
| OG-11 | OFFSET_Z | zét / ống lượn / z đứng / offset / `Z 500x300` | bd1d662 |
| OG-12 | ELBOW | cút / co 90..30 / chếch / elbow | bd1d662 |
| OG-13 | SHOE_TAP / TAKEOFF | chân rẽ / gót giày / cổ trích / take-off | bd1d662 |
| OG-14 | REDUCER | côn... / reducer, bắt đầu *côn*, hoặc 2 đầu kích thước khác nhau | bd1d662 |
| OG-15 | FITTING_M2 | *phụ kiện* và không có kích thước | bd1d662 |
| OG-16 | SPIRAL_DUCT | ống tròn / tròn xoắn, hoặc là ống tròn | bd1d662 |
| OG-17 | DUCT_M2 | ĐVT / chữ m² và không có kích thước | bd1d662 |
| OG-18 | DUCT_RECT | còn lại | bd1d662 |

Bổ sung: OG-19 tiêu âm theo Title (b5bf9c1) · OG-20 Zét thiếu E → trống giá (7ebdc48) · OG-21 hộp trong Ghi chú (nhiều hộp cộng tiền — User 03/11; **1 hộp khác Tên → vẫn theo Ghi chú + HỎI LẠI USER — User chốt 03/11, mới**) · OG-22 LCCT/G4 trong cút (7cdc069) · OG-23 LCCT trong phụ kiện vuông · OG-24 canvas chống cháy.

## 2. Kiểm chứng tương đương
So code sau C1 (bản sao chưa commit): 52 BOQ (9.317 dòng parser, 46.585 lần giải mã × 5 biến thể cờ), 20.000 ca van, 75.000 ca ống ngẫu nhiên → 0 lệch. Self-test 53/53, unit 39/39, E2E mặc định & `--include-duct` PASS. Quét 52 BOQ: chưa có dòng hộp gió 1 kích thước Ghi chú khác Tên (14 dòng MKS là nhiều hộp — đã chốt).

## 3. Bốn phát hiện khi kiểm kê — ĐÃ SỬA 2026-11-03 (User duyệt)

| # | Dòng BOQ | Quyết định User | Sửa |
|---|---|---|---|
| 1–2 | CAND `Chụp thông gió D110/D160`; NOXH / CAND `Ventcap` | Chụp thông hơi / Ventcap / chụp thông gió: Swind **mặc định không báo** | OG-01 thêm *chụp thông gió* (→ VENTCAP, không còn thành ống xoắn); giữ nhóm CANVAS (bỏ mặc định, chỉ báo khi `--include-canvas`); console in rõ *trong đó N dòng Chụp thông hơi / Ventcap*; AGENTS.md 4b |
| 3 | TAHK `Lắp đặt giá đỡ ống gió ... thép góc L25x25` dưới Title `Nối mềm trước và sau quạt:` | Hàng thương mại | Parser: Tên (bỏ tiền tố *lắp đặt / gia công*) bắt đầu *giá đỡ / giá treo / quang treo / ty treo* → THUONG_MAI, không kế thừa nhóm từ Title (AGENTS.md 1a, 3c) |
| 4 | `Flexible connection` | Khớp nối mềm | OG-02 + `manufacturable_catalog.json` (CANVAS) thêm *flexible connection* |

**Giải trình E2E:** mặc định & `--include-duct` **không lệch** (canvas / ventcap vốn bị bỏ mặc định; giá đỡ trước nằm trong số canvas bị bỏ). Chạy thêm `--include-canvas` (bản sau C1 → bản mới):
- BG ĐHKK-TAHK: 157 → 134 dòng, −189.410.600 — bỏ 23 dòng giá đỡ trước bị tính như *ống gió vuông 25x25*. Số canvas bị bỏ mặc định 39 → 16.
- CAND: +181.056.000 — 4 dòng *Chụp thông gió* từ ống xoắn `SR-D110` 76.000 / `SR-D160` 111.000 → chụp thông hơi Inox `SFX-S-DN100` 105.000 / `SFX-S-DN150` 145.000 (số lượng lớn).
- NOXH: không đổi (Ventcap đã nhận đúng từ trước).
