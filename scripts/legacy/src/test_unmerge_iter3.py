import xlrd

def test_unmerge_overlap():
    file_path = "../BẢNG TÍNH GIÁ SWIND  chuẩn 2026.xls"
    wb = xlrd.open_workbook(file_path, formatting_info=True)
    
    issues = []
    for sheet_name in wb.sheet_names():
        sheet = wb.sheet_by_name(sheet_name)
        
        seen_cells = {}
        for crange in sheet.merged_cells:
            rlo, rhi, clo, chi = crange
            for rowx in range(rlo, rhi):
                for colx in range(clo, chi):
                    cell = (rowx, colx)
                    if cell in seen_cells:
                        issues.append(f"Sheet {sheet_name}: Overlapping merge at {cell}. Previously in {seen_cells[cell]}, now in {crange}.")
                    seen_cells[cell] = crange
                            
    if not issues:
        print("Iteration 3: No overlapping merge cells found.")
    else:
        for issue in issues:
            print(issue)

test_unmerge_overlap()
