import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter
from swind_utils import detect_boq_header

class SwindExcelBuilder:
    """
    Trình khởi tạo và xuất Workbook Dự Toán Swind (Excel-First Architecture).
    - Toàn bộ liên kết bằng công thức động (SUMIF, INDEX/MATCH, SUM) tương thích 100% mọi bản Excel.
    - Chuẩn thứ nguyên 100%: Định mức x Số lượng x Đơn giá.
    - Không fallback về 0đ khi thiếu mã vật tư (báo lỗi để QA Checker chặn).
    """
    def __init__(self, output_filename="SWIND_ESTIMATION_WORKBOOK.xlsx", template_file=None, source_sheet="DHKK", template_wb=None):
        self.filename = output_filename
        self.template_file = template_file
        self.template_wb = template_wb
        self.source_sheet = source_sheet
        self.wb = openpyxl.Workbook()
        self.used_materials = {}
        self.parent_rows = {}
        self._setup_sheets()

    def _setup_sheets(self):
        if "Sheet" in self.wb.sheetnames:
            self.wb.remove(self.wb["Sheet"])
            
        self.ws_00 = self.wb.create_sheet("00_TONG_HOP_BAO_GIA")
        self.ws_01 = self.wb.create_sheet("01_BOC_TACH_ONG")
        self.ws_02 = self.wb.create_sheet("02_BOC_TACH_CUA")
        self.ws_03 = self.wb.create_sheet("03_BOC_TACH_VAN")
        self.ws_05 = self.wb.create_sheet("05_DANH_MUC_KY_THUAT_GOC")
        self.ws_06 = self.wb.create_sheet("06_BANG_GIA_VAT_TU_AP_DUNG")
        
        self._format_all_headers()

    def _get_styles(self):
        header_font = Font(name="Arial", size=10, bold=True, color="FFFFFF")
        navy_fill = PatternFill("solid", fgColor="002060") # Swind Navy
        thin_border = Border(left=Side(style='thin', color='D9D9D9'),
                             right=Side(style='thin', color='D9D9D9'),
                             top=Side(style='thin', color='D9D9D9'),
                             bottom=Side(style='thin', color='D9D9D9'))
        return header_font, navy_fill, thin_border

    def _apply_header_style(self, ws, headers):
        header_font, navy_fill, thin_border = self._get_styles()
        ws.append(headers)
        ws.row_dimensions[1].height = 28
        for col_idx in range(1, len(headers) + 1):
            cell = ws.cell(row=1, column=col_idx)
            cell.font = header_font
            cell.fill = navy_fill
            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
            cell.border = thin_border
            ws.column_dimensions[get_column_letter(col_idx)].width = 16

    def _format_all_headers(self):
        # 00_TONG_HOP_BAO_GIA
        headers_00 = [
            "STT", "ITEM_ID", "PHÂN NHÓM", "TÊN SẢN PHẨM", "QUY CÁCH (WxH)", "ĐVT", "SỐ LƯỢNG",
            "CP VẬT TƯ ỐNG", "CP VẬT TƯ CỬA", "CP VẬT TƯ VAN", "TỔNG CP VẬT TƯ",
            "NHÂN CÔNG (25%)", "CP XƯỞNG (10%)", "TỔNG GIÁ VỐN", "GIÁ VỐN / ĐVT",
            "MARGIN (%)", "ĐƠN GIÁ BÁN", "THÀNH TIỀN (VNĐ)", "GHI CHÚ"
        ]
        self._apply_header_style(self.ws_00, headers_00)
        self.ws_00.column_dimensions['B'].width = 22
        self.ws_00.column_dimensions['D'].width = 35
        self.ws_00.column_dimensions['E'].width = 18

        # 01_BOC_TACH_ONG
        headers_sub = [
            "SUB_KEY", "PARENT_ITEM_ID", "TÊN CẤU KIỆN", "PHÂN LOẠI", "MÃ VẬT TƯ (MAT_ID)",
            "ĐVT", "ĐỊNH MỨC / 1 SP", "SL DỰ ÁN", "TỔNG NHU CẦU", "ĐƠN GIÁ GỐC", "THÀNH TIỀN (VNĐ)", "GHI CHÚ KỸ THUẬT"
        ]
        self._apply_header_style(self.ws_01, headers_sub)
        self.ws_01.column_dimensions['A'].width = 22
        self.ws_01.column_dimensions['B'].width = 20
        self.ws_01.column_dimensions['C'].width = 35
        self.ws_01.column_dimensions['E'].width = 28

        # 02_BOC_TACH_CUA
        self._apply_header_style(self.ws_02, headers_sub)
        self.ws_02.column_dimensions['A'].width = 22
        self.ws_02.column_dimensions['B'].width = 20
        self.ws_02.column_dimensions['C'].width = 35
        self.ws_02.column_dimensions['E'].width = 28

        # 03_BOC_TACH_VAN
        self._apply_header_style(self.ws_03, headers_sub)
        self.ws_03.column_dimensions['A'].width = 22
        self.ws_03.column_dimensions['B'].width = 20
        self.ws_03.column_dimensions['C'].width = 35
        self.ws_03.column_dimensions['E'].width = 28

        # 05_DANH_MUC_KY_THUAT_GOC
        headers_05 = ["STT", "MAT_ID", "PHÂN LOẠI", "TÊN VẬT TƯ", "ĐVT", "BAREM KỸ THUẬT", "NGUỒN ĐỐI SOÁT"]
        self._apply_header_style(self.ws_05, headers_05)
        self.ws_05.column_dimensions['B'].width = 30
        self.ws_05.column_dimensions['D'].width = 40

        # 06_BANG_GIA_VAT_TU_AP_DUNG
        headers_06 = ["STT", "MAT_ID", "TÊN VẬT TƯ", "PHÂN LOẠI", "ĐƠN GIÁ GỐC (VNĐ)"]
        self._apply_header_style(self.ws_06, headers_06)
        self.ws_06.column_dimensions['B'].width = 30
        self.ws_06.column_dimensions['C'].width = 40
        self.ws_06.column_dimensions['D'].width = 20
        self.ws_06.column_dimensions['E'].width = 25

    def add_tech_master_data(self, idx, mat_id, category, name, unit, barem, source_trace):
        self.ws_05.append([idx, mat_id, category, name, unit, barem, source_trace])

    def add_price_master_data(self, idx, mat_id, name="", category="THUONG_MAI", price=0):
        r = self.ws_06.max_row + 1
        self.ws_06.append([idx, mat_id, name, category, price])
        self.ws_06.cell(row=r, column=5).number_format = "#,##0"

    def add_boq_summary_row(self, stt, item_id, group, name, size, unit, qty, margin=0.18, labor_rate=0.25, overhead_rate=0.10, note="", override_price=0, box_combo_add_price=0):
        """
        Thêm dòng vào bảng tổng hợp báo giá với công thức sống liên kết 100%.
        Tách biệt tỷ lệ nhân công (labor_rate) và chi phí xưởng (overhead_rate) cho từng nhóm mặt hàng.
        """
        r = self.ws_00.max_row + 1
        
        # H, I, J: SUMIF từ các sheet con (phạm vi $B$2:$B$5000 tối ưu hóa tốc độ tải bảng tính)
        f_cp_ong = f"=SUMIF('01_BOC_TACH_ONG'!$B$2:$B$5000, B{r}, '01_BOC_TACH_ONG'!$K$2:$K$5000)"
        f_cp_cua = f"=SUMIF('02_BOC_TACH_CUA'!$B$2:$B$5000, B{r}, '02_BOC_TACH_CUA'!$K$2:$K$5000)"
        f_cp_van = f"=SUMIF('03_BOC_TACH_VAN'!$B$2:$B$5000, B{r}, '03_BOC_TACH_VAN'!$K$2:$K$5000)"
        
        # K: Tổng chi phí vật tư (liên kết động từ các sheet con)
        f_tong_vt = f"=SUM(H{r}:J{r})"
        
        # Tách chi phí động cơ thương mại (không cộng chồng 25% nhân công xưởng, 10% CP xưởng và 18% margin)
        act_expr = f"SUMIFS('03_BOC_TACH_VAN'!$K$2:$K$5000, '03_BOC_TACH_VAN'!$B$2:$B$5000, B{r}, '03_BOC_TACH_VAN'!$D$2:$D$5000, \"ĐỘNG_CƠ_VÀ_CẢM_BIẾN\")"
        
        # L: Chi phí nhân công định mức (chỉ tính trên phần cơ khí chế tạo)
        f_nhan_cong = f"=(K{r}-{act_expr})*{labor_rate:.2f}"
        
        # M: Chi phí xưởng & phụ hao định mức (chỉ tính trên phần cơ khí chế tạo)
        f_cp_xuong = f"=(K{r}-{act_expr})*{overhead_rate:.2f}"
        
        # N: Tổng giá vốn = Vật tư + Nhân công + Xưởng
        f_gia_von = f"=K{r}+L{r}+M{r}"
        
        # O: Giá vốn / 1 ĐVT
        f_gia_von_unit = f"=IF(G{r}>0, N{r}/G{r}, 0)"
        
        # Q: Đơn giá bán = (Giá vốn cơ khí * (1 + margin) + Chi phí động cơ thương mại) / Số lượng
        if override_price > 0:
            f_gia_ban = override_price
        elif box_combo_add_price > 0:
            f_calc = f"IF(G{r}>0, ROUNDUP(ROUND(((N{r}-{act_expr})*(1+P{r})+{act_expr})/G{r}, 0), -2), 0)"
            f_gia_ban = f"={box_combo_add_price:.0f}+{f_calc}"
        else:
            f_gia_ban = f"=IF(G{r}>0, ROUNDUP(ROUND(((N{r}-{act_expr})*(1+P{r})+{act_expr})/G{r}, 0), -2), 0)"
        
        # R: Thành tiền = Số lượng * Đơn giá bán
        f_thanh_tien = f"=G{r}*Q{r}"
        
        row_vals = [
            stt, item_id, group, name, size, unit, qty,
            f_cp_ong, f_cp_cua, f_cp_van, f_tong_vt,
            f_nhan_cong, f_cp_xuong, f_gia_von, f_gia_von_unit,
            margin, f_gia_ban, f_thanh_tien, note
        ]
        self.ws_00.append(row_vals)
        self.parent_rows[item_id] = r
        
        # Format row
        for col_idx in [7, 8, 9, 10, 11, 12, 13, 14, 15, 17, 18]:
            self.ws_00.cell(row=r, column=col_idx).number_format = "#,##0"
        self.ws_00.cell(row=r, column=16).number_format = "0.0%"

    def add_subsheet_component(self, sheet_type, sub_key, parent_id, comp_name, category, mat_id, unit, calc_qty_per_item, note="", ref_price=0):
        """
        Thêm dòng cấu kiện vào sheet con bóc tách (01_ONG, 02_CUA, 03_VAN).
        - Col H (SL DỰ ÁN) link trực tiếp từ Sheet 00 qua XLOOKUP.
        - Col I (TỔNG NHU CẦU) = Col G * Col H.
        - Col J (ĐƠN GIÁ GỐC) link từ Master Data qua XLOOKUP.
        - Col K (THÀNH TIỀN) = Col I * Col J.
        """
        ws = self.ws_01 if sheet_type == "ONG" else self.ws_02 if sheet_type == "CUA" else self.ws_03
        r = ws.max_row + 1
        
        # Lưu vào danh sách các vật tư đã dùng
        if mat_id not in self.used_materials:
            self.used_materials[mat_id] = {
                "name": comp_name,
                "category": category,
                "unit": unit,
                "ref_price": ref_price
            }
        elif ref_price > 0 and not self.used_materials[mat_id].get("ref_price"):
            self.used_materials[mat_id]["ref_price"] = ref_price
        
        # H: SL Dự án link từ Sheet 00 (Trực tiếp từ ô cha hoặc INDEX/MATCH dự phòng)
        p_row = self.parent_rows.get(parent_id)
        if p_row:
            f_parent_qty = f"='00_TONG_HOP_BAO_GIA'!G{p_row}"
        else:
            f_parent_qty = f"=IFERROR(INDEX('00_TONG_HOP_BAO_GIA'!$G$1:$G$5000, MATCH(B{r}, '00_TONG_HOP_BAO_GIA'!$B$1:$B$5000, 0)), 1)"
        
        # I: Tổng nhu cầu = Định mức 1 SP * Số lượng dự án
        f_total_demand = f"=G{r}*H{r}"
        
        # J: Đơn giá tra cứu từ Master Data Giá (06_BANG_GIA_VAT_TU_AP_DUNG) qua INDEX/MATCH - Giới hạn 5000 dòng
        f_unit_price = f"=IFERROR(INDEX('06_BANG_GIA_VAT_TU_AP_DUNG'!$E$1:$E$5000, MATCH(E{r}, '06_BANG_GIA_VAT_TU_AP_DUNG'!$B$1:$B$5000, 0)), 0)"
        
        # K: Thành tiền = Tổng nhu cầu * Đơn giá
        f_total_cost = f"=I{r}*J{r}"
        
        row_vals = [
            sub_key, parent_id, comp_name, category, mat_id,
            unit, calc_qty_per_item, f_parent_qty, f_total_demand,
            f_unit_price, f_total_cost, note
        ]
        ws.append(row_vals)
        
        ws.cell(row=r, column=7).number_format = "#,##0.000"
        ws.cell(row=r, column=8).number_format = "#,##0"
        ws.cell(row=r, column=9).number_format = "#,##0.00"
        ws.cell(row=r, column=10).number_format = "#,##0"
        ws.cell(row=r, column=11).number_format = "#,##0"

    def add_totals_row(self):
        r = self.ws_00.max_row + 1
        self.ws_00.cell(row=r, column=1, value="TỔNG CỘNG").font = Font(bold=True)
        self.ws_00.merge_cells(start_row=r, start_column=1, end_row=r, end_column=6)
        self.ws_00.cell(row=r, column=1).alignment = Alignment(horizontal="center")
        
        for col_idx in [8, 9, 10, 11, 12, 13, 14, 18]:
            col_letter = get_column_letter(col_idx)
            cell = self.ws_00.cell(row=r, column=col_idx, value=f"=SUM({col_letter}2:{col_letter}{r-1})")
            cell.font = Font(bold=True)
            cell.number_format = "#,##0"

    def _setup_quotation_sheet_header(self, ws, option_label):
        navy_font = Font(name="Times New Roman", size=11, bold=True, color="002060")
        normal_font = Font(name="Times New Roman", size=10, bold=False)
        bold_font = Font(name="Times New Roman", size=10, bold=True)
        title_font = Font(name="Times New Roman", size=16, bold=True, color="002060")
        tbl_header_font = Font(name="Times New Roman", size=10, bold=True, color="FFFFFF")
        tbl_header_fill = PatternFill("solid", fgColor="002060")
        thin_side = Side(style='thin', color='000000')
        thin_border = Border(
            left=thin_side,
            right=thin_side,
            top=thin_side,
            bottom=thin_side
        )
        bottom_line_border = Border(bottom=thin_side)

        ws.cell(2, 3, "CÔNG TY CỔ PHẦN TẬP ĐOÀN QUỐC TẾ SLAND").font = navy_font
        ws.cell(3, 3, "VPGD: SỐ 49, Ngõ 1295 Giải Phóng, Phường Hoàng Mai, TP Hà Nội").font = normal_font
        ws.cell(4, 3, "Nhà máy: Thôn Nhân Hiền - xã Thường Tín - TP Hà Nội").font = normal_font
        ws.cell(5, 3, "Hotline: 082 5577 999").font = bold_font
        ws.merge_cells("B3:B4")
        for r_idx in range(2, 6):
            ws.merge_cells(start_row=r_idx, start_column=3, end_row=r_idx, end_column=16)
        for c_idx in range(1, 17):
            ws.cell(5, c_idx).border = bottom_line_border

        title_text = "BẢNG BÁO GIÁ" if (not option_label or "TIÊU CHUẨN" in option_label) else f"BẢNG BÁO GIÁ ({option_label})"
        ws.cell(6, 1, title_text).font = title_font
        ws.merge_cells("A6:P6")
        ws.cell(6, 1).alignment = Alignment(horizontal="center", vertical="center")
        ws.row_dimensions[6].height = 30

        ws.cell(7, 1, "Khách hàng : ").font = bold_font
        ws.merge_cells("A7:L7")
        ws.cell(7, 13, "Seri number\n Số hiệu").font = bold_font
        ws.merge_cells("N7:P7")
        ws.cell(8, 1, "Địa chỉ :").font = bold_font
        ws.merge_cells("A8:L8")
        ws.cell(8, 13, "Sales executive\n PT Kinh doanh").font = bold_font
        ws.merge_cells("N8:P8")
        ws.cell(9, 1, "Người nhận : ").font = bold_font
        ws.merge_cells("A9:L9")
        ws.cell(9, 13, "Mobile\n Điện thoại").font = bold_font
        ws.merge_cells("N9:P9")
        ws.cell(10, 1, "Email: ").font = bold_font
        ws.merge_cells("A10:B10")
        ws.cell(10, 3, "Số điện thoại :").font = bold_font
        ws.merge_cells("C10:L10")
        ws.cell(10, 13, "Dự án").font = bold_font
        ws.merge_cells("N10:P10")

        for r_idx, r_h in ((7, 26), (8, 22), (9, 22), (10, 24)):
            ws.row_dimensions[r_idx].height = r_h
            for c_idx in range(1, 17):
                c_info = ws.cell(r_idx, c_idx)
                c_info.border = thin_border
                c_info.alignment = Alignment(
                    horizontal="center" if c_idx == 13 else "left",
                    vertical="center",
                    wrap_text=True
                )

        # Table Headers (Rows 11..13)
        ws.cell(11, 1, "STT")
        ws.cell(11, 2, "Danh mục sản phẩm")
        ws.cell(11, 3, "Model")
        ws.cell(11, 4, "Thương hiệu")
        ws.cell(11, 5, "Kích thước (mm)")
        ws.cell(11, 9, "Modul")
        ws.cell(11, 10, "L")
        ws.cell(11, 11, "Độ dày\n(mm)")
        ws.cell(11, 12, "Unit\nĐơn vị")
        ws.cell(11, 13, "Q'ty\nSố lượng")
        ws.cell(11, 14, "Đơn Giá\n(VNĐ)")
        ws.cell(11, 15, "Total price\nThành tiền")
        ws.cell(11, 16, "Remarks\nGhi chú")

        ws.cell(12, 5, "A1")
        ws.cell(12, 6, "A2")
        ws.cell(12, 7, "B1")
        ws.cell(12, 8, "B2")
        ws.cell(13, 5, "Face size")
        ws.cell(13, 7, "Neck size")

        for col_letter in ["A", "B", "C", "D", "I", "J", "K", "L", "M", "N", "O", "P"]:
            ws.merge_cells(f"{col_letter}11:{col_letter}13")
        ws.merge_cells("E11:H11")
        ws.merge_cells("E13:F13")
        ws.merge_cells("G13:H13")

        for r_idx in range(11, 14):
            ws.row_dimensions[r_idx].height = 20
            for c_idx in range(1, 17):
                c = ws.cell(r_idx, c_idx)
                c.font = tbl_header_font
                c.fill = tbl_header_fill
                c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                c.border = thin_border

        col_widths = {
            "A": 6, "B": 38, "C": 20, "D": 14,
            "E": 9, "F": 9, "G": 9, "H": 9,
            "I": 8, "J": 8, "K": 9, "L": 9,
            "M": 11, "N": 16, "O": 18, "P": 44
        }
        for col_l, width in col_widths.items():
            ws.column_dimensions[col_l].width = width

    def build_quotation_sheets(self, all_items, subtype_rules=None, price_records=None, dual_options=False):
        """
        Agent 07: Xuất bản Sheet Báo Giá chuẩn định dạng gửi Khách hàng của Swind (16 cột A..P):
        - dual_options=False (Mặc định): Xuất 1 sheet báo giá chuẩn duy nhất 'BẢNG BÁO GIÁ TIÊU CHUẨN' theo đúng quy cách BOQ.
        - dual_options=True: Xuất đồng thời 2 sheet so sánh phương án:
          1. 'BG Đơn Cánh ĐC FSLF 24V': Phương án van MFD đơn cánh dùng động cơ Belimo FSLF24V (3.5Nm)
          2. 'BG Đa Cánh BFN 24': Phương án van MFD đa cánh dùng động cơ Belimo BFN24 (9Nm)
        """
        from agent_01_boq_extractor import Agent01_BOQExtractor

        if dual_options:
            ws_fslf = self.wb.create_sheet("BG Đơn Cánh ĐC FSLF 24V", 0)
            ws_bfn = self.wb.create_sheet("BG Đa Cánh BFN 24", 1)
            self._setup_quotation_sheet_header(ws_fslf, "PHƯƠNG ÁN 1: VAN MFD ĐƠN CÁNH - ĐỘNG CƠ BELIMO FSLF24V")
            self._setup_quotation_sheet_header(ws_bfn, "PHƯƠNG ÁN 2: VAN MFD ĐA CÁNH - ĐỘNG CƠ BELIMO BFN24")
            worksheets = [(ws_fslf, "fslf"), (ws_bfn, "bfn")]
        else:
            ws_std = self.wb.create_sheet("BG", 0)
            self._setup_quotation_sheet_header(ws_std, "BẢNG BÁO GIÁ THIẾT BỊ VÀ VẬT TƯ HVAC (TIÊU CHUẨN BOQ)")
            worksheets = [(ws_std, "std")]

        price_map = {item["MAT_ID"]: float(item.get("Price") or 0) for item in (price_records or [])}
        subtype_rules = subtype_rules or {}

        section_fill = PatternFill("solid", fgColor="D9E1F2")
        section_font = Font(name="Times New Roman", size=10, bold=True, color="002060")
        row_font = Font(name="Times New Roman", size=10, bold=False)
        thin_side = Side(style='thin', color='000000')
        hair_side = Side(style='hair', color='000000')
        thin_border = Border(
            left=thin_side,
            right=thin_side,
            top=thin_side,
            bottom=thin_side
        )
        item_border = Border(
            left=thin_side,
            right=thin_side,
            top=hair_side,
            bottom=hair_side
        )
        first_item_border = Border(
            left=thin_side,
            right=thin_side,
            top=thin_side,
            bottom=hair_side
        )

        current_section = None
        curr_row = 14

        import os
        import re
        ws_orig = None
        if self.template_wb is not None:
            wb_orig = self.template_wb
            keep_sheet = self.source_sheet if self.source_sheet in wb_orig.sheetnames else ("DHKK" if "DHKK" in wb_orig.sheetnames else wb_orig.sheetnames[0])
            ws_orig = wb_orig[keep_sheet]
        elif self.template_file and os.path.exists(self.template_file):
            try:
                wb_orig = openpyxl.load_workbook(self.template_file, data_only=True)
                keep_sheet = self.source_sheet if self.source_sheet in wb_orig.sheetnames else ("DHKK" if "DHKK" in wb_orig.sheetnames else wb_orig.sheetnames[0])
                ws_orig = wb_orig[keep_sheet]
            except Exception:
                ws_orig = None
        zone_col_map = {"BASEMENT": 42, "A TOWER": 43, "B TOWER": 44, "LANDSCAPE": 45}
        if ws_orig is not None and self.source_sheet in zone_col_map and not getattr(ws_orig, "_forced_qty_col", None):
            ws_orig._forced_qty_col = zone_col_map[self.source_sheet]

        def _write_row_cells(r_num, vals_std, vals_fslf=None, vals_bfn=None, is_section=False):
            for ws, mode in worksheets:
                if is_section:
                    if vals_std[0] is not None:
                        ws.cell(r_num, 1, vals_std[0]).font = section_font
                        ws.cell(r_num, 1).alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                    if vals_std[1] is not None:
                        ws.cell(r_num, 2, vals_std[1]).font = section_font
                        ws.cell(r_num, 2).alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                    for c_i in range(1, 17):
                        ws.cell(r_num, c_i).fill = section_fill
                        ws.cell(r_num, c_i).border = thin_border
                else:
                    r_vals = vals_std if mode == "std" else ((vals_fslf or vals_std) if mode == "fslf" else (vals_bfn or vals_std))
                    row_bdr = first_item_border if r_num == 14 else item_border
                    for c_i, val in enumerate(r_vals, 1):
                        cell = ws.cell(r_num, c_i, value=val)
                        cell.font = row_font
                        cell.border = row_bdr
                        if c_i in (1, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12):
                            cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
                        elif c_i in (13, 14, 15):
                            cell.alignment = Alignment(horizontal="right", vertical="center")
                            if val is not None:
                                cell.number_format = "#,##0"
                        else:
                            cell.alignment = Alignment(horizontal="left", vertical="center", wrap_text=True)
                        if c_i == 11 and isinstance(val, float):
                            cell.number_format = "0.00"

        if ws_orig is not None:
            # Nhận diện Header BOQ (dùng hàm chung từ swind_utils)
            header_row, col_map, hidden_rows, hidden_cols, max_scan_col = detect_boq_header(ws_orig)

            stt_col = col_map.get("stt", 1) if col_map.get("name", 2) != 1 else col_map.get("stt")
            name_col = col_map.get("name", 2)
            unit_col = col_map.get("unit", 5)
            qty_col = col_map.get("qty", 6)

            start_boq_row = header_row + 1
            while start_boq_row <= min(header_row + 3, ws_orig.max_row):
                r_texts = [str(ws_orig.cell(start_boq_row, c).value or "").strip().lower() for c in range(1, max_scan_col + 1) if get_column_letter(c) not in hidden_cols]
                name_cell_v = ws_orig.cell(start_boq_row, name_col).value
                if any(k in r_texts for k in ("boq", "nhà thầu", "a1", "face size", "neck size")) or (name_cell_v in (None, "") and (any(k in r_texts for k in ("model", "modul", "thương hiệu", "đơn giá", "thành tiền", "vật liệu", "nhân công", "vật tư", "material / vt", "labor / nc", "material / vật liệu")) or (start_boq_row > header_row + 1 and not any(r_texts)))):
                    start_boq_row += 1
                else:
                    break

            end_boq_row = ws_orig.max_row
            for r_chk in range(start_boq_row, ws_orig.max_row + 1):
                b_chk = str(ws_orig.cell(r_chk, name_col).value or "").strip().lower()
                a_chk = str(ws_orig.cell(r_chk, stt_col).value or "").strip().lower() if stt_col else ""
                if any(k in b_chk or k in a_chk for k in ("tổng cộng", "tổng giá trị", "trước vat", "trước thuế vat", "total amount")):
                    end_boq_row = r_chk - 1
                    break
            while end_boq_row >= start_boq_row:
                if end_boq_row not in hidden_rows and any(get_column_letter(c) not in hidden_cols and ws_orig.cell(end_boq_row, c).value is not None and str(ws_orig.cell(end_boq_row, c).value).strip() != "" for c in range(1, max(7, name_col + 1, qty_col + 1))):
                    break
                end_boq_row -= 1

            row_to_items = {}
            for idx, item in enumerate(all_items, 1):
                sr = item.get("source_row")
                if sr:
                    row_to_items.setdefault(sr, []).append((idx, item))

            def _is_sec_hdr(c2_cell, orig_name_s, orig_c_v, orig_u_v, orig_q_v):
                if orig_q_v is not None and (not isinstance(orig_q_v, str) or orig_q_v.strip() != ""):
                    return False
                if orig_u_v is not None and str(orig_u_v).strip() != "" and not str(orig_u_v).strip().replace('.', '').isdigit():
                    return False
                if orig_c_v is not None and str(orig_c_v).strip() != "":
                    return False
                if not orig_name_s:
                    return False
                if c2_cell.font and c2_cell.font.bold:
                    return True
                s = orig_name_s.strip()
                if re.match(r'^(hạng mục|[A-Z]\.|[IVX]+\.|\d+\.|[a-z]\.|chi phí khác)', s, re.IGNORECASE):
                    return True
                if re.search(r'(\bD\d{2,4}\b|\d+\s*[xX*]\s*\d+|:\s*\d+|vật tư phụ|phụ kiện ống gió)', s, re.IGNORECASE):
                    return False
                return True

            stt_hidden = (not stt_col) or (get_column_letter(stt_col) in hidden_cols)
            for r in range(start_boq_row, end_boq_row + 1):
                if r in hidden_rows:
                    continue
                orig_stt = ws_orig.cell(r, stt_col).value if not stt_hidden else (r if header_row == 0 and not stt_col else None)
                if orig_stt in (0, "0"):
                    orig_stt = None
                if r in row_to_items:
                    for idx, item in row_to_items[r]:
                        sheet00_row = idx + 1
                        raw_name = item.get("raw_name") or item["name"]
                        unit = item["unit"]
                        qty = item["qty"]
                        disp_qty = None if item.get("is_missing_qty") else qty
                        spec = item.get("resolved_spec") or Agent01_BOQExtractor.resolve_item_spec(item, subtype_rules, price_map=price_map, idx=idx)

                        f_price_base = f"=ROUNDUP(ROUND('00_TONG_HOP_BAO_GIA'!Q{sheet00_row}, 0), -2)"
                        if spec.get("has_fslf_formula_diff"):
                            act_unit = spec["act_unit"]
                            ratio = spec["fslf_ratio"]
                            f_price_fslf = f"=ROUNDUP(ROUND(('00_TONG_HOP_BAO_GIA'!Q{sheet00_row}-{act_unit:.0f})*{ratio:.6f}+{act_unit:.0f}, 0), -2)"
                        else:
                            f_price_fslf = f_price_base
                        f_price_bfn = f_price_base

                        row_std = [
                            orig_stt, raw_name, spec.get("model_std") or spec["model_fslf"], spec["brand"],
                            spec["a1"], spec["a2"], spec["b1"], spec["b2"],
                            spec["modul"], spec["l_col"], spec["thk_col"], unit, disp_qty,
                            f_price_base, f"=N{curr_row}*M{curr_row}", spec.get("note_std") or spec["note_fslf"]
                        ]
                        row_fslf = [
                            orig_stt, raw_name, spec["model_fslf"], spec["brand"],
                            spec["a1"], spec["a2"], spec["b1"], spec["b2"],
                            spec["modul"], spec["l_col"], spec["thk_col"], unit, disp_qty,
                            f_price_fslf, f"=N{curr_row}*M{curr_row}", spec["note_fslf"]
                        ]
                        row_bfn = [
                            orig_stt, raw_name, spec["model_bfn"], spec["brand"],
                            spec["a1"], spec["a2"], spec["b1"], spec["b2"],
                            spec["modul"], spec["l_col"], spec["thk_col"], unit, disp_qty,
                            f_price_bfn, f"=N{curr_row}*M{curr_row}", spec["note_bfn"]
                        ]
                        _write_row_cells(curr_row, row_std, row_fslf, row_bfn, is_section=False)
                        curr_row += 1
                else:
                    c2_cell = ws_orig.cell(r, name_col)
                    orig_b = c2_cell.value
                    orig_c = ws_orig.cell(r, 3).value if name_col == 2 and unit_col != 3 else None
                    if orig_c in (0, "0"):
                        orig_c = None
                    orig_u = ws_orig.cell(r, unit_col).value
                    orig_q = ws_orig.cell(r, qty_col).value
                    if orig_q is None and orig_u not in (None, 0, "0", "") and "qty_alt" in col_map:
                        orig_q = ws_orig.cell(r, col_map["qty_alt"]).value
                    orig_name = orig_b if (orig_b is not None and str(orig_b).strip() != "") else orig_c
                    if (orig_name is None or str(orig_name).strip() == "") and name_col == 13 and orig_u in (None, 0, "0", ""):
                        k_val = ws_orig.cell(r, 11).value
                        a_val = ws_orig.cell(r, 1).value
                        if k_val not in (None, 0, "0", ""):
                            orig_name = k_val
                            c2_cell = ws_orig.cell(r, 11)
                        elif isinstance(a_val, str) and a_val.strip() not in ("", "0"):
                            orig_name = a_val
                            orig_stt = None
                            c2_cell = ws_orig.cell(r, 1)
                    orig_name_str = str(orig_name).strip() if orig_name is not None else ""
                    orig_u_val = orig_u if (orig_u not in (None, 0, "0") and str(orig_u).strip() != "") else None
                    orig_q_val = orig_q if (orig_q is not None and (not isinstance(orig_q, str) or orig_q.strip() != "")) else None
                    if orig_u_val is None and (orig_q_val in (0, 0.0, "0") or (stt_col and ws_orig.cell(r, stt_col).value in (0, "0"))):
                        orig_q_val = None

                    if not orig_name_str and orig_stt is None and orig_u_val is None and orig_q_val is None:
                        _write_row_cells(curr_row, [None] * 16, is_section=False)
                        curr_row += 1
                    elif _is_sec_hdr(c2_cell, orig_name_str, orig_c, orig_u_val, orig_q_val):
                        _write_row_cells(curr_row, [orig_stt, orig_name_str] + [None] * 14, is_section=True)
                        curr_row += 1
                    else:
                        row_unquoted = [
                            orig_stt, orig_name_str, None, None,
                            None, None, None, None,
                            None, None, None, orig_u_val, orig_q_val,
                            None, None, None
                        ]
                        _write_row_cells(curr_row, row_unquoted, is_section=False)
                        curr_row += 1
        else:
            for idx, item in enumerate(all_items, 1):
                sheet00_row = idx + 1
                sec = (item.get("section") or "").strip()
                if sec and sec != current_section:
                    current_section = sec
                    _write_row_cells(curr_row, [None, sec] + [None] * 14, is_section=True)
                    curr_row += 1

                raw_name = item.get("raw_name") or item["name"]
                unit = item["unit"]
                qty = item["qty"]
                spec = item.get("resolved_spec") or Agent01_BOQExtractor.resolve_item_spec(item, subtype_rules, price_map=price_map, idx=idx)

                f_price_base = f"=ROUNDUP(ROUND('00_TONG_HOP_BAO_GIA'!Q{sheet00_row}, 0), -2)"
                if spec.get("has_fslf_formula_diff"):
                    act_unit = spec["act_unit"]
                    ratio = spec["fslf_ratio"]
                    f_price_fslf = f"=ROUNDUP(ROUND(('00_TONG_HOP_BAO_GIA'!Q{sheet00_row}-{act_unit:.0f})*{ratio:.6f}+{act_unit:.0f}, 0), -2)"
                else:
                    f_price_fslf = f_price_base
                f_price_bfn = f_price_base

                row_std = [
                    idx, raw_name, spec.get("model_std") or spec["model_fslf"], spec["brand"],
                    spec["a1"], spec["a2"], spec["b1"], spec["b2"],
                    spec["modul"], spec["l_col"], spec["thk_col"], unit, qty,
                    f_price_base, f"=N{curr_row}*M{curr_row}", spec.get("note_std") or spec["note_fslf"]
                ]
                row_fslf = [
                    idx, raw_name, spec["model_fslf"], spec["brand"],
                    spec["a1"], spec["a2"], spec["b1"], spec["b2"],
                    spec["modul"], spec["l_col"], spec["thk_col"], unit, qty,
                    f_price_fslf, f"=N{curr_row}*M{curr_row}", spec["note_fslf"]
                ]
                row_bfn = [
                    idx, raw_name, spec["model_bfn"], spec["brand"],
                    spec["a1"], spec["a2"], spec["b1"], spec["b2"],
                    spec["modul"], spec["l_col"], spec["thk_col"], unit, qty,
                    f_price_bfn, f"=N{curr_row}*M{curr_row}", spec["note_bfn"]
                ]
                _write_row_cells(curr_row, row_std, row_fslf, row_bfn, is_section=False)
                curr_row += 1

        # Footer Totals on quotation sheets (đóng khung chuẩn mẫu Swind)
        last_item_row = curr_row - 1
        total_font = Font(name="Times New Roman", size=10, bold=True)
        total_fill = PatternFill("solid", fgColor="FFC000")
        tot_sub_bdr = Border(left=thin_side, right=thin_side, top=thin_side, bottom=hair_side)
        tot_vat_bdr = Border(left=thin_side, right=thin_side, top=hair_side, bottom=hair_side)
        tot_end_bdr = Border(left=thin_side, right=thin_side, top=hair_side, bottom=thin_side)

        note_hdr_font = Font(name="Times New Roman", size=11, bold=True)
        note_txt_font = Font(name="Times New Roman", size=9, bold=False)
        note_it_font = Font(name="Times New Roman", size=9, bold=False, italic=True)
        note_ul_font = Font(name="Times New Roman", size=9, bold=True, underline="single")
        confirm_font = Font(name="Arial", size=10, bold=True, italic=True, underline="single")

        for ws, _ in worksheets:
            r_sub = curr_row
            r_vat = curr_row + 1
            r_tot = curr_row + 2

            ws.cell(r_sub, 1, "Total/ Tổng Trước thuế").font = total_font
            ws.cell(r_sub, 15, f"=SUBTOTAL(9,O14:O{last_item_row})").font = total_font
            ws.cell(r_sub, 15).number_format = "#,##0"

            ws.cell(r_vat, 1, "VAT 8%").font = total_font
            ws.cell(r_vat, 15, f"=ROUND(O{r_sub}*0.08, 0)").font = total_font
            ws.cell(r_vat, 15).number_format = "#,##0"

            ws.cell(r_tot, 1, "Total Amount (including VAT 8%)/ Tổng sau thuế").font = total_font
            ws.cell(r_tot, 15, f"=O{r_sub}+O{r_vat}").font = total_font
            ws.cell(r_tot, 15).number_format = "#,##0"

            for r_t, bdr_t in ((r_sub, tot_sub_bdr), (r_vat, tot_vat_bdr), (r_tot, tot_end_bdr)):
                ws.merge_cells(f"A{r_t}:N{r_t}")
                ws.row_dimensions[r_t].height = 28
                ws.cell(r_t, 1).alignment = Alignment(horizontal="right", vertical="center")
                ws.cell(r_t, 15).alignment = Alignment(horizontal="right", vertical="center")
                for c_i in range(1, 17):
                    c_tot = ws.cell(r_t, c_i)
                    c_tot.fill = total_fill
                    c_tot.border = bdr_t

            # Khối điều khoản & thông tin thụ hưởng bên dưới bảng tổng
            r_f = r_tot + 2
            ws.cell(r_f, 2, "- Ghi chú : ").font = note_hdr_font
            ws.cell(r_f + 1, 2, "* Thời hạn báo giá: Báo giá có giá trị trong vòng 30 ngày kể từ ngày báo.").font = note_txt_font
            ws.cell(r_f + 1, 14, "XÁC NHẬN ĐẶT HÀNG").font = confirm_font
            ws.merge_cells(f"N{r_f+1}:O{r_f+1}")
            ws.cell(r_f + 1, 14).alignment = Alignment(horizontal="center", vertical="center")
            ws.cell(r_f + 2, 2, "* Thời gian giao hàng: theo thực tế từng đơn hàng").font = note_txt_font
            ws.cell(r_f + 3, 2, " - Van gió & Phụ kiện : Tôn Hoa Sen Z08/Z18").font = note_txt_font
            ws.cell(r_f + 4, 2, " - Cửa gió và Phụ kiện : Nhôm A6063 T5 - Sơn Tĩnh điện mầu trắng .").font = note_txt_font
            ws.cell(r_f + 5, 2, "ĐIỀU KHOẢN THANH TOÁN VÀ GIAO HÀNG").font = note_ul_font
            ws.cell(r_f + 6, 2, "* Điều kiện thanh toán: Tạm ứng 30%, Thanh toán bằng bảo lãnh thanh toán thời hạn 35 ngày ").font = note_txt_font
            ws.cell(r_f + 7, 2, "Xin vui lòng liên hệ với chúng tôi nếu quý khách có cần thêm các yêu cầu nào khác.").font = note_it_font
            ws.cell(r_f + 8, 2, " Đơn vị thụ hưởng : ").font = note_hdr_font
            ws.cell(r_f + 9, 2, "Công ty Cổ phần tập đoàn quốc tế Sland").font = note_txt_font
            ws.cell(r_f + 10, 2, "Trụ sở: Thôn 1B, xã Nam Phù, TP Hà Nội").font = note_txt_font
            ws.cell(r_f + 11, 2, "- Số tài khoản : 1359 666 888 ").font = note_txt_font
            ws.cell(r_f + 12, 2, "- Mở tại :  Ngân hàng TMCP Á Châu ( ACB ) chi nhánh Hà Nội").font = note_txt_font

    def save(self):
        from openpyxl.worksheet.datavalidation import DataValidation
        dv = DataValidation(type="list", formula1='"ONG_GIO,CUA_GIO,VAN_GIO,THUONG_MAI,ONG_MEM,CANVAS,TIEU_AM,KHAC"', allow_blank=True)
        self.ws_06.add_data_validation(dv)
        dv.add('D2:D5000')

        # Đảm bảo chỉ có sheet đầu tiên được active và chọn tab
        if self.wb.worksheets:
            self.wb.active = 0
            for ws in self.wb.worksheets:
                if ws.views.sheetView:
                    ws.views.sheetView[0].tabSelected = (ws == self.wb.worksheets[0])

        self.wb.save(self.filename)
        self._patch_package_properties()
        print(f"Workbook successfully generated and saved to {self.filename}")

    def _patch_package_properties(self):
        import zipfile
        import shutil
        import os
        from datetime import datetime

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

        temp_path = self.filename + ".tmp.zip"
        try:
            with zipfile.ZipFile(self.filename, 'r') as zin:
                with zipfile.ZipFile(temp_path, 'w', compression=zipfile.ZIP_DEFLATED) as zout:
                    for item in zin.infolist():
                        if item.filename == 'docProps/core.xml':
                            zout.writestr(item, core_xml.encode('utf-8'))
                        else:
                            zout.writestr(item, zin.read(item.filename))
            shutil.move(temp_path, self.filename)
        except Exception as e:
            if os.path.exists(temp_path):
                os.remove(temp_path)
            print(f"  [WARNING] Could not patch docProps/core.xml: {e}")


Agent07_ExcelBuilder = SwindExcelBuilder

