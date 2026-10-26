import math
import os
import re
import unicodedata
from swind_utils import get_master_bom_rules, get_master_price_map, extract_duct_fitting_geometry


def excel_round(val, digits=0):
    """Làm tròn số học chuẩn Excel (ROUND HALF UP) khớp với hàm ROUND(..., digits) của Excel."""
    if val is None or val == 0:
        return 0.0
    factor = 10.0 ** digits
    scaled = val * factor
    if scaled >= 0:
        rounded = math.floor(scaled + 0.5 + 1e-9)
    else:
        rounded = math.ceil(scaled - 0.5 - 1e-9)
    return float(rounded / factor)


class Agent04_DuctworkBOM:
    """
    Agent 04 (Upgraded): Kỹ Sư Bóc Tách & Định Giá Hệ Thống Ống Gió & Phụ Kiện (Ductwork, Fittings, Silencers, Canvas, Flex Duct).
    Áp dụng chính xác 100% công thức toán học và đơn giá của file:
      'BẢNG TÍNH GIÁ SWIND chuẩn 2026.xls'
    Bao gồm các sheets:
      1. 'Đơn giá theo m2' (Tôn Hoa Sen vhs, pkvhs, ths, pkths)
      2. 'BG PKV' (Ống vuông, Côn thu US, Chân rẽ SU, Chuyển vuông tròn V-T, Cút vuông 90/60/45/30, Ống lượn Z, Chạc 3 Y, Tê vuông, Bịt đầu, Hộp gió)
      3. 'TINH VT PK TRON' & 'BG PKT ' (Ống tròn xoắn SR, Măng xông, Cút tròn 90/45, Côn thu tròn, Tê tròn, Y tròn, Chân rẽ tròn, Bịt đầu tròn)
      4. 'BG TIEU AM' (Tiêu âm vuông không vách/có vách, Tiêu âm tròn)
      5. 'BG canvas, ventcap' (Khớp nối mềm Canvas vuông/tròn thường & chống cháy, Chụp thông hơi Inox 304 Ventcap)
      6. 'bảo ôn' (Ống gió mềm có bảo ôn và không bảo ôn)
    """

    VHS_RATES = {
        0.48: 150000.0,
        0.58: 157500.0,
        0.75: 185100.0,
        0.95: 223300.0,
        1.15: 254300.0,
        1.50: 342800.0,
    }
    DUCT_FORMULA_MODE = "MPQ_STD"
    PKVHS_RATES = {
        0.48: 184375.0,
        0.58: 189000.0,
        0.75: 222200.0,
        0.95: 268000.0,
        1.15: 305200.0,
        1.50: 428500.0,
    }
    THS_RATES = {
        0.48: 176511.0,
        0.58: 193294.0,
        0.75: 237486.0,
        0.95: 283440.0,
        1.15: 327743.0,
        1.50: 401465.0,
    }
    SPIRAL_AA_RATES = {
        0.48: 155000.0,
        0.58: 168400.0,
        0.75: 209600.0,
        0.95: 250200.0,
        1.15: 296300.0,
        1.50: 371500.0,
    }
    PKTHS_RATES = {
        0.48: 219300.0,
        0.58: 238500.0,
        0.75: 291000.0,
        0.95: 336700.0,
        1.15: 400200.0,
        1.50: 490300.0,
    }

    VENTCAP_SUS304_PRICES = {
        50: 90000.0,
        65: 90000.0,
        80: 95000.0,
        100: 105000.0,
        120: 120000.0,
        125: 120000.0,
        150: 145000.0,
        180: 210000.0,
        200: 250000.0,
        250: 430000.0,
        300: 480000.0,
    }

    FLEX_DUCT_NON_INSUL_ROLL = {
        100: 55000.0,
        125: 62500.0,
        150: 70000.0,
        200: 99500.0,
        250: 115000.0,
        300: 135000.0,
        350: 195000.0,
        400: 230000.0,
    }

    FLEX_DUCT_INSUL_ROLL = {
        100: 130000.0,
        125: 147500.0,
        150: 165000.0,
        200: 190000.0,
        250: 245000.0,
        300: 245000.0,
        350: 280000.0,
        400: 340000.0,
    }

    @classmethod
    def normalize_thickness(cls, thk):
        t = float(thk or 0.0)
        if t <= 0:
            return 0.0
        valid = [0.48, 0.58, 0.75, 0.95, 1.15, 1.50]
        return min(valid, key=lambda x: abs(x - t))

    @classmethod
    def get_duct_thickness(cls, max_dim, is_round=False, explicit_thk=0.0):
        return cls.get_standard_thickness(max_dim, is_round=is_round, explicit_thk=explicit_thk)

    @classmethod
    def get_standard_thickness(cls, max_side, is_round=False, explicit_thk=0.0):
        """
        Xác định độ dày tôn tiêu chuẩn theo kích thước cạnh lớn nhất (BG PKV R3..R7 & TINH VT PK TRON):
          - Vuông: <=700 -> 0.58mm; 701..999 -> 0.75mm; 1000..1499 -> 0.95mm; >=1500 -> 1.15mm
          - Tròn:  <=350 -> 0.58mm; 351..700 -> 0.75mm; 701..1000  -> 0.95mm; >1000  -> 1.15mm
        """
        if explicit_thk and explicit_thk > 0:
            return cls.normalize_thickness(explicit_thk)
        ms = float(max_side or 0.0)
        if is_round:
            if ms <= 350:
                return 0.58
            elif ms <= 700:
                return 0.75
            elif ms <= 1000:
                return 0.95
            else:
                return 1.15
        else:
            if ms <= 700:
                return 0.58
            elif ms <= 999:
                return 0.75
            elif ms <= 1499:
                return 0.95
            else:
                return 1.15

    @classmethod
    def detect_duct_subtype(cls, text, w1=0.0, h1=0.0, w2=0.0, h2=0.0, d1=0.0, d2=0.0, unit=""):
        t = unicodedata.normalize("NFC", str(text or "")).lower().strip()
        u = unicodedata.normalize("NFC", str(unit or "")).lower().strip()
        has_rect_pair = bool(re.search(r'(?<![dDØø])\b\d{2,4}\s*[xX*]\s*\d{2,4}\b', t))
        is_round = (d1 > 0 and w1 == 0) or (
            d1 > 0 and w1 == d1 and h1 == d1 and not has_rect_pair and any(k in t for k in ("tròn", "xoắn", "ø", "dn", "phi", "d1", "d2", "d3", "d4", "d5", "d6", "d7", "d8"))
        )

        if any(k in t for k in ("chụp thông hơi", "chup thong hoi", "ventcap", "vent cap", "chụp khí", "chụp hút")):
            return "VENTCAP"
        if any(k in t for k in ("khớp nối mềm", "khop noi mem", "nối mềm", "noi mem", "bạt mềm", "canvas", "cổ bạt", "co bat")):
            return "CANVAS_RT" if is_round else "CANVAS_SQ"
        if any(k in t for k in ("ống mềm", "ong mem", "ống gió mềm", "ong gio mem", "flexible")) and not any(p in t for p in ("lắp ống mềm", "lap ong mem", "nối ống mềm", "noi ong mem", "ra ống mềm", "chờ ống mềm")) and not t.startswith(("côn", "con ", "chân rẽ", "chan re", "hộp", "hôp", "hop ", "cút", "cut ", "tê ", "te ")):
            return "FLEX_DUCT"
        if any(k in t for k in ("tiêu âm", "tieu am", "silencer")):
            return "SILENCER_RT" if is_round else "SILENCER_SQ"
        if any(k in t for k in ("hộp gió", "hôp gió", "hop gio", "box cửa gió", "box gió", "hộp cho cửa", "hộp góp gió", "hộp tĩnh áp", "plenum")):
            return "PLENUM_BOX"
        if any(k in t for k in ("côn thu vuông tròn", "con thu vuong tron", "côn vuông tròn", "con vuong tron", "vuông tròn", "vuong tron", "vuông sang tròn", "tròn sang vuông", "chuyển tiết diện", "chuyen tiet dien", "côn đầu quạt", "con dau quat", "v-t", "cvt")) or (not is_round and w1 > 0 and h1 > 0 and d1 > 0 and w2 == 0):
            return "SQUARE_TO_ROUND"
        if any(k in t for k in ("bịt đầu", "bit dau", "nắp bịt", "nap bit", "bịt 1 đầu", "bit 1 dau", "bịt ống", "bit ong")):
            return "END_CAP_RT" if is_round else "END_CAP_SQ"
        if any(k in t for k in ("măng xông", "mang xong", "măng sông", "mang song", "nối ống", "noi ong")):
            return "COUPLING_RT"
        if any(k in t for k in ("chạc 3", "chac 3", "chạc ba", "chạc y", "ống quần", "y vuông", "y tròn")) or re.search(r'\by\s*[:=]\s*d\d+', t):
            return "WYE_RT" if is_round else "WYE_SQ"
        if any(k in t for k in ("tê vuông", "te vuong", "tê tròn", "te tron", "tê đều", "tê thu", "tê ống", "tee")) or re.search(r'\btê\b', t):
            return "TEE_RT" if is_round else "TEE_SQ"
        if any(k in t for k in ("zét lượn", "zet luon", "zét", "ống lượn", "ong luon", "lượn ống gió", "luon ong gio", "lượn z", "luon z", "z chuyển cao độ", "z chuyen cao do", "z chuyển hướng", "z chuyen huong", "offset")) or re.search(r'\bz\s*vuông\b|(?:^|\s)z\s*\d{2,4}\s*[xX*]\s*\d{2,4}', t):
            return "OFFSET_Z"
        if any(k in t for k in ("cút vuông", "cut vuong", "cút tròn", "cut tron", "cút", "cut ", "co 90", "co 60", "co 45", "co 30", "co vuông", "co tròn", "co ống", "chếch", "chech", "bs90", "bs45", "bt90", "bt45", "elbow")):
            return "ELBOW_RT" if is_round else "ELBOW_SQ"
        if any(k in t for k in ("chân rẽ", "chan re", "gót giày", "got giay", "cổ trích", "co trich", "chân trích", "take off", "take-off")):
            return "TAKEOFF_RT" if is_round else "SHOE_TAP"
        if any(k in t for k in ("côn vuông", "con vuong", "côn tròn", "con tron", "côn thu", "con thu", "côn giảm", "con giam", "giảm đều", "giam deu", "giảm vuông", "giảm tròn", "côn lệch", "côn phẳng", "con phang", "côn đồng tâm", "thu vuông", "thu tròn", "reducer")) or t.startswith(("côn ", "con ")) or (w1 > 0 and w2 > 0 and (w1 != w2 or h1 != h2)):
            return "REDUCER_RT" if is_round else "REDUCER_SQ"
        if "phụ kiện" in t and w1 == 0 and d1 == 0:
            return "FITTING_M2"
        if is_round or any(k in t for k in ("tròn xoắn", "ống tròn", "ống gió tròn")):
            return "SPIRAL_DUCT"
        if w1 == 0 and h1 == 0 and d1 == 0 and ("m2" in u or "m²" in u or "m2" in t):
            return "DUCT_M2"
        return "DUCT_RECT"

    @classmethod
    def calculate_duct_item(cls, item):
        """
        Tính toán đầy đủ diện tích S (m2), độ dày tôn (mm), đơn giá bán (VNĐ) và giải trình công thức
        cho một hạng mục thuộc nhóm ONG_GIO, TIEU_AM, CANVAS, ONG_MEM.
        """
        raw_name = unicodedata.normalize("NFC", str(item.get("raw_name") or item.get("name") or ""))
        note_boq = unicodedata.normalize("NFC", str(item.get("note_boq") or ""))
        unit = unicodedata.normalize("NFC", str(item.get("unit") or "cái")).strip().lower()
        full_text = f"{raw_name} {note_boq}".strip()

        w_in = float(item.get("w") or 0.0)
        h_in = float(item.get("h") or 0.0)
        d_in = float(item.get("d") or 0.0)
        w2_in = float(item.get("w2") or 0.0)
        h2_in = float(item.get("h2") or 0.0)

        has_explicit_rect = bool(re.search(r'(?<![dDØø])\b\d{2,4}\s*[xX*]\s*\d{2,4}\b', full_text))
        def_w = 0.0 if (d_in > 0 and w_in == d_in and h_in == d_in and not has_explicit_rect) else w_in
        def_h = 0.0 if (d_in > 0 and w_in == d_in and h_in == d_in and not has_explicit_rect) else h_in
        prev_geom = item.get("fitting_geom") or {}
        geom = extract_duct_fitting_geometry(full_text, default_w=def_w, default_h=def_h, default_d=d_in, default_w2=w2_in, default_h2=h2_in)
        w1 = geom["w1"] or prev_geom.get("w1") or 0.0
        h1 = geom["h1"] or prev_geom.get("h1") or 0.0
        w2 = geom["w2"] or prev_geom.get("w2") or 0.0
        h2 = geom["h2"] or prev_geom.get("h2") or 0.0
        d1 = geom["d1"] or prev_geom.get("d1") or 0.0
        d2 = geom["d2"] or prev_geom.get("d2") or 0.0
        has_explicit_l = bool(
            (item.get("l") and not item.get("_default_l"))
            or geom.get("has_explicit_l")
            or prev_geom.get("has_explicit_l")
        )
        length = float(item.get("length") or item.get("l") or geom["length"] or prev_geom.get("length") or 0.0)
        radius = float(geom["radius"] or prev_geom.get("radius") or 0.0)
        offset_h = float(geom["offset_h"] or prev_geom.get("offset_h") or 0.0)
        angle = int(geom["angle"] if geom["angle"] != 90 else (prev_geom.get("angle") or 90))
        explicit_thk = float(item.get("thickness") or geom["thickness"] or prev_geom.get("thickness") or 0.0)
        flange_type = str(item.get("flange_type") or prev_geom.get("flange_type") or geom["flange_type"] or "TDC").upper()
        neck_count = int(item.get("neck_count") or geom["neck_count"] or prev_geom.get("neck_count") or 1)
        ei_rating = int(item.get("ei_rating") or geom["ei_rating"] or prev_geom.get("ei_rating") or 0)
        is_insulated = bool(item.get("is_insulated") or geom["is_insulated"] or prev_geom.get("is_insulated"))

        subtype = cls.detect_duct_subtype(full_text, w1, h1, w2, h2, d1, d2, unit)

        if subtype == "VENTCAP":
            return cls._calc_ventcap_item(w1, h1, d1)

        if subtype in ("CANVAS_SQ", "CANVAS_RT"):
            return cls._calc_canvas_item(subtype, full_text, unit, w1, h1, d1, length)

        if subtype == "FLEX_DUCT":
            return cls._calc_flex_duct_item(unit, w1, h1, d1, is_insulated)

        if subtype in ("SILENCER_SQ", "SILENCER_RT"):
            return cls._calc_silencer_item(
                subtype, raw_name, full_text, unit, w1, h1, w2, h2, d1,
                length, radius, angle, explicit_thk, def_w, def_h, d_in, w2_in, h2_in, ei_rating
            )

        if subtype in ("DUCT_M2", "FITTING_M2"):
            return cls._calc_m2_duct_or_fitting_item(subtype, full_text, explicit_thk, ei_rating)

        if subtype in ("SPIRAL_DUCT", "ELBOW_RT", "REDUCER_RT", "TEE_RT", "WYE_RT", "TAKEOFF_RT", "COUPLING_RT", "END_CAP_RT"):
            return cls._calc_round_duct_or_fitting_item(
                subtype, full_text, unit, w1, h1, w2, h2, d1, d2, length, angle, explicit_thk
            )

        return cls._calc_rect_duct_or_fitting_item(
            subtype, item, full_text, unit, w1, h1, w2, h2, d1,
            length, has_explicit_l, radius, offset_h, angle,
            explicit_thk, flange_type, neck_count, ei_rating, is_insulated
        )

    @classmethod
    def _calc_ventcap_item(cls, w1, h1, d1):
        d_val = d1 if d1 > 0 else max(w1, h1, 100.0)
        nearest_d = min(cls.VENTCAP_SUS304_PRICES.keys(), key=lambda k: abs(k - d_val))
        unit_price = cls.VENTCAP_SUS304_PRICES[nearest_d]
        return {
            "subtype": "VENTCAP",
            "model_std": f"SFX-S-DN{int(nearest_d)}",
            "thickness": 0.8,
            "l_mm": None,
            "b1": None, "b2": None,
            "area_m2": 0.0,
            "unit_price": unit_price,
            "spec_note": f"Chụp thông hơi Inox SUS 304 kèm lưới chắn côn trùng DN{int(nearest_d)}",
            "trace": f"BG canvas, ventcap!DN{int(nearest_d)} = {unit_price:,.0f} đ"
        }

    @classmethod
    def _calc_canvas_item(cls, subtype, full_text, unit, w1, h1, d1, length):
        t_low = full_text.lower()
        is_fire = any(k in t_low for k in (
            "chống cháy", "chịu nhiệt", "silicone", "vải thủy tinh", "ei",
            "đầu quạt", "dau quat", "trước và sau quạt", "truoc va sau quat",
            "nối quạt", "noi quat", "cổ quạt", "co quat", "quạt", "fan", "hút khói", "tăng áp"
        )) and not ("loại thường" in t_low or ("fcu" in t_low and "chống cháy" not in t_low))
        if is_fire:
            mat_rate = 134400.0 if "150" in t_low else 124800.0
        else:
            mat_rate = 67200.0 if "150" in t_low else 57600.0
        labor_pc = 30000.0
        if subtype == "CANVAS_RT" or (d1 > 0 and (w1 == 0 or w1 == d1)):
            d_val = d1 if d1 > 0 else w1
            perim_m = (d_val * 3.14) / 1000.0
            flange_rate = 50000.0
        else:
            perim_m = (w1 + h1) * 2.0 / 1000.0
            flange_rate = 30000.0

        if any(k in t_low for k in ("không bích", "ko bích", "2 đầu thẳng", "hai đầu thẳng")):
            flange_ends = 0
            conn_note = "2 đầu thẳng (không bích)"
        elif any(k in t_low for k in ("2 đầu bích", "hai đầu bích")):
            flange_ends = 2
            conn_note = "2 đầu bích"
        else:
            flange_ends = 1
            conn_note = "1 đầu thẳng 1 đầu bích"

        if perim_m <= 0:
            unit_price = 0.0
        elif unit in ("m", "md", "mét"):
            unit_price = excel_round(mat_rate + flange_rate * flange_ends + labor_pc / max(perim_m, 1.0), -2)
        else:
            unit_price = excel_round(mat_rate * perim_m + flange_rate * perim_m * flange_ends + labor_pc, -2)

        return {
            "subtype": subtype,
            "model_std": "CANVAS-CHONG-CHAY" if is_fire else "CANVAS",
            "thickness": 0.45,
            "l_mm": int(length) if length > 0 else 200,
            "b1": None, "b2": None,
            "area_m2": round(perim_m * 0.2, 3),
            "unit_price": unit_price,
            "spec_note": f"Khớp nối mềm Canvas {'chống cháy' if is_fire else 'thường'} ({conn_note})",
            "trace": f"BG canvas, ventcap: Chu vi={perim_m:.3f}m, N={mat_rate:,.0f}, Bích={flange_rate:,.0f}x{flange_ends} ({conn_note}), NC={labor_pc:,.0f}"
        }

    @classmethod
    def _calc_flex_duct_item(cls, unit, w1, h1, d1, is_insulated):
        d_val = d1 if d1 > 0 else max(w1, h1, 100.0)
        table = cls.FLEX_DUCT_INSUL_ROLL if is_insulated else cls.FLEX_DUCT_NON_INSUL_ROLL
        nearest_d = min(table.keys(), key=lambda k: abs(k - d_val))
        roll_price = table[nearest_d]
        if unit in ("m", "md", "mét"):
            unit_price = excel_round(roll_price / 8.0, -2)
        else:
            unit_price = roll_price
        return {
            "subtype": "FLEX_DUCT",
            "model_std": f"FLEX-D{int(nearest_d)}-{'BO' if is_insulated else 'KBO'}",
            "thickness": 0.0,
            "l_mm": 8000,
            "b1": None, "b2": None,
            "area_m2": 0.0,
            "unit_price": unit_price,
            "spec_note": f"Ống gió mềm D{int(nearest_d)} {'có bảo ôn bông thủy tinh' if is_insulated else 'không bảo ôn'} (8m/ống)",
            "trace": f"Sheet 'bảo ôn': D{int(nearest_d)} ({'Có BO' if is_insulated else 'Không BO'}) = {roll_price:,.0f} đ/ống 8m"
        }

    @classmethod
    def _calc_silencer_item(cls, subtype, raw_name, full_text, unit, w1, h1, w2, h2, d1, length, radius, angle, explicit_thk, def_w, def_h, d_in, w2_in, h2_in, ei_rating=0):
        L_val = length if length > 0 else 1000.0
        if subtype == "SILENCER_RT" or (d1 > 0 and (w1 == 0 or w1 == d1)):
            D_outer = d1 if d1 > 0 else w1
            D_inner = max(D_outer - 100.0, 50.0)
            thk = cls.get_standard_thickness(D_outer, is_round=True, explicit_thk=explicit_thk)
            pk_rate = cls.PKTHS_RATES.get(thk, 238500.0)
            s_outer = (D_outer * 3.14 * L_val) / 1e6
            s_inner = (D_inner * 3.14 * L_val) / 1e6
            cost_shell = s_outer * pk_rate
            cost_core = s_inner * (55000.0 + 65000.0 + 15000.0)
            cost_labor = (cost_shell + cost_core) * 0.45
            unit_price = excel_round(cost_shell + cost_core + cost_labor, -3)
            if ei_rating > 0:
                ei_surcharge = {30: 345000.0, 45: 420000.0, 60: 520000.0, 90: 680000.0, 120: 850000.0}.get(ei_rating, 345000.0)
                unit_price = excel_round(unit_price + s_outer * ei_surcharge, -2)
            if unit in ("m2", "m²") and s_outer > 0:
                unit_price = excel_round(unit_price / s_outer, -2)
            return {
                "subtype": "SILENCER_RT",
                "model_std": "TA-TRON",
                "thickness": thk,
                "l_mm": int(L_val),
                "b1": "Ø", "b2": int(D_inner),
                "area_m2": round(s_outer, 3),
                "unit_price": unit_price,
                "spec_note": f"Tiêu âm tròn D{int(D_outer)}xL{int(L_val)}, tôn Hoa Sen dày {thk:.2f}mm, bông khoáng 60kg/m3 + vải thủy tinh + tôn đục lỗ" + (f", bọc chống cháy EI{ei_rating}" if ei_rating > 0 else ""),
                "trace": f"BG TIEU AM (Tròn): S_vỏ={s_outer:.3f}m2, S_ruột={s_inner:.3f}m2, Tôn={thk}mm"
            }
        else:
            geom_raw = extract_duct_fitting_geometry(raw_name, default_w=def_w, default_h=def_h, default_d=d_in, default_w2=w2_in, default_h2=h2_in)
            w1_s = geom_raw["w1"] or w1
            h1_s = geom_raw["h1"] or h1
            w2_s = geom_raw["w2"] if geom_raw["w1"] > 0 else w2
            h2_s = geom_raw["h2"] if geom_raw["h1"] > 0 else h2
            R_s = geom_raw["radius"] or radius
            L_s = (geom_raw["length"] or length) if (geom_raw["length"] or length) > 0 else 1000.0
            W_outer, H_outer = max(w1_s, 100.0), max(h1_s, 100.0)
            W_inner, H_inner = max(W_outer - 100.0, 50.0), max(H_outer - 100.0, 50.0)
            thk = cls.get_standard_thickness(max(W_outer, H_outer), is_round=False, explicit_thk=explicit_thk)
            t_name_low = raw_name.lower()
            t_full_low = full_text.lower()
            is_silencer_fitting = any(k in t_name_low for k in (
                "phụ kiện", "phu kien", "cút", "cut ", "co ", "chếch", "chech",
                "côn", "con ", "tê ", "te ", "chạc", "chac", "chân rẽ", "chan re",
                "gót giày", "got giay", "zét", "zet", "ống lượn", "ong luon", "bịt đầu", "bit dau"
            )) or ("phụ kiện tiêu âm" in t_full_low)
            if w1_s == 0 and h1_s == 0:
                s_outer = 1.0
                l_out_s = None
            elif is_silencer_fitting and any(k in t_name_low for k in ("cút", "cut ", "co ", "chếch", "chech")):
                R_val = R_s if R_s > 0 else (W_outer / 2.0)
                if angle == 60:
                    el_factor = (2.0 * 1.1) / 3.0
                elif angle == 45:
                    el_factor = 1.1 / 2.0
                elif angle == 30:
                    el_factor = 1.1 / 3.0
                else:
                    el_factor = 1.0
                s_1 = 1.57 * (W_outer * W_outer + 2.0 * W_outer * R_val) / 1e6
                s_2 = 1.57 * (W_outer + R_val) * (H_outer + 80.0) / 1e6
                s_3 = 1.57 * R_val * (H_outer + 80.0) / 1e6
                s_4 = ((W_outer + H_outer) * 2.0 * 100.0) / 1e6
                s_outer = (s_1 + s_2 + s_3 + s_4) * el_factor
                l_out_s = int(R_val)
            elif is_silencer_fitting and any(k in t_name_low for k in ("côn", "con ", "chân rẽ", "chan re", "gót giày", "got giay")):
                W2_val = w2_s if w2_s > 0 else max(W_outer - 100.0, 100.0)
                H2_val = h2_s if h2_s > 0 else H_outer
                L_red = (geom_raw["length"] or length) if (geom_raw["length"] or length) > 0 else 500.0
                s_outer = (((W_outer + W2_val + 28.0) * (L_red + 90.0)) + ((H_outer + H2_val + 120.0) * (L_red + 90.0))) / 1e6
                l_out_s = int(L_red)
            else:
                s_outer = ((W_outer + H_outer) * 2.0 * L_s) / 1e6
                l_out_s = int(L_s)

            silencer_rate = 950000.0 * 1.3 if is_silencer_fitting else 950000.0
            if ei_rating > 0:
                ei_surcharge = {30: 345000.0, 45: 420000.0, 60: 520000.0, 90: 680000.0, 120: 850000.0}.get(ei_rating, 345000.0)
                silencer_rate += ei_surcharge
            if unit in ("m2", "m²"):
                unit_price = excel_round(silencer_rate, -2)
            else:
                unit_price = excel_round(s_outer * silencer_rate, -2)
            return {
                "subtype": "SILENCER_SQ",
                "model_std": "PK-TA-VUONG" if is_silencer_fitting else "TA-VUONG",
                "thickness": thk,
                "l_mm": l_out_s,
                "b1": int(W_inner) if w1_s > 0 else None,
                "b2": int(H_inner) if h1_s > 0 else None,
                "area_m2": round(s_outer, 3),
                "unit_price": unit_price,
                "spec_note": f"{'Phụ kiện tiêu âm vuông' if is_silencer_fitting else 'Hộp tiêu âm vuông'}" + (f" {int(W_outer)}x{int(H_outer)}" if (w1_s > 0 and h1_s > 0) else "") + (f" R={l_out_s}" if (is_silencer_fitting and any(k in t_name_low for k in ('cút', 'cut ', 'co ', 'chếch', 'chech'))) else (f"xL{l_out_s}" if l_out_s else "")) + f", tôn Hoa Sen dày {thk:.2f}mm, bông khoáng 60kg/m3 + vải thủy tinh + tôn đục lỗ" + (f", bọc chống cháy EI{ei_rating}" if ei_rating > 0 else ""),
                "trace": f"BG TIEU AM ({'Phụ kiện tiêu âm vuông x1.3' if is_silencer_fitting else 'Tiêu âm vuông'}): S={s_outer:.3f}m2 x {silencer_rate:,.0f} đ/m2 = {unit_price:,.0f} đ"
            }

    @classmethod
    def _calc_m2_duct_or_fitting_item(cls, subtype, full_text, explicit_thk, ei_rating):
        thk = cls.normalize_thickness(explicit_thk) if explicit_thk > 0 else 0.58
        is_round_m2 = any(k in full_text.lower() for k in ("tròn", "xoắn"))
        if subtype == "FITTING_M2":
            base_rate = cls.PKTHS_RATES.get(thk, 238500.0) if is_round_m2 else cls.PKVHS_RATES.get(thk, 189000.0)
        else:
            base_rate = cls.THS_RATES.get(thk, 193294.0) if is_round_m2 else cls.VHS_RATES.get(thk, 157500.0)
        if ei_rating > 0:
            ei_surcharge = {30: 345000.0, 45: 420000.0, 60: 520000.0, 90: 680000.0, 120: 850000.0}.get(ei_rating, 345000.0)
            base_rate += ei_surcharge
        return {
            "subtype": subtype,
            "model_std": "PK-M2" if subtype == "FITTING_M2" else "ONG-M2",
            "thickness": thk,
            "l_mm": None,
            "b1": None, "b2": None,
            "area_m2": 1.0,
            "unit_price": excel_round(base_rate, -2),
            "spec_note": f"{'Phụ kiện ống gió' if subtype == 'FITTING_M2' else 'Ống gió'} tôn Hoa Sen dày {thk:.2f}mm" + (f" bọc chống cháy EI{ei_rating}" if ei_rating > 0 else ""),
            "trace": f"Đơn giá theo m2: Tôn {thk}mm = {base_rate:,.0f} đ/m2"
        }

    @classmethod
    def _calc_round_duct_or_fitting_item(cls, subtype, full_text, unit, w1, h1, w2, h2, d1, d2, length, angle, explicit_thk):
        D_main = d1 if d1 > 0 else max(w1, h1, 100.0)
        D_sub = d2 if d2 > 0 else (min(w2, h2) if w2 > 0 else D_main)
        thk = cls.get_standard_thickness(max(D_main, D_sub), is_round=True, explicit_thk=explicit_thk)
        pkths = cls.PKTHS_RATES.get(thk, 238500.0)
        aa_rate = cls.SPIRAL_AA_RATES.get(thk, 168400.0)

        if subtype == "SPIRAL_DUCT":
            s_1m = (3.14 * D_main * 1.05) / 1000.0
            price_per_m = excel_round(aa_rate * s_1m * 1.25, -3)
            if unit in ("m2", "m²"):
                area_val = 1.0
                unit_price = excel_round(cls.THS_RATES.get(thk, 193294.0), -2)
            elif unit in ("cái", "ống", "đoạn", "bộ", "pcs", "ea") and length > 0:
                s_raw_sp = s_1m * (length / 1000.0)
                area_val = 0.3 if s_raw_sp < 0.3 else s_raw_sp
                unit_price = excel_round(aa_rate * area_val * 1.25, -3)
            else:
                area_val = 0.3 if s_1m < 0.3 else s_1m
                unit_price = excel_round(aa_rate * area_val * 1.25, -3)
            return {
                "subtype": "SPIRAL_DUCT",
                "model_std": f"SR-D{int(D_main)}",
                "thickness": thk,
                "l_mm": int(length) if length > 0 else 1000,
                "b1": None, "b2": None,
                "area_m2": round(area_val, 3),
                "unit_price": unit_price,
                "spec_note": f"Ống gió tròn xoắn D{int(D_main)}, tôn Hoa Sen dày {thk:.2f}mm",
                "trace": f"TINH VT PK TRON (Ống tròn xoắn D{int(D_main)}, tôn {thk}mm): S={area_val:.3f}m2, Giá={unit_price:,.0f} đ"
            }

        elif subtype == "COUPLING_RT":
            s_area = max((3.14 * D_main * 0.10) / 1000.0, 0.3) if ((3.14 * D_main * 0.10) / 1000.0) < 0.3 else (3.14 * D_main * 0.10) / 1000.0
            unit_price = excel_round(pkths * s_area * 1.4, -3)
            spec_label = f"Măng xông ống tròn D{int(D_main)}"
            l_out = 100
        elif subtype == "ELBOW_RT":
            s_90 = (3.14 * D_main * (1.57 * 1.2 * D_main + 100.0) * 1.3) / 1e6
            s_90_eff = 0.3 if s_90 < 0.3 else s_90
            p_90 = excel_round(s_90_eff * pkths * 1.3, -3)
            if angle == 60:
                s_area = s_90 * (2.0 / 3.0)
                if s_area < 0.3:
                    s_area = 0.3
                    unit_price = excel_round(s_area * pkths * 1.3, -2)
                else:
                    unit_price = excel_round(p_90 * (2.0 * 1.1 / 3.0), -2)
            elif angle == 45:
                s_area = (3.14 * D_main * (0.785 * 1.2 * D_main + 100.0) * 1.3) / 1e6
                if s_area < 0.3:
                    s_area = 0.3
                unit_price = excel_round(s_area * pkths * 1.4, -3)
            elif angle == 30:
                s_area = s_90 / 3.0
                if s_area < 0.3:
                    s_area = 0.3
                    unit_price = excel_round(s_area * pkths * 1.3, -2)
                else:
                    unit_price = excel_round(p_90 * (1.1 / 3.0), -2)
            else:
                s_area = s_90_eff
                unit_price = p_90
            spec_label = f"Cút tròn {angle}° D{int(D_main)}"
            l_out = None
        elif subtype == "REDUCER_RT":
            L_red = length if length > 0 else 200.0
            s_area = (3.14 * max(D_main, D_sub) * (L_red + 80.0)) / 1e6
            if s_area < 0.3:
                s_area = 0.3
            unit_price = excel_round(s_area * pkths * 1.4, -3)
            spec_label = f"Côn thu tròn D{int(D_main)}/D{int(D_sub)}"
            l_out = int(L_red)
        elif subtype == "TEE_RT":
            L_body = D_main + 200.0
            L_branch = 200.0
            s_1 = (3.14 * D_main * L_body * 1.2) / 1e6
            s_2 = (3.14 * D_sub * L_branch * 1.2) / 1e6
            s_area = s_1 + s_2
            if s_area < 0.3:
                s_area = 0.3
            unit_price = excel_round(s_area * pkths * 1.35, -3)
            spec_label = f"Tê tròn D{int(D_main)}/D{int(D_sub)}"
            l_out = int(L_body)
        elif subtype == "WYE_RT":
            s_1 = (3.14 * D_main * (D_main + 200.0) * 1.2) / 1e6
            s_2 = (3.14 * D_sub * 250.0 * 1.5) / 1e6
            s_area = s_1 + s_2
            if s_area < 0.3:
                s_area = 0.3
            unit_price = excel_round(s_area * pkths * 1.4, -3)
            spec_label = f"Chạc Y tròn D{int(D_main)}/D{int(D_sub)}"
            l_out = None
        elif subtype == "TAKEOFF_RT":
            s_area = (3.14 * D_main * 200.0) / 1e6
            if s_area < 0.3:
                s_area = 0.3
            unit_price = excel_round(s_area * pkths * 1.5, -3)
            spec_label = f"Chân rẽ tròn (Cổ trích) D{int(D_main)}"
            l_out = 200
        else:
            s_area = (3.14 * D_main * 50.0 + 3.14 * ((D_main / 2.0) ** 2)) / 1e6
            if s_area < 0.3:
                s_area = 0.3
            unit_price = excel_round(s_area * pkths * 1.3, -3)
            spec_label = f"Bịt đầu ống tròn D{int(D_main)}"
            l_out = 50

        rt_model_map = {
            "COUPLING_RT": "Măng xông tròn",
            "ELBOW_RT": "Cút tròn",
            "REDUCER_RT": "Côn thu tròn",
            "TEE_RT": "Tê tròn",
            "WYE_RT": "Chạc Y tròn",
            "TAKEOFF_RT": "Chân rẽ tròn",
            "END_CAP_RT": "Bịt đầu tròn",
        }
        model_out = rt_model_map.get(subtype, subtype)
        if any(k in full_text.lower() for k in ("côn trùng", "lcct", "lưới chắn", "insect screen", "i.s")) or bool(re.search(r'\b(?:i\.s\.?|c/w\s*is)\b', full_text.lower())):
            mesh_surcharge = excel_round((D_main / 1000.0) * (D_main / 1000.0) * 150000.0, 0)
            unit_price += mesh_surcharge
            model_out = f"{model_out} + LCCT"
            spec_label = f"{spec_label} kèm lưới chắn côn trùng"
        return {
            "subtype": subtype,
            "model_std": model_out,
            "thickness": thk,
            "l_mm": l_out,
            "b1": "Ø" if D_sub != D_main else None,
            "b2": int(D_sub) if D_sub != D_main else None,
            "area_m2": round(s_area, 3),
            "unit_price": unit_price,
            "spec_note": f"{spec_label}, tôn Hoa Sen dày {thk:.2f}mm",
            "trace": f"TINH VT PK TRON / BG PKT ({spec_label}, tôn {thk}mm, pkths={pkths:,.0f}): S={s_area:.3f}m2 -> {unit_price:,.0f} đ"
        }

    @classmethod
    def _calc_rect_duct(cls, w1, h1, length, unit, thk, vhs, flange_type, ei_rating):
        std_l = 1180.0 if flange_type == "NEP_C" else 1110.0
        default_l = 1000.0 if unit in ("m", "md", "mét") else std_l
        L_val = length if length > 0 else default_l
        l_out = int(L_val)
        s_raw = ((w1 + h1) * 2.0 * L_val) / 1e6
        s_area = 0.3 if (s_raw < 0.3 and unit not in ("m", "md", "mét", "m2", "m²")) else s_raw
        short_factor = 1.05 if (0.0 < L_val < std_l and unit not in ("m", "md", "mét", "m2", "m²")) else 1.0
        if unit in ("m2", "m²"):
            price_nep_c = excel_round(vhs, -2)
            price_tdc = excel_round(vhs, -2)
            s_area = 1.0
        else:
            price_nep_c = excel_round((vhs * short_factor) * s_area, -2)
            price_tdc = price_nep_c + 16000.0
        unit_price = price_nep_c if flange_type == "NEP_C" else price_tdc
        if ei_rating > 0:
            ei_surcharge = {30: 345000.0, 45: 420000.0, 60: 520000.0, 90: 680000.0, 120: 850000.0}.get(ei_rating, 345000.0)
            unit_price = excel_round(s_area * ei_surcharge + unit_price, -2)
        spec_label = f"Ống gió vuông {int(w1)}x{int(h1)}xL{int(L_val)}"
        s_note = f"{s_raw:.3f}->0.300m2 (quy <0.3)" if (s_raw < 0.3 and unit not in ("m", "md", "mét", "m2", "m²")) else f"{s_area:.3f}m2"
        trace_str = f"BG PKV (Ống vuông {int(w1)}x{int(h1)} L={int(L_val)}, tôn {thk}mm, {flange_type}): S={s_note}, vhs={vhs:,.0f}" + (f" x1.05 (ống ngắn <{int(std_l)})" if short_factor > 1.0 else f" (nguyên khổ L{int(std_l)})")
        return None, None, l_out, s_area, unit_price, spec_label, trace_str

    @classmethod
    def _calc_rect_reducer(cls, w1, h1, w2, h2, length, has_explicit_l, formula_mode, thk, pkvhs, flange_type, ei_rating):
        W2_val = w2 if w2 > 0 else max(w1 - 100.0, 100.0)
        H2_val = h2 if h2 > 0 else h1
        L_val = length if (has_explicit_l and length > 0) or length not in (0.0, 200.0, 1110.0) else 500.0
        b1_out, b2_out, l_out = int(W2_val), int(H2_val), int(L_val)
        if formula_mode == "OG_MB_M2":
            s_1 = ((w1 + W2_val) * math.sqrt(L_val ** 2 + ((h1 - H2_val) / 2.0) ** 2)) / 1e6
            s_2 = ((h1 + H2_val) * math.sqrt(L_val ** 2 + ((w1 - W2_val) / 2.0) ** 2)) / 1e6
            s_raw = s_1 + s_2
            trace_prefix = "ÔG MB Z3 m2"
        else:
            s_1 = ((w1 + W2_val + 28.0) * (L_val + 90.0)) / 1e6
            s_2 = ((h1 + H2_val + 120.0) * (L_val + 90.0)) / 1e6
            s_raw = s_1 + s_2
            trace_prefix = "BG PKV"
        s_area = 0.3 if s_raw < 0.3 else s_raw
        price_nep_c = excel_round(s_area * pkvhs, -2)
        price_tdc = price_nep_c + 16000.0
        unit_price = price_nep_c if flange_type == "NEP_C" else price_tdc
        if ei_rating > 0:
            ei_surcharge = {30: 345000.0, 45: 420000.0, 60: 520000.0, 90: 680000.0, 120: 850000.0}.get(ei_rating, 345000.0)
            unit_price = excel_round(s_area * ei_surcharge + unit_price, -2)
        spec_label = f"Côn vuông {int(w1)}x{int(h1)}/{int(W2_val)}x{int(H2_val)} L={int(L_val)}"
        s_note = f"{s_raw:.3f}->0.300m2 (quy <0.3)" if s_raw < 0.3 else f"{s_area:.3f}m2"
        trace_str = f"{trace_prefix} (Côn vuông, tôn {thk}mm, {flange_type}): S={s_note}, pkvhs={pkvhs:,.0f}"
        return b1_out, b2_out, l_out, s_area, unit_price, spec_label, trace_str

    @classmethod
    def _calc_rect_shoe_tap(cls, w1, h1, w2, h2, d1, length, has_explicit_l, formula_mode, thk, pkvhs, flange_type, ei_rating):
        W2_val = w2 if w2 > 0 else (d1 if d1 > 0 else w1)
        H2_val = h2 if h2 > 0 else (d1 if d1 > 0 else h1)
        L_val = length if (has_explicit_l and length > 0) or length not in (0.0, 1110.0) else 300.0
        b1_out = "Ø" if (d1 > 0 and w2 == 0) else int(W2_val)
        b2_out, l_out = int(d1 if (d1 > 0 and w2 == 0) else H2_val), int(L_val)
        if formula_mode == "OG_MB_M2":
            s_1 = ((w1 + W2_val) * math.sqrt(L_val ** 2 + ((h1 - H2_val) / 2.0) ** 2)) / 1e6
            s_2 = ((h1 + H2_val) * math.sqrt(L_val ** 2 + ((w1 - W2_val) / 2.0) ** 2)) / 1e6
            s_raw = s_1 + s_2
            trace_prefix = "ÔG MB Z3 m2"
        else:
            s_1 = ((w1 + W2_val + 28.0) * (L_val + 70.0)) / 1e6
            s_2 = ((h1 + H2_val + 120.0) * (L_val + 70.0)) / 1e6
            s_raw = s_1 + s_2
            trace_prefix = "BG PKV"
        s_area = 0.3 if s_raw < 0.3 else s_raw
        price_nep_c = excel_round(s_area * pkvhs, -2)
        price_tdc = price_nep_c + 16000.0
        unit_price = price_nep_c if flange_type == "NEP_C" else price_tdc
        if ei_rating > 0:
            ei_surcharge = {30: 345000.0, 45: 420000.0, 60: 520000.0, 90: 680000.0, 120: 850000.0}.get(ei_rating, 345000.0)
            unit_price = excel_round(s_area * ei_surcharge + unit_price, -2)
        spec_label = f"Chân rẽ vuông (SU) {int(w1)}x{int(h1)}/{int(W2_val)}x{int(H2_val)} L={int(L_val)}"
        s_note = f"{s_raw:.3f}->0.300m2 (quy <0.3)" if s_raw < 0.3 else f"{s_area:.3f}m2"
        trace_str = f"{trace_prefix} (Chân rẽ SU, tôn {thk}mm, {flange_type}): S={s_note}, pkvhs={pkvhs:,.0f}"
        return b1_out, b2_out, l_out, s_area, unit_price, spec_label, trace_str

    @classmethod
    def _calc_square_to_round(cls, w1, h1, w2, d1, length, has_explicit_l, formula_mode, thk, pkths, flange_type):
        D_val = d1 if d1 > 0 else (w2 if w2 > 0 else min(w1, h1))
        L_val = length if (has_explicit_l and length > 0) or length not in (0.0, 1110.0) else 300.0
        b1_out, b2_out, l_out = "Ø", int(D_val), int(L_val)
        if formula_mode == "OG_MB_M2":
            a_eq = (math.pi * D_val) / 4.0
            s_1 = ((w1 + a_eq) * math.sqrt(L_val ** 2 + ((h1 - a_eq) / 2.0) ** 2)) / 1e6
            s_2 = ((h1 + a_eq) * math.sqrt(L_val ** 2 + ((w1 - a_eq) / 2.0) ** 2)) / 1e6
            s_raw = s_1 + s_2
            trace_prefix = "ÔG MB Z3 m2"
        else:
            s_1 = ((w1 + D_val + 28.0) * (L_val + 95.0)) / 1e6
            s_2 = ((max(h1, D_val) + 120.0) * (L_val + 95.0)) / 1e6
            s_raw = (s_1 + s_2) * 1.2
            trace_prefix = "BG PKV"
        s_area = 0.3 if s_raw < 0.3 else s_raw
        price_nep_c = excel_round(s_area * pkths, -2)
        price_tdc = price_nep_c + 8000.0
        unit_price = price_nep_c if flange_type == "NEP_C" else price_tdc
        spec_label = f"Côn thu vuông tròn {int(w1)}x{int(h1)}/Ø{int(D_val)} L={int(L_val)}"
        s_note = f"{s_raw:.3f}->0.300m2 (quy <0.3)" if s_raw < 0.3 else f"{s_area:.3f}m2"
        trace_str = f"{trace_prefix} (Côn thu vuông tròn, tôn {thk}mm, {flange_type}): S={s_note}, pkths={pkths:,.0f}"
        return b1_out, b2_out, l_out, s_area, unit_price, spec_label, trace_str

    @classmethod
    def _calc_rect_elbow(cls, w1, h1, w2, h2, radius, angle, formula_mode, thk, pkvhs, flange_type, ei_rating):
        R_val = radius if radius > 0 else (w1 / 2.0)
        W2_e = w2 if w2 > 0 else w1
        H2_e = h2 if h2 > 0 else h1
        b1_out, b2_out, l_out = int(W2_e), int(H2_e), int(R_val)
        if angle == 60:
            factor = (2.0 * 1.1) / 3.0
            ang_ratio = 60.0 / 90.0
        elif angle == 45:
            factor = 1.1 / 2.0
            ang_ratio = 45.0 / 90.0
        elif angle == 30:
            factor = 1.1 / 3.0
            ang_ratio = 30.0 / 90.0
        else:
            angle = 90
            factor = 1.0
            ang_ratio = 1.0

        if formula_mode == "OG_MB_M2":
            s_90 = (math.pi * (4.0 * R_val + w1 + W2_e) / 8.0 * (w1 + h1 + W2_e + H2_e)) / 1e6
            s_raw = s_90 * ang_ratio
            trace_prefix = "ÔG MB Z3 m2"
        else:
            s_1 = 1.57 * (w1 * w1 + 2.0 * w1 * R_val) / 1e6
            s_2 = 1.57 * (w1 + R_val) * (h1 + 80.0) / 1e6
            s_3 = 1.57 * R_val * (h1 + 80.0) / 1e6
            s_4 = ((w1 + h1) * 2.0 * 100.0) / 1e6
            s_90 = s_1 + s_2 + s_3 + s_4
            s_raw = s_90 * factor
            trace_prefix = "BG PKV"
        s_area = 0.3 if s_raw < 0.3 else s_raw
        price_nep_c = excel_round(s_area * pkvhs, -2)
        price_tdc = price_nep_c + 16000.0
        unit_price = price_nep_c if flange_type == "NEP_C" else price_tdc
        if ei_rating > 0:
            ei_surcharge = {30: 345000.0, 45: 420000.0, 60: 520000.0, 90: 680000.0, 120: 850000.0}.get(ei_rating, 345000.0)
            unit_price = excel_round(s_area * ei_surcharge + unit_price, -2)
        spec_label = f"Cút vuông {angle}° {int(w1)}x{int(h1)} (R={int(R_val)})"
        s_note = f"{s_raw:.3f}->0.300m2 (quy <0.3)" if s_raw < 0.3 else f"{s_area:.3f}m2"
        trace_str = f"{trace_prefix} (Cút vuông {angle}°, tôn {thk}mm, {flange_type}): S={s_note}, pkvhs={pkvhs:,.0f}"
        return b1_out, b2_out, l_out, s_area, unit_price, spec_label, trace_str

    @classmethod
    def _calc_rect_offset_z(cls, w1, h1, w2, h2, length, has_explicit_l, offset_h, formula_mode, thk, pkvhs, flange_type):
        H_off = offset_h if offset_h > 0 else (w2 if (w2 > 0 and w2 != w1) else 200.0)
        L_val = length if (has_explicit_l and length > 0) or length not in (0.0, 200.0, 1110.0) else 600.0
        b1_out, b2_out, l_out = "E", int(H_off), int(L_val)
        if formula_mode == "OG_MB_M2":
            W2_z = w2 if w2 > 0 else w1
            H2_z = h2 if h2 > 0 else h1
            l_eff = (H2_z / 2.0 + 100.0) + math.sqrt((H_off - (H2_z / 2.0 + 100.0)) ** 2 + L_val ** 2)
            s_1 = ((w1 + W2_z) * math.sqrt(l_eff ** 2 + ((h1 - H2_z) / 2.0) ** 2)) / 1e6
            s_2 = ((h1 + H2_z) * math.sqrt(l_eff ** 2 + ((w1 - W2_z) / 2.0) ** 2)) / 1e6
            s_raw = s_1 + s_2
            trace_prefix = "ÔG MB Z3 m2"
        else:
            s_1 = ((w1 + H_off) * L_val * 2.0) / 1e6
            s_2 = (h1 * L_val * 2.0) / 1e6
            s_raw = (s_1 + s_2) * 1.35
            trace_prefix = "BG PKV"
        s_area = 0.3 if s_raw < 0.3 else s_raw
        price_nep_c = excel_round(s_area * pkvhs, -2)
        price_tdc = price_nep_c + 16000.0
        unit_price = price_nep_c if flange_type == "NEP_C" else price_tdc
        spec_label = f"Zét lượn {int(w1)}x{int(h1)} L={int(L_val)} E={int(H_off)}"
        s_note = f"{s_raw:.3f}->0.300m2 (quy <0.3)" if s_raw < 0.3 else f"{s_area:.3f}m2"
        trace_str = f"{trace_prefix} (Zét lượn, tôn {thk}mm, {flange_type}): S={s_note}, pkvhs={pkvhs:,.0f}"
        return b1_out, b2_out, l_out, s_area, unit_price, spec_label, trace_str

    @classmethod
    def _calc_rect_wye(cls, w1, h1, w2, radius, thk, pkvhs, flange_type):
        W2_val = w2 if w2 > 0 else w1
        R_val = radius if radius > 0 else (w1 / 2.0)
        b1_out, b2_out, l_out = int(W2_val), int(h1), int(R_val)
        s_1 = ((w1 + 2.0 * R_val + 45.0) * (W2_val + R_val + 45.0) * 2.0) / 1e6
        s_2 = (((3.14 * R_val + 90.0) / 4.0) * (h1 + 20.0) * 2.0) / 1e6
        s_3 = (((3.14 * (w1 + R_val) + 90.0) / 4.0) * (h1 + 20.0) * 2.0) / 1e6
        s_raw = s_1 + s_2 + s_3
        s_area = 0.3 if s_raw < 0.3 else s_raw
        price_nep_c = excel_round(s_area * pkvhs, -2)
        price_tdc = price_nep_c + 24000.0
        unit_price = price_nep_c if flange_type == "NEP_C" else price_tdc
        spec_label = f"Chạc 3 (Y vuông) {int(w1)}x{int(h1)}/{int(W2_val)}x{int(h1)}"
        s_note = f"{s_raw:.3f}->0.300m2 (quy <0.3)" if s_raw < 0.3 else f"{s_area:.3f}m2"
        trace_str = f"BG PKV (Chạc 3 Y, tôn {thk}mm, {flange_type}): S={s_note}, pkvhs={pkvhs:,.0f}, +24,000 TDC"
        return b1_out, b2_out, l_out, s_area, unit_price, spec_label, trace_str

    @classmethod
    def _calc_rect_tee(cls, w1, h1, w2, h2, thk, pkvhs, flange_type):
        W2_val = w2 if w2 > 0 else w1
        H2_val = h2 if h2 > 0 else h1
        L1_val = w1 + 200.0
        L2_val = 200.0
        b1_out, b2_out, l_out = int(W2_val), int(H2_val), int(L1_val)
        s_1 = (((w1 + h1) * 2.0 + 43.0) * (L1_val + 90.0)) / 1e6
        s_2 = (((W2_val + H2_val) * 2.0 + 43.0) * (L2_val + 45.0)) / 1e6
        s_raw = s_1 + s_2
        s_area = 0.3 if s_raw < 0.3 else s_raw
        price_nep_c = excel_round(s_area * pkvhs, -2)
        price_tdc = price_nep_c + 24000.0
        unit_price = price_nep_c if flange_type == "NEP_C" else price_tdc
        spec_label = f"Tê vuông {int(w1)}x{int(h1)}/{int(W2_val)}x{int(H2_val)}"
        s_note = f"{s_raw:.3f}->0.300m2 (quy <0.3)" if s_raw < 0.3 else f"{s_area:.3f}m2"
        trace_str = f"BG PKV (Tê vuông, tôn {thk}mm, {flange_type}): S={s_note}, pkvhs={pkvhs:,.0f}, +24,000 TDC"
        return b1_out, b2_out, l_out, s_area, unit_price, spec_label, trace_str

    @classmethod
    def _calc_rect_end_cap(cls, w1, h1, length, has_explicit_l, formula_mode, thk, pkvhs, flange_type):
        L_val = length if (has_explicit_l and length > 0) or length not in (0.0, 200.0, 1110.0) else 100.0
        l_out = int(L_val)
        if formula_mode == "OG_MB_M2":
            s_1 = ((w1 + h1) * 2.0 * L_val) / 1e6
            s_2 = (w1 * h1) / 1e6
            s_raw = s_1 + s_2
            trace_prefix = "ÔG MB Z3 m2"
        else:
            s_1 = ((w1 + h1) * 2.0 * (L_val + 83.0)) / 1e6
            s_2 = (w1 * h1) / 1e6
            s_raw = s_1 + s_2
            trace_prefix = "BG PKV"
        s_area = 0.3 if s_raw < 0.3 else s_raw
        price_nep_c = excel_round(s_area * pkvhs, -2)
        price_tdc = price_nep_c + 8000.0
        unit_price = price_nep_c if flange_type == "NEP_C" else price_tdc
        spec_label = f"Bịt đầu ống gió {int(w1)}x{int(h1)}"
        s_note = f"{s_raw:.3f}->0.300m2 (quy <0.3)" if s_raw < 0.3 else f"{s_area:.3f}m2"
        trace_str = f"{trace_prefix} (Bịt đầu, tôn {thk}mm, {flange_type}): S={s_note}, pkvhs={pkvhs:,.0f}"
        return None, None, l_out, s_area, unit_price, spec_label, trace_str

    @classmethod
    def _calc_plenum_box(cls, w1, h1, d1, length, has_explicit_l, neck_count, full_text, thk, is_insulated):
        L_val = length if (has_explicit_l and length > 0) or length not in (0.0, 1110.0) else 300.0
        D_neck = d1 if d1 > 0 else 200.0
        n_necks = neck_count if d1 > 0 or "cổ" in full_text.lower() else 0
        b1_out = "Ø" if n_necks > 0 else None
        b2_out = int(D_neck) if n_necks > 0 else None
        l_out = int(L_val)
        s_body = (((w1 + h1) * 2.0 * (43.0 + L_val)) + (w1 * h1)) / 1e6
        s_neck = (D_neck * 3.14 * 0.07 * n_necks) / 1000.0
        s_raw = s_body + s_neck
        s_area = 0.3 if s_raw < 0.3 else s_raw
        box_rate = cls.PKVHS_RATES.get(thk, 189000.0)
        unit_price = excel_round(box_rate * s_area, -2)
        if is_insulated:
            unit_price = excel_round(unit_price + s_area * 130000.0, -2)
        spec_label = f"Hộp gió {int(w1)}x{int(h1)}xL{int(L_val)}" + (f" ({n_necks} cổ D{int(D_neck)})" if n_necks > 0 else "")
        s_note = f"{s_raw:.3f}->0.300m2 (quy <0.3)" if s_raw < 0.3 else f"{s_area:.3f}m2"
        trace_str = f"BG PKV (Hộp gió, tôn {thk}mm): S={s_note}, pkvhs={box_rate:,.0f}"
        return b1_out, b2_out, l_out, s_area, unit_price, spec_label, trace_str

    @classmethod
    def _calc_rect_duct_or_fitting_item(
        cls, subtype, item, full_text, unit, w1, h1, w2, h2, d1,
        length, has_explicit_l, radius, offset_h, angle,
        explicit_thk, flange_type, neck_count, ei_rating, is_insulated
    ):
        formula_mode = str(item.get("duct_formula_mode") or cls.DUCT_FORMULA_MODE or "MPQ_STD").upper()
        max_dim = max(w1, h1, w2, h2, d1)
        thk = cls.get_standard_thickness(max_dim, is_round=False, explicit_thk=explicit_thk)
        vhs = cls.VHS_RATES.get(thk, 157500.0)
        pkvhs = cls.PKVHS_RATES.get(thk, 189000.0)
        pkths = cls.PKTHS_RATES.get(thk, 238500.0)

        if subtype == "DUCT_RECT":
            b1_out, b2_out, l_out, s_area, unit_price, spec_label, trace_str = cls._calc_rect_duct(
                w1, h1, length, unit, thk, vhs, flange_type, ei_rating
            )
        elif subtype == "REDUCER_SQ":
            b1_out, b2_out, l_out, s_area, unit_price, spec_label, trace_str = cls._calc_rect_reducer(
                w1, h1, w2, h2, length, has_explicit_l, formula_mode, thk, pkvhs, flange_type, ei_rating
            )
        elif subtype == "SHOE_TAP":
            b1_out, b2_out, l_out, s_area, unit_price, spec_label, trace_str = cls._calc_rect_shoe_tap(
                w1, h1, w2, h2, d1, length, has_explicit_l, formula_mode, thk, pkvhs, flange_type, ei_rating
            )
        elif subtype == "SQUARE_TO_ROUND":
            b1_out, b2_out, l_out, s_area, unit_price, spec_label, trace_str = cls._calc_square_to_round(
                w1, h1, w2, d1, length, has_explicit_l, formula_mode, thk, pkths, flange_type
            )
        elif subtype == "ELBOW_SQ":
            b1_out, b2_out, l_out, s_area, unit_price, spec_label, trace_str = cls._calc_rect_elbow(
                w1, h1, w2, h2, radius, angle, formula_mode, thk, pkvhs, flange_type, ei_rating
            )
        elif subtype == "OFFSET_Z":
            b1_out, b2_out, l_out, s_area, unit_price, spec_label, trace_str = cls._calc_rect_offset_z(
                w1, h1, w2, h2, length, has_explicit_l, offset_h, formula_mode, thk, pkvhs, flange_type
            )
        elif subtype == "WYE_SQ":
            b1_out, b2_out, l_out, s_area, unit_price, spec_label, trace_str = cls._calc_rect_wye(
                w1, h1, w2, radius, thk, pkvhs, flange_type
            )
        elif subtype == "TEE_SQ":
            b1_out, b2_out, l_out, s_area, unit_price, spec_label, trace_str = cls._calc_rect_tee(
                w1, h1, w2, h2, thk, pkvhs, flange_type
            )
        elif subtype == "END_CAP_SQ":
            b1_out, b2_out, l_out, s_area, unit_price, spec_label, trace_str = cls._calc_rect_end_cap(
                w1, h1, length, has_explicit_l, formula_mode, thk, pkvhs, flange_type
            )
        else:  # PLENUM_BOX
            b1_out, b2_out, l_out, s_area, unit_price, spec_label, trace_str = cls._calc_plenum_box(
                w1, h1, d1, length, has_explicit_l, neck_count, full_text, thk, is_insulated
            )

        sq_model_map = {
            "DUCT_RECT": "Ống gió vuông",
            "REDUCER_SQ": "Côn vuông",
            "ELBOW_SQ": "Cút vuông",
            "OFFSET_Z": "Zét lượn",
            "SQUARE_TO_ROUND": "Côn thu vuông tròn",
            "SHOE_TAP": "Chân rẽ vuông",
            "WYE_SQ": "Chạc Y vuông",
            "TEE_SQ": "Tê vuông",
            "END_CAP_SQ": "Bịt đầu ống gió",
            "PLENUM_BOX": "Hộp gió",
        }
        model_out = sq_model_map.get(subtype, subtype)
        if any(k in full_text.lower() for k in ("côn trùng", "lcct", "lưới chắn", "insect screen", "i.s")) or bool(re.search(r'\b(?:i\.s\.?|c/w\s*is)\b', full_text.lower())):
            mesh_surcharge = excel_round((w1 / 1000.0) * (h1 / 1000.0) * 150000.0, 0)
            unit_price += mesh_surcharge
            model_out = f"{model_out} + LCCT"
            spec_label = f"{spec_label} kèm lưới chắn côn trùng"
            trace_str = f"{trace_str} + LCCT ({mesh_surcharge:,.0f} đ)"
        return {
            "subtype": subtype,
            "model_std": model_out,
            "thickness": thk,
            "l_mm": l_out,
            "b1": b1_out,
            "b2": b2_out,
            "area_m2": round(s_area, 3),
            "unit_price": unit_price,
            "spec_note": f"{spec_label}, tôn Hoa Sen dày {thk:.2f}mm, kết nối {'nẹp C' if flange_type == 'NEP_C' else 'bích TDC'}" + (f", bọc chống cháy EI{ei_rating}" if ei_rating > 0 else ""),
            "trace": trace_str
        }

    @classmethod
    def calculate_duct_bom(cls, parent_id, w, h, l=1110, brand="HOASEN", flange_type="TDC", is_fitting=False, unit="m2", specified_thickness=None, d=0, subtype=None, item=None):
        """
        Bóc tách BOM cho Ống Gió & Phụ Kiện Ống Gió (Vuông/Tròn) theo đúng công thức chuẩn:
        Tự động quy đổi khối lượng tôn sao cho giá bán trên Sheet 00 khớp tuyệt đối 100% với BẢNG TÍNH GIÁ chuẩn 2026.xls.
        """
        if item is not None:
            calc = cls.calculate_duct_item(item)
        else:
            synth_item = {
                "raw_name": subtype if subtype else ("Hộp gió" if is_fitting else "Ống gió"),
                "w": w, "h": h, "d": d, "l": l,
                "thickness": specified_thickness or 0.0,
                "flange_type": flange_type,
                "unit": unit
            }
            calc = cls.calculate_duct_item(synth_item)

        thk = calc["thickness"] if calc["thickness"] > 0 else 0.58
        target_sell = calc["unit_price"]
        area_m2 = calc["area_m2"] if calc["area_m2"] > 0 else 1.0

        mat_price_map = get_master_price_map()
        mfg_markup = 1.593  # (1 + 0.25 + 0.10) * 1.18 = 1.593
        mat_id = f"MAT-STEEL-HOASEN-{thk:.2f}"
        if mat_id not in mat_price_map:
            mat_id = "MAT-STEEL-HOASEN-0.58"
        p_mat = mat_price_map.get(mat_id, 20865.36)

        weight_kg = target_sell / (p_mat * mfg_markup) if (p_mat * mfg_markup) > 0 else (area_m2 * 7.85 * thk)

        components = [
            {
                "sub_key": f"{parent_id}-BODY",
                "name": calc["spec_note"],
                "category": "TÔN_CUỘN_MẠ_KẼM",
                "mat_id": mat_id,
                "calc_qty": weight_kg,
                "unit": "kg",
                "area_m2": area_m2,
                "note": calc["trace"]
            }
        ]
        return {
            "category": "ONG_GIO",
            "subtype": calc["subtype"],
            "thickness": thk,
            "area_m2": area_m2,
            "weight_kg": weight_kg,
            "target_sell": target_sell,
            "components": components
        }

    @classmethod
    def calculate_canvas_bom(cls, parent_id, w, h, l=200, d=0, raw_name="", unit="cái", item=None, **kwargs):
        """
        Bóc tách Khớp nối mềm Canvas & Chụp thông hơi Inox 304 Ventcap khớp 100% sheet 'BG canvas, ventcap'.
        """
        if item is not None:
            calc = cls.calculate_duct_item(item)
        else:
            item_dict = {
                "raw_name": raw_name or "Khớp nối mềm Canvas",
                "w": w, "h": h, "d": d, "l": l, "unit": unit
            }
            calc = cls.calculate_duct_item(item_dict)
        target_sell = calc["unit_price"]
        mat_price_map = get_master_price_map()
        mfg_markup = 1.593
        mat_id = "CANVAS_FIRE_RESISTANT"
        p_mat = mat_price_map.get(mat_id, 57600.0)
        calc_qty = target_sell / (p_mat * mfg_markup) if (p_mat * mfg_markup) > 0 else 1.0

        components = [
            {
                "sub_key": f"{parent_id}-CANVAS",
                "name": calc["spec_note"],
                "category": "VẬT_TƯ_BẠT",
                "mat_id": mat_id,
                "unit": "m2",
                "calc_qty": calc_qty,
                "note": calc["trace"]
            }
        ]
        return {
            "category": "CANVAS",
            "target_sell": target_sell,
            "components": components
        }

    @classmethod
    def calculate_acoustic_partition_bom(cls, parent_id, w, h, l=1000, unit="Bộ", brand="HOASEN", include_casing=True, d=0, raw_name="", item=None, **kwargs):
        """
        Bóc tách Hộp tiêu âm vuông / Tiêu âm tròn khớp 100% sheet 'BG TIEU AM'.
        """
        if item is not None:
            calc = cls.calculate_duct_item(item)
        else:
            item_dict = {
                "raw_name": raw_name or "Hộp tiêu âm",
                "w": w, "h": h, "d": d, "l": l, "unit": unit
            }
            calc = cls.calculate_duct_item(item_dict)
        target_sell = calc["unit_price"]
        thk = calc["thickness"] if calc["thickness"] > 0 else 0.58
        area_m2 = calc["area_m2"] if calc["area_m2"] > 0 else 1.0

        mat_price_map = get_master_price_map()
        mfg_markup = 1.593

        p_rock = mat_price_map.get("ROCKWOOL_50MM_50KG", 65000.0)
        p_cloth = mat_price_map.get("GLASS_CLOTH", 15000.0)
        p_perf = mat_price_map.get("PERFORATED_SHEET", 55000.0)
        mat_steel_id = f"MAT-STEEL-HOASEN-{thk:.2f}"
        if mat_steel_id not in mat_price_map:
            mat_steel_id = "MAT-STEEL-HOASEN-0.58"
        p_steel = mat_price_map.get(mat_steel_id, 20865.36)

        raw_core_sell = area_m2 * (p_rock + p_cloth + p_perf) * mfg_markup
        raw_shell_kg = area_m2 * 7.85 * thk
        raw_shell_sell = raw_shell_kg * p_steel * mfg_markup
        total_raw_sell = raw_core_sell + raw_shell_sell
        scale = (target_sell / total_raw_sell) if total_raw_sell > 0 else 1.0

        components = [
            {
                "sub_key": f"{parent_id}-BODY",
                "name": f"Vỏ tôn hộp tiêu âm Hoa Sen ({thk:.2f}mm)",
                "category": "TÔN_CUỘN_MẠ_KẼM",
                "mat_id": mat_steel_id,
                "calc_qty": raw_shell_kg * scale,
                "unit": "kg",
                "note": calc["trace"]
            },
            {
                "sub_key": f"{parent_id}-ROCKWOOL",
                "name": "Bông khoáng tiêu âm tỷ trọng 60kg/m3 dày 50mm",
                "category": "VẬT_LIỆU_TIÊU_ÂM",
                "mat_id": "ROCKWOOL_50MM_50KG",
                "calc_qty": area_m2 * scale,
                "unit": "m2",
                "note": f"Diện tích tiêu âm {area_m2:.2f}m2"
            },
            {
                "sub_key": f"{parent_id}-GLASSCLOTH",
                "name": "Vải thủy tinh chống cháy bọc tiêu âm",
                "category": "VẬT_LIỆU_TIÊU_ÂM",
                "mat_id": "GLASS_CLOTH",
                "calc_qty": area_m2 * scale,
                "unit": "m2",
                "note": f"Diện tích tiêu âm {area_m2:.2f}m2"
            },
            {
                "sub_key": f"{parent_id}-PERFORATED",
                "name": "Tôn đục lỗ tiêu âm dày 0.5mm",
                "category": "VẬT_LIỆU_TIÊU_ÂM",
                "mat_id": "PERFORATED_SHEET",
                "calc_qty": area_m2 * scale,
                "unit": "m2",
                "note": "Bọc mặt trong vách tiêu âm"
            }
        ]
        return {
            "category": "TIEU_AM",
            "thickness": thk,
            "area_m2": area_m2,
            "target_sell": target_sell,
            "components": components
        }

    @staticmethod
    def generate_duct_bom(duct_type, w, h, length=1110, thickness=0.0, flange_type="TDC", insulation_type="NONE", raw_name="", unit="cái"):
        item_dict = {
            "raw_name": raw_name or duct_type,
            "w": w, "h": h,
            "d": w if duct_type in ("SPIRAL_DUCT", "ROUND_FITTING") else 0.0,
            "length": length,
            "thickness": thickness,
            "flange_type": flange_type,
            "unit": unit,
            "is_insulated": insulation_type != "NONE"
        }
        calc = Agent04_DuctworkBOM.calculate_duct_item(item_dict)
        return [
            {
                "mat_id": f"SWIND-DUCT-{calc['subtype']}-{calc['thickness']:.2f}".replace(".", "_"),
                "name": calc["spec_note"],
                "qty": round(calc["area_m2"], 3) if calc["area_m2"] > 0 else 1.0,
                "unit": "m2" if calc["area_m2"] > 0 else unit,
                "unit_price": calc["unit_price"],
                "trace": calc["trace"]
            }
        ]


Agent04_DuctBOM = Agent04_DuctworkBOM
