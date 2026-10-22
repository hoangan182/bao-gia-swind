import openpyxl
import re
import json
import os
from swind_utils import detect_boq_header, get_subtype_rules

class SwindBOQParser:
    """
    Trình phân tích BOQ tự động, nhận diện cấu trúc động:
    - Tìm dòng tiêu đề (header) động.
    - Phân biệt dòng phân nhóm (Category Header) và dòng sản phẩm thực tế.
    - Trích xuất thông số kích thước (W, H, L) và chủng loại sản phẩm.
    """
    def __init__(self, boq_filepath):
        self.filepath = boq_filepath
        self.wb = openpyxl.load_workbook(boq_filepath, data_only=True)
        self.commercial_catalog = []
        self.manufacturable_catalog = []
        self._load_catalogs()
        
        self.learned_keywords = {}
        learning_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data/master_data/boq_keyword_learning.json")
        if os.path.exists(learning_path):
            with open(learning_path, "r", encoding="utf-8") as f:
                self.learned_keywords = json.load(f)

    def _load_catalogs(self):
        try:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            candidates = [
                os.path.join(base_dir, "../data/master_data"),
                os.path.join(base_dir, "data/master_data"),
                os.path.abspath("data/master_data")
            ]
            comm_path, mfg_path = None, None
            for cand in candidates:
                cp = os.path.join(cand, "commercial_catalog.json")
                mp = os.path.join(cand, "manufacturable_catalog.json")
                if os.path.exists(cp) and os.path.exists(mp):
                    comm_path, mfg_path = cp, mp
                    break
            if comm_path and mfg_path:
                with open(comm_path, "r", encoding="utf-8") as f:
                    self.commercial_catalog = json.load(f)
                with open(mfg_path, "r", encoding="utf-8") as f:
                    self.manufacturable_catalog = json.load(f)
                print(f"[SwindBOQParser] Đã nạp thành công {len(self.commercial_catalog)} mục thương mại & {len(self.manufacturable_catalog)} mục sản xuất.")
            else:
                print(f"[SwindBOQParser] CẢNH BÁO: Không tìm thấy file catalog tại: {candidates}")
        except Exception as e:
            print(f"[SwindBOQParser] Lỗi khi nạp catalogs: {e}")

    def parse_sheet(self, sheet_name, max_items=None):
        if sheet_name not in self.wb.sheetnames:
            raise ValueError(f"Sheet {sheet_name} không tồn tại trong {self.filepath}")
            
        ws = self.wb[sheet_name]
        
        # 1. Nhận diện Header BOQ (dùng hàm chung từ swind_utils)
        header_row, col_map, hidden_rows, hidden_cols, max_scan_col = detect_boq_header(ws)
        combo_cfg = get_subtype_rules().get("COMBO_AND_DETECTION_RULES", {})
        cv_kws = tuple(combo_cfg.get("missing_qty_cv_keywords", ("louver", "luover", "louvre", "miệng gió", "cửa gió", "cửa nan", "van ", "vcd", "mfd", "mfsd", "nrd", "prd")))
        cv_rx = combo_cfg.get("missing_qty_cv_regex", r'\b(fd|md|sag|rag|eag|oag|pag|seg|eal|oal|fal)\b')
            
        items = []
        current_section = "SẢN PHẨM"
        
        for r in range(header_row + 1, ws.max_row + 1):
            if r in hidden_rows:
                continue
                
            name_val = ws.cell(r, col_map.get("name", 2)).value
            qty_val = ws.cell(r, col_map.get("qty", 14)).value
            unit_val = ws.cell(r, col_map.get("unit", 13)).value
            
            if not name_val:
                continue
                
            name_str = str(name_val).strip()
            raw_name_str = name_str
            is_missing_qty = False
            is_pure_dim = bool(re.match(r'^(?:[dD]\d+|\d+\s*[xX*]\s*\d+)$', name_str))
            if name_str.lower().endswith(("kích thước:", "kích thước")) and not re.search(r'\d', name_str):
                current_section = name_str
                continue
            if is_pure_dim and current_section and current_section.upper() != "SẢN PHẨM":
                name_str = f"{current_section.strip()} {name_str}"
            
            # Kiểm tra xem có phải dòng tiêu đề phân nhóm không (giữ lại dòng Cửa/Van có quy cách kích thước dù chưa điền khối lượng)
            if qty_val is None or not isinstance(qty_val, (int, float)) or qty_val <= 0:
                nl_chk = name_str.lower()
                is_blank_qty = (qty_val is None or str(qty_val).strip() == "")
                is_zero_qty_with_unit = (qty_val in (0, 0.0, "0") and unit_val not in (None, "", 0, "0"))
                has_cv_kw = any(k in nl_chk for k in cv_kws) or bool(re.search(cv_rx, nl_chk))
                has_cv_dim = bool(re.search(r'(\d+\s*[xX*]\s*\d+|\b[dD]\d{2,4}\b|\b(?:vcd|fd|nrd|prd|md)\s+\d{2,4}\b)', nl_chk))
                if (is_blank_qty or is_zero_qty_with_unit) and has_cv_kw and has_cv_dim and "tổng cộng" not in nl_chk:
                    is_missing_qty = is_blank_qty
                    qty_val = 0.0
                else:
                    if not unit_val and not is_pure_dim and "tổng cộng" not in nl_chk:
                        current_section = name_str
                    continue
                
            if not unit_val:
                if ws.cell(r, col_map.get("stt", 1)).value in (0, "0") and not re.search(r'\d', name_str):
                    current_section = name_str
                    continue
                unit_val = "m" if any(k in name_str.lower() for k in ("ống đồng", "ông đồng", "cách nhiệt", "upvc")) else "Cái"
                
            # Đọc kích thước (Chỉ đọc từ cột tương ứng nếu header thực sự có cột đó)
            w_val = ws.cell(r, col_map["w"]).value if "w" in col_map else None
            h_val = ws.cell(r, col_map["h"]).value if "h" in col_map else None
            l_val = ws.cell(r, col_map["l"]).value if "l" in col_map else 200
            thk_val = ws.cell(r, col_map["thickness"]).value if "thickness" in col_map else None
            spec_val = ws.cell(r, col_map["spec"]).value if "spec" in col_map else None
            spec_str = str(spec_val).strip() if spec_val not in (None, 0, "0", "#REF!", "#VALUE!", "#N/A") else ""
            model_val = ws.cell(r, col_map["model"]).value if "model" in col_map else None
            if model_val in (0, "0", "#REF!", "#VALUE!", "#N/A"):
                model_val = None
            remarks_val = ws.cell(r, col_map["remarks"]).value if "remarks" in col_map else None
            note_boq_raw = str(remarks_val).strip() if remarks_val not in (None, 0, "0") else ""
            note_boq = " ".join(x for x in (spec_str, note_boq_raw) if x)
            
            w = float(w_val) if isinstance(w_val, (int, float)) else 0
            h = float(h_val) if isinstance(h_val, (int, float)) else 0
            l = float(l_val) if isinstance(l_val, (int, float)) else 200
            thickness = float(thk_val) if isinstance(thk_val, (int, float)) else 0.75
            
            # Chuẩn bị tên đầy đủ kèm tiền tố danh mục cha (section)
            clean_section = current_section.strip()
            full_name_str = name_str
            if clean_section and clean_section.upper() != "SẢN PHẨM" and clean_section.lower() not in name_str.lower():
                clean_section = re.sub(r'^[\dIVXLC]+\.\s*', '', clean_section)
                full_name_str = f"{clean_section} {name_str}"
                
            # Phân loại sản phẩm (Category detection) động từ Master Catalog
            name_lower = name_str.lower().replace('ồ', 'ố')
            full_name_lower = full_name_str.lower()
            model_str = str(model_val).strip() if model_val is not None else ""
            category = "KHAC"
            
            # Hàm kiểm tra từ khóa an toàn (chống va chạm từ con, ví dụ: 'chống cháy' chứa 'ống')
            def match_keyword(kw, text):
                if kw not in text:
                    return False
                if " " in kw:
                    return True
                return bool(re.search(r'\b' + re.escape(kw) + r'\b', text))

            # 1. Kiểm tra Học máy (Learned keywords)
            if name_lower in self.learned_keywords:
                category = self.learned_keywords[name_lower]
            elif full_name_lower in self.learned_keywords:
                category = self.learned_keywords[full_name_lower]
            else:
                # 2. Kiểm tra các trường hợp đặc thù ưu tiên cao (tránh bị từ khóa ngắn như 'van', 'cửa', 'miệng', 'fd' bắt nhầm)
                # 2a. Van nước / Cửa sổ / Thiết bị bắt đầu bằng Quạt, Máy lạnh, Dàn lạnh, Dàn nóng, Chụp thông hơi -> THUONG_MAI
                if name_lower.startswith("cửa sổ") and ("cấp bù gió" in name_lower or "khi có cháy" in name_lower):
                    category = "VAN_GIO"
                elif name_lower.startswith(("quạt ", "máy lạnh", "dàn lạnh", "dàn nóng", "cửa sổ", "chụp thông hơi", "tủ điện", "tủ điều khiển", "vent cap", "ventcap")):
                    category = "THUONG_MAI"
                else:
                    for comm in self.commercial_catalog:
                        if comm.get("product_code") in ("VALVE_WATER", "PIPE_COPPER"):
                            if comm.get("product_code") == "VALVE_WATER" and any(k in name_lower for k in ("lửa", "khói", "cháy", "mfd", "mfsd", "fd", "vcd", "nrd", "md")):
                                continue
                            if comm.get("product_code") == "PIPE_COPPER" and any(k in name_lower for k in ("louver", "louvre", "cửa gió", "miệng gió")):
                                continue
                            if any(match_keyword(kw, name_lower) for kw in comm.get("keywords", [])):
                                category = "THUONG_MAI"
                                break

                # 2b. Box / Hộp tĩnh áp tôn mạ kẽm & Phụ kiện ống gió (Cút, Côn, Chân rẽ, Tê) -> ONG_GIO
                if category == "KHAC" and name_lower.startswith(("box ", "hộp ", "cút ", "côn ", "chân rẽ", "tê ")) and not name_lower.startswith(("hộp và cửa", "hộp + cửa", "hộp kèm cửa", "box và cửa", "box + cửa")) and "tiêu âm" not in name_lower:
                    category = "ONG_GIO"

                # 2c. Kiểm tra Hàng Sản Xuất có độ đặc thù cao (Canvas, Tiêu âm, Cửa, Van, Ống mềm)
                if category == "KHAC":
                    for mfg in self.manufacturable_catalog:
                        if mfg.get("mapping_category") not in ("ONG_GIO", "KHAC"):
                            if any(match_keyword(kw, name_lower) for kw in mfg.get("keywords", [])):
                                category = mfg.get("mapping_category")
                                break
    
                # 3. Nếu chưa khớp, kiểm tra toàn bộ Hàng Thương Mại còn lại
                if category == "KHAC":
                    for comm in self.commercial_catalog:
                        if any(match_keyword(kw, name_lower) for kw in comm.get("keywords", [])):
                            category = "THUONG_MAI"
                            break
                        
                # 4. Nếu vẫn chưa khớp, kiểm tra Ống Gió
                if category == "KHAC":
                    for mfg in self.manufacturable_catalog:
                        if mfg.get("mapping_category") == "ONG_GIO":
                            if any(match_keyword(kw, name_lower) for kw in mfg.get("keywords", [])):
                                category = "ONG_GIO"
                                break

            # 5. Fallback heuristics có kiểm soát chặt chẽ
            if category == "KHAC":
                has_duct = bool(re.search(r'\bống\s+gió\b|\btole\b|\btôn\b', name_lower))
                if has_duct or "ống gió" in current_section.lower():
                    category = "ONG_GIO"
                
            # Trích xuất kích thước từ cả tên, cột Mã hiệu (model) và cột Ghi chú BOQ nếu cột W/H trống
            dim_search_text = f"{name_str} {model_str} {note_boq}".strip()
            # Loại bỏ các thông số công suất/lưu lượng/áp suất để tránh bắt nhầm
            dim_clean_text = re.sub(r'\b\d+(?:[.,]\d+)?\s*(?:kW|W|HP|l/s|m3/h|Pa|V|Hz|dB|A)\b', ' ', dim_search_text, flags=re.IGNORECASE)
            d_val = 0.0

            l_explicit = re.search(r'\bL\s*[:=]\s*(\d+)\b', dim_clean_text, re.IGNORECASE)
            if l_explicit:
                l = float(l_explicit.group(1))

            # Bóc tách đường kính tròn D / DN / Ø / Phi (kể cả viết dạng D100x100: "cứ kích thước D là tròn")
            d_match = re.search(r'(?:^|[\s_(+:-])(?:[dD][nN]?|Ø|phi\s*)(\d{2,4})(?:\s*[xX*]\s*\1)?(?:\s*mm)?(?:\b|(?=[^\w]))', dim_clean_text, re.IGNORECASE)
            rect_search_text = re.sub(r'(?<![a-zA-Z])(?:[dD][nN]?|Ø|phi\s*)(\d{2,4})\s*[xX*]\s*\1\b', ' ', dim_clean_text, flags=re.IGNORECASE)

            if w == 0 and h == 0:
                dim_3d = re.search(r'(\d+)\s*[xX*]\s*(\d+)\s*[xX*]\s*(\d+)', rect_search_text)
                dim_2d = re.search(r'(\d+)\s*[xX*]\s*(\d+)', rect_search_text)
                # Hỗ trợ bắt lỗi gõ nhầm chữ 'x' thành số '6' dạng 10006300 (4 chữ số + 6 + 3 chữ số tròn trăm)
                dim_typo = re.search(r'\b(\d{3,4})6(\d00)\b', rect_search_text)
                if dim_3d:
                    w = float(dim_3d.group(1))
                    h = float(dim_3d.group(2))
                    l = float(dim_3d.group(3))
                elif dim_2d:
                    w = float(dim_2d.group(1))
                    h = float(dim_2d.group(2))
                elif dim_typo:
                    w = float(dim_typo.group(1))
                    h = float(dim_typo.group(2))

            if d_match and w == 0 and h == 0:
                parsed_d = float(d_match.group(1))
                if 50 <= parsed_d <= 3000:
                    d_val = parsed_d
                    if category in ("VAN_GIO", "CUA_GIO", "ONG_GIO", "TIEU_AM"):
                        w = d_val
                        h = d_val

            # Bóc tách diện tích m2 (ví dụ: Cửa sổ cấp bù gió khi có cháy 1.5m2 / 0.8m2 / 0.75m2) hoặc 1 kích thước đơn (mặc định tròn D, ví dụ VCD 150)
            if w == 0 and h == 0 and category in ("VAN_GIO", "CUA_GIO"):
                area_match = re.search(r'(\d+(?:[.,]\d+)?)\s*m2\b', dim_search_text, re.IGNORECASE)
                if area_match:
                    try:
                        area_m2 = float(area_match.group(1).replace(',', '.'))
                        if area_m2 >= 1.0:
                            w = round(area_m2 * 1000.0)
                            h = 1000.0
                        elif area_m2 > 0:
                            w = 1000.0
                            h = round(area_m2 * 1000.0)
                    except:
                        pass
                elif d_val == 0:
                    no_ei_text = re.sub(r'\bEI\s*\d+\b', ' ', dim_clean_text, flags=re.IGNORECASE)
                    single_d_rx = combo_cfg.get("single_dim_damper_regex", r'\b(?:vcd|fd|nrd|prd|md|obd|mfd|mfsd)\s+(\d{2,4})\b')
                    single_d_match = re.search(single_d_rx, no_ei_text, re.IGNORECASE)
                    if single_d_match:
                        parsed_sd = float(single_d_match.group(1))
                        if 50 <= parsed_sd <= 2000:
                            d_val = parsed_sd
                            w = d_val
                            h = d_val

            is_missing_dims = False
            orig_category = category
            if category in ("VAN_GIO", "CUA_GIO") and w == 0 and h == 0 and d_val == 0:
                is_missing_dims = True
                category = "THUONG_MAI"
            elif category == "CUA_GIO" and d_val > 0 and any(k in full_name_lower for k in ("miệng", "cửa", "diffuser", "ead")):
                category = "THUONG_MAI"

            # Trích xuất chỉ số chống cháy EI (EI30, EI60, EI90, EI120)
            ei_rating = 0
            ei_match = re.search(r'\bEI\s*(\d+)\b', dim_search_text, re.IGNORECASE)
            if ei_match:
                ei_rating = int(ei_match.group(1))
            elif "cấp bù gió khi có cháy" in name_lower:
                ei_rating = 120

            # Trích xuất độ dày từ tên sản phẩm hoặc model nếu có chỉ định rõ
            thk_match = re.search(r'(?:tole|tôn|zam|dày|day|thk|độ dày)\s*(\d+[.,]\d+)\s*mm', dim_search_text, re.IGNORECASE)
            if not thk_match:
                thk_match = re.search(r'(\d+[.,]\d+)\s*mm', dim_search_text, re.IGNORECASE)
            if thk_match:
                try:
                    parsed_thk = float(thk_match.group(1).replace(',', '.'))
                    if 0.3 <= parsed_thk <= 5.0: # Giới hạn dải độ dày hợp lý
                        thickness = parsed_thk
                except:
                    pass
                    
            name_str = full_name_str

            # Rule 1: Kích thước cửa gió ghi KTC hoặc cửa bù khí (mặc định nan Z) thì cộng thêm mỗi cạnh 50mm
            ktc_rx = combo_cfg.get("ktc_regex", r'\bktc\b|kích\s*thước\s*cổ')
            raw_makeup_chk = f"{raw_name_str} {model_str} {note_boq}".lower()
            is_makeup_air_z = (
                any(k in raw_makeup_chk for k in ("cấp khí bù", "bù khí", "cấp gió bù", "bù gió"))
                and not any(k in raw_makeup_chk for k in ("fag", "sag", "rag", "oag", "pag", "seg", "eag", "sdg", "obd", "nan thẳng", "bầu dục"))
            )
            is_ktc = bool(re.search(ktc_rx, dim_search_text, re.IGNORECASE)) or is_makeup_air_z

            # Rule 6 & 7: Kiểm tra dòng sản phẩm kết hợp Van + Cửa (Combo)
            search_combo_txt = f"{raw_name_str} {name_str} {model_str}".lower().replace("\n", " ")
            diff_rx = combo_cfg.get("combo_diffuser_regex", r'\bmiệng\s*gió\b|\bcửa\s*gió\b|\bcửa\s*nan\b|\blouver\b|\bluover\b|\blouvre\b|cửa\s*(?:nan|thẳng|gió|\+)')
            damp_rx = combo_cfg.get("combo_damper_regex", r'\b(mfd|mfsd|md|fd|prd|nrd|vcd)\b|van\s+(?:on/off|on-off|chống\s*cháy|chặn\s*lửa|động\s*cơ|một\s*chiều|1\s*chiều|xả\s*áp)')
            has_diffuser = bool(re.search(diff_rx, search_combo_txt))
            m_damper = re.search(damp_rx, search_combo_txt)

            damper_priority = {"MFSD": 1, "MFD": 2, "FD": 3, "MD": 4, "PRD": 5, "NRD": 6, "VCD": 7}

            def _detect_damper_type(tok_str):
                t = tok_str.strip().lower()
                if re.search(diff_rx, t) and not re.search(r'\b(mfsd|mfd|vcd|vd|nrd|prd|md|fd)\b', t):
                    m_v = re.search(r'\bvan\b.*', t)
                    if not m_v:
                        return None
                    t = m_v.group(0)
                if re.search(r'\bmfsd\b', t): return "MFSD"
                if re.search(r'\bmfd\b|ngăn\s*cháy.*động\s*cơ|chống\s*cháy.*động\s*cơ|chặn\s*lửa.*động\s*cơ', t): return "MFD"
                if re.search(r'\bvcd\b|\bvd\b|điều\s*chỉnh.*lưu\s*lượng', t): return "VCD"
                if re.search(r'\bnrd\b|1\s*chiều|một\s*chiều', t): return "NRD"
                if re.search(r'\bprd\b|xả\s*áp', t): return "PRD"
                if re.search(r'\bmd\b|động\s*cơ|on/off|on-off', t): return "MD"
                if re.search(r'\bfd\b|chặn\s*lửa|chống\s*cháy|dập\s*lửa|cầu\s*chì', t): return "FD"
                return None

            scan_source = f"{raw_name_str} + {model_str}" if model_str else raw_name_str
            tokens = [tk.strip() for tk in re.split(r'\s*(?:\+|(?:\bkèm\b|\bgắn\b|\btích\s*hợp\b|\bkết\s*hợp\b)(?!\s*(?:động\s*cơ|mô\s*tơ|môtơ|mo\s*tơ|motor|cầu\s*chì)))\s*', scan_source, flags=re.IGNORECASE) if tk.strip()]
            detected_dampers = []
            for tk in tokens:
                dt = _detect_damper_type(tk)
                if dt and dt not in detected_dampers:
                    detected_dampers.append(dt)
            if not detected_dampers and m_damper:
                dt = _detect_damper_type(m_damper.group(0))
                if dt:
                    detected_dampers.append(dt)

            if category in ("CUA_GIO", "VAN_GIO") and has_diffuser and m_damper and detected_dampers:
                sorted_dampers = sorted(detected_dampers, key=lambda x: damper_priority.get(x, 99))
                w_diff = (w + 50.0) if (is_ktc and w > 0) else w
                h_diff = (h + 50.0) if (is_ktc and h > 0) else h
                d_diff = (d_val + 50.0) if (is_ktc and d_val > 0) else d_val
                items.append({
                    "source_row": r,
                    "source_sheet": sheet_name,
                    "section": current_section,
                    "raw_name": raw_name_str,
                    "name": name_str,
                    "note_boq": note_boq,
                    "category": "CUA_GIO",
                    "combo_damper": sorted_dampers[0],
                    "combo_dampers": sorted_dampers,
                    "w_damper": w,
                    "h_damper": h,
                    "d_damper": d_val,
                    "model": model_str.upper(),
                    "w": w_diff,
                    "h": h_diff,
                    "d": d_diff,
                    "l": l,
                    "thickness": 0.0,
                    "ei_rating": ei_rating,
                    "unit": str(unit_val).strip() if str(unit_val).strip() else "cái",
                    "qty": float(qty_val),
                    "is_missing_qty": is_missing_qty,
                    "ref_price": ws.cell(r, col_map["price"]).value if "price" in col_map else None,
                    "is_ktc_applied": True
                })

            elif category == "VAN_GIO" and not has_diffuser:
                if len(detected_dampers) > 1:
                    # Sắp xếp theo thứ bậc ưu tiên để chọn van chính (MFSD > MFD > FD > MD > PRD > NRD > VCD)
                    sorted_dampers = sorted(detected_dampers, key=lambda x: damper_priority.get(x, 99))
                    primary_type = sorted_dampers[0]
                    secondary_dampers = sorted_dampers[1:]
                    secondary_type = secondary_dampers[0] if secondary_dampers else None

                    items.append({
                        "source_row": r,
                        "source_sheet": sheet_name,
                        "section": current_section,
                        "raw_name": raw_name_str,
                        "name": name_str,
                        "note_boq": note_boq,
                        "category": "VAN_GIO",
                        "model": primary_type,
                        "secondary_damper": secondary_type,
                        "secondary_dampers": secondary_dampers,
                        "w": w,
                        "h": h,
                        "d": d_val,
                        "l": l,
                        "thickness": thickness,
                        "ei_rating": ei_rating,
                        "unit": str(unit_val).strip() if str(unit_val).strip() else "cái",
                        "qty": float(qty_val),
                        "is_missing_qty": is_missing_qty,
                        "ref_price": ws.cell(r, col_map["price"]).value if "price" in col_map else None
                    })
                else:
                    # Không match combo Van+Van → xử lý như van đơn thông thường
                    item_data = {
                        "source_row": r,
                        "source_sheet": sheet_name,
                        "section": current_section,
                        "raw_name": raw_name_str,
                        "name": name_str,
                        "note_boq": note_boq,
                        "category": category,
                        "orig_category": orig_category,
                        "is_missing_dims": is_missing_dims,
                        "model": model_str.upper(),
                        "w": w,
                        "h": h,
                        "d": d_val,
                        "l": l,
                        "thickness": thickness,
                        "ei_rating": ei_rating,
                        "unit": str(unit_val).strip(),
                        "qty": float(qty_val),
                        "is_missing_qty": is_missing_qty,
                        "ref_price": ws.cell(r, col_map["price"]).value if "price" in col_map else None,
                        "is_ktc_applied": False
                    }
                    items.append(item_data)

            else:
                # Không phải Combo: Xử lý KTC cho Cửa gió (độ dày & chiều dài Van gió lấy trực tiếp từ Agent05_DamperBOM)
                if category == "CUA_GIO" and is_ktc:
                    if w > 0: w += 50.0
                    if h > 0: h += 50.0
                    if d_val > 0: d_val += 50.0

                item_data = {
                    "source_row": r,
                    "source_sheet": sheet_name,
                    "section": current_section,
                    "raw_name": raw_name_str,
                    "name": name_str,
                    "note_boq": note_boq,
                    "category": category,
                    "orig_category": orig_category,
                    "is_missing_dims": is_missing_dims,
                    "model": model_str.upper(),
                    "w": w,
                    "h": h,
                    "d": d_val,
                    "l": l,
                    "thickness": thickness,
                    "ei_rating": ei_rating,
                    "unit": str(unit_val).strip(),
                    "qty": float(qty_val),
                    "is_missing_qty": is_missing_qty,
                    "ref_price": ws.cell(r, col_map["price"]).value if "price" in col_map else None,
                    "is_ktc_applied": True if category == "CUA_GIO" else False
                }
                items.append(item_data)
            
            if max_items and len(items) >= max_items:
                break
                
        return items

    def auto_detect_hvac_sheets(self):
        """
        Tự động nhận diện các Sheet liên quan đến Cơ Điện Lạnh (HVAC/MEP).
        """
        combo_cfg = get_subtype_rules().get("COMBO_AND_DETECTION_RULES", {})
        keywords = combo_cfg.get("hvac_sheet_keywords", [
            "dhkk", "hvac", "thong gio", "thông gió", "thong_gio", 
            "hut khoi", "hút khói", "hut_khoi", "tang ap", "tăng áp", "tang áp", "tăng ap",
            "tang_ap", "duct", "lanh", "lạnh", "ventilation", "m.4 duct"
        ])
        detected = []
        for s in self.wb.sheetnames:
            s_lower = s.lower().strip()
            if any(kw in s_lower for kw in keywords):
                detected.append(s)
        return detected

    def parse_sheets(self, sheet_names=None, max_items_per_sheet=None):
        """
        Quét nhiều sheet dự thầu và gom cụm sản phẩm.
        """
        if sheet_names is None:
            sheet_names = self.auto_detect_hvac_sheets()
            if not sheet_names:
                # Nếu không auto-detect được sheet nào, lấy sheet đầu tiên không phải summary
                for s in self.wb.sheetnames:
                    if not any(k in s.lower() for k in ("summary", "cover", "bìa")):
                        sheet_names = [s]
                        break
                if not sheet_names:
                    sheet_names = [self.wb.sheetnames[0]]

        all_items = []
        for s in sheet_names:
            try:
                sheet_items = self.parse_sheet(s, max_items=max_items_per_sheet)
                all_items.extend(sheet_items)
            except Exception as e:
                print(f"[SwindBOQParser] Cảnh báo khi bóc tách sheet '{s}': {e}")
        return all_items
