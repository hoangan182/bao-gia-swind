"""Test bộ điều kiện JSON dùng chung (src/rule_dsl.py — Việc 4, Task 1)."""
import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "src"))

from rule_dsl import RuleContext  # noqa: E402


def _ctx(**kw):
    ctx = RuleContext({}, groups={"van": ["mfd", "fd"]},
                      predicates={"co_so": lambda t: any(c.isdigit() for c in t)}, **kw)
    ctx.text.update(ten="cửa gió chống cháy 600x300", rong="")
    ctx.num.update(w=600.0, h=300.0, d=0.0)
    ctx.flags.update(has_obd=True, has_mesh=False)
    return ctx


class TestRuleDsl(unittest.TestCase):
    def test_flags(self):
        c = _ctx()
        self.assertTrue(c.ok("has_obd"))
        self.assertFalse(c.ok("has_mesh"))
        self.assertTrue(c.ok("!has_mesh"))
        self.assertFalse(c.ok("!has_obd"))
        self.assertTrue(c.ok(True))
        self.assertFalse(c.ok(False))

    def test_tat_ca_mot_trong_khong(self):
        c = _ctx()
        self.assertTrue(c.ok({"tat_ca": ["has_obd", "!has_mesh"]}))
        self.assertFalse(c.ok({"tat_ca": ["has_obd", "has_mesh"]}))
        self.assertTrue(c.ok({"mot_trong": ["has_mesh", "has_obd"]}))
        self.assertFalse(c.ok({"mot_trong": ["has_mesh"]}))
        self.assertTrue(c.ok({"khong": "has_mesh"}))
        self.assertFalse(c.ok({"khong": "has_obd"}))

    def test_tu_khoa_and_tru_and_groups(self):
        c = _ctx()
        self.assertTrue(c.ok({"tu_khoa": ["cửa gió"], "trong": "ten"}))
        self.assertFalse(c.ok({"tu_khoa": ["van"], "trong": "ten"}))
        self.assertFalse(c.ok({"tu_khoa": ["cửa gió"], "trong": "ten", "tru": ["cửa gió"]}))
        c.text["ten"] = "van mfd 600x300"
        self.assertTrue(c.ok({"tu_khoa": ["@van"], "trong": "ten"}))
        self.assertEqual(c.words(["@van", "x"]), ["mfd", "fd", "x"])

    def test_tu_khoa_khop_bien(self):
        c = _ctx()
        # 'ống' nằm trong 'chống' — so chuỗi con khớp, so ranh giới từ thì không
        self.assertTrue(c.ok({"tu_khoa": ["ống"], "trong": "ten"}))
        self.assertFalse(c.ok({"tu_khoa": ["ống"], "trong": "ten", "khop_bien": True}))
        self.assertTrue(c.ok({"tu_khoa": ["cháy"], "trong": "ten", "khop_bien": True}))

    def test_regex(self):
        c = _ctx()
        self.assertTrue(c.ok({"regex": r"\d+x\d+", "trong": "ten"}))
        self.assertFalse(c.ok({"regex": r"^van", "trong": "ten"}))
        self.assertTrue(c.ok({"regex": "CỬA", "trong": "ten", "ignorecase": True}))

    def test_so_sanh_thuoc(self):
        c = _ctx()
        self.assertTrue(c.ok({"so_sanh": ["max_wh", ">=", 600]}))
        self.assertFalse(c.ok({"so_sanh": ["min_wh", ">", 300]}))
        self.assertTrue(c.ok({"so_sanh": ["h", "==", ["w", "*", 0.5]]}))
        self.assertTrue(c.ok({"thuoc": ["w", [600, 450]]}))
        self.assertFalse(c.ok({"thuoc": ["h", [600, 450]]}))

    def test_bat_dau(self):
        c = _ctx()
        self.assertTrue(c.ok({"bat_dau": ["van", "cửa"], "trong": "ten"}))
        self.assertFalse(c.ok({"bat_dau": ["van"], "trong": "ten"}))
        c.text["ten"] = "mfd 600x300"
        self.assertTrue(c.ok({"bat_dau": "@van", "trong": "ten"}))

    def test_ham(self):
        c = _ctx()
        self.assertTrue(c.ok({"ham": "co_so", "trong": "ten"}))
        self.assertFalse(c.ok({"ham": "co_so", "trong": "rong"}))

    def test_unknown_predicate_raises(self):
        c = _ctx()
        with self.assertRaises(ValueError):
            c.ok({"ham": "os.system", "trong": "ten"})

    def test_unknown_condition_raises(self):
        with self.assertRaises(ValueError):
            _ctx().ok({"la": 1})

    def test_hits_recorded_and_negation_skipped(self):
        c = _ctx()
        c.ok({"tu_khoa": ["cửa"], "trong": "ten"})
        self.assertEqual(c.hits, {"ten"})
        c.hits = set()
        c.ok({"khong": {"tu_khoa": ["cửa"], "trong": "ten"}})
        self.assertEqual(c.hits, set())
        c.ok({"bat_dau": ["cửa"], "trong": "ten"})
        self.assertEqual(c.hits, {"ten"})
        c.hits = set()
        c.flag_src["has_obd"] = {"ghi_chu"}
        c.ok("has_obd")
        self.assertEqual(c.hits, {"ghi_chu"})


if __name__ == "__main__":
    unittest.main()
