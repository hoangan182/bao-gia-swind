"""
Bộ nhận diện VAN GIÓ (damper_classifier) — chạy bảng rule `data/master_data/damper_rules.json`.

Tách từ chuỗi if/elif cũ trong `Agent01._resolve_damper_spec` và `_detect_damper_type` trong
`SwindBOQParser.parse_sheet` (kế hoạch tách agent đọc BOQ, việc C, 2026-11-03).
Module chỉ PHÂN LOẠI: loại van → EI → hãng động cơ / mã MFD → mô-men → Model + ghi chú báo giá.
Phần tính BOM / tỷ lệ giá đơn cánh – đa cánh và ghép combo Van + Van vẫn ở Agent 01 (ghép giá, không phải phân loại).

Mỗi bước mang id rule VG-xx; từ khóa / ngưỡng / mẫu chữ nằm trong JSON. Sửa rule: sửa JSON, ghi `nguon` / `ly_do`,
thêm `vi_du_dung` / `vi_du_sai` rồi chạy `tests/test_swind_damper_rules.py`. Vai trò: `.agents/roles/damper_classifier_role.md`.
"""
import os
import re
import json

RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "master_data", "damper_rules.json")
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


def _any(words, text):
    return any(k in text for k in words)


# ---------------------------------------------------------------- Loại van

def _type_from_model_col(R, model_item, raw_low):
    """VG-01: cột Model ghi mã / loại van → trả loại, None nếu không chốt được."""
    for opt in R["VG-01"]["thu_tu"]:
        hit = (model_item in opt.get("bang", ()) or _any(opt.get("chua", ()), model_item)
               or _any(opt.get("raw_search_chua", ()), raw_low))
        if hit:
            return model_item if opt["loai"] == "@chinh_no" else opt["loai"]
    return None


def _raw_name_has_words(R, item):
    r2 = R["VG-02"]
    raw_nm = str(item.get("raw_name") or "")
    return bool(re.search(r2["regex_ten_co_chu"], re.sub(r2["regex_bo_don_vi_ten"], '', raw_nm, flags=re.IGNORECASE)))


def _effective_name(R, item):
    return str(item.get("raw_name") or "") if _raw_name_has_words(R, item) else str(item.get("name", ""))


def _type_from_own_row(R, item, subtype_rules):
    """VG-02A: Tên chỉ ghi kích thước → loại van do Ghi chú / cột Model của chính dòng ghi (bỏ cụm vật liệu chống cháy)."""
    own = (str(item.get("note_boq") or "") + " " + str(item.get("model") or "")).lower()
    own = re.sub(R["VG-02"]["regex_bo_vat_lieu_chong_chay"], ' ', own).strip()
    if not own:
        return None
    diff_rx = (subtype_rules.get("COMBO_AND_DETECTION_RULES") or {}).get("combo_diffuser_regex", r'(?!x)x')
    found = detect_dampers(own, "", None, diff_rx, R)
    return sort_by_priority(found, R)[0] if found else None


def classify_type(item, subtype_rules, raw_search, full_search, rules=None):
    """VG-01..VG-05 (kể cả VG-02A): trả (loại van, mã Swind ghi ở cột Model hoặc None, danh sách id rule đã kích hoạt)."""
    from agent_01_boq_extractor import Agent01_BOQExtractor as A01
    R = rules or load_rules()
    trail = []
    raw_low = raw_search.lower()
    full_low = full_search.lower()
    model_item = str(item.get("model") or "").strip().upper()
    model_code = next((mc for mc in R["VG-01"]["ma_model"] if mc in model_item), None)
    note_mode = item.get("spec_priority") == "note"

    damper_type = _type_from_model_col(R, model_item, raw_low)
    if damper_type:
        trail.append("VG-01")
    else:
        name_model = (_effective_name(R, item) + " " + str(item.get("model", ""))).lower()
        note_only = str(item.get("note_boq") or "").lower()
        own_type = None if (note_mode or _raw_name_has_words(R, item)) else _type_from_own_row(R, item, subtype_rules)
        if own_type:
            # Loại van do chính dòng ghi thắng Title; động cơ / xả áp ở Title vẫn kế thừa qua VG-03 / VG-04 (AGENTS.md 1a)
            damper_type = own_type
            trail.append("VG-02A")
        else:
            r2 = R["VG-02"]
            texts = {
                "ten_model": name_model, "raw_search": raw_search, "full_search": full_search,
                "ghi_chu_bo_vat_lieu": re.sub(r2["regex_bo_vat_lieu_chong_chay"], ' ', note_only),
            }
            order = r2["thu_tu_nguon_che_do_note"] if (note_mode and note_only) else r2["thu_tu_nguon"]
            damper_type = r2["mac_dinh"]
            for src in reversed(order):  # giữ đúng thứ tự lồng get_subtype(a, get_subtype(b, get_subtype(c, mặc định)))
                damper_type = A01.get_subtype(subtype_rules, "VAN_GIO", texts[src], damper_type)
            trail.append("VG-02")

        r3 = R["VG-03"]
        mprd_src = (note_only + " " + raw_low + " " + full_low) if note_mode else name_model
        if damper_type in r3["ap_cho"] and _any(r3["tu_khoa_xa_ap"], mprd_src) and _any(r3["tu_khoa_dieu_khien"], mprd_src):
            damper_type = "MPRD"
            trail.append("VG-03")

        r4 = R["VG-04"]
        if damper_type in r4["ap_cho"]:
            rs_low = (note_only + " " + raw_low) if note_mode else (name_model + " " + raw_low)
            fd_note_without_motor = note_mode and damper_type == "FD" and not _any(r4["tu_khoa_dong_co"], note_only)
            if not fd_note_without_motor and _any(r4["tu_khoa_chong_chay"], rs_low) and _any(r4["tu_khoa_dong_co"], rs_low):
                damper_type = "MFD"
                trail.append("VG-04")

    if damper_type == "PRD" and _any(R["VG-05"]["tu_khoa"], raw_low):
        damper_type = "MPRD"
        trail.append("VG-05")
    return damper_type, model_code, trail


# ---------------------------------------------------------------- Phân loại đầy đủ

def classify(item, subtype_rules, raw_search, full_search, w, h, d, ei_rating, a1, a2, rules=None):
    """
    Phân loại 1 dòng VAN_GIO (VG-01..VG-10). Ghi lại vào `item` như code cũ (ei_rating chế độ note, fd_non_ei_keyword, w/h/d van FD tròn).
    Trả dict: damper_type, eff_type, eff_model_code, motor_brand, is_klb_req, is_honeywell_req, is_fd_ei, ei_rating,
    w/h/d, w_use/h_use, a1/a2, trail (id rule đã kích hoạt).
    """
    R = rules or load_rules()
    damper_type, model_code, trail = classify_type(item, subtype_rules, raw_search, full_search, R)
    eff_type = "MFD" if damper_type == "MFD_LOUVER" else damper_type
    w_use = w if w > 0 else (d if d > 0 else 300.0)
    h_use = h if h > 0 else (d if d > 0 else 300.0)
    req_motor = str(item.get("motor_brand_override") or "").strip().upper()
    req_mfd_model = str(item.get("mfd_model_override") or "").strip()
    eff_req_code = model_code or (req_mfd_model if eff_type in ("MFD", "MFSD") else "")

    # VG-06: --spec-priority note → EI theo Ghi chú
    note_prio_low = str(item.get("note_boq") or "").lower() if item.get("spec_priority") == "note" else ""
    if note_prio_low:
        r6 = R["VG-06"]
        m_ei = re.search(r6["regex_ei"], note_prio_low)
        if m_ei:
            ei_rating = int(m_ei.group(1))
            item["ei_rating"] = ei_rating
            trail.append("VG-06")
        elif eff_type in r6["ap_cho_boc"] and ei_rating == 0 and _any(r6["tu_khoa_boc"], note_prio_low):
            ei_rating = r6["ei_khi_boc"]
            item["ei_rating"] = ei_rating
            trail.append("VG-06")

    # VG-07: hãng động cơ chỉ theo cờ User / mã Swind ở cột Model
    ma_hang = R["VG-07"]["ma_hang"]
    is_klb_req = (req_motor == "KLB") or (ma_hang.get(eff_req_code) == "KLB")
    is_honeywell_req = (req_motor == "HONEYWELL") or (ma_hang.get(eff_req_code) == "HONEYWELL")
    motor_brand = "KLB" if is_klb_req else ("HONEYWELL" if is_honeywell_req else "BELIMO")

    # VG-08: MD giữ EI BOQ ghi → bọc KSH (User chốt 2026-11-03; trước đây MD luôn EI = 0)

    # VG-09: FD mặc định EI120 có bọc; FD thường chỉ khi BOQ ghi rõ (→ hỏi lại User ở Kiểm soát cuối)
    fd_txt_low = (raw_search + " " + full_search + " " + str(item.get("note_boq") or "")).lower()
    fd_non_ei_kw = next((k for k in R["VG-09"]["tu_khoa_fd_thuong"] if k in fd_txt_low), None) if eff_type == "FD" else None
    is_fd_explicit_non_ei = bool(fd_non_ei_kw) and ei_rating == 0 and eff_req_code != "2.01"
    if eff_type == "FD":
        item["fd_non_ei_keyword"] = fd_non_ei_kw if is_fd_explicit_non_ei else None
        trail.append("VG-09")
    is_fd_ei = (eff_type == "FD") and not is_fd_explicit_non_ei
    if is_fd_ei and d > 0:
        w = h = d
        d = 0.0
        w_use, h_use = w, h
        item["w"], item["h"], item["d"] = w, h, 0.0
        a1, a2 = int(w), int(h)

    # VG-10: mã MFD
    r10 = R["VG-10"]
    belimo_mfd_def = r10["mac_dinh_belimo"]
    if note_prio_low and eff_type in ("MFD", "MFSD") and motor_brand == "BELIMO":
        if _any(r10["tu_khoa_1_05"], note_prio_low):
            belimo_mfd_def = "1.05"
        elif ei_rating >= r10["ei_1_01_tu"] or _any(r10["tu_khoa_1_01"], note_prio_low):
            belimo_mfd_def = "1.01"
    if eff_type == "FD":
        eff_model_code = eff_req_code or ("2.01" if is_fd_ei else "FD")
    else:
        eff_model_code = eff_req_code or ("1.03" if is_klb_req else ("1.04" if is_honeywell_req else belimo_mfd_def))
    if eff_type in ("MFD", "MFSD"):
        trail.append("VG-10")

    return {
        "damper_type": damper_type, "eff_type": eff_type, "eff_model_code": eff_model_code,
        "motor_brand": motor_brand, "is_klb_req": is_klb_req, "is_honeywell_req": is_honeywell_req,
        "is_fd_ei": is_fd_ei, "ei_rating": ei_rating,
        "w": w, "h": h, "d": d, "w_use": w_use, "h_use": h_use, "a1": a1, "a2": a2,
        "trail": trail,
        # Cờ dự án --md-shaft-only (User yêu cầu 2026-11-03, dự án 150-YCVT LUXQV): van MD báo trục chờ, không gồm động cơ
        "md_shaft_only": bool(item.get("md_shaft_only")),
    }


# ---------------------------------------------------------------- Mô-men + Model / ghi chú

def actuator_torque(brand, w_mod, h_mod, rules=None):
    """VG-11: trả (mô-men, model Honeywell hoặc None) theo kích thước 1 modul."""
    r11 = (rules or load_rules())["VG-11"]
    s_mod = (w_mod * h_mod) / 1_000_000.0
    if brand == "BELIMO":
        b = r11["belimo"]
        if max(w_mod, h_mod) < b["canh_lon_mm"]:
            return b["nho"], None
        return next(x["nm"] for x in b["bac_dien_tich"] if "s_max" not in x or s_mod <= x["s_max"]), None
    row = next(x for x in r11["theo_dien_tich"] if "s_max" not in x or s_mod <= x["s_max"])
    return row["nm"], row.get("model_honeywell")


def build_model_note(res, mod_cnt, is_clamped, w_mod, h_mod, is_single_blade, rules=None):
    """VG-11 + VG-12: trả (model_fslf, model_bfn, note_fslf, note_bfn) cho phương án đơn cánh (FSLF) / đa cánh (BFN)."""
    R = rules or load_rules()
    t = R["VG-12"]
    bien = t["bien"]
    eff_type, damper_type, code = res["eff_type"], res["damper_type"], res["eff_model_code"]
    motor_brand = res["motor_brand"]
    is_louver = damper_type == "MFD_LOUVER"
    multi = mod_cnt > 1
    v = {
        "mod_cnt": mod_cnt,
        "mod_txt": bien["mod_txt"].format(mod_cnt=mod_cnt) if multi else "",
        "mod_hw_txt": bien["mod_hw_txt"].format(mod_cnt=mod_cnt) if multi else "",
        "clamp_txt": bien["clamp_txt"] if is_clamped else "",
        "lv_txt": bien["lv_txt"] if is_louver else "",
        "mod_dmp_txt": bien["mod_dmp_txt"].format(mod_cnt=mod_cnt) if multi else "",
        "canh": bien["canh_1"] if is_single_blade else bien["canh_nhieu"],
    }

    if eff_type in ("MFD", "MFSD"):
        tpl = t["mfd"].get(code) or t["mfd"]["*"]
        model_fslf = t["model_mfd_louver"] if (is_louver and tpl.get("louver_doi_model", True)) else tpl["model"]
        note_fslf = tpl["ghi_chu"].format(**v)
        bfn = t["mfd"]["_phuong_an_da_canh"]
        model_bfn = t["model_mfd_louver"] if is_louver else bfn["model"]
        note_bfn = bfn["ghi_chu"].format(**v)
        return model_fslf, model_bfn, note_fslf, note_bfn
    if eff_type == "FD":
        tpl = t["fd_ei"] if res["is_fd_ei"] else t["fd_thuong"]
        note = tpl["ghi_chu"].format(**v)
        return tpl["model"], tpl["model"], note, note
    if eff_type == "MD":
        tm = t["md"]
        if res.get("md_shaft_only"):
            note = (tm["truc_cho_nhieu_modul"] if multi else tm["truc_cho_1_modul"]).format(**v)
        elif res["is_klb_req"]:
            note = (tm["KLB_nhieu_modul"] if multi else tm["KLB_1_modul"]).format(**v)
        elif res["is_honeywell_req"] or motor_brand == "HONEYWELL":
            nm, model_hw = actuator_torque("HONEYWELL", w_mod, h_mod, R)
            note = tm["HONEYWELL"].format(nm=nm, model_hw=model_hw, **v)
        else:
            nm, _ = actuator_torque("BELIMO", w_mod, h_mod, R)
            note = tm["BELIMO"].format(nm=nm, **v)
        if res["ei_rating"] > 0:
            note += tm["hau_to_co_ei"]
        return tm["model"], tm["model"], note, note
    if eff_type == "MPRD":
        tm = t["mprd"]
        nm, _ = actuator_torque(motor_brand, w_mod, h_mod, R)
        if motor_brand == "BELIMO":
            act_txt = tm["dong_co_belimo"].format(nm=nm)
        else:
            act_txt = tm["dong_co_khac"].format(hang=tm["ten_hang"].get(motor_brand, motor_brand), nm=nm)
        note = (tm["co_ei"] if res["ei_rating"] > 0 else tm["khong_ei"]).format(act_txt=act_txt)
        return tm["model"], tm["model"], note, note
    tpl = t["don_gian"].get(eff_type) or t["don_gian"]["*"]
    note = tpl["co_ei"] if res["ei_rating"] > 0 else tpl["khong_ei"]
    return tpl["model"], tpl["model"], note, note


# ---------------------------------------------------------------- Parser: tách van trong combo (VG-13)

def fix_typos(text, rules=None):
    for pat, rep in (rules or load_rules())["VG-13"]["sua_go_nham"]:
        text = re.sub(pat, rep, text)
    return text


def detect_damper_type(tok_str, diff_rx, rules=None):
    """Nhận diện loại van trong 1 cụm chữ (đã tách theo '+ / kèm / gắn ...'); cụm là cửa gió thì chỉ xét phần 'van ...'."""
    r13 = (rules or load_rules())["VG-13"]
    t = fix_typos(tok_str.strip().lower(), rules)
    if re.search(diff_rx, t) and not re.search(r13["regex_ma_van"], t):
        m_v = re.search(r13["regex_phan_van"], t)
        if not m_v:
            return None
        t = m_v.group(0)
    for dtype, pat in r13["nhan_dien"]:
        if re.search(pat, t):
            return dtype
    return None


def detect_dampers(scan_base, model_str, m_damper_text, diff_rx, rules=None):
    """Danh sách loại van trong dòng (theo thứ tự xuất hiện). Cột Mã SP/Model chỉ bổ sung khi Tên chưa ghi van nào."""
    R = rules or load_rules()
    split_rx = R["VG-13"]["regex_tach"]
    found = []
    for src in (scan_base, model_str):
        if found or not src:
            continue
        for tk in re.split(split_rx, src, flags=re.IGNORECASE):
            dt = detect_damper_type(tk, diff_rx, R) if tk.strip() else None
            if dt and dt not in found:
                found.append(dt)
    if not found and m_damper_text is not None:
        dt = detect_damper_type(m_damper_text, diff_rx, R)
        if dt:
            found.append(dt)
    return found


def sort_by_priority(dampers, rules=None):
    order = (rules or load_rules())["VG-13"]["thu_bac"]
    return sorted(dampers, key=lambda x: order.index(x) if x in order else 99)
