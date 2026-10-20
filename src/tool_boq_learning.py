import sys
import os
import json

def resolve_path(rel_path):
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    return os.path.join(base, rel_path)

if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Usage: python tool_boq_learning.py <item_name> <category>")
        sys.exit(1)
        
    name = sys.argv[1].lower().strip()
    category = sys.argv[2].upper().strip()
    
    path = resolve_path("data/master_data/boq_keyword_learning.json")
    data = {}
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            
    data[name] = category
    
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        
    print(f"[THÀNH CÔNG] Đã dạy AI: '{name}' -> '{category}'")
