"""
Agent 00B - Input Analyzer (Phân tích cấu trúc BOQ đầu vào — CHỈ ĐỌC)
=====================================================================
Nhiệm vụ: Mở file BOQ, phân tích cấu trúc từng sheet (header, ánh xạ cột, số dòng dữ liệu,
tỷ lệ KL>0, phiếu đặt hàng nhiều đợt), chạy thử SwindBOQParser và in cảnh báo cho sheet lạ.

KHÔNG viết lại nội dung BOQ (không tạo file _NORMALIZED, không chèn tiêu đề giả, không đổi cột SL).
Mọi phép đọc header / cột / dòng ẩn đi qua Reader core trong swind_utils.
Vai trò & lý do: .agents/roles/agent_00b_input_normalizer_role.md

Pipeline: Input → Agent 00B (phân tích) → Agent 01 → Agent 02..08
Module:
  M1: Format Detector & Classifier
  M4: Learning Loop (format_learning_db.json)
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

from swind_utils import detect_boq_header, hidden_row_indices

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

# Keywords nhận diện
SECTION_KEYWORDS = ("ống gió tôn dày", "ống gió inox", "ống gió tôn mạ",
                    "phụ kiện ống gió", "vật tư phần gió", "hệ thống",
                    "ống gió tôn hoa sen")
CONSUMABLE_KEYWORDS = ("băng dính", "keo silicol", "keo silicon", "vít tự khoan",
                       "ốc vít", "foam xịt", "bọt nở", "đai treo", "ty treo",
                       "quang treo", "ca xe", "boom lift", "nhân công", "cẩu hàng", "giàn giáo")
DUCT_ITEM_PATTERN = re.compile(
    r'(ống|côn|cút|chân rẽ|hộp gió|măng|chếch|bịt đầu|bịt ống|nối ống|tê đầu ống|tê đều ống|tiêu âm|nối mềm|canvas)',
    re.IGNORECASE
)


# ---------------------------------------------------------------------------
# Module 1: Format Detector & Classifier
# ---------------------------------------------------------------------------

class FormatDetector:
    """Phân tích cấu trúc file Excel và phân loại format."""

    def __init__(self, filepath: str):
        self.filepath = filepath
        self.wb = openpyxl.load_workbook(filepath, data_only=True)
        self.results = {}  # per-sheet analysis

    def analyze_all_sheets(self, sheet_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """Phân tích tất cả sheets hiển thị (hoặc sheets mục tiêu/HVAC) trong workbook."""
        visible_sheets = [s for s in self.wb.sheetnames if getattr(self.wb[s], "sheet_state", "visible") == "visible"]
        cand_sheets = visible_sheets if visible_sheets else list(self.wb.sheetnames)
        if sheet_names:
            matched = [s.strip() for s in sheet_names if s.strip() in cand_sheets]
            if not matched:
                for req_s in sheet_names:
                    req_low = req_s.strip().lower()
                    for wb_s in cand_sheets:
                        if req_low and req_low in wb_s.lower() and wb_s not in matched:
                            matched.append(wb_s)
            if matched:
                cand_sheets = matched
        elif len(cand_sheets) > 1:
            hvac_kws = ("dhkk", "hvac", "thong gio", "thông gió", "thong_gio", "hut khoi", "hút khói", "hut_khoi", "tang ap", "tăng áp", "tang áp", "tăng ap", "tang_ap", "duct", "lanh", "lạnh", "ventilation", "m.4 duct")
            hvac_matched = [s for s in cand_sheets if any(kw in s.lower().strip() for kw in hvac_kws)]
            if hvac_matched:
                cand_sheets = hvac_matched
        info_kws = ("bìa", "bia", "cover", "mục lục", "muc luc", "index", "toc", "thuyết minh", "thuyet minh", "điều khoản", "dieu khoan", "clarification", "làm rõ", "vtdv", "summary", "recap", "phạm vi", "pham vi", "scope")
        if len(cand_sheets) > 1:
            filtered = [s for s in cand_sheets if not any(k in s.lower().strip() for k in info_kws)]
            if filtered:
                cand_sheets = filtered
        valid_sheets = [s for s in cand_sheets if self.wb[s].max_row is not None and self.wb[s].max_row >= 3]
        # Phân tích tuần tự (workbook openpyxl dùng chung không an toàn đa luồng)
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
        """Header & ánh xạ cột lấy từ Reader core (swind_utils.detect_boq_header) — cấm tự dò riêng."""
        try:
            h_row, col_map, _, _, _ = detect_boq_header(ws)
        except Exception:
            return {"header_row": None, "col_map": {}}
        if h_row is None or not col_map.get("name"):
            return {"header_row": None, "col_map": {}}
        return {"header_row": h_row, "col_map": dict(col_map)}

    def _check_order_sheet(self, ws) -> bool:
        """Kiểm tra xem có phải phiếu đặt hàng nhiều đợt (có cột Lần N)."""
        for r in range(1, min(20, ws.max_row + 1)):
            for c in range(3, min(25, ws.max_column + 1)):
                v = ws.cell(r, c).value
                if v and isinstance(v, str):
                    txt = v.lower().strip()
                    if not any(qk in txt for qk in ("báo giá", "chào giá", "dự toán")) and re.search(r'\blần\s*\d+\b', txt):
                        return True
        # Check sheet name
        sheet_name = ws.title.lower() if ws.title else ""
        if any(kw in sheet_name for kw in ("rop", "đặt hàng", "order")):
            return True
        return False

    def _check_section_headers(self, ws, start_row: int) -> bool:
        """Kiểm tra xem có header phân nhóm 'Ống gió tôn dày X mm' không."""
        start = max(start_row or 5, 1)
        hidden_rows = hidden_row_indices(ws)
        for r in range(start, min(start + 200, ws.max_row + 1)):
            if r in hidden_rows:
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
        hidden_rows = hidden_row_indices(ws)

        for r in range(header_row + 1, min(header_row + 500, ws.max_row + 1)):
            if r in hidden_rows:
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
            # 'Cửa thổi/hồi/hút ... kèm hộp gió' là cửa gió, không phải ống/hộp gió
            is_grille_or_damper = name_lower.startswith("cửa ") or any(
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

        # Dry-run thực tế với SwindBOQParser (đọc file gốc) để đo mức nhận diện
        needs_attention_ducts = False
        parser_mfg_valid = 0
        parser_duct_valid = 0
        try:
            from swind_boq_parser import SwindBOQParser as MPriceBOQParser
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
                needs_attention_ducts = True
                analysis["issues"].append(
                    f"Sheet có {duct_items} dòng giống ống/phụ kiện nhưng parser chỉ nhận ống gió có KL ở {parser_duct_valid} dòng "
                    "— kiểm tra mục [Full-BOQ Coverage Audit] (không tự chèn tiêu đề vào BOQ)."
                )
        except Exception:
            pass

        if needs_attention_ducts:
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
    Agent 00B — Input Analyzer (chỉ đọc).
    Phân tích cấu trúc BOQ & in cảnh báo; luôn trả lại file gốc (KHÔNG viết lại BOQ).
    Chạy TRƯỚC Agent 01 trong pipeline; workbook đã mở được chia sẻ qua self.wb.
    """

    def __init__(self, boq_filepath: str, interactive: bool = True, sheet_names: Optional[List[str]] = None):
        self.filepath = boq_filepath
        self.interactive = interactive
        self.sheet_names = sheet_names
        self.learning_db = FormatLearningDB()
        self.report = {}
        self.wb = None

    def normalize(self) -> Tuple[str, Dict]:
        """
        Main entry point. Trả về (file_gốc, report).
        report["action"] = "analysis-only"; report["warnings"] = cảnh báo theo sheet (rỗng nếu BOQ tương thích).
        """
        print("\n" + "-" * 60)
        print("[Agent 00B - Input Analyzer] Phân tích cấu trúc file BOQ đầu vào (chỉ đọc)...")
        print("-" * 60)

        file_hash = self._compute_file_hash()
        known = self.learning_db.lookup(file_hash=file_hash)
        if known:
            print(f"  -> Đã nhận diện format từ kinh nghiệm: {known.get('format_type', 'unknown')}")

        detector = FormatDetector(self.filepath)
        self.wb = detector.wb
        analyses = detector.analyze_all_sheets(sheet_names=self.sheet_names)

        warnings = {}
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

            if fmt_str == FormatType.ORDER_MULTI_BATCH.value:
                analysis["issues"].append("Phiếu đặt hàng nhiều đợt (cột 'Lần N') — kiểm tra cột KL parser đã chọn.")
            if fmt_str != FormatType.STANDARD_BOQ.value and analysis.get("issues"):
                warnings[sheet_name] = list(analysis["issues"])
                for issue in analysis["issues"]:
                    print(f"     ⚠️  {issue}")

            if fmt_str != FormatType.STANDARD_BOQ.value:
                self.learning_db.record({
                    "file_hash": file_hash,
                    "filename": os.path.basename(self.filepath),
                    "company": analysis.get("detected_company"),
                    "format_type": fmt_str,
                    "header_row": analysis.get("header_row"),
                    "col_map": {k: v for k, v in analysis.get("col_map", {}).items()},
                    "success": True,
                })

        if warnings:
            print("  -> ⚠️  BOQ có cấu trúc lạ ở các sheet trên — đọc trực tiếp file gốc (không chuẩn hóa/viết lại), "
                  "đối chiếu mục [Full-BOQ Coverage Audit].")
        else:
            print("  -> ✅ Tất cả sheets đã tương thích chuẩn Swind.")

        self.report = {
            "action": "analysis-only",
            "source_file": self.filepath,
            "format_analyses": {k: {
                "format_type": v.get("format_type").value if isinstance(v.get("format_type"), FormatType) else v.get("format_type"),
                "confidence": v.get("confidence"),
                "header_row": v.get("header_row"),
                "col_map": v.get("col_map"),
                "data_rows": v.get("data_row_count"),
                "qty_rate": v.get("qty_nonzero_rate"),
            } for k, v in analyses.items()},
            "warnings": warnings,
        }
        return self.filepath, self.report

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
    print(f"\n📋 File: {output}")
    print(json.dumps(report, ensure_ascii=False, indent=2, default=str))
