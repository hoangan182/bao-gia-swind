# DAMPER CLASSIFIER: NHẬN DIỆN VAN GIÓ THEO BẢNG RULE (`VAN_GIO`)
> **Mã định danh:** `SWIND-DAMPER-CLASSIFIER`
> **Module thực thi:** [`src/damper_classifier.py`](file:///Users/hoangan/work/PCCC/swind/src/damper_classifier.py)
> **Bảng rule:** [`data/master_data/damper_rules.json`](file:///Users/hoangan/work/PCCC/swind/data/master_data/damper_rules.json) (bảng tra từ khóa → loại van dùng chung: `subtype_rules.json -> VAN_GIO`)
> **Vị trí trong luồng:** `SwindBOQParser.parse_sheet` gọi `detect_dampers` / `sort_by_priority` để tách van trong dòng combo; `Agent01._resolve_damper_spec` gọi `classify` + `build_model_note` cho mọi dòng `VAN_GIO` (kể cả van phụ trong combo).
> **Kế hoạch gốc:** [KE_HOACH_TACH_AGENT_DOC_BOQ.md](file:///Users/hoangan/work/PCCC/swind/plan/KE_HOACH_TACH_AGENT_DOC_BOQ.md) mục 4 · Bảng kiểm kê: [BANG_RULE_VAN_GIO.md](file:///Users/hoangan/work/PCCC/swind/plan/BANG_RULE_VAN_GIO.md)

---

## 1. VAI TRÒ
- **Chỉ phân loại** 1 dòng van: loại van (FD / MFD / MFSD / MD / MPRD / PRD / NRD / VCD / OBD) → EI → hãng động cơ & mã MFD → mô-men động cơ → Model + ghi chú báo giá (phương án đơn cánh FSLF và đa cánh BFN).
- **Không** tính BOM / giá: số modul, thu côn, tỷ lệ giá đơn cánh – đa cánh, ghép van phụ trong combo vẫn ở `Agent01._resolve_damper_spec` (gọi `Agent05_DamperBOM`).
- Chỉ ghi lại vào item các trường Agent 01 trước đây đã ghi: `ei_rating` (chế độ note), `fd_non_ei_keyword` (cờ hỏi lại FD thường), `w/h/d` (FD tròn → vuông).

## 2. CẤU TRÚC BẢNG RULE
Các bước chạy **theo thứ tự id** `VG-01 → VG-13`; mỗi rule mang từ khóa / ngưỡng / mẫu chữ của nó, kèm `nguon`, `ly_do`, `vi_du_dung` (`vi_du_sai`, `vi_du_combo`).

| id | Bước |
|---|---|
| `VG-01` | Cột Model ghi mã Swind / loại van → chốt loại, bỏ qua tra từ khóa |
| `VG-02A` | Tên chỉ ghi kích thước → loại van theo Ghi chú / cột Model của chính dòng (rồi vẫn qua VG-03/04) |
| `VG-02` | Tra `subtype_rules.json VAN_GIO`: Tên hiệu lực + Model → chính dòng → cả Title cha (mặc định VCD); chế độ note: Ghi chú trước |
| `VG-03` | PRD/MD + xả áp + động cơ → MPRD |
| `VG-04` | FD/MD/VCD + chống cháy + động cơ → MFD |
| `VG-05` | PRD mà chính dòng ghi MPRD / xả áp điện → MPRD |
| `VG-06` | Chế độ note: EI theo Ghi chú; bọc MgO → EI60 |
| `VG-07` | Hãng động cơ mặc định Belimo (chỉ đổi theo cờ User / mã 1.03, 1.04) |
| `VG-08` | MD giữ EI BOQ ghi → bọc KSH 10mm |
| `VG-09` | FD mặc định EI120 có bọc; FD thường chỉ khi BOQ ghi rõ → hỏi lại User; FD tròn → vuông |
| `VG-10` | Mã MFD (1.02 mặc định; KLB 1.03; Honeywell 1.04; chế độ note 1.05 / 1.01) |
| `VG-11` | Mô-men động cơ MD / MPRD theo kích thước 1 modul |
| `VG-12` | Mẫu Model + ghi chú báo giá |
| `VG-13` | Parser: tách các van trong dòng combo, thứ bậc van chính (sửa gõ nhầm `van MDF` đã chuyển sang `typo_rules.json` TY-01) |

## 3. QUY TẮC SỬA RULE (AGENTS.md mục 7)
1. Đổi từ khóa / ngưỡng / mẫu chữ / thứ tự nguồn tra → **sửa JSON**. Đổi cấu trúc bước (thêm điều kiện mới) → sửa đúng hàm của bước đó trong `damper_classifier.py`, ghi id rule; không viết nhánh riêng cho 1 dự án.
2. Trước khi sửa: `git log -S "<từ khóa>"` tìm commit / dự án sinh ra rule (đã ghi ở `nguon`). Rẽ nhánh giữ case cũ; chỉ xóa khi rule được xác nhận sai.
3. Mỗi rule ≥ 1 ví dụ (ưu tiên dòng BOQ thật, ghi `nguon_boq`). Ví dụ kiểm `loai`, `model`, `ghi_chu_chua`, `fd_thuong`; combo kiểm `van`.
4. Chạy: `./venv/bin/python -m unittest tests/test_swind_damper_rules.py` + self-test + unit + E2E 2 chế độ; file nào lệch phải giải thích được.

## 4. LỊCH SỬ
- 2026-10-20 → 2026-11-03: rule nằm trong `Agent01._resolve_damper_spec` (~300 dòng) và `_detect_damper_type` của parser (xem `nguon` từng rule).
- 2026-11-03 (việc C tách agent đọc BOQ): trích ra bảng JSON + `damper_classifier`. Kiểm chứng tương đương 100% so code cũ (worktree HEAD `f31a9d4`): 52 BOQ `input/` — 9.315 dòng parser (2.147 van) + 46.575 lần gọi `resolve_item_spec` (5 biến thể cờ: mặc định, `--spec-priority note`, `--motor-brand KLB / HONEYWELL`, `--mfd-model 1.01`), 20.000 ca van ngẫu nhiên, 100.000 ca tách combo ngẫu nhiên → 0 lệch; E2E 2 chế độ không đổi.
- 2026-11-03 (User duyệt): `VG-02A` dòng chỉ ghi kích thước theo Ghi chú (TAHK R542), tách combo theo chữ *và*, MD có EI thì bọc (`VG-08`); parser nhận `miệng gio` / mã `AAG`. Giải trình E2E: `plan/BANG_RULE_VAN_GIO.md` mục 3.
