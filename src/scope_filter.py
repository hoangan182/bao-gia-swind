"""
Bộ lọc PHẠM VI BÁO GIÁ (scope_filter) — chạy bảng rule `data/master_data/scope_rules.json`.

Quyết định dòng nào Swind báo / không báo / giữ giá đối tác / hỏi lại User. Tách từ các danh sách từ khóa rải rác trong
`SwindBOQParser.parse_sheet` và `swind_master_runner` (kế hoạch tách agent đọc BOQ, việc C3, 2026-11-03).
Mỗi hàm mang id rule PV-xx; từ khóa / regex nằm trong JSON. Sửa rule: sửa JSON, ghi `nguon` / `ly_do`, thêm `vi_du`,
chạy `tests/test_swind_scope_rules.py`. Vai trò: `.agents/roles/scope_filter_role.md`.
"""
import os
import re
import json

RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "master_data", "scope_rules.json")
_RULES_CACHE = {}


def load_rules(path=None):
    path = path or RULES_PATH
    mtime = os.path.getmtime(path)
    cached = _RULES_CACHE.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    rules = {r["id"].split("_", 1)[0]: r for r in data["quy_tac"]}
    rules["_all"] = data
    _RULES_CACHE[path] = (mtime, rules)
    return rules


def match_keyword(kw, text):
    """Từ khóa 1 chữ so theo ranh giới từ (chống va chạm từ con: 'chống cháy' chứa 'ống'); cụm nhiều chữ so chuỗi con."""
    if kw not in text:
        return False
    if " " in kw:
        return True
    return bool(re.search(r'\b' + re.escape(kw) + r'\b', text))


# ---------------------------------------------------------------- Parser: phân loại ngoài phạm vi

def is_non_swind_system_item(name_lower, full_name_lower, sec_lower, name_str, full_name_str, note_boq, rules=None):
    """PV-01: ống nước / chữa cháy / ống đồng / cáp điện / bộ nguồn van / van nước DN → True (xếp THUONG_MAI)."""
    r = (rules or load_rules())["PV-01"]
    is_cable = bool(re.search(r["regex_cap_dien"], name_lower)) or bool(re.search(r["regex_bo_nguon"], name_lower))
    is_dn_valve = (name_lower.startswith(tuple(r["van_nuoc_bat_dau"])) and bool(re.search(r["regex_van_nuoc_dn"], name_lower))
                   and not any(match_keyword(k, name_lower) for k in r["tu_khoa_van_gio"]))
    is_hvac_prd = is_hvac_pressure_damper(full_name_lower, full_name_str, note_boq, rules)
    hit = is_cable or is_dn_valve or ((not is_hvac_prd) and any(pk in name_lower for pk in r["tu_khoa_ong_nuoc"]))
    if not hit and not is_hvac_prd and any(pk in full_name_lower for pk in r["tu_khoa_ong_nuoc"]):
        # Từ khóa ống nước chỉ nằm ở ngữ cảnh Title / dòng mô tả (không ở Tên dòng): Tên dòng tự ghi loại hàng
        # Swind (van gió / cửa gió / MFD...) thì dòng thắng Title (quy tắc 1a) — User yêu cầu 2026-11-24, dự án
        # AC.OG.CGVG R21-24, R65-68: mô tả 'Khung cánh thép tráng kẽm ... van MFD' kéo MFD / NRD / cửa gió thành THUONG_MAI
        hit = not any(dk in name_lower for dk in r["tru_ten_title_ong_nuoc"])
    if not hit and any(sk in sec_lower for sk in r["title_ong_nuoc"]):
        if not any(dk in name_lower for dk in r["tru_ten_title_ong_nuoc"]):
            hit = True
    if not hit and name_lower.startswith(tuple(r["phu_kien_ong_nuoc_bat_dau"])):
        if re.search(r["regex_phu_kien_ong_nuoc"], name_str, re.IGNORECASE):
            if not any(dk in name_lower for dk in r["tru_phu_kien_ong_nuoc"]):
                hit = True
    if not hit and name_lower.startswith(tuple(r.get("bat_dau_hang_ong_nuoc", ()))):
        # Đồng hồ (áp suất / đo nước), mặt bích, van phao, van xả đáy: đọc nội dung dòng, không phụ thuộc Title cha
        if not any(dk in name_lower for dk in r["tru_phu_kien_ong_nuoc"]):
            hit = True
    return hit


def is_hvac_pressure_damper(full_name_lower, full_name_str, note_boq, rules=None):
    """PV-01: 'van giảm áp / van xả áp' có kích thước AxB hoặc chữ tôn / EI / động cơ... là VAN GIÓ, không phải van nước."""
    r = (rules or load_rules())["PV-01"]
    return any(k in full_name_lower for k in r["van_gio_xa_ap"]) and (
        bool(re.search(r["regex_kt"], f"{full_name_str} {note_boq}"))
        or any(k in f"{full_name_lower} {note_boq.lower()}" for k in r["tu_khoa_van_xa_ap_gio"])
    )


def is_commercial_by_name(name_lower, rules=None):
    """PV-02: Tên (bỏ tiền tố 'lắp đặt / gia công' cho giá đỡ) bắt đầu bằng thiết bị / phụ trợ → THUONG_MAI."""
    r = (rules or load_rules())["PV-02"]
    return bool(re.match(r["regex_gia_do"], name_lower)) or name_lower.startswith(tuple(r["bat_dau"]))


def is_insect_screen_code(name_lower, rules=None):
    """PV-12: mã 'IS' đứng riêng ngay trước kích thước (IS 850x250, AL IS-1000x800) → lưới chắn côn trùng."""
    return bool(re.search((rules or load_rules())["PV-12"]["regex"], name_lower))


def is_louver_code(name_lower, rules=None):
    """PV-14: mã 'AL' đứng đầu Tên ngay trước kích thước (AL 600x300) → Louver nan Z (User chốt 2026-11-03)."""
    return bool(re.search((rules or load_rules())["PV-14"]["regex"], name_lower))


def is_glued_damper_code(name_lower, rules=None):
    """PV-15: mã van viết liền kích thước ở đầu Tên (FD550x350, MFD350x150) → van gió (2026-11-06, 261031 NOXH hầm)."""
    return bool(re.search((rules or load_rules())["PV-15"]["regex"], name_lower))


def is_fan_connection_transition(name_lower, rules=None):
    """PV-16: Tên chỉ '<W>x<H>/Quạt' (chuyển tiết diện nối miệng quạt, thiếu đường kính) → không báo (User chốt 2026-11-17)."""
    return bool(re.search((rules or load_rules())["PV-16"]["regex"], name_lower))


def is_duct_insulation(name_lower, rules=None):
    """PV-17: Tên bắt đầu 'Cách nhiệt / Bảo ôn ống gió ...' → vật tư cách nhiệt, không báo (User chốt 2026-11-20)."""
    return bool(re.search((rules or load_rules())["PV-17"]["regex"], name_lower))


def is_non_swind_omission(row_txt, rules=None):
    """PV-11 (User duyệt 2026-11-03): dòng ống gas / PVC / PPR / uPVC, bảo ôn, URL -> không phải hàng Swind, không cảnh báo SÓT DÒNG.
    LCCT không thuộc danh sách này (mặt hàng có báo giá)."""
    t = str(row_txt or "").lower()
    r = (rules or load_rules())["PV-11"]["khong_phai_hang_swind_sot_dong"]
    return any(k in t for k in r["tu_khoa"]) or any(re.search(rx, t) for rx in r.get("regex", []))


def read_check_confirms(verify_warnings, quoted_sheets, rules=None):
    """PV-13: cảnh báo kiểm chứng đọc BOQ ở sheet có dòng báo giá → dòng HỎI LẠI USER cho Kiểm soát cuối."""
    out = []
    for sh, warns in (verify_warnings or {}).items():
        if sh in quoted_sheets and warns:
            out.append(f"[HỎI LẠI USER] Kiểm chứng đọc BOQ (PV-13) — sheet '{sh}': parser chọn cột/dòng lệch so với đếm thô file gốc, "
                       f"giá có thể sai, xác nhận cột SL / dòng trước khi gửi khách (sửa bằng --override nếu cần): " + " | ".join(warns[:5]))
    return out


def is_auxiliary_material(name_lower, rules=None):
    """PV-03: kẹp bích / ty treo / bu lông → THUONG_MAI (chỉ xét khi chưa phân loại được)."""
    return any(k in name_lower for k in (rules or load_rules())["PV-03"]["tu_khoa"])


def adjust_category_after_dims(category, w, h, d, name_lower, full_name_lower, row_text, unit, is_user_skip, rules=None):
    """
    PV-05..PV-08 sau khi đã có kích thước: trả (category mới, is_missing_dims).
    row_text = Tên gốc + Model + Ghi chú của chính dòng (xét PV-07 chỉ lấy hộp).
    """
    R = rules or load_rules()
    is_missing_dims = False
    no_dim = (w == 0 and h == 0 and d == 0)
    r5 = R["PV-05"]
    # PV-05 mở rộng (User chốt 2026-11-11, KL TB+VT CT3): Cửa / Van THIẾU 1 CẠNH, hoặc hàng chỉ có dạng chữ nhật
    # (Louver...) mà BOQ chỉ ghi đường kính D -> không đủ kích thước: không báo giá, chỉ ghi chú (thay giả định 300)
    nhom_du_kt = tuple(r5.get("nhom_thieu_1_canh", ()))
    one_side = (d == 0 and (w == 0) != (h == 0))
    if one_side:
        # Tên ghi D<n> trùng cạnh đã có (VD Fezix 'BG SWIND' R110 'VCD kích thước: D100', cột W=100, H trống) = hàng TRÒN đủ KT
        side = int(w or h)
        if re.search(rf'(?<![a-z0-9])(?:d|ø|phi\s*){side}(?!\d)', full_name_lower):
            one_side = False
    rect_only_round = (d > 0 and any(k in full_name_lower for k in r5.get("tu_khoa_chi_chu_nhat", ())))
    if is_user_skip:
        category = "THUONG_MAI"
    elif category in r5["nhom"] and (no_dim or (category in nhom_du_kt and (one_side or rect_only_round))):
        is_missing_dims = True
        category = "THUONG_MAI"
    elif category == "CUA_GIO" and d > 0 and any(k in full_name_lower for k in R["PV-06"]["tu_khoa"]):
        category = "THUONG_MAI"
    elif category == "CUA_GIO" and box_only_rx(R).search(row_text):
        category = "ONG_GIO"
    r8 = R["PV-08"]
    if category == "ONG_GIO" and no_dim and (any(k in name_lower for k in r8["tu_khoa"])
                                             or (name_lower.startswith(tuple(r8["bat_dau"])) and str(unit).strip().lower() not in r8["don_vi_m2"])):
        category = "THUONG_MAI"
    return category, is_missing_dims


def box_only_rx(rules=None):
    """PV-07: regex dòng cửa ghi 'chỉ gồm hộp / không gồm cửa gió'."""
    return re.compile((rules or load_rules())["PV-07"]["regex"], re.IGNORECASE)


def non_quotable_categories(include_flex_duct, rules=None):
    r = (rules or load_rules())["PV-04"]
    return tuple(r["nhom_khong_bao_khi_bao_ong_mem"] if include_flex_duct else r["nhom_khong_bao"])


def should_skip_row(category, w, h, d, name_lower, ref_price, include_flex_duct, is_missing_z_offset, rules=None, unit=None):
    """PV-04: dòng không báo (nhóm ngoài phạm vi / ống không kích thước / Zét thiếu E) và BOQ không có đơn giá đối tác → bỏ.
    Ngoại lệ: ống / phụ kiện ống ghi tổng m² (ĐVT m2, không kích thước) KHÔNG bỏ ở parser — Agent 04 tính đơn giá m² theo
    độ dày (duct_rules OG-15 / OG-17); runner vẫn bỏ nhóm ONG_GIO khi không có --include-duct (User chốt 2026-11-13,
    dự án NBT-BG DA luxora-Đầm vạc-Vĩnh Yên: 'Ống gió tôn tráng kẽm dày 0.58mm' m2 bị lọc NO_DIMS dù chạy --include-duct)."""
    R = rules or load_rules()
    r = R["PV-04"]
    is_m2_duct = (category in r.get("nhom_m2_khong_can_kich_thuoc", [])
                  and str(unit or "").strip().lower() in r.get("don_vi_m2", []))
    not_quoted = (is_missing_z_offset or category in non_quotable_categories(include_flex_duct, R)
                  or (w == 0 and h == 0 and d == 0 and category in r["nhom_can_kich_thuoc"] and not is_m2_duct))
    if not not_quoted:
        return False
    has_partner_price = isinstance(ref_price, (int, float)) and ref_price > 0
    keep_anyway = not name_lower.startswith(r["giu_dong_khong_gia_tru_bat_dau"]) and any(k in name_lower for k in r["giu_dong_khong_gia"])
    return not has_partner_price and not keep_anyway


# ---------------------------------------------------------------- Runner: dòng ống kèm sản phẩm Swind (PV-10)

def split_duct_rows_with_swind_products(items, resolve_spec, rules=None):
    """
    Khi KHÔNG báo ống gió: đọc nội dung từng dòng ONG_GIO thay vì bỏ cả dòng (User chốt 2026-11-02).
    - Ống/cút kèm LCCT / lọc G4 → đánh dấu duct_swind_part_only (chỉ báo phần LCCT / lọc).
    - Ống ghi sản phẩm Swind khác / chỉ lấy hộp / Ghi chú phủ định lọc → trả về để HỎI LẠI USER.
    `resolve_spec(item_copy, idx)` = Agent01.resolve_item_spec (nhận diện LCCT / lọc, không lặp từ khóa ở đây).
    """
    R = rules or load_rules()
    r = R["PV-10"]
    other_swind_rx = re.compile(r["regex_san_pham_khac"], re.IGNORECASE)
    neg_rx = re.compile(r["regex_phu_dinh"], re.IGNORECASE)
    box_rx = box_only_rx(R)
    swind_part, ask = [], []
    for idx, it in enumerate(items, 1):
        if it.get("category") != "ONG_GIO":
            continue
        try:
            sp = resolve_spec(dict(it), idx) or {}
        except Exception:
            sp = {}
        if sp.get("has_mesh") or sp.get("has_filter"):
            it["duct_swind_part_only"] = True
            swind_part.append(it)
            if neg_rx.search(str(it.get("note_boq") or "")):
                it["duct_swind_ask_reason"] = f"Ghi chú '{str(it.get('note_boq')).strip()[:60]}' khác Tên — đang báo theo Tên"
                ask.append(it)
        elif box_rx.search(f"{it.get('raw_name') or ''} {it.get('model') or ''} {it.get('note_boq') or ''}"):
            it["duct_swind_ask_reason"] = "BOQ ghi chỉ gồm hộp, không gồm cửa gió -> không báo cửa; hộp gió chỉ báo khi --include-duct"
            ask.append(it)
        elif other_swind_rx.search(f"{it.get('raw_name') or ''} {it.get('note_boq') or ''}"):
            it["duct_swind_ask_reason"] = "có ghi sản phẩm Swind khác (van / OBD / cửa / louver) chưa tách được giá, phần ống không báo"
            ask.append(it)
    return swind_part, ask


# ---------------------------------------------------------------- Coverage Audit (PV-11)

def coverage_lists(rules=None):
    """PV-11: các danh sách từ khóa dùng cho Full-BOQ Coverage Audit (tên biến giữ như runner cũ)."""
    r = (rules or load_rules())["PV-11"]
    return {
        "SWIND_SCOPE_KWS": tuple(r["tu_khoa_pham_vi"]),
        "SWIND_SCOPE_CUA_VAN_KWS": tuple(r["tu_khoa_pham_vi_chi_cua_van"]),
        "SWIND_NON_SCOPE_KWS": tuple(r["tu_khoa_ngoai_pham_vi"]),
        "SWIND_NON_SCOPE_PREFIXES": tuple(r["tien_to_ngoai_pham_vi"]),
        "LUMP_SUM_UNITS": tuple(r["dvt_tron_goi"]),
        "DUCT_NAME_PREFIXES": tuple(r["tien_to_ong_gio"]),
        "CANVAS_NAME_PREFIXES": tuple(r["tien_to_canvas"]),
        "VERB_RX": r["regex_dong_tu_dau_dong"],
    }


# ---------------------------------------------------------------- Helper tên (chuyển từ runner, Việc 4, 2026-11-25)
# Dữ liệu (tiền tố, regex động từ, từ khóa LCCT) nằm ở PV-11 trong scope_rules.json.

def main_noun(name, rules=None):
    """Bỏ các động từ đầu dòng ("Cung cấp và lắp đặt", "Gia công, lắp đặt", "SX & LĐ"...) để lấy danh từ chính."""
    verb = coverage_lists(rules)["VERB_RX"]
    n = re.sub(r'^\s*[-•*+]+\s*', '', str(name or "").lower().strip())
    return re.sub(rf'^(?:{verb}(?:\s*(?:,|và|&|\+|/)\s*{verb})*)\s*:?\s*', '', n)


def is_canvas_like_name(name, rules=None):
    prefixes = coverage_lists(rules)["CANVAS_NAME_PREFIXES"]
    return any(main_noun(name, rules).startswith(p) for p in prefixes)


def is_duct_like_name(name, rules=None):
    prefixes = coverage_lists(rules)["DUCT_NAME_PREFIXES"]
    return any(main_noun(name, rules).startswith(p) for p in prefixes)


def is_swind_product_name(name, scope_kws, rules=None):
    noun = main_noun(name, rules)
    if any(noun.startswith(p) for p in coverage_lists(rules)["SWIND_NON_SCOPE_PREFIXES"]):
        return False
    return any(k in noun for k in scope_kws)


def is_lcct_m2_title(name_lower, rules=None):
    """Title 'LCCT ... kích thước:' (ĐVT m2 có KL) báo LCCT theo m² — từ khóa PV-11 `tu_khoa_lcct_theo_m2.tu_khoa`
    (chuỗi con trên Tên chữ thường; có 'insect screen'). Parser gọi (Task A, 2026-11-25)."""
    r = (rules or load_rules())["PV-11"]
    return any(k in name_lower for k in r["tu_khoa_lcct_theo_m2"]["tu_khoa"])


def is_insect_screen_name(name, rules=None):
    """Tên có chữ LCCT / lưới chắn côn trùng (từ khóa ở PV-11 `tu_khoa_luoi_chan_con_trung`)."""
    r = (rules or load_rules())["PV-11"]
    return any(k in name for k in r["tu_khoa_luoi_chan_con_trung"])


# ---------------------------------------------------------------- Runner: danh sách theo cờ (Task B, dọn sạch sau Việc 4, 2026-11-25)

def audit_scope_keywords(only_cua_van, include_duct, include_canvas, rules=None):
    """PV-11: từ khóa phạm vi của Coverage Audit theo cờ chạy — bỏ `tu_khoa_pham_vi_theo_co.include_duct` khi không
    --include-duct, `include_canvas` khi không --include-canvas (giữ thứ tự danh sách gốc)."""
    R = rules or load_rules()
    cov = coverage_lists(R)
    kws = cov["SWIND_SCOPE_CUA_VAN_KWS"] if only_cua_van else cov["SWIND_SCOPE_KWS"]
    by_flag = R["PV-11"]["tu_khoa_pham_vi_theo_co"]
    if not include_duct:
        kws = tuple(k for k in kws if k not in by_flag["include_duct"])
    if not include_canvas:
        kws = tuple(k for k in kws if k not in by_flag["include_canvas"])
    return kws


def is_main_cv_name(name_lower, rules=None):
    """PV-11 `tu_khoa_hang_chinh_kem_lcct`: Tên có Louver / cửa / van là hàng chính (LCCT chỉ đi kèm) — dòng thiếu KT
    vẫn THÔNG BÁO USER, không bỏ lặng lẽ như LCCT đứng riêng (User chốt 2026-11-11)."""
    return any(k in name_lower for k in (rules or load_rules())["PV-11"]["tu_khoa_hang_chinh_kem_lcct"]["tu_khoa"])


def is_cua_van_only_excluded(row_txt_lower, rules=None):
    """PV-11 `tu_khoa_loai_tru_chi_cua_van`: chế độ --only-cua-van, dòng ống chờ / ống lồng / khớp nối mềm / sleeve /
    flexible không cảnh báo SÓT DÒNG."""
    return any(k in row_txt_lower for k in (rules or load_rules())["PV-11"]["tu_khoa_loai_tru_chi_cua_van"]["tu_khoa"])


def is_straight_fire_duct_row(name_lower, sub_title_lower, rules=None):
    """PV-18 (cờ --duct-straight-only): dòng là ống gió thẳng? Ngữ cảnh = Tên nếu Tên bắt đầu `tien_to_ong` hoặc có từ
    khóa phụ kiện, ngược lại = Title con; giữ khi ngữ cảnh bắt đầu `tien_to_ong` và không có từ khóa phụ kiện."""
    r = (rules or load_rules())["PV-18"]
    pre, fit = r["tien_to_ong"], r["tu_khoa_phu_kien"]
    ctx = name_lower if (name_lower.startswith(pre) or any(k in name_lower for k in fit)) else sub_title_lower
    return ctx.startswith(pre) and not any(k in ctx for k in fit)
