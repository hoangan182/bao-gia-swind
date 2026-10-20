import re
import unicodedata
import hashlib
import openpyxl
from openpyxl.utils import get_column_letter

VIETNAMESE_CHAR_MAP = {
    'à': 'a', 'á': 'a', 'ả': 'a', 'ã': 'a', 'ạ': 'a',
    'ă': 'a', 'ắ': 'a', 'ằ': 'a', 'ẳ': 'a', 'ẵ': 'a', 'ặ': 'a',
    'â': 'a', 'ấ': 'a', 'ầ': 'a', 'ẩ': 'a', 'ẫ': 'a', 'ậ': 'a',
    'đ': 'd', 'Đ': 'D',
    'è': 'e', 'é': 'e', 'ẻ': 'e', 'ẽ': 'e', 'ẹ': 'e',
    'ê': 'e', 'ế': 'e', 'ề': 'e', 'ể': 'e', 'ễ': 'e', 'ệ': 'e',
    'ì': 'i', 'í': 'i', 'ỉ': 'i', 'ĩ': 'i', 'ị': 'i',
    'ò': 'o', 'ó': 'o', 'ỏ': 'o', 'õ': 'o', 'ọ': 'o',
    'ô': 'o', 'ố': 'o', 'ồ': 'o', 'ổ': 'o', 'ỗ': 'o', 'ộ': 'o',
    'ơ': 'o', 'ớ': 'o', 'ờ': 'o', 'ở': 'o', 'ỡ': 'o', 'ợ': 'o',
    'ù': 'u', 'ú': 'u', 'ủ': 'u', 'ũ': 'u', 'ụ': 'u',
    'ư': 'u', 'ứ': 'u', 'ừ': 'u', 'ử': 'u', 'ữ': 'u', 'ự': 'u',
    'ỳ': 'y', 'ý': 'y', 'ỷ': 'y', 'ỹ': 'y', 'ỵ': 'y'
}

def remove_vietnamese_accents(text):
    """
    Chuyển đổi toàn bộ chuỗi tiếng Việt có dấu thành không dấu (ASCII).
    Hỗ trợ cả Unicode dựng sẵn (NFC) và tổ hợp (NFD).
    """
    if not text:
        return ""
    # Chuẩn hóa về NFC trước
    s = unicodedata.normalize('NFC', text)
    result = []
    for ch in s:
        lower_ch = ch.lower()
        if lower_ch in VIETNAMESE_CHAR_MAP:
            mapped = VIETNAMESE_CHAR_MAP[lower_ch]
            result.append(mapped.upper() if ch.isupper() else mapped)
        else:
            result.append(ch)
    s = "".join(result)
    # Loại bỏ các dấu kết hợp còn sót lại (nếu có)
    s = unicodedata.normalize('NFD', s)
    s = "".join(ch for ch in s if unicodedata.category(ch) != 'Mn')
    return s

def vietnamese_slugify(text, max_len=40, add_hash=True):
    """
    Sinh mã định danh chuẩn (Slug / MAT_ID) từ chuỗi tiếng Việt:
    - Loại bỏ dấu tiếng Việt.
    - Thay thế ký tự đặc biệt, khoảng trắng bằng dấu gạch dưới '_'.
    - Gộp các dấu gạch dưới liên tiếp thành một dấu '_'.
    - Thêm hash ngắn 4 ký tự nếu chuỗi bị cắt ngắn để chống xung đột (collision).
    """
    if not text:
        return "UNKNOWN"
        
    raw_clean = remove_vietnamese_accents(text.strip())
    # Thay thế các ký tự không phải chữ và số thành '_'
    slug = re.sub(r'[^a-zA-Z0-9]', '_', raw_clean)
    # Gộp nhiều dấu '_' liên tiếp thành 1
    slug = re.sub(r'_+', '_', slug).strip('_').upper()
    
    if not slug:
        slug = "ITEM"
        
    if len(slug) <= max_len:
        return slug
        
    if add_hash:
        # Băm MD5 4 ký tự từ chuỗi đã chuẩn hóa khoảng trắng để tránh xung đột
        normalized_text = re.sub(r'\s+', ' ', text.strip())
        hash_suffix = hashlib.md5(normalized_text.encode('utf-8')).hexdigest()[:4].upper()
        allowed_len = max_len - 5 # chừa chỗ cho '_' + 4 ký tự hash
        truncated = slug[:allowed_len].rstrip('_')
        return f"{truncated}_{hash_suffix}"
    else:
        return slug[:max_len].rstrip('_')

def detect_boq_header(ws):
    """
    Nhận diện dòng header và ánh xạ cột (col_map) của file BOQ khách hàng.
    Trả về (header_row, col_map, hidden_rows, hidden_cols, max_scan_col).
    Dùng chung cho cả SwindBOQParser và SwindExcelBuilder.
    """
    hidden_cols = {col_let for col_let, dim in ws.column_dimensions.items() if dim.hidden}
    hidden_rows = {r_idx for r_idx, dim in ws.row_dimensions.items() if dim.hidden}
    max_scan_col = min(ws.max_column, 60)

    header_row = None
    col_map = {}

    aliases = get_subtype_rules().get("HEADER_ALIASES", {})
    NAME_KEYWORDS = tuple(aliases.get("name_keywords", ("sản phẩm", "hạng mục", "quy cách", "công tác", "nội dung", "diễn giải", "mô tả", "tên vật tư", "danh mục")))
    NAME_CAND_KEYWORDS = tuple(aliases.get("name_cand_keywords", ("sản phẩm", "hạng mục", "danh mục", "công tác", "nội dung", "diễn giải", "mô tả", "tên vật tư")))
    QTY_KEYWORDS = tuple(aliases.get("qty_keywords", ("số lượng", "q'ty", "qty", "khối lượng", "sl", "kl")))
    STT_KEYWORDS = tuple(aliases.get("stt_keywords", ("stt", "tt", "no", "no.")))
    SPEC_KEYWORDS = tuple(aliases.get("spec_keywords", ("thông số", "quy cách")))
    MODEL_KEYWORDS = tuple(aliases.get("model_keywords", ("model", "mã hiệu")))
    BRAND_KEYWORDS = tuple(aliases.get("brand_keywords", ("thương hiệu", "nhãn hiệu", "xuất xứ")))
    SIZE_KEYWORDS = tuple(aliases.get("size_keywords", ("kích thước", "size")))
    THK_KEYWORDS = tuple(aliases.get("thickness_keywords", ("độ dày",)))
    UNIT_KEYWORDS = tuple(aliases.get("unit_keywords", ("unit", "đơn vị")))
    PRICE_KEYWORDS = tuple(aliases.get("price_keywords", ("đơn giá", "price")))
    TOTAL_KEYWORDS = tuple(aliases.get("total_keywords", ("thành tiền", "total")))
    REMARKS_KEYWORDS = tuple(aliases.get("remarks_keywords", ("ghi chú", "remarks")))

    for r in range(1, min(25, ws.max_row + 1)):
        if r in hidden_rows:
            continue
        row_vals = {c: re.sub(r'\s+', ' ', str(ws.cell(r, c).value).lower()).strip()
                    for c in range(1, max_scan_col + 1)
                    if get_column_letter(c) not in hidden_cols and ws.cell(r, c).value is not None}
        has_name = any(any(k in v for k in NAME_KEYWORDS) for v in row_vals.values())
        has_qty = any(any(k in v for k in QTY_KEYWORDS) for v in row_vals.values())
        if has_name and has_qty:
            header_row = r
            name_cands = []
            qty_cands = []
            for c, v in row_vals.items():
                if any(k in v for k in NAME_CAND_KEYWORDS):
                    name_cands.append(c)
                elif v in STT_KEYWORDS:
                    if "stt" not in col_map: col_map["stt"] = c
                elif any(k in v for k in SPEC_KEYWORDS):
                    if "spec" not in col_map: col_map["spec"] = c
                elif any(k in v for k in MODEL_KEYWORDS):
                    if "model" not in col_map: col_map["model"] = c
                elif any(k in v for k in BRAND_KEYWORDS):
                    if "brand" not in col_map: col_map["brand"] = c
                elif any(k in v for k in SIZE_KEYWORDS):
                    if "w" not in col_map: col_map["w"] = c
                elif any(k in v for k in THK_KEYWORDS):
                    if "thickness" not in col_map: col_map["thickness"] = c
                elif any(k in v for k in UNIT_KEYWORDS):
                    if "unit" not in col_map: col_map["unit"] = c
                elif any(k in v for k in QTY_KEYWORDS):
                    qty_cands.append(c)
                elif any(k in v for k in PRICE_KEYWORDS):
                    if "price" not in col_map: col_map["price"] = c
                elif any(k in v for k in TOTAL_KEYWORDS):
                    if "total" not in col_map: col_map["total"] = c
                elif any(k in v for k in REMARKS_KEYWORDS):
                    if "remarks" not in col_map: col_map["remarks"] = c
            if name_cands:
                col_map["name"] = max(name_cands, key=lambda col_c: sum(1 for rr in range(r + 1, min(ws.max_row + 1, r + 25)) if ws.cell(rr, col_c).value not in (None, "")))
            if qty_cands:
                col_map["qty"] = max(qty_cands, key=lambda col_c: sum(1 for rr in range(r + 1, min(ws.max_row + 1, r + 25)) if isinstance(ws.cell(rr, col_c).value, (int, float)) and ws.cell(rr, col_c).value > 0))
            break

    if header_row is None:
        # Fallback: bố cục chuẩn Swind (Row 11)
        header_row = 11
        col_map = {
            "stt": 1, "name": 2, "desc": 3, "model": 4, "brand": 5,
            "w": 6, "h": 7, "l": 11, "thickness": 12,
            "unit": 13, "qty": 14, "price": 15, "total": 16, "remarks": 17
        }

    return header_row, col_map, hidden_rows, hidden_cols, max_scan_col

_CACHED_PRICE_MAP = None
_CACHED_BOM_RULES = None
_CACHED_SUBTYPE_RULES = None

def get_subtype_rules(force_reload=False):
    """
    Đọc bộ quy tắc phân loại sản phẩm, từ khóa nhận diện & quy tắc Combo từ data/master_data/subtype_rules.json.
    """
    global _CACHED_SUBTYPE_RULES
    if _CACHED_SUBTYPE_RULES is not None and not force_reload:
        return _CACHED_SUBTYPE_RULES

    import os
    import json
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rules_path = os.path.join(base_dir, "data", "master_data", "subtype_rules.json")
    if os.path.exists(rules_path):
        with open(rules_path, "r", encoding="utf-8") as f:
            _CACHED_SUBTYPE_RULES = json.load(f)
    else:
        _CACHED_SUBTYPE_RULES = {}
    return _CACHED_SUBTYPE_RULES

def get_master_price_map(force_reload=False):
    """
    Đọc trực tiếp bảng đơn giá vật tư từ bộ file Master Data đã có sẵn (data/master_data/).
    Luôn ưu tiên phiên bản giá mới nhất trong data/master_data/prices/ (nếu có update giá).
    """
    global _CACHED_PRICE_MAP
    if _CACHED_PRICE_MAP is not None and not force_reload:
        return _CACHED_PRICE_MAP

    import os
    import glob
    import json
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    master_dir = os.path.join(base_dir, "data", "master_data")
    prices_dir = os.path.join(master_dir, "prices")

    db_files = sorted(glob.glob(os.path.join(prices_dir, "master_database_price_*.json")))
    db_path = db_files[-1] if db_files else os.path.join(master_dir, "master_database_price.json")
    price_map = {}
    if os.path.exists(db_path):
        with open(db_path, "r", encoding="utf-8") as f:
            for item in json.load(f):
                price_map[item["MAT_ID"]] = float(item.get("Price") or 0.0)

    com_files = sorted(glob.glob(os.path.join(prices_dir, "master_commercial_price_*.json")))
    com_path = com_files[-1] if com_files else os.path.join(master_dir, "master_commercial_price.json")
    if os.path.exists(com_path):
        with open(com_path, "r", encoding="utf-8") as f:
            for item in json.load(f):
                price_map[item["MAT_ID"]] = float(item.get("Price") or 0.0)

    _CACHED_PRICE_MAP = price_map
    return _CACHED_PRICE_MAP

def get_master_bom_rules(force_reload=False):
    """
    Đọc trực tiếp bộ quy tắc & hệ số định mức chuẩn từ data/master_data/master_bom_rules.json (đã giải mã 1 lần).
    """
    global _CACHED_BOM_RULES
    if _CACHED_BOM_RULES is not None and not force_reload:
        return _CACHED_BOM_RULES

    import os
    import json
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    rules_path = os.path.join(base_dir, "data", "master_data", "master_bom_rules.json")
    if os.path.exists(rules_path):
        with open(rules_path, "r", encoding="utf-8") as f:
            _CACHED_BOM_RULES = json.load(f)
    else:
        _CACHED_BOM_RULES = {}
    return _CACHED_BOM_RULES

if __name__ == "__main__":
    test_cases = [
        "Lưới bảo vệ",
        "Quạt hướng trục CEF-B2-Z1-01~02 5290/9430 l/s @ 500/1350 Pa, chống cháy 300°C trong 2h",
        "Cửa gió nan Z 600x600",
        "Chi phí cắt đục, đóng lưới trám trét tường",
        "Lớp chống cháy EI30",
        "Vật tư phụ, phụ kiện"
    ]
    for tc in test_cases:
        print(f"'{tc}'\n -> Slug: '{vietnamese_slugify(tc)}'\n")
