"""Bảng 'đã hiểu thế nào': mỗi dòng BOQ mang item["decisions"] ghi hệ thống hiểu dòng ra sao
(loại hàng / kiểu / model), dựa trên chữ nào, và có chắc không. Chỉ dùng thư viện chuẩn."""
import json
import os

import default_policy

SOURCES = ("TEN", "GHI_CHU", "TITLE", "MODEL", "CO_USER", "HOC_MAY", "MAC_DINH")
FIELDS = ("loai_hang", "kieu", "model")

TEXT_SOURCE = {
    "title_low": "TITLE",
    "note_boq_low": "GHI_CHU",
    "note_model_low": "GHI_CHU",
    "raw_name_low": "TEN",
    "raw_name": "TEN",
    "primary_diff_search": "TEN",
    "ten_model": "TEN",
    "raw_search": "TEN",
    "full_search": "TITLE",
    "combined_search": "TITLE",
    "unaccent_search": "TITLE",
    "blade_search": "TEN",
}


def record(item, field, value, source, rule, sure=True):
    """Ghi/thay quyết định cho `field` (thay bản cũ cùng field)."""
    srcs = [source] if isinstance(source, str) else list(source)
    uniq = []
    for s in srcs:
        if s not in SOURCES:
            raise ValueError(f"Nguồn không hợp lệ: {s!r} (hợp lệ: {SOURCES})")
        if s not in uniq:
            uniq.append(s)
    rec = {"truong": field, "gia_tri": value, "nguon": uniq, "rule": rule, "chac": bool(sure)}
    decs = [d for d in (item.get("decisions") or []) if d.get("truong") != field]
    decs.append(rec)
    item["decisions"] = decs


def confirm_by_user(item):
    """--override ok=1 (item["default_confirmed"], Việc 3 2026-11-25): quyết định mặc định / chưa chắc được User duyệt
    → thêm nguồn CO_USER, chac=True, giữ nguyên rule + giá trị (bảng 'đã hiểu thế nào' không còn liệt kê dòng)."""
    if not item.get("default_confirmed"):
        return
    for d in item.get("decisions") or []:
        if "MAC_DINH" in d.get("nguon", []) or not d.get("chac", True):
            if "CO_USER" not in d["nguon"]:
                d["nguon"] = list(d["nguon"]) + ["CO_USER"]
            d["chac"] = True


def _qty(item):
    try:
        return float(item.get("qty") or 0)
    except (TypeError, ValueError):
        return 0.0


def _settled_rules():
    return {r["ap_cho"] for k, r in default_policy.load_rules().items() if k != "_all" and r["xu_ly"] == "GIU"}


def _is_settled_default(d):
    """Quyết định MAC_DINH mà bảng default_rules.json xếp GIU (mặc định đã chốt) → không cần User xem."""
    return d.get("rule") in _settled_rules()


def review_rows(all_items):
    out = []
    for it in all_items:
        decs = it.get("decisions") or []
        if not decs or _qty(it) <= 0:
            continue
        if it.get("skip") or it.get("is_skipped"):
            continue
        if not any(("MAC_DINH" in d.get("nguon", []) or not d.get("chac", True)) and not _is_settled_default(d)
                   and "CO_USER" not in d.get("nguon", [])  # User đã duyệt (--override ok=1)
                   for d in decs):
            continue
        out.append({
            "sheet": it.get("source_sheet"),
            "row": it.get("source_row"),
            "raw_name": it.get("raw_name") or it.get("name"),
            "decisions": decs,
        })
    return out


def _fmt_decs(decs):
    return "; ".join(f"{d['truong']}={d['gia_tri']} ← {'+'.join(d['nguon'])} ({d['rule']})" for d in decs)


def console_lines(all_items, limit=15):
    rows = review_rows(all_items)
    lines = []
    for r in rows[:limit]:
        decs = r["decisions"]
        short = "; ".join(f"{d['truong'].replace('loai_hang', 'loai').replace('kieu', 'kieu')}={d['gia_tri']}"
                          f" ← {'+'.join(d['nguon'])} ({d['rule']})" for d in decs)
        lines.append(f"R{r['row']} [{r['sheet']}] '{r['raw_name']}' → {short}")
    if len(rows) > limit:
        lines.append(f"... và {len(rows) - limit} dòng nữa — xem DECISION_REVIEW.md")
    return lines


def explain(item):
    return "\n".join(
        f"{d['truong']} = {d['gia_tri']}  ← {'+'.join(d['nguon'])} ({d['rule']})"
        + ("" if d.get("chac", True) else "  [cần xác nhận]")
        for d in item.get("decisions") or []
    )


def _cell(s):
    return str(s if s is not None else "").replace("|", "\\|").replace("\n", " ")


def write_report(all_items, out_dir):
    os.makedirs(out_dir, exist_ok=True)
    traced = [{
        "sheet": it.get("source_sheet"), "row": it.get("source_row"),
        "raw_name": it.get("raw_name") or it.get("name"), "qty": it.get("qty"),
        "decisions": it["decisions"],
    } for it in all_items if it.get("decisions")]
    jp = os.path.join(out_dir, "DECISION_TRACE.json")
    with open(jp, "w", encoding="utf-8") as f:
        json.dump(traced, f, ensure_ascii=False, indent=2)

    rows = review_rows(all_items)
    multi = len({r["sheet"] for r in rows}) > 1
    md = ["# Dòng hệ thống hiểu theo mặc định / cần xác nhận", "",
          "| Dòng | BOQ ghi | Hiểu là | Căn cứ | Độ chắc |", "| --- | --- | --- | --- | --- |"]
    for r in rows:
        ref = f"{r['sheet']}!R{r['row']}" if multi else f"R{r['row']}"
        hieu = "; ".join(f"{d['truong']}={d['gia_tri']}" for d in r["decisions"])
        cancu = "; ".join(f"{'+'.join(d['nguon'])} ({d['rule']})" for d in r["decisions"])
        chac = "chắc chắn" if all(d.get("chac", True) for d in r["decisions"]) else "cần xác nhận"
        md.append("| " + " | ".join(_cell(x) for x in (ref, r["raw_name"], hieu, cancu, chac)) + " |")
    mp = os.path.join(out_dir, "DECISION_REVIEW.md")
    with open(mp, "w", encoding="utf-8") as f:
        f.write("\n".join(md) + "\n")
    return jp, mp
