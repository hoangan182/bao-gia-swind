"""
Bộ nhận diện ỐNG GIÓ & PHỤ KIỆN (duct_classifier) — chạy bảng rule `data/master_data/duct_rules.json`.

Tách từ chuỗi if cũ trong `Agent04.detect_duct_subtype` và các danh sách từ khóa rải rác (LCCT / G4 trong cút,
LCCT trong phụ kiện vuông, canvas chống cháy, hộp trong Ghi chú) — kế hoạch tách agent đọc BOQ, việc C2, 2026-11-03.
Module chỉ PHÂN LOẠI; công thức tôn / giá vẫn ở `Agent04._calc_*`.

Sửa rule: sửa JSON (thêm từ khóa / đổi thứ tự / thêm rule), ghi `nguon` / `ly_do`, thêm ví dụ rồi chạy
`tests/test_swind_duct_rules.py`. Điều kiện hình học mới → thêm vào `_GEOM` (có tên, ghi trong `cu_phap.hinh_hoc`).
Vai trò: `.agents/roles/duct_classifier_role.md`.
"""
import os
import re
import json
import unicodedata

RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "master_data", "duct_rules.json")
_RULES_CACHE = {}


def load_rules(path=None):
    path = path or RULES_PATH
    mtime = os.path.getmtime(path)
    cached = _RULES_CACHE.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    data["_extra"] = {r["id"].split("_", 1)[0]: r for r in data["quy_tac_bo_sung"]}
    data["_box_rx"] = re.compile(data["_extra"]["OG-21"]["regex_hop"], re.IGNORECASE)
    _RULES_CACHE[path] = (mtime, data)
    return data


_GEOM = {
    "tron": lambda g: g["is_round"],
    "vuong_co_d_khong_w2": lambda g: not g["is_round"] and g["w1"] > 0 and g["h1"] > 0 and g["d1"] > 0 and g["w2"] == 0,
    "hai_dau_khac_nhau": lambda g: g["w1"] > 0 and g["w2"] > 0 and (g["w1"] != g["w2"] or g["h1"] != g["h2"]),
    "khong_w_khong_d": lambda g: g["w1"] == 0 and g["d1"] == 0,
    "khong_kich_thuoc": lambda g: g["w1"] == 0 and g["h1"] == 0 and g["d1"] == 0,
}


def _matches(rule, t, u, g):
    if rule.get("mac_dinh"):
        return True
    hit = (any(k in t for k in rule.get("tu_khoa", ()))
           or any(re.search(p, t) for p in rule.get("regex", ()))
           or bool(rule.get("bat_dau") and t.startswith(tuple(rule["bat_dau"])))
           or any(k in u for k in rule.get("don_vi", ()))
           or ("hoac_hinh_hoc" in rule and _GEOM[rule["hoac_hinh_hoc"]](g)))
    if not hit:
        return False
    if "va_hinh_hoc" in rule and not _GEOM[rule["va_hinh_hoc"]](g):
        return False
    if any(p in t for p in rule.get("tru_cum", ())):
        return False
    if rule.get("tru_bat_dau") and t.startswith(tuple(rule["tru_bat_dau"])):
        return False
    return True


def detect_subtype(text, w1=0.0, h1=0.0, w2=0.0, h2=0.0, d1=0.0, d2=0.0, unit="", category="", rules=None, trail=None):
    """Loại ống / phụ kiện theo bảng `thu_tu_nhan_dien` (rule đầu tiên khớp thắng) + OG-19 (nhóm TIEU_AM)."""
    R = rules or load_rules()
    t = unicodedata.normalize("NFC", str(text or "")).lower().strip()
    u = unicodedata.normalize("NFC", str(unit or "")).lower().strip()
    rt = R["ong_tron"]
    has_rect_pair = bool(re.search(rt["regex_cap_vuong"], t))
    is_round = (d1 > 0 and w1 == 0) or (
        d1 > 0 and w1 == d1 and h1 == d1 and not has_rect_pair and any(k in t for k in rt["tu_khoa"])
    )
    g = {"is_round": is_round, "w1": w1, "h1": h1, "w2": w2, "h2": h2, "d1": d1}
    rule = next(r for r in R["thu_tu_nhan_dien"] if _matches(r, t, u, g))
    res = rule["ket_qua"]
    subtype = res if isinstance(res, str) else res["tron" if is_round else "vuong"]
    if trail is not None:
        trail.append(rule["id"])
    if str(category or "").upper() == "TIEU_AM" and subtype not in ("SILENCER_SQ", "SILENCER_RT"):
        subtype = "SILENCER_RT" if (d1 > 0 and w1 == 0) else "SILENCER_SQ"
        if trail is not None:
            trail.append("OG-19")
    return subtype


# ---------------------------------------------------------------- Hộp trong Ghi chú (OG-21)

def parse_note_boxes(note_text, rules=None):
    """Các hộp ghi trong Ghi chú dạng 'BOX CẤP 600x300x300 / BOX HỒI 700x300x300' -> [(nhãn, W, H, L), ...]."""
    R = rules or load_rules()
    return [
        (m.group(1).strip().lower(), float(m.group(2)), float(m.group(3)), float(m.group(4)))
        for m in R["_box_rx"].finditer(note_text or "")
    ]


def note_box_conflict(raw_name, note_text, rules=None):
    """OG-21: Ghi chú ghi ĐÚNG 1 hộp mà W x H khác kích thước ghi ở Tên → trả mô tả để HỎI LẠI USER, ngược lại None."""
    R = rules or load_rules()
    boxes = parse_note_boxes(note_text, R)
    if len(boxes) != 1:
        return None
    m = re.search(R["_extra"]["OG-21"]["regex_kt_ten"], str(raw_name or "").replace('×', 'x'))
    if not m:
        return None
    nw, nh = float(m.group(1)), float(m.group(2))
    _, bw, bh, bl = boxes[0]
    if {nw, nh} == {bw, bh}:
        return None
    return f"Tên ghi {int(nw)}x{int(nh)}, Ghi chú ghi hộp {int(bw)}x{int(bh)}xL{int(bl)} — đang tính theo Ghi chú"


# ---------------------------------------------------------------- Phụ kiện kèm theo (OG-22..OG-24)

def elbow_mesh_filter(raw_name, rules=None):
    """OG-22: (có LCCT, có lọc G4) ghi ở Tên dòng cút."""
    r = (rules or load_rules())["_extra"]["OG-22"]
    low = str(raw_name or "").lower()
    return any(k in low for k in r["tu_khoa_luoi"]), any(k in low for k in r["tu_khoa_loc"])


def has_mesh_on_rect(full_text, rules=None):
    """OG-23: ống / phụ kiện vuông ghi kèm lưới chắn côn trùng."""
    r = (rules or load_rules())["_extra"]["OG-23"]
    low = str(full_text or "").lower()
    return any(k in low for k in r["tu_khoa"]) or bool(re.search(r["regex"], low))


def is_fire_canvas(model_std, raw_search, rules=None):
    """OG-24: canvas chống cháy."""
    r = (rules or load_rules())["_extra"]["OG-24"]
    return ("CHONG-CHAY" in str(model_std or "")) or any(k in raw_search for k in r["tu_khoa"])
