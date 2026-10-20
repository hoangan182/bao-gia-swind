import json
import os

db_path = "data/master_data/master_database_price.json"
with open(db_path, "r", encoding="utf-8") as f:
    prices = json.load(f)
    
prices.append({
    "MAT_ID": "MAT-ACTUATOR-BELIMO-BF24",
    "Price": 5500000,
    "Source": "Bang_Tinh_Gia_Swind_Chuan_2026_Estimated",
    "Unit": "cái"
})

with open(db_path, "w", encoding="utf-8") as f:
    json.dump(prices, f, ensure_ascii=False, indent=4)
