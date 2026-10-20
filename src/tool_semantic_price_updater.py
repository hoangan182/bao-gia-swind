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

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python tool_semantic_price_updater.py <keyword> <new_price> [--yes]")
        sys.exit(1)
        
    keyword = sys.argv[1]
    new_price = sys.argv[2]
    auto_yes = "--yes" in sys.argv or "-y" in sys.argv
    update_price(keyword, new_price, auto_confirm=auto_yes)
