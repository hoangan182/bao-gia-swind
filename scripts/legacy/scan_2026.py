import pandas as pd
import sys

import glob
file_matches = glob.glob("*chua*n 2026.xls*")
file_path = file_matches[0] if file_matches else "BẢNG TÍNH GIÁ SWIND  chuẩn 2026.xls"
try:
    xl = pd.ExcelFile(file_path)
    print("Sheets:", xl.sheet_names)
    
    for sheet in xl.sheet_names:
        print(f"\n--- Sheet: {sheet} ---")
        df = pd.read_excel(xl, sheet_name=sheet)
        
        # Search for Belimo or BFN
        mask_bfn = df.apply(lambda row: row.astype(str).str.contains('BFN|Belimo|MGO|chống cháy|1.15|động cơ', case=False, na=False).any(), axis=1)
        found = df[mask_bfn]
        if not found.empty:
            print(f"Found {len(found)} rows matching criteria:")
            print(found.head(10).to_string(index=False))
except Exception as e:
    print(f"Error reading file: {e}")
