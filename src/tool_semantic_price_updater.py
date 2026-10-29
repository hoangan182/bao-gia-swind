import os
import sys
import glob
import json
from datetime import datetime
from difflib import SequenceMatcher

def resolve_path(rel_path):
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel_path)

TECH_DB = resolve_path("data/master_data/master_database_tech.json")
COM_TECH_DB = resolve_path("data/master_data/master_commercial_tech.json")
PRICES_DIR = resolve_path("data/master_data/prices")
PRICE_DB_FALLBACK = resolve_path("data/master_data/master_database_price.json")
COM_PRICE_DB_FALLBACK = resolve_path("data/master_data/master_commercial_price.json")

def get_latest_file(directory, prefix, fallback):
    pattern = os.path.join(directory, f"{prefix}*.json")
    files = glob.glob(pattern)
    if not files:
        return fallback
    files.sort()
    return files[-1]

def similar(a, b):
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()

def find_best_match(keyword, tech_records):
    best_match = None
    best_score = 0.0
    for item in tech_records:
        name = item.get("Name", "")
        mat_id = item.get("MAT_ID", "")
        # Semantic mapping score (simple string similarity for now)
        score_name = similar(keyword, name)
        score_id = similar(keyword, mat_id)
        score = max(score_name, score_id)
        
        # Check if keyword is exactly in the name
        if keyword.lower() in name.lower() or keyword.lower() in mat_id.lower():
            score += 0.3 # Boost score for exact substring match
            
        if score > best_score:
            best_score = score
            best_match = item
    return best_match, best_score

def update_price(keyword, new_price, auto_confirm=False):
    new_price = float(new_price)
    print(f"\n[NLP Price Guard] Tìm kiếm vật tư khớp với: '{keyword}'...")
    
    # Load all tech records
    with open(TECH_DB, "r", encoding="utf-8") as f:
        db_tech = json.load(f)
    com_tech = []
    if os.path.exists(COM_TECH_DB):
        with open(COM_TECH_DB, "r", encoding="utf-8") as f:
            com_tech = json.load(f)
            
    # Find match in both DBs
    db_match, db_score = find_best_match(keyword, db_tech)
    com_match, com_score = find_best_match(keyword, com_tech)
    
    # Determine the absolute best match
    is_commercial = False
    best_match = db_match
    best_score = db_score
    
    if com_score > db_score:
        best_match = com_match
        best_score = com_score
        is_commercial = True
        
    # An toàn: Ngưỡng tối thiểu phải đạt 0.65 để tránh gán nhầm
    if best_score < 0.65 or not best_match:
        print(f"\n[TỪ CHỐI CẬP NHẬT] Không tìm thấy vật tư nào đủ độ tin cậy khớp với '{keyword}'.")
        print(f" -> Độ khớp cao nhất chỉ đạt {best_score * 100:.1f}% (Yêu cầu an toàn >= 65.0%).")
        if best_match:
            print(f" -> Mặt hàng gần nhất là: [{best_match['MAT_ID']}] - {best_match.get('Name', '')}")
        print(" -> Để đảm bảo an toàn, vui lòng cung cấp tên đầy đủ hoặc mã MAT_ID chính xác hơn.")
        return False
        
    mat_id = best_match['MAT_ID']
    mat_name = best_match.get('Name', '')
    
    # Load the corresponding price DB
    if is_commercial:
        prefix = "master_commercial_price_"
        fallback = COM_PRICE_DB_FALLBACK
    else:
        prefix = "master_database_price_"
        fallback = PRICE_DB_FALLBACK
        
    latest_price_file = get_latest_file(PRICES_DIR, prefix, fallback)
    with open(latest_price_file, "r", encoding="utf-8") as f:
        price_data = json.load(f)
        
    old_price = 0.0
    for item in price_data:
        if item["MAT_ID"] == mat_id:
            old_price = float(item.get("Price", 0))
            break

    print("\n" + "=" * 65)
    print("🔍 KẾT QUẢ ĐỐI SOÁT VẬT TƯ (TRƯỚC KHI CẬP NHẬT):")
    print("=" * 65)
    print(f"  • Từ khóa đầu vào   : '{keyword}'")
    print(f"  • Mã vật tư khớp     : [{mat_id}]")
    print(f"  • Tên quy cách       : {mat_name}")
    print(f"  • Cơ sở dữ liệu      : {'Hàng Thương Mại' if is_commercial else 'Vật Tư Sản Xuất'}")
    print(f"  • Độ tin cậy khớp    : {best_score * 100:.1f}% (Đạt tiêu chuẩn an toàn)")
    print(f"  • Đơn giá hiện tại   : {old_price:,.0f} VNĐ")
    print(f"  • Đơn giá cập nhật   : {new_price:,.0f} VNĐ")
    print("=" * 65)
    
    # Human Confirmation Gate
    if not auto_confirm:
        try:
            choice = input("\n>> Bạn có chắc chắn muốn lưu mức giá mới này vào Audit DB? [Y/N]: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            choice = "N"
            
        if choice != "Y":
            print("\n[HỦY BỎ] Thao tác cập nhật giá đã bị hủy bởi người dùng.")
            return False

    # Thực hiện cập nhật
    updated = False
    for item in price_data:
        if item["MAT_ID"] == mat_id:
            item["Price"] = new_price
            updated = True
            break
            
    if not updated:
        price_data.append({"MAT_ID": mat_id, "Price": new_price})
        
    # Lưu file Audit mới (Append-only)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    if not os.path.exists(PRICES_DIR):
        os.makedirs(PRICES_DIR, exist_ok=True)
    new_price_file = os.path.join(PRICES_DIR, f"{prefix}{timestamp}.json")
    
    with open(new_price_file, "w", encoding="utf-8") as f:
        json.dump(price_data, f, indent=4, ensure_ascii=False)
        
    print(f"\n[THÀNH CÔNG] Đã lưu mức giá mới {new_price:,.0f} VNĐ cho mã [{mat_id}].")
    print(f"  -> File gốc bảo toàn: {os.path.basename(latest_price_file)}")
    print(f"  -> Sinh file Audit mới tại: {new_price_file}")
    return True

PRICING_CONSTANTS_DB = resolve_path("data/master_data/pricing_constants.json")


def _flatten(node, prefix=""):
    for k, v in node.items():
        if k.startswith("_"):
            continue
        key = f"{prefix}.{k}" if prefix else k
        if isinstance(v, dict):
            yield from _flatten(v, key)
        else:
            yield key, v


def list_pricing_constants(prefix=""):
    with open(PRICING_CONSTANTS_DB, "r", encoding="utf-8") as f:
        data = json.load(f)
    for key, val in _flatten(data):
        if key.startswith(prefix):
            print(f"  {key:<60} {val:>14,.4g}" if isinstance(val, float) and val < 100 else f"  {key:<60} {val:>14,.0f}")


def update_pricing_constant(key, new_value, auto_confirm=False):
    """
    Cập nhật 1 hằng số công thức xưởng trong pricing_constants.json (VD: 'van.ton_m2.bac_lon').
    Lưu bản sao file cũ vào data/master_data/prices/pricing_constants_<timestamp>.json (Audit trail).
    """
    new_value = float(new_value)
    with open(PRICING_CONSTANTS_DB, "r", encoding="utf-8") as f:
        data = json.load(f)
    node = data
    parts = key.split(".")
    for part in parts[:-1]:
        if not isinstance(node, dict) or part not in node:
            node = None
            break
        node = node[part]
    if not isinstance(node, dict) or parts[-1] not in node or isinstance(node[parts[-1]], dict):
        print(f"[TỪ CHỐI] Không tìm thấy hằng số '{key}'. Dùng --list-constants <tiền_tố> để tra cứu khóa đúng.")
        return False
    old_value = node[parts[-1]]
    print(f"  • Hằng số : {key}\n  • Hiện tại: {old_value:,.4g}\n  • Mới     : {new_value:,.4g}")
    if not auto_confirm:
        try:
            choice = input(">> Xác nhận cập nhật? [Y/N]: ").strip().upper()
        except (EOFError, KeyboardInterrupt):
            choice = "N"
        if choice != "Y":
            print("[HỦY BỎ]")
            return False
    os.makedirs(PRICES_DIR, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup = os.path.join(PRICES_DIR, f"pricing_constants_{timestamp}.json")
    with open(backup, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    node[parts[-1]] = new_value
    data["_cap_nhat"] = datetime.now().strftime("%Y-%m-%d")
    with open(PRICING_CONSTANTS_DB, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    print(f"[THÀNH CÔNG] {key}: {old_value:,.4g} -> {new_value:,.4g} | Bản cũ lưu tại {backup}")
    print("  -> Chạy lại: ./venv/bin/python src/swind_item_inspector.py --self-test  (cập nhật baseline nếu thay đổi đã được duyệt)")
    return True


if __name__ == "__main__":
    auto_yes = "--yes" in sys.argv or "-y" in sys.argv
    if "--list-constants" in sys.argv:
        idx = sys.argv.index("--list-constants")
        list_pricing_constants(sys.argv[idx + 1] if len(sys.argv) > idx + 1 and not sys.argv[idx + 1].startswith("-") else "")
        sys.exit(0)
    if "--constant" in sys.argv:
        idx = sys.argv.index("--constant")
        ok = update_pricing_constant(sys.argv[idx + 1], sys.argv[idx + 2], auto_confirm=auto_yes)
        sys.exit(0 if ok else 1)
    if len(sys.argv) < 3:
        print("Usage: python tool_semantic_price_updater.py <keyword> <new_price> [--yes]")
        print("       python tool_semantic_price_updater.py --constant <khóa> <giá_trị> [--yes]   (hằng số công thức xưởng)")
        print("       python tool_semantic_price_updater.py --list-constants [tiền_tố]          (VD: van.ton_m2)")
        sys.exit(1)
        
    keyword = sys.argv[1]
    new_price = sys.argv[2]
    update_price(keyword, new_price, auto_confirm=auto_yes)
