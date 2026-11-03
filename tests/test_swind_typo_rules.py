"""
Test bảng rule chuẩn hóa lỗi chính tả BOQ (data/master_data/typo_rules.json → src/typo_normalizer.py).

Mỗi rule TY-xx phải có nguồn gốc, lý do và ≥ 1 ví dụ; mọi `vi_du_dung` được chạy lại.
Chuẩn hóa chỉ tạo CHUỖI SO KHỚP — không ghi lại BOQ.
Chạy: ./venv/bin/python -m unittest discover -s tests -p "test_swind_*.py"
"""
import os
import re
import sys
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
sys.path.insert(0, SRC)

import typo_normalizer as tn  # noqa: E402


def _old_match_text(text_lower):
    """Thân `_match_text` cũ của swind_boq_parser (trước 2026-11-03) — mốc so sánh hành vi."""
    text_lower = re.sub(r'\b(miệng|cửa|mặt)\s+gio\b', r'\1 gió', text_lower)
    return text_lower.replace('_', ' ')


def _old_fix_typos(text):
    return re.sub(r"\bvan\s+mdf\b", "van mfd", text)


LEGACY_SAMPLES = [
    "Cửa gió hồi KT 250x250 + ODB", "Miệng gio kèm OBD 600x600", "AG_AAG-OBD-600x300", "Van MDF 400x400",
    "van mdf_kèm động cơ", "Cửa gio cấp", "mặt gio nan bầu dục", "Ống gió tôn mạ kẽm dày 0.75 _ cút 90",
    "Hộp gió hồi", "Côn thu 800x400-400x400", "Van chặn lửa FD EI60 Ø300", "Lưới chắn côn trùng IS 850x250",
    "cửa gió hồi 1 lớp nan_KT 300x300", "Cửa gió tháo lắp 2 khung", "VCD 200x200 tay gạt", "Louver nan Z WL 1000x500",
    "Tủ điện tăng áp hút khói", "van mdf", "Miệng gió khuếch tán 4 hướng 600x600", "Van 1 chiều NRD 500x500",
]


class TypoRuleTableTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.rules = tn.load_rules()

    def test_every_rule_has_source_and_examples(self):
        for r in self.rules["_all"]["quy_tac"]:
            with self.subTest(rule=r["id"]):
                self.assertTrue(r.get("nguon"), "thiếu nguon")
                self.assertTrue(r.get("ly_do"), "thiếu ly_do")
                self.assertTrue(r.get("vi_du_dung"), "thiếu vi_du_dung")

    def test_dictionary_examples(self):
        for ex in self.rules["TY-01"]["vi_du_dung"]:
            with self.subTest(ex=ex):
                self.assertEqual(tn.apply_dictionary(ex["vao"], ex["pham_vi"]), ex["ra"])

    def test_dictionary_examples_required(self):
        cases = [
            ("cửa hồi", "ten", "cửa hối"),
            ("cửa hồi", "full", "cửa hồi"),
            ("van mdf 400x400", "combo", "van mfd 400x400"),
            ("van mdf", "ten", "van mdf"),
            ("miệng gio kèm obd", "ten", "miệng gió kèm obd"),
            ("ag_aag-obd", "ten", "ag aag-obd"),
            ("ag_aag-obd", "title", "ag_aag-obd"),
            ("miệng gio_kèm", "ten", "miệng gio kèm"),
        ]
        for vao, scope, ra in cases:
            with self.subTest(vao=vao, scope=scope):
                self.assertEqual(tn.apply_dictionary(vao, scope), ra)

    def test_legacy_equivalence(self):
        for s in LEGACY_SAMPLES:
            low = s.lower()
            with self.subTest(s=s):
                # Lớp TY-01 giữ đúng hành vi các bản vá cũ (TY-02 khôi phục dấu chạy sau, được phép đổi chuỗi)
                self.assertEqual(tn.apply_dictionary(low, "ten"), _old_match_text(low.replace('ồ', 'ố')))
                self.assertEqual(tn.apply_dictionary(low, "full"), _old_match_text(low))
                self.assertEqual(tn.apply_dictionary(low, "title"), low.replace('ồ', 'ố'))
                self.assertEqual(tn.apply_dictionary(low, "combo"), _old_match_text(_old_fix_typos(low)))
                self.assertEqual(tn.apply_dictionary(low, "agent01"), low)
                self.assertEqual(tn.apply_dictionary(low, "van"), _old_fix_typos(low))

    def test_damper_fix_typos_delegates(self):
        import damper_classifier as dmc
        self.assertEqual(dmc.fix_typos("van mdf 400x400"), "van mfd 400x400")


class AccentRestoreTest(unittest.TestCase):
    """TY-02: khôi phục dấu theo từ vựng Swind (cụm ≥ 2 chữ)."""

    def test_rule_examples(self):
        r = tn.load_rules()["TY-02"]
        for ex in r["vi_du_dung"] + r["vi_du_sai"]:
            with self.subTest(ex=ex):
                self.assertEqual(tn.restore_accents(ex["vao"])[0], ex["ra"])

    def test_restore_unaccented_phrase(self):
        out, ev = tn.restore_accents("cua gio hoi 300x300")
        self.assertEqual(out, "cửa gió hồi 300x300")
        self.assertEqual([e["loai"] for e in ev], ["KHOI_PHUC_DAU"])

    def test_accented_word_never_changed(self):
        # Chữ ĐÃ có dấu không bị đổi dấu: 'ống luồn' (luồn dây điện) ≠ 'ống lượn' (TONG HOP HVAC R715, E2E 2026-11-03);
        # nhầm dấu kiểu 'cửa giò' xử lý bằng từ điển TY-01 đã duyệt.
        self.assertEqual(tn.restore_accents("ống luồn dây điện d50")[0], "ống luồn dây điện d50")
        self.assertEqual(tn.restore_accents("cửa giò cấp")[0], "cửa giò cấp")

    def test_partially_unaccented_phrase_restored(self):
        self.assertIn("cửa gió hồi", tn.restore_accents("cửa gio hoi 300x300")[0])

    def test_single_word_not_restored(self):
        self.assertEqual(tn.restore_accents("con 400x200")[0], "con 400x200")

    def test_unaccented_con_thu_restored(self):
        self.assertIn("côn thu", tn.restore_accents("con thu 800x400")[0])

    def test_two_accented_words_differ_not_restored(self):
        # 'dòng có' (đã có dấu, khác 2 chữ) không được biến thành 'động cơ'
        self.assertEqual(tn.restore_accents("dòng có kl")[0], "dòng có kl")

    def test_collision_uses_priority(self):
        # 'hop gio' trùng 'hộp gió' / 'hôp gió' trong từ vựng → bảng uu_tien chọn 'hộp gió'
        self.assertIn("hộp gió", tn.restore_accents("hop gio 600x600")[0])

    def test_real_collision_skipped(self):
        # 'công tắc' / 'công tác' khác nghĩa → không đoán
        self.assertEqual(tn.restore_accents("cong tac 1")[0], "cong tac 1")

    def test_protected_pair_tich_hop(self):
        out = tn.restore_accents("van tich hop dong co")[0]
        self.assertNotIn("hộp", out)
        self.assertEqual(tn.restore_accents("hợp gió")[0], "hợp gió")

    def test_accented_text_unchanged(self):
        out, ev = tn.restore_accents("cửa gió hồi kèm van điều chỉnh lưu lượng 600x300")
        self.assertEqual(out, "cửa gió hồi kèm van điều chỉnh lưu lượng 600x300")
        self.assertEqual(ev, [])

    def test_normalize_for_match_restores_in_scope(self):
        self.assertIn("cửa gió hồi", tn.normalize_for_match("cua gio hoi", "agent01"))
        self.assertEqual(tn.normalize_for_match("cua gio hoi", "van"), "cua gio hoi")

    def test_unaccented_row_classifies_like_accented(self):
        from agent_01_boq_extractor import Agent01_BOQExtractor
        from swind_utils import get_subtype_rules

        def spec(ten):
            item = {"category": "CUA_GIO", "raw_name": ten, "name": ten, "note_boq": "", "section": "",
                    "model": "", "w": 600, "h": 300, "d": 0, "spec_priority": "name"}
            return Agent01_BOQExtractor.resolve_item_spec(item, get_subtype_rules(), price_map={}, idx=1)
        a = spec("Cửa gió hồi kèm van điều chỉnh lưu lượng 600x300")
        b = spec("Cua gio hoi kem van dieu chinh luu luong 600x300")
        self.assertEqual(b.get("model_std"), a.get("model_std"))
        self.assertEqual(b.get("has_obd"), a.get("has_obd"))


class CodeTypoTest(unittest.TestCase):
    """TY-03 / TY-04: phát hiện & đoán mã viết tắt gõ sai theo ngữ cảnh."""

    def test_rule_examples(self):
        R = tn.load_rules()
        for ex in R["TY-03"]["vi_du_dung"] + R["TY-04"]["vi_du_dung"]:
            with self.subTest(ex=ex):
                ev = tn.detect_code_typos(ex["ten"], ex["ngu_canh"])
                self.assertEqual([(e["loai"], e["sua"]) for e in ev], [(ex["loai"], ex["sua"])])
        for ex in R["TY-03"]["vi_du_sai"]:
            with self.subTest(ex=ex):
                self.assertEqual(tn.detect_code_typos(ex["ten"], ex["ngu_canh"]), [])

    def test_odb_on_diffuser_row(self):
        ev = tn.detect_code_typos("Cửa gió hồi KT 250x250 + ODB",
                                  "Tủ điện tăng áp hút khói Cửa gió hồi KT 250x250 + ODB")
        self.assertEqual([(e["loai"], e["goc"], e["sua"]) for e in ev], [("DOAN", "odb", "obd")])

    def test_mdf_under_fire_motor_title(self):
        ev = tn.detect_code_typos("MDF 600x400", "Van chặn lửa động cơ MDF 600x400")
        self.assertEqual([(e["loai"], e["sua"]) for e in ev], [("DOAN", "mfd")])

    def test_no_context_asks(self):
        # Dòng không có dấu hiệu cửa gió / van → không đoán được, hỏi lại
        ev = tn.detect_code_typos("ODB 300x300", "ODB 300x300")
        self.assertEqual(len(ev), 1)
        self.assertEqual(ev[0]["loai"], "HOI_LAI")
        self.assertIsNone(ev[0]["sua"])
        self.assertEqual(ev[0]["ung_vien"], ["obd"])

    def test_fire_note_does_not_veto_single_candidate(self):
        # NRD có ghi chú chống cháy EI60 là hợp lệ (bọc KSH) — LUXQV R29 'Van gió một chiều RND ... chống cháy EI60'
        t = "Van gió một chiều NDR vuông KT: 1000x600mm, chống cháy EI60"
        self.assertEqual([(e["loai"], e["sua"]) for e in tn.detect_code_typos(t, t)], [("DOAN", "nrd")])

    def test_customer_codes_not_flagged(self):
        # Mã riêng của khách (quét input/ 2026-11-03): họ miệng gió xAG, SEG, van FSD — không phải lỗi gõ
        for t in ("Miệng gió tạo áp PAG 800x350 + OBD", "Miệng gió hút khói: SEG 800x400 + OBD",
                  "Miệng gió cấp FAG 800x400", "Van FSD 600x600 EI120 động cơ", "Cửa gió SL2 khe 1500"):
            with self.subTest(t=t):
                self.assertEqual(tn.detect_code_typos(t, t), [])

    def test_repeated_letter_typo(self):
        ev = tn.detect_code_typos("Cửa gió nan Z kèm LCCCT 600x400", "Cửa gió nan Z kèm LCCCT 600x400")
        self.assertEqual([(e["loai"], e["sua"]) for e in ev], [("DOAN", "lcct")])

    def test_ndr_transposition(self):
        ev = tn.detect_code_typos("Van NDR 400x400", "Van một chiều NDR 400x400")
        self.assertEqual([(e["loai"], e["sua"]) for e in ev], [("DOAN", "nrd")])

    def test_known_code_no_event(self):
        self.assertEqual(tn.detect_code_typos("Van MFD 500x500 + OBD", "Van MFD 500x500 + OBD"), [])

    def test_known_dictionary_typo_no_event(self):
        # 'van mdf' đã có trong TY-01 → không sinh sự kiện
        self.assertEqual(tn.detect_code_typos("Van MDF 400x400", "Van MDF 400x400"), [])

    def test_vietnamese_syllables_not_flagged(self):
        for t in ("Gia do thep sat ma kem 600x400", "mat bich", "Cua gio hoi kem van"):
            with self.subTest(t=t):
                self.assertEqual(tn.detect_code_typos(t, t), [])

    def test_english_words_not_flagged(self):
        t = "Supply air grille with OBD, fan box"
        self.assertEqual(tn.detect_code_typos(t, t), [])

    def test_guess_applied_to_match_text(self):
        ev = tn.detect_code_typos("Cửa gió hồi KT 250x250 + ODB", "Cửa gió hồi KT 250x250 + ODB")
        self.assertIn("+ obd", tn.normalize_for_match("cửa gió hồi kt 250x250 + odb", "agent01", ev))
        from agent_01_boq_extractor import Agent01_BOQExtractor
        from swind_utils import get_subtype_rules
        t = "Cửa gió hồi KT 250x250 + ODB"
        item = {"category": "CUA_GIO", "raw_name": t, "name": t, "note_boq": "", "section": "", "model": "",
                "w": 250, "h": 250, "d": 0, "spec_priority": "name", "typo_events": ev}
        spec = Agent01_BOQExtractor.resolve_item_spec(item, get_subtype_rules(), price_map={}, idx=1)
        self.assertTrue(spec.get("has_obd"))
        self.assertEqual(spec.get("model_std"), "SDG+O")

    def test_parser_tags_typo_events(self):
        import tempfile
        import openpyxl
        from swind_boq_parser import SwindBOQParser
        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "BOQ"
        ws.append(["STT", "Tên vật tư", "Đơn vị", "Khối lượng", "Ghi chú"])
        ws.append([1, "Cửa gió hồi KT 250x250 + ODB", "cái", 2, ""])
        ws.append([2, "Cửa gió cấp 300x300", "cái", 3, ""])
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "boq.xlsx")
            wb.save(path)
            items = SwindBOQParser(path).parse_sheet("BOQ")
        by_row = {it["source_row"]: it for it in items}
        self.assertEqual([e["loai"] for e in by_row[2].get("typo_events") or [] if e["loai"] == "DOAN"], ["DOAN"])
        self.assertFalse([e for e in by_row[3].get("typo_events") or [] if e["loai"] in ("DOAN", "HOI_LAI")])


class ReportingTest(unittest.TestCase):
    """Task 4: chữ đánh dấu Sheet BG + dòng Kiểm soát cuối."""
    DOAN = {"loai": "DOAN", "goc": "odb", "sua": "obd", "ung_vien": ["obd"], "rule": "TY-04"}
    HOI = {"loai": "HOI_LAI", "goc": "fmd", "sua": None, "ung_vien": ["fd", "md", "mfd"], "rule": "TY-04"}
    KPD = {"loai": "KHOI_PHUC_DAU", "goc": "cua gio", "sua": "cửa gió", "rule": "TY-02"}

    def test_bg_flag_text(self):
        self.assertEqual(tn.bg_flag([self.DOAN]), "⚠️ ĐÃ HIỂU: ODB = OBD — xin xác nhận")
        self.assertEqual(tn.bg_flag([self.HOI]), "⚠️ CHƯA RÕ: FMD (có thể: FD / MD / MFD)")
        self.assertIsNone(tn.bg_flag([self.KPD]))
        self.assertIsNone(tn.bg_flag(None))
        self.assertEqual(tn.bg_flag([self.DOAN, self.KPD, self.HOI]),
                         "⚠️ ĐÃ HIỂU: ODB = OBD — xin xác nhận; ⚠️ CHƯA RÕ: FMD (có thể: FD / MD / MFD)")

    def test_gate_lines(self):
        items = [
            {"source_row": 5, "raw_name": "Cửa gió + ODB", "qty": 2, "typo_events": [self.DOAN]},
            {"source_row": 6, "raw_name": "Van FMD", "qty": 1, "typo_events": [self.HOI]},
            {"source_row": 7, "raw_name": "Cửa gió + ODB", "qty": 0, "typo_events": [self.DOAN]},
            {"source_row": 8, "raw_name": "cua gio", "qty": 1, "typo_events": [self.KPD]},
        ]
        lines = tn.gate_lines(items)
        self.assertEqual(len(lines), 2)
        self.assertTrue(lines[0].startswith("[ĐÃ ĐOÁN — XÁC NHẬN] 1 dòng"))
        self.assertIn("R5 'Cửa gió + ODB': ODB→OBD", lines[0])
        self.assertNotIn("R7", lines[0])
        self.assertTrue(lines[1].startswith("[HỎI LẠI USER] 1 dòng"))
        self.assertIn("R6 'Van FMD': FMD? (FD / MD / MFD)", lines[1])
        self.assertEqual(tn.gate_lines([items[3]]), [])

    def test_bg_sheet_marks_guessed_row(self):
        import shutil
        import subprocess
        import tempfile
        import openpyxl
        learning = [os.path.join(ROOT, "data", "master_data", f) for f in
                    ("format_learning_db.json", "boq_keyword_learning.json", "pending_approval_queue.json",
                     "swind_experience_db.json", "typo_rules.json")]
        with tempfile.TemporaryDirectory() as d:
            backup = {}
            for f in learning:
                if os.path.exists(f):
                    backup[f] = os.path.join(d, os.path.basename(f) + ".bak")
                    shutil.copy2(f, backup[f])
            try:
                wb = openpyxl.Workbook()
                ws = wb.active
                ws.title = "BOQ"
                ws.append(["STT", "Tên vật tư", "Đơn vị", "Khối lượng", "Ghi chú"])
                ws.append([1, "Cửa gió hồi KT 250x250 + ODB", "cái", 2, ""])
                ws.append([2, "Cửa gió cấp 300x300", "cái", 3, ""])
                boq = os.path.join(d, "TYPO_TEST_BOQ.xlsx")
                wb.save(boq)
                out = os.path.join(d, "out")
                env = dict(os.environ, SWIND_OUTPUT_DIR=out)
                res = subprocess.run([os.path.join(ROOT, "venv", "bin", "python"), os.path.join(SRC, "swind_master_runner.py"),
                                      boq, "--non-interactive", "--auto-accept"], cwd=ROOT, env=env,
                                     capture_output=True, text=True, timeout=300)
                self.assertIn("[ĐÃ ĐOÁN — XÁC NHẬN]", res.stdout)
                quotes = [os.path.join(r, f) for r, _, fs in os.walk(out) for f in fs
                          if f == "TYPO_TEST_BOQ.xlsx" and "internal_estimation" not in r and "thanh_phan" not in r]
                self.assertTrue(quotes, res.stdout[-2000:])
                bg = openpyxl.load_workbook(quotes[0])["BG"]
                rows = {str(bg.cell(r, 2).value): r for r in range(1, bg.max_row + 1) if bg.cell(r, 2).value}
                r1, r2 = rows["Cửa gió hồi KT 250x250 + ODB"], rows["Cửa gió cấp 300x300"]
                self.assertTrue(str(bg.cell(r1, 16).value).endswith("⚠️ ĐÃ HIỂU: ODB = OBD — xin xác nhận"))
                self.assertEqual(bg.cell(r1, 2).fill.fgColor.rgb[-6:], "FFFF00")
                self.assertNotEqual((bg.cell(r2, 2).fill.fgColor.rgb or "")[-6:], "FFFF00")
            finally:
                for f, b in backup.items():
                    shutil.copy2(b, f)


class LearningTest(unittest.TestCase):
    """Task 5: lỗi mới được duyệt qua hàng chờ Agent 02 → từ điển TY-01 (bản sao trong thư mục tạm)."""

    def setUp(self):
        import shutil
        import tempfile
        import agent_02_boq_reviewer as a02
        self.a02 = a02
        self.tmp = tempfile.TemporaryDirectory()
        d = self.tmp.name
        self.rules = os.path.join(d, "typo_rules.json")
        shutil.copy2(tn.RULES_PATH, self.rules)
        self.queue = os.path.join(d, "pending_approval_queue.json")
        with open(self.queue, "w", encoding="utf-8") as f:
            f.write('{"pending_proposals": []}')
        self.learning = os.path.join(d, "boq_keyword_learning.json")
        with open(self.learning, "w", encoding="utf-8") as f:
            f.write("{}")
        self._orig = (tn.RULES_PATH, a02.QUEUE_PATH, a02.LEARNING_PATH)
        tn.RULES_PATH, a02.QUEUE_PATH, a02.LEARNING_PATH = self.rules, self.queue, self.learning

    def tearDown(self):
        tn.RULES_PATH, self.a02.QUEUE_PATH, self.a02.LEARNING_PATH = self._orig
        self.tmp.cleanup()

    def _queue(self):
        import json
        with open(self.queue, encoding="utf-8") as f:
            return json.load(f)["pending_proposals"]

    def test_add_dictionary_entry_idempotent(self):
        n0 = len(tn.load_rules()["TY-01"]["tu_dien"])
        self.assertTrue(tn.add_dictionary_entry("ODB", "OBD", "test"))
        self.assertFalse(tn.add_dictionary_entry("odb", "obd", "test"))
        entries = tn.load_rules()["TY-01"]["tu_dien"]
        self.assertEqual(len(entries), n0 + 1)
        self.assertEqual(entries[-1]["thay"], "obd")
        self.assertEqual(entries[-1]["pham_vi"], list(tn.ALL_SCOPES))

    def test_typo_proposal_dedup(self):
        self.a02.save_typo_proposal("odb", "obd", "Cổ bi", "Cửa gió hồi KT 250x250 + ODB")
        self.a02.save_typo_proposal("odb", "obd", "Cổ bi", "Cửa gió hồi KT 250x250 + ODB")
        q = [p for p in self._queue() if p.get("loai") == "TYPO"]
        self.assertEqual(len(q), 1)
        self.assertEqual((q[0]["raw_name"], q[0]["proposed_id"], q[0]["status"]), ("odb", "obd", "PENDING_APPROVAL"))

    def test_approve_typo_writes_rule_not_keywords(self):
        self.a02.save_typo_proposal("odb", "obd", "Cổ bi", "Cửa gió hồi + ODB")
        self.a02.approve_pending_keywords(approve_all=True)
        self.assertTrue(any(e["thay"] == "obd" for e in tn.load_rules()["TY-01"]["tu_dien"]))
        with open(self.learning, encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "{}")
        self.assertEqual([p["status"] for p in self._queue()], ["APPROVED"])

    def test_approved_typo_becomes_silent(self):
        tn.add_dictionary_entry("odb", "obd", "test")
        t = "Cửa gió hồi + ODB"
        self.assertEqual(tn.detect_code_typos(t, t), [])
        self.assertIn("obd", tn.normalize_for_match(t.lower(), "agent01"))

    def test_add_typo_cli(self):
        import subprocess
        env = dict(os.environ, SWIND_TYPO_RULES=self.rules)
        res = subprocess.run([os.path.join(ROOT, "venv", "bin", "python"), os.path.join(SRC, "agent_02_boq_reviewer.py"),
                              "--add-typo", "FMD=MFD"], cwd=ROOT, env=env, capture_output=True, text=True, timeout=120)
        self.assertEqual(res.returncode, 0, res.stdout + res.stderr)
        self.assertTrue(any(e["mau"] == r"\bfmd\b" for e in tn.load_rules(self.rules)["TY-01"]["tu_dien"]))


class ReviewFixTest(unittest.TestCase):
    """Lỗi do review cuối phát hiện (2026-11-03)."""

    def test_unaccented_ong_luon_not_duct(self):
        # 'ong luon' không dấu không được khôi phục thành 'ống lượn' (ống luồn dây điện ≠ ống gió cong)
        out = tn.restore_accents("ong luon day dien d20")[0]
        self.assertNotIn("lượn", out)
        self.assertTrue(out.startswith("ong luon "))

    def test_side_table_items_not_tagged_from_main_row(self):
        from swind_boq_parser import tag_typo_events
        ev = [{"loai": "DOAN", "goc": "odb", "sua": "obd", "ung_vien": ["obd"], "rule": "TY-04"}]
        items = [{"source_row": 3, "raw_name": "Cửa gió ODB"},
                 {"source_row": 3, "raw_name": "Van FD 400x400", "is_side_table": True}]
        tag_typo_events(items, {3: ev})
        self.assertEqual(items[0]["typo_events"], ev)
        self.assertNotIn("typo_events", items[1])

    def test_real_abbreviations_not_guessed(self):
        for t in ("Van MD động cơ 24 VDC 400x400", "Volume damper RND D250", "Fire damper RND D300",
                  "DM van vận chuyển"):
            with self.subTest(t=t):
                self.assertEqual(tn.detect_code_typos(t, t), [])

    def test_rejected_guess_is_honoured(self):
        import json
        import shutil
        import tempfile
        import builtins
        import agent_02_boq_reviewer as a02
        with tempfile.TemporaryDirectory() as d:
            rules = os.path.join(d, "typo_rules.json")
            shutil.copy2(tn.RULES_PATH, rules)
            queue = os.path.join(d, "q.json")
            learning = os.path.join(d, "l.json")
            open(queue, "w").write('{"pending_proposals": []}')
            open(learning, "w").write("{}")
            orig = (tn.RULES_PATH, a02.QUEUE_PATH, a02.LEARNING_PATH, builtins.input)
            tn.RULES_PATH, a02.QUEUE_PATH, a02.LEARNING_PATH = rules, queue, learning
            builtins.input = lambda *_: "R"
            try:
                a02.save_typo_proposal("odb", "obd", "test", "Cửa gió hồi + ODB")
                a02.approve_pending_keywords(approve_all=False, interactive=True)
                t = "Cửa gió hồi + ODB"
                self.assertEqual(tn.detect_code_typos(t, t), [])
                self.assertIn("odb", tn.load_rules()["TY-03"]["loai_tru"])
                self.assertEqual(json.load(open(queue))["pending_proposals"][0]["status"], "REJECTED")
            finally:
                tn.RULES_PATH, a02.QUEUE_PATH, a02.LEARNING_PATH, builtins.input = orig

    def test_unaccented_name_column_rules(self):
        from agent_01_boq_extractor import Agent01_BOQExtractor
        from swind_utils import get_subtype_rules

        def model(ten):
            item = {"category": "CUA_GIO", "raw_name": ten, "name": ten, "note_boq": "nan z", "section": "",
                    "model": "", "w": 600, "h": 300, "d": 0, "spec_priority": "name"}
            return Agent01_BOQExtractor.resolve_item_spec(item, get_subtype_rules(), price_map={}, idx=1).get("model_std")
        self.assertEqual(model("Cua gio nan thang 600x300"), model("Cửa gió nan thẳng 600x300"))


if __name__ == "__main__":
    unittest.main()
