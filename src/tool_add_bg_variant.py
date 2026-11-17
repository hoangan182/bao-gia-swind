"""
Gộp Sheet `BG` của một file báo giá biến thể (VD động cơ KLB) vào file báo giá mặc định thành 1 sheet mới nằm cạnh `BG`.

User yêu cầu 2026-11-17 (dự án 261111-BOQ C07 / C09 MEP): 1 file duy nhất, sheet `BG` (mặc định) + `BG-KLB` (động cơ KLB),
thay vì 2 file riêng. Giữ nguyên hình ảnh / logo của các sheet BOQ gốc (openpyxl làm rơi drawing → khôi phục lại từ BOQ khách).

Dùng:
  ./venv/bin/python src/tool_add_bg_variant.py "<base.xlsx>" "<variant.xlsx>" --name BG-KLB --src-boq "<BOQ khách.xlsx>"
"""
import argparse
import os
import sys

import openpyxl

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from swind_merge_quotations import copy_sheet_content, restore_boq_drawings  # noqa: E402


def add_bg_variant(base_file, variant_file, new_name="BG-KLB", src_sheet="BG", src_boq=None):
    wb_base = openpyxl.load_workbook(base_file)
    wb_var = openpyxl.load_workbook(variant_file)
    if src_sheet not in wb_base.sheetnames or src_sheet not in wb_var.sheetnames:
        raise SystemExit(f"Thiếu sheet '{src_sheet}' ở file mặc định hoặc file biến thể")
    if new_name in wb_base.sheetnames:
        del wb_base[new_name]
    orig_count = wb_base.sheetnames.index(src_sheet)  # các sheet BOQ gốc nằm trước BG
    ws_new = wb_base.create_sheet(new_name, wb_base.sheetnames.index(src_sheet) + 1)
    copy_sheet_content(wb_var[src_sheet], ws_new)
    wb_base.save(base_file)
    if src_boq:
        restore_boq_drawings(src_boq, base_file, orig_count)
    return base_file


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("base")
    ap.add_argument("variant")
    ap.add_argument("--name", default="BG-KLB")
    ap.add_argument("--src-sheet", default="BG")
    ap.add_argument("--src-boq", default=None, help="BOQ gốc của khách (để khôi phục hình ảnh / logo)")
    a = ap.parse_args()
    print(add_bg_variant(a.base, a.variant, a.name, a.src_sheet, a.src_boq))
