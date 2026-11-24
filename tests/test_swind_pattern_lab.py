"""Kiểm thử thư viện mẫu dòng (src/swind_pattern_lab.py) — tầng 1 + 2 kiểm thử hồi quy (2026-11-24)."""
import json
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))
import swind_pattern_lab as L  # noqa: E402

LAYOUT = {"stt": 1, "name": 2, "unit": 3, "qty": 4}


class TestSignature(unittest.TestCase):
    def test_bo_qua_so(self):
        a = L._signature("Van gió", "", {"name": "Van chặn lửa 400x300", "unit": "Cái", "qty": 2}, LAYOUT)
        b = L._signature("Van gió", "", {"name": "Van chặn lửa 600x500", "unit": "Cái", "qty": 9}, LAYOUT)
        self.assertEqual(a, b)

    def test_khac_title_khac_mau(self):
        a = L._signature("Van gió", "", {"name": "400x300", "unit": "Cái"}, LAYOUT)
        b = L._signature("Cửa gió", "", {"name": "400x300", "unit": "Cái"}, LAYOUT)
        self.assertNotEqual(a, b)

    def test_khac_bo_cuc_khac_mau(self):
        a = L._signature("", "", {"name": "Van FD 400x300"}, LAYOUT)
        b = L._signature("", "", {"name": "Van FD 400x300"}, dict(LAYOUT, spec=5))
        self.assertNotEqual(a, b)


class TestReplay(unittest.TestCase):
    def _inst(self, row, title, name, unit="Cái", qty=2):
        cells = {"stt": row, "name": name, "unit": unit, "qty": qty}
        return ("sig" + str(row), "F.xlsx", "S", row, title, "", json.dumps(cells, ensure_ascii=False),
                json.dumps(LAYOUT, sort_keys=True), 0)

    def test_sheet_ao_dung_title_va_loai_hang(self):
        res = L._replay_chunk([
            self._inst(10, "Van chặn lửa", "400x300"),                    # dòng chỉ kích thước kế thừa Title
            self._inst(11, "", "Cửa gió nan thẳng 600x300 + OBD"),
            self._inst(12, "", "Quạt hướng trục 5000m3/h"),               # thiết bị → bị lọc
        ])
        self.assertEqual(res["F.xlsx|S|10"]["out"][0]["status"], "PRICED")
        self.assertEqual(res["F.xlsx|S|10"]["out"][0]["category"], "VAN_GIO")
        self.assertEqual(res["F.xlsx|S|11"]["out"][0]["model_std"], "SDG+O")
        self.assertTrue(res["F.xlsx|S|12"]["out"][0]["status"].startswith("SKIP:"))

    def test_on_dinh(self):
        chunk = [self._inst(10, "Van chặn lửa", "400x300"), self._inst(11, "", "Louver 1000x500 kèm LCCT")]
        self.assertEqual(L._replay_chunk(chunk), L._replay_chunk(chunk))


class TestCanaryFeatures(unittest.TestCase):
    def test_dac_trung_dong(self):
        v = {"out": [{"status": "PRICED", "category": "CUA_GIO", "model_std": "SDG+O+N + FD", "price_source": "SWIND_CALC"}],
             "trace": ["CG-09_DU_PHONG"]}
        f = L._instance_features(v)
        self.assertTrue({"S:PRICED", "C:CUA_GIO", "M:CUA_GIO:SDG", "M:CUA_GIO:FD", "SUF:CUA_GIO:O", "SUF:CUA_GIO:N",
                         "P:SWIND_CALC", "R:CG-09_DU_PHONG"} <= f)

    def test_hang_thuong_mai_khong_tinh_model(self):
        f = L._instance_features({"out": [{"status": "SKIP:OUT_OF_SCOPE_THUONG_MAI", "category": "THUONG_MAI", "model_std": "Quạt 5000"}]})
        self.assertIn("S:SKIP:OUT_OF_SCOPE_THUONG_MAI", f)
        self.assertFalse(any(x.startswith("M:") for x in f))

    def test_vet_rule_ghi_khi_chay_lai(self):
        res = L._replay_chunk([TestReplay()._inst(10, "", "Cửa gió nan thẳng 600x300 + OBD")])
        self.assertTrue(any(t.startswith("CG-") for t in res["F.xlsx|S|10"]["trace"]))


if __name__ == "__main__":
    unittest.main()
