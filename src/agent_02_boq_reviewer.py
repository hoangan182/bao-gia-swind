import sys
import os
import json
from difflib import SequenceMatcher
from swind_boq_parser import SwindBOQParser


def resolve_path(rel_path):
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel_path)


def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def get_catalogs():
    learning_path = resolve_path("data/master_data/boq_keyword_learning.json")
    learned_map = {}
    if os.path.exists(learning_path):
        with open(learning_path, "r", encoding="utf-8") as f:
            learned_map = json.load(f)

    with open(resolve_path("data/master_data/commercial_catalog.json"), "r") as f:
        com_cat = json.load(f)
    with open(resolve_path("data/master_data/manufacturable_catalog.json"), "r") as f:
        mfg_cat = json.load(f)

    all_known_cats = [(c["name"], c.get("mapping_category", "THUONG_MAI")) for c in com_cat + mfg_cat]
    return learned_map, all_known_cats


def find_ambiguous_items(items):
    learned_map, all_known_cats = get_catalogs()
    ambiguous_items = []

    for item in items:
        name = item["name"].strip()
        raw_name = item.get("raw_name", name).strip()
        if raw_name.lower() in learned_map:
            item["category"] = learned_map[raw_name.lower()]
            continue
        if name.lower() in learned_map:
            item["category"] = learned_map[name.lower()]
            continue

        cat = item["category"]
        if cat == "KHAC":
            best_match_name = ""
            best_match_cat = ""
            best_score = 0.0

            for kname, kcat in all_known_cats:
                score = max(similar(raw_name, kname), similar(name, kname))
                if score > best_score:
                    best_score = score
                    best_match_name = kname
                    best_match_cat = kcat

            item["suggested_cat"] = best_match_cat if best_score > 0.4 else None
            item["suggested_name"] = best_match_name if best_score > 0.4 else None
            item["suggested_score"] = best_score
            ambiguous_items.append(item)

    return ambiguous_items


LEARNING_PATH = "data/master_data/boq_keyword_learning.json"
QUEUE_PATH = "data/master_data/pending_approval_queue.json"
AUTO_APPLY_MIN_SCORE = 0.6


def _load_json(rel_path, default):
    path = resolve_path(rel_path)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return default
    return default


def _write_json(rel_path, data, indent=2):
    with open(resolve_path(rel_path), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def save_learned_keyword(name, category, project_name="General", approved=False, score=None):
    """
    Two-Tier Learning:
    - approved=True  (kỹ sư chọn tay trong phiên HITL): ghi thẳng vào từ điển sống boq_keyword_learning.json.
    - approved=False (gợi ý tự động / auto-accept): CHỈ đưa vào hàng chờ pending_approval_queue.json,
      không làm thay đổi từ điển cho tới khi được duyệt bằng `agent_02_boq_reviewer.py --approve-pending`.
    """
    clean_key = name.lower().strip()
    if approved:
        data = _load_json(LEARNING_PATH, {})
        data[clean_key] = category
        _write_json(LEARNING_PATH, data, indent=4)

    queue = _load_json(QUEUE_PATH, {"pending_proposals": []})
    queue.setdefault("pending_proposals", [])
    status = "APPROVED" if approved else "PENDING_APPROVAL"
    existing = next((p for p in queue["pending_proposals"] if p.get("raw_name") == clean_key and p.get("proposed_id") == category), None)
    if existing is None:
        queue["pending_proposals"].append({
            "raw_name": clean_key,
            "proposed_id": category,
            "standard_name": category,
            "project": project_name,
            "proposed_by": "Engineer" if approved else "AutoSuggest",
            "score": round(score, 3) if score is not None else None,
            "status": status
        })
    elif approved:
        existing["status"] = "APPROVED"
    _write_json(QUEUE_PATH, queue)


def approve_pending_keywords(approve_all=False, interactive=True):
    """Duyệt hàng chờ từ khóa tự học -> chuyển các đề xuất được chấp thuận vào từ điển sống."""
    queue = _load_json(QUEUE_PATH, {"pending_proposals": []})
    pending = [p for p in queue.get("pending_proposals", []) if p.get("status") == "PENDING_APPROVAL"]
    if not pending:
        print("[Agent 02] Hàng chờ duyệt trống.")
        return 0
    data = _load_json(LEARNING_PATH, {})
    n_ok = 0
    for idx, prop in enumerate(pending, 1):
        label = f"[{idx}/{len(pending)}] '{prop['raw_name']}' -> [{prop['proposed_id']}] (score={prop.get('score')}, dự án={prop.get('project')})"
        if approve_all:
            choice = "Y"
        elif interactive:
            try:
                choice = input(f"  {label}  Duyệt? [Y/n/r=từ chối]: ").strip().upper() or "Y"
            except (EOFError, KeyboardInterrupt):
                break
        else:
            print(f"  {label}")
            continue
        if choice == "Y":
            data[prop["raw_name"]] = prop["proposed_id"]
            prop["status"] = "APPROVED"
            n_ok += 1
        elif choice == "R":
            prop["status"] = "REJECTED"
    if not approve_all and not interactive:
        return 0
    _write_json(LEARNING_PATH, data, indent=4)
    _write_json(QUEUE_PATH, queue)
    print(f"[Agent 02] Đã duyệt {n_ok} từ khóa vào từ điển sống.")
    return n_ok


def apply_suggestions_non_interactive(ambiguous_items, auto_accept=False, project_name="General"):
    """
    Chế độ headless: chỉ áp gợi ý có độ tin cậy >= AUTO_APPLY_MIN_SCORE cho LẦN CHẠY NÀY khi có --auto-accept,
    đồng thời đưa vào hàng chờ duyệt (không ghi từ điển sống). Trả về danh sách mặt hàng còn chưa phân loại.
    """
    unresolved = []
    for item in ambiguous_items:
        sug_cat = item.get("suggested_cat")
        score = float(item.get("suggested_score") or 0)
        raw_name = item.get("raw_name", item.get("name", ""))
        if auto_accept and sug_cat and score >= AUTO_APPLY_MIN_SCORE:
            item["category"] = sug_cat
            save_learned_keyword(raw_name, sug_cat, project_name=project_name, approved=False, score=score)
            print(f"  -> [Auto-accept] '{raw_name}' -> [{sug_cat}] (độ tin cậy {score*100:.0f}%, đã đưa vào hàng chờ duyệt)")
        else:
            unresolved.append(item)
    for item in unresolved:
        sug = f" | Gợi ý: '{item.get('suggested_name')}' [{item.get('suggested_cat')}] {float(item.get('suggested_score') or 0)*100:.0f}%" if item.get("suggested_cat") else ""
        print(f"  ⚠️ [Chưa phân loại - giữ KHAC] R{item.get('source_row')}: '{item.get('raw_name', item.get('name'))}' (KL={item.get('qty')} {item.get('unit')}){sug}")
    return unresolved


def resolve_ambiguous_interactive(ambiguous_items, auto_accept_all=False):
    if not ambiguous_items:
        return True

    print("\n" + "=" * 70)
    print(f"🤖 [Agent 02 - BOQ Reviewer] Cần xác nhận {len(ambiguous_items)} mặt hàng chưa rõ ràng (HITL):")
    print("=" * 70)

    cat_options = {
        "1": "ONG_GIO",
        "2": "CUA_GIO",
        "3": "VAN_GIO",
        "4": "THUONG_MAI",
        "5": "ONG_MEM",
        "6": "CANVAS",
        "7": "TIEU_AM",
        "8": "KHAC"
    }

    accept_all = auto_accept_all
    accept_all_thuong_mai = False

    for idx, item in enumerate(ambiguous_items, 1):
        name = item["name"]
        raw_name = item.get("raw_name", name)
        qty = item["qty"]
        unit = item["unit"]
        sug_cat = item.get("suggested_cat")
        sug_name = item.get("suggested_name")
        score = item.get("suggested_score", 0.0)

        if accept_all_thuong_mai:
            item["category"] = "THUONG_MAI"
            save_learned_keyword(raw_name, "THUONG_MAI", approved=True)
            print(f"  [{idx}/{len(ambiguous_items)}] Tự động đẩy: '{name}' -> [THUONG_MAI]")
            continue

        if accept_all and sug_cat:
            item["category"] = sug_cat
            save_learned_keyword(raw_name, sug_cat, approved=False, score=score)
            print(f"  [{idx}/{len(ambiguous_items)}] Tự động áp gợi ý: '{name}' -> [{sug_cat}] (đưa vào hàng chờ duyệt)")
            continue

        print(f"\n  [{idx}/{len(ambiguous_items)}] Tên: '{name}' | Số lượng: {qty} {unit}")
        if sug_name and sug_cat:
            print(f"     🤖 AI Gợi ý: Có thể là '{sug_name}' -> Phân nhóm [{sug_cat}] (Độ tin cậy: {score*100:.1f}%)")
        else:
            print("     🤖 AI: Chưa tìm thấy gợi ý tương thích trong Master Catalog.")

        prompt = "     >> Chọn: [Enter/Y]: Đồng ý AI | [A]: Đồng ý TẤT CẢ AI | [T]: Tất cả còn lại -> THƯƠNG MẠI | [1:Ống, 2:Cửa, 3:Van, 4:Thương mại, S:Bỏ qua]: "
        try:
            choice = input(prompt).strip().upper()
        except (EOFError, KeyboardInterrupt):
            choice = "S"

        if choice in ["Y", ""] and sug_cat:
            chosen_cat = sug_cat
        elif choice == "A" and sug_cat:
            accept_all = True
            chosen_cat = sug_cat
        elif choice == "T":
            accept_all_thuong_mai = True
            chosen_cat = "THUONG_MAI"
        elif choice in cat_options:
            chosen_cat = cat_options[choice]
        elif choice == "S":
            chosen_cat = "KHAC"
        else:
            chosen_cat = sug_cat if sug_cat else "KHAC"

        item["category"] = chosen_cat
        if chosen_cat != "KHAC":
            save_learned_keyword(raw_name, chosen_cat, approved=True)
            print(f"     ✅ Đã cập nhật & học máy: '{raw_name}' -> [{chosen_cat}]")
        else:
            print("     ⚠️ Giữ nguyên nhóm 'KHAC' (Cần tra cứu giá/công thức sau).")

    print("\n[OK] Hoàn tất phiên rà soát BOQ (Agent 02).")
    return True


def run_reviewer(boq_file, sheet_name="DHKK", interactive=False):
    parser = SwindBOQParser(boq_file)
    items = parser.parse_sheet(sheet_name)
    ambiguous_items = find_ambiguous_items(items)

    if not ambiguous_items:
        print("\n[OK] Không có mặt hàng nào chưa rõ ràng. Bóc tách hoàn hảo.")
        return True

    if interactive:
        return resolve_ambiguous_interactive(ambiguous_items)

    print(f"\n[CẢNH BÁO] Phát hiện {len(ambiguous_items)} mặt hàng chưa rõ ràng (AMBIGUOUS):")
    for i, item in enumerate(ambiguous_items[:5]):
        suggestion = ""
        if item.get("suggested_name"):
            suggestion = f" -> 🤖 AI Gợi ý: Có thể là '{item['suggested_name']}' (Thuộc nhóm {item['suggested_cat']})?"
        print(f"  {i+1}. Tên: {item['name']} | Số lượng: {item['qty']} {item['unit']}{suggestion}")
    if len(ambiguous_items) > 5:
        print(f"  ... (Và {len(ambiguous_items) - 5} mặt hàng khác)")

    out_path = resolve_path("data/projects/temp_ambiguous.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(ambiguous_items, f, indent=4, ensure_ascii=False)

    print("\nĐể định nghĩa và phân loại chính xác, vui lòng chạy Master Runner hoặc cập nhật học máy.")
    return False


class Agent02_BOQReviewer:
    """
    Agent 02 - BOQ Reviewer & Two-Tier Semantic Learning (HITL)
    """
    find_ambiguous_items = staticmethod(find_ambiguous_items)
    resolve_ambiguous_interactive = staticmethod(resolve_ambiguous_interactive)
    save_learned_keyword = staticmethod(save_learned_keyword)
    approve_pending_keywords = staticmethod(approve_pending_keywords)
    apply_suggestions_non_interactive = staticmethod(apply_suggestions_non_interactive)
    run_reviewer = staticmethod(run_reviewer)


if __name__ == "__main__":
    if "--approve-pending" in sys.argv:
        # Duyệt hàng chờ từ khóa tự học: --approve-pending [--all | --list]
        approve_pending_keywords(approve_all="--all" in sys.argv, interactive="--list" not in sys.argv)
        sys.exit(0)
    if len(sys.argv) < 2:
        print("Usage: python agent_02_boq_reviewer.py <path_to_boq_excel> [--interactive]")
        print("       python agent_02_boq_reviewer.py --approve-pending [--all | --list]")
        sys.exit(1)
    is_interactive = "--interactive" in sys.argv
    success = run_reviewer(sys.argv[1], interactive=is_interactive)
    sys.exit(0 if success else 1)
