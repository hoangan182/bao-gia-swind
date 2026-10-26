import os
import sys
import re
import glob
import shutil
import zipfile
import argparse
from copy import copy
from datetime import datetime
import openpyxl
from openpyxl.cell.cell import MergedCell
from swind_utils import vietnamese_slugify


def sanitize_sheet_title(title, existing_titles=None):
    """
    Làm sạch tên Sheet theo quy định của Excel (tối đa 31 ký tự, không chứa ký tự cấm \\ / * ? : [ ]).
    Đảm bảo không trùng tên với các sheet đã có trong workbook.
    """
    if not title:
        title = "Sheet"
    clean = re.sub(r'[\\/*?:\[\]]', '_', str(title)).strip().strip("'")
    if not clean:
        clean = "Sheet"
    base = clean[:31]
    if existing_titles is None:
        return base
    candidate = base
    counter = 2
    while candidate in existing_titles:
        suffix = f"_{counter}"
        candidate = f"{base[:31 - len(suffix)]}{suffix}"
        counter += 1
    return candidate


def copy_sheet_content(src_ws, dst_ws):
    """
    Copy nguyên vẹn nội dung, công thức, định dạng (font, fill, border, alignment, number_format),
    độ rộng cột, chiều cao dòng và các ô gộp (merged cells) từ src_ws sang dst_ws.
    """
    if src_ws.views.sheetView and dst_ws.views.sheetView:
        dst_ws.views.sheetView[0].showGridLines = src_ws.views.sheetView[0].showGridLines
        if src_ws.views.sheetView[0].zoomScale:
            dst_ws.views.sheetView[0].zoomScale = src_ws.views.sheetView[0].zoomScale

    dst_ws.freeze_panes = src_ws.freeze_panes
    dst_ws.sheet_format.defaultRowHeight = src_ws.sheet_format.defaultRowHeight
    dst_ws.sheet_format.defaultColWidth = src_ws.sheet_format.defaultColWidth

    for col_letter, col_dim in src_ws.column_dimensions.items():
        dst_col = dst_ws.column_dimensions[col_letter]
        dst_col.width = col_dim.width
        dst_col.hidden = col_dim.hidden
        dst_col.bestFit = col_dim.bestFit
        dst_col.outline_level = col_dim.outline_level

    for row_idx, row_dim in src_ws.row_dimensions.items():
        dst_row = dst_ws.row_dimensions[row_idx]
        dst_row.height = row_dim.height
        dst_row.hidden = row_dim.hidden
        dst_row.outline_level = row_dim.outline_level

    for row in src_ws.iter_rows():
        for cell in row:
            dst_cell = dst_ws.cell(row=cell.row, column=cell.column)
            if not isinstance(cell, MergedCell) and not isinstance(dst_cell, MergedCell):
                dst_cell.value = cell.value
            if cell.has_style:
                dst_cell.font = copy(cell.font)
                dst_cell.fill = copy(cell.fill)
                dst_cell.border = copy(cell.border)
                dst_cell.alignment = copy(cell.alignment)
                dst_cell.number_format = cell.number_format
                dst_cell.protection = copy(cell.protection)

    for merged_range in src_ws.merged_cells.ranges:
        dst_ws.merge_cells(str(merged_range))


def _patch_core_properties(filepath):
    now_str = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    core_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:dcterms="http://purl.org/dc/terms/" '
        'xmlns:dcmitype="http://purl.org/dc/dcmitype/" '
        'xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance">\n'
        '<dc:creator>Swind Multi-Agent AI</dc:creator>\n'
        '<cp:lastModifiedBy>Swind Multi-Agent AI</cp:lastModifiedBy>\n'
        f'<dcterms:created xsi:type="dcterms:W3CDTF">{now_str}</dcterms:created>\n'
        f'<dcterms:modified xsi:type="dcterms:W3CDTF">{now_str}</dcterms:modified>\n'
        '</cp:coreProperties>'
    )
    temp_path = filepath + ".tmp.zip"
    try:
        with zipfile.ZipFile(filepath, 'r') as zin:
            with zipfile.ZipFile(temp_path, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
                for item in zin.infolist():
                    if item.filename == 'docProps/core.xml':
                        zout.writestr(item, core_xml.encode('utf-8'))
                    else:
                        zout.writestr(item, zin.read(item.filename))
        shutil.move(temp_path, filepath)
    except Exception:
        if os.path.exists(temp_path):
            os.remove(temp_path)


def _find_input_boq_sheets(project_name, boq_file=None):
    """
    Tìm danh sách tên Sheet gốc trong thư mục input/ (nếu có) để đặt lại đúng tên Sheet tiếng Việt
    và sắp xếp đúng thứ tự như file BOQ khách hàng.
    """
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = []
    if boq_file and os.path.exists(boq_file):
        candidates.append(boq_file)
    else:
        input_dir = os.path.join(base_dir, "input")
        for ext in ("*.xlsx", "*.xlsm", "*.xls"):
            for fp in glob.glob(os.path.join(input_dir, ext)):
                bname = os.path.basename(fp)
                pname = bname.replace("_BOQ_MEP (NCC).xlsx", "").replace(".xlsm", "").replace(".xlsx", "").replace(".xls", "").strip()
                if pname == project_name or (project_name.upper() == "CAND" and "CAND" in pname.upper()):
                    candidates.append(fp)

    if not candidates:
        return {}

    try:
        wb = openpyxl.load_workbook(candidates[0], read_only=True)
        slug_to_info = {
            "BASEMENT": (1, "BASEMENT"),
            "A_TOWER": (2, "A TOWER"),
            "B_TOWER": (3, "B TOWER"),
            "LANDSCAPE": (4, "LANDSCAPE"),
        }
        for idx, sh_name in enumerate(wb.sheetnames):
            sh_slug = vietnamese_slugify(sh_name, max_len=30, add_hash=False).replace('-', '_')
            slug_to_info[sh_slug] = (idx, sh_name)
        wb.close()
        return slug_to_info
    except Exception:
        return {}


def discover_project_sheet_files(project_dir, project_name=None, boq_file=None):
    """
    Tự động quét các file *_BAO_GIA.xlsx thành phần trong thư mục dự án (bỏ qua file tổng hợp chung).
    Trả về danh sách [(sheet_label, file_path), ...] theo đúng thứ tự sheet gốc.
    """
    if not project_name:
        project_name = os.path.basename(os.path.normpath(project_dir))

    merged_main = f"{project_name}_BAO_GIA.xlsx"
    merged_th = f"{project_name}_BAO_GIA_TONG_HOP.xlsx"
    prefix = f"{project_name}_"
    suffix = "_BAO_GIA.xlsx"

    slug_to_orig = _find_input_boq_sheets(project_name, boq_file=boq_file)
    items = []

    for fp in sorted(glob.glob(os.path.join(project_dir, "*_BAO_GIA.xlsx"))):
        fname = os.path.basename(fp)
        if fname in (merged_main, merged_th):
            continue
        if fname.endswith(("_BAO_GIA_ECOBA.xlsx", "_BAO_GIA_FORM_KHACH.xlsx", "_TONG_HOP_BAO_GIA.xlsx", "_BAO_GIA_TONG_HOP.xlsx")):
            continue
        if not (fname.startswith(prefix) and fname.endswith(suffix)):
            continue
        sh_slug = fname[len(prefix):-len(suffix)]
        if not sh_slug:
            continue

        if sh_slug in slug_to_orig:
            order_idx, sh_label = slug_to_orig[sh_slug]
        else:
            m_num = re.match(r'^(\d+)', sh_slug)
            order_idx = int(m_num.group(1)) if m_num else 999
            sh_label = sh_slug

        items.append((order_idx, sh_slug, sh_label, fp))

    items.sort(key=lambda x: (x[0], x[1]))
    return [(sh_label, fp) for _, _, sh_label, fp in items]


def merge_project_quotation_files(project_dir, project_name=None, sheet_files=None, output_file=None, boq_file=None):
    """
    Gộp các file báo giá thành phần của 1 dự án thành 1 file Excel báo giá duy nhất (nhiều sheet).
    Mỗi file thành phần được copy nguyên vẹn sang 1 sheet tương ứng trong file gộp.
    """
    project_dir = os.path.abspath(project_dir)
    if not project_name:
        project_name = os.path.basename(os.path.normpath(project_dir))

    if sheet_files is None:
        sheet_files = discover_project_sheet_files(project_dir, project_name=project_name, boq_file=boq_file)
    else:
        filtered = []
        for sh_label, fp in sheet_files:
            if not os.path.exists(fp):
                continue
            fname = os.path.basename(fp)
            if fname.endswith(("_BAO_GIA_ECOBA.xlsx", "_BAO_GIA_FORM_KHACH.xlsx")):
                continue
            filtered.append((sh_label, fp))
        sheet_files = filtered

    if len(sheet_files) <= 1:
        return None

    if not output_file:
        output_file = os.path.join(project_dir, f"{project_name}_BAO_GIA.xlsx")

    merged_wb = openpyxl.Workbook()
    if "Sheet" in merged_wb.sheetnames:
        default_ws = merged_wb["Sheet"]
    else:
        default_ws = None

    existing_titles = set()
    copied_count = 0

    for sh_label, fp in sheet_files:
        if not os.path.exists(fp):
            continue
        src_wb = openpyxl.load_workbook(fp, data_only=False)
        src_sheets = src_wb.sheetnames
        if len(src_sheets) == 1:
            src_ws = src_wb[src_sheets[0]]
            tab_title = sanitize_sheet_title(sh_label, existing_titles)
            existing_titles.add(tab_title)
            dst_ws = merged_wb.create_sheet(title=tab_title)
            copy_sheet_content(src_ws, dst_ws)
            copied_count += 1
        else:
            for s_name in src_sheets:
                src_ws = src_wb[s_name]
                combined_label = f"{sh_label}_{s_name}" if s_name != "BẢNG BÁO GIÁ TIÊU CHUẨN" else sh_label
                tab_title = sanitize_sheet_title(combined_label, existing_titles)
                existing_titles.add(tab_title)
                dst_ws = merged_wb.create_sheet(title=tab_title)
                copy_sheet_content(src_ws, dst_ws)
                copied_count += 1
        src_wb.close()

    if default_ws is not None and len(merged_wb.sheetnames) > 1:
        merged_wb.remove(default_ws)

    if copied_count == 0:
        return None

    merged_wb.active = 0
    for idx, ws in enumerate(merged_wb.worksheets):
        if ws.views.sheetView:
            ws.views.sheetView[0].tabSelected = (idx == 0)

    merged_wb.save(output_file)
    _patch_core_properties(output_file)
    return output_file


def resolve_project_dir(target):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    projects_root = os.path.join(base_dir, "data", "projects")

    if os.path.isdir(target):
        return os.path.abspath(target)

    cand_in_projects = os.path.join(projects_root, target)
    if os.path.isdir(cand_in_projects):
        return os.path.abspath(cand_in_projects)

    # Nếu truyền đường dẫn file input/xxx.xlsx
    bname = os.path.basename(target).replace("_BOQ_MEP (NCC).xlsx", "").replace(".xlsm", "").replace(".xlsx", "").replace(".xls", "").strip()
    cand_from_file = os.path.join(projects_root, bname)
    if os.path.isdir(cand_from_file):
        return os.path.abspath(cand_from_file)

    # Tìm gần đúng theo slug không dấu
    target_slug = vietnamese_slugify(bname, max_len=40, add_hash=False)
    if os.path.isdir(projects_root):
        for entry in sorted(os.listdir(projects_root)):
            full_p = os.path.join(projects_root, entry)
            if os.path.isdir(full_p):
                if vietnamese_slugify(entry, max_len=40, add_hash=False) == target_slug or target_slug in vietnamese_slugify(entry, max_len=40, add_hash=False):
                    return os.path.abspath(full_p)

    return None


def main():
    parser = argparse.ArgumentParser(
        description="Swind Quotation Sheet Merger - Gộp các file báo giá thành phần của dự án thành 1 file Excel duy nhất."
    )
    parser.add_argument(
        "project",
        nargs="?",
        default=None,
        help="Tên dự án, đường dẫn thư mục dự án (data/projects/<Tên dự án>) hoặc file BOQ đầu vào"
    )
    parser.add_argument(
        "-o", "--output",
        default=None,
        help="Đường dẫn file Excel gộp đầu ra (mặc định: data/projects/<Tên dự án>/<Tên dự án>_BAO_GIA.xlsx)"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Quét và gộp tự động toàn bộ các dự án có nhiều file báo giá trong data/projects/"
    )

    args = parser.parse_args()
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    projects_root = os.path.join(base_dir, "data", "projects")

    if args.all:
        if not os.path.isdir(projects_root):
            print(f"[LỖI] Không tìm thấy thư mục dự án: {projects_root}")
            sys.exit(1)
        merged_any = False
        for entry in sorted(os.listdir(projects_root)):
            p_dir = os.path.join(projects_root, entry)
            if not os.path.isdir(p_dir):
                continue
            sheet_files = discover_project_sheet_files(p_dir, project_name=entry)
            if len(sheet_files) > 1:
                out_fp = merge_project_quotation_files(p_dir, project_name=entry, sheet_files=sheet_files)
                if out_fp:
                    merged_any = True
                    print(f"✅ [{entry}] Đã gộp {len(sheet_files)} sheets -> {out_fp}")
        if not merged_any:
            print("Không có dự án nào có nhiều hơn 1 file báo giá cần gộp.")
        return

    if args.project:
        p_dir = resolve_project_dir(args.project)
        if not p_dir:
            print(f"[LỖI] Không tìm thấy thư mục dự án tương ứng với: {args.project}")
            sys.exit(1)
        p_name = os.path.basename(os.path.normpath(p_dir))
        sheet_files = discover_project_sheet_files(p_dir, project_name=p_name)
        if len(sheet_files) <= 1:
            print(f"[THÔNG BÁO] Dự án '{p_name}' chỉ có {len(sheet_files)} file báo giá, không cần gộp.")
            return
        out_fp = merge_project_quotation_files(
            p_dir,
            project_name=p_name,
            sheet_files=sheet_files,
            output_file=args.output
        )
        print("=" * 75)
        print(f"🎉 ĐÃ GỘP THÀNH CÔNG {len(sheet_files)} SHEET BÁO GIÁ CỦA DỰ ÁN '{p_name}':")
        for idx, (sh_label, fp) in enumerate(sheet_files, 1):
            print(f"  [{idx}] Sheet '{sh_label}' <- {os.path.basename(fp)}")
        print(f"  ➔ File Báo giá chung: {out_fp}")
        print("=" * 75)
        return

    # Nếu không truyền tham số, liệt kê các dự án có nhiều file báo giá và mặc định chạy dự án mới nhất
    candidates = []
    if os.path.isdir(projects_root):
        for entry in sorted(os.listdir(projects_root)):
            p_dir = os.path.join(projects_root, entry)
            if not os.path.isdir(p_dir):
                continue
            sheet_files = discover_project_sheet_files(p_dir, project_name=entry)
            if len(sheet_files) > 1:
                mtime = max(os.path.getmtime(fp) for _, fp in sheet_files)
                candidates.append((mtime, entry, p_dir, sheet_files))

    if not candidates:
        print("[THÔNG BÁO] Không tìm thấy dự án nào có nhiều file báo giá cần gộp trong data/projects/.")
        return

    candidates.sort(key=lambda x: x[0], reverse=True)
    _, p_name, p_dir, sheet_files = candidates[0]
    out_fp = merge_project_quotation_files(p_dir, project_name=p_name, sheet_files=sheet_files, output_file=args.output)
    print("=" * 75)
    print(f"🎉 ĐÃ GỘP THÀNH CÔNG {len(sheet_files)} SHEET BÁO GIÁ CỦA DỰ ÁN '{p_name}':")
    for idx, (sh_label, fp) in enumerate(sheet_files, 1):
        print(f"  [{idx}] Sheet '{sh_label}' <- {os.path.basename(fp)}")
    print(f"  ➔ File Báo giá chung: {out_fp}")
    print("=" * 75)


if __name__ == "__main__":
    main()
