"""
Phân vai Title cha / Dòng con (title_row_resolver) — chạy bảng rule `data/master_data/title_row_rules.json`.

Vai Title: NONE / LOAI_HANG / PHU_KIEN / HANG_MUC. Vai Dòng (chỉ chữ của chính dòng): DU_LOAI / CHI_KT / KHONG_NHAN_RA.
`decide` chỉ trả các ô phải HỎI LẠI User (TITLE_ROW_ASK = Loại 4, TITLE_UNCLEAR = Title không có loại hàng);
các ô khác trả None → parser giữ hành vi hiện tại (kế thừa thông số, dòng ghi loại khác thắng Title — AGENTS.md 1a).
Module chỉ đọc chuỗi, không đọc / ghi Excel. Thiết kế: docs/superpowers/specs/2026-11-23-title-dong-va-chinh-ta-design.md.
"""
import os
import re
import json
import unicodedata

from scope_filter import match_keyword

MASTER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "master_data")
RULES_PATH = os.environ.get("SWIND_TITLE_ROW_RULES") or os.path.join(MASTER_DIR, "title_row_rules.json")
_CACHE = {}


def load_rules(path=None):
    """{ 'TR-01': rule, ..., '_all': data } — cache theo mtime."""
    path = path or RULES_PATH
    mtime = os.path.getmtime(path)
    c = _CACHE.get(path)
    if c and c[0] == mtime:
        return c[1]
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    rules = {r["id"].split("_", 1)[0]: r for r in data["quy_tac"]}
    rules["_all"] = data
    _CACHE[path] = (mtime, rules)
    return rules


def _norm(text):
    return unicodedata.normalize("NFC", str(text or "")).lower().strip()


def product_keywords(manufacturable_catalog, commercial_catalog):
    """Từ khóa loại hàng = keywords 2 catalog + TR-01."""
    kws = {_norm(k) for cat in (manufacturable_catalog or [], commercial_catalog or []) for it in cat for k in it.get("keywords", [])}
    kws |= {_norm(k) for k in load_rules()["TR-01"]["tu_khoa"]}
    # Mã viết tắt chuẩn Swind (TY-03.ma_chuan: msfd, mprd, sdg...) cũng là loại hàng (E2E 2026-11-23, NOXH 'MSFD 1000x200')
    import typo_normalizer
    kws |= {_norm(k) for k in typo_normalizer.load_rules()["TY-03"]["ma_chuan"]}
    return frozenset(k for k in kws if k)


def product_keywords_from_files():
    out = []
    for f in ("manufacturable_catalog.json", "commercial_catalog.json"):
        with open(os.path.join(MASTER_DIR, f), "r", encoding="utf-8") as fh:
            out.append(json.load(fh))
    return product_keywords(*out)


def _has_any(words, text):
    return any(match_keyword(w, text) for w in words)


def title_role(title_lower, kws):
    t = re.sub(r'^[\divxlc]+(?:\.\d+)*[.)]?\s+', '', _norm(title_lower))
    if not t or t == "sản phẩm":
        return "NONE"
    if _has_any(kws, t):
        return "LOAI_HANG"
    params = [_norm(w) for w in load_rules()["TR-02"]["tu_khoa"]]
    if _has_any(params, t) or re.search(r'(?<![a-z])ei\s*\d{2,3}\b', t):
        return "PHU_KIEN"
    return "HANG_MUC"


def row_role(own_text_lower, kws, aux_text_lower=""):
    """Vai Dòng theo chữ ô Tên; `aux_text_lower` (Ghi chú / Spec / Model) chỉ dùng để chứng minh DU_LOAI —
    chữ lạ trong Ghi chú (mã riêng của khách) không làm dòng thành KHONG_NHAN_RA."""
    t = _norm(own_text_lower)
    if _has_any(kws, t) or (aux_text_lower and _has_any(kws, _norm(aux_text_lower))):
        return "DU_LOAI"
    R = load_rules()
    r3 = R["TR-03"]
    t = t.replace("×", "x")
    # Bỏ chữ trong danh sách TRƯỚC (mẫu mã ký hiệu có thể nuốt nửa chữ: '600x400/dquạt' -> 'uạt'), rồi tới mẫu
    skip = sorted({_norm(w) for w in r3["tu_bo"] + R["TR-02"]["tu_khoa"]}, key=len, reverse=True)
    for w in skip:
        t = re.sub(r'(?<![^\W\d_])' + re.escape(w) + r'(?![^\W\d_])', ' ', t)
    t = re.sub(r'\+\s*[a-z]{1,2}\b', ' ', t)
    for pat in r3["mau_bo"]:
        t = re.sub(pat, ' ', t)
    return "KHONG_NHAN_RA" if re.findall(r'[^\W\d_]+', t) else "CHI_KT"


def decide(t_role, r_role, category, title_wins=False):
    """Ô HỎI LẠI của TR-04 → 'TITLE_ROW_ASK' / 'TITLE_UNCLEAR'; ô khác → None (giữ hành vi hiện tại)."""
    r4 = load_rules()["TR-04"]
    if title_wins or category not in r4["nhom_ap_dung"]:
        return None
    for o in r4["o_hoi_lai"]:
        if o["title"] == t_role and o["dong"] == r_role:
            return o["ket_qua"]
    return None
