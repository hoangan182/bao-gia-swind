# Trợ lý báo giá từ báo giá cũ — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Biến luồng "nhặt giá BG cũ + báo mới phần còn lại" thành trợ lý AI dẫn từng bước, hỏi theo nhóm, nhớ quyết định theo dự án.

**Architecture:** Agent 10 (`src/agent_10_old_quote_carrier.py`) được nâng cấp: chữ ký ghép nhận combo / cấp EI / hộp gió, mỗi dòng có khoá ổn định + nhóm + đề xuất, xuất `--plan-json`, nhận `--decisions`. Module mới `src/old_quote_memory.py` lưu quyết định theo dự án ở `data/old_quote_memory/`. Skill `.agents/skills/bao-gia-tu-bg-cu/SKILL.md` điều phối cuộc hỏi đáp (gọi Agent 10 qua CLI, hỏi User bằng hộp chọn).

**Tech Stack:** Python 3.12 (`./venv/bin/python`), openpyxl, unittest.

**Spec:** `docs/superpowers/specs/2026-11-23-tro-ly-bao-gia-tu-bg-cu-design.md`

## Global Constraints

- Không đổi rule nhận diện / giá của Agent 01..08 và `swind_master_runner.py`.
- Cờ cũ của Agent 10 (`--accept-review`, `--accept-converted`, `--converted-yellow-only`, `--multi-price-new`, `--force-new`, `--neck-rows`, `--dry-run`, `--boq-sheet`) giữ nguyên hành vi.
- Kho ghi nhớ: `data/old_quote_memory/<project_key>.json`, thư mục nằm trong `.gitignore`; KHÔNG ghi vào `output/<Dự án>/` (runner xoá thư mục này mỗi lần chạy).
- Đọc BOQ chỉ qua Reader core `swind_utils` (`detect_boq_header`...).
- **Không commit / push** (AGENTS.md: User tự đẩy git) — bước "Commit" thay bằng kiểm tra `git status` không có file dữ liệu dự án.
- Chữ hiển thị cho User viết tiếng Việt.
- Ghi chú nguồn cạnh mỗi rule mới: `(2026-11-23, dự án 261123_HH3_RFQ)`.

## Review Focus

1. Báo lần 2 có **2 dòng trùng hệt tên + KT** (cùng mặt hàng, khác khu) → khoá `#1`, `#2` ổn định theo thứ tự; xoá 1 dòng ở giữa không được làm dòng kia nhận nhầm quyết định của dòng đã xoá → test ở Task 2.
2. Dòng BG cũ được chọn **đổi giá** giữa 2 lần (User sửa BG cũ) → quyết định `carry` không áp lại, hỏi lại với lý do "giá BG cũ đổi" → test ở Task 3.
3. File `--decisions` thiếu quyết định cho một dòng nhóm cần hỏi → dừng mã thoát 3, liệt kê khoá thiếu, KHÔNG âm thầm báo mới → test ở Task 4.
4. Kho ghi nhớ hỏng / JSON sai cú pháp → báo lỗi rõ tên file, coi như chưa có ghi nhớ (không crash, không ghi đè file hỏng) → test ở Task 3.
5. BOQ ghi EI ở cột Spec (không ở Tên), BG cũ ghi EI ở Model (`SWIND-1.05- MFD-EI120`) → vẫn so được cấp EI → test ở Task 1.

---

### Task 1: Chữ ký ghép — combo, cấp EI, hộp gió, cờ lý do

**Files:**
- Modify: `src/agent_10_old_quote_carrier.py` (`accessories`, `build_signature`, `load_old_quote` — dòng `sig["family_priced"] = ...`, `match_row`)
- Create: `tests/test_swind_old_quote_carrier.py`

**Interfaces:**
- Produces:
  - `combo_family(text: str) -> str | None` — trả `"VCD+FD"`, `"LOUVER+FD"`, `"LOUVER+MFD"`, `"GRILLE+<VAN>"` (VAN ∈ FD/MFD/MD/VCD/NRD) khi chính chuỗi ghi cả 2 thành phần; ngược lại `None`.
  - `ei_level(text: str) -> int | None` — regex `EI\s*-?\s*(\d{2,3})`, lấy số lớn nhất.
  - `priced_family(sig: dict) -> str` — combo: thay phần van bằng `family_model` nếu `family_model` là van; không combo: `family_model or family`. Thay dòng `sig["family_priced"] = sig["family_model"] or sig["family"]` trong `load_old_quote`.
  - `build_signature(...)` thêm khoá `sig["ei"]` (từ name + extra + model) và `"BOX"` trong `sig["acc"]` (regex `HOP GIO|\bBOX\b|PLENUM` trên chuỗi đã `norm`) cho GRILLE / LOUVER / combo cửa.
  - `match_row(item, entries)` trả thêm `res["flags"]: set[str]` ⊂ `{"profile", "swap", "box", "ei", "multi"}`. Khác chỉ bởi `BOX` → ứng viên `REVIEW` cờ `box` (không rơi vào `near`). FD / MFD / combo có van chống cháy: `sig["ei"] != es["ei"]` (None tính là một giá trị) → `REVIEW` cờ `ei`. GRILLE: chỉ so EI khi BOQ có EI.

- [ ] **Step 1: Viết test thất bại** (`tests/test_swind_old_quote_carrier.py`, kiểu unittest như `tests/test_swind_odd_size_flag.py`; helper `_entry(name, note="", model="", price=100000)` dựng entry bằng `build_signature` + `priced_family` giống `load_old_quote`)

```python
def test_combo_family(self):
    self.assertEqual(combo_family("Van điều chỉnh lưu lượng (VCD) + van ngăn lửa (FD) 200x150"), "VCD+FD")
    self.assertEqual(combo_family("Louver + lưới chắn côn trùng + van ngăn cháy FD 1000x400"), "LOUVER+FD")
    self.assertIsNone(combo_family("Van ngăn lửa (FD) cầu chì nhiệt 200x150, chịu lửa EI30"))

def test_combo_not_matched_to_single_valve(self):
    m = match_row(_item("Van điều chỉnh lưu lượng (VCD) + van ngăn lửa (FD) 200x150"),
                  [_entry("Van ngăn lửa (FD): 200x150", model="SWIND-2.01- E-FD-EI120")])
    self.assertEqual(m["status"], "NEW")

def test_combo_old_model_fd_still_combo(self):
    m = match_row(_item("Louver + lưới chắn côn trùng + van ngăn cháy FD 800x400, chịu lửa EI120"),
                  [_entry("Louver + Luới chắn côn trùng + Van ngăn cháy (FD) : 800x400", model="SWIND-2.01- E-FD-EI120")])
    self.assertEqual(m["status"], "EXACT")

def test_ei_mismatch_is_review(self):
    m = match_row(_item("Van ngăn lửa (FD) cầu chì nhiệt 600x300, chịu lửa EI30"),
                  [_entry("Van ngăn lửa (FD): 600x300", model="SWIND-2.01- E-FD-EI120")])
    self.assertEqual(m["status"], "REVIEW"); self.assertIn("ei", m["flags"])

def test_ei_from_spec_and_model(self):  # Review Focus 5
    it = _item("Van ngăn lửa điều khiển bằng động cơ (MFD) 800x800", spec="giới hạn chịu lửa EI120")
    m = match_row(it, [_entry("MFD 800x800", model="SWIND-1.05- MFD-EI120")])
    self.assertEqual(m["status"], "EXACT")

def test_box_mismatch_is_review(self):
    m = match_row(_item("Louver lấy gió tươi + lưới chắn côn trùng 300x150"),
                  [_entry("Louver lấy gió tươi 300x150 + Hộp gió + LCCT", note="WL+N+ hộp gió")])
    self.assertEqual(m["status"], "REVIEW"); self.assertIn("box", m["flags"])

def test_numbering_row_skipped(self):
    # BOQ tạm: header 'Mô tả/Description | Đv/ Unit | Khối lượng', ngay dưới là dòng '1 | 2 | 4 | 5'
    _, rows = load_boq_rows(self._boq_with_numbering_row())
    self.assertNotIn("2", [r["name"] for r in rows])
```

- [ ] **Step 2: Chạy test, xác nhận FAIL**

Run: `./venv/bin/python -m unittest tests.test_swind_old_quote_carrier -v`
Expected: FAIL — `ImportError: cannot import name 'combo_family'`.

- [ ] **Step 3: Cài đặt** các hàm ở khối Interfaces. Thứ tự ưu tiên trong `match_row` khi `same_tier` xếp hạng: điểm `reasons` rỗng trước, giữ nguyên các khoá điểm hiện có. Ghi chú nguồn cạnh từng rule.

- [ ] **Step 4: Chạy test, xác nhận PASS**

Run: `./venv/bin/python -m unittest tests.test_swind_old_quote_carrier -v` → OK.
Chạy thêm dry-run HH3 (không đổi file đầu ra):
`./venv/bin/python src/agent_10_old_quote_carrier.py "compare/23111/261123_HH3_RFQ_Cua_gio_Van_gio_Ham_L1_L2_Y1.xlsx" --old-quote "compare/23111/BG_SLAND - CTD - 20260429_CO LOA_HH3_MEP_BOQ_SENT_R4. UP.xlsx" --old-sheets "BG Than,BG Thân L1,BG Thân L2,BG Thân Y" --dry-run`
Expected: dòng 64 (VCD+FD) nằm trong "Không có trong BG cũ"; dòng 71–75 (FD EI30) và 20/21/22/25/37/44/49/50/52/53/54 (hộp gió) nằm ở "Cần xác nhận".

- [ ] **Step 5: Không commit** — `git status --short` chỉ thấy `src/agent_10_old_quote_carrier.py`, `tests/test_swind_old_quote_carrier.py`.

---

### Task 2: Khoá dòng, nhóm, đề xuất, gợi ý tuỳ chọn

**Files:**
- Modify: `src/agent_10_old_quote_carrier.py`
- Test: `tests/test_swind_old_quote_carrier.py`

**Interfaces:**
- Consumes: `match_row(...)["flags"]`, `sig["ei"]`, `sig["acc"]` (Task 1).
- Produces:
  - Hằng nhóm: `GROUP_EXACT="khop"`, `GROUP_PROFILE="kieu_nan"`, `GROUP_BOX="khac_hop"`, `GROUP_EI="khac_ei"`, `GROUP_CONVERTED="combo_doi_loai"`, `GROUP_MULTI="nhieu_gia"`, `GROUP_NEW="khong_co"`; `GROUP_ORDER` theo thứ tự trên; `GROUP_LABEL` (chữ tiếng Việt như bảng §5.3 spec).
  - `row_keys(items: list[dict]) -> dict[int, str]` — `boq_row → key`; key = `f"{norm(name)}|{family}|{size}|{'+'.join(sorted(acc))}|{ei}|{norm(unit)}#{n}"`, `n` = thứ tự xuất hiện (1-based) của phần trước `#` trong BOQ. Không dùng số dòng, STT, cột Spec thô.
  - `classify(match: dict) -> tuple[str, str, str]` — `(group, proposal, reason)`; `proposal ∈ {"carry","new","ask"}`. Ưu tiên cờ: CONVERTED/combo > `ei` > `box` > `profile`/`swap` > `multi` > EXACT. `khop` → `carry`; `khong_co`, `combo_doi_loai` → `new`; `kieu_nan` → `carry` nếu cùng mã nan (`sig["code"]`) hoặc cùng model nan, ngược lại `ask`; `khac_hop`, `khac_ei`, `nhieu_gia` → `ask`.
  - Chọn giá khi nhiều giá (`multi`): cùng cấu hình (box/ei) → sheet ưu tiên (`prio`) → tổng KL lớn nhất trong BG cũ; `reason` ghi đủ các giá + dòng BG cũ.
  - `suggest_options(matches: list[dict]) -> dict` — từ Model / ghi chú các entry khớp: `{"mfd_model": {"value": "1.05", "evidence": ["BG Than!85", ...]}, "motor_brand": {"value": "BELIMO", "evidence": [...]}}`; regex mã MFD `SWIND-(1\.0[1-5])`; hãng `BELIMO|KLB|HONEYWELL`; khoá vắng nếu không thấy.
  - `suggest_project_key(boq_path: str) -> str` — stem file, bỏ tiền tố ngày `^\d{6}_`, chuẩn hoá `[^A-Za-z0-9]+ → _`.

- [ ] **Step 1: Viết test thất bại**

```python
def test_keys_stable_on_insert_and_duplicates(self):  # Review Focus 1
    a = [_it(10, "Van VCD D100"), _it(11, "Louver 300x150"), _it(12, "Louver 300x150")]
    b = [_it(10, "Van VCD D100"), _it(11, "Cửa mới 500x500"), _it(12, "Louver 300x150"), _it(13, "Louver 300x150")]
    ka, kb = row_keys(a), row_keys(b)
    self.assertEqual(ka[10], kb[10]); self.assertEqual(ka[11], kb[12]); self.assertEqual(ka[12], kb[13])
    self.assertTrue(ka[11].endswith("#1")); self.assertTrue(ka[12].endswith("#2"))

def test_classify_groups(self):
    self.assertEqual(classify({"status": "EXACT", "flags": set()})[:2], ("khop", "carry"))
    self.assertEqual(classify({"status": "REVIEW", "flags": {"ei", "box"}})[:2], ("khac_ei", "ask"))
    self.assertEqual(classify({"status": "NEW", "flags": set()})[:2], ("khong_co", "new"))

def test_suggest_mfd_from_old_models(self):
    ms = [{"entry": {"model": "SWIND-1.05- MFD-EI120", "sheet": "BG Than", "row": 85, "note": "", "remark": "BELIMO"}}]
    self.assertEqual(suggest_options(ms)["mfd_model"]["value"], "1.05")

def test_suggest_project_key(self):
    self.assertEqual(suggest_project_key("x/261123_HH3_RFQ_Cua_gio.xlsx"), "HH3_RFQ_Cua_gio")
```

- [ ] **Step 2: Chạy test, xác nhận FAIL** — `./venv/bin/python -m unittest tests.test_swind_old_quote_carrier -v` → `ImportError: row_keys`.
- [ ] **Step 3: Cài đặt** các hàm ở Interfaces (thuần, không I/O).
- [ ] **Step 4: Chạy test, xác nhận PASS** — cùng lệnh → OK.
- [ ] **Step 5: Không commit** — `git status --short` như Task 1.

---

### Task 3: Kho ghi nhớ theo dự án

**Files:**
- Create: `src/old_quote_memory.py`
- Modify: `.gitignore` (thêm `data/old_quote_memory/`)
- Test: `tests/test_swind_old_quote_memory.py`

**Interfaces:**
- Consumes: khoá dòng (Task 2), entry BG cũ (`sheet`, `row`, `price`, `name`).
- Produces:
  - `MEMORY_DIR = <BASE_DIR>/data/old_quote_memory`
  - `load_memory(project_key: str, base_dir: str = MEMORY_DIR) -> dict` — không có file → `{}`; JSON hỏng → in `⚠️ [GHI NHỚ] File <path> hỏng (<lỗi>) — bỏ qua, không ghi đè` và trả `{"_corrupt": True}`.
  - `apply_memory(plan_rows: list[dict], memory: dict, entries: list[dict], old_quote: dict) -> None` — gán `row["decided_by"]="memory"` + `row["decision"]` khi: cùng key; `action=="new"` luôn áp; `action=="carry"` chỉ áp khi `old_quote["path"]` và `old_quote["mtime"]` trùng kho **và** entry `ref` còn tồn tại với cùng `price` và `name`. Không áp → giữ `decided_by=None`, `row["reason"]` thêm `"thay đổi so với lần trước: <giá BG cũ đổi | dòng BG cũ không còn | đổi file BG cũ>"`.
  - `save_memory(project_key: str, memory: dict, decisions: dict, plan: dict, run_totals: dict, base_dir: str = MEMORY_DIR) -> str` — gộp quyết định User (`decided_by ∈ {"user","memory"}`), cập nhật `old_quote`, `options`, nối `runs[]` (`at`, `boq`, `totals`); không ghi khi `memory.get("_corrupt")`; trả đường dẫn file.
  - Định dạng file (spec §5.4): `{project_key, display_name, old_quote:{path, mtime, sheets}, options:{runner_args:[...]}, rows:{key:{action, ref, price_at_decision, neck, decided_at, source_run}}, runs:[...]}`.

- [ ] **Step 1: Viết test thất bại** (dùng `tempfile.TemporaryDirectory()` làm `base_dir`)

```python
def test_carry_reapplied_only_when_price_same(self):  # Review Focus 2
    mem = {"old_quote": {"path": "bg.xlsx", "mtime": 1}, "rows": {"K#1": {"action": "carry", "ref": "BG!10", "price_at_decision": 100}}}
    rows = [{"key": "K#1", "decided_by": None, "reason": ""}]
    apply_memory(rows, mem, [{"sheet": "BG", "row": 10, "price": 120, "name": "x"}], {"path": "bg.xlsx", "mtime": 1})
    self.assertIsNone(rows[0]["decided_by"]); self.assertIn("giá BG cũ đổi", rows[0]["reason"])

def test_new_always_reapplied_even_if_file_changed(self):
    mem = {"old_quote": {"path": "a.xlsx", "mtime": 1}, "rows": {"K#1": {"action": "new"}}}
    rows = [{"key": "K#1", "decided_by": None, "reason": ""}]
    apply_memory(rows, mem, [], {"path": "b.xlsx", "mtime": 2})
    self.assertEqual(rows[0]["decided_by"], "memory")

def test_corrupt_file_not_overwritten(self):  # Review Focus 4
    p = os.path.join(d, "HH3.json"); open(p, "w").write("{bad")
    mem = load_memory("HH3", d); self.assertTrue(mem["_corrupt"])
    save_memory("HH3", mem, {"rows": {}}, {"rows": []}, {}, d)
    self.assertEqual(open(p).read(), "{bad")

def test_roundtrip(self):
    path = save_memory("HH3", {}, {"rows": {"K#1": {"action": "new"}}, "options": {"runner_args": ["--mfd-model", "1.05"]}},
                       {"rows": [{"key": "K#1", "decided_by": "user"}], "old_quote": {"path": "bg.xlsx", "mtime": 1, "sheets": ["BG"]}},
                       {"total": 1}, d)
    self.assertEqual(load_memory("HH3", d)["options"]["runner_args"], ["--mfd-model", "1.05"])
```

- [ ] **Step 2: Chạy test, xác nhận FAIL** — `./venv/bin/python -m unittest tests.test_swind_old_quote_memory -v` → `ModuleNotFoundError: old_quote_memory`.
- [ ] **Step 3: Cài đặt** `src/old_quote_memory.py` theo Interfaces; ghi file bằng ghi tạm + `os.replace` (không để file dở dang). Thêm `data/old_quote_memory/` vào `.gitignore` cạnh `data/projects/`.
- [ ] **Step 4: Chạy test, xác nhận PASS** — cùng lệnh → OK; `git check-ignore data/old_quote_memory/x.json` in ra đường dẫn.
- [ ] **Step 5: Không commit** — `git status --short`.

---

### Task 4: CLI `--plan-json` / `--decisions` / `--project-key` và ghép vào luồng chạy

**Files:**
- Modify: `src/agent_10_old_quote_carrier.py` (`main`)
- Test: `tests/test_swind_old_quote_carrier.py` (test CLI dùng `subprocess` trên BOQ + BG cũ tự dựng nhỏ; chỉ chạy tới `--plan-json` hoặc lỗi thiếu quyết định — không gọi runner)

**Interfaces:**
- Consumes: Task 1–3.
- Produces (CLI, thêm vào `argparse` hiện có):
  - `--project-key <str>` — mặc định `suggest_project_key(boq)`.
  - `--memory-dir <path>` — mặc định `MEMORY_DIR`; `--no-memory` tắt đọc/ghi kho.
  - `--plan-json <file>` — chạy ghép + `apply_memory`, ghi JSON rồi thoát 0 (không chạy runner, không ghi kho). Thiếu `--old-sheets` + có `--plan-json` → ghi `{"sheet_summary": [{"sheet", "priced_rows"}], "project_key_suggestion": ...}` rồi thoát 1.
  - Plan JSON: `{project_key, project_key_suggestion, boq, boq_sheet, old_quote:{path, mtime, sheets}, memory:{exists, decided_rows, last_run_at}, rows:[{key, boq_row, stt, name, unit, qty, group, proposal, reason, candidates:[{ref, name, model, note, price}], decided_by, decision}], suggested_options, remembered_options}`. `decided_by`: `"memory"` | `"auto"` (proposal `carry`/`new`) | `null` (proposal `ask`).
  - `--decisions <file>` — JSON `{rows:{key:{action:"carry"|"new", ref?:"Sheet!row", neck?:bool}}, options:{runner_args:[...]}}`. Khi có cờ này: `carried` = dòng `carry` (dùng `ref` nếu có, không thì ứng viên tốt nhất) ∪ dòng `auto`/`memory` có `carry`; còn lại báo mới; `neck:true` gộp vào tập `neck_rows`; `options.runner_args` nối vào `runner_args`. Dòng `decided_by=null` không có trong file → in `⛔ [THIẾU QUYẾT ĐỊNH] N dòng: <key...>` và thoát 3 (Review Focus 3). Quyết định trong file được ghi `decided_by="user"`.
  - Sau khi ghép file cuối thành công và `stats["unpriced_list"]` rỗng → `save_memory(...)`, in `💾 [GHI NHỚ] Đã lưu N quyết định: <path>`.
  - `OLD_QUOTE_MATCH_REPORT.json` thêm trường `key`, `group`, `decided_by` mỗi dòng.

- [ ] **Step 1: Viết test thất bại**

```python
def test_plan_json_groups_and_no_runner(self):
    rc, plan = self._run_plan()  # fixture: FD EI30 vs BG cũ EI120, VCD+FD, Louver có/không hộp, dòng mới
    self.assertEqual(rc, 0)
    groups = {r["name"]: r["group"] for r in plan["rows"]}
    self.assertEqual(groups["Van ngăn lửa (FD) 600x300, chịu lửa EI30"], "khac_ei")
    self.assertEqual(groups["Van điều chỉnh lưu lượng (VCD) + van ngăn lửa (FD) 200x150"], "khong_co")
    self.assertFalse(os.listdir(self.mem_dir))  # plan không ghi kho

def test_missing_decision_exits_3(self):  # Review Focus 3
    rc, out = self._run_with_decisions({"rows": {}})
    self.assertEqual(rc, 3); self.assertIn("THIẾU QUYẾT ĐỊNH", out)
```

- [ ] **Step 2: Chạy test, xác nhận FAIL** — `./venv/bin/python -m unittest tests.test_swind_old_quote_carrier -v` → lỗi `unrecognized arguments: --plan-json`.
- [ ] **Step 3: Cài đặt** theo Interfaces; giữ nguyên toàn bộ in console hiện có (bảng tổng hợp Agent 10).
- [ ] **Step 4: Chạy test, xác nhận PASS** — cùng lệnh → OK; chạy toàn bộ `./venv/bin/python -m unittest discover -s tests -p "test_swind_*.py"` → OK; `./venv/bin/python src/swind_item_inspector.py --self-test` → không lệch.
- [ ] **Step 5: Không commit** — `git status --short`.

---

### Task 5: Skill `bao-gia-tu-bg-cu` + tài liệu

**Files:**
- Create: `.agents/skills/bao-gia-tu-bg-cu/SKILL.md`
- Create: symlink `.claude/skills/bao-gia-tu-bg-cu` → `../../.agents/skills/bao-gia-tu-bg-cu`
- Modify: `.agents/roles/agent_10_old_quote_carrier_role.md`, `AGENTS.md` (mục *LUỒNG RẼ (ON-DEMAND) — NHẶT GIÁ TỪ BÁO GIÁ CŨ*)

**Interfaces:**
- Consumes: CLI Task 4.

- [ ] **Step 1: Viết `SKILL.md`** — frontmatter:
  `name: bao-gia-tu-bg-cu`; `description:` *"Dẫn User từng bước báo giá BOQ/RFQ mới theo báo giá cũ: nhặt giá dòng trùng vật tư + kích thước, phần còn lại hệ thống báo mới, nhớ quyết định theo dự án. Kích hoạt khi User yêu cầu copy/nhặt giá từ báo giá cũ sang BOQ mới."*
  Thân skill = 6 bước spec §5.1, mỗi bước ghi: lệnh CLI chính xác, đọc trường nào của plan JSON, hỏi gì (hộp chọn, tối đa 4 câu/lượt, nhóm theo `GROUP_ORDER`, mỗi nhóm ≤ 6 ví dụ + tổng số dòng + đề xuất đứng đầu có "(Đề xuất)"), ghi quyết định vào `<scratchpad>/decisions_<project_key>.json`. Kèm các luật: không dùng `--force-new`/`--accept-review` theo số dòng khi chạy qua skill; `--include-duct` chỉ khi User nói rõ; báo kết quả bằng bảng tổng hợp Agent 10 + link file cuối + danh sách dòng Kiểm soát cuối (theo AGENTS.md); lần báo lại chỉ hỏi dòng `decided_by=null` và nhắc 1 dòng "dùng lại: sheet ..., tuỳ chọn ...".
- [ ] **Step 2: Tạo symlink** — `mkdir -p .claude/skills && ln -s ../../.agents/skills/bao-gia-tu-bg-cu .claude/skills/bao-gia-tu-bg-cu`; kiểm `ls -L .claude/skills/bao-gia-tu-bg-cu/SKILL.md` → tồn tại.
- [ ] **Step 3: Cập nhật tài liệu** — role md: thêm cờ `--plan-json`, `--decisions`, `--project-key`, `--memory-dir`, `--no-memory`, bảng nhóm §5.3, kho ghi nhớ §5.4. `AGENTS.md`: mục Agent 10 thêm 1 đoạn "Chạy qua skill `bao-gia-tu-bg-cu` (User chốt 2026-11-23): trợ lý dẫn từng bước, nhớ quyết định theo dự án ở `data/old_quote_memory/`".
- [ ] **Step 4: Kiểm** — `grep -n "bao-gia-tu-bg-cu" AGENTS.md .agents/roles/agent_10_old_quote_carrier_role.md` có kết quả.
- [ ] **Step 5: Không commit** — `git status --short`.

---

### Task 6: Kiểm chứng trên HH3 (chạy thật + mô phỏng báo lần 2)

**Files:**
- Không sửa code. Dùng scratchpad cho file quyết định và RFQ mô phỏng.

- [ ] **Step 1: Chạy HH3 qua skill** với quyết định đã chốt trong phiên 2026-11-23: nhóm `kieu_nan`, `khac_hop`, `khac_ei` → `carry`; `nhieu_gia` → giá đề xuất; tuỳ chọn `--include-duct --duct-uplift 7 --mfd-model 1.05`; `--project-key HH3_MIK_CO_LOA`.
  Expected: Kiểm soát cuối ✅, mã thoát 0, **TỔNG TRƯỚC VAT = 16,435,221,594** (nếu lệch: liệt kê từng dòng khác giá so với `OLD_QUOTE_MATCH_REPORT.json` lần 2026-11-23 và giải thích — chỉ chấp nhận lệch do chọn giá ở nhóm `nhieu_gia`), không dùng `--force-new`; file `data/old_quote_memory/HH3_MIK_CO_LOA.json` được tạo.
- [ ] **Step 2: Mô phỏng báo lần 2** — chép RFQ vào scratchpad, chèn 2 dòng mới (`Van gió 1 chiều (NRD) 500x500`, `Louver + lưới chắn côn trùng 700x300`) và sửa KT dòng `Van gió 1 chiều (NRD) 400x200` → `450x200`. Chạy `--plan-json` cùng `--project-key HH3_MIK_CO_LOA`.
  Expected: mọi dòng cũ không đổi có `decided_by ∈ {"memory","auto"}`; dòng `decided_by=null` (phải hỏi) chỉ có thể là 1 trong 3 dòng mới/sửa; 3 dòng đó không dòng nào là `"memory"`.
- [ ] **Step 3: Kiểm git** — `git status --short` không có `output/`, `compare/`, `data/old_quote_memory/`; chạy lệnh kiểm tra trước push trong AGENTS.md → không in dòng nào.
- [ ] **Step 4: Báo User** kết quả 2 bước trên + danh sách file đã sửa (User tự commit).
