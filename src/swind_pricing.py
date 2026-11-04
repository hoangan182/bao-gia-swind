"""
SWIND PRICING — hàm tính giá dùng chung cho Agent 04 / 05 / 06, runner và Agent 10.

Mỗi quy tắc tính giá chỉ nằm ở MỘT chỗ (đợt gom giá 2026-11-03, User duyệt;
spec: docs/superpowers/specs/2026-11-03-swind-pricing-consolidation-design.md).
- Số liệu (đơn giá/m², hằng số OBD...) nằm trong data/master_data/pricing_constants.json (đọc qua swind_utils.K).
- Rule mô-men động cơ nằm trong data/master_data/damper_rules.json (VG-11, đọc qua damper_classifier.actuator_torque).
- Khi 2 nơi từng cho kết quả khác nhau: giá trị trong Master Data JSON thắng.
Module chỉ phụ thuộc swind_utils và damper_classifier; không import agent nào.
"""
import math

from swind_utils import get_master_bom_rules, get_master_price_map

DEFAULT_MFG_MARKUP = 1.593  # (1 + 0.25 + 0.10) * 1.18

# Giá vật tư dự phòng khi Master Data thiếu mã (trước đây viết rải trong agent_05 / agent_06)
_FALLBACK_MAT_PRICES = {
    "MAT-ALU-EGGCRATE-CORE": 750000.0,
    "MAT-ALU-KHUNG-BD": 126000.0,
    "MAT-ALU-KHUNG-OBD": 133000.0,
    "MAT-ALU-KHUNG-Z-2-LOP": 126000.0,
    "MAT-ALU-NAN-Z-DAY": 126000.0,
    "MAT-DOOR-ACCESSORY": 15000.0,
    "MAT-FILTER-G4": 220000.0,
    "MAT-FIREBOARD-10MM-BODY": 518500.0,
    "MAT-MESH-INOX-304": 150000.0,
    "MAT-PAINT-POWDER": 75000.0,
}


def excel_round(value, ndigits=0):
    """ROUND của Excel (làm tròn 0.5 ra xa số 0), có bù sai số dấu phẩy động (+1e-9) — bản của Agent 04.
    Trả int khi ndigits <= 0, float khi ndigits > 0."""
    if not value:
        return 0 if ndigits <= 0 else 0.0
    factor = 10.0 ** ndigits
    scaled = value * factor
    rounded = math.floor(scaled + 0.5 + 1e-9) if scaled >= 0 else math.ceil(scaled - 0.5 - 1e-9)
    result = rounded / factor
    return int(round(result)) if ndigits <= 0 else float(result)


def mfg_markup(group):
    """Hệ số giá bán / giá vốn xưởng của nhóm rule ('damper_rules' / 'diffuser_rules' / 'ductwork_rules')."""
    node = get_master_bom_rules().get(group) or {}
    return float(node.get("mfg_markup_factor", DEFAULT_MFG_MARKUP)) if isinstance(node, dict) else DEFAULT_MFG_MARKUP


def mat_price(mat_id):
    """Đơn giá vật tư từ Master Data; thiếu mã -> bảng dự phòng; không có -> 0."""
    price_map = get_master_price_map()
    if mat_id in price_map:
        return price_map[mat_id]
    return _FALLBACK_MAT_PRICES.get(mat_id, 0.0)


# ---------------------------------------------------------------- Động cơ van (MD / MPRD / MFD)
# Bảng mã động cơ theo hãng — nguồn duy nhất cho cờ --motor-price / --mprd-motor-price của runner
ACTUATOR_IDS = {
    "BELIMO": frozenset({
        "MAT-ACTUATOR-BELIMO-FSLF24", "MAT-ACTUATOR-BELIMO-BFN24",
        "MAT-ACTUATOR-BELIMO-5NM", "MAT-ACTUATOR-BELIMO-10NM", "MAT-ACTUATOR-BELIMO-20NM",
        "MAT-ACTUATOR-BELIMO-MPRD-5NM", "MAT-ACTUATOR-BELIMO-MPRD", "MAT-ACTUATOR-BELIMO-MPRD-20NM",
    }),
    "KLB": frozenset({"MAT-ACTUATOR-KLB-V6006FS500S", "MAT-ACTUATOR-SWIND-VIWECO"}),
    "HONEYWELL": frozenset({
        "MAT-ACTUATOR-HONEYWELL", "MAT-ACTUATOR-HONEYWELL-5NM", "MAT-ACTUATOR-HONEYWELL-10NM", "MAT-ACTUATOR-HONEYWELL-20NM",
    }),
    "MPRD": frozenset({"MAT-ACTUATOR-BELIMO-MPRD-5NM", "MAT-ACTUATOR-BELIMO-MPRD", "MAT-ACTUATOR-BELIMO-MPRD-20NM"}),
}
_MPRD_IDS = {"5Nm": "MAT-ACTUATOR-BELIMO-MPRD-5NM", "10Nm": "MAT-ACTUATOR-BELIMO-MPRD", "20Nm": "MAT-ACTUATOR-BELIMO-MPRD-20NM"}


def select_actuator(kind, brand, w_mod, h_mod, *, is_single_blade=False, mfd_model=None, mfd_mode=None):
    """Chọn động cơ van -> (mat_id, tên hiển thị, mô-men '5Nm'/'10Nm'/'20Nm' hoặc None với MFD).
    kind: 'MD' | 'MPRD' | 'MFD'. Mô-men MD/MPRD theo damper_rules.json VG-11 (damper_classifier.actuator_torque).
    Thứ tự giữ như agent_05 cũ: hãng KLB / Honeywell xét TRƯỚC MPRD (MPRD + KLB -> VIWECO)."""
    brand = str(brand or "BELIMO").strip().upper()
    if kind == "MFD":
        if mfd_model == "1.03" or brand == "KLB":
            return "MAT-ACTUATOR-KLB-V6006FS500S", "Động cơ chặn lửa ON/OFF KLB (Swin V6006FS500S EI90) 5Nm", None
        if mfd_model == "1.04" or brand == "HONEYWELL":
            return "MAT-ACTUATOR-HONEYWELL", "Động cơ chặn lửa ON/OFF 9Nm, 230V (HONEYWELL MS4609F1010/B)", None
        if mfd_model == "1.01":
            return "MAT-ACTUATOR-BELIMO-BFN24", "Động cơ chặn lửa ON/OFF 9Nm, 230V/24V (BELIMO BFN24 / BFN230)", None
        if is_single_blade or mfd_model == "1.02" or mfd_mode == "single_fslf24":
            return "MAT-ACTUATOR-BELIMO-FSLF24", "Động cơ chặn lửa ON/OFF 3.5Nm, 230V/24V (BELIMO FSLF24 / FSLF230)", None
        return "MAT-ACTUATOR-BELIMO-BFN24", "Động cơ chặn lửa ON/OFF 9Nm, 230V/24V (BELIMO BFN24 / BFN230)", None
    if kind not in ("MD", "MPRD"):
        raise ValueError(f"select_actuator: kind không hợp lệ '{kind}'")
    import damper_classifier  # import trong hàm: damper_classifier -> swind_pricing (ghi chú) tránh vòng import
    if brand == "KLB":
        # Bảng giá chỉ có 1 mã KLB cho van MD/MPRD (VIWECO 10Nm)
        return "MAT-ACTUATOR-SWIND-VIWECO", "Động cơ van gió KLB/VIWECO 24V - 10Nm ON/OFF", "10Nm"
    if brand == "HONEYWELL":
        nm, model_hw = damper_classifier.actuator_torque("HONEYWELL", w_mod, h_mod)
        return f"MAT-ACTUATOR-HONEYWELL-{nm.upper()}", f"Động cơ van gió HoneyWell ON/OFF {nm} (Model: {model_hw})", nm
    nm, _ = damper_classifier.actuator_torque("BELIMO", w_mod, h_mod)
    if kind == "MPRD":
        return _MPRD_IDS[nm], f"Động cơ tuyến tính 230V Belimo On/Off {nm}", nm
    return f"MAT-ACTUATOR-BELIMO-{nm.upper()}", f"Động cơ van gió Belimo ON/OFF {nm}", nm


# ---------------------------------------------------------------- Van OBD nhôm (rời — Agent 05, gắn cửa — Agent 06)
def calc_obd(w_mm, h_mm, mult=1.0, markup_group="diffuser_rules"):
    """Giá bán & định mức van OBD nhôm sơn tĩnh điện -> {target_sell, frame_kg, blade_kg, acc_bo}.
    Hằng số: pricing_constants.json -> obd. mult: hệ số riêng của cửa (VD SLB 2 lớp nan đen, Agent 06 tự tính).
    frame_kg / blade_kg / acc_bo đã quy đổi về đơn giá Master Data để BOM x giá vật tư x markup = target_sell."""
    from swind_utils import K
    a_m = float(w_mm or 200.0) / 1000.0
    b_m = float(h_mm or 200.0) / 1000.0
    buoc = K("obd.buoc_nan_m", 0.04)
    he_so = K("obd.he_so", 1.15) * mult
    raw_frame_kg = 2.0 * (a_m + b_m) * K("obd.khung_kg_m", 0.158)
    raw_blade_kg = (a_m / buoc) * b_m * K("obd.nan_kg_m", 0.10)
    raw_acc_cost = (a_m / buoc) * K("obd.phu_kien_moi_nan", 1500.0) + K("obd.phu_kien_co_dinh", 5000.0)
    p_alu = float((get_master_bom_rules().get("diffuser_rules") or {}).get("aluminum_selling_price_per_kg", 168000.0))
    unrounded = ((raw_frame_kg + raw_blade_kg) * p_alu + raw_acc_cost) * he_so
    target = excel_round(unrounded, -3)
    scale = (target / unrounded) if unrounded > 0 else 1.0
    markup = mfg_markup(markup_group)
    p_alu_master = mat_price("MAT-ALU-KHUNG-OBD")
    p_acc_master = mat_price("MAT-DOOR-ACCESSORY")
    return {
        "target_sell": target,
        "frame_kg": raw_frame_kg * (p_alu * he_so * scale) / (p_alu_master * markup),
        "blade_kg": raw_blade_kg * (p_alu * he_so * scale) / (p_alu_master * markup),
        "acc_bo": (raw_acc_cost * he_so * scale) / (p_acc_master * markup),
    }


# ---------------------------------------------------------------- Lưới / LCCT / Lọc G4 (Agent 04, Agent 06)
_MESH = {
    # loai: (khoá pricing_constants, giá mặc định /m², số chữ số làm tròn)
    "lcct": ("cua.luoi_chan_con_trung_m2", 200000.0, 0),   # Lưới chắn côn trùng LCCT (rời / kèm ống-cút)
    "luoi": ("cua.luoi_m2", 150000.0, -3),                 # Lưới gắn cửa / louver
}


def mesh_price(w_mm, h_mm, loai):
    """Giá bán lưới theo diện tích. loai: 'lcct' | 'luoi'.
    Gom giá 2026-11-03: ống/cút có '+ LCCT' (Agent 04) đổi từ luoi_m2 150k sang luoi_chan_con_trung_m2 200k (JSON thắng)."""
    if loai not in _MESH:
        raise ValueError(f"mesh_price: loại lưới không hợp lệ '{loai}' (lcct | luoi)")
    from swind_utils import K
    key, default, ndigits = _MESH[loai]
    return excel_round((float(w_mm) / 1000.0) * (float(h_mm) / 1000.0) * K(key, default), ndigits)


def filter_g4_price(w_mm, h_mm):
    """Giá bán lọc thô G4 kèm khung nhôm theo diện tích (pricing_constants.json -> cua.loc_g4_m2), làm tròn nghìn."""
    from swind_utils import K
    return excel_round((float(w_mm) / 1000.0) * (float(h_mm) / 1000.0) * K("cua.loc_g4_m2", 200000.0), -3)


# ---------------------------------------------------------------- Từ chi phí vật tư -> giá bán (runner & swind_item_inspector)
_COMM_DEFAULT = ["THUONG_MAI", "ONG_MEM", "KHAC"]
_MFG_DEFAULT = ["ONG_GIO", "CUA_GIO", "VAN_GIO", "CANVAS", "TIEU_AM"]


def financial_rates(category, fin_policy):
    """(nhân công, quản lý, lợi nhuận) theo nhóm hàng — financial_policy.json. Nhóm lạ -> như hàng thương mại."""
    fin_policy = fin_policy or {}
    if category in (fin_policy.get("MANUFACTURING", {}).get("categories", _MFG_DEFAULT)) and \
            category not in (fin_policy.get("COMMERCIAL", {}).get("categories", _COMM_DEFAULT)):
        cfg = fin_policy.get("MANUFACTURING", {})
        return cfg.get("labor_rate", 0.25), cfg.get("overhead_rate", 0.10), cfg.get("margin", 0.18)
    cfg = fin_policy.get("COMMERCIAL", {})
    return cfg.get("labor_rate", 0.0), cfg.get("overhead_rate", 0.02), cfg.get("margin", 0.10)


def sell_price(components, price_map, category, fin_policy):
    """Giá bán 1 đơn vị từ BOM: chi phí vật tư (giá Master Data, thiếu -> ref_price) + nhân công & quản lý trên phần
    không phải động cơ, nhân (1 + lợi nhuận); động cơ cộng nguyên giá. Đơn giá làm tròn lên bội 100đ.
    Trả {m_cost, mot_cost, l_cost, o_cost, margin, sell_unit_raw, sell_unit, sell_mat, sell_lab}."""
    m_cost = mot_cost = 0.0
    for c in components:
        cost = c["calc_qty"] * (price_map.get(c["mat_id"], 0.0) or c.get("ref_price", 0.0))
        m_cost += cost
        if c.get("category") == "ĐỘNG_CƠ_VÀ_CẢM_BIẾN":
            mot_cost += cost
    l_rate, o_rate, mg = financial_rates(category, fin_policy)
    l_cost = (m_cost - mot_cost) * l_rate
    o_cost = (m_cost - mot_cost) * o_rate
    raw = math.floor(((m_cost + l_cost + o_cost - mot_cost) * (1 + mg) + mot_cost) + 0.5)
    return {
        "m_cost": m_cost, "mot_cost": mot_cost, "l_cost": l_cost, "o_cost": o_cost, "margin": mg,
        "sell_unit_raw": raw,
        "sell_unit": int(math.ceil(raw / 100.0) * 100) if raw > 0 else 0,
        "sell_mat": math.floor(((m_cost + o_cost - mot_cost) * (1 + mg) + mot_cost) + 0.5),
        "sell_lab": math.floor(l_cost * (1 + mg) + 0.5),
    }
