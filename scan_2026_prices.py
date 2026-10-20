import pandas as pd

file_path = "/Users/hoangan/work/swind/BẢNG TÍNH GIÁ SWIND  chuẩn 2026.xls"
try:
    xl = pd.ExcelFile(file_path)
    df_ton = pd.read_excel(xl, sheet_name="Vat tu tôn")
    
    print("--- GIÁ VẬT TƯ TÔN ---")
    for r in range(len(df_ton)):
        row = df_ton.iloc[r]
        for c in range(len(row)):
            val = str(row.iloc[c])
            if "1.15" in val or "Motor" in val or "4200" in val or "MGO" in val:
                print(f"Row {r}: {val} - {list(row.dropna().values)[:5]}")
except Exception as e:
    print(f"Error: {e}")
