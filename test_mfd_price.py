import sys
sys.path.append('src')
from swind_bom_engine import SwindBOMEngine
import json

res = SwindBOMEngine.calculate_damper_bom("TEST-01", "MFD", 500, 500, brand="Hoa_Sen")
components = res["components"]

with open("data/master_data/master_database_price.json", "r", encoding="utf-8") as f:
    prices = json.load(f)
    
price_map = {p["MAT_ID"]: p["Price"] for p in prices}

print(f"--- BÓC TÁCH GIÁ VAN MFD 500x500 ---")
total_price = 0
for comp in components:
    qty = comp.get("calc_qty", 0)
    mat_id = comp.get("mat_id", "")
    unit_price = price_map.get(mat_id, 0)
    cost = qty * unit_price
    total_price += cost
    print(f"- {comp['name']} (Mã: {mat_id}): {qty:.2f} {comp['unit']} x {unit_price:,} đ = {cost:,.0f} đ")

print(f"\n=> TỔNG GIÁ VẬT TƯ (CHƯA NHÂN CÔNG): {total_price:,.0f} đ")
