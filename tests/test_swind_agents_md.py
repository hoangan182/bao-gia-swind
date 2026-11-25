"""Lưới an toàn khi rút gọn AGENTS.md (kế hoạch 2026-11-24-1): không mất mã rule / cờ CLI / link, giữ quy tắc bắt buộc hỏi lại."""
import os
import re
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DOC_FILES = [
    "AGENTS.md",
    ".agents/rules/04_QUY_TAC_NGHIEP_VU.md",
    ".agents/rules/05_CLI_VA_KIEM_THU.md",
    ".agents/rules/06_BAN_DO_AGENT.md",
]
FIXTURE = os.path.join(ROOT, "tests", "fixtures", "agents_md_rule_ids_2026-11-24.txt")
ABS_PREFIX = "file:///Users/hoangan/work/PCCC/swind/"


def read(rel):
    """File chưa tồn tại -> coi như rỗng."""
    try:
        with open(os.path.join(ROOT, rel), encoding="utf-8") as f:
            return f.read()
    except OSError:
        return ""


class AgentsMdTest(unittest.TestCase):
    def test_size_limit(self):
        self.assertLessEqual(os.path.getsize(os.path.join(ROOT, "AGENTS.md")), 8192)

    def test_no_rule_id_lost(self):
        with open(FIXTURE, encoding="utf-8") as f:
            ids = [x.strip() for x in f if x.strip()]
        text = "\n".join(read(p) for p in DOC_FILES)
        lost = [i for i in ids if not re.search(r"(?<![A-Za-z0-9-])" + re.escape(i) + r"(?![A-Za-z0-9])", text)]
        self.assertEqual(lost, [], f"Mất mã rule: {lost}")

    def test_cli_flags_documented(self):
        src = read("src/swind_master_runner.py")
        flags = sorted(set(re.findall(r"add_argument\(\s*[\"'](--[a-z0-9-]+)", src)))
        self.assertTrue(flags)
        text = read("AGENTS.md") + "\n" + read(".agents/rules/05_CLI_VA_KIEM_THU.md")
        missing = [f for f in flags if not re.search(re.escape(f) + r"(?![a-z0-9-])", text)]
        self.assertEqual(missing, [], f"Cờ CLI chưa được ghi tài liệu: {missing}")

    def test_links_resolve(self):
        text = read("AGENTS.md")
        bad = []
        for target in re.findall(r"\]\(([^)\s]+)\)", text):
            if re.match(r"https?://", target):
                continue
            t = target.split("#", 1)[0]
            if not t:
                continue
            if t.startswith(ABS_PREFIX):
                rel = t[len(ABS_PREFIX):]
            elif t.startswith("file://"):
                continue
            else:
                rel = t
            if not os.path.exists(os.path.join(ROOT, rel)):
                bad.append(target)
        self.assertEqual(bad, [], f"Link hỏng: {bad}")

    def test_ask_rules_kept(self):
        text = read("AGENTS.md")
        must = ["1c", "2b", "2c", "OG-21", "OG-22", "PV-13", "TY-05", "TITLE_ROW_ASK",
                "VG-09", "--title-wins", "--approve-pending"]
        missing = [m for m in must if m not in text]
        self.assertEqual(missing, [], f"AGENTS.md thiếu: {missing}")


if __name__ == "__main__":
    unittest.main()
