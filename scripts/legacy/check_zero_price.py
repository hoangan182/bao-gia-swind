import json

with open("data/master_data/master_database_price.json", "r") as f:
    prices = json.load(f)

zero_prices = [p["MAT_ID"] for p in prices if p.get("Price", 0) == 0]
print(f"Có {len(zero_prices)} mã vật tư đang có giá = 0.")
if zero_prices:
    print("Ví dụ 5 mã:", zero_prices[:5])
