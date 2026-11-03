# BÀN GIAO PHIÊN — TÁCH AGENT ĐỌC BOQ (3 việc còn lại)

Ngày lập: 2026-11-03. Kế hoạch gốc: [KE_HOACH_TACH_AGENT_DOC_BOQ.md](KE_HOACH_TACH_AGENT_DOC_BOQ.md) (mục 4 = tiến độ).
Mỗi việc dưới đây làm trong **1 hội thoại riêng**, theo thứ tự A → B → C. Mở hội thoại mới bằng câu:
> *"Đọc plan/BAN_GIAO_TACH_AGENT_DOC_BOQ.md, làm việc A"* (hoặc B, C).

---

## 0. TRẠNG THÁI HIỆN TẠI (đã xong, đã commit trên nhánh `tach-agent-doc-boq`)

| Commit | Nội dung |
|---|---|
| `7ebdc48` | Rule phản hồi Kỹ thuật 02/11: chữ Z thiếu độ lệch E, van MDF, MFD + Mã SP, override skip |
| `eeebc61` | Bước 1–2: Agent 00B chỉ đọc (không viết lại BOQ), Reader core `swind_utils` (`detect_boq_header`, `hidden_col_letters`, `hidden_row_indices`, `visible_rows`, `visible_cols`), rule nhiều hộp gió trong Ghi chú |

- Nhánh chưa merge vào `main`, chưa push (User tự làm).
- Kiểm thử lúc bàn giao: self-test 53/53, unit 17/17, E2E mặc định PASS (baseline đã cập nhật).
- **Baseline `--include-duct` (`data/master_data/e2e_baseline_include_duct.json`) đang lệch 32 file từ TRƯỚC đợt này** (chưa cập nhật sau các đợt sửa rule trước). Đừng coi các lệch đó là lỗi do việc mới gây ra. Cách làm: chụp ảnh kết quả *trước khi sửa* vào scratchpad rồi so với ảnh *sau khi sửa* (xem mục 2). Chỉ lưu đè baseline này khi User đồng ý.

## 1. QUYẾT ĐỊNH USER ĐÃ CHỐT (không hỏi lại)

- Agent 00B **không được viết lại BOQ**; mọi đọc header/cột/dòng ẩn đi qua Reader core. Cấm chèn/bịa nội dung (tiêu đề giả, độ dày 0.58...).
- BOQ có sẵn **đơn giá đối tác** (kể cả hàng thương mại) → mặc định giữ nguyên trên BG; chỉ bỏ khi User yêu cầu. (CAND 11,8 tỷ cũ là ngoại lệ Kỹ thuật.)
- Ghi chú liệt kê ≥ 2 hộp (`BOX CẤP ... / BOX HỒI ...`) → 1 dòng, đơn giá = tổng các hộp, ghi chú nêu đủ.
- Tầng đọc cấu trúc: **giữ 1 bộ đọc** (Reader core) + thêm **bộ kiểm chứng độc lập** (việc A). Tầng nhận diện loại hàng: **tách riêng** từng loại (việc B, C).
- Quy trình sửa rule (đã ghi trong `AGENTS.md` mục 7): `git log -S` tìm nguồn gốc → rẽ nhánh giữ case cũ, chỉ xóa khi rule xác nhận sai → ghi lý do + nguồn → chạy đủ kiểm thử; file nào lệch phải giải thích được.

## 2. QUY TẮC LÀM VIỆC (bẫy đã gặp)

1. **Không chạy runner ghi vào `output/` thật** khi thử nghiệm (phiên trước lỡ ghi đè `output/Xin giá cửa dự án CAND/`, phải khôi phục từ `output/_history/`). Luôn đặt `SWIND_OUTPUT_DIR=<scratchpad>/out_xxx`.
2. **So sánh cũ/mới từng dòng:** sao chép `src/` vào scratchpad (`oldrepo/src`, symlink `data`, `venv`), chạy cả 2 bản với `SWIND_OUTPUT_DIR` khác nhau rồi so sheet `BG*`. Bản "cũ" phải là code cũ **hoàn chỉnh** (phiên trước từng so sai vì bản cũ dùng runner đã sửa) — dùng `git worktree add <scratchpad>/old <commit>` là chắc nhất.
3. Đừng sửa `src/` khi E2E đang chạy nền (runner chạy từng file bằng subprocess, sẽ nạp code mới giữa chừng).
4. Ảnh chụp E2E trước khi sửa: `swind_e2e_regression.py [--runner-args=--include-duct] --baseline <scratchpad>/x.json --save-baseline`.
5. Unit test không được ghi vào file dữ liệu sống (`format_learning_db.json`, từ điển học...) — trỏ `DB_PATH` sang thư mục tạm như `ReaderCoreTest`.
6. Lệnh kiểm thử:
   ```bash
   ./venv/bin/python src/swind_item_inspector.py --self-test
   ./venv/bin/python -m unittest discover -s tests -p "test_swind_*.py"
   ./venv/bin/python src/swind_e2e_regression.py
   ./venv/bin/python src/swind_e2e_regression.py --runner-args=--include-duct --baseline data/master_data/e2e_baseline_include_duct.json
   ./venv/bin/python src/swind_item_inspector.py --refresh-index   # sau khi sửa code
   ```

---

## VIỆC A — Bộ kiểm chứng độc lập cho tầng đọc cấu trúc ✅ XONG 2026-11-03 (xem KE_HOACH mục 4)

**Mục tiêu:** Reader core là điểm đọc duy nhất → nếu nó chọn nhầm cột/dòng thì mọi dự án sai theo. Thêm một bước *kiểm chứng* (không phải bộ đọc thứ 2, không sửa kết quả) để bắt lỗi kiểu CC17 chọn nhầm cột `TỔNG` thay `KL ECB`, hay VGCG/MKS đọc cột ẩn.

**Đề xuất làm:**
1. Trong Agent 00B (`src/agent_00b_input_normalizer.py`, đã có dry-run parser trong `_classify_format`), đếm thô trên file gốc cho từng sheet:
   - các cột **hiển thị** có số > 0 bên dưới header: số dòng có số, tổng giá trị, tiêu đề cột;
   - số dòng hiển thị có tên hàng + số lượng;
   - so với kết quả parser: cột SL parser chọn, số dòng có KL, tổng KL.
2. Cảnh báo `⚠️ [KIỂM CHỨNG ĐỌC BOQ]` khi: cột SL parser chọn có ít dòng có số hơn hẳn cột SL ứng viên khác cùng nhóm tiêu đề (KL/SL/Khối lượng/Q'ty); parser dùng cột/dòng ẩn; tổng KL các dòng đã bóc lệch lớn so với đếm thô. Quyết định với User: chỉ cảnh báo hay đưa vào `[KIỂM SOÁT CUỐI]` (`evaluate_quotation_gate`, `src/swind_master_runner.py`) như lỗi chặn.
3. Test mẫu trong `tests/`: workbook dựng tay có (a) dải cột ẩn chứa cột SL, (b) 2 cột KL (`KL CĐT` ẩn / `KL ECB` hiển thị), (c) cột `TỔNG` sau `KL ECB` như CC17 `DG-CAN HO`.

**Dữ liệu đối chiếu:** `input/Khối lượng VGCG tòa CC17 ...xlsm` (sheet `DG-CAN HO` và `D.2-CAN HO` cùng cấu trúc, SL đúng = cột `KL ECB` = 313/dòng), `input/260910_MKS_BoQ ...BP05a...xlsx` (dải ẩn `B:E`, `V:AC`, `AD:AN`), `input/26BDCC09-3.VGCG-Lan 1.xlsx`.

**Xong khi:** E2E 2 chế độ không lệch (việc này chỉ thêm cảnh báo), không cảnh báo giả trên 52 file `input/` (mỗi cảnh báo còn lại phải kiểm tra tay là đúng).

---

## VIỆC B — Mục 3 kế hoạch: tách bộ nhận diện CỬA GIÓ thành bảng rule ✅ XONG 2026-11-03 (xem KE_HOACH mục 4, `plan/BANG_RULE_CUA_GIO.md`)

**Hiện trạng:** `Agent01._resolve_diffuser_spec` trong `src/agent_01_boq_extractor.py` (dòng ~411–931, ~520 dòng, xem `.agents/rules/03_FORMULA_INDEX.md`) là chuỗi `if/elif` (Rule 1 KTC→KTM +50mm, Rule 2..6 `SD/SDG/SDGK/WL/SLB/ECG`, combo Cửa+Van, tháo lắp ×1.15, cấp bù, khuếch tán...). Một phần phân loại cửa còn nằm trong `SwindBOQParser.parse_sheet` (`src/swind_boq_parser.py`, ~860 dòng) và `data/master_data/subtype_rules.json`.

**Các bước:**
1. **Kiểm kê trước khi đổi:** liệt kê từng nhánh rule → mỗi rule ghi `id`, điều kiện, kết quả (model), `nguon` (`git log -S` ra commit/ngày/dự án), `ly_do`. Lưu bảng nháp vào `plan/` cho User duyệt.
2. **Test mẫu trước:** mỗi rule ≥ 1 dòng BOQ mẫu (Tên + Spec/Ghi chú + Title cha → model + ghi chú mong đợi), lấy từ BOQ thật trong `input/`. Thêm `vi_du_sai` cho các case từng sai: cửa thổi khuếch tán vuông (cổ 450→300 sai), "cấp bù" khi Tên đã ghi Louver/nan Z, Tên `nan bầu dục` vs Ghi chú `nan thẳng`.
3. **Trích bảng rule ra JSON** (VD `data/master_data/diffuser_rules.json`): danh sách có thứ tự ưu tiên tường minh; mỗi rule có `id`, `dieu_kien`, `ket_qua`, `nguon`, `ly_do`, `vi_du_dung`, `vi_du_sai`. Viết module `diffuser_classifier` đọc bảng → **kết quả E2E phải giữ nguyên 100%** trước khi đổi bất kỳ rule nào.
4. Chỉ sau đó mới sửa các lỗi đã biết (mục 1 kế hoạch: #3 khuếch tán, #4 cấp bù, #5 cảnh báo Tên vs Ghi chú thiếu cặp `nan bầu dục / nan thẳng`), mỗi lần sửa kèm test + giải trình E2E.
5. Viết file vai trò `.agents/roles/diffuser_classifier_role.md`, đăng ký vào `AGENTS.md`, refresh `03_FORMULA_INDEX.md`.

**Xong khi:** self-test, unit, E2E 2 chế độ không lệch ở bước 3; mọi lệch ở bước 4 đều được User duyệt.

---

## VIỆC C — Mục 4 kế hoạch: lặp lại cho VAN, ỐNG, PHẠM VI

Làm theo đúng khuôn việc B (kiểm kê → test mẫu → JSON giữ nguyên E2E → mới sửa):
- ✅ **C1 XONG 2026-11-03** (`src/damper_classifier.py`, `data/master_data/damper_rules.json`, `plan/BANG_RULE_VAN_GIO.md` — mục 3 có 4 phát hiện chờ User). `damper_classifier`: `Agent01._resolve_damper_spec` (dòng ~105–408) + phần combo/`_detect_damper_type` trong parser. Rule đã chốt cần giữ: FD mặc định EI120 có bọc; động cơ mặc định 1.02 Belimo; MD/MPRD mô-men theo cạnh ≥ 1000mm / > 1.8 m²; "van MDF" = MFD; Mã SP chỉ bổ sung loại van khi Tên chưa ghi.
- ✅ **C2 XONG 2026-11-03** (`src/duct_classifier.py`, `data/master_data/duct_rules.json`, `plan/BANG_RULE_ONG_GIO.md` — mục 3 có 4 phát hiện chờ User). `duct_classifier`: `Agent01._resolve_duct_spec` (~934–1019), `Agent04.detect_duct_subtype` (`src/agent_04_bom_duct.py`), `extract_duct_fitting_geometry`. Rule đã chốt: chữ Z thiếu độ lệch E → để trống giá; nhiều hộp trong Ghi chú → tổng các hộp.
- ✅ **C3 XONG 2026-11-03** (`src/scope_filter.py`, `data/master_data/scope_rules.json`, `plan/BANG_RULE_PHAM_VI.md`). `scope_filter` (phạm vi báo giá): `non_quotable_cats` + giữ giá đối tác trong `parse_sheet`, `audit_full_boq_coverage` (runner ~1214–1337), danh mục thương mại, ống gió/canvas/ống mềm mặc định không báo, LCCT/G4 trong dòng ống, bộ nguồn van = thương mại.
  - **Lưu ý đã phát hiện:** ở chế độ `--include-duct`, hộp gió lấy kích thước Ghi chú trước Tên (`dim_search_text` gộp Tên + Ghi chú). User đã chốt cách tính cho trường hợp nhiều hộp; trường hợp Ghi chú ghi 1 kích thước khác Tên chưa có cảnh báo hỏi lại — cần đưa vào bảng rule và hỏi User.

- **Bàn giao thêm từ việc B (2026-11-03):**
  - Áp nguyên tắc Title cha (AGENTS.md quy tắc 1a: thông số kế thừa, **loại hàng dòng tự ghi thắng Title**) vào `damper_classifier` / `duct_classifier` / `scope_filter`. Hiện nguyên tắc nằm rải rác: `standalone_chk_text` (Agent 01 cửa gió), danh sách loại trừ Tên trong `parse_sheet` (gán `CUA_GIO` theo Title, bước 2c khớp danh mục trên Tên + Title — đã thêm `tole / tôn / box`). Khi tách, gom về 1 bảng rule và rà các bước khớp danh mục khác trên `full_name_lower` (bước 3 thương mại, bước 4 ống gió) xem có kéo loại hàng từ Title không.
  - `scope_filter` nhận lại `BOX_ONLY_RX` (`src/swind_boq_parser.py`, dòng cửa gió *chỉ gồm hộp* → hộp gió) và lý do hỏi lại tương ứng trong `split_duct_rows_with_swind_products` (runner).
  - Baseline E2E mặc định đã lưu (User duyệt 5 file lệch, 2026-11-03).
  - Dòng Cửa/Van không có kích thước: không báo giá, giữ giá đối tác nếu có, chỉ thông báo (User chốt 2026-11-03) — `scope_filter` nhận lại rule này (`audit_full_boq_coverage` + `evaluate_quotation_gate` trong runner).

**Cuối việc C:** cập nhật baseline `--include-duct` sau khi User rà 32 file lệch tồn đọng.
