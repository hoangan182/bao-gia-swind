import xlrd

def test_unmerge_empty_top_left():
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
            top_left_value = data[rlo][clo]
            
            # Check if top-left is empty but others are not
            if str(top_left_value).strip() == "":
                for rowx in range(rlo, rhi):
                    for colx in range(clo, chi):
                        cell_val = data[rowx][colx]
                        if str(cell_val).strip() != "":
                            issues.append(f"Sheet {sheet_name}, Merge Range ({rlo}:{rhi}, {clo}:{chi}): Top-left is empty but cell ({rowx},{colx}) has value '{cell_val}'.")
                            
    if not issues:
        print("Iteration 2: No empty top-left issues found.")
    else:
        for issue in issues:
            print(issue)

test_unmerge_empty_top_left()
