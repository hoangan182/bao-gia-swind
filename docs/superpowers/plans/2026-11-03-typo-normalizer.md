# Bộ chuẩn hóa lỗi chính tả BOQ (`typo_normalizer`) — Kế hoạch triển khai

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Gom mọi xử lý lỗi chính tả BOQ về một module + một file rule, khôi phục dấu theo từ vựng Swind, đoán mã viết tắt gõ sai theo ngữ cảnh (đánh dấu trên Sheet `BG`) và học lỗi mới qua hàng chờ Agent 02.

**Architecture:** `src/typo_normalizer.py` (module thuần, không đọc Excel) chạy bảng `data/master_data/typo_rules.json` (`TY-01..TY-04`). Parser và Agent 01 gọi `normalize_for_match(text, scope, events)` để lấy **chuỗi so khớp** — không bao giờ ghi lại nội dung BOQ. Parser phát hiện lỗi mã một lần mỗi dòng, gắn `item["typo_events"]`; runner đưa sự kiện ra Kiểm soát cuối, báo cáo độ phủ và hàng chờ Agent 02; `swind_excel_builder` tô vàng dòng trên `BG`.

**Tech Stack:** Python 3 (`./venv/bin/python`), `unittest`, `re`, `json`; dùng lại `swind_utils.remove_vietnamese_accents`. Không thêm thư viện.

**Spec:** [docs/superpowers/specs/2026-11-03-typo-normalizer-design.md](../specs/2026-11-03-typo-normalizer-design.md)

## Global Constraints

- Chuẩn hóa chỉ áp vào chuỗi so khớp; file BOQ và cột Tên trên Sheet `BG` giữ nguyên chữ khách viết. Ghi chú đánh dấu chỉ **thêm vào**, không thay.
- Không dùng LLM; cùng đầu vào → cùng kết quả.
- Mã van `MD / FD / MFD / MFSD / PRD / NRD / VCD / MPRD` chỉ được đoán khi ngữ cảnh loại hết các mã còn lại; không thì `HOI_LAI`.
- Không tự ghi vào từ điển sống khi chưa duyệt (chỉ vào `pending_approval_queue.json`).
- Mỗi rule `TY-*` có `id`, `nguon`, `ly_do`, `vi_du_dung`, `vi_du_sai` như các file rule khác.
- Chữ đánh dấu trên `BG`: đoán được → `⚠️ ĐÃ HIỂU: ODB = OBD — xin xác nhận`; không đoán được → `⚠️ CHƯA RÕ: <chữ gốc> (có thể: A / B)`. Khôi phục dấu và lỗi đã có trong từ điển: **không** đánh dấu.
- Dòng đã đoán không chặn báo giá.
- **AI không commit / push** (AGENTS.md — User tự đẩy git). Không có bước commit trong kế hoạch; cuối mỗi task chạy kiểm tra file cấm của AGENTS.md trên `git status`.
- Mọi lệnh Python chạy bằng `./venv/bin/python` từ gốc repo.

## Review Focus

1. **BOQ viết không dấu toàn bộ** (`Cua gio hoi kem van dieu chinh luu luong`) — phải nhận đúng loại hàng như bản có dấu, không tô vàng dòng nào. Test: `test_unaccented_row_classifies_like_accented` (Task 2).
2. **Chữ tiếng Việt không dấu trùng mã** (`sat` của *sắt* gần `SAG`, `mat` gần `MD`) — không được sinh sự kiện. Test: `test_vietnamese_syllables_not_flagged` (Task 3).
3. **Cột `DESCRIPTION` tiếng Anh** (`Supply air grille with OBD`, `fan`, `box`) — không sinh sự kiện giả. Test: `test_english_words_not_flagged` (Task 3).
4. **`tích hợp` không thành `hộp`** sau khôi phục dấu (`van tich hop dong co` vẫn tách combo đúng). Test: `test_protected_pair_tich_hop` (Task 2).
5. **Lỗi đã duyệt chạy lại không đánh dấu nữa** — sau `--approve-pending`, cùng dòng ra `TU_DIEN`, không vào `BG`/Kiểm soát cuối. Test: `test_approved_typo_becomes_silent` (Task 5).

---

## Cấu trúc file

| File | Việc |
|---|---|
| Create `data/master_data/typo_rules.json` | Bảng rule `TY-01 tu_dien`, `TY-02 khoi_phuc_dau/giu_dau`, `TY-03 ma_chuan/loai_tru/am_tiet`, `TY-04 doan` |
| Create `src/typo_normalizer.py` | Nạp rule (cache theo mtime), từ điển theo phạm vi, khôi phục dấu, phát hiện & áp lỗi mã, chữ đánh dấu `BG`, ghi rule học |
| Create `tests/test_swind_typo_rules.py` | Ví dụ từng rule + ca Review Focus |
| Create `.agents/roles/typo_normalizer_role.md` | Đặc tả vai trò (khuôn như `damper_classifier_role.md`) |
| Modify `src/swind_boq_parser.py` (~23–27, ~293–295, ~658, ~667, nơi dựng item) | Đổi chỗ vá cũ sang `normalize_for_match`; gắn `typo_events` |
| Modify `src/damper_classifier.py:282-285` | `fix_typos` gọi `apply_dictionary(text, "van")` |
| Modify `data/master_data/damper_rules.json` (VG-13) | Bỏ `sua_go_nham` (chuyển sang TY-01), ghi chú chỗ mới |
| Modify `src/agent_01_boq_extractor.py:504-505` | `raw_search` / `full_search` qua `normalize_for_match(..., "agent01", item.get("typo_events"))` |
| Modify `src/swind_master_runner.py` (`audit_full_boq_coverage` ~1306, `evaluate_quotation_gate` ~1757, sau khi có `all_items`) | Báo cáo, Kiểm soát cuối, gửi đề xuất Agent 02 |
| Modify `src/swind_excel_builder.py` (~574–592) | Dòng đã báo giá có sự kiện → thêm ghi chú + tô vàng |
| Modify `src/agent_02_boq_reviewer.py` (~89–150, CLI) | Đề xuất loại `TYPO`, duyệt ghi vào TY-01, cờ `--add-typo` |
| Modify `AGENTS.md`, `.agents/rules/03_FORMULA_INDEX.md` | Dòng Agent 01 · Chính tả, quy tắc đọc cảnh báo; refresh index |

Phạm vi (`scope`) dùng chung: `"ten"`, `"title"`, `"full"`, `"combo"`, `"van"`, `"agent01"`. Hằng `ALL_SCOPES` trong module.

---

### Task 1: Module + TY-01 gom bản vá cũ (E2E không lệch)

**Files:**
- Create: `data/master_data/typo_rules.json`, `src/typo_normalizer.py`, `tests/test_swind_typo_rules.py`, `.agents/roles/typo_normalizer_role.md`
- Modify: `src/swind_boq_parser.py:23-27,293-295,658,667`, `src/damper_classifier.py:282-285`, `data/master_data/damper_rules.json` (VG-13), `src/agent_01_boq_extractor.py:504-505`, `AGENTS.md` (bảng Quy trình B, thêm dòng *Agent 01 · Chính tả*)

**Interfaces:**
- Produces:
  - `typo_normalizer.ALL_SCOPES: tuple[str, ...]`
  - `load_rules(path: str | None = None) -> dict` — `{ "TY-01": rule, ..., "_all": data }`, cache theo mtime (khuôn `damper_classifier.load_rules`)
  - `apply_dictionary(text: str, scope: str) -> str` — chạy các mục `TY-01.tu_dien` **theo thứ tự trong file**, chỉ mục có `scope` trong `pham_vi`
  - `normalize_for_match(text: str, scope: str, events: list[dict] | None = None) -> str` — Task 1: chỉ `apply_dictionary`; Task 2/3 mở rộng (chữ ký giữ nguyên)

- [ ] **Step 1: Chạy baseline trước khi sửa** — `./venv/bin/python src/swind_item_inspector.py --self-test` và `./venv/bin/python -m unittest discover -s tests -p "test_swind_*.py"`. Ghi lại kết quả (phải đạt hết). E2E 2 baseline chạy ở Step 7.

- [ ] **Step 2: Tạo `typo_rules.json`** với `_mo_ta`, `phien_ban: "2026-11-03"`, `quy_tac: [...]`. `TY-01_TU_DIEN.tu_dien` đúng 4 mục, **đúng thứ tự này** (thứ tự giữ hành vi cũ):

  | # | `mau` (regex) | `thay` | `pham_vi` | `nguon` |
  |---|---|---|---|---|
  | 1 | `ồ` | `ố` | `["ten","title"]` | 1805d82 2026-10-20 (`.replace('ồ','ố')` parser) |
  | 2 | `\bvan\s+mdf\b` | `van mfd` | `["combo","van"]` | User xác nhận 2026-11-02 (VG-13) |
  | 3 | `\b(miệng\|cửa\|mặt)\s+gio\b` | `\1 gió` | `["ten","full","combo"]` | User chốt 2026-11-03, BOQ_ANH_KHACH_01 R13 |
  | 4 | `_` | ` ` | `["ten","full","combo"]` | User chốt 2026-11-03, BOQ_ANH_KHACH_01 R37 |

  `TY-02`, `TY-03`, `TY-04` tạo khung rỗng (`"bat": false`) để Task 2/3 điền.

- [ ] **Step 3: Viết test** `tests/test_swind_typo_rules.py` (khuôn `test_swind_damper_rules.py`):
  - `test_every_rule_has_source_and_examples` — mọi rule có `nguon`, `ly_do`, ≥1 `vi_du_dung`.
  - `test_dictionary_examples` — chạy `vi_du_dung` của TY-01 (dạng `{"vao","pham_vi","ra"}`), gồm: `("cửa hồi","ten") → "cửa hối"`; `("cửa hồi","full") → "cửa hồi"`; `("van mdf 400x400","combo") → "van mfd 400x400"`; `("van mdf","ten") → "van mdf"`; `("miệng gio kèm obd","ten") → "miệng gió kèm obd"`; `("ag_aag-obd","ten") → "ag aag-obd"`; `("ag_aag-obd","title") → "ag_aag-obd"`; `("miệng gio_kèm","ten") → "miệng gio kèm"` (mục 3 chạy trước mục 4 — giữ đúng hành vi cũ).
  - `test_legacy_equivalence` — với 30 chuỗi mẫu (lấy cột Tên từ 3 file trong `input/` bằng Reader core, nạp lúc test; bỏ qua nếu thư mục trống), so `normalize_for_match(s,"ten")` với biểu thức cũ `_old_match_text(s.lower().replace('ồ','ố'))` (sao chép thân `_match_text` cũ vào test làm mốc).

- [ ] **Step 4: Chạy test để thấy FAIL** — `./venv/bin/python -m unittest tests.test_swind_typo_rules -v` → `ModuleNotFoundError: typo_normalizer`.

- [ ] **Step 5: Viết `src/typo_normalizer.py`** (`load_rules`, `apply_dictionary`, `normalize_for_match`) rồi đổi chỗ gọi:
  - parser 293: `name_lower = typo_normalizer.normalize_for_match(name_str.lower(), "ten")`
  - parser 294: `full_name_lower = typo_normalizer.normalize_for_match(f"{full_name_str} {aux_context}".lower().strip(), "full")`
  - parser 295: `sec_lower = typo_normalizer.normalize_for_match(f"{current_section} {current_section_aux}".lower(), "title").strip()`
  - parser 658: `search_combo_txt = typo_normalizer.normalize_for_match(search_combo_txt, "combo")`
  - parser 667: `own_txt = typo_normalizer.normalize_for_match(f"...".lower().replace("\n", " "), "combo")`
  - xóa `_match_text` (chỉ parser dùng — xác nhận bằng `grep -rn "_match_text" src tests`).
  - `damper_classifier.fix_typos(text, rules=None)` → `return typo_normalizer.apply_dictionary(text, "van")` (giữ chữ ký; `detect_damper_type` không đổi). Bỏ `sua_go_nham` khỏi VG-13, thêm `"sua_go_nham_chuyen_sang": "typo_rules.json TY-01"`.
  - Agent 01 dòng 504–505: bọc 2 chuỗi bằng `normalize_for_match(..., "agent01", item.get("typo_events"))` (TY-01 chưa có mục `agent01` → không đổi kết quả).
  - Viết `.agents/roles/typo_normalizer_role.md`; thêm dòng *Agent 01 · Chính tả* vào bảng Quy trình B trong `AGENTS.md`.

- [ ] **Step 6: Chạy test** — `./venv/bin/python -m unittest discover -s tests -p "test_swind_*.py"` → toàn bộ PASS; `./venv/bin/python src/swind_item_inspector.py --self-test` → PASS.

- [ ] **Step 7: E2E 2 baseline** — `./venv/bin/python src/swind_e2e_regression.py` và bản `--include-duct` (theo cách chạy 2 baseline trong AGENTS mục 4/7). Điều kiện qua: **không file nào `DIFF` / `FAIL`** so với trước Step 5. Có lệch → sửa thứ tự/phạm vi TY-01 cho tới khi khớp, không lưu baseline.

---

### Task 2: TY-02 khôi phục dấu theo từ vựng

**Files:**
- Modify: `data/master_data/typo_rules.json` (TY-02), `src/typo_normalizer.py`, `tests/test_swind_typo_rules.py`

**Interfaces:**
- Consumes: `load_rules`, `normalize_for_match` (Task 1)
- Produces:
  - `vocabulary_phrases() -> dict[str, str]` — `{cụm_bỏ_dấu: cụm_có_dấu}`, chỉ cụm ≥ 2 chữ, có ít nhất 1 ký tự có dấu, cụm bỏ dấu **chỉ ứng với một** cụm có dấu (trùng nhiều → loại). Nguồn: mọi list chuỗi dưới khóa chứa `tu_khoa`, `keywords`, `tien_to`, `bat_dau` trong `diffuser_rules.json`, `damper_rules.json`, `duct_rules.json`, `scope_rules.json`, `manufacturable_catalog.json`, `subtype_rules.json`; bỏ chuỗi có ký tự regex (`\ ( ) [ ] | ? * + ^ $`); cộng `TY-02.them`, trừ `TY-02.bo`. Cache theo mtime các file nguồn.
  - `restore_accents(text: str) -> tuple[str, list[dict]]` — sự kiện `{"loai": "KHOI_PHUC_DAU", "goc": str, "sua": str, "rule": "TY-02"}`
  - `normalize_for_match` thêm bước `restore_accents` sau `apply_dictionary` khi `scope in TY-02.pham_vi` (`["ten","title","full","combo","agent01"]`).

- [ ] **Step 1: Điền TY-02**: `pham_vi` như trên; `giu_dau: ["hộp","hợp","côn","con","tê","te","cút","cut"]` (builder bổ sung cặp khi rà `vocabulary_phrases()` — in ra các chữ bỏ dấu trùng nhau và chọn); `them: []`, `bo: []`.

- [ ] **Step 2: Viết test**:
  - `test_restore_unaccented_phrase` — `restore_accents("cua gio hoi 300x300")[0] == "cửa gió hồi 300x300"`, 1 sự kiện `KHOI_PHUC_DAU`.
  - `test_restore_wrong_accent` — `"cửa giò cấp"` → chứa `"cửa gió"`.
  - `test_single_word_not_restored` — `restore_accents("con 400x200")[0] == "con 400x200"`.
  - `test_protected_pair_tich_hop` — `"van tich hop dong co"` không chứa `"hộp"`; và `damper_classifier` tách combo của `"van tich hop dong co 400x400"` cho cùng kết quả với `"van tích hợp động cơ 400x400"`.
  - `test_accented_text_unchanged` — chuỗi đã đúng dấu → không đổi, 0 sự kiện.
  - `test_unaccented_row_classifies_like_accented` — dựng item `CUA_GIO` như `_run_example` của `test_swind_diffuser_rules.py` cho `"Cua gio hoi kem van dieu chinh luu luong 600x300"` và bản có dấu → `resolved_spec` cùng `model_std` và `has_obd`.

- [ ] **Step 3: Chạy test để thấy FAIL** — `./venv/bin/python -m unittest tests.test_swind_typo_rules -v`.

- [ ] **Step 4: Viết `vocabulary_phrases`, `restore_accents`** — so khớp trên chuỗi bỏ dấu (`remove_vietnamese_accents(...).lower()`, độ dài bằng chuỗi gốc NFC nên ánh xạ vị trí 1:1), cụm dài trước, không chồng lấn, có ranh giới chữ; bỏ qua khi một chữ trong đoạn gốc thuộc `giu_dau` và khác chữ tương ứng trong cụm chuẩn; chỉ thay khi đoạn gốc ≠ cụm chuẩn.

- [ ] **Step 5: Chạy test** — unit toàn bộ + `--self-test` PASS.

- [ ] **Step 6: E2E 2 baseline** — liệt kê mọi file `DIFF`; mỗi file ghi 1 dòng giải thích (dòng nào, chữ nào được khôi phục, loại hàng trước/sau). **Dừng, đưa danh sách cho User duyệt** trước khi `--save-baseline`.

---

### Task 3: TY-03/TY-04 phát hiện & đoán mã gõ sai

**Files:**
- Modify: `data/master_data/typo_rules.json` (TY-03, TY-04), `src/typo_normalizer.py`, `src/swind_boq_parser.py` (nơi dựng dict item của dòng), `tests/test_swind_typo_rules.py`

**Interfaces:**
- Consumes: `apply_dictionary`, `restore_accents`, `normalize_for_match` (Task 1–2)
- Produces:
  - `detect_code_typos(row_text: str, context_text: str) -> list[dict]` — sự kiện `{"loai": "DOAN"|"HOI_LAI", "goc": str, "sua": str|None, "ung_vien": list[str], "rule": "TY-04"}`; `row_text` = Tên + Ghi chú + cột Model của chính dòng, `context_text` = Title cha + `row_text`.
  - `apply_guesses(text: str, events: list[dict] | None) -> str` — thay `\b{goc}\b` (không phân biệt hoa thường) bằng `sua` cho sự kiện `DOAN`.
  - `normalize_for_match(text, scope, events)` gọi `apply_guesses` cuối cùng.
  - Parser gắn `item["typo_events"] = restore_events + code_events` cho mọi item của dòng (cả item tách combo).

- [ ] **Step 1: Điền TY-03** (giá trị chốt):
  - `ma_chuan`: `obd {nhom:[CUA_GIO,VAN_GIO]}`, `lcct`, `g4`, `sdg`, `swl`, `wl`, `slb`, `scd`, `sag`, `dag`, `seeg`, `sobd`, `sdgk` `{nhom:[CUA_GIO]}`; van `{nhom:[VAN_GIO], chay, dong_co}`: `vcd(0,0)`, `nrd(0,0)`, `prd(0,0)`, `md(0,1)`, `fd(1,0)`, `mfd(1,1)`, `mfsd(1,1)`, `mprd(0,1)`; `ei {nhom:[CUA_GIO,VAN_GIO]}`.
  - `loai_tru`: `kt, mm, dn, pvc, ppr, upvc, ac, dc, tc, tcvn, ul, with, and, for, the, air, fan, duct, type, size, box, fcu, ahu, pau, erv, ref, inox, sus, ea, oa, sa, ra, fa`.
  - `am_tiet` (chữ tiếng Việt không dấu, bỏ qua): `^(ngh|ng|nh|ch|gh|gi|kh|ph|qu|th|tr|[bcdghklmnpqrstvx])?[aeiouy]{1,3}(ng|nh|ch|[cmnpt])?$`.

- [ ] **Step 2: Điền TY-04**: `tin_hieu_cua: ["cửa gió","miệng gió","cửa nan","cửa hồi","cửa cấp","louver","grille","diffuser","khuếch tán"]`, `tin_hieu_van: ["van","damper"]`, `tin_hieu_chay: ["chặn lửa","chống cháy","ngăn cháy","fire"]` + regex `\bei\s*\d{2,3}\b`, `tin_hieu_dong_co: ["động cơ","mô tơ","môtơ","motor","actuator"]`. So khớp tín hiệu trên chuỗi bỏ dấu cả 2 vế.

- [ ] **Step 3: Viết test**:
  - `test_odb_on_diffuser_row` — `detect_code_typos("Cửa gió hồi KT 250x250 + ODB", "Tủ điện tăng áp hút khói Cửa gió hồi KT 250x250 + ODB")` → 1 sự kiện `DOAN`, `goc="odb"`, `sua="obd"`.
  - `test_mdf_under_fire_motor_title` — `("MDF 600x400", "Van chặn lửa động cơ MDF 600x400")` → `DOAN`, `sua="mfd"`.
  - `test_ambiguous_damper_code_asks` — `("Van FMD 500x500", "Van FMD 500x500")` → `HOI_LAI`, `sua is None`, `sorted(ung_vien) == ["fd","md","mfd"]`.
  - `test_known_code_no_event` — `"Van MFD 500x500 + OBD"` → `[]`.
  - `test_vietnamese_syllables_not_flagged` — `"Gia do thep sat ma kem 600x400"`, `"mat bich"` → `[]`.
  - `test_english_words_not_flagged` — `"Supply air grille with OBD, fan box"` → `[]`.
  - `test_guess_applied_to_match_text` — `normalize_for_match("cửa gió hồi + odb", "agent01", events_odb)` chứa `"+ obd"`; và `Agent01.resolve_item_spec` cho item đó có `has_obd == True`.

- [ ] **Step 4: Chạy test để thấy FAIL.**

- [ ] **Step 5: Viết `detect_code_typos`, `apply_guesses`**:
  - Token: `re.findall(r"(?<![a-z0-9])[a-z][a-z0-9]{1,4}(?![a-z0-9])", remove_vietnamese_accents(apply_dictionary(row_text.lower(), "agent01")).lower())`; bỏ token thuộc `ma_chuan`, `loai_tru`, khớp `am_tiet`.
  - Ứng viên: token dài 2 → chỉ đảo 2 ký tự; dài ≥ 3 → khoảng cách Damerau (OSA) = 1 tới mã trong `ma_chuan`. Không có ứng viên → không sự kiện.
  - Lọc ngữ cảnh: nhóm của dòng = `{CUA_GIO nếu có tin_hieu_cua} ∪ {VAN_GIO nếu có tin_hieu_van}`; giữ ứng viên có `nhom` giao nhóm dòng; ứng viên van có `chay/dong_co` thì phải bằng đúng tín hiệu cháy / động cơ của ngữ cảnh.
  - Còn đúng 1 → `DOAN`; còn 0 hoặc ≥ 2 → `HOI_LAI` (`ung_vien` = danh sách trước lọc, sắp xếp).
  - Parser: gọi 1 lần mỗi dòng ngay sau khi có `raw_name_str`, `note_boq`, `model_str`, `clean_section`; truyền `events` vào các `normalize_for_match` ở Task 1 và gắn vào item.

- [ ] **Step 6: Chạy test** — unit toàn bộ + `--self-test` PASS.

- [ ] **Step 7: Quét `input/`** — không viết script phụ (AGENTS.md); thêm cờ `--typo-scan "<file.xlsx>"` vào `src/swind_item_inspector.py` (in mọi sự kiện `DOAN`/`HOI_LAI` theo sheet/dòng, dùng Reader core + parser, không ghi file). Chạy cho mọi file trong `input/`, gom danh sách. **Dừng, đưa danh sách cho User duyệt**: sự kiện sai → thêm `loai_tru`; đúng → giữ cho Task 5 nạp từ điển.

- [ ] **Step 8: E2E 2 baseline** — giải thích từng file `DIFF` như Task 2 Step 6; User duyệt trước khi lưu baseline.

---

### Task 4: Kiểm soát cuối, báo cáo nội bộ, đánh dấu Sheet `BG`

**Files:**
- Modify: `src/typo_normalizer.py`, `src/swind_master_runner.py` (`audit_full_boq_coverage` ~1306, `evaluate_quotation_gate` ~1757), `src/swind_excel_builder.py` (~574–592), `tests/test_swind_typo_rules.py`, `tests/test_swind_e2e_invariants.py` (nếu bất biến đọc dòng `[KIỂM SOÁT CUỐI]`)

**Interfaces:**
- Consumes: `item["typo_events"]` (Task 3)
- Produces:
  - `bg_flag(events: list[dict] | None) -> str | None` — nối bằng `"; "`: `DOAN` → `⚠️ ĐÃ HIỂU: {GOC} = {SUA} — xin xác nhận`; `HOI_LAI` → `⚠️ CHƯA RÕ: {GOC} (có thể: {A / B / C})`; mã in HOA; `TU_DIEN`/`KHOI_PHUC_DAU` → bỏ qua; không còn gì → `None`.
  - `gate_lines(all_items: list[dict]) -> list[str]` — tối đa 2 dòng, chỉ item `qty > 0`, liệt kê ≤ 10 dòng mỗi loại dạng `R{source_row} '{raw_name}': ODB→OBD`:
    - `[ĐÃ ĐOÁN — XÁC NHẬN] {n} dòng hệ thống tự hiểu lỗi gõ mã (tô vàng trên Sheet BG): ...`
    - `[HỎI LẠI USER] {n} dòng có mã nghi gõ sai, không đoán được (đang đọc nguyên chữ, tô vàng trên Sheet BG): ...`

- [ ] **Step 1: Viết test**:
  - `test_bg_flag_text` — sự kiện `DOAN odb→obd` → `"⚠️ ĐÃ HIỂU: ODB = OBD — xin xác nhận"`; `HOI_LAI fmd [fd,md,mfd]` → `"⚠️ CHƯA RÕ: FMD (có thể: FD / MD / MFD)"`; chỉ `KHOI_PHUC_DAU` → `None`.
  - `test_gate_lines` — 1 item `DOAN`, 1 item `HOI_LAI`, 1 item `qty=0` → đúng 2 dòng, item `qty=0` không có mặt.
  - `test_bg_sheet_marks_guessed_row` — chạy runner trên BOQ tạm dựng bằng `openpyxl` trong `tempfile` (1 sheet, 2 dòng: `Cửa gió hồi KT 250x250 + ODB` và `Cửa gió cấp 300x300`), `--non-interactive --auto-accept`; mở file báo giá: ô Tên dòng 1 vẫn là chữ gốc, cột Ghi chú (cột 16) **kết thúc bằng** `⚠️ ĐÃ HIỂU: ODB = OBD — xin xác nhận`, nền `FFFF00`; dòng 2 không tô vàng; console có `[ĐÃ ĐOÁN — XÁC NHẬN]`.

- [ ] **Step 2: Chạy test để thấy FAIL.**

- [ ] **Step 3: Cài đặt**:
  - `bg_flag`, `gate_lines` trong module.
  - `evaluate_quotation_gate`: `confirm.extend(typo_normalizer.gate_lines(all_items or []))` cạnh các dòng `[HỎI LẠI USER]` hiện có.
  - `audit_full_boq_coverage`: `coverage[sh_name]["typo_events"] = [{"row", "raw_name", "events"}]` cho item của sheet có sự kiện bất kỳ loại nào (kể cả `KHOI_PHUC_DAU`, `TU_DIEN`).
  - `swind_excel_builder` nhánh dòng đã báo giá: `flag = typo_normalizer.bg_flag(item.get("typo_events"))`; có `flag` → cột 16 của cả `row_std/row_fslf/row_bfn` = `f"{note} | {flag}"` (note rỗng → `flag`), tô `flag_fill` cột 1–16 trên mọi worksheet như nhánh chưa báo giá, thêm vào `self.flagged_bg_rows`.

- [ ] **Step 4: Chạy test** — unit toàn bộ + `--self-test` PASS; E2E bất biến vẫn đạt.

---

### Task 5: Học lỗi mới qua Agent 02

**Files:**
- Modify: `src/typo_normalizer.py`, `src/agent_02_boq_reviewer.py`, `src/swind_master_runner.py` (sau khi có `all_items`, cạnh chỗ Agent 02 lưu từ khóa), `tests/test_swind_typo_rules.py`, `AGENTS.md` (mục 6 Từ khóa tự học + bảng CLI)

**Interfaces:**
- Consumes: `item["typo_events"]`, `load_rules`
- Produces:
  - `typo_normalizer.add_dictionary_entry(goc: str, sua: str, nguon: str, pham_vi: list[str] | None = None) -> bool` — thêm cuối `TY-01.tu_dien` mục `{"mau": rf"\b{re.escape(goc.lower())}\b", "thay": sua.lower(), "pham_vi": pham_vi or list(ALL_SCOPES), "nguon": nguon}`; đã có `mau` → `False`, không ghi. Ghi JSON `indent=1, ensure_ascii=False` (khuôn file rule).
  - `agent_02_boq_reviewer.save_typo_proposal(goc: str, sua: str, project_name: str, context: str) -> None` — thêm vào `pending_proposals`: `{"loai": "TYPO", "raw_name": goc, "proposed_id": sua, "standard_name": sua, "project": ..., "context": ..., "proposed_by": "TypoGuess", "status": "PENDING_APPROVAL"}`; trùng `(loai, raw_name, proposed_id)` → bỏ.
  - `approve_pending_keywords`: đề xuất `loai == "TYPO"` được duyệt → `add_dictionary_entry(goc, sua, f"{ngày} — duyệt từ dự án {project}")`, **không** ghi `boq_keyword_learning.json`.
  - CLI `agent_02_boq_reviewer.py --add-typo "odb=obd"` (cho câu trả lời `HOI_LAI` của User) → `add_dictionary_entry(..., nguon=f"{ngày} — User chốt")`.
  - Runner: mỗi sự kiện `DOAN` → `save_typo_proposal`.

- [ ] **Step 1: Viết test** (dùng bản sao `typo_rules.json` và hàng chờ trong `tempfile`, vá đường dẫn module):
  - `test_add_dictionary_entry_idempotent` — lần 1 `True`, lần 2 `False`, `tu_dien` dài thêm đúng 1.
  - `test_typo_proposal_dedup` — gọi `save_typo_proposal` 2 lần cùng cặp → 1 mục.
  - `test_approve_typo_writes_rule_not_keywords` — duyệt `--all` → TY-01 có mục `odb`, `boq_keyword_learning.json` không đổi.
  - `test_approved_typo_becomes_silent` — sau khi thêm `odb→obd`, `detect_code_typos` của dòng `Cửa gió hồi + ODB` → `[]` và `normalize_for_match(..., "agent01")` chứa `obd`.

- [ ] **Step 2: Chạy test để thấy FAIL.**

- [ ] **Step 3: Cài đặt** theo Interfaces. `detect_code_typos` chạy trên chuỗi đã `apply_dictionary(..., "agent01")` nên lỗi đã duyệt không sinh sự kiện.

- [ ] **Step 4: Chạy test** — unit toàn bộ + `--self-test` PASS. Xác nhận E2E vẫn khôi phục `pending_approval_queue.json` (`LEARNING_FILES` trong `swind_e2e_regression.py`) và **thêm `typo_rules.json` vào `LEARNING_FILES`** để E2E không ghi rule.

---

### Task 6: Hồi quy toàn phần & tài liệu

**Files:**
- Modify: `AGENTS.md` (Fast-path: cách đọc `[ĐÃ ĐOÁN — XÁC NHẬN]` — AI phải liệt kê cho User như `HỎI LẠI USER`, mời duyệt `--approve-pending` / `--add-typo`), `.agents/roles/typo_normalizer_role.md`, `.agents/rules/03_FORMULA_INDEX.md`

- [ ] **Step 1:** `./venv/bin/python -m unittest discover -s tests -p "test_swind_*.py"` → PASS; `./venv/bin/python src/swind_item_inspector.py --self-test` → PASS.
- [ ] **Step 2:** E2E 2 baseline; mọi `DIFF` đã được User duyệt ở Task 2/3 → `--save-baseline` cho cả 2 (chỉ sau khi User đồng ý).
- [ ] **Step 3:** `./venv/bin/python src/swind_item_inspector.py --refresh-index`.
- [ ] **Step 4:** Cập nhật `AGENTS.md` + file vai trò; chạy lệnh kiểm tra file cấm của AGENTS.md trên `git status --porcelain` → không in dòng nào. Báo User danh sách file thay đổi để User tự commit.
