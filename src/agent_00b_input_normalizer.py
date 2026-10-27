"""
Agent 00B - Input Normalizer (Chuẩn hóa Đầu vào BOQ)
=====================================================
Nhiệm vụ: Nhận file BOQ đầu vào (Excel/PDF/Ảnh) ở BẤT KỲ FORMAT nào,
phân tích cấu trúc, chuẩn hóa về format Swind chuẩn trước khi đưa vào
Agent 01 (BOQ Extractor).

Pipeline: Input → Agent 00B → Agent 01 → Agent 02..08

4 Module chính:
  M1: Format Detector & Classifier
  M2: Structure Normalizer
  M3: Validation & Confidence Gate
  M4: Learning Loop (format_learning_db.json)

Kiến trúc: Agent 00B chạy TRƯỚC Agent 01 trong run_master_pipeline().
Nếu file đã chuẩn → pass-through (không đổi gì).
Nếu file cần normalize → tạo file _NORMALIZED.xlsx → Agent 01 đọc file mới.
"""

import os
import re
import json
import unicodedata
import hashlib
from datetime import datetime
from enum import Enum
from typing import Dict, List, Tuple, Optional, Any

import openpyxl
from openpyxl.utils import get_column_letter

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

class FormatType(Enum):
    STANDARD_BOQ = "STANDARD_BOQ"              # Format chuẩn Swind, pass-through
    SEMI_STANDARD = "SEMI_STANDARD"            # Gần chuẩn nhưng thiếu section headers
    CUSTOM_FORMAT = "CUSTOM_FORMAT"            # Format khách hàng hoàn toàn khác (Sowitech, etc.)
    ORDER_MULTI_BATCH = "ORDER_MULTI_BATCH"    # Phiếu đặt hàng nhiều đợt (Lần N)
    TRANSPOSED = "TRANSPOSED"                  # Bảng ngang (items theo cột, không theo dòng)
    PRICE_COMPARISON = "PRICE_COMPARISON"      # Bảng so giá đối thủ
    CONTRACT_EMBEDDED = "CONTRACT_EMBEDDED"    # BOQ lồng trong hợp đồng/phụ lục

class ConfidenceLevel(Enum):
    HIGH = "HIGH"       # ≥80% parse rate → chạy tự động
    MEDIUM = "MEDIUM"   # 50-80% parse rate → cảnh báo, hỏi user
    LOW = "LOW"         # <50% → DỪNG LẠI

# Keywords nhận diện
NAME_KEYWORDS = ("sản phẩm", "hạng mục", "quy cách", "công tác", "công việc", "nội dung",
                 "mô tả", "tên vật tư", "tên vật liệu", "danh mục", "tên hàng",
                 "vật tư yêu cầu", "mục", "hàng hóa", "vật liệu",
                 "description", "item", "material", "particulars", "品名", "规格")
QTY_KEYWORDS = ("số lượng", "q'ty", "qty", "khối lượng", "sl", "kl diễn giải",
                "kl đặt", "kl tổng", "kl", "lũy kế", "cần về", "đặt hàng",
                "sl đặt", "cung cấp đợt này", "yêu cầu cấp",
                "count", "quantity", "nos", "수량", "数量")
UNIT_KEYWORDS = ("unit", "đơn vị", "đvt", "đv tính", "ea", "nr")
REMARKS_KEYWORDS = ("ghi chú", "remarks", "remark", "note", "chú thích")
SECTION_KEYWORDS = ("ống gió tôn dày", "ống gió inox", "ống gió tôn mạ",
                    "phụ kiện ống gió", "vật tư phần gió", "hệ thống",
                    "ống gió tôn hoa sen")
ORDER_KEYWORDS = ("đặt hàng", "phiếu yêu cầu", "rop", "lần 1", "lần 2",
                  "lần 3", "lần 4", "lần 5", "lần 6", "lần 7", "lần 8")
CONSUMABLE_KEYWORDS = ("băng dính", "keo silicol", "keo silicon", "vít tự khoan",
                       "ốc vít", "foam xịt", "bọt nở", "đai treo", "ty treo",
                       "quang treo", "ca xe", "boom lift", "nhân công", "cẩu hàng", "giàn giáo")
EXCEL_ERROR_PREFIXES = ("#REF!", "#VALUE!", "#NAME?", "#N/A", "#DIV/0!", "#NUM!", "#NULL!")
DUCT_ITEM_PATTERN = re.compile(
    r'(ống|côn|cút|chân rẽ|hộp gió|măng|chếch|bịt đầu|bịt ống|nối ống|tê đầu ống|tê đều ống|tiêu âm|nối mềm|canvas)',
    re.IGNORECASE
)
DIM_PATTERN = re.compile(r'([wWaAbB]?\s*\d{2,4}\s*[xX×*]\s*[hHbBwW]?\s*\d{2,4}|[dDØø][nN]?\s*\d{2,4})')

# ---------------------------------------------------------------------------
# Module 1: Format Detector & Classifier
# ---------------------------------------------------------------------------

class FormatDetector:
    """Phân tích cấu trúc file Excel và phân loại format."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.wb = openpyxl.load_workbook(filepath, data_only=True)
        self.results = {}  # per-sheet analysis

    def analyze_all_sheets(self) -> Dict[str, Any]:
        """Phân tích tất cả sheets hiển thị (visible) trong workbook (bỏ qua sheet ẩn & sheet bìa/thông tin)."""
        from concurrent.futures import ThreadPoolExecutor
        visible_sheets = [s for s in self.wb.sheetnames if getattr(self.wb[s], "sheet_state", "visible") == "visible"]
        cand_sheets = visible_sheets if visible_sheets else list(self.wb.sheetnames)
        info_kws = ("bìa", "bia", "cover", "mục lục", "muc luc", "index", "toc", "thuyết minh", "thuyet minh", "điều khoản", "dieu khoan", "clarification", "làm rõ", "vtdv", "summary", "recap")
        if len(cand_sheets) > 1:
            filtered = [s for s in cand_sheets if not any(k in s.lower().strip() for k in info_kws)]
            if filtered:
                cand_sheets = filtered
        valid_sheets = [s for s in cand_sheets if self.wb[s].max_row is not None and self.wb[s].max_row >= 3]
        if len(valid_sheets) > 1:
            with ThreadPoolExecutor(max_workers=min(len(valid_sheets), 3)) as ex:
                mapped = list(ex.map(lambda sn: (sn, self._analyze_sheet(self.wb[sn], sn)), valid_sheets))
            for sn, res in mapped:
                self.results[sn] = res
        else:
            for sheet_name in valid_sheets:
                self.results[sheet_name] = self._analyze_sheet(self.wb[sheet_name], sheet_name)
        return self.results

    def _analyze_sheet(self, ws, sheet_name: str) -> Dict[str, Any]:
        """Phân tích cấu trúc 1 sheet."""
        analysis = {
            "sheet_name": sheet_name,
            "max_row": ws.max_row,
            "max_col": ws.max_column,
            "format_type": FormatType.STANDARD_BOQ,
            "confidence": 0.0,
            "header_row": None,
            "col_map": {},
            "has_section_headers": False,
            "has_lan_n_columns": False,
            "merged_cell_count": len(ws.merged_cells.ranges) if hasattr(ws, 'merged_cells') else 0,
            "detected_company": None,
            "issues": [],
            "data_row_count": 0,
            "duct_item_count": 0,
        }

        # 1. Scan header area (rows 1-25)
        header_info = self._scan_header_area(ws)
        analysis.update(header_info)

        # 2. Check for order sheet (Lần N columns)
        if self._check_order_sheet(ws):
            analysis["format_type"] = FormatType.ORDER_MULTI_BATCH
            analysis["has_lan_n_columns"] = True
            return analysis

        # 3. Check for section headers
        h_row = analysis.get("header_row") if analysis.get("header_row") is not None else 10
        analysis["has_section_headers"] = self._check_section_headers(ws, h_row)

        # 4. Detect company/format
        analysis["detected_company"] = self._detect_company(ws)

        # 5. Count data rows and duct items
        data_stats = self._count_data_rows(ws, h_row, analysis.get("col_map", {}))
        analysis.update(data_stats)

        # 6. Determine format type
        analysis["format_type"] = self._classify_format(analysis)
        analysis["confidence"] = self._compute_confidence(analysis)

        return analysis

    def _scan_header_area(self, ws) -> Dict:
        """Scan rows 1-40 to find header row and column mapping (hỗ trợ merged cells & fallback detect_boq_header)."""
        result = {"header_row": None, "col_map": {}}

        # Flatten merged cells in header area (rows 1..40)
        merged_lookup = {}
        if hasattr(ws, "merged_cells"):
            for m_range in ws.merged_cells.ranges:
                if m_range.min_row <= 40:
                    top_val = ws.cell(m_range.min_row, m_range.min_col).value
                    if top_val is not None:
                        for mr in range(m_range.min_row, min(41, m_range.max_row + 1)):
                            for mc in range(m_range.min_col, min(35, m_range.max_col + 1)):
                                merged_lookup[(mr, mc)] = top_val

        for r in range(1, min(41, ws.max_row + 1)):
            row_texts = {}
            for c in range(1, min(30, ws.max_column + 1)):
                v = ws.cell(r, c).value
                if v is None and (r, c) in merged_lookup:
                    v = merged_lookup[(r, c)]
                if v is not None:
                    txt = unicodedata.normalize('NFC', str(v)).lower().strip()
                    txt = re.sub(r'\s+', ' ', txt)
                    row_texts[c] = txt

            if len(row_texts) < 2:
                continue

            found_name = False
            found_qty = False
            col_map = {}
            name_cands = []
            qty_cands = []
            first_price_col = min(
                (c for c, txt in row_texts.items() if any(pk in txt for pk in ("đơn giá", "price")) or txt in ("đg", "giá")),
                default=9999
            )

            for c, txt in row_texts.items():
                is_strict_qty = txt.startswith(("kl ", "sl ", "khối lượng", "số lượng", "q'ty", "qty"))
                if not is_strict_qty and any(kw in txt for kw in NAME_KEYWORDS):
                    name_cands.append(c)
                    if "name" not in col_map:
                        col_map["name"] = c
                        found_name = True
                if any(kw in txt for kw in QTY_KEYWORDS) or (txt in ("tổng", "tổng số", "tổng cộng") and c < first_price_col):
                    qty_cands.append(c)
                    if "qty" not in col_map:
                        col_map["qty"] = c
                        found_qty = True
                if any(kw in txt for kw in UNIT_KEYWORDS) and "unit" not in col_map:
                    col_map["unit"] = c
                if any(kw in txt for kw in REMARKS_KEYWORDS) and "remarks" not in col_map:
                    col_map["remarks"] = c
                if "stt" in txt or txt in ("tt", "no", "no."):
                    col_map["stt"] = c

            if len(name_cands) > 1:
                col_map["name"] = max(
                    name_cands,
                    key=lambda nc: sum(
                        1 for rr in range(r + 1, min(r + 40, ws.max_row + 1))
                        if ws.cell(rr, nc).value not in (None, "")
                    )
                )

            # Nếu có nhiều cột qty candidate (VD: "KL diễn giải" và "KL tổng theo HĐ"), chọn cột có nhiều số dương nhất
            if len(qty_cands) > 1:
                best_qc = max(
                    qty_cands,
                    key=lambda qc: sum(
                        1 for rr in range(r + 1, min(r + 80, ws.max_row + 1))
                        if isinstance(ws.cell(rr, qc).value, (int, float)) and ws.cell(rr, qc).value > 0
                    )
                )
                col_map["qty"] = best_qc
                found_qty = True

            if found_name and found_qty:
                # GUARD: name và qty phải ở cột khác nhau
                if col_map.get("name") == col_map.get("qty"):
                    conflict_col = col_map["name"]
                    del col_map["name"]
                    found_name = False
                    for c2, txt2 in row_texts.items():
                        if c2 == conflict_col:
                            continue
                        if any(kw in txt2 for kw in NAME_KEYWORDS) and "name" not in col_map:
                            col_map["name"] = c2
                            found_name = True
                            break
                    if not found_name:
                        for c_cand in range(1, conflict_col):
                            if c_cand in row_texts:
                                col_map["name"] = c_cand
                                found_name = True
                                break
                        if not found_name:
                            col_map["name"] = 2
                            found_name = True

                if found_name and found_qty:
                    result["header_row"] = r
                    result["col_map"] = col_map

                    # Scan sub-header rows for dimension columns
                    for sub_r in range(r + 1, min(r + 3, ws.max_row + 1)):
                        for c in range(1, min(30, ws.max_column + 1)):
                            v = ws.cell(sub_r, c).value
                            if v is None:
                                continue
                            sv = re.sub(r'\s*\([^)]*\)', '', str(v).lower().strip()).strip()
                            if sv in ("w", "w1", "a1", "rộng"):
                                col_map["w"] = c
                            elif sv in ("h", "h1", "a2", "cao"):
                                col_map["h"] = c
                            elif sv in ("w2", "b1"):
                                col_map["w2"] = c
                            elif sv in ("h2", "b2"):
                                col_map["h2"] = c
                            elif sv in ("l", "l1", "dài"):
                                col_map["l"] = c
                            elif sv in ("r", "r(ø)"):
                                col_map["r_or_d"] = c
                    break

        # Fallback sang detect_boq_header (Tầng 2, 3, 4: Headerless, Price-only, Dimension pattern)
        if result["header_row"] is None:
            try:
                from swind_utils import detect_boq_header
                h_row, p_col_map, _, _, _ = detect_boq_header(ws)
                if h_row is not None and p_col_map.get("name"):
                    result["header_row"] = h_row
                    result["col_map"] = dict(p_col_map)
            except Exception:
                pass

        return result

    def _check_order_sheet(self, ws) -> bool:
        """Kiểm tra xem có phải phiếu đặt hàng nhiều đợt (có cột Lần N)."""
        for r in range(1, min(20, ws.max_row + 1)):
            for c in range(1, min(25, ws.max_column + 1)):
                v = ws.cell(r, c).value
                if v and isinstance(v, str):
                    txt = v.lower().strip()
                    if re.search(r'lần\s*\d+', txt):
                        return True
        # Check sheet name
        sheet_name = ws.title.lower() if ws.title else ""
        if any(kw in sheet_name for kw in ("rop", "đặt hàng", "order")):
            return True
        return False

    def _check_section_headers(self, ws, start_row: int) -> bool:
        """Kiểm tra xem có header phân nhóm 'Ống gió tôn dày X mm' không."""
        start = max(start_row or 5, 1)
        for r in range(start, min(start + 200, ws.max_row + 1)):
            if ws.row_dimensions[r].hidden:
                continue
            v = ws.cell(r, 2).value  # Cột B thường chứa section header
            if v:
                txt = unicodedata.normalize('NFC', str(v)).lower()
                if any(kw in txt for kw in SECTION_KEYWORDS):
                    return True
        return False

    def _detect_company(self, ws) -> Optional[str]:
        """Phát hiện công ty/đơn vị lập BOQ từ header."""
        company_patterns = {
            "sowitech": r'sowitech',
            "cand": r'c[aă]nd|canđ',
            "swind": r'swind|mpq',
            "hoa_binh": r'hòa bình|hoa binh',
            "coteccons": r'coteccons',
            "newtecons": r'newtecons',
            "unicons": r'unicons',
        }
        for r in range(1, min(15, ws.max_row + 1)):
            for c in range(1, min(20, ws.max_column + 1)):
                v = ws.cell(r, c).value
                if v:
                    txt = unicodedata.normalize('NFC', str(v)).lower()
                    for company, pattern in company_patterns.items():
                        if re.search(pattern, txt):
                            return company
        return None

    def _count_data_rows(self, ws, header_row: int, col_map: Dict) -> Dict:
        """Đếm số dòng data thực tế và ống gió."""
        name_col = col_map.get("name", 2)
        qty_col = col_map.get("qty")
        unit_col = col_map.get("unit")
        data_rows = 0
        duct_items = 0
        qty_nonzero = 0
        empty_streak = 0

        for r in range(header_row + 1, min(header_row + 500, ws.max_row + 1)):
            if ws.row_dimensions[r].hidden:
                continue
            name_v = ws.cell(r, name_col).value
            if not name_v:
                empty_streak += 1
                if empty_streak >= 40:
                    break
                continue
            empty_streak = 0
            name_str = unicodedata.normalize('NFC', str(name_v)).strip()
            if len(name_str) < 3:
                continue
            name_lower = name_str.lower()
            if any(kw in name_lower for kw in ("cộng tiền", "tiền vat", "tổng tiền", "tổng cộng",
                                                "ghi chú", "điều khoản", "xác nhận", "thanh toán")):
                continue
            data_rows += 1
            unit_v = str(ws.cell(r, unit_col).value or "").strip() if unit_col else ""
            is_consumable = any(ck in name_lower for ck in CONSUMABLE_KEYWORDS)
            is_equip = (unit_v == "Bộ") or any(
                ek in name_lower for ek in ("quạt", "bộ lọc", "máy lạnh", "dàn lạnh", "fcu", "pau", "ahu",
                                            "ống đồng", "ống nước", "ống nhựa", "upvc", "ppr", "van nước", "van bướm", "y lọc",
                                            "ống pvc", "pvc", "emt", "ống g.i", "ống gi", "ống luồn", "ống thép")
            )
            is_grille_or_damper = any(
                gk in name_lower for gk in ("cửa gió", "miệng gió", "louver", "côn trùng", "van ", "damper", "grille", "diffuser")
            )
            is_sec_hdr = ("cung cấp" in name_lower and "lắp đặt" in name_lower) or any(sk in name_lower for sk in SECTION_KEYWORDS)
            if not is_consumable and not is_equip and not is_grille_or_damper and not is_sec_hdr and DUCT_ITEM_PATTERN.search(name_str):
                duct_items += 1
            if qty_col:
                qty_v = ws.cell(r, qty_col).value
                if isinstance(qty_v, (int, float)) and qty_v > 0:
                    qty_nonzero += 1

        return {
            "data_row_count": data_rows,
            "duct_item_count": duct_items,
            "qty_nonzero_count": qty_nonzero,
            "qty_nonzero_rate": qty_nonzero / data_rows if data_rows > 0 else 0,
        }

    def _classify_format(self, analysis: Dict) -> FormatType:
        """Phân loại format dựa trên phân tích & kiểm thử thực tế với SwindBOQParser."""
        if analysis.get("has_lan_n_columns"):
            return FormatType.ORDER_MULTI_BATCH

        has_header = analysis.get("header_row") is not None
        has_sections = analysis.get("has_section_headers", False)
        qty_rate = analysis.get("qty_nonzero_rate", 0)
        data_rows = analysis.get("data_row_count", 0)
        duct_items = analysis.get("duct_item_count", 0)
        max_row = analysis.get("max_row", 0)

        if data_rows < 2:
            if max_row > 30 and data_rows == 0:
                analysis["issues"].append(
                    f"Sheet có {max_row} dòng nhưng không detect được data rows. "
                    "Có thể parser đọc nhầm cột SL (tất cả = 0)."
                )
                return FormatType.CUSTOM_FORMAT
            return FormatType.STANDARD_BOQ  # Truly empty/minimal sheet

        # Cross-check & Dry-run thực tế với detect_boq_header và SwindBOQParser
        needs_normalize_for_qty = False
        needs_normalize_for_ducts = False
        parser_mfg_valid = 0
        parser_duct_valid = 0
        try:
            from swind_utils import detect_boq_header
            from swind_boq_parser import SwindBOQParser as MPriceBOQParser
            _ws_check = self.wb[analysis["sheet_name"]]
            parser_result = detect_boq_header(_ws_check)
            parser_qty_col = parser_result[1].get("qty") if parser_result else None
            our_qty_col = analysis.get("col_map", {}).get("qty")
            h_row = analysis.get("header_row") if analysis.get("header_row") is not None else 10
            if parser_qty_col and our_qty_col and parser_qty_col != our_qty_col:
                parser_qty_count = 0
                our_qty_count = 0
                for r in range(h_row + 1, min(h_row + 60, _ws_check.max_row + 1)):
                    if _ws_check.row_dimensions[r].hidden:
                        continue
                    pv = _ws_check.cell(r, parser_qty_col).value
                    ov = _ws_check.cell(r, our_qty_col).value
                    if isinstance(pv, (int, float)) and pv > 0:
                        parser_qty_count += 1
                    if isinstance(ov, (int, float)) and ov > 0:
                        our_qty_count += 1
                if our_qty_count > parser_qty_count * 2 and our_qty_count >= 3:
                    needs_normalize_for_qty = True
                    analysis["issues"].append(
                        f"Parser sẽ chọn cột SL={parser_qty_col} ({parser_qty_count} items>0) "
                        f"nhưng cột {our_qty_col} có {our_qty_count} items>0. Cần normalize."
                    )

            # Dry-run SwindBOQParser trên sheet
            _parser = MPriceBOQParser(self.filepath, wb=self.wb)
            parsed_items = _parser.parse_sheet(analysis["sheet_name"])
            mfg_cats = ("CUA_GIO", "VAN_GIO", "ONG_GIO", "CANVAS", "TIEU_AM", "ONG_MEM")
            mfg_items = [it for it in parsed_items if it.get("category") in mfg_cats]
            parser_mfg_valid = sum(1 for it in mfg_items if (it.get("qty") or 0) > 0 or (it.get("ref_price") or 0) > 0)
            parser_duct_valid = sum(
                1 for it in mfg_items
                if it.get("category") in ("ONG_GIO", "TIEU_AM", "CANVAS", "ONG_MEM") and (it.get("qty") or 0) > 0
            )
            # Nếu sheet có nhiều dòng ống/phụ kiện nhưng parser bóc được rất ít do thiếu section header "Ống gió..."
            if duct_items >= 4 and parser_duct_valid < duct_items * 0.6:
                needs_normalize_for_ducts = True
                analysis["issues"].append(
                    f"Sheet có {duct_items} dòng ống/phụ kiện nhưng parser chỉ nhận diện được {parser_duct_valid} dòng. "
                    "Cần bổ sung section header 'Ống gió tôn dày...'."
                )
        except Exception:
            pass

        if needs_normalize_for_qty or needs_normalize_for_ducts:
            return FormatType.CUSTOM_FORMAT

        # Nếu SwindBOQParser đã bóc tách tốt (đủ SL>0 và không rơi rớt ống gió) → STANDARD_BOQ (Pass-through!)
        if parser_mfg_valid >= 2 and (parser_mfg_valid >= data_rows * 0.5 or parser_mfg_valid >= 10):
            analysis["data_row_count"] = max(data_rows, parser_mfg_valid)
            analysis["qty_nonzero_rate"] = max(qty_rate, 0.9)
            return FormatType.STANDARD_BOQ

        if has_header and has_sections and qty_rate > 0.5:
            return FormatType.STANDARD_BOQ

        if has_header and not has_sections and qty_rate > 0.5:
            return FormatType.SEMI_STANDARD

        if has_header and qty_rate < 0.1 and data_rows > 10:
            analysis["issues"].append(
                f"Chỉ {qty_rate*100:.0f}% items có SL>0 ({data_rows} dòng data). "
                "Có thể parser đọc nhầm cột SL."
            )
            return FormatType.CUSTOM_FORMAT

        if not has_header:
            return FormatType.CUSTOM_FORMAT

        if has_header and not has_sections and qty_rate > 0.1:
            return FormatType.SEMI_STANDARD

        return FormatType.CUSTOM_FORMAT

    def _compute_confidence(self, analysis: Dict) -> float:
        """Tính confidence score cho kết quả phân tích."""
        score = 0.0
        if analysis.get("header_row") is not None:
            score += 0.3
        if analysis.get("has_section_headers") or analysis.get("format_type") == FormatType.STANDARD_BOQ:
            score += 0.2
        qty_rate = analysis.get("qty_nonzero_rate", 0)
        score += min(qty_rate, 1.0) * 0.3
        if analysis.get("col_map", {}).get("name"):
            score += 0.1
        if analysis.get("col_map", {}).get("unit") or analysis.get("format_type") == FormatType.STANDARD_BOQ:
            score += 0.1
        return round(score, 2)

# ---------------------------------------------------------------------------
# Module 2: Structure Normalizer
# ---------------------------------------------------------------------------

class StructureNormalizer:
    """Chuẩn hóa cấu trúc BOQ về format Swind chuẩn."""

    STANDARD_HEADER = {
        'A6': '\nSTT', 'B6': '\nDanh mục sản phẩm', 'C6': 'Model',
        'D6': 'Thương hiệu', 'E6': 'Kích thước (mm)', 'I6': 'Modul',
        'J6': 'L', 'K6': 'Độ dày\n(m)', 'L6': 'Unit\nĐơn vị',
        'M6': "Q'ty\nSố lượng", 'N6': 'Prices\nĐơn giá',
        'O6': 'Total price\nThành tiền', 'P6': 'Remarks\nGhi chú',
    }
    STANDARD_SUB_HEADER = {
        'E7': 'A1', 'F7': 'A2', 'G7': 'B1', 'H7': 'B2',
        'E8': 'Face size', 'G8': 'Neck size',
    }

    def __init__(self, source_filepath: str, analyses: Dict[str, Any]):
        self.source = source_filepath
        self.analyses = analyses
        self.wb_src = openpyxl.load_workbook(source_filepath, data_only=True)

    def normalize(self) -> Tuple[str, Dict]:
        """
        Chuẩn hóa file BOQ. Trả về (output_filepath, normalization_report).
        Nếu không cần normalize → trả về (source_filepath, report).
        """
        needs_normalize = False
        sheets_to_normalize = []
        sheets_passthrough = []

        for sheet_name, analysis in self.analyses.items():
            fmt = analysis.get("format_type", FormatType.STANDARD_BOQ)
            if isinstance(fmt, str):
                fmt = FormatType(fmt)
            if fmt in (FormatType.SEMI_STANDARD, FormatType.CUSTOM_FORMAT):
                needs_normalize = True
                sheets_to_normalize.append((sheet_name, analysis))
            else:
                sheets_passthrough.append(sheet_name)

        if not needs_normalize:
            return self.source, {"action": "pass-through", "reason": "All sheets are standard format"}

        # Tạo file normalized
        output_path = re.sub(r'\.xlsx?$', '_NORMALIZED.xlsx', self.source, flags=re.IGNORECASE)
        if output_path == self.source:
            output_path = self.source + "_NORMALIZED.xlsx"
        wb_new = openpyxl.Workbook()
        # Remove default sheet
        if 'Sheet' in wb_new.sheetnames:
            del wb_new['Sheet']

        report = {"action": "normalized", "sheets": {}}

        # Normalize từng sheet cần xử lý
        for sheet_name, analysis in sheets_to_normalize:
            ws_src = self.wb_src[sheet_name]
            fmt = analysis.get("format_type", FormatType.STANDARD_BOQ)
            if isinstance(fmt, str):
                fmt = FormatType(fmt)

            if fmt == FormatType.SEMI_STANDARD:
                ws_new = wb_new.create_sheet(sheet_name)
                result = self._normalize_semi_standard(ws_src, ws_new, analysis)
            elif fmt == FormatType.CUSTOM_FORMAT:
                ws_new = wb_new.create_sheet(sheet_name)
                result = self._normalize_custom_format(ws_src, ws_new, analysis)
            elif fmt == FormatType.ORDER_MULTI_BATCH:
                ws_new = wb_new.create_sheet(sheet_name)
                result = self._normalize_order_sheet(ws_src, ws_new, analysis)
            else:
                ws_new = wb_new.create_sheet(sheet_name)
                result = self._copy_sheet(ws_src, ws_new)

            report["sheets"][sheet_name] = result

        # Copy pass-through sheets
        for sheet_name in sheets_passthrough:
            ws_src = self.wb_src[sheet_name]
            ws_new = wb_new.create_sheet(sheet_name)
            self._copy_sheet(ws_src, ws_new)
            report["sheets"][sheet_name] = {"action": "pass-through"}

        wb_new.save(output_path)
        report["output_file"] = output_path
        return output_path, report

    def _write_standard_header(self, ws):
        """Ghi header chuẩn Swind vào sheet."""
        for cell_ref, value in self.STANDARD_HEADER.items():
            ws[cell_ref] = value
        for cell_ref, value in self.STANDARD_SUB_HEADER.items():
            ws[cell_ref] = value

    def _normalize_semi_standard(self, ws_src, ws_new, analysis: Dict) -> Dict:
        """
        Normalize sheet gần chuẩn: copy data + thêm section headers cho ống thẳng.
        """
        self._write_standard_header(ws_new)

        header_row = analysis.get("header_row", 10) or 10
        col_map = analysis.get("col_map", {})
        name_col = col_map.get("name", 2)
        qty_col = col_map.get("qty", 13)
        unit_col = col_map.get("unit", 12)

        out_row = 10
        items_copied = 0
        added_section = False

        # Thêm section header mặc định
        ws_new.cell(out_row, 1, value='B')
        ws_new.cell(out_row, 2, value='Vật tư phần gió')
        out_row += 1
        ws_new.cell(out_row, 1, value=1)
        ws_new.cell(out_row, 2, value='Ống gió tôn dày 0.58mm')
        out_row += 1
        added_section = True

        stt = 0
        empty_streak = 0
        for r in range(header_row + 1, ws_src.max_row + 1):
            if ws_src.row_dimensions[r].hidden:
                continue
            name_v = ws_src.cell(r, name_col).value
            if not name_v:
                empty_streak += 1
                if empty_streak >= 40:
                    break
                continue
            empty_streak = 0
            name_str = str(name_v).strip()
            if len(name_str) < 2:
                continue

            # Skip footer/summary rows
            name_lower = name_str.lower()
            if any(kw in name_lower for kw in ("cộng tiền", "tiền vat", "tổng tiền", "ghi chú",
                                                "điều khoản", "xác nhận", "thanh toán")):
                continue

            # Check if this is a section header (has name but no qty/unit)
            qty_v = ws_src.cell(r, qty_col).value if qty_col else None
            unit_v = ws_src.cell(r, unit_col).value if unit_col else None
            is_section = (qty_v is None or str(qty_v).strip() in ('', '0')) and \
                         (unit_v is None or str(unit_v).strip() == '')

            if is_section and any(kw in name_lower for kw in SECTION_KEYWORDS):
                ws_new.cell(out_row, 1, value='')
                ws_new.cell(out_row, 2, value=name_str)
                out_row += 1
                continue

            # Data row
            stt += 1
            qty = float(qty_v) if isinstance(qty_v, (int, float)) else 0
            unit = str(unit_v).strip() if unit_v else 'cái'

            ws_new.cell(out_row, 1, value=stt)
            ws_new.cell(out_row, 2, value=name_str)
            ws_new.cell(out_row, 12, value=unit)
            ws_new.cell(out_row, 13, value=qty)
            ws_new.cell(out_row, 15, value=0)

            # Copy dimension columns if available
            for dim_key, target_col in [("w", 5), ("h", 6), ("w2", 7), ("h2", 8), ("l", 10), ("thickness", 11)]:
                if dim_key in col_map:
                    dv = ws_src.cell(r, col_map[dim_key]).value
                    if isinstance(dv, (int, float)):
                        ws_new.cell(out_row, target_col, value=dv)
                    elif isinstance(dv, str) and re.match(r'^[\d.]+$', dv.strip()):
                        ws_new.cell(out_row, target_col, value=float(dv.strip()))

            # Copy remarks
            remarks_col = col_map.get("remarks")
            if remarks_col:
                rv = ws_src.cell(r, remarks_col).value
                if rv:
                    ws_new.cell(out_row, 16, value=str(rv))

            out_row += 1
            items_copied += 1

        return {
            "action": "semi_standard_normalize",
            "items_copied": items_copied,
            "section_headers_added": added_section,
        }

    def _normalize_custom_format(self, ws_src, ws_new, analysis: Dict) -> Dict:
        """
        Normalize format hoàn toàn khác: phát hiện cột nguồn, remap sang chuẩn.
        Xử lý đặc biệt:
          - Section header "Ống gió tôn dày X mm" / "Ống gió Inox"
          - Skip equipment (Bộ), footer rows
          - Kích thước lấy từ tên item (KHÔNG đặt vào cột E,F cho ống gió)
          - Tự detect cột qty tối ưu (nhiều số dương nhất)
        """
        self._write_standard_header(ws_new)

        # Tìm cột thực tế chứa SL (scan nhiều cột tìm cột có nhiều số dương nhất)
        header_row = analysis.get("header_row") if analysis.get("header_row") is not None else self._find_header_row_heuristic(ws_src)
        col_map = analysis.get("col_map", {})
        name_col = col_map.get("name", 2)

        # Nếu qty_nonzero_rate thấp → thử tìm cột qty khác
        if analysis.get("qty_nonzero_rate", 0) < 0.3:
            better_qty_col = self._find_best_qty_column(ws_src, header_row, name_col)
            if better_qty_col:
                col_map["qty"] = better_qty_col

        qty_col = col_map.get("qty")
        unit_col = col_map.get("unit")
        remarks_col = col_map.get("remarks")

        # ------ Thu thập tất cả data items trước ------
        items = []
        empty_streak = 0
        for r in range(header_row + 1, ws_src.max_row + 1):
            if ws_src.row_dimensions[r].hidden:
                continue
            name_v = ws_src.cell(r, name_col).value
            if not name_v:
                empty_streak += 1
                if empty_streak >= 40:
                    break
                continue
            empty_streak = 0
            name_str = unicodedata.normalize('NFC', str(name_v).strip())
            if len(name_str) < 2:
                continue

            name_lower = name_str.lower()
            # Skip footer / boilerplate
            if any(kw in name_lower for kw in ("cộng tiền", "tiền vat", "tổng tiền", "tổng cộng",
                                                "ghi chú", "điều khoản", "xác nhận",
                                                "thanh toán", "chúng tôi chuyên",
                                                "xin vui lòng", "hàng hóa mới",
                                                "vật liệu sử dụng", "báo giá đã",
                                                "lưu ý nếu", "thời gian giao",
                                                "thời hạn báo", "điều kiện thanh",
                                                "tên tài khoản", "tài khoản cá nhân",
                                                "người làm đơn", "chỉ huy trưởng")):
                continue

            unit_v = ws_src.cell(r, unit_col).value if unit_col else None
            unit_str = str(unit_v).strip() if unit_v else ''
            qty_v = ws_src.cell(r, qty_col).value if qty_col else None
            qty = float(qty_v) if isinstance(qty_v, (int, float)) else 0

            # Phân loại dòng: section header, equipment, consumable, hoặc data item
            is_equipment = (unit_str == 'Bộ') or name_lower.startswith(('quạt ', 'bộ lọc'))
            is_consumable = any(ck in name_lower for ck in CONSUMABLE_KEYWORDS)
            is_section_header = False

            # Dòng section header: có tên nhưng qty=0 và không có unit data
            if (qty == 0 or qty_v is None) and (unit_str == '' or unit_str == '0'):
                is_section_header = True
            if "cung cấp" in name_lower and "lắp đặt" in name_lower:
                is_section_header = True

            items.append({
                'row': r,
                'name': name_str,
                'name_lower': name_lower,
                'unit': unit_str if unit_str else 'cái',
                'qty': qty,
                'is_equipment': is_equipment,
                'is_consumable': is_consumable,
                'is_section_header': is_section_header,
            })

        # ------ Phân loại material sections ------
        material_sections = []  # [(start_idx, material_type, section_name)]
        for i, item in enumerate(items):
            if not item['is_section_header']:
                continue
            nl = item['name_lower']
            if 'inox' in nl:
                material_sections.append((i, 'inox', item['name']))
            elif 'cung cấp' in nl and ('tôn' in nl or 'mạ kẽm' in nl):
                material_sections.append((i, 'ton', item['name']))
            elif 'ống gió tôn' in nl or 'tôn mạ kẽm' in nl:
                material_sections.append((i, 'ton', item['name']))

        # ------ Ghi output ------
        out_row = 10
        stt = 0
        items_copied = 0
        section_added = False
        current_material = None

        for i, item in enumerate(items):
            if item['is_equipment'] or item.get('is_consumable'):
                continue

            if item['is_section_header']:
                nl = item['name_lower']
                if 'inox' in nl:
                    current_material = 'inox'
                    ws_new.cell(out_row, 1, value='')
                    ws_new.cell(out_row, 2, value='Hệ thống ống gió Inox')
                    out_row += 1
                    ws_new.cell(out_row, 1, value=1)
                    ws_new.cell(out_row, 2, value='Ống gió Inox dày 0.8mm')
                    out_row += 1
                    section_added = True
                elif ('cung cấp' in nl and ('tôn' in nl or 'mạ kẽm' in nl)) or \
                     'ống gió tôn' in nl or 'tôn mạ kẽm' in nl:
                    current_material = 'ton'
                    ws_new.cell(out_row, 1, value='B')
                    ws_new.cell(out_row, 2, value='Vật tư phần gió')
                    out_row += 1
                    ws_new.cell(out_row, 1, value=1)
                    ws_new.cell(out_row, 2, value='Ống gió tôn dày 0.58mm')
                    out_row += 1
                    section_added = True
                continue

            if not section_added:
                ws_new.cell(out_row, 1, value='B')
                ws_new.cell(out_row, 2, value='Vật tư phần gió')
                out_row += 1
                ws_new.cell(out_row, 1, value=1)
                ws_new.cell(out_row, 2, value='Ống gió tôn dày 0.58mm')
                out_row += 1
                section_added = True
                current_material = 'ton'

            stt += 1
            ws_new.cell(out_row, 1, value=stt)
            ws_new.cell(out_row, 2, value=item['name'])
            ws_new.cell(out_row, 12, value=item['unit'])
            ws_new.cell(out_row, 13, value=item['qty'])
            ws_new.cell(out_row, 15, value=0)

            remark_val = None
            if remarks_col:
                rv = ws_src.cell(item['row'], remarks_col).value
                if rv and isinstance(rv, str):
                    rv_s = rv.strip()
                    if len(rv_s) > 1 and not rv_s.upper().startswith(EXCEL_ERROR_PREFIXES) and not rv_s.startswith("#"):
                        remark_val = rv_s
            if not remark_val:
                for scan_c in range(ws_src.max_column, name_col, -1):
                    if scan_c == unit_col:
                        continue
                    rv = ws_src.cell(item['row'], scan_c).value
                    if rv and isinstance(rv, str):
                        rv_s = rv.strip()
                        if len(rv_s) > 3 and not rv_s.upper().startswith(EXCEL_ERROR_PREFIXES) and not rv_s.startswith("#"):
                            remark_val = rv_s
                            break
            if remark_val:
                ws_new.cell(out_row, 16, value=remark_val)

            out_row += 1
            items_copied += 1

        return {
            "action": "custom_format_normalize",
            "items_copied": items_copied,
            "qty_column_used": qty_col,
            "material_sections_detected": current_material is not None,
        }

    def _normalize_order_sheet(self, ws_src, ws_new, analysis: Dict) -> Dict:
        """
        Normalize phiếu đặt hàng nhiều đợt.
        """
        self._copy_sheet(ws_src, ws_new)
        return {
            "action": "order_sheet_detected",
            "needs_user_input": True,
            "message": "Phát hiện phiếu đặt hàng nhiều đợt. Cần chỉ định cột Lần N cụ thể."
        }

    def _copy_sheet(self, ws_src, ws_new) -> Dict:
        """Copy nguyên sheet."""
        for r in range(1, ws_src.max_row + 1):
            for c in range(1, min(ws_src.max_column + 1, 25)):
                ws_new.cell(r, c, value=ws_src.cell(r, c).value)
        return {"action": "copy"}

    def _find_header_row_heuristic(self, ws) -> int:
        """Tìm header row bằng heuristic khi detect_boq_header fail."""
        for r in range(1, min(30, ws.max_row + 1)):
            non_empty = sum(1 for c in range(1, min(20, ws.max_column + 1))
                          if ws.cell(r, c).value is not None)
            if non_empty >= 4:
                return r
        return 10

    def _find_best_qty_column(self, ws, header_row: int, name_col: int) -> Optional[int]:
        """
        Tìm cột chứa SL thực tế bằng cách đếm cột nào có nhiều số dương nhất.
        """
        candidates = {}
        for c in range(1, min(ws.max_column + 1, 25)):
            if c == name_col:
                continue
            count_positive = 0
            count_total = 0
            values = []
            for r in range(header_row + 1, min(header_row + 80, ws.max_row + 1)):
                v = ws.cell(r, c).value
                if isinstance(v, (int, float)):
                    count_total += 1
                    values.append(v)
                    if v > 0:
                        count_positive += 1
            if count_total < 3:
                continue
            if values and max(values) > 100000:
                continue
            if len(values) >= 3:
                positive_vals = [v for v in values if v > 0]
                diffs = [values[i+1] - values[i] for i in range(min(10, len(values)-1)) if values[i+1] > 0 and values[i] > 0]
                if diffs and all(d == 1 for d in diffs):
                    continue
                if positive_vals and min(positive_vals) > 15:
                    increasing = sum(1 for i in range(len(values)-1) if values[i+1] >= values[i])
                    if increasing > len(values) * 0.7:
                        continue
            candidates[c] = count_positive

        if candidates:
            for c in candidates:
                hv = ws.cell(header_row, c).value
                if hv:
                    htxt = str(hv).lower().strip()
                    if any(kw in htxt for kw in QTY_KEYWORDS):
                        return c
            right_candidates = {c: v for c, v in candidates.items() if c > name_col}
            if right_candidates:
                best_col = max(right_candidates, key=right_candidates.get)
                if right_candidates[best_col] >= 3:
                    return best_col
            best_col = max(candidates, key=candidates.get)
            if candidates[best_col] >= 3:
                return best_col
        return None

# ---------------------------------------------------------------------------
# Module 3: Validation & Confidence Gate
# ---------------------------------------------------------------------------

class ValidationGate:
    """Kiểm tra kết quả normalize trước khi đưa vào pipeline chính."""

    def __init__(self, filepath: str):
        self.filepath = filepath

    def validate(self) -> Dict:
        """
        Validate file đã normalize bằng cách parse thử.
        Trả về validation report.
        """
        from swind_utils import detect_boq_header

        wb = openpyxl.load_workbook(self.filepath, data_only=True)
        report = {
            "file": self.filepath,
            "sheets": {},
            "overall_confidence": ConfidenceLevel.HIGH.value,
            "issues": [],
        }

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            if ws.max_row is None or ws.max_row < 5:
                continue

            try:
                header_row, col_map, _, _, _ = detect_boq_header(ws)
            except Exception as e:
                report["sheets"][sheet_name] = {
                    "error": str(e),
                    "confidence": ConfidenceLevel.LOW.value,
                }
                report["overall_confidence"] = ConfidenceLevel.LOW.value
                continue

            name_col = col_map.get("name", 2)
            qty_col = col_map.get("qty")

            total_items = 0
            qty_nonzero = 0
            has_dims = 0

            for r in range(header_row + 1, min(header_row + 200, ws.max_row + 1)):
                name_v = ws.cell(r, name_col).value
                if not name_v or len(str(name_v).strip()) < 3:
                    continue
                total_items += 1

                if qty_col:
                    qv = ws.cell(r, qty_col).value
                    if isinstance(qv, (int, float)) and qv > 0:
                        qty_nonzero += 1

                if DIM_PATTERN.search(str(name_v)) or re.search(r'D\d{2,4}', str(name_v)):
                    has_dims += 1

            sheet_report = {
                "header_row": header_row,
                "col_map_keys": list(col_map.keys()),
                "total_items": total_items,
                "qty_nonzero": qty_nonzero,
                "qty_nonzero_rate": round(qty_nonzero / total_items, 2) if total_items > 0 else 0,
                "dims_detected": has_dims,
                "dims_rate": round(has_dims / total_items, 2) if total_items > 0 else 0,
            }

            if total_items == 0:
                sheet_report["confidence"] = ConfidenceLevel.LOW.value
            elif sheet_report["qty_nonzero_rate"] >= 0.7 and total_items >= 5:
                sheet_report["confidence"] = ConfidenceLevel.HIGH.value
            elif sheet_report["qty_nonzero_rate"] >= 0.3:
                sheet_report["confidence"] = ConfidenceLevel.MEDIUM.value
            else:
                sheet_report["confidence"] = ConfidenceLevel.LOW.value
                report["issues"].append(
                    f"Sheet '{sheet_name}': Chỉ {sheet_report['qty_nonzero_rate']*100:.0f}% items có SL>0. "
                    f"Có thể parser đọc nhầm cột SL."
                )

            report["sheets"][sheet_name] = sheet_report

        confidence_order = {ConfidenceLevel.HIGH.value: 2, ConfidenceLevel.MEDIUM.value: 1, ConfidenceLevel.LOW.value: 0}
        worst = min(
            (sr.get("confidence", ConfidenceLevel.HIGH.value) for sr in report["sheets"].values()),
            key=lambda x: confidence_order.get(x, 0),
            default=ConfidenceLevel.HIGH.value
        )
        report["overall_confidence"] = worst

        return report

# ---------------------------------------------------------------------------
# Module 4: Learning Loop
# ---------------------------------------------------------------------------

class FormatLearningDB:
    """Lưu trữ và tra cứu format patterns đã học."""

    DB_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "data", "master_data", "format_learning_db.json")

    def __init__(self):
        self.patterns = []
        self._load()

    def _load(self):
        if os.path.exists(self.DB_PATH):
            try:
                with open(self.DB_PATH, "r", encoding="utf-8") as f:
                    self.patterns = json.load(f)
            except Exception:
                self.patterns = []

    def _save(self):
        os.makedirs(os.path.dirname(self.DB_PATH), exist_ok=True)
        with open(self.DB_PATH, "w", encoding="utf-8") as f:
            json.dump(self.patterns, f, ensure_ascii=False, indent=2)

    def lookup(self, company: Optional[str] = None, file_hash: Optional[str] = None) -> Optional[Dict]:
        """Tra cứu pattern đã học cho company hoặc file hash."""
        for p in reversed(self.patterns):
            if file_hash and p.get("file_hash") == file_hash:
                return p
            if company and p.get("company") == company:
                return p
        return None

    def record(self, entry: Dict):
        """Ghi nhận pattern mới sau dự án thành công."""
        entry["timestamp"] = datetime.now().isoformat()
        self.patterns.append(entry)
        if len(self.patterns) > 100:
            self.patterns = self.patterns[-100:]
        self._save()

# ---------------------------------------------------------------------------
# Main Agent Class
# ---------------------------------------------------------------------------

class Agent00B_InputNormalizer:
    """
    Agent 00B — Input Normalizer
    Chuẩn hóa file BOQ đầu vào về format Swind chuẩn.
    Chạy TRƯỚC Agent 01 trong pipeline.
    """

    def __init__(self, boq_filepath: str, interactive: bool = True):
        self.filepath = boq_filepath
        self.interactive = interactive
        self.learning_db = FormatLearningDB()
        self.report = {}

    def normalize(self) -> Tuple[str, Dict]:
        """
        Main entry point. Trả về (output_filepath, report).
        Nếu file đã chuẩn → trả về file gốc.
        Nếu cần normalize → trả về file mới + report.
        """
        print("\n" + "-" * 60)
        print("[Agent 00B - Input Normalizer] Phân tích cấu trúc file BOQ đầu vào...")
        print("-" * 60)

        file_hash = self._compute_file_hash()
        known = self.learning_db.lookup(file_hash=file_hash)
        if known:
            print(f"  -> Đã nhận diện format từ kinh nghiệm: {known.get('format_type', 'unknown')}")

        detector = FormatDetector(self.filepath)
        self.wb = detector.wb
        analyses = detector.analyze_all_sheets()

        for sheet_name, analysis in analyses.items():
            fmt = analysis.get("format_type", FormatType.STANDARD_BOQ)
            fmt_str = fmt.value if isinstance(fmt, FormatType) else fmt
            conf = analysis.get("confidence", 0)
            data_rows = analysis.get("data_row_count", 0)
            qty_rate = analysis.get("qty_nonzero_rate", 0)
            company = analysis.get("detected_company", "")
            sections = "✓" if analysis.get("has_section_headers") else "✗"

            print(f"  -> Sheet '{sheet_name}': Format={fmt_str} | Confidence={conf:.0%} | "
                  f"Data={data_rows} dòng | SL>0={qty_rate:.0%} | "
                  f"Section headers={sections}"
                  f"{f' | Company={company}' if company else ''}")

        passthrough_types = (FormatType.STANDARD_BOQ, FormatType.ORDER_MULTI_BATCH,
                             FormatType.STANDARD_BOQ.value, FormatType.ORDER_MULTI_BATCH.value)
        all_standard = all(
            a.get("format_type") in passthrough_types
            for a in analyses.values()
        )

        if all_standard:
            print("  -> ✅ Tất cả sheets đã tương thích chuẩn Swind. Không cần tạo file normalize mới.")
            self.report = {"action": "pass-through", "file": self.filepath}
            return self.filepath, self.report

        print("  -> 🔄 Phát hiện format không chuẩn. Tiến hành chuẩn hóa...")
        normalizer = StructureNormalizer(self.filepath, analyses)
        output_path, norm_report = normalizer.normalize()

        print("  -> ✅ Kiểm tra kết quả chuẩn hóa...")
        validator = ValidationGate(output_path)
        val_report = validator.validate()

        confidence = val_report.get("overall_confidence", ConfidenceLevel.HIGH.value)
        issues = val_report.get("issues", [])

        if confidence == ConfidenceLevel.LOW.value:
            print(f"  -> ⚠️  CẢNH BÁO: Confidence THẤP sau normalize!")
            for issue in issues:
                print(f"     ⚠️  {issue}")
            if self.interactive:
                print("  -> Khuyến nghị kiểm tra file trước khi chạy báo giá.")
        elif confidence == ConfidenceLevel.MEDIUM.value:
            print(f"  -> ⚡ Confidence TRUNG BÌNH. Một số items có thể thiếu SL.")
            for issue in issues:
                print(f"     ℹ️  {issue}")
        else:
            print(f"  -> ✅ Confidence CAO. File đã chuẩn hóa thành công.")

        for sn, sr in val_report.get("sheets", {}).items():
            if "total_items" in sr:
                print(f"     Sheet '{sn}': {sr['total_items']} items | "
                      f"SL>0={sr.get('qty_nonzero_rate', 0):.0%} | "
                      f"Kích thước={sr.get('dims_rate', 0):.0%}")

        for sheet_name, analysis in analyses.items():
            fmt = analysis.get("format_type", FormatType.STANDARD_BOQ)
            if isinstance(fmt, FormatType):
                fmt = fmt.value
            if fmt != FormatType.STANDARD_BOQ.value:
                self.learning_db.record({
                    "file_hash": file_hash,
                    "filename": os.path.basename(self.filepath),
                    "company": analysis.get("detected_company"),
                    "format_type": fmt,
                    "header_row": analysis.get("header_row"),
                    "col_map": {k: v for k, v in analysis.get("col_map", {}).items()},
                    "success": confidence != ConfidenceLevel.LOW.value,
                })

        self.report = {
            "action": norm_report.get("action", "normalized"),
            "source_file": self.filepath,
            "output_file": output_path,
            "format_analyses": {k: {
                "format_type": v.get("format_type").value if isinstance(v.get("format_type"), FormatType) else v.get("format_type"),
                "confidence": v.get("confidence"),
                "data_rows": v.get("data_row_count"),
                "qty_rate": v.get("qty_nonzero_rate"),
            } for k, v in analyses.items()},
            "validation": val_report,
            "normalization_details": norm_report,
        }

        if output_path != self.filepath:
            print(f"  -> File chuẩn hóa: {output_path}")

        return output_path, self.report

    def _compute_file_hash(self) -> str:
        """Tính hash của file để lookup learning DB."""
        h = hashlib.md5()
        with open(self.filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                h.update(chunk)
        return h.hexdigest()[:12]


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python agent_00b_input_normalizer.py <boq_file.xlsx>")
        sys.exit(1)

    filepath = sys.argv[1]
    agent = Agent00B_InputNormalizer(filepath, interactive=True)
    output, report = agent.normalize()
    print(f"\n📋 Output: {output}")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
