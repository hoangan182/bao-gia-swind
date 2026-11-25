"""
Chính sách MẶC ĐỊNH (default_policy) — chạy bảng `data/master_data/default_rules.json` (Việc 3, User chốt 2026-11-24).
Mặc định chưa chốt (BAO_VA_HOI) → vẫn báo giá, tô vàng Sheet BG + hỏi lại ở Kiểm soát cuối; mặc định đã chốt (GIU) → im lặng.
Chỉ đọc item["decisions"]; KHÔNG import decision_trace (decision_trace import module này).
"""
import os
import json

MASTER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "master_data")
RULES_PATH = os.environ.get("SWIND_DEFAULT_RULES") or os.path.join(MASTER_DIR, "default_rules.json")
_CACHE = {}


def load_rules(path=None):
    """{ 'MD-01': rule, ..., '_all': data } — cache theo mtime."""
    path = path or RULES_PATH
    mtime = os.path.getmtime(path)
    c = _CACHE.get(path)
    if c and c[0] == mtime:
        return c[1]
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    rules = {r["id"]: r for r in data["quy_tac"]}
    rules["_all"] = data
    _CACHE[path] = (mtime, rules)
    return rules


def _has_partner_price(item):
    # Runner chỉ giữ giá đối tác qua override_price (hàng không phải cửa/van); cửa/van có ref_price vẫn do Swind tính giá → vẫn hỏi.
    try:
        return float(item.get("override_price") or 0) > 0
    except (TypeError, ValueError):
        return False


# Nhãn tiếng Việt của mã loại hàng (hiện cho khách trên BG / Kiểm soát cuối); mã lạ giữ nguyên.
LOAI_HANG_VI = {
    "ONG_GIO": "ống gió / phụ kiện ống", "CUA_GIO": "cửa gió", "VAN_GIO": "van gió", "TIEU_AM": "tiêu âm",
    "CANVAS": "khớp nối mềm", "ONG_MEM": "ống mềm", "THUONG_MAI": "hàng thương mại", "KHAC": "chưa phân loại",
}


def _label(p):
    gt = p.get("gia_tri")
    return LOAI_HANG_VI.get(gt, gt) if p.get("truong") == "loai_hang" else gt


def policy(item):
    """Quyết định BAO_VA_HOI đầu tiên khớp `ap_cho` (và `chi_khi_gia_tri` nếu rule có);
    None nếu đã duyệt / không có / chỉ GIU / dòng có giá đối tác / hàng THUONG_MAI, KHAC (Swind không báo)."""
    if item.get("default_confirmed") or _has_partner_price(item):
        return None
    if item.get("category") in ("THUONG_MAI", "KHAC"):
        return None
    rules = [r for k, r in load_rules().items() if k != "_all"]
    for d in item.get("decisions") or []:
        for r in rules:
            if r["xu_ly"] == "BAO_VA_HOI" and d.get("rule") == r["ap_cho"]:
                if r.get("chi_khi_gia_tri") and d.get("gia_tri") not in r["chi_khi_gia_tri"]:
                    continue
                return {"id": r["id"], "xu_ly": r["xu_ly"], "truong": d.get("truong"), "gia_tri": d.get("gia_tri")}
    return None


def _where(item):
    return "%s!%s" % (item.get("source_sheet", ""), item.get("source_row", ""))


def _qty(item):
    try:
        return float(item.get("qty") or 0)
    except (TypeError, ValueError):
        return 0.0


def _where_gate(item):
    sh, row = item.get("source_sheet"), item.get("source_row", "")
    return "%s!R%s" % (sh, row) if sh else "R%s" % row


def bg_flag(item):
    if _qty(item) <= 0:
        return None
    p = policy(item)
    if not p:
        return None
    return ("⚠️ ĐÃ HIỂU THEO MẶC ĐỊNH: %s (BOQ không ghi rõ loại) — xin xác nhận "
            "(--override \"%s:ok=1\" hoặc loai=<mã>)" % (_label(p), _where(item)))


def gate_lines(all_items, limit=10):
    hits = []
    for it in all_items or []:
        if _qty(it) <= 0:
            continue
        p = policy(it)
        if p:
            hits.append((it, p))
    if not hits:
        return []
    ex = "; ".join("%s '%s'=%s" % (_where_gate(it), it.get("raw_name", ""), _label(p)) for it, p in hits[:limit])
    return ["[HỎI LẠI USER] %d dòng báo theo MẶC ĐỊNH (BOQ không ghi rõ loại) — tô vàng Sheet BG, xác nhận bằng "
            "--override \"<sheet>!<dòng>:ok=1\" hoặc loai=<mã>: %s" % (len(hits), ex)]
