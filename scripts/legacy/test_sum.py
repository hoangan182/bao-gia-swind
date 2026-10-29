import pandas as pd
import sys

def sum_sheet00(file_path):
    df = pd.read_excel(file_path, sheet_name="00. Tổng Hợp BOQ")
    col = [c for c in df.columns if "Thành" in c or "Total" in c or "Price" in c or "Giá" in c]
    if col:
        return df[col[0]].sum()
    return 0

try:
    print(sum_sheet00("data/projects/Haus_Dalat/Haus_Dalat_ESTIMATION_20261010_221539.xlsx"))
except Exception as e:
    print("Error:", e)
