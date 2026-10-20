import xlrd

file_path = "../BẢNG TÍNH GIÁ SWIND  chuẩn 2026.xls"
wb = xlrd.open_workbook(file_path, formatting_info=True)

issues = []
for sheet_name in wb.sheet_names():
    sheet = wb.sheet_by_name(sheet_name)
    data = []
    for r in range(sheet.nrows):
        row = []
        for c in range(sheet.ncols):
            row.append(sheet.cell_value(r, c))
        data.append(row)
        
    for crange in sheet.merged_cells:
        rlo, rhi, clo, chi = crange
        try:
            top_left_value = data[rlo][clo]
            for rowx in range(rlo, rhi):
                for colx in range(clo, chi):
                    if rowx >= len(data) or colx >= len(data[rowx]):
                        issues.append(f"IndexError in {sheet_name}: rlo={rlo}, rhi={rhi}, clo={clo}, chi={chi}. Data bounds: {len(data)}x{len(data[0]) if data else 0}")
                    else:
                        data[rowx][colx] = top_left_value
        except IndexError:
            issues.append(f"Top-left IndexError in {sheet_name}: rlo={rlo}, clo={clo}")

if not issues:
    print("Iteration 1: No errors found in basic unmerge.")
else:
    for issue in issues:
        print(issue)
