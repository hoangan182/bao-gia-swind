# BẢNG KIỂM KÊ RULE NHẬN DIỆN VAN GIÓ (việc C1 — 2026-11-03)

Nguồn dữ liệu sống: [`data/master_data/damper_rules.json`](../data/master_data/damper_rules.json) (bảng dưới là bản tóm tắt để duyệt).
Bộ chạy: `src/damper_classifier.py` · Vai trò: `.agents/roles/damper_classifier_role.md` · Test: `tests/test_swind_damper_rules.py`.

## 1. Các bước (chạy theo thứ tự)

| id | Điều kiện → kết quả | Nguồn | Ví dụ BOQ thật |
|---|---|---|---|
| `VG-01` | Cột Model `FD` / `2.01` / `E-FD` → FD; `1.01` / `MFSD` → MFSD; `MFD` / `1.02..1.05` → MFD; `MPRD` (hoặc chính dòng ghi mprd / xả áp điện) → MPRD; `OBD/VCD/MD/NRD/PRD` → chính nó | bd1d662 20/10; dde7498 28/10 | C08 `Van FD + NRD` (parser ghi Model `FD`) |
| `VG-02` | Tra `subtype_rules.json VAN_GIO`: Tên hiệu lực + Model → chính dòng → cả Title (mặc định VCD). Chế độ note: Ghi chú (bỏ cụm *tấm/bọc chống cháy*) trước | bd1d662; 1e5672d 29/10 | MKS `Van điều chỉnh lưu lượng VCD, kt 300x300` → VCD |
| `VG-03` | PRD/MD + *xả áp / giảm áp* + *động cơ / điện / điều khiển / on-off* → MPRD | 1e5672d 29/10 | BDCC09 VGCG R64 `Van xả áp động cơ 1100x600` → M-PRD, Belimo tuyến tính 10Nm |
| `VG-04` | FD/MD/VCD + *chặn lửa / ngăn cháy / chống cháy...* + *động cơ / mô tơ / motor / mfd* → MFD (chế độ note: FD mà Ghi chú không ghi động cơ thì giữ FD) | bd1d662; 1e5672d | mẫu `Van chống cháy gắn mô tơ` |
| `VG-05` | PRD mà chính dòng ghi *mprd / xả áp động cơ / điện / điều khiển* → MPRD | dde7498 28/10 | mẫu |
| `VG-06` | Chế độ note: EI theo Ghi chú; NRD/PRD/MPRD/VCD + *bọc MgO* → EI60 | 1e5672d | mẫu |
| `VG-07` | Hãng động cơ mặc định Belimo — chỉ đổi theo cờ User hoặc mã 1.03 / 1.04 ở cột Model | AGENTS.md 4d | mẫu `Van MFD` + Ghi chú `Động cơ Honeywell` → vẫn 1.02 |
| `VG-08` | MD → EI 0 | bd1d662 | Minh Triết R241 `Van MD KT: 1800x400, EI60` → MD không bọc |
| `VG-09` | FD mặc định EI120 có bọc; *FD thường / loại thường / không EI...* → FD thường + hỏi lại; FD tròn → vuông | 590365b 30/10; b5bf9c1 26/10 | Minh Triết R231 `Van FD KT: 1000x400 - EI60` → EI120 |
| `VG-10` | Mã MFD: 1.02 (Belimo) / 1.03 (KLB) / 1.04 (Honeywell); chế độ note: *đa cánh / 2390* → 1.05, EI ≥ 120 / *bfn / 4751* → 1.01 | bd1d662; 1e5672d | 01.PYCVT R12 `Van MFD KT: 1000x200` → 1.02 |
| `VG-11` | Mô-men Belimo: cạnh modul ≥ 1000 → 10Nm (> 1.8 m² → 20Nm), còn lại 5Nm; Honeywell / KLB theo diện tích 0.8 / 1.8 m² | 4e14743 22/10; 7cdc069 02/11 | mẫu `Van MD 1000x400` → 10Nm |
| `VG-12` | Mẫu Model + ghi chú (MFD theo mã, FD EI / thường, MD theo hãng, MPRD, NRD/PRD/OBD/VCD có / không bọc) | bd1d662; 4e14743; 7cdc069 | — |
| `VG-13` | Parser tách van theo `+ / kèm / gắn / tích hợp / kết hợp / c/w / with` (không tách *kèm động cơ / cầu chì*); Mã SP chỉ bổ sung khi Tên chưa ghi van; `van MDF` = MFD; van chính MFSD > MFD > FD > MD > PRD > NRD > VCD | 1805d82; 4e14743; 7ebdc48 03/11 | C08 `Van FD+VCD` → FD + VCD; `Van MFD + VD` → MFD + VCD |

## 2. Kiểm chứng tương đương (trước khi đổi bất kỳ rule nào)
So code cũ (worktree `f31a9d4`) — 0 lệch: 52 BOQ `input/` (9.315 dòng parser, 2.147 van), 46.575 lần gọi `resolve_item_spec` với 5 biến thể cờ, 20.000 ca van ngẫu nhiên, 100.000 ca tách combo ngẫu nhiên. Self-test 53/53, unit 33/33, E2E mặc định & `--include-duct` PASS so ảnh chụp trước khi sửa.

## 3. Bốn phát hiện khi kiểm kê — ĐÃ SỬA 2026-11-03 (User duyệt)

| # | Lỗi | Sửa |
|---|---|---|
| 1 | TAHK R542/R571: Title `Van giảm áp kèm động cơ ...`, Tên chỉ `1000x600`, Ghi chú `Van MFD EI60` → MPRD (vì Tên hiệu lực lấy Title, tra Title trước Ghi chú) | Rule mới `VG-02A`: Tên chỉ ghi kích thước → loại van theo Ghi chú / cột Model của chính dòng (bỏ cụm *tấm/bọc chống cháy*); sau đó vẫn chạy `VG-03`/`VG-04` để kế thừa động cơ / xả áp từ Title (R327 Title `... kèm động cơ loại on/off FD` + Ghi chú `Van FD EI60` → MFD, giữ như cũ) |
| 2 | `Van FD và NRD` mất FD | `VG-13` tách thêm theo chữ *và* (trừ *và động cơ / cầu chì*) |
| 3 | `Miệng gio kèm OBD` (thiếu dấu), `AG_AAG-OBD-...` → van OBD rời | Parser `_match_text` (chỉ để so khớp): `miệng/cửa/mặt gio` = `gió`, `_` = khoảng trắng; mã `aag` thêm vào `manufacturable_catalog.json` (CUA_GIO) và `combo_diffuser_regex` |
| 4 | MD ghi EI bị bỏ EI | `VG-08`: MD giữ EI → bọc KSH 10mm như NRD/PRD/VCD (Agent 05 + runner + inspector bỏ chỗ ép EI = 0), ghi chú thêm *ĐG bao gồm bọc thêm tấm cách nhiệt KSH dày 10mm* |

**Giải trình E2E** (so ảnh chụp code trước khi sửa; 2 chế độ lệch cùng 6 file, cùng số tiền chênh):

| File | Chênh | Dòng |
|---|---|---|
| 01.PYCVT ĐƠN 69 | +2.592.000 | R16 `Van MD 1200x500` — Ghi chú `Đạt GHCL EI60` → bọc (#4) |
| 14. Minh Triết | +21.441.600 | R240 `Van FD và NRD` → FD EI120 + NRD (#2); R241, R242 `Van MD ... EI60` → bọc (#4) |
| BG ĐHKK-TAHK | +16.246.000 | R542, R571 MPRD 4.515.500 → MFD 8.577.000 (#1) |
| BOQ_ANH_KHACH_01 | +19.036.300, 24 → 26 dòng | R13, R37 → cửa SDG+O (#3); R26 `AG_NRD-1200×250`, R35 `AG_MFD-1100x1200...` trước bị lọc `OUT_OF_SCOPE_KHAC`, nay nhận ra mã van sau khi tách `_` (#3) |
| TONG HOP HVAC | +9.759.000 | 8 dòng `Van MD kèm động cơ ... EI30/EI60` → bọc (#4) |
| CAND `Tang áp HK A3` | +310.400 | R251 `Van gió MD 800x350 - EI30` (combo cửa + MD) → bọc (#4) |

## 4. Phát hiện mới (chưa sửa — thuộc việc C3 phạm vi, chờ User)
- `BOQ_ANH_KHACH_01` (BOQ bóc từ ảnh): parser bỏ R20–22 `IS 850x250` (lưới chắn côn trùng), R24–25 `AL IS-1000x800`, R27–29 `AG MPRD-1200×900-E160` — trên BG có ghi `⚠️ CHƯA BÁO GIÁ`. Danh mục chưa có từ khóa `is` đứng riêng / `mprd`. R31, R34, R35, R36 mỗi ô ghép 2 mặt hàng (lỗi OCR) — chỉ báo mặt hàng đầu.
