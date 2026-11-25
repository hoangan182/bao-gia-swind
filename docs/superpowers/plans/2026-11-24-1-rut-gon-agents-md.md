# Việc 1 — Rút gọn AGENTS.md — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** AGENTS.md nạp mỗi phiên giảm từ 57 KB xuống ≤ 8 KB mà không mất rule nghiệp vụ, cờ CLI hay lệnh kiểm thử nào.

**Architecture:** AGENTS.md chỉ giữ thứ AI cần ở *mọi* phiên: lệnh chạy, danh sách tình huống bắt buộc hỏi lại User (mỗi dòng ≤ 1 câu, kèm mã rule), quy tắc git, lệnh kiểm thử, bảng chỉ đường. Nội dung chi tiết chuyển nguyên văn sang 3 file trong `.agents/rules/` (đọc khi cần). Một unit test chống mất nội dung: mọi mã rule và mọi cờ CLI phải còn xuất hiện ở AGENTS.md hoặc file đích.

**Tech Stack:** Markdown, Python unittest.

**Spec:** `docs/superpowers/plans/2026-11-24-00-tong-quan-4-viec.md` (mục Việc 1)

## Global Constraints

- AGENTS.md ≤ 8192 byte (UTF-8).
- Chuyển **nguyên văn** (cắt/dán), không viết lại nội dung rule khi chuyển; chỉ AGENTS.md mới được viết gọn.
- Không đổi code, không đổi JSON.
- AI không commit.

## Review Focus

1. Một rule "AI bắt buộc hỏi lại" bị chuyển đi mà không để lại dòng nhắc trong AGENTS.md → AI phiên sau không hỏi. Test `test_ask_rules_kept` kiểm các mã: `1c`, `2b`, `2c`, `3`, `4c`, `OG-21`, `OG-22`, `PV-13`, `TY-05`, `TITLE_ROW_ASK`.
2. Link tương đối trong AGENTS.md trỏ file không tồn tại → test `test_links_resolve`.
3. Cờ CLI mới thêm sau này không có trong tài liệu → test `test_cli_flags_documented` đọc cờ trực tiếp từ `swind_master_runner.py`.
4. Mã rule bị mất khi chuyển → test `test_no_rule_id_lost` so với ảnh chụp mã rule trước khi sửa.
5. Memory của User trỏ tới mục AGENTS.md cũ → không xử lý trong kế hoạch này (memory chỉ ghi tên rule, không ghi số mục).

---

### Task 1: Test chống mất nội dung + ảnh chụp mã rule hiện tại

**Files:**
- Create: `tests/test_swind_agents_md.py`
- Create: `tests/fixtures/agents_md_rule_ids_2026-11-24.txt` (một mã một dòng, sinh từ AGENTS.md hiện tại)

**Interfaces:**
- Produces: `DOC_FILES = ["AGENTS.md", ".agents/rules/04_QUY_TAC_NGHIEP_VU.md", ".agents/rules/05_CLI_VA_KIEM_THU.md", ".agents/rules/06_BAN_DO_AGENT.md"]` — các task sau thêm nội dung vào đúng 3 file này.

- [ ] **Step 1: Sinh ảnh chụp mã rule**

```bash
grep -oE '\b(CG|VG|OG|PV|TY|TR|CG-KT)-[0-9]+[A-Z]?\b' AGENTS.md | sort -u > tests/fixtures/agents_md_rule_ids_2026-11-24.txt
wc -l tests/fixtures/agents_md_rule_ids_2026-11-24.txt
```
Expected: khoảng 40–60 dòng.

- [ ] **Step 2: Viết test**

```python
class AgentsMdTest(unittest.TestCase):
    def test_size_limit(self):
        self.assertLessEqual(os.path.getsize(os.path.join(ROOT, "AGENTS.md")), 8192)
    def test_no_rule_id_lost(self):   # mọi mã trong fixture xuất hiện trong ít nhất 1 file của DOC_FILES
    def test_cli_flags_documented(self):  # mọi '--xxx' trong add_argument của src/swind_master_runner.py có trong AGENTS.md hoặc 05_CLI_VA_KIEM_THU.md
    def test_links_resolve(self):     # mọi link markdown tương đối / file:///Users/hoangan/work/PCCC/swind/... trong AGENTS.md tồn tại
    def test_ask_rules_kept(self):    # AGENTS.md chứa từng chuỗi: "1c", "2b", "2c", "OG-21", "OG-22", "PV-13", "TY-05", "TITLE_ROW_ASK", "VG-09", "--title-wins", "--approve-pending"
```
Đọc cờ bằng regex `add_argument\(\s*["'](--[a-z0-9-]+)` trên `src/swind_master_runner.py`. File chưa tồn tại → coi như rỗng (test fail đúng chỗ, không crash).

- [ ] **Step 3: Chạy test**

Run: `./venv/bin/python -m unittest tests/test_swind_agents_md.py -v`
Expected: `test_size_limit` FAIL (57406 > 8192); `test_no_rule_id_lost`, `test_cli_flags_documented` PASS (AGENTS.md còn nguyên). Nếu `test_cli_flags_documented` FAIL ngay bây giờ: ghi lại cờ thiếu, task 2 bổ sung.

---

### Task 2: Tách nội dung chi tiết sang 3 file `.agents/rules/`

**Files:**
- Create: `.agents/rules/04_QUY_TAC_NGHIEP_VU.md` — nguyên văn khối "QUY TẮC QUÉT TOÀN BỘ BOQ" (mục 1 → 6) và "CỔNG KIỂM SOÁT CUỐI", "THƯ MỤC ĐẦU RA", "XUẤT BÁO CÁO", giữ số mục cũ (1a, 1b, 4a-0b…) để tra ngược.
- Create: `.agents/rules/05_CLI_VA_KIEM_THU.md` — nguyên văn "Bảng tham số CLI", "LUỒNG RẼ Agent 10", toàn bộ mục "QUY TẮC TỐC ĐỘ KHI KIỂM TRA / SỬA / THÊM CÔNG THỨC" (inspector, E2E, pattern lab, hằng số giá, từ khóa tự học, quy trình sửa rule).
- Create: `.agents/rules/06_BAN_DO_AGENT.md` — nguyên văn mục "1. PHÂN TÁCH 2 QUY TRÌNH & DANH SÁCH AGENT" (2 bảng).
- Modify: `.agents/rules/00_FAST_QUOTATION_EXECUTION.md` — đọc so với AGENTS.md mới; phần trùng lặp thay bằng 1 dòng trỏ về AGENTS.md.

- [ ] **Step 1: Cắt/dán nguyên văn 3 khối vào 3 file mới**, mỗi file mở đầu bằng 1 dòng: `> Chuyển nguyên văn từ AGENTS.md ngày 2026-11-24. AGENTS.md giữ bản tóm tắt.`
- [ ] **Step 2: Chạy test** — `test_no_rule_id_lost`, `test_cli_flags_documented` vẫn PASS (AGENTS.md chưa xoá gì).

---

### Task 3: Viết lại AGENTS.md bản gọn

**Files:**
- Modify: `AGENTS.md` (thay toàn bộ)
- Modify: `docs/AGENTS.md` (bản cũ 10 KB) → thay bằng 1 dòng trỏ về `../AGENTS.md`

Bố cục cố định (thứ tự, mỗi phần tối đa):
1. **Chạy báo giá** (≤ 15 dòng): lệnh runner `--non-interactive --auto-accept`, không đọc code trước khi chạy, không viết script phụ đọc kết quả, chỉ báo File Báo Giá Cuối Cùng + Bảng Tổng Hợp, BOQ `.xls` phải chuyển xlsx.
2. **Mặc định đã chốt, không hỏi** (≤ 8 dòng): không báo ống gió / canvas / ventcap / ống mềm trừ cờ; động cơ Belimo 1.02; cột/dòng ẩn bỏ qua; FD không EI → FD thường; cửa không ghi kiểu → SDG; hộp chỉ cộng khi `--include-box`.
3. **Bắt buộc hỏi lại User khi console in** (≤ 14 dòng, mỗi dòng: dấu hiệu console → việc AI làm → lệnh duyệt): `⛔ BÁO GIÁ CHƯA HOÀN CHỈNH`; `[KIỂM CHỨNG ĐỌC BOQ]` (2b, PV-13); Ghi chú/Spec khác Cột Tên (3, `--spec-priority`); `[ĐÃ ĐOÁN — XÁC NHẬN]` / `CHƯA RÕ` (2c, TY-04/TY-05, `--approve-pending`, `--add-typo`); `TITLE_ROW_ASK` / Title không rõ (1c, `--title-wins`); ống kèm sản phẩm Swind (OG-22); hộp gió Ghi chú khác Tên (OG-21); FD vừa EI vừa "thường" (VG-09); `[THÔNG BÁO USER]` thiếu kích thước (PV-05, `--override`); `[CẢNH BÁO SÓT DÒNG]`.
4. **Git** (≤ 6 dòng): được / không được commit, lệnh kiểm trước khi push, AI không commit.
5. **Sửa rule / công thức** (≤ 10 dòng): `--locate`, `03_FORMULA_INDEX.md`, sửa trong JSON không thêm if/elif, `pattern_lab --check` + E2E canh gác, `git log -S` trước khi sửa rule.
6. **Đọc thêm khi cần** (bảng 4 dòng): 04 nghiệp vụ, 05 CLI & kiểm thử, 06 bản đồ agent, `03_FORMULA_INDEX.md`.

- [ ] **Step 1: Viết AGENTS.md theo bố cục trên**
- [ ] **Step 2: Chạy test**

Run: `./venv/bin/python -m unittest tests/test_swind_agents_md.py -v`
Expected: 5 test PASS. `wc -c AGENTS.md` ≤ 8192.

- [ ] **Step 3: Thử thực tế** — mở phiên Claude Code mới, hỏi "chạy báo giá file input/<1 file nhỏ>" và "FD không ghi EI báo gì?". Đạt khi AI chạy đúng lệnh không đọc code, và trả lời đúng FD thường (hoặc tự mở 04 để tra).
- [ ] **Step 4: Báo User danh sách file để commit**: `AGENTS.md`, `docs/AGENTS.md`, `.agents/rules/04_*.md`, `05_*.md`, `06_*.md`, `00_FAST_QUOTATION_EXECUTION.md`, `tests/test_swind_agents_md.py`, `tests/fixtures/agents_md_rule_ids_2026-11-24.txt`.

**Duy trì về sau:** rule mới ghi chi tiết vào `04_QUY_TAC_NGHIEP_VU.md` (và `nguon`/`ly_do` trong JSON); AGENTS.md chỉ thêm 1 dòng khi rule đó *bắt buộc hỏi lại User*. `test_size_limit` chặn AGENTS.md phình lại.
