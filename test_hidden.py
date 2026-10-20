import openpyxl
wb = openpyxl.load_workbook("data/projects/Haus_Dalat/Haus_Dalat_ESTIMATION_20261011_100917.xlsx")
for sheet in wb.worksheets:
    print(f"Sheet: {sheet.title}, State: {sheet.sheet_state}")
