"""
Test module giá dùng chung src/swind_pricing.py (đợt gom giá 2026-11-03, spec docs/superpowers/specs/2026-11-03-swind-pricing-consolidation-design.md).
Chạy: ./venv/bin/python -m unittest tests.test_swind_pricing -v
"""
import os
import sys
import unittest

SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src")
sys.path.insert(0, SRC)

from swind_pricing import excel_round, mfg_markup, mat_price, select_actuator, ACTUATOR_IDS, calc_obd, mesh_price, filter_g4_price, financial_rates, sell_price  # noqa: E402


class ExcelRound(unittest.TestCase):
    def test_excel_round_matches_agent04(self):
        for v, n, exp in [(2.675, 2, 2.68), (1234.5, 0, 1235), (-2.5, 0, -3), (12500, -3, 13000), (1.005, 2, 1.01), (None, 0, 0)]:
            self.assertEqual(excel_round(v, n), exp, (v, n))

    def test_int_when_ndigits_not_positive(self):
        self.assertIsInstance(excel_round(1234.4, 0), int)
        self.assertIsInstance(excel_round(12345, -3), int)
        self.assertIsInstance(excel_round(1.234, 2), float)


class Defaults(unittest.TestCase):
    def test_mfg_markup(self):
        self.assertAlmostEqual(mfg_markup("damper_rules"), 1.593)
        self.assertAlmostEqual(mfg_markup("diffuser_rules"), 1.593)
        self.assertAlmostEqual(mfg_markup("ductwork_rules"), 1.593)

    def test_mat_price_known_and_unknown(self):
        self.assertGreater(mat_price("MAT-ALU-KHUNG-OBD"), 0)
        self.assertEqual(mat_price("MAT-KHONG-TON-TAI"), 0.0)


class Actuator(unittest.TestCase):
    def test_select_actuator_boundaries(self):
        cases = [
            ("MD", "BELIMO", 999, 999, "MAT-ACTUATOR-BELIMO-5NM", "5Nm"),
            ("MD", "BELIMO", 1000, 500, "MAT-ACTUATOR-BELIMO-10NM", "10Nm"),
            ("MD", "BELIMO", 1500, 1200, "MAT-ACTUATOR-BELIMO-10NM", "10Nm"),   # 1.8 m² đúng ngưỡng
            ("MD", "BELIMO", 1500, 1201, "MAT-ACTUATOR-BELIMO-20NM", "20Nm"),
            ("MD", "HONEYWELL", 1000, 800, "MAT-ACTUATOR-HONEYWELL-5NM", "5Nm"),  # 0.8 m² đúng ngưỡng
            ("MD", "HONEYWELL", 1000, 801, "MAT-ACTUATOR-HONEYWELL-10NM", "10Nm"),
            ("MD", "HONEYWELL", 1500, 1201, "MAT-ACTUATOR-HONEYWELL-20NM", "20Nm"),
            ("MD", "KLB", 400, 400, "MAT-ACTUATOR-SWIND-VIWECO", "10Nm"),
            ("MD", "KLB", 2000, 1500, "MAT-ACTUATOR-SWIND-VIWECO", "10Nm"),
            ("MPRD", "BELIMO", 999, 999, "MAT-ACTUATOR-BELIMO-MPRD-5NM", "5Nm"),
            ("MPRD", "BELIMO", 1000, 500, "MAT-ACTUATOR-BELIMO-MPRD", "10Nm"),
            ("MPRD", "BELIMO", 1500, 1201, "MAT-ACTUATOR-BELIMO-MPRD-20NM", "20Nm"),
            # agent_05 xét hãng KLB / Honeywell trước MPRD -> giữ nguyên
            ("MPRD", "KLB", 400, 400, "MAT-ACTUATOR-SWIND-VIWECO", "10Nm"),
            ("MPRD", "HONEYWELL", 400, 400, "MAT-ACTUATOR-HONEYWELL-5NM", "5Nm"),
        ]
        for kind, brand, w, h, mat, nm in cases:
            got = select_actuator(kind, brand, w, h)
            self.assertEqual((got[0], got[2]), (mat, nm), (kind, brand, w, h))

    def test_display_names_unchanged(self):
        self.assertEqual(select_actuator("MD", "BELIMO", 400, 400)[1], "Động cơ van gió Belimo ON/OFF 5Nm")
        self.assertEqual(select_actuator("MD", "HONEYWELL", 400, 400)[1], "Động cơ van gió HoneyWell ON/OFF 5Nm (Model: CN4605A)")
        self.assertEqual(select_actuator("MPRD", "BELIMO", 1000, 500)[1], "Động cơ tuyến tính 230V Belimo On/Off 10Nm")
        self.assertEqual(select_actuator("MD", "KLB", 400, 400)[1], "Động cơ van gió KLB/VIWECO 24V - 10Nm ON/OFF")

    def test_mfd_models(self):
        self.assertEqual(select_actuator("MFD", "BELIMO", 600, 400, is_single_blade=True)[0], "MAT-ACTUATOR-BELIMO-FSLF24")
        self.assertEqual(select_actuator("MFD", "BELIMO", 600, 400, mfd_model="1.01")[0], "MAT-ACTUATOR-BELIMO-BFN24")
        self.assertEqual(select_actuator("MFD", "BELIMO", 600, 400, mfd_model="1.02")[0], "MAT-ACTUATOR-BELIMO-FSLF24")
        self.assertEqual(select_actuator("MFD", "BELIMO", 600, 400, mfd_model="1.03")[0], "MAT-ACTUATOR-KLB-V6006FS500S")
        self.assertEqual(select_actuator("MFD", "BELIMO", 600, 400, mfd_model="1.04")[0], "MAT-ACTUATOR-HONEYWELL")
        self.assertEqual(select_actuator("MFD", "BELIMO", 600, 400, mfd_mode="single_fslf24")[0], "MAT-ACTUATOR-BELIMO-FSLF24")
        self.assertEqual(select_actuator("MFD", "KLB", 600, 400)[0], "MAT-ACTUATOR-KLB-V6006FS500S")
        self.assertEqual(select_actuator("MFD", "BELIMO", 1200, 800)[0], "MAT-ACTUATOR-BELIMO-BFN24")
        self.assertIsNone(select_actuator("MFD", "BELIMO", 1200, 800)[2])

    def test_actuator_ids_cover_every_selected_id(self):
        allowed = set().union(*ACTUATOR_IDS.values())
        for kind in ("MD", "MPRD", "MFD"):
            for brand in ("BELIMO", "KLB", "HONEYWELL"):
                for w, h in [(400, 400), (1000, 800), (1500, 1500)]:
                    for m in (None, "1.01", "1.02", "1.03", "1.04", "1.05"):
                        self.assertIn(select_actuator(kind, brand, w, h, mfd_model=m)[0], allowed)

    def test_actuator_ids_match_runner_lists(self):
        self.assertEqual(ACTUATOR_IDS["MPRD"], frozenset({"MAT-ACTUATOR-BELIMO-MPRD-5NM", "MAT-ACTUATOR-BELIMO-MPRD", "MAT-ACTUATOR-BELIMO-MPRD-20NM"}))
        self.assertEqual(ACTUATOR_IDS["KLB"], frozenset({"MAT-ACTUATOR-KLB-V6006FS500S", "MAT-ACTUATOR-SWIND-VIWECO"}))
        self.assertTrue(ACTUATOR_IDS["MPRD"] <= ACTUATOR_IDS["BELIMO"])


class Obd(unittest.TestCase):
    def test_calc_obd_matches_current_code(self):
        # Số đo từ agent_05._calc_obd_damper ngày 2026-11-03 (trước khi gom)
        for (w, h), (frame, blade, acc) in {
            (200, 200): (0.115033, 0.091007, 0.600395),
            (600, 400): (0.288713, 0.54819, 1.326061),
            (1200, 800): (0.576058, 2.187561, 2.405305),
        }.items():
            r = calc_obd(w, h, markup_group="damper_rules")
            self.assertAlmostEqual(r["frame_kg"], frame, places=5)
            self.assertAlmostEqual(r["blade_kg"], blade, places=5)
            self.assertAlmostEqual(r["acc_bo"], acc, places=5)

    def test_calc_obd_defaults_missing_size(self):
        self.assertEqual(calc_obd(None, 0)["target_sell"], calc_obd(200, 200)["target_sell"])

    def test_target_sell_rounded_to_thousand(self):
        self.assertEqual(calc_obd(600, 400)["target_sell"] % 1000, 0)

    def test_mult_scales_target(self):
        self.assertGreater(calc_obd(600, 400, mult=1.5)["target_sell"], calc_obd(600, 400)["target_sell"])


class Mesh(unittest.TestCase):
    def test_lcct_uses_insect_screen_price(self):
        self.assertEqual(mesh_price(1000, 1000, "lcct"), 200000)
        self.assertEqual(mesh_price(333, 333, "lcct"), 22178)       # 0.110889 m² × 200000, làm tròn đồng

    def test_luoi_rounds_to_thousand(self):
        self.assertEqual(mesh_price(1000, 1000, "luoi"), 150000)
        self.assertEqual(mesh_price(333, 333, "luoi"), 17000)       # 16633 → 17000

    def test_filter_g4(self):
        self.assertEqual(filter_g4_price(600, 600), 72000)

    def test_unknown_type(self):
        with self.assertRaises(ValueError):
            mesh_price(100, 100, "chim")


POLICY = {"COMMERCIAL": {"categories": ["THUONG_MAI", "ONG_MEM", "KHAC"], "labor_rate": 0.0, "overhead_rate": 0.02, "margin": 0.10},
          "MANUFACTURING": {"categories": ["ONG_GIO", "CUA_GIO", "VAN_GIO", "CANVAS", "TIEU_AM"], "labor_rate": 0.25, "overhead_rate": 0.10, "margin": 0.18}}


class SellPrice(unittest.TestCase):
    def test_financial_rates(self):
        self.assertEqual(financial_rates("VAN_GIO", POLICY), (0.25, 0.10, 0.18))
        self.assertEqual(financial_rates("THUONG_MAI", POLICY), (0.0, 0.02, 0.10))
        self.assertEqual(financial_rates("LA_LUNG", POLICY), (0.0, 0.02, 0.10))   # nhóm lạ -> thương mại
        self.assertEqual(financial_rates("VAN_GIO", {}), (0.25, 0.10, 0.18))       # policy rỗng -> mặc định

    def test_sell_price_with_motor(self):
        # vật tư 200.000 + động cơ 500.000: NC 50.000, QL 20.000; (270.000 x 1,18) + 500.000 = 818.600
        comps = [{"mat_id": "A", "calc_qty": 2, "category": "NHÔM"}, {"mat_id": "M", "calc_qty": 1, "category": "ĐỘNG_CƠ_VÀ_CẢM_BIẾN"}]
        r = sell_price(comps, {"A": 100000.0, "M": 500000.0}, "VAN_GIO", POLICY)
        self.assertEqual((r["m_cost"], r["mot_cost"]), (700000.0, 500000.0))
        self.assertEqual(r["sell_unit"], 818600)
        self.assertEqual(r["sell_mat"], 759600)     # (220.000 x 1,18) + 500.000
        self.assertEqual(r["sell_lab"], 59000)      # 50.000 x 1,18

    def test_sell_unit_rounds_up_to_hundred(self):
        r = sell_price([{"mat_id": "A", "calc_qty": 1, "category": "NHÔM"}], {"A": 100001.0}, "VAN_GIO", POLICY)
        self.assertEqual(r["sell_unit"] % 100, 0)
        self.assertGreaterEqual(r["sell_unit"], r["sell_unit_raw"])

    def test_ref_price_used_when_master_missing(self):
        r = sell_price([{"mat_id": "X", "calc_qty": 1, "category": "TM", "ref_price": 1000.0}], {}, "THUONG_MAI", POLICY)
        self.assertEqual(r["m_cost"], 1000.0)

    def test_zero_cost_gives_zero(self):
        self.assertEqual(sell_price([], {}, "VAN_GIO", POLICY)["sell_unit"], 0)


if __name__ == "__main__":
    unittest.main()
