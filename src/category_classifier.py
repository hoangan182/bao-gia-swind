"""
Bộ quyết định LOẠI HÀNG (nhóm) của 1 dòng BOQ theo bảng rule `data/master_data/category_rules.json`.

Việc 4 — gom quyết định loại hàng về classifier (Task 3, 2026-11-25): thay chuỗi if/elif ~170 dòng trong
`SwindBOQParser.parse_sheet`. Bảng có thứ tự; ngữ nghĩa giữ y hệt chuỗi cũ:

- Rule chỉ được xét khi loại hàng hiện tại còn `KHAC`.
- Mỗi rule thuộc 1 `khoi` (`BUOC_1_4` = Học máy / ống nước / bước 2-4, `BUOC_5` = fallback có kiểm soát):
  khi 1 rule khớp, các rule còn lại CÙNG khối bị bỏ qua (giữ if/elif cũ: Học máy trả `KHAC` vẫn bỏ bước 2-4
  nhưng bước 5 vẫn chạy).
- Rule khớp sau cùng là rule quyết định (`rule_id`). Không rule nào khớp → `khong_khop` (`LH-KHAC`).
- `nguon_chu`: TEN | TITLE | GHI_CHU | HOC_MAY | TEN_HOAC_TITLE (= TITLE khi dòng chỉ kích thước đã ghép Title
  vào tên — cờ `name_has_title` — vì chữ 'tên' khi đó thực chất là chữ Title).
- `chac` của kết quả = `chac` của rule VÀ loại hàng ≠ KHAC.
- `chuan_hoa` (cuối bảng): PHU_KIEN_ONG→ONG_GIO, KHOP_NOI_MEM|CHUP_THONG_HOI→CANVAS, CUA_GIO ghi Ventcap→CANVAS.

Điều kiện dùng `rule_dsl.RuleContext`, cộng 1 điều kiện riêng của bộ này (dữ liệu catalog, không phải
cú pháp chung): `{"tra_danh_muc": <spec>}` (tra catalog có khớp không).
Kết quả rule: `"<NHÓM>"`, `{"hoc_may": "<biến>"}` (tra từ điển học máy; không có → rule coi như không khớp), hoặc spec tra catalog
`{"danh_muc": "SX"|"TM", "trong": "<biến>", "chi_ma"|"chi_nhom"|"nhom_tru": [..], "gan": "<NHÓM>",
"bo_qua_khi": [{"ma"|"nhom": [..], "khi": <điều kiện>}]}` — catalog nạp như `SwindBOQParser._load_catalogs`,
từ khóa catalog so theo ranh giới từ (`scope_filter.match_keyword`).
"""
import json
import os
import re

import duct_classifier
import scope_filter
from rule_dsl import RuleContext

RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                          "data", "master_data", "category_rules.json")

_FILTER_CACHE = {}


def _coarse_filter_cfg():
    """(tiền tố lọc thô, regex lọc tinh) từ category_rules.json -> loc_tho_dung_rieng; nạp lại khi file đổi (mtime)."""
    data = load_rules()
    hit = _FILTER_CACHE.get("cfg")
    if hit and hit[0] is data:
        return hit[1]
    cfg = data["loc_tho_dung_rieng"]
    val = (tuple(cfg["tien_to"]), re.compile(cfg["regex_loc_tinh"]))
    _FILTER_CACHE["cfg"] = (data, val)
    return val


def is_standalone_coarse_filter(name_lower):
    """Dòng BOQ là lọc bụi thô / G4 đứng riêng (không phải lọc tinh F5-F9/HEPA, than hoạt tính, lọc tĩnh điện, lọc túi).
    Danh sách tiền tố / regex lọc tinh: category_rules.json -> loc_tho_dung_rieng (Task A, 2026-11-25)."""
    prefixes, fine_rx = _coarse_filter_cfg()
    n = re.sub(r'^\s*[-•*+]+\s*', '', name_lower)
    n = re.sub(r'^(?:cung cấp|gia công|sản xuất|lắp đặt)(?:\s*(?:,|và|&)\s*(?:cung cấp|gia công|sản xuất|lắp đặt))*\s*:?\s*', '', n)
    return n.startswith(prefixes) and not fine_rx.search(n)


# Danh sách trắng hàm điều kiện `{"ham": ...}` (không eval / import động)
PREDICATES = {
    "is_standalone_coarse_filter": is_standalone_coarse_filter,
    "scope_filter.is_commercial_by_name": scope_filter.is_commercial_by_name,
    "is_fan_connection_transition": scope_filter.is_fan_connection_transition,
    "is_duct_insulation": scope_filter.is_duct_insulation,
    "is_insect_screen_code": scope_filter.is_insect_screen_code,
    "is_louver_code": scope_filter.is_louver_code,
    "is_glued_damper_code": scope_filter.is_glued_damper_code,
    "is_auxiliary_material": scope_filter.is_auxiliary_material,
    "duct_classifier.is_ventcap_name": duct_classifier.is_ventcap_name,
}

_CACHE = {}


def load_rules(path=None):
    p = path or RULES_PATH
    mt = os.path.getmtime(p)
    hit = _CACHE.get(p)
    if hit and hit[0] == mt:
        return hit[1]
    with open(p, encoding="utf-8") as f:
        data = json.load(f)
    _CACHE[p] = (mt, data)
    return data


class _Ctx(RuleContext):
    label = "category_rules"

    def __init__(self, rules, catalogs, learned):
        super().__init__(rules, rules.get("nhom_tu_khoa"), PREDICATES)
        self.catalogs = catalogs or {}
        self.learned = learned or {}

    def lookup(self, spec):
        """Tra catalog theo spec → nhóm khớp đầu tiên (thứ tự catalog) hoặc None."""
        cat_list = self.catalogs.get("manufacturable" if spec["danh_muc"] == "SX" else "commercial", [])
        txt = self.text[spec["trong"]]
        for entry in cat_list:
            code, grp = entry.get("product_code"), entry.get("mapping_category")
            if "chi_ma" in spec and code not in spec["chi_ma"]:
                continue
            if "chi_nhom" in spec and grp not in spec["chi_nhom"]:
                continue
            if "nhom_tru" in spec and grp in spec["nhom_tru"]:
                continue
            if any((code in sk.get("ma", ()) or grp in sk.get("nhom", ())) and self.ok(sk["khi"])
                   for sk in spec.get("bo_qua_khi", ())):
                continue
            if any(scope_filter.match_keyword(kw, txt) for kw in entry.get("keywords", [])):
                if not self._neg:
                    self._add_hit(spec["trong"], None)
                return spec.get("gan") or (grp if spec["danh_muc"] == "SX" else "THUONG_MAI")
        return None

    def ok(self, cond):
        if isinstance(cond, dict):
            if "tra_danh_muc" in cond:
                return self.lookup(cond["tra_danh_muc"]) is not None
        return super().ok(cond)

    def result(self, kq):
        if isinstance(kq, str):
            return kq
        if "hoc_may" in kq:
            return self.learned.get(self.text[kq["hoc_may"]])
        return self.lookup(kq)


def _nguon(rule, flags):
    src = rule["nguon_chu"]
    if src == "TEN_HOAC_TITLE":
        src = "TITLE" if flags.get("name_has_title") else "TEN"
    return [src]


def classify(texts, flags, catalogs, learned, rules=None):
    """texts: name_lower, full_name_lower, sec_lower, note_boq, model_str, raw_name_str, name_str (chuỗi parser);
    flags: is_plumbing_item, is_hvac_prd, name_has_title; catalogs: {"manufacturable", "commercial"};
    learned: từ điển học máy {chữ: nhóm} (boq_keyword_learning.json).
    → {"category", "rule_id", "nguon", "chac"}."""
    R = rules or load_rules()
    ctx = _Ctx(R, catalogs, learned)
    note_boq = texts.get("note_boq") or ""
    model_str = texts.get("model_str") or ""
    ctx.text = {
        "name_lower": texts["name_lower"], "full_name_lower": texts["full_name_lower"],
        "sec_lower": texts["sec_lower"], "name_str": texts.get("name_str") or "",
        "note_lower": note_boq.lower(), "note_model_lower": f"{note_boq} {model_str}".lower(),
        "raw_name_lower": str(texts.get("raw_name_str") or "").lower(),
    }
    ctx.flags = {
        "is_plumbing_item": bool(flags.get("is_plumbing_item")), "is_hvac_prd": bool(flags.get("is_hvac_prd")),
        "name_has_title": bool(flags.get("name_has_title")),
        "co_ghi_chu_model": bool(note_boq or model_str),
        "title_khac_ten": texts["full_name_lower"] != texts["name_lower"],
    }
    category, rule, done = "KHAC", None, set()
    for r in R["quy_tac"]:
        if category != "KHAC" or r["khoi"] in done:
            continue
        if not ctx.ok(r["khi"]):
            continue
        val = ctx.result(r["ket_qua"])
        if val is None:
            continue
        category, rule = val, r
        done.add(r["khoi"])
    for ch in R.get("chuan_hoa", []):
        if category in ch["tu"] and ("khi" not in ch or ctx.ok(ch["khi"])):
            category = ch["thanh"]
    if rule is None:
        rule = R["khong_khop"]
    return {"category": category, "rule_id": rule["id"], "nguon": _nguon(rule, ctx.flags),
            "chac": bool(rule.get("chac", True)) and category != "KHAC"}
