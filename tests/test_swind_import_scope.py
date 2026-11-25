"""Chặn lỗi UnboundLocalError do `import x` cục bộ trong hàm che tên đã import ở đầu file.

Sự cố 2026-11-25: `import decision_trace` đặt trong run_master_pipeline làm `decision_trace` thành tên cục bộ của cả hàm,
nên nhánh `--lined-duct-as-duct` (dùng decision_trace TRƯỚC dòng import) bị UnboundLocalError. E2E không chạy cờ hiếm này
nên không bắt được. Test này quét mọi file src/*.py: một hàm có import cục bộ trùng tên import đầu file VÀ dùng tên đó
trước dòng import → fail.
"""
import ast
import glob
import os
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _module_level_names(tree):
    names = set()
    for n in tree.body:
        if isinstance(n, ast.Import):
            names |= {(a.asname or a.name).split(".")[0] for a in n.names}
        elif isinstance(n, ast.ImportFrom):
            names |= {a.asname or a.name for a in n.names}
    return names


def shadowed_use_before_import(source):
    """Trả danh sách (hàm, tên, dòng import, dòng dùng sớm nhất) có nguy cơ UnboundLocalError."""
    tree = ast.parse(source)
    top = _module_level_names(tree)
    bad = []
    for fn in ast.walk(tree):
        if not isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        first_import = {}
        for n in ast.walk(fn):
            if isinstance(n, (ast.Import, ast.ImportFrom)):
                for a in n.names:
                    nm = (a.asname or a.name).split(".")[0] if isinstance(n, ast.Import) else (a.asname or a.name)
                    if nm in top:
                        first_import[nm] = min(first_import.get(nm, n.lineno), n.lineno)
        for nm, line in first_import.items():
            uses = [x.lineno for x in ast.walk(fn) if isinstance(x, ast.Name) and x.id == nm and x.lineno < line]
            if uses:
                bad.append((fn.name, nm, line, min(uses)))
    return bad


class ImportScopeTest(unittest.TestCase):
    def test_detector_catches_the_2026_11_25_bug(self):
        src = (
            "import decision_trace\n"
            "def run():\n"
            "    decision_trace.record(1)\n"
            "    try:\n"
            "        import decision_trace\n"
            "    except Exception:\n"
            "        pass\n"
        )
        self.assertEqual(shadowed_use_before_import(src), [("run", "decision_trace", 5, 3)])

    def test_local_import_after_use_of_other_name_is_fine(self):
        src = "import os\ndef f():\n    import json\n    return json.dumps({})\n"
        self.assertEqual(shadowed_use_before_import(src), [])

    def test_no_function_uses_a_name_before_shadowing_it_locally(self):
        problems = []
        for path in sorted(glob.glob(os.path.join(ROOT, "src", "*.py"))):
            with open(path, encoding="utf-8") as fh:
                for fn, nm, imp, use in shadowed_use_before_import(fh.read()):
                    problems.append(f"{os.path.basename(path)}:{fn}: dùng '{nm}' ở dòng {use} trước import cục bộ dòng {imp}")
        self.assertEqual(problems, [], "UnboundLocalError tiềm ẩn:\n" + "\n".join(problems))


if __name__ == "__main__":
    unittest.main()
