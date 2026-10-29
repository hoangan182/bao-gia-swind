import xlrd

wb = xlrd.open_workbook('input/HDL-A1 HVAC TECHNICAL DATA.xls')
s = wb.sheet_by_name('M.4 DUCT WORKS')
print(f"--- Sheet: M.4 DUCT WORKS ---")
for r in range(15, 45):
    row_vals = s.row_values(r)
    if any(row_vals):
        print(f"Row {r}: {row_vals[:15]}")
