"""Tạo file MẪU Sheet 'BG' (form báo giá chuẩn Swind) từ một sheet báo giá đã chỉnh form tay.

Nguồn mẫu hiện hành (User chốt 2026-11-24): input/BG20- Sland-Xtech 23.11.26  AC.OG.CGVG.xlsx, sheet 'B1'.
File mẫu KHÔNG chứa dữ liệu dự án của khách (chỉ đầu trang, dòng mẫu style, dòng tổng, điều khoản) → được commit.

Bố cục file mẫu (sheet 'BG') — swind_excel_builder đọc theo đúng các hằng số TPL_* bên dưới:
  1..14 : đầu trang (công ty, khách hàng, tiêu đề cột) — dòng 14 trống; dữ liệu bắt đầu dòng 15
  15    : style dòng Title nhóm (section)
  16    : style dòng mặt hàng
  18..20: 3 dòng tổng (Trước thuế / VAT / Sau thuế)
  22..34: khối ghi chú, điều khoản, thụ hưởng

Chạy:  ./venv/bin/python scripts/build_bg_template.py "<file nguồn.xlsx>" --sheet B1 \
           --section-row 16 --item-row 30 --total-row 257 --note-row 261
"""
import argparse
import os
import sys
from copy import copy

import openpyxl

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "data", "master_data", "templates", "BG_MAU_SWIND.xlsx")

TPL_HEADER_LAST, TPL_SECTION_ROW, TPL_ITEM_ROW, TPL_TOTAL_ROW, TPL_NOTE_ROW = 14, 15, 16, 18, 22
NOTE_ROWS = 13
SALES_NAME, SALES_PHONE = "Ms Nhài", "0945588248"  # User chốt 2026-11-24: cố định PT Kinh doanh + ĐT


def _copy_cell(src, dst, value=True):
    if value:
        dst.value = src.value
    if src.has_style:  # khác workbook: chép từng thành phần (chỉ số _style thuộc workbook nguồn)
        dst.font, dst.fill, dst.border = copy(src.font), copy(src.fill), copy(src.border)
        dst.alignment, dst.protection = copy(src.alignment), copy(src.protection)
        dst.number_format = src.number_format


def _copy_row(ws_s, r_s, ws_d, r_d, value=True, ncol=17):
    if ws_s.row_dimensions[r_s].height:
        ws_d.row_dimensions[r_d].height = ws_s.row_dimensions[r_s].height
    for c in range(1, ncol + 1):
        _copy_cell(ws_s.cell(r_s, c), ws_d.cell(r_d, c), value=value)


def _copy_merges(ws_s, ws_d, r_from, r_to, off):
    for m in ws_s.merged_cells.ranges:
        if r_from <= m.min_row and m.max_row <= r_to:
            ws_d.merge_cells(start_row=m.min_row + off, start_column=m.min_col, end_row=m.max_row + off, end_column=m.max_col)


def build(src_path, sheet, section_row, item_row, total_row, note_row):
    wb_s = openpyxl.load_workbook(src_path)
    ws_s = wb_s[sheet]
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BG"
    # Đầu trang 1..14 (giá trị + style + merge)
    for r in range(1, TPL_HEADER_LAST + 1):
        _copy_row(ws_s, r, ws, r)
    _copy_merges(ws_s, ws, 1, TPL_HEADER_LAST, 0)
    ws["K11"] = "Độ dày"  # User chốt 2026-11-24: không ghi đơn vị (mẫu B1 ghi 'Độ dày\n(m)')
    ws["P7"] = None
    ws["P8"] = SALES_NAME
    ws["P9"] = SALES_PHONE
    # Dòng mẫu style (không giữ chữ của khách)
    _copy_row(ws_s, section_row, ws, TPL_SECTION_ROW, value=False)
    _copy_row(ws_s, item_row, ws, TPL_ITEM_ROW, value=False)
    # Dòng tổng + điều khoản (giữ chữ, công thức builder ghi lại)
    for i in range(3):
        _copy_row(ws_s, total_row + i, ws, TPL_TOTAL_ROW + i)
        for c in range(2, 18):
            if c != 15:
                ws.cell(TPL_TOTAL_ROW + i, c).value = None
    _copy_merges(ws_s, ws, total_row, total_row + 2, TPL_TOTAL_ROW - total_row)
    for i in range(NOTE_ROWS):
        _copy_row(ws_s, note_row + i, ws, TPL_NOTE_ROW + i)
    _copy_merges(ws_s, ws, note_row, note_row + NOTE_ROWS - 1, TPL_NOTE_ROW - note_row)
    # Độ rộng cột, zoom, lề, khổ giấy
    for col_l, dim in ws_s.column_dimensions.items():
        if dim.width:
            ws.column_dimensions[col_l].width = dim.width
    ws.sheet_view.zoomScale = ws_s.sheet_view.zoomScale
    ws.sheet_view.showGridLines = ws_s.sheet_view.showGridLines
    ws.page_margins = copy(ws_s.page_margins)
    ws.page_setup.orientation = ws_s.page_setup.orientation
    ws.page_setup.paperSize = ws_s.page_setup.paperSize
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    wb.save(OUT)
    return OUT


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("src")
    ap.add_argument("--sheet", default="B1")
    ap.add_argument("--section-row", type=int, default=16)
    ap.add_argument("--item-row", type=int, default=30)
    ap.add_argument("--total-row", type=int, default=257)
    ap.add_argument("--note-row", type=int, default=261)
    a = ap.parse_args()
    print(build(a.src, a.sheet, a.section_row, a.item_row, a.total_row, a.note_row))
    sys.exit(0)
