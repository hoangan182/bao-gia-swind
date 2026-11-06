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
    hit = is_cable or is_dn_valve or ((not is_hvac_prd) and any(pk in name_lower or pk in full_name_lower for pk in r["tu_khoa_ong_nuoc"]))
    if not hit and any(sk in sec_lower for sk in r["title_ong_nuoc"]):
        if not any(dk in name_lower for dk in r["tru_ten_title_ong_nuoc"]):
            hit = True
    if not hit and name_lower.startswith(tuple(r["phu_kien_ong_nuoc_bat_dau"])):
        if re.search(r["regex_phu_kien_ong_nuoc"], name_str, re.IGNORECASE):
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
    if is_user_skip:
        category = "THUONG_MAI"
    elif category in R["PV-05"]["nhom"] and no_dim:
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


def should_skip_row(category, w, h, d, name_lower, ref_price, include_flex_duct, is_missing_z_offset, rules=None):
    """PV-04: dòng không báo (nhóm ngoài phạm vi / ống không kích thước / Zét thiếu E) và BOQ không có đơn giá đối tác → bỏ."""
    R = rules or load_rules()
    r = R["PV-04"]
    not_quoted = (is_missing_z_offset or category in non_quotable_categories(include_flex_duct, R)
                  or (w == 0 and h == 0 and d == 0 and category in r["nhom_can_kich_thuoc"]))
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
