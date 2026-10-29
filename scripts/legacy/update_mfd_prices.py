import json
import os

db_path = "data/master_data/master_database_price.json"
if os.path.exists(db_path):
    with open(db_path, "r", encoding="utf-8") as f:
        prices = json.load(f)
        
    # Thêm giá Tôn 1.15 (từ file 2026: 22400 đ/kg)
    prices.append({
        "MAT_ID": "MAT-STEEL-HOA_SEN-1.15",
        "Price": 22400,
        "Source": "Bang_Tinh_Gia_Swind_Chuan_2026",
        "Unit": "kg"
    })
    
    # Thêm giá Motor dập lửa (từ file 2026: 4.200.000 đ/cái)
    prices.append({
        "MAT_ID": "MAT-ACTUATOR-BELIMO-BFN24",
        "Price": 4200000,
        "Source": "Bang_Tinh_Gia_Swind_Chuan_2026",
        "Unit": "cái"
    })
    
    # Tạm tính giá Bọc cách nhiệt MGO (Tiêu chuẩn EI) khoảng 300,000 đ/m2
    prices.append({
        "MAT_ID": "MAT-INSULATION-EI-DAMPER",
        "Price": 300000,
        "Source": "Bang_Tinh_Gia_Swind_Chuan_2026_Estimated",
        "Unit": "m2"
    })

    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(prices, f, ensure_ascii=False, indent=4)
        
    print("Đã cập nhật thành công 3 vật tư vào Database!")
