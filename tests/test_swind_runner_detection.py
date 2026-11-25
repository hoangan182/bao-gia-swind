"""
Ghim hành vi NHẬN DIỆN còn trong swind_master_runner (Task B — dọn sạch sau Việc 4, 2026-11-25).

Các test này viết TRƯỚC khi chuyển từ khóa sang JSON (scope_rules / diffuser_rules / damper_rules / duct_rules) và phải
qua trên code chưa sửa — sau khi chuyển vẫn phải qua y hệt:
- Bộ dò xung đột Tên – Ghi chú (`print_quotation_summary_table`): dòng nào bị in `⚠️ [PHÁT HIỆN GHI CHÚ / SPEC KHÁC BIỆT ...]`.
  Line-diff giá KHÔNG bắt được mục này (không đổi giá) → ghim từng nhánh ở đây.
- `fire_duct_section_rows(..., straight_only=True)` (cờ --fire-duct-only --duct-straight-only): E2E không chạy cờ này.
Chạy: ./venv/bin/python -m unittest discover -s tests -p "test_swind_*.py"
"""
import contextlib
import io
import os
import sys
import unittest

import openpyxl

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, SRC)

import swind_master_runner as runner  # noqa: E402

ASK_HEAD = "PHÁT HIỆN GHI CHÚ / SPEC KHÁC BIỆT CỘT TÊN"


def _item(cat, sub, rn, nb, note_prio=False, section="", override=0, brand=None):
    sp = {"subtype": sub, "model_std": "M", "a1": 600, "a2": 300}
    if brand:
        sp["motor_brand"] = brand
    return {"category": cat, "raw_name": rn, "note_boq": nb, "resolved_spec": sp, "qty": 2, "calc_sell_unit": 1000,
            "override_price": override, "spec_priority": "note" if note_prio else "name", "source_sheet": "S",
            "source_row": 7, "section": section}


def _run(items):
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        runner.print_quotation_summary_table(["S"], items)
    out = buf.getvalue()
    lines = out.splitlines()
    ask = []
    if ASK_HEAD in out:
        i = next(k for k, ln in enumerate(lines) if ASK_HEAD in ln)
        ask = [ln.strip()[2:] for ln in lines[i + 1:] if ln.startswith("   - ")]
    return out, ask


# (nhóm, subtype, Tên, Ghi chú, ưu tiên ghi chú, nhãn cảnh báo mong đợi hoặc None)
CASES = [
    # --- Cửa gió: nhánh 1 sọt trứng
    ("CUA_GIO", "", "Cửa gió nan thẳng 600x300", "Cửa nan sọt trứng", False, "[Cửa gió - Tên vs Ghi chú]"),
    ("CUA_GIO", "", "Cửa gió 600x300", "eggcrate", False, "[Cửa gió - Tên vs Ghi chú]"),
    ("CUA_GIO", "", "Cửa gió sọt trứng 600x600", "nan sọt trứng", False, None),
    ("CUA_GIO", "", "Cửa ECG 600x600", "eggcrate", False, None),
    ("CUA_GIO", "", "Miệng hút gió EAG+OBD kích thước: 200x200", "Cửa nan sọt trứng kèm van OBD", False, "[Cửa gió - Tên vs Ghi chú]"),
    # nhánh 1 không khớp (Tên có sọt trứng) → rơi xuống nhánh 2 (Ghi chú louver + Tên sọt trứng)
    ("CUA_GIO", "", "Cửa sọt trứng 600x600", "sọt trứng louver", False, "[Cửa gió - Tên vs Ghi chú]"),
    # --- nhánh 2 nan Z / louver
    ("CUA_GIO", "", "Miệng gió EAG 300x300", "Louver nan Z", False, "[Cửa gió - Tên vs Ghi chú]"),
    ("CUA_GIO", "", "Miệng gió SAG 300x300", "nan z", False, "[Cửa gió - Tên vs Ghi chú]"),
    ("CUA_GIO", "", "Cửa gió nan thẳng 600x300", "Nan Z", False, "[Cửa gió - Tên vs Ghi chú]"),
    ("CUA_GIO", "", "Cửa gió 600x300", "Nan Z", False, None),
    ("CUA_GIO", "", "Cửa gió message 600x300", "nan z", False, "[Cửa gió - Tên vs Ghi chú]"),  # 'sag' chuỗi con (giữ cố ý)
    # --- nhánh 3 bầu dục / nan thẳng
    ("CUA_GIO", "", "Cửa gió khe slot 1000x150", "nan thẳng bầu dục", False, "[Cửa gió - Tên vs Ghi chú]"),
    ("CUA_GIO", "", "Cửa gió sọt trưng 600x600", "nan thẳng", False, "[Cửa gió - Tên vs Ghi chú]"),
    ("CUA_GIO", "", "Cửa gió kiểu lưới 600x600", "bầu dục", False, "[Cửa gió - Tên vs Ghi chú]"),
    ("CUA_GIO", "", "Cửa gió slot nan thẳng 1000x150", "bầu dục", False, None),
    ("CUA_GIO", "", "Cửa gió 600x600", "bầu dục", False, None),
    # --- ưu tiên Ghi chú / Ghi chú trống → không hỏi
    ("CUA_GIO", "", "Cửa gió nan thẳng 600x300", "Cửa nan sọt trứng", True, None),
    ("CUA_GIO", "", "Cửa gió nan thẳng 600x300", "", False, None),
    # --- Van cơ NRD / PRD / MPRD / VCD
    ("VAN_GIO", "NRD", "Van 1 chiều NRD 400x400", "van chặn lửa", False, "[Van gió - Tên vs Ghi chú]"),
    ("VAN_GIO", "VCD", "Van VCD 400x400", "bọc tấm MgO", False, "[Van gió - Tên vs Ghi chú]"),
    ("VAN_GIO", "PRD", "Van xả áp PRD 400x400", "MFD", False, "[Van gió - Tên vs Ghi chú]"),
    ("VAN_GIO", "MPRD", "Van xả áp MPRD 400x400", "van ngăn cháy", False, "[Van gió - Tên vs Ghi chú]"),
    ("VAN_GIO", "VCD", "Van VCD 400x400", "SMD", False, "[Van gió - Tên vs Ghi chú]"),
    ("VAN_GIO", "VCD", "Van VCD 400x400", "tấm chống cháy MgO", False, "[Van gió - Tên vs Ghi chú]"),
    ("VAN_GIO", "VCD", "Van VCD 400x400", "bọc chống cháy", False, "[Van gió - Tên vs Ghi chú]"),
    ("VAN_GIO", "VCD", "Van VCD 400x400", "Van EI60", False, None),
    ("VAN_GIO", "PRD", "Van xả áp PRD 400x400", "MFD", True, None),
    ("VAN_GIO", "FD", "Van FD 400x400", "van chặn lửa MFD", False, None),
    # --- Van MFD Ghi chú 'Van FD' (KHÔNG xét ưu tiên ghi chú)
    ("VAN_GIO", "MFD", "Van MFD 400x400", "Van FD", False, "[Van gió - Tên vs Ghi chú]"),
    ("VAN_GIO", "MFD", "Van MFD 400x400", "Van FD", True, "[Van gió - Tên vs Ghi chú]"),
    ("VAN_GIO", "MSFD", "Van MSFD 400x400", "van fd EI60", False, "[Van gió - Tên vs Ghi chú]"),
    ("VAN_GIO", "MFD", "Van MFD 400x400", "Van FD kèm động cơ", False, None),
    ("VAN_GIO", "MFD", "Van MFD 400x400", "Van FD on/off", False, None),
    ("VAN_GIO", "MFD", "Van MFD 400x400", "Van FD loại MFD", False, None),
    ("VAN_GIO", "MD", "Van MD 400x400", "Van FD", False, None),
    # --- EI Tên vs Ghi chú (van MFD/MD)
    ("VAN_GIO", "MFD", "Van MFD EI60 400x400", "EI90", False, "[Van PCCC - EI Tên vs Spec]"),
    ("VAN_GIO", "MFD", "Van MFD EI60 400x400", "EI 60", False, None),
    # --- loại khác: không xét
    ("ONG_GIO", "", "Ống gió 400x400", "nan z louver", False, None),
]


class ConflictDetectorPinnedTest(unittest.TestCase):
    def test_cases(self):
        for cat, sub, rn, nb, prio, label in CASES:
            with self.subTest(ten=rn, ghi_chu=nb, sub=sub, uu_tien_ghi_chu=prio):
                _, ask = _run([_item(cat, sub, rn, nb, prio)])
                if label is None:
                    self.assertEqual(ask, [])
                else:
                    self.assertEqual(len(ask), 1)
                    self.assertTrue(ask[0].startswith(label), ask[0])

    def test_partner_price_rows_not_checked(self):
        _, ask = _run([_item("CUA_GIO", "", "Cửa gió nan thẳng 600x300", "Cửa nan sọt trứng", override=5000)])
        self.assertEqual(ask, [])

    def test_exact_text_diffuser(self):
        _, ask = _run([_item("CUA_GIO", "", "Cửa gió nan thẳng 600x300", "Cửa nan sọt trứng")])
        self.assertEqual(ask, ["[Cửa gió - Tên vs Ghi chú] BOQ R7 (600x300, SL=2): Tên='Cửa gió nan thẳng 600x300' "
                               "vs Ghi chú='Cửa nan sọt trứng' -> Đang áp Model='M' (ĐG=1,000đ)"])

    def test_exact_text_damper_with_section(self):
        _, ask = _run([_item("VAN_GIO", "NRD", "400x400", "van chặn lửa", section="Van 1 chiều NRD")])
        self.assertEqual(ask, ["[Van gió - Tên vs Ghi chú] BOQ R7 (600x300, SL=2): Tên='Van 1 chiều NRD -> 400x400' "
                               "vs Ghi chú='van chặn lửa' -> Đang áp Model='M' (ĐG=1,000đ)"])

    def test_motor_brand_is_info_not_ask(self):
        out, ask = _run([_item("VAN_GIO", "MFD", "Van MFD 400x400", "động cơ KLB")])
        self.assertEqual(ask, [])
        self.assertIn("ℹ️  [Hãng ĐC] 1 van MFD/MD", out)
        out, ask = _run([_item("VAN_GIO", "MFD", "Van MFD 400x400", "động cơ KLB", brand="KLB")])
        self.assertNotIn("[Hãng ĐC]", out)


def _ws(rows):
    wb = openpyxl.Workbook()
    ws = wb.active
    for r, txt in enumerate(rows, 1):
        if txt is not None:
            ws.cell(r, 2, txt)
    return ws


class FireDuctStraightOnlyPinnedTest(unittest.TestCase):
    ROWS = [
        "+ Đường ống gió chống cháy EI60",   # 1 tiêu đề nhóm
        "Ống gió thẳng tôn dày 1.0mm:",     # 2 Title con
        "400x300",                          # 3 chỉ KT, Title con ống thẳng → giữ
        "Cút 90 độ 400x300",                # 4 phụ kiện → bỏ
        "Phụ kiện:",                        # 5 Title con
        "500x300",                          # 6 dưới Title phụ kiện → bỏ
        "Ống gió 600x400 kèm co 45",        # 7 'co ' → bỏ
        "Ống gió tên A 300x300",            # 8 'tê' chuỗi con của 'tên' → bỏ (giữ nguyên hành vi cũ)
        "Ống gió 300x300",                  # 9 → giữ
        "Chạc ba 300x300",                  # 10 → bỏ
        "Hộp gió 300x300",                  # 11 → bỏ
        "Măng xông D200",                   # 12 → bỏ
        "+ Thiết bị quạt",                  # 13 hết nhóm
        "Ống gió 300x300",                  # 14 ngoài nhóm chống cháy
    ]

    def test_straight_only(self):
        self.assertEqual(runner.fire_duct_section_rows(_ws(self.ROWS), straight_only=True), {3, 9})

    def test_all_fire_rows(self):
        self.assertEqual(runner.fire_duct_section_rows(_ws(self.ROWS), straight_only=False), {3, 4, 6, 7, 8, 9, 10, 11, 12})


if __name__ == "__main__":
    unittest.main()
