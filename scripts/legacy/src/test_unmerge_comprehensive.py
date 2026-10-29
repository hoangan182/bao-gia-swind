"""
BỘ TEST KIỂM THỬ TOÀN DIỆN VÀ PHẢN BIỆN THUẬT TOÁN UNMERGE (RETEST & STRESS TESTS)
Tác giả: Swind Senior Auditor Agent
Mục tiêu: 
1. Retest thực tế 100% trên 17 sheets của file gốc 'BẢNG TÍNH GIÁ SWIND  chuẩn 2026.xls'
2. Phản biện và stress-test các trường hợp bệnh lý (Pathological Edge Cases):
   - Case 1: Out-of-bounds merges (Merge range vượt quá kích thước thật của bảng)
   - Case 2: Silent Data Clobbering (Ô phụ trong merge có chứa dữ liệu khác bị ghi đè mất)
   - Case 3: Overlapping Merges (Xung đột dải merge chồng chéo)
   - Case 4: Blank Merge (Dải merge toàn ô rỗng)
   - Case 5: Kiểu dữ liệu đặc biệt (Số 0, 0.0, Boolean False, None, String khoảng trắng)
"""

import xlrd
import pandas as pd
import numpy as np
import time

def audit_real_master_file(file_path):
    print("=" * 60)
    print("PHẦN 1: RETEST THỰC TẾ TRÊN 17 SHEETS CỦA FILE MASTER")
    print("=" * 60)
    wb = xlrd.open_workbook(file_path, formatting_info=True)
    
    total_sheets = len(wb.sheet_names())
    total_merges = 0
    sheet_stats = []
    
    for sname in wb.sheet_names():
        s = wb.sheet_by_name(sname)
        n_merges = len(s.merged_cells)
        total_merges += n_merges
        
        # Kiểm tra chi tiết từng dải merge
        v_merges = 0
        h_merges = 0
        block_merges = 0
        blank_merges = 0
        non_empty_subs = 0
        
        for crange in s.merged_cells:
            rlo, rhi, clo, chi = crange
            is_v = (rhi - rlo > 1) and (chi - clo == 1)
            is_h = (rhi - rlo == 1) and (chi - clo > 1)
            is_block = (rhi - rlo > 1) and (chi - clo > 1)
            if is_v: v_merges += 1
            elif is_h: h_merges += 1
            elif is_block: block_merges += 1
            
            # Kiểm tra ô rỗng
            if rlo < s.nrows and clo < s.ncols:
                tl = s.cell_value(rlo, clo)
                if s.cell_type(rlo, clo) == xlrd.XL_CELL_EMPTY or str(tl).strip() == "":
                    blank_merges += 1
                    
            # Kiểm tra ô phụ có dữ liệu không
            for r in range(rlo, min(rhi, s.nrows)):
                for c in range(clo, min(chi, s.ncols)):
                    if r == rlo and c == clo: continue
                    if s.cell_type(r, c) != xlrd.XL_CELL_EMPTY and str(s.cell_value(r, c)).strip() != "":
                        non_empty_subs += 1
                        
        sheet_stats.append({
            "sheet": sname,
            "rows": s.nrows,
            "cols": s.ncols,
            "merges": n_merges,
            "v_merges": v_merges,
            "h_merges": h_merges,
            "block_merges": block_merges,
            "blank_merges": blank_merges,
            "non_empty_subs": non_empty_subs
        })
        
    df_stats = pd.DataFrame(sheet_stats)
    print(df_stats.to_string(index=False))
    print("-" * 60)
    print(f"Tổng số sheet: {total_sheets}")
    print(f"Tổng số dải merge: {total_merges}")
    print(f"Tổng số merge rỗng hoàn toàn: {df_stats['blank_merges'].sum()}")
    print(f"Số ô phụ có dữ liệu ngầm bị nguy cơ mất (non-empty subs): {df_stats['non_empty_subs'].sum()}")
    return df_stats

def stress_test_synthetic_edge_cases():
    print("\n" + "=" * 60)
    print("PHẦN 2: PHẢN BIỆN & STRESS-TEST CÁC CA BỆNH LÝ (EDGE CASES)")
    print("=" * 60)
    
    # Giả lập ma trận data và các dải merge bất thường
    test_cases = [
        {
            "name": "Case 1: Out of bounds (Merge range khai báo vượt kích thước data)",
            "data": [["A", "B"], ["C", "D"]], # 2x2
            "merged_cells": [(0, 5, 0, 5)],    # Yêu cầu merge 5x5!
            "expected_behavior": "Phải tự clamp về kích thước thật (2x2), không bị IndexError."
        },
        {
            "name": "Case 2: Giá trị số 0 (Zero Preserving)",
            "data": [[0, ""], ["", ""]],
            "merged_cells": [(0, 2, 0, 2)],
            "expected_behavior": "Số 0 không được coi là rỗng! Tất cả các ô phải bằng 0."
        },
        {
            "name": "Case 3: Top-left rỗng nhưng góc dưới có dữ liệu",
            "data": [["", ""], ["", "FOUND_ME"]],
            "merged_cells": [(0, 2, 0, 2)],
            "expected_behavior": "Phải tìm thấy 'FOUND_ME' và fill cho cả 4 ô."
        },
        {
            "name": "Case 4: Xung đột dữ liệu ngầm (Top-left có 'A' nhưng ô con có 'B')",
            "data": [["Header_A", ""], ["Secret_B", ""]],
            "merged_cells": [(0, 2, 0, 2)],
            "expected_behavior": "Nếu vô tư ghi đè 'Header_A', 'Secret_B' sẽ bị mất vĩnh viễn! Cần có cơ chế cảnh báo."
        },
        {
            "name": "Case 5: Overlapping merges (Chồng lấn)",
            "data": [["A", "B", "C"], ["D", "E", "F"]],
            "merged_cells": [(0, 2, 0, 2), (0, 2, 1, 3)], # Cột 1 bị trùng ở cả 2 range!
            "expected_behavior": "Phải phát hiện xung đột và xử lý theo policy (Strict: Raise, Tolerant: Log warning & retain first)."
        }
    ]

    for tc in test_cases:
        print(f"\n--> Đang test: {tc['name']}")
        print(f"    Kỳ vọng: {tc['expected_behavior']}")
        
        # Thử nghiệm với thuật toán hiện tại
        data_copy = [row[:] for row in tc["data"]]
        seen_cells = {}
        error = None
        data_lost_warning = []
        
        try:
            for crange in tc["merged_cells"]:
                rlo, rhi, clo, chi = crange
                
                # Check Bounds
                if rlo < 0 or clo < 0 or rlo >= len(data_copy) or (len(data_copy) > 0 and clo >= len(data_copy[0])):
                    continue
                    
                top_left_value = data_copy[rlo][clo]
                
                # Check Empty Top-Left (Lưu ý: số 0 không được coi là rỗng!)
                is_empty_tl = (top_left_value is None) or (isinstance(top_left_value, str) and top_left_value.strip() == "")
                if is_empty_tl:
                    for rx in range(rlo, min(rhi, len(data_copy))):
                        for cx in range(clo, min(chi, len(data_copy[rx]))):
                            v = data_copy[rx][cx]
                            if v is not None and not (isinstance(v, str) and v.strip() == ""):
                                top_left_value = v
                                break
                        if top_left_value is not None and not (isinstance(top_left_value, str) and top_left_value.strip() == ""):
                            break
                            
                # Check Overlap & Clobbering
                for rx in range(rlo, min(rhi, len(data_copy))):
                    for cx in range(clo, min(chi, len(data_copy[rx]))):
                        if (rx, cx) in seen_cells:
                            raise ValueError(f"Xung đột overlap tại ({rx}, {cx}) giữa dải {seen_cells[(rx, cx)]} và {crange}")
                        seen_cells[(rx, cx)] = crange
                        
                        # Cảnh báo mất dữ liệu ngầm
                        old_val = data_copy[rx][cx]
                        if (rx != rlo or cx != clo) and old_val not in (None, "") and old_val != top_left_value:
                            data_lost_warning.append(f"Mất dữ liệu ngầm tại ({rx}, {cx}): '{old_val}' bị ghi đè bởi '{top_left_value}'")
                            
                        data_copy[rx][cx] = top_left_value
        except Exception as e:
            error = str(e)
            
        if error:
            print(f"    Kết quả: Ném lỗi ngoại lệ: {error}")
        else:
            print(f"    Kết quả: Thành công. Ma trận sau unmerge: {data_copy}")
        if data_lost_warning:
            print(f"    [CẢNH BÁO QUAN TRỌNG]: {data_lost_warning}")

if __name__ == "__main__":
    audit_real_master_file("BẢNG TÍNH GIÁ SWIND  chuẩn 2026.xls")
    stress_test_synthetic_edge_cases()
