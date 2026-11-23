"""Kho ghi nhớ quyết định theo dự án cho luồng Agent 10 / trợ lý 'bao-gia-tu-bg-cu' (User chốt 2026-11-23, dự án 261123_HH3_RFQ).

Lưu ở data/old_quote_memory/<project_key>.json (trong .gitignore — dữ liệu dự án), KHÔNG ở output/<Dự án>/ vì runner
xoá thư mục đó mỗi lần chạy. Chỉ lưu quyết định của User; dòng tự quyết (khớp chắc chắn / không có) được tính lại mỗi lần.
"""
import json
import os
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MEMORY_DIR = os.path.join(BASE_DIR, "data", "old_quote_memory")


def _path(project_key, base_dir):
    return os.path.join(base_dir, f"{project_key}.json")


def load_memory(project_key, base_dir=MEMORY_DIR):
    p = _path(project_key, base_dir)
    if not os.path.exists(p):
        return {}
    try:
        with open(p, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError) as ex:
        print(f"⚠️ [GHI NHỚ] File {p} hỏng ({ex}) — bỏ qua, không ghi đè")
        return {"_corrupt": True}


def _ref_entry(entries, ref):
    for e in entries:
        if f"{e['sheet']}!{e['row']}" == ref:
            return e
    return None


def apply_memory(plan_rows, memory, entries, old_quote):
    """Gán decided_by='memory' cho dòng đã có quyết định còn hợp lệ; dòng thay đổi -> giữ None + ghi lý do."""
    saved = (memory or {}).get("rows") or {}
    mq = (memory or {}).get("old_quote") or {}
    same_file = mq.get("path") == old_quote.get("path") and mq.get("mtime") == old_quote.get("mtime")
    for row in plan_rows:
        d = saved.get(row["key"])
        if not d:
            continue
        why = None
        if d.get("action") == "carry":
            e = _ref_entry(entries, d.get("ref"))
            if not same_file:
                why = "đổi file BG cũ"
            elif e is None:
                why = "dòng BG cũ không còn"
            elif e["price"] != d.get("price_at_decision"):
                why = f"giá BG cũ đổi ({d.get('price_at_decision'):,} -> {e['price']:,})"
        if why:
            row["reason"] = ((row.get("reason") or "") + "; " if row.get("reason") else "") + f"thay đổi so với lần trước: {why}"
            continue
        row["decided_by"] = "memory"
        row["decision"] = {k: d[k] for k in ("action", "ref", "neck") if k in d}


def save_memory(project_key, memory, decisions, plan, run_totals, base_dir=MEMORY_DIR):
    """Gộp quyết định User (decided_by user/memory) vào kho, ghi nguyên tử. Không ghi khi kho đang hỏng."""
    p = _path(project_key, base_dir)
    if (memory or {}).get("_corrupt"):
        print(f"⚠️ [GHI NHỚ] Không ghi đè file hỏng {p} — sửa / xoá file rồi chạy lại để lưu quyết định")
        return p
    now = datetime.now().isoformat(timespec="seconds")
    mem = dict(memory or {})
    rows = dict(mem.get("rows") or {})
    who = {r["key"]: r.get("decided_by") for r in plan.get("rows", [])}
    for key, d in (decisions.get("rows") or {}).items():
        if who.get(key) not in ("user", "memory"):
            continue
        prev = rows.get(key) or {}
        rec = {"action": d.get("action"), "ref": d.get("ref"), "price_at_decision": d.get("price"), "neck": bool(d.get("neck")),
               "decided_at": prev.get("decided_at") if who.get(key) == "memory" and prev else now, "source_run": plan.get("boq")}
        rows[key] = {k: v for k, v in rec.items() if v is not None}
    mem.update({"project_key": project_key, "display_name": mem.get("display_name") or project_key,
                "old_quote": plan.get("old_quote") or mem.get("old_quote"), "rows": rows})
    if decisions.get("options"):
        mem["options"] = decisions["options"]
    mem.setdefault("runs", []).append({"at": now, "boq": plan.get("boq"), "totals": run_totals})
    os.makedirs(base_dir, exist_ok=True)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(mem, f, ensure_ascii=False, indent=1)
    os.replace(tmp, p)
    return p
