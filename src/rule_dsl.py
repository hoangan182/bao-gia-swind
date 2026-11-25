"""
Bộ điều kiện JSON dùng chung cho các bộ phân loại theo bảng rule (rule_dsl).

Tách từ `diffuser_classifier._Ctx` (Việc 4 — gom quyết định loại hàng về classifier, Task 1, 2026-11-24) để
bộ phân loại loại hàng mới dùng lại cùng cú pháp. Cú pháp điều kiện:

- `true` / `false`; cờ `"x"` (cờ bật) / `"!x"` (cờ tắt)
- `{"tat_ca": [..]}`, `{"mot_trong": [..]}`, `{"khong": cond}`
- `{"tu_khoa": [..], "trong": "<biến>", "tru": [..], "khop_bien": true}` — chuỗi con; `khop_bien` → so theo
  ranh giới từ (`scope_filter.match_keyword`). Mục `"@nhom"` mở rộng theo nhóm từ khóa.
- `{"regex": "...", "trong": "<biến>", "ignorecase": true}`
- `{"bat_dau": [..], "trong": "<biến>"}` — chuỗi bắt đầu bằng 1 trong các từ
- `{"ham": "<tên>", "trong": "<biến>"}` — gọi hàm trong danh sách trắng `predicates` (không eval / import động)
- `{"so_sanh": [a, op, b]}` (a/b: số, biến số, `max_wh` / `min_wh`, hoặc `[biến, "*", hệ số]`)
- `{"thuoc": ["<biến số>", [giá trị..]]}`

Ghi vết (bảng 'đã hiểu thế nào', Việc 2): khi tu_khoa / regex / bat_dau khớp ngoài mệnh đề `khong` → gọi
`_add_hit(biến, matcher)`; cờ dương khớp → cộng `flag_src[cờ]` vào `hits`. Lớp con ghi đè `_add_hit` để quy nguồn.
"""
import re


class RuleContext:
    """Trạng thái 1 lần phân loại: biến văn bản `text`, biến số `num`, cờ `flags`, vết `hits`."""

    label = "rule_dsl"

    def __init__(self, rules, groups=None, predicates=None):
        self.rules = rules
        self.groups_cfg = groups or {}
        self.predicates = predicates or {}
        self.text = {}
        self.flags = {}
        self.num = {}
        self._groups = {}
        self.hits = set()
        self.flag_src = {}
        self._neg = 0

    # --- Dữ liệu ---
    def nums(self, name):
        if name == "max_wh":
            return max(self.num["w"], self.num["h"])
        if name == "min_wh":
            return min(self.num["w"], self.num["h"])
        return self.num[name]

    def group(self, name):
        if name not in self._groups:
            self._groups[name] = tuple(self.groups_cfg[name])
        return self._groups[name]

    def words(self, items):
        out = []
        for it in ([items] if isinstance(items, str) else items):
            if it.startswith("@"):
                out.extend(self.group(it[1:]))
            else:
                out.append(it)
        return out

    def operand(self, v):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return v
        if isinstance(v, list):  # [biến, '*', hệ số]
            return self.operand(v[0]) * float(v[2])
        return self.nums(v)

    # --- Hook lớp con ---
    def regex_pattern(self, cond):
        return cond["regex"]

    def _add_hit(self, var, matcher):
        self.hits.add(var)

    # --- Điều kiện ---
    def ok(self, cond):
        if cond is True or cond is False:
            return cond
        if isinstance(cond, str):
            if cond.startswith("!"):
                return not self.flags.get(cond[1:], False)
            val = bool(self.flags.get(cond, False))
            if val and not self._neg:
                self.hits |= self.flag_src.get(cond, set())
            return val
        if "tat_ca" in cond:
            return all(self.ok(c) for c in cond["tat_ca"])
        if "mot_trong" in cond:
            return any(self.ok(c) for c in cond["mot_trong"])
        if "khong" in cond:
            self._neg += 1
            try:
                return not self.ok(cond["khong"])
            finally:
                self._neg -= 1
        if "tu_khoa" in cond:
            txt = self.text[cond["trong"]]
            skip = set(cond.get("tru", ()))
            words = [k for k in self.words(cond["tu_khoa"]) if k not in skip]
            if cond.get("khop_bien"):
                from scope_filter import match_keyword  # import muộn tránh vòng import
                matcher = lambda t: any(match_keyword(k, t) for k in words)  # noqa: E731
                val = matcher(txt)
            else:
                matcher = lambda t: any(k in t for k in words)  # noqa: E731
                val = any(k in txt for k in words)
            if val and not self._neg:
                self._add_hit(cond["trong"], matcher)
            return val
        if "regex" in cond:
            pat = self.regex_pattern(cond)
            fl = re.IGNORECASE if cond.get("ignorecase") else 0
            val = bool(re.search(pat, self.text[cond["trong"]], fl))
            if val and not self._neg:
                self._add_hit(cond["trong"], lambda t: bool(re.search(pat, t, fl)))
            return val
        if "so_sanh" in cond:
            a, op, b = cond["so_sanh"]
            a, b = self.operand(a), self.operand(b)
            return {">": a > b, ">=": a >= b, "<": a < b, "<=": a <= b, "==": a == b, "!=": a != b}[op]
        if "thuoc" in cond:
            var, vals = cond["thuoc"]
            return int(self.nums(var)) in vals
        if "bat_dau" in cond:
            prefixes = tuple(self.words(cond["bat_dau"]))
            val = self.text[cond["trong"]].startswith(prefixes)
            if val and not self._neg:
                self._add_hit(cond["trong"], lambda t: t.startswith(prefixes))
            return val
        if "ham" in cond:
            fn = self.predicates.get(cond["ham"])
            if fn is None:
                raise ValueError(f"{self.label}: hàm điều kiện không có trong danh sách trắng: {cond['ham']!r}")
            return bool(fn(self.text[cond["trong"]]))
        raise ValueError(f"{self.label}: điều kiện không hiểu: {cond}")

    def pick_opt(self, options):
        for opt in options:
            if "khi" not in opt or self.ok(opt["khi"]):
                return opt
        return None
