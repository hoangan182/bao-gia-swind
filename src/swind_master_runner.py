import os
import sys
import glob
import json
import re
import math
import argparse
import shutil
from datetime import datetime

try:
    import openpyxl
except ImportError:
    _venv_py = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "venv", "bin", "python")
    if os.path.exists(_venv_py) and os.path.abspath(sys.executable) != os.path.abspath(_venv_py):
        os.execv(_venv_py, [_venv_py] + sys.argv)
    raise

# Quy trình B: Lập Báo Giá Dự Án từ BOQ Khách Hàng (Agent 01 -> Agent 08)
# Chỉ nhận file BOQ của khách hàng, phân tích và áp giá dựa theo bộ file Master Data đã có sẵn.
# (Quy trình A - Agent 00 giải mã Bảng tính chuẩn 1 lần & Agent 09 cập nhật giá theo yêu cầu được tách độc lập)
from agent_00b_input_normalizer import Agent00B_InputNormalizer
from agent_01_boq_extractor import Agent01_BOQExtractor
from agent_02_boq_reviewer import find_ambiguous_items, resolve_ambiguous_interactive, apply_suggestions_non_interactive
from agent_03_input_auditor import Agent03_InputAuditor
from agent_04_bom_duct import Agent04_DuctworkBOM
from agent_05_bom_damper import Agent05_DamperBOM
from agent_06_bom_diffuser import Agent06_DiffuserBOM
from agent_07_excel_builder import Agent07_ExcelBuilder
from agent_08_qa_checker import Agent08_QAChecker
from swind_utils import vietnamese_slugify, prune_named_styles_in_file, get_quotation_profile, vat_label
from openpyxl.cell.cell import MergedCell

def safe_set(ws, row, col, val, num_fmt=None):
    cell = ws.cell(row, col)
    if not isinstance(cell, MergedCell):
        cell.value = val
        if num_fmt:
            cell.number_format = num_fmt

def resolve_path(rel_path):
    if os.path.isabs(rel_path) and os.path.exists(rel_path):
        return rel_path
    if os.path.exists(rel_path):
        return os.path.abspath(rel_path)
    base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    clean_rel = rel_path.lstrip("./").lstrip("../")
    alt = os.path.join(base, clean_rel)
    if os.path.exists(alt):
        return alt
    alt_src = os.path.join(os.path.dirname(os.path.abspath(__file__)), rel_path)
    if os.path.exists(alt_src):
        return alt_src
    return rel_path

def get_latest_file(directory, prefix, fallback):
    if not os.path.exists(directory):
        return fallback
    pattern = os.path.join(directory, f"{prefix}*.json")
    files = glob.glob(pattern)
    if not files:
        return fallback
    files.sort()
    return files[-1]

def load_master_data():
    """
    Nạp trực tiếp bộ file Master Data đã có sẵn trong data/master_data/ (không giải mã lại Bảng tính chuẩn .xls).
    Bao gồm: master_database_tech.json, phiên bản giá mới nhất trong data/master_data/prices/,
    accessory_rules.json, subtype_rules.json, financial_policy.json.
    """
    prices_dir = resolve_path("data/master_data/prices")
    master_tech_json = resolve_path("data/master_data/master_database_tech.json")
    master_price_json = resolve_path("data/master_data/master_database_price.json")
    
    # 1. Load Tech Data (Deduplicate by MAT_ID, commercial overrides internal)
    with open(master_tech_json, 'r', encoding='utf-8') as f:
        raw_tech = json.load(f)
    tech_map = {item["MAT_ID"]: item for item in raw_tech}
    com_tech_path = resolve_path("data/master_data/master_commercial_tech.json")
    if os.path.exists(com_tech_path):
        with open(com_tech_path, 'r', encoding='utf-8') as f:
            for item in json.load(f):
                tech_map[item["MAT_ID"]] = item
    tech = list(tech_map.values())
            
    # 2. Load Price Data (Audit mechanism: find latest, deduplicate by MAT_ID)
    latest_db_price = get_latest_file(prices_dir, "master_database_price_", master_price_json)
    with open(latest_db_price, 'r', encoding='utf-8') as f:
        raw_price = json.load(f)
    price_map = {item["MAT_ID"]: item for item in raw_price}
        
    com_fallback = resolve_path("data/master_data/master_commercial_price.json")
    latest_com_price = get_latest_file(prices_dir, "master_commercial_price_", com_fallback)
    if os.path.exists(latest_com_price):
        with open(latest_com_price, 'r', encoding='utf-8') as f:
            for item in json.load(f):
                price_map[item["MAT_ID"]] = item
    price = list(price_map.values())
            
    # 3. Load Accessory Rules
    rules_path = resolve_path("data/master_data/accessory_rules.json")
    acc_rules = []
    if os.path.exists(rules_path):
        with open(rules_path, 'r', encoding='utf-8') as f:
            acc_rules = json.load(f)
            
    # 4. Load Subtype Rules
    subtype_rules_path = resolve_path("data/master_data/subtype_rules.json")
    subtype_rules = {}
    if os.path.exists(subtype_rules_path):
        with open(subtype_rules_path, 'r', encoding='utf-8') as f:
            subtype_rules = json.load(f)
            
    # 5. Load Financial Policy
    fin_policy_path = resolve_path("data/master_data/financial_policy.json")
    fin_policy = {}
    if os.path.exists(fin_policy_path):
        with open(fin_policy_path, 'r', encoding='utf-8') as f:
            fin_policy = json.load(f)
            
    return tech, price, acc_rules, subtype_rules, fin_policy

def select_input_file():
    """
    Interactive prompt để chọn file BOQ nếu người dùng không truyền tham số CLI.
    """
    input_dir = resolve_path("input")
    if not os.path.exists(input_dir):
        os.makedirs(input_dir, exist_ok=True)

    img_dir = resolve_path("input picture")
    if os.path.exists(img_dir):
        try:
            from agent_01b_image_boq_reader import Agent01B_ImageBOQReader
            reader = Agent01B_ImageBOQReader(os.path.dirname(input_dir))
            if reader.list_customer_images(img_dir):
                reader.process_image_folder(img_dir, split_per_image=True)
        except Exception as e:
            print(f"[CẢNH BÁO] Không thể tự động đọc ảnh trong 'input picture/': {e}")
        
    candidates = []
    for ext in ["*.xlsx", "*.xls"]:
        candidates.extend(glob.glob(os.path.join(input_dir, ext)))
        
    candidates.sort()
    
    if not candidates:
        print("[LỖI] Không tìm thấy file BOQ nào trong thư mục 'input/'.")
        print("Vui lòng copy file Excel dự thầu vào thư mục 'input/' rồi chạy lại.")
        sys.exit(1)
        
    print("\n" + "=" * 60)
    print("📁 DANH SÁCH FILE BOQ TRONG THƯ MỤC INPUT:")
    print("=" * 60)
    for idx, path in enumerate(candidates, 1):
        print(f"  [{idx}] {os.path.basename(path)}")
        
    print("\n" + "="*60)
    print("⚠️ LƯU Ý QUAN TRỌNG VỀ CÁC GIẢ ĐỊNH BÓC TÁCH (SYSTEM ASSUMPTIONS):")
    print("="*60)
    print("  1. VAN CHẶN LỬA (FD, MFD, MFSD): Tự động ép độ dày tôn và bọc cách nhiệt chống cháy chuẩn EI (MGO/KHS).")
    print("  2. HỘP TIÊU ÂM: Hệ thống mặc định sử dụng Bông Rockwool tỷ trọng 50kg/m3. Nếu dự án yêu cầu 60kg/m3, vui lòng điều chỉnh đơn giá của mã 'ROCKWOOL_50MM_50KG' trong Sheet 06.")
    print("  3. BÍCH KẾT NỐI: Hệ thống mặc định tính TDF/TDC. Nếu dự án bắt buộc dùng Bích V (V30x3), cần tùy chỉnh hệ số bằng tay sau khi xuất file.")
    print("  4. ĐỘNG CƠ & CÁNH VAN: Mặc định báo giá chuẩn theo BOQ ('BẢNG BÁO GIÁ TIÊU CHUẨN'). Chỉ xuất đồng thời 2 phương án Đơn cánh/Đa cánh khi có cờ --dual-options.")
    print("  5. TÁCH FILE DỰ TOÁN: Mặc định tách riêng từng Sheet kỹ thuật ra từng file báo giá độc lập. Dùng --merge-sheets nếu muốn gộp chung.")
    print("  6. VẬT TƯ MỚI: Nếu thấy cảnh báo Đơn Giá = 0 khi chạy xong, hãy nhập giá vào Sheet 06 và chạy 'agent_09_price_learner.py' để hệ thống học giá!")
    print("="*60 + "\n")

    prompt = f">> Chọn số thứ tự file cần chạy dự toán [1-{len(candidates)}] (Mặc định 1): "
    try:
        choice = input(prompt).strip()
        selected_idx = int(choice) - 1 if choice.isdigit() and 1 <= int(choice) <= len(candidates) else 0
    except (EOFError, KeyboardInterrupt):
        selected_idx = 0
        
    return candidates[selected_idx]

def _add_bom_components(builder, sheet_type, parent_id, bom, name=None, note=None):
    """Ghi toàn bộ cấu kiện của 1 BOM (Agent 04/05/06) vào sheet bóc tách tương ứng dưới cùng PARENT_ITEM_ID."""
    for comp in bom["components"]:
        builder.add_subsheet_component(
            sheet_type=sheet_type,
            sub_key=comp["sub_key"],
            parent_id=parent_id,
            comp_name=name(comp) if name else comp["name"],
            category=comp["category"],
            mat_id=comp["mat_id"],
            unit=comp["unit"],
            calc_qty_per_item=comp["calc_qty"],
            note=note(comp) if note else comp.get("note", "")
        )


def process_single_sheet_estimation(
    boq_file,
    source_sheet,
    sheet_items,
    output_workbook,
    qa_report_path,
    tech_records,
    price_records,
    acc_rules,
    subtype_rules,
    fin_policy,
    project_name,
    dual_options=False,
    template_wb=None,
    include_box=False,
    flag_rows=None
):
    """
    Quy trình dự toán và xuất file độc lập cho 1 Sheet kỹ thuật (Agent 04 -> Agent 08).
    """
    print("\n" + "-" * 60)
    print(f"[Sheet: {source_sheet}] Bóc tách định mức & Khởi tạo Workbook Dự toán ({len(sheet_items)} dòng BOQ)...")
    print("-" * 60)

    # Agent 01 giải mã tập trung 1 lần duy nhất toàn bộ hồ sơ kỹ thuật cho từng dòng BOQ
    Agent01_BOQExtractor.enrich_all_items(sheet_items, subtype_rules, price_records=price_records)
    has_standalone_cv_ref = any(
        float(it.get("ref_price") or 0) > 0
        and it.get("category") in ("CUA_GIO", "VAN_GIO")
        and not (it.get("is_box_combo") or (it.get("resolved_spec") or {}).get("is_box_combo"))
        for it in sheet_items
    )

    builder = Agent07_ExcelBuilder(output_workbook, template_file=boq_file, source_sheet=source_sheet, template_wb=template_wb)

    # Nạp Sheet 05 (Tech)
    for idx, item in enumerate(tech_records, 1):
        barem = item.get("Weight_kg_m") or item.get("Density_kg_m2") or ""
        barem_str = f"{barem} kg/m" if item.get("Weight_kg_m") else f"{barem} kg/m2" if item.get("Density_kg_m2") else ""
        builder.add_tech_master_data(
            idx=idx,
            mat_id=item["MAT_ID"],
            category=item["Category"],
            name=item["Name"],
            unit=item["Unit"],
            barem=barem_str,
            source_trace=item.get("Source_Trace", "Master Data")
        )

    # Nạp Sheet 06 (Price)
    tech_names = {item["MAT_ID"]: item.get("Name", "") for item in tech_records}
    tech_cats = {item["MAT_ID"]: item.get("Category", "THUONG_MAI") for item in tech_records}
    for idx, item in enumerate(price_records, 1):
        builder.add_price_master_data(
            idx=idx,
            mat_id=item["MAT_ID"],
            name=tech_names.get(item["MAT_ID"], ""),
            category=tech_cats.get(item["MAT_ID"], "THUONG_MAI"),
            price=item["Price"]
        )

    def get_financial_rates(category):
        comm_cats = fin_policy.get("COMMERCIAL", {}).get("categories", ["THUONG_MAI", "ONG_MEM", "KHAC"])
        mfg_cats = fin_policy.get("MANUFACTURING", {}).get("categories", ["ONG_GIO", "CUA_GIO", "VAN_GIO", "CANVAS", "TIEU_AM"])

        if category in comm_cats:
            cfg = fin_policy.get("COMMERCIAL", {})
            return cfg.get("labor_rate", 0.0), cfg.get("overhead_rate", 0.02), cfg.get("margin", 0.10)
        elif category in mfg_cats:
            cfg = fin_policy.get("MANUFACTURING", {})
            return cfg.get("labor_rate", 0.25), cfg.get("overhead_rate", 0.10), cfg.get("margin", 0.18)
        else:
            cfg = fin_policy.get("COMMERCIAL", {})
            return cfg.get("labor_rate", 0.0), cfg.get("overhead_rate", 0.02), cfg.get("margin", 0.10)

    price_map = {item["MAT_ID"]: float(item.get("Price") or 0) for item in price_records}
    orig_add_comp = builder.add_subsheet_component
    item_comps = {}
    def tracked_add_subsheet_component(sheet_type, sub_key, parent_id, comp_name, category, mat_id, unit, calc_qty_per_item, note="", ref_price=0):
        orig_add_comp(sheet_type, sub_key, parent_id, comp_name, category, mat_id, unit, calc_qty_per_item, note, ref_price)
        item_comps.setdefault(parent_id, []).append({
            "mat_id": mat_id,
            "calc_qty": calc_qty_per_item,
            "category": category,
            "ref_price": ref_price
        })
    builder.add_subsheet_component = tracked_add_subsheet_component

    # Tiến hành phân rã BOM qua Agent 04 (Ống), Agent 05 (Van), Agent 06 (Cửa)
    item_counter = 1
    for item in sheet_items:
        cat = item["category"]
        name = item["name"]
        raw_name = item.get("raw_name", name)
        unit = item["unit"]
        qty = item["qty"]
        w = item["w"]
        h = item["h"]
        l = item["l"]
        d = item.get("d", 0)
        thk = item["thickness"]
        spec = item["resolved_spec"]
        if w > 0 and h > 0 and d > 0 and (w != d or h != d):
            dim_str = f"{int(w)}x{int(h)}/D{int(d)}"
        elif d > 0:
            dim_str = f"D{int(d)}"
        elif w > 0:
            dim_str = f"{int(w)}x{int(h)}"
        else:
            dim_str = "-"

        # Ghi nhận khi BOM phải dùng kích thước GIẢ ĐỊNH (BOQ thiếu 1 cạnh) để cổng kiểm soát cuối yêu cầu xác nhận
        assumed_dim = None
        if d <= 0 and (w <= 0 or h <= 0):
            if cat in ("VAN_GIO", "CUA_GIO"):
                assumed_dim = f"{int(w) if w > 0 else 300}x{int(h) if h > 0 else 300}"
            elif cat == "TIEU_AM":
                assumed_dim = f"{int(w) if w > 0 else 1000}x{int(h) if h > 0 else 1000}"
            elif cat == "ONG_GIO" and str(unit).strip().lower() not in ("m2", "m²", "md", "m"):
                assumed_dim = f"{int(w) if w > 0 else 500}x{int(h) if h > 0 else 500}"
        if assumed_dim:
            item["dim_assumption"] = assumed_dim

        # Tạo ITEM_ID chuẩn
        if cat == "ONG_GIO":
            prefix, group_name = "SW-DUCT", "ỐNG GIÓ"
            size_str = f"{thk:.2f}mm" if not spec["is_fitting"] else dim_str
        elif cat == "VAN_GIO":
            prefix, group_name = "SW-DAMPER", "VAN GIÓ"
            size_str = dim_str
        elif cat == "THUONG_MAI":
            prefix, group_name = "SW-TRD", "THƯƠNG MẠI"
            size_str = dim_str
        elif cat == "ONG_MEM":
            prefix, group_name = "SW-FLEX", "ỐNG GIÓ MỀM"
            size_str = dim_str
        elif cat == "CANVAS":
            prefix, group_name = "SW-CV", "KHỚP NỐI MỀM"
            size_str = dim_str
        elif cat == "TIEU_AM":
            prefix, group_name = "SW-ACST", "VÁCH NGĂN / HỘP TIÊU ÂM"
            size_str = dim_str
        elif cat == "CUA_GIO":
            prefix, group_name = "SW-DIFF", "CỬA GIÓ"
            size_str = dim_str
        else:
            prefix, group_name = "SW-UNKN", "HẠNG MỤC KHÁC"
            size_str = dim_str

        item_id = f"{prefix}-{item_counter:03d}"

        is_box_combo = spec.get("is_box_combo") or item.get("is_box_combo") or (
            any(k in raw_name.lower() for k in ("kèm hộp gió", "kèm hộp", "kèm box", "có hộp gió", "gắn hộp gió"))
            and any(k in raw_name.lower() for k in ("cửa gió", "miệng gió", "cửa cấp", "miệng cấp", "cửa hồi", "miệng hồi"))
        )
        override_price = 0
        box_combo_add_price = 0
        try:
            p_ref = float(item.get("ref_price") or 0)
            if p_ref > 0:
                if is_box_combo and cat == "CUA_GIO":
                    if not include_box and not has_standalone_cv_ref:
                        box_combo_add_price = int(math.ceil(p_ref / 100.0) * 100)
                elif cat not in ("CUA_GIO", "VAN_GIO") and (not has_standalone_cv_ref or cat in ("THUONG_MAI", "KHAC")):
                    override_price = int(round(p_ref))
        except:
            override_price = 0
            box_combo_add_price = 0
        item["override_price"] = override_price

        note_str = spec.get("note_std") or spec.get("note_fslf") or ""
        if not note_str:
            note_str = "Hàng thương mại" if cat == "THUONG_MAI" else "Ống mềm" if cat == "ONG_MEM" else ""

        if is_box_combo and cat == "CUA_GIO" and not include_box:
            if box_combo_add_price > 0:
                note_str = f"{note_str} (ĐG bao gồm Hộp gió đã báo {box_combo_add_price:,.0f}đ + Cửa gió Swind)" if note_str else f"ĐG bao gồm Hộp gió đã báo {box_combo_add_price:,.0f}đ + Cửa gió Swind"
            elif ". Không tính box" not in note_str:
                note_str = f"{note_str} (ĐG chỉ bao gồm phần Cửa gió Swind)" if note_str else "ĐG chỉ bao gồm phần Cửa gió Swind"

        labor_rate, overhead_rate, margin_rate = get_financial_rates(cat)
        builder.add_boq_summary_row(
            stt=item_counter,
            item_id=item_id,
            group=group_name,
            name=name,
            size=size_str,
            unit=unit,
            qty=qty,
            margin=margin_rate,
            labor_rate=labor_rate,
            overhead_rate=overhead_rate,
            note=note_str,
            override_price=override_price,
            box_combo_add_price=box_combo_add_price
        )

        # Bóc tách chi tiết BOM theo Xưởng chuyên môn
        if cat == "ONG_GIO":
            is_fitting = spec["is_fitting"]
            sub_t = spec.get("subtype")
            bom = Agent04_DuctworkBOM.calculate_duct_bom(
                parent_id=item_id,
                w=w if w > 0 else (d if d > 0 else 500),
                h=h if h > 0 else (d if d > 0 else 500),
                l=l if l > 0 else (300 if is_fitting else 1120),
                brand="PN",
                flange_type="TDF",
                is_fitting=is_fitting,
                unit=unit,
                specified_thickness=thk,
                d=d,
                subtype=sub_t,
                item=item
            )
            _add_bom_components(builder, "ONG", item_id, bom)
            if spec.get("has_mesh"):
                w_m = w if w > 0 else (d if d > 0 else 300)
                h_m = h if h > 0 else (d if d > 0 else 300)
                lcct_bom = Agent06_DiffuserBOM.calculate_diffuser_bom(
                    parent_id=f"{item_id}-LCCT",
                    diffuser_type="LCCT",
                    w=w_m,
                    h=h_m,
                    profile_type="LCCT"
                )
                _add_bom_components(builder, "CUA", item_id, lcct_bom)
            if spec.get("has_filter"):
                w_f = w if w > 0 else (d if d > 0 else 300)
                h_f = h if h > 0 else (d if d > 0 else 300)
                flt_bom = Agent06_DiffuserBOM.calculate_diffuser_bom(
                    parent_id=f"{item_id}-G4",
                    diffuser_type="FILTER_G4",
                    w=w_f,
                    h=h_f,
                    profile_type="FILTER_G4"
                )
                _add_bom_components(builder, "CUA", item_id, flt_bom)
        elif cat == "VAN_GIO":
            damper_type = spec["subtype"]
            ei_rating = 0 if damper_type == "MD" else item.get("ei_rating", 0)
            m_code = spec.get("model_code")
            motor_brand = spec.get("motor_brand", "BELIMO")
            bom = Agent05_DamperBOM.calculate_damper_bom(
                parent_id=item_id,
                damper_type="MFD" if damper_type == "MFD_LOUVER" else damper_type,
                w=w if w > 0 else 300,
                h=h if h > 0 else 300,
                brand="PN",
                ei_rating=ei_rating,
                model_code=m_code,
                motor_brand=motor_brand,
                d=d
            )
            _add_bom_components(builder, "VAN", item_id, bom)
            # Van+Van Combo: Tính thêm BOM cho tất cả các van phụ (secondary_dampers) và cộng dồn vào cùng parent_id
            sec_dmps = item.get("secondary_dampers") or ([item.get("secondary_damper")] if item.get("secondary_damper") else [])
            for sec_idx, sec_dmp in enumerate(sec_dmps, 1):
                sec_bom = Agent05_DamperBOM.calculate_damper_bom(
                    parent_id=f"{item_id}-SEC{sec_idx}",
                    damper_type=sec_dmp,
                    w=w if w > 0 else 300,
                    h=h if h > 0 else 300,
                    brand="PN",
                    ei_rating=0,
                    model_code=None,
                    motor_brand=motor_brand,
                    d=d
                )
                _add_bom_components(builder, "VAN", item_id, sec_bom, name=lambda comp: f"Van {sec_dmp} kèm combo - {comp['name']}", note=lambda comp: f"Van phụ {sec_dmp} trong combo {damper_type}+{sec_dmp}")
            if damper_type == "MFD_LOUVER":
                louver_bom = Agent06_DiffuserBOM.calculate_diffuser_bom(
                    parent_id=f"{item_id}-LV",
                    diffuser_type="LOUVER",
                    w=w if w > 0 else 1000,
                    h=h if h > 0 else 1000,
                    profile_type="Z",
                    has_mesh=True
                )
                _add_bom_components(builder, "CUA", item_id, louver_bom, name=lambda comp: f"Louver kèm cửa sổ bù gió - {comp['name']}")
        elif cat in ["THUONG_MAI", "ONG_MEM", "KHAC"]:
            clean_name = vietnamese_slugify(raw_name, max_len=35)
            mat_id = f"MAT-{cat}-{clean_name}"
            comp_unit = unit
            calc_qty_per_item = 1.0
            comm_markup = (1.0 + overhead_rate + labor_rate) * (1.0 + margin_rate)
            if cat == "ONG_MEM" and spec.get("dia_val"):
                nearest_d = min((100, 150, 200, 250, 300, 350, 400), key=lambda k: abs(k - int(spec["dia_val"])))
                mat_id = f"FLEX_DUCT_D{nearest_d}_{spec['subtype']}"
                comp_unit = "ống"
                base_factor = 0.125 if unit.lower() in ["m", "md", "mét", "met"] else 1.0
                calc_qty_per_item = base_factor / comm_markup if comm_markup > 0 else base_factor
            builder.add_subsheet_component(
                sheet_type="ONG",
                sub_key=f"{item_id}-TM",
                parent_id=item_id,
                comp_name=name,
                category=cat,
                mat_id=mat_id,
                unit=comp_unit,
                calc_qty_per_item=calc_qty_per_item,
                note="Ống mềm quy đổi chuẩn 8m/ống" if mat_id.startswith("FLEX_DUCT_") else "Hàng thương mại mua ngoài",
                ref_price=override_price
            )
        elif cat == "CANVAS":
            bom = Agent04_DuctworkBOM.calculate_canvas_bom(
                parent_id=item_id,
                w=w,
                h=h,
                l=l if l > 0 else 200,
                is_fire_resistant=bool(spec.get("is_fire_canvas")),
                d=d,
                raw_name=f"{raw_name} {item.get('note_boq', '')}".strip(),
                unit=unit,
                item=item
            )
            _add_bom_components(builder, "ONG", item_id, bom)
        elif cat == "TIEU_AM":
            bom = Agent04_DuctworkBOM.calculate_acoustic_partition_bom(
                parent_id=item_id,
                w=w if w > 0 else 1000,
                h=h if h > 0 else 1000,
                l=l if l > 0 else 1000,
                unit=unit,
                include_casing=("tiêu âm trong" not in raw_name.lower()),
                is_box=("hộp" in raw_name.lower()),
                d=d,
                raw_name=f"{raw_name} {item.get('note_boq', '')}".strip(),
                item=item
            )
            _add_bom_components(builder, "ONG", item_id, bom)
        elif cat == "CUA_GIO":
            bom = Agent06_DiffuserBOM.calculate_diffuser_bom(
                parent_id=item_id,
                diffuser_type="DIFFUSER",
                w=w if w > 0 else 300,
                h=h if h > 0 else 300,
                profile_type=spec["subtype"],
                has_obd=spec["has_obd"],
                has_mesh=spec["has_mesh"],
                has_filter=spec["has_filter"],
                is_double_layer=spec["is_double_layer"],
                is_black_2nd_layer=spec["is_black_2nd_layer"],
                is_removable=bool(spec.get("is_removable")),
                n_slots=int(spec.get("n_slots") or 0)
            )
            _add_bom_components(builder, "CUA", item_id, bom)
            combo_dmps = item.get("combo_dampers") or ([item["combo_damper"]] if item.get("combo_damper") else [])
            if combo_dmps:
                w_dmp = float(item.get("w_damper") or w or 300)
                h_dmp = float(item.get("h_damper") or h or 300)
                d_dmp = float(item.get("d_damper") or 0)
                for d_idx, c_dmp in enumerate(combo_dmps):
                    dmp_bom = Agent05_DamperBOM.calculate_damper_bom(
                        parent_id=f"{item_id}-{c_dmp}" if d_idx == 0 else f"{item_id}-{c_dmp}{d_idx}",
                        damper_type=c_dmp,
                        w=w_dmp,
                        h=h_dmp,
                        brand="PN",
                        ei_rating=item.get("ei_rating", 0) if d_idx == 0 else 0,
                        model_code=spec.get("model_code") if d_idx == 0 else None,
                        motor_brand=spec.get("motor_brand", "BELIMO"),
                        d=d_dmp
                    )
                    _add_bom_components(builder, "VAN", item_id, dmp_bom, name=lambda comp: f"Van {c_dmp} kèm cửa gió - {comp['name']}")
            if include_box and spec.get("is_box_combo") and spec.get("box_spec"):
                bx = spec["box_spec"]
                box_synth = {
                    "raw_name": f"Hộp gió {int(bx['w_box'])}x{int(bx['h_box'])}xL{int(bx['l_box'])}" + (f" ({bx['n_necks']} cổ D{int(bx['d_box'])})" if bx.get("n_necks", 0) > 0 else ""),
                    "w": bx["w_box"],
                    "h": bx["h_box"],
                    "d": bx.get("d_box", 0.0),
                    "l": bx["l_box"],
                    "thickness": bx["thk_box"],
                    "neck_count": bx.get("n_necks", 0),
                    "is_insulated": bx.get("is_insulated", False),
                    "unit": "cái"
                }
                box_bom = Agent04_DuctworkBOM.calculate_duct_bom(
                    parent_id=f"{item_id}-BOX",
                    w=bx["w_box"],
                    h=bx["h_box"],
                    l=bx["l_box"],
                    brand="HOASEN",
                    flange_type="TDC",
                    is_fitting=True,
                    unit="cái",
                    specified_thickness=bx["thk_box"],
                    d=bx.get("d_box", 0.0),
                    subtype="PLENUM_BOX",
                    item=box_synth
                )
                _add_bom_components(builder, "ONG", item_id, box_bom, name=lambda comp: f"Hộp cửa gió - {comp['name']}")

        # Phụ kiện đi kèm (Accessory Rules) - Chỉ xét trên tên gốc của Cửa gió / Van gió
        if cat in ["CUA_GIO", "VAN_GIO"]:
            for rule in acc_rules:
                kw_low = rule["keyword"].lower()
                if kw_low in raw_name.lower() and not raw_name.lower().startswith(kw_low):
                    if rule.get("mat_id_prefix") == "MAT-BOX-":
                        box_bom = Agent04_DuctworkBOM.calculate_duct_bom(
                            parent_id=f"{item_id}-BOX",
                            w=w if w > 0 else 300,
                            h=h if h > 0 else 300,
                            l=300,
                            brand="PN",
                            flange_type="TDF",
                            is_fitting=True,
                            unit="Bộ"
                        )
                        _add_bom_components(builder, "ONG", item_id, box_bom, name=lambda comp: f"Box cửa gió - {comp['name']}", note=lambda comp: "Bóc tách động Box tôn đi kèm cửa gió")
                    else:
                        acc_mat_id = rule["mat_id_prefix"] + vietnamese_slugify(raw_name, max_len=25)
                        builder.add_subsheet_component(
                            sheet_type=rule["sheet_type"],
                            sub_key=f"{item_id}-{rule['keyword'].upper()}",
                            parent_id=item_id,
                            comp_name=f"{rule['accessory_name_prefix']} {size_str}".strip(),
                            category=rule["category"],
                            mat_id=acc_mat_id,
                            unit="Cái",
                            calc_qty_per_item=1.0,
                            note="Phụ kiện bóc tách động (Rule-based)"
                        )
        # Ghi nhận giá trị dự toán tính toán trực tiếp trên item phục vụ Bảng chào giá thống nhất
        comps = item_comps.get(item_id, [])
        m_cost = 0.0
        mot_cost = 0.0
        for c in comps:
            m_id = c["mat_id"]
            p = price_map.get(m_id, 0.0) or c.get("ref_price", 0.0)
            cost = c["calc_qty"] * p
            m_cost += cost
            if c.get("category") == "ĐỘNG_CƠ_VÀ_CẢM_BIẾN":
                mot_cost += cost

        l_rate, o_rate, mg_rate = get_financial_rates(cat)
        l_cost = (m_cost - mot_cost) * l_rate
        o_cost = (m_cost - mot_cost) * o_rate
        raw_sell_unit = math.floor(((m_cost + l_cost + o_cost - mot_cost) * (1 + mg_rate) + mot_cost) + 0.5)
        diff_sell_unit = int(math.ceil(raw_sell_unit / 100.0) * 100) if raw_sell_unit > 0 else 0
        item["calc_sell_diffuser_unit"] = diff_sell_unit
        if override_price > 0:
            item["calc_sell_unit"] = int(override_price)
            item["calc_sell_mat"] = int(override_price)
            item["calc_sell_lab"] = 0
        elif box_combo_add_price > 0:
            item["calc_sell_mat"] = math.floor(((m_cost + o_cost - mot_cost) * (1 + mg_rate) + mot_cost) + 0.5) + int(box_combo_add_price)
            item["calc_sell_lab"] = math.floor(l_cost * (1 + mg_rate) + 0.5)
            item["calc_sell_unit"] = int(box_combo_add_price + diff_sell_unit)
        else:
            item["calc_sell_mat"] = math.floor(((m_cost + o_cost - mot_cost) * (1 + mg_rate) + mot_cost) + 0.5)
            item["calc_sell_lab"] = math.floor(l_cost * (1 + mg_rate) + 0.5)
            item["calc_sell_unit"] = diff_sell_unit
        item["calc_note"] = note_str
        item["calc_brand"] = "SWIND"
        if qty == 0 and item_id in builder.parent_rows:
            builder.ws_00.cell(builder.parent_rows[item_id], 17, value=int(item["calc_sell_unit"]))

        item_counter += 1

    # Thêm vật tư mới phát sinh vào Sheet 05 & 06
    existing_price_mat_ids = {item["MAT_ID"] for item in price_records}
    missing_mat_idx = len(price_records) + 1
    new_commercial_items = []

    for mat_id, info in builder.used_materials.items():
        if mat_id not in existing_price_mat_ids:
            seed_price = info.get("ref_price", 0) or 0
            builder.add_price_master_data(idx=missing_mat_idx, mat_id=mat_id, name=info["name"], category=info["category"], price=seed_price)
            existing_price_mat_ids.add(mat_id)
            builder.add_tech_master_data(
                idx=missing_mat_idx,
                mat_id=mat_id,
                category=info["category"],
                name=info["name"],
                unit=info["unit"],
                barem="-",
                source_trace="Phát sinh từ BOQ (chưa có trong CSDL)"
            )
            if seed_price == 0:
                new_commercial_items.append({"MAT_ID": mat_id, "Name": info["name"]})
            missing_mat_idx += 1

    builder.add_totals_row()

    # -------------------------------------------------------------
    # LIÊN KẾT MIRROR SHEET (00_BANG_CHAO_GIA) NẾU CÓ (AGENT 07)
    # -------------------------------------------------------------
    if "00_BANG_CHAO_GIA" in builder.wb.sheetnames:
        out_ws = builder.wb["00_BANG_CHAO_GIA"]
        from openpyxl.styles import Font
        boq_map = {}
        for idx, item in enumerate(sheet_items, 1):
            sr = item.get("source_row")
            if sr:
                boq_map.setdefault(sr, []).append(idx + 1)

        # Kiểm tra xem sheet gốc có layout 16/17 cột của Swind, layout CAND, layout Col 9/10 hay layout của Haus Dalat
        is_swind_layout = False
        is_cand_layout = False
        is_col9_layout = False
        for hdr_r in range(1, min(20, out_ws.max_row + 1)):
            v4 = str(out_ws.cell(hdr_r, 4).value or "").lower()
            v6 = str(out_ws.cell(hdr_r, 6).value or "").lower()
            v9 = str(out_ws.cell(hdr_r, 9).value or "").lower()
            v11 = str(out_ws.cell(hdr_r, 11).value or "").lower()
            v14 = str(out_ws.cell(hdr_r, 14).value or "").lower()
            v15 = str(out_ws.cell(hdr_r, 15).value or "").lower()
            if ("số lượng" in v14 or "q'ty" in v14) and ("đơn giá" in v15 or "price" in v15):
                is_swind_layout = True
                break
            if "khối lượng" in v6 and ("đơn giá" in v11 or "vật tư" in v11 or "nhân công" in str(out_ws.cell(hdr_r, 12).value or "").lower()):
                is_cand_layout = True
                break
            if ("số lượng" in v4 or "khối lượng" in v4) and ("đơn giá" in v9 or "price" in v9):
                is_col9_layout = True
                break

        from openpyxl.cell.cell import MergedCell

        def safe_set(ws, row, col, val, num_fmt=None):
            cell = ws.cell(row, col)
            if not isinstance(cell, MergedCell):
                cell.value = val
                if num_fmt:
                    cell.number_format = num_fmt

        if is_swind_layout:
            for r in range(1, out_ws.max_row + 1):
                if r in boq_map:
                    rows = boq_map[r]
                    if len(rows) == 1:
                        safe_set(out_ws, r, 15, f"=ROUND('00_TONG_HOP_BAO_GIA'!Q{rows[0]}, 0)", "#,##0")
                    else:
                        sum_expr = " + ".join([f"'00_TONG_HOP_BAO_GIA'!Q{rr}" for rr in rows])
                        safe_set(out_ws, r, 15, f"=ROUND({sum_expr}, 0)", "#,##0")
                    safe_set(out_ws, r, 16, f"=O{r}*N{r}", "#,##0")
            r_total = out_ws.max_row + 2
            out_ws.cell(row=r_total, column=15, value="TỔNG CỘNG:").font = Font(bold=True, color="FF0000")
            cell_sum = out_ws.cell(row=r_total, column=16, value=f"=SUBTOTAL(9,P1:P{r_total-1})")
            cell_sum.font = Font(bold=True, color="FF0000")
            cell_sum.number_format = "#,##0"
        elif is_col9_layout:
            for r in range(1, out_ws.max_row + 1):
                if r in boq_map:
                    rows = boq_map[r]
                    if len(rows) == 1:
                        safe_set(out_ws, r, 9, f"=ROUND('00_TONG_HOP_BAO_GIA'!Q{rows[0]}, 0)", "#,##0")
                    else:
                        sum_expr = " + ".join([f"'00_TONG_HOP_BAO_GIA'!Q{rr}" for rr in rows])
                        safe_set(out_ws, r, 9, f"=ROUND({sum_expr}, 0)", "#,##0")
                    safe_set(out_ws, r, 10, f"=D{r}*I{r}", "#,##0")
            r_total = out_ws.max_row + 2
            out_ws.cell(row=r_total, column=9, value="TỔNG CỘNG:").font = Font(bold=True, color="FF0000")
            cell_sum = out_ws.cell(row=r_total, column=10, value=f"=SUBTOTAL(9,J1:J{r_total-1})")
            cell_sum.font = Font(bold=True, color="FF0000")
            cell_sum.number_format = "#,##0"
        elif is_cand_layout:
            for r in range(1, out_ws.max_row + 1):
                if r in boq_map:
                    rows = boq_map[r]
                    if len(rows) == 1:
                        sheet00_row = rows[0]
                        safe_set(out_ws, r, 11, f"=IF('00_TONG_HOP_BAO_GIA'!G{sheet00_row}>0, ('00_TONG_HOP_BAO_GIA'!K{sheet00_row} + '00_TONG_HOP_BAO_GIA'!M{sheet00_row}) * (1 + '00_TONG_HOP_BAO_GIA'!P{sheet00_row}) / '00_TONG_HOP_BAO_GIA'!G{sheet00_row}, 0)", "#,##0")
                        safe_set(out_ws, r, 12, f"=IF('00_TONG_HOP_BAO_GIA'!G{sheet00_row}>0, '00_TONG_HOP_BAO_GIA'!L{sheet00_row} * (1 + '00_TONG_HOP_BAO_GIA'!P{sheet00_row}) / '00_TONG_HOP_BAO_GIA'!G{sheet00_row}, 0)", "#,##0")
                        safe_set(out_ws, r, 17, f'=IF(K{r}=0, "CẢNH BÁO: Đơn giá = 0. Tra cứu lại Sheet 06!", \'00_TONG_HOP_BAO_GIA\'!S{sheet00_row})')
                    else:
                        mat_parts = [f"IF('00_TONG_HOP_BAO_GIA'!G{rr}>0, ('00_TONG_HOP_BAO_GIA'!K{rr} + '00_TONG_HOP_BAO_GIA'!M{rr}) * (1 + '00_TONG_HOP_BAO_GIA'!P{rr}) / '00_TONG_HOP_BAO_GIA'!G{rr}, 0)" for rr in rows]
                        lab_parts = [f"IF('00_TONG_HOP_BAO_GIA'!G{rr}>0, '00_TONG_HOP_BAO_GIA'!L{rr} * (1 + '00_TONG_HOP_BAO_GIA'!P{rr}) / '00_TONG_HOP_BAO_GIA'!G{rr}, 0)" for rr in rows]
                        notes_concat = " & \" + \" & ".join([f"'00_TONG_HOP_BAO_GIA'!S{rr}" for rr in rows])
                        safe_set(out_ws, r, 11, f"=ROUND({' + '.join(mat_parts)}, 0)", "#,##0")
                        safe_set(out_ws, r, 12, f"=ROUND({' + '.join(lab_parts)}, 0)", "#,##0")
                        safe_set(out_ws, r, 17, f'=IF(K{r}=0, "CẢNH BÁO: Đơn giá = 0. Tra cứu lại Sheet 06!", {notes_concat})')
                    safe_set(out_ws, r, 13, f"=K{r}*{vat_label()}", "#,##0")
                    safe_set(out_ws, r, 14, f"=L{r}*{vat_label()}", "#,##0")
                    safe_set(out_ws, r, 15, f"=(K{r}+M{r})*F{r}", "#,##0")
                    safe_set(out_ws, r, 16, f"=(L{r}+N{r})*F{r}", "#,##0")
                    item_ref = next((it for it in sheet_items if it.get("source_row") == r), None)
                    if item_ref:
                        safe_set(out_ws, r, 4, item_ref.get("calc_brand", "SWIND"))
            # Cập nhật dòng tổng cộng nguyên bản của biểu mẫu CAND
            has_orig_total = False
            for r_chk in range(max(1, out_ws.max_row - 5), out_ws.max_row + 1):
                c2_val = str(out_ws.cell(r_chk, 2).value or "").lower()
                if "tổng cộng" in c2_val:
                    out_ws.cell(r_chk, 15, value=f"=SUBTOTAL(9,O4:O{r_chk-1})")
                    out_ws.cell(r_chk, 16, value=f"=SUBTOTAL(9,P4:P{r_chk-1})")
                    out_ws.cell(r_chk, 15).number_format = "#,##0"
                    out_ws.cell(r_chk, 16).number_format = "#,##0"
                    if r_chk + 1 <= out_ws.max_row:
                        out_ws.cell(r_chk + 1, 15, value=f"=O{r_chk}+P{r_chk}")
                        out_ws.cell(r_chk + 1, 15).number_format = "#,##0"
                    has_orig_total = True
                    break
            if not has_orig_total:
                r_total = out_ws.max_row + 2
                out_ws.cell(row=r_total, column=14, value="TỔNG CỘNG:").font = Font(bold=True, color="FF0000")
                cell_sum = out_ws.cell(row=r_total, column=15, value=f"=SUBTOTAL(9,O1:O{r_total-1}) + SUBTOTAL(9,P1:P{r_total-1})")
                cell_sum.font = Font(bold=True, color="FF0000")
                cell_sum.number_format = "#,##0"
        else:
            for r in range(1, out_ws.max_row + 1):
                if r in boq_map:
                    rows = boq_map[r]
                    if len(rows) == 1:
                        sheet00_row = rows[0]
                        out_ws.cell(r, 9, value=f"=IF('00_TONG_HOP_BAO_GIA'!G{sheet00_row}>0, ('00_TONG_HOP_BAO_GIA'!K{sheet00_row} + '00_TONG_HOP_BAO_GIA'!M{sheet00_row}) * (1 + '00_TONG_HOP_BAO_GIA'!P{sheet00_row}) / '00_TONG_HOP_BAO_GIA'!G{sheet00_row}, 0)")
                        out_ws.cell(r, 10, value=f"=IF('00_TONG_HOP_BAO_GIA'!G{sheet00_row}>0, '00_TONG_HOP_BAO_GIA'!L{sheet00_row} * (1 + '00_TONG_HOP_BAO_GIA'!P{sheet00_row}) / '00_TONG_HOP_BAO_GIA'!G{sheet00_row}, 0)")
                        out_ws.cell(r, 11, value=f"='00_TONG_HOP_BAO_GIA'!Q{sheet00_row}")
                        out_ws.cell(r, 12, value=f"=('00_TONG_HOP_BAO_GIA'!K{sheet00_row} + '00_TONG_HOP_BAO_GIA'!M{sheet00_row}) * (1 + '00_TONG_HOP_BAO_GIA'!P{sheet00_row})")
                        out_ws.cell(r, 13, value=f"='00_TONG_HOP_BAO_GIA'!L{sheet00_row} * (1 + '00_TONG_HOP_BAO_GIA'!P{sheet00_row})")
                        out_ws.cell(r, 14, value=f"='00_TONG_HOP_BAO_GIA'!R{sheet00_row}")
                        out_ws.cell(r, 15, value=f'=IF(K{r}=0, "CẢNH BÁO: Đơn giá = 0. Tra cứu lại Sheet 06!", \'00_TONG_HOP_BAO_GIA\'!S{sheet00_row})')
                    else:
                        sum_q = " + ".join([f"'00_TONG_HOP_BAO_GIA'!Q{rr}" for rr in rows])
                        sum_r = " + ".join([f"'00_TONG_HOP_BAO_GIA'!R{rr}" for rr in rows])
                        notes_concat = " & \" + \" & ".join([f"'00_TONG_HOP_BAO_GIA'!S{rr}" for rr in rows])
                        out_ws.cell(r, 11, value=f"=ROUND({sum_q}, 0)")
                        out_ws.cell(r, 14, value=f"=ROUND({sum_r}, 0)")
                        out_ws.cell(r, 15, value=f'=IF(K{r}=0, "CẢNH BÁO: Đơn giá = 0. Tra cứu lại Sheet 06!", {notes_concat})')
            r_total = out_ws.max_row + 2
            out_ws.cell(row=r_total, column=13, value="TỔNG CỘNG DỰ ÁN:").font = Font(bold=True, color="FF0000")
            cell_sum = out_ws.cell(row=r_total, column=14, value=f"=SUBTOTAL(9,N1:N{r_total-1})")
            cell_sum.font = Font(bold=True, color="FF0000")
            cell_sum.number_format = "#,##0"

    print("\n" + "-" * 60)
    if dual_options:
        print(f"[{source_sheet}] Xuất bản 2 Phương án Báo giá (Đơn Cánh & Đa Cánh)...")
    else:
        print(f"[{source_sheet}] Xuất bản BẢNG BÁO GIÁ TIÊU CHUẨN (Chuẩn BOQ)...")
    print("-" * 60)
    builder.build_quotation_sheets(sheet_items, subtype_rules, price_records, dual_options=dual_options, flag_rows=flag_rows)
    builder.save()
    print(f"  -> File dự toán đã xuất thành công: {output_workbook}")

    # -------------------------------------------------------------
    # BƯỚC 4: AGENT 08 - INDEPENDENT 3-LAYER QA CHECKER
    # -------------------------------------------------------------
    print("\n" + "-" * 60)
    print(f"[{source_sheet}] [Agent 08 - QA Checker] Kích hoạt kiểm toán độc lập 3 tầng trên Workbook...")
    print("-" * 60)
    checker = Agent08_QAChecker(output_workbook, project_name=project_name, wb=builder.wb)
    report = checker.run_full_audit()
    value_issues = checker.run_value_audit(sheet_items)
    if value_issues:
        report["issues"].extend(value_issues)
        report["total_issues_found"] = len(report["issues"])
        if any(i["severity"] in ("CRITICAL", "HIGH") for i in value_issues):
            report["qa_status"] = "QA_REJECTED"
    with open(qa_report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=4)

    print(f"  -> Trạng thái kiểm toán: {report['qa_status']}")
    print(f"  -> Số hạng mục BOQ kiểm toán: {report['total_items_audited']}")
    print(f"  -> Số cấu kiện linh kiện kiểm toán: {report['total_components_audited']}")
    print(f"  -> Số vấn đề phát hiện: {report['total_issues_found']}")

    if report["issues"]:
        print("  -> DANH SÁCH LỖI / CẢNH BÁO:")
        sev_rank = {"CRITICAL": 0, "HIGH": 1, "WARNING": 2}
        shown = sorted(report["issues"], key=lambda i: sev_rank.get(i["severity"], 3))[:15]
        for issue in shown:
            print(f"     [{issue['severity']}] {issue['sheet']} (Row {issue['row']}): {issue['message']}")
        if len(report["issues"]) > len(shown):
            print(f"     ... (và {len(report['issues']) - len(shown)} vấn đề khác, xem chi tiết trong file QA report)")
    else:
        print("  -> CHỨNG CHỈ QA_PASSED ĐÃ ĐƯỢC CẤP! Báo cáo hoàn toàn hợp lệ.")

    if new_commercial_items:
        print(f"  ⚠️ Phát hiện {len(new_commercial_items)} mặt hàng mới phát sinh có ĐƠN GIÁ = 0 trong Sheet 06.")

    report["_wb"] = builder.wb
    return report


def export_customer_boq_quotation_files(
    boq_file,
    project_dir,
    project_name,
    target_sheets,
    all_items,
    template_wb=None,
    orig_boq_file=None,
    est_wbs=None
):
    """
    Xuất trực tiếp các file Báo giá gửi khách hàng:
    - Giữ nguyên tên file gốc (không thêm hậu tố _BAO_GIA).
    - File báo giá gồm 2 Sheet:
      1. Sheet BOQ gốc giữ nguyên không thay đổi.
      2. Sheet báo giá của Swind với tên sheet là 'BG' (Format chuẩn 16 cột A..P của Swind, đóng khung đầy đủ).
    """
    print("\n" + "=" * 75)
    print("📦 [SWIND MASTER] XUẤT CÁC FILE BÁO GIÁ TIÊU CHUẨN GỬI KHÁCH HÀNG")
    print("=" * 75)

    customer_files = []
    src_boq = orig_boq_file if (orig_boq_file and os.path.exists(orig_boq_file) and orig_boq_file.lower().endswith(('.xlsx', '.xlsm'))) else boq_file
    orig_stem = os.path.splitext(os.path.basename(orig_boq_file or boq_file))[0].strip() if (orig_boq_file or boq_file) else project_name

    # Dọn các file *_BAO_GIA.xlsx cũ trong project_dir nếu có
    for old_bg in glob.glob(os.path.join(project_dir, "*_BAO_GIA.xlsx")):
        try:
            os.remove(old_bg)
        except Exception:
            pass

    for sh_name in target_sheets:
        sh_slug = vietnamese_slugify(sh_name, max_len=30, add_hash=False).replace('-', '_')
        if len(target_sheets) == 1:
            est_file = os.path.join(project_dir, "internal_estimation", f"{project_name}_ESTIMATION.xlsx")
            out_file = os.path.join(project_dir, f"{orig_stem}.xlsx")
            if not os.path.exists(est_file):
                est_file = os.path.join(project_dir, "internal_estimation", f"{project_name}_{sh_slug}_ESTIMATION.xlsx")
        else:
            est_file = os.path.join(project_dir, "internal_estimation", f"{project_name}_{sh_slug}_ESTIMATION.xlsx")
            out_file = os.path.join(project_dir, f"{project_name}_{sh_slug}_BAO_GIA.xlsx")

        if not os.path.exists(est_file):
            continue

        wb = (est_wbs or {}).get(sh_name) or openpyxl.load_workbook(est_file)
        keep_sheet = "BG" if "BG" in wb.sheetnames else ("BẢNG BÁO GIÁ TIÊU CHUẨN" if "BẢNG BÁO GIÁ TIÊU CHUẨN" in wb.sheetnames else wb.sheetnames[0])
        if not (src_boq and os.path.exists(src_boq)):
            for s in list(wb.sheetnames):
                if s != keep_sheet:
                    wb.remove(wb[s])

        ws = wb[keep_sheet]
        ws.title = "BG"
        sh_items = [it for it in all_items if it.get("source_sheet") == sh_name]
        q_row_price = {idx + 1: int(it.get("calc_sell_unit", 0)) for idx, it in enumerate(sh_items, 1)}

        for r in range(14, ws.max_row + 1):
            val_n = ws.cell(r, 14).value
            if isinstance(val_n, str) and "'00_TONG_HOP_BAO_GIA'!Q" in val_n:
                m_q = re.search(r"'00_TONG_HOP_BAO_GIA'!Q(\d+)", val_n)
                if m_q:
                    q_row = int(m_q.group(1))
                    ws.cell(r, 14).value = q_row_price.get(q_row, 0)
                    ws.cell(r, 14).number_format = "#,##0"
            val_p = ws.cell(r, 16).value
            if isinstance(val_p, str) and "FSLF24V US" in val_p:
                ws.cell(r, 16).value = val_p.replace("FSLF24V US", "FSLF US")

        if wb.worksheets:
            wb.active = 0
            if ws.views.sheetView:
                ws.views.sheetView[0].tabSelected = True

        # Giữ nguyên toàn bộ các Sheet BOQ gốc (không thay đổi) + đặt Sheet báo giá 'BG' của Swind ở cuối cùng
        if src_boq and os.path.exists(src_boq):
            from copy import copy
            from swind_merge_quotations import restore_boq_drawings
            wb_cust = openpyxl.load_workbook(src_boq)
            keep_all_orig = (len(target_sheets) == 1)
            orig_keep = sh_name if sh_name in wb_cust.sheetnames else wb_cust.sheetnames[0]
            if not keep_all_orig:
                removed_sheets = [s for s in wb_cust.sheetnames if s != orig_keep]
                if removed_sheets and template_wb is not None and orig_keep in template_wb.sheetnames:
                    ws_keep = wb_cust[orig_keep]
                    ws_val_keep = template_wb[orig_keep]
                    for (rr, cc), cell_k in list(ws_keep._cells.items()):
                        cv = cell_k.value
                        if isinstance(cv, str) and cv.startswith("=") and any(rs in cv for rs in removed_sheets):
                            cell_k.value = ws_val_keep.cell(rr, cc).value
                for s in list(wb_cust.sheetnames):
                    if s != orig_keep:
                        wb_cust.remove(wb_cust[s])
                try:
                    wb_cust.defined_names.clear()
                except Exception:
                    pass
            orig_sheet_count = len(wb_cust.worksheets)
            try:
                from openpyxl.utils import column_index_from_string
                for ws_clean in wb_cust.worksheets:
                    if ws_clean.max_column > 200 or ws_clean.max_row > 20000:
                        if ws_clean.auto_filter and ws_clean.auto_filter.ref:
                            ws_clean.auto_filter.ref = None
                        real_max_c = max((c for (r, c), cell in ws_clean._cells.items() if cell.value is not None), default=20)
                        real_max_r = max((r for (r, c), cell in ws_clean._cells.items() if cell.value is not None), default=100)
                        for m_r in ws_clean.merged_cells.ranges:
                            real_max_c = max(real_max_c, m_r.max_col)
                            real_max_r = max(real_max_r, m_r.max_row)
                        phantom_keys = [k for k in ws_clean._cells if k[1] > real_max_c + 2 or k[0] > real_max_r + 10]
                        for pk in phantom_keys:
                            del ws_clean._cells[pk]
                        for col_l in list(ws_clean.column_dimensions.keys()):
                            if column_index_from_string(col_l) > real_max_c + 2:
                                del ws_clean.column_dimensions[col_l]
            except Exception:
                pass
            bg_title = "BG" if "BG" not in wb_cust.sheetnames else "BG_SWIND"
            ws_swind = wb_cust.create_sheet(bg_title)
            if ws.views.sheetView and ws_swind.views.sheetView:
                ws_swind.views.sheetView[0].showGridLines = ws.views.sheetView[0].showGridLines
            for col_l, dim in ws.column_dimensions.items():
                ws_swind.column_dimensions[col_l].width = dim.width
            for r_idx, dim in ws.row_dimensions.items():
                ws_swind.row_dimensions[r_idx].height = dim.height
            for m_range in ws.merged_cells.ranges:
                ws_swind.merge_cells(str(m_range))
            style_cache = {}
            for row in ws.iter_rows():
                for cell in row:
                    new_c = ws_swind.cell(cell.row, cell.column)
                    if not isinstance(cell, MergedCell) and not isinstance(new_c, MergedCell):
                        new_c.value = cell.value
                    if cell.has_style:
                        s_key = tuple(cell._style)
                        cached_s = style_cache.get(s_key)
                        if cached_s is not None:
                            new_c._style = copy(cached_s)
                        else:
                            new_c.font = copy(cell.font)
                            new_c.fill = copy(cell.fill)
                            new_c.border = copy(cell.border)
                            new_c.alignment = copy(cell.alignment)
                            new_c.number_format = cell.number_format
                            style_cache[s_key] = copy(new_c._style)
            last_idx = len(wb_cust.worksheets) - 1
            wb_cust.active = last_idx
            if wb_cust.views:
                wb_cust.views[0].firstSheet = 0
                wb_cust.views[0].activeTab = last_idx
                wb_cust.views[0].showSheetTabs = True
            if wb_cust.security:
                wb_cust.security.lockStructure = False
            for idx_s, w_s in enumerate(wb_cust.worksheets):
                if w_s.views.sheetView:
                    w_s.views.sheetView[0].tabSelected = (idx_s == last_idx)
            wb_cust.save(out_file)

            # Khôi phục hình ảnh/logo (drawings & media) trên các sheet BOQ gốc nếu có
            if keep_all_orig:
                try:
                    restore_boq_drawings(src_boq, out_file, orig_sheet_count)
                except Exception as e_draw:
                    print(f"  [Cảnh báo] Không thể khôi phục drawing gốc: {e_draw}")

            customer_files.append((sh_name, out_file))
            orig_desc = f"Toàn bộ {orig_sheet_count} Sheets BOQ gốc" if keep_all_orig else f"Sheet '{orig_keep}' gốc"
            print(f"  -> File Báo giá chuẩn gửi khách ({orig_desc} + Sheet '{bg_title}' ở cuối): {out_file}")
        else:
            wb.save(out_file)
            customer_files.append((sh_name, out_file))
            print(f"  -> File Báo giá chuẩn gửi khách: {out_file}")

        # Nếu BOQ gốc là định dạng bảng so sánh nhà thầu (ví dụ Ecoba: có cột ECOBA LỰA CHỌN & PHƯƠNG ÁN 1),
        # đồng thời xuất thêm 1 bản điền trực tiếp trên form gốc của khách hàng
        is_ecoba_sheet = False
        if template_wb is not None and sh_name in template_wb.sheetnames:
            ws_chk_ec = template_wb[sh_name]
            is_ecoba_sheet = ("LỰA CHỌN" in str(ws_chk_ec.cell(10, 16).value or "").upper() and "PHƯƠNG ÁN 1" in str(ws_chk_ec.cell(10, 29).value or "").upper())
        if boq_file and os.path.exists(boq_file) and (is_ecoba_sheet or template_wb is None):
            try:
                wb_cust = openpyxl.load_workbook(boq_file)
                if wb_cust is not None and sh_name in wb_cust.sheetnames:
                    ws_cust = wb_cust[sh_name]
                    v16 = str(ws_cust.cell(10, 16).value or "").upper()
                    v29 = str(ws_cust.cell(10, 29).value or "").upper()
                    if "LỰA CHỌN" in v16 and "PHƯƠNG ÁN 1" in v29:
                        row_map = {it["source_row"]: it for it in sh_items if it.get("source_row")}
                        for r_c in range(12, ws_cust.max_row + 1):
                            c_name = ws_cust.cell(r_c, 8).value
                            c_a = str(ws_cust.cell(r_c, 1).value or "").lower()
                            if "tổng" in c_a or "vat" in c_a:
                                break
                            if r_c in row_map:
                                it_c = row_map[r_c]
                                sp_c = it_c.get("resolved_spec", {})
                                m_val = sp_c.get("model_std") or sp_c.get("model_fslf") or it_c.get("model")
                                b_val = sp_c.get("brand") or "SWIND"
                                p_val = int(it_c.get("calc_sell_unit", 0))
                                n_val = sp_c.get("note_std") or sp_c.get("note_fslf") or ""
                                ws_cust.cell(r_c, 29, value=m_val)
                                ws_cust.cell(r_c, 30, value=b_val)
                                ws_cust.cell(r_c, 31, value="Việt Nam")
                                ws_cust.cell(r_c, 32, value=p_val).number_format = "#,##0"
                                ws_cust.cell(r_c, 34, value=f"=AF{r_c}*M{r_c}").number_format = "#,##0"
                                if ws_cust.cell(r_c, 35).value is None:
                                    ws_cust.cell(r_c, 35, value=f"=AG{r_c}*M{r_c}").number_format = "#,##0"
                                ws_cust.cell(r_c, 36, value=f"=AH{r_c}+AI{r_c}").number_format = "#,##0"
                                ws_cust.cell(r_c, 37, value=n_val)
                                ws_cust.cell(r_c, 16, value=f"=AC{r_c}")
                                ws_cust.cell(r_c, 17, value=f"=AD{r_c}")
                                ws_cust.cell(r_c, 18, value=f"=AE{r_c}")
                                ws_cust.cell(r_c, 19, value=f"=AF{r_c}").number_format = "#,##0"
                                ws_cust.cell(r_c, 21, value=f"=S{r_c}*M{r_c}").number_format = "#,##0"
                                if ws_cust.cell(r_c, 22).value is None:
                                    ws_cust.cell(r_c, 22, value=f"=T{r_c}*M{r_c}").number_format = "#,##0"
                                if ws_cust.cell(r_c, 23).value is None:
                                    ws_cust.cell(r_c, 23, value=f"=V{r_c}+U{r_c}").number_format = "#,##0"
                                ws_cust.cell(r_c, 24, value=f"=AK{r_c}")
                            elif c_name:
                                for col_clr in (16, 17, 18, 19, 24, 29, 30, 31, 32, 37):
                                    ws_cust.cell(r_c, col_clr, value=None)
                        ecoba_out = os.path.join(project_dir, f"{project_name}_BAO_GIA_ECOBA.xlsx")
                        wb_cust.save(ecoba_out)
                        customer_files.append((f"{sh_name} (Form gốc Ecoba)", ecoba_out))
                        print(f"  -> File Báo giá điền trực tiếp trên Form gốc khách hàng: {ecoba_out}")
            except Exception as e:
                print(f"  [Cảnh báo] Không thể xuất form gốc khách hàng: {e}")

    if len(customer_files) > 1:
        from swind_merge_quotations import merge_project_quotation_files
        merged_out = merge_project_quotation_files(
            project_dir=project_dir,
            project_name=project_name,
            sheet_files=customer_files,
            output_file=os.path.join(project_dir, f"{orig_stem}.xlsx"),
            boq_file=src_boq
        )
        if merged_out:
            customer_files.append(("TỔNG HỢP (GỘP CÁC SHEET)", merged_out))
            print(f"  -> File Báo giá chung (Gộp {len(customer_files) - 1} sheets): {merged_out}")

    print("=" * 75 + "\n")
    return customer_files


SWIND_SCOPE_KWS = ("cửa gió", "miệng gió", "cửa cấp", "cửa hồi", "miệng cấp", "miệng hồi", "louver", "cửa chớp", "van ", "van gió",
                   "vcd", "mfd", "nrd", "lọc", "phin lọc", "filter", "ống gió", "tiêu âm", "hộp gió", "plenum", "nối mềm", "canvas")
SWIND_SCOPE_CUA_VAN_KWS = ("cửa gió", "miệng gió", "cửa cấp", "cửa hồi", "miệng cấp", "miệng hồi", "louver", "cửa chớp", "van ", "van gió",
                           "vcd", "mfd", "nrd", "lọc", "phin lọc", "filter")
SWIND_NON_SCOPE_KWS = ("quạt", "thiết bị", "chi phí", "dàn nóng", "dàn lạnh", "điều hòa", "máy ", "ahu", "fcu", "nhân công", "bảo ôn", "cách nhiệt")
# Danh từ chính (đầu tên) của hạng mục KHÔNG phải sản phẩm Swind dù tên có nhắc tới van/cửa/quạt
SWIND_NON_SCOPE_PREFIXES = ("giá treo", "gía treo", "giá đỡ", "gía đỡ", "bộ lò", "lò xo", "bộ điều khiển", "điều khiển", "nút ấn", "nút nhấn",
                            "tủ ", "tủ điện", "cảm biến", "dây ", "cáp ", "quạt", "thiết bị", "chi phí", "nhân công", "máy ", "đồng hồ", "công tắc",
                            "aptomat", "atomat", "mcb", "mccb", "mcc", "hồ sơ", "khối lượng sắt", "sắt thép", "thép ", "chụp hút mùi", "vật tư phụ", "vật tư  phụ",
                            "khung treo", "khung đỡ", "bệ đỡ", "ti treo", "ty treo", "vỏ tủ", "rơ le", "rơle", "đèn", "ống điện", "ống điên",
                            "ống nước", "ống đồng", "ống pvc", "ống ppr", "ống upvc", "ống thép")
# ĐVT trọn gói: không cần kích thước -> không chặn, chỉ cần User xác nhận phạm vi
LUMP_SUM_UNITS = ("lô", "gói", "hệ", "hệ thống", "ls", "lot", "trọn gói", "tg")


DUCT_NAME_PREFIXES = ("ống gió", "ong gio", "ống tròn", "ống xoắn", "ống vuông", "cút", "co 90", "co 45", "côn", "con giam", "con chuyen",
                      "chân rẽ", "chan re", "tê ", "chạc", "bịt đầu", "ống lượn", "chếch", "măng xông", "phụ kiện ống", "pk ống")


def is_duct_like_name(name):
    return any(_main_noun(name).startswith(p) for p in DUCT_NAME_PREFIXES)


def _main_noun(name):
    # Bỏ các động từ đầu dòng ("Cung cấp và lắp đặt", "Gia công, lắp đặt", "SX & LĐ"...) để lấy danh từ chính
    verb = r'(?:cung cấp|gia công|sản xuất|sx|lắp đặt|lắp|lđ|vận chuyển)'
    n = re.sub(r'^\s*[-•*+]+\s*', '', str(name or "").lower().strip())
    return re.sub(rf'^(?:{verb}(?:\s*(?:,|và|&|\+|/)\s*{verb})*)\s*:?\s*', '', n)


def is_swind_product_name(name, scope_kws):
    noun = _main_noun(name)
    if any(noun.startswith(p) for p in SWIND_NON_SCOPE_PREFIXES):
        return False
    return any(k in noun for k in scope_kws)


def audit_full_boq_coverage(boq_wb, target_sheets, raw_all_items, filtered_items, only_cua_van=False, parser=None, include_duct=True):
    """
    Quét toàn bộ 100% các dòng trên từng Sheet BOQ gốc để kiểm tra độ phủ, độc lập với quyết định lọc của parser:
    - Dòng Cửa/Van có KL nhưng thiếu kích thước (không thể báo giá) -> lỗi chặn.
    - Dòng bị parser lọc bỏ có KL mà tên thuộc phạm vi sản phẩm Swind (lọc G4, ống gió m2, tiêu âm...) -> cần xác nhận.
    - Dòng có KL/kích thước mà parser không đọc tới -> nghi sót dòng.
    Trả về dict {sheet: {"missing_dims": [...], "skipped_in_scope": [...], "suspect_unparsed": [...]}}.
    """
    from swind_utils import detect_boq_header
    print("\n" + "-" * 60)
    print("[Agent 01 - Full-BOQ Coverage Audit] Quét 100% dòng BOQ & đối chiếu chống sót...")
    print("-" * 60)
    scope_kws = SWIND_SCOPE_CUA_VAN_KWS if only_cua_van else SWIND_SCOPE_KWS
    if not include_duct:
        scope_kws = tuple(k for k in scope_kws if k != "ống gió")
    coverage = {}
    for sh_name in target_sheets:
        if sh_name not in boq_wb.sheetnames:
            continue
        ws = boq_wb[sh_name]
        header_row, col_map, hidden_rows, _, _ = detect_boq_header(ws)
        raw_list = [it for it in raw_all_items if it.get("source_sheet") == sh_name]
        quoted_list = [it for it in filtered_items if it.get("source_sheet") == sh_name]
        raw_map = {it.get("source_row"): it for it in raw_list if not it.get("is_side_table")}
        quoted_map = {it.get("source_row"): it for it in quoted_list if not it.get("is_side_table")}
        skipped_set = getattr(parser, "skipped_rows", {}).get(sh_name, set()) if parser else set()
        skip_reasons = getattr(parser, "skip_reasons", {}).get(sh_name, {}) if parser else {}
        titles_inherited = sorted({it.get("section", "") for it in filtered_items if it.get("source_sheet") == sh_name and it.get("section") and it.get("section") != "SẢN PHẨM"})
        missing_qty_notes = []
        missing_dims = []
        skipped_in_scope = []
        flag_rows = {}
        skipped_other_cnt = 0
        suspect_unparsed = []
        for r in sorted(skipped_set):
            info = skip_reasons.get(r) or {}
            if float(info.get("qty") or 0) <= 0:
                continue
            nm_l = str(info.get("name") or "").lower()
            desc = f"Dòng {r}: Tên='{info.get('name')}' | Spec='{info.get('spec')}' | ĐVT='{info.get('unit')}' | KL={info.get('qty'):g}"
            is_non_product = any(_main_noun(info.get("name")).startswith(p) for p in SWIND_NON_SCOPE_PREFIXES)
            is_lump_sum = str(info.get("unit") or "").strip().lower() in LUMP_SUM_UNITS
            if info.get("reason") == "MISSING_DIMS" and not is_non_product and not is_lump_sum:
                missing_dims.append(desc)
                flag_rows[r] = "⛔ CHƯA BÁO GIÁ: thiếu kích thước / mã ký hiệu chưa tra được — cần xác nhận"
            elif not is_non_product and is_swind_product_name(nm_l, scope_kws) and not any(k in nm_l for k in SWIND_NON_SCOPE_KWS):
                skipped_in_scope.append(f"{desc} | Lý do lọc={info.get('reason')}")
                flag_rows[r] = f"⚠️ CHƯA BÁO GIÁ: dòng thuộc phạm vi Swind bị lọc ({info.get('reason')}) — cần xác nhận"
            else:
                skipped_other_cnt += 1
        empty_streak = 0
        for r in range((header_row or 1) + 1, ws.max_row + 1):
            if r in hidden_rows:
                continue
            if r in quoted_map:
                empty_streak = 0
                if quoted_map[r].get("is_missing_qty"):
                    missing_qty_notes.append(f"Dòng {r}: '{quoted_map[r].get('raw_name')}' (Title: '{quoted_map[r].get('section')}') — đã áp đơn giá, cột KL gốc để trống")
                continue
            if r in raw_map or r in skipped_set:
                empty_streak = 0
                continue
            nm_v = ws.cell(r, col_map.get("name", 2)).value
            sp_v = ws.cell(r, col_map["spec"]).value if "spec" in col_map else None
            qt_v = ws.cell(r, col_map["qty"]).value if "qty" in col_map else None
            un_v = ws.cell(r, col_map["unit"]).value if "unit" in col_map else None
            row_txt = f"{nm_v or ''} {sp_v or ''}".strip()
            if not row_txt and qt_v is None and un_v is None:
                empty_streak += 1
                if empty_streak >= 40:
                    break
                continue
            empty_streak = 0
            if not row_txt or "tổng cộng" in row_txt.lower():
                continue
            has_pos_qty = isinstance(qt_v, (int, float)) and qt_v > 0
            has_dim = bool(re.search(r'([wWaAbB]?\s*\d{2,4}\s*[xX*]\s*[hHbBwW]?\s*\d{2,4}|\b[dD][nN]?\s*\d{2,4}\b)', row_txt))
            if has_pos_qty or has_dim:
                if only_cua_van and any(k in row_txt.lower() for k in ("ống chờ", "ống lồng", "ống nối mềm", "mềm ei", "khớp nối mềm", "sleeve", "flexible")):
                    continue
                if not include_duct and is_duct_like_name(row_txt):
                    continue
                suspect_unparsed.append(f"Dòng {r}: Tên='{nm_v}' | Spec='{sp_v}' | ĐVT='{un_v}' | KL={qt_v}")
        print(f"  -> Sheet '{sh_name}': Đã báo giá={len(quoted_list)} dòng | Đã lọc ngoài phạm vi={len(raw_list) - len(quoted_list) + len(skipped_set)} dòng | Title cha kế thừa={len(titles_inherited)}")
        if titles_inherited:
            print(f"     • Danh mục Title cha đã quét & kế thừa: {titles_inherited}")
        for mq in missing_qty_notes:
            print(f"     • [Lưu ý KL trống] {mq}")
        if missing_dims:
            print(f"     ⛔ [THIẾU KÍCH THƯỚC — CHƯA CÓ GIÁ, BẮT BUỘC HỎI LẠI USER] {len(missing_dims)} dòng Cửa/Van có KL nhưng không đọc được kích thước (mã ký hiệu S2/R3... cần bảng tra kích thước):")
            for md in missing_dims:
                print(f"        - {md}")
        if skipped_in_scope:
            print(f"     ⚠️ [DÒNG BỊ LỌC CÓ KL THUỘC PHẠM VI SWIND — CẦN XÁC NHẬN] {len(skipped_in_scope)} dòng:")
            for si in skipped_in_scope:
                print(f"        - {si}")
        if skipped_other_cnt:
            print(f"     • {skipped_other_cnt} dòng có KL bị lọc vì ngoài phạm vi (thiết bị, quạt, chi phí...) — xem INPUT_COVERAGE_REPORT.json")
        if suspect_unparsed:
            print(f"     ⚠️ [CẢNH BÁO SÓT DÒNG] Phát hiện {len(suspect_unparsed)} dòng có KL/Kích thước chưa được bóc tách:")
            for su in suspect_unparsed:
                print(f"        - {su}")
        if not (missing_dims or skipped_in_scope or suspect_unparsed):
            print("     ✅ Đạt 100% độ phủ BOQ: Không có dòng Cửa/Van/Vật tư mục tiêu nào bị bỏ sót!")
        coverage[sh_name] = {
            "missing_dims": missing_dims,
            "skipped_in_scope": skipped_in_scope,
            "suspect_unparsed": suspect_unparsed,
            "flag_rows": flag_rows,
            "skipped_rows_detail": {str(k): v for k, v in skip_reasons.items()},
        }
    return coverage


def run_master_pipeline(boq_file, sheet_names=None, interactive=True, auto_accept=False, dual_options=False, merge_sheets=False, only_cua_van=False, motor_brand=None, mfd_model=None, row_overrides=None, neck_size=False, motor_price=None, include_flex_duct=False, spec_priority="name", include_box=False, strict=False, include_duct=False):
    """
    Hàm điều phối Quy trình B: Nhận file BOQ khách hàng -> Phân tích & Áp giá từ Master Data có sẵn (Agent 01 -> Agent 08).
    """
    orig_boq_file = boq_file
    base_name = os.path.basename(boq_file)
    project_name = base_name.replace("_BOQ_MEP (NCC).xlsx", "").replace(".xlsm", "").replace(".xlsx", "").replace(".xls", "").strip()

    project_dir = resolve_path(f"data/projects/{project_name}")
    os.makedirs(project_dir, exist_ok=True)

    # Tối ưu tốc độ: BOQ copy-paste qua nhiều file thường tích tụ hàng chục nghìn Named Style rác (mỗi lần
    # openpyxl mở file chậm 5-9s). Tạo 1 bản gọn (giữ nguyên tên file, giá trị, hình ảnh, VBA) để toàn bộ pipeline dùng.
    fast_dir = os.path.join(project_dir, "internal_estimation", "_fast_boq")
    if boq_file.lower().endswith((".xlsx", ".xlsm")):
        try:
            os.makedirs(fast_dir, exist_ok=True)
            fast_path = os.path.join(fast_dir, base_name)
            n_pruned = prune_named_styles_in_file(boq_file, fast_path)
            if n_pruned > 0:
                print(f"  • [Tối ưu tốc độ] Đã loại {n_pruned:,} Named Style rác trong BOQ gốc (bản gọn dùng nội bộ, file gốc không đổi)")
                boq_file = fast_path
                orig_boq_file = fast_path
        except Exception as e_fast:
            print(f"  • [Tối ưu tốc độ] Bỏ qua bước làm gọn style ({e_fast})")

    print("\n" + "=" * 75)
    print(f"🚀 SWIND BOQ ESTIMATION RUNNER (QUY TRÌNH B: AGENT 01..08) - PROJECT: {project_name.upper()}")
    print("=" * 75)
    print(f"  • File BOQ khách hàng: {boq_file}")
    print("  • Nguồn đơn giá & định mức: data/master_data/ (Master Data có sẵn - Không giải mã lại file chuẩn)")
    print(f"  • Thư mục dự án: {project_dir}")
    print(f"  • Chế độ báo giá van: {'2 Phương án (Đơn Cánh & Đa Cánh)' if dual_options else 'Báo giá chuẩn theo BOQ (Tiêu Chuẩn)'}")
    print(f"  • Chế độ tách Sheet: {'Gộp tất cả sheet' if merge_sheets else 'Tách riêng từng sheet ra file báo giá độc lập'}")
    print(f"  • Thời gian chạy: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # -------------------------------------------------------------
    # BƯỚC 0B: AGENT 00B - INPUT NORMALIZER (CHUẨN HÓA ĐẦU VÀO)
    # -------------------------------------------------------------
    shared_wb = None
    try:
        agent_00b = Agent00B_InputNormalizer(boq_file, interactive=interactive, sheet_names=sheet_names)
        normalized_file, norm_report = agent_00b.normalize()
        if normalized_file != boq_file:
            internal_dir = os.path.join(project_dir, "internal_estimation")
            os.makedirs(internal_dir, exist_ok=True)
            norm_dest = os.path.join(internal_dir, f"{project_name}_NORMALIZED.xlsx")
            if os.path.exists(normalized_file) and os.path.abspath(normalized_file) != os.path.abspath(norm_dest):
                shutil.move(normalized_file, norm_dest)
                normalized_file = norm_dest
                norm_report["output_file"] = norm_dest
            norm_report_path = os.path.join(internal_dir, "INPUT_NORMALIZATION_REPORT.json")
            with open(norm_report_path, "w", encoding="utf-8") as f:
                json.dump(norm_report, f, ensure_ascii=False, indent=2, default=str)
            boq_file = normalized_file
        else:
            shared_wb = getattr(agent_00b, "wb", None)
    except Exception as e:
        print(f"  [Agent 00B] Cảnh báo: Không thể normalize ({e}). Tiếp tục với file gốc.")

    # -------------------------------------------------------------
    # BƯỚC 1: AGENT 01 - BOQ EXTRACTOR & SPEC RESOLVER
    # -------------------------------------------------------------
    print("\n" + "-" * 60)
    print("[Agent 01 - BOQ Extractor] Quét cấu trúc BOQ và nhận diện Sheet kỹ thuật...")
    print("-" * 60)
    Agent01_BOQExtractor.INCLUDE_BOX = bool(include_box)
    agent_01 = Agent01_BOQExtractor(boq_file=boq_file, project_name=project_name, wb=shared_wb, include_flex_duct=include_flex_duct)
    target_sheets, all_items = agent_01.detect_and_parse(sheet_names=sheet_names)
    # Override kích thước cho dòng parser đã loại (thiếu kích thước) -> parse lại với kích thước User cung cấp
    if row_overrides:
        ov_by_sheet = {}
        for k_ov, v_ov in row_overrides.items():
            if isinstance(k_ov, tuple):
                ov_by_sheet[k_ov] = v_ov
            elif len(target_sheets) == 1:
                ov_by_sheet[(target_sheets[0], k_ov)] = v_ov
        need_reparse = any(
            any(k in v for k in ("w", "h", "d")) and r in agent_01.parser.skipped_rows.get(sh, set())
            for (sh, r), v in ov_by_sheet.items()
        )
        if need_reparse:
            agent_01.parser.row_overrides = ov_by_sheet
            target_sheets, all_items = agent_01.detect_and_parse(sheet_names=sheet_names)
            print(f"  -> [--override] Đã parse lại với kích thước do User cung cấp cho {len(ov_by_sheet)} dòng.")
    n_src_sheets = len({it.get("source_sheet") for it in all_items})
    plain_ov_rows = [k for k in (row_overrides or {}) if not isinstance(k, tuple)]
    if plain_ov_rows and n_src_sheets > 1:
        print(f"  ⚠️ [--override] BOQ có {n_src_sheets} sheet: ghi đè theo số dòng {plain_ov_rows} KHÔNG được áp (tránh ghi đè nhầm cùng số dòng ở mọi sheet). Dùng cú pháp 'Tên Sheet!Dòng:...'.")
    for it in all_items:
        it["include_box"] = bool(include_box)
        if spec_priority in ("name", "note"):
            it["spec_priority"] = spec_priority
        if motor_brand:
            it["motor_brand_override"] = str(motor_brand).strip().upper()
        if mfd_model:
            it["mfd_model_override"] = str(mfd_model).strip()
        if neck_size:
            it["neck_size_override"] = True
        r_ov = (row_overrides or {}).get((it.get("source_sheet"), it.get("source_row")))
        if r_ov is None and n_src_sheets <= 1:
            r_ov = (row_overrides or {}).get(it.get("source_row"))
        if r_ov:
            for k_ov, v_ov in r_ov.items():
                if k_ov in ("w", "h", "d", "l", "thickness", "qty", "ref_price"):
                    it[k_ov] = float(v_ov)
                elif k_ov == "skip":
                    it["is_skipped_ei"] = bool(int(v_ov))
                else:
                    it[k_ov] = v_ov
    print(f"  -> Các sheet được chọn xử lý: {target_sheets}")
    print(f"  -> Tổng số dòng sản phẩm bóc tách: {len(all_items)} dòng.")

    if not all_items:
        print("[LỖI] Không bóc tách được dòng sản phẩm nào từ các sheet trên. Dừng quy trình.")
        return {"project_name": project_name, "project_dir": project_dir, "final_file": "",
                "gate": {"blocking": ["Không bóc tách được dòng sản phẩm nào"], "confirm": [], "unpriced_rows": 0}}

    raw_extracted_items = list(all_items)
    if only_cua_van:
        print("\n" + "=" * 75)
        print("🎯 ÁP DỤNG RULE: CHỈ BÁO GIÁ CỬA GIÓ & VAN GIÓ (KHÔNG BÁO ỐNG GIÓ & HÀNG THƯƠNG MẠI)")
        print("=" * 75)
        all_items = [it for it in all_items if it.get("category") in ("CUA_GIO", "VAN_GIO")]
        print(f"  -> Số dòng sản phẩm sau khi lọc: {len(all_items)} dòng (chỉ Cửa gió & Van gió).")
    elif not include_duct:
        n_duct = sum(1 for it in all_items if it.get("category") == "ONG_GIO")
        if n_duct:
            all_items = [it for it in all_items if it.get("category") != "ONG_GIO"]
            print(f"\n  -> [Mặc định] KHÔNG báo giá Ống gió & phụ kiện ống: bỏ {n_duct} dòng ONG_GIO (chạy kèm --include-duct nếu khách yêu cầu báo ống gió).")
            if not all_items:
                print("\n" + "=" * 75)
                print(f"⛔ BOQ chỉ gồm Ống gió & phụ kiện ống ({n_duct} dòng) — mặc định Swind KHÔNG báo giá ống gió.")
                print("   -> Hỏi lại User; nếu khách yêu cầu báo ống gió, chạy lại kèm cờ --include-duct.")
                print("=" * 75 + "\n")
                return {"project_name": project_name, "project_dir": project_dir, "final_file": "",
                        "gate": {"blocking": [f"BOQ chỉ có {n_duct} dòng ống gió (mặc định không báo)"], "confirm": [], "unpriced_rows": 0}}
    n_duct_excluded = 0 if (include_duct or only_cua_van) else sum(1 for it in raw_extracted_items if it.get("category") == "ONG_GIO")

    target_sheets = [sh for sh in target_sheets if any(it.get("source_sheet") == sh for it in all_items)]
    coverage = {}
    try:
        coverage = audit_full_boq_coverage(agent_01.parser.wb, target_sheets, raw_extracted_items, all_items, only_cua_van=only_cua_van, parser=agent_01.parser, include_duct=include_duct)
        internal_dir_cov = os.path.join(project_dir, "internal_estimation")
        os.makedirs(internal_dir_cov, exist_ok=True)
        with open(os.path.join(internal_dir_cov, "INPUT_COVERAGE_REPORT.json"), "w", encoding="utf-8") as f:
            json.dump(coverage, f, ensure_ascii=False, indent=2, default=str)
    except Exception as e_cov:
        print(f"  ⛔ [Coverage Audit lỗi — không xác nhận được độ phủ BOQ] {e_cov}")
        coverage = {"_error": str(e_cov)}

    if not motor_brand and not mfd_model:
        print("  -> [Rule Mặc Định Cố Định] Các van động cơ chưa chỉ định hãng/mã trong BOQ sẽ tự động áp dụng: Mã MFD 1.02 - Động cơ BELIMO.")

    # -------------------------------------------------------------
    # BƯỚC 2: AGENT 02 (BOQ REVIEWER) & AGENT 03 (INPUT AUDITOR)
    # -------------------------------------------------------------
    print("\n" + "-" * 60)
    print("[Agent 02 - BOQ Reviewer] Rà soát phân loại mặt hàng & Học từ khóa ngữ nghĩa...")
    print("-" * 60)
    ambiguous_items = find_ambiguous_items(all_items)
    unresolved_items = []

    if ambiguous_items:
        if interactive:
            resolve_ambiguous_interactive(ambiguous_items, auto_accept_all=auto_accept)
        else:
            print(f"  -> [Non-Interactive Mode] Phát hiện {len(ambiguous_items)} mặt hàng lạ (nhóm KHAC).")
            unresolved_items = apply_suggestions_non_interactive(ambiguous_items, auto_accept=auto_accept, project_name=project_name)
    else:
        print("  -> Tuyệt vời! 100% mặt hàng đã được nhận diện và phân nhóm chuẩn xác.")
    input_audit = Agent03_InputAuditor(project_name=project_name).audit_parsed_boq_items(all_items)
    rep_src = os.path.join(project_dir, "INPUT_AUDIT_REPORT.json")
    rep_dst = os.path.join(project_dir, "internal_estimation", "INPUT_AUDIT_REPORT.json")
    if os.path.exists(rep_src):
        os.makedirs(os.path.join(project_dir, "internal_estimation"), exist_ok=True)
        shutil.move(rep_src, rep_dst)

    # -------------------------------------------------------------
    # BƯỚC 3: NẠP MASTER DATA & THỰC HIỆN DỰ TOÁN THEO RULE
    # -------------------------------------------------------------
    tech_records, price_records, acc_rules, subtype_rules, fin_policy = load_master_data()
    if motor_price is not None and float(motor_price) > 0:
        mp_val = float(motor_price)
        mb_up = str(motor_brand or "").strip().upper()
        target_act_ids = {"MAT-ACTUATOR-HONEYWELL", "MAT-ACTUATOR-HONEYWELL-5NM", "MAT-ACTUATOR-HONEYWELL-10NM", "MAT-ACTUATOR-HONEYWELL-20NM"} if mb_up == "HONEYWELL" else (
            {"MAT-ACTUATOR-KLB-V6006FS500S", "MAT-ACTUATOR-SWIND-VIWECO"} if mb_up == "KLB" else (
                {"MAT-ACTUATOR-BELIMO-FSLF24", "MAT-ACTUATOR-BELIMO-BFN24", "MAT-ACTUATOR-BELIMO-5NM", "MAT-ACTUATOR-BELIMO-10NM", "MAT-ACTUATOR-BELIMO-20NM"}
            )
        )
        changed = []
        for pr in price_records:
            if pr.get("MAT_ID") in target_act_ids:
                changed.append((pr["MAT_ID"], float(pr.get("Price") or 0)))
                pr["Price"] = mp_val
                pr["Purchase_Price"] = mp_val
        print(f"\n  -> [--motor-price] Ghi đè giá gốc {len(changed)} mã động cơ {'(' + mb_up + ')' if mb_up else '(BELIMO - mặc định)'} = {mp_val:,.0f}đ cho dự án này:")
        for mid, old_p in changed:
            print(f"       • {mid}: {old_p:,.0f}đ -> {mp_val:,.0f}đ")
        if len({p for _, p in changed}) > 1:
            print("     ⚠️ Các mã trên vốn có giá gốc KHÁC NHAU (khác moment xoắn / loại). Nếu chỉ muốn ghi đè 1 loại, chạy kèm --motor-brand và kiểm tra lại.")

    generated_files = []
    qa_reports = {}

    if len(target_sheets) > 1 and not merge_sheets:
        print("\n" + "=" * 75)
        print(f"📋 PHÁT HIỆN {len(target_sheets)} SHEET KỸ THUẬT -> XỬ LÝ LẦN LƯỢT {len(target_sheets)} SHEET WORKER")
        print("=" * 75)
        internal_dir = os.path.join(project_dir, "internal_estimation")
        os.makedirs(internal_dir, exist_ok=True)

        def _run_sheet_worker(task_arg):
            s_idx, sh_name = task_arg
            sh_items = [it for it in all_items if it.get("source_sheet") == sh_name]
            if not sh_items:
                print(f"  -> [{s_idx}/{len(target_sheets)}] Sheet '{sh_name}': Không có dòng sản phẩm hợp lệ, bỏ qua.")
                return None

            sh_slug = vietnamese_slugify(sh_name, max_len=30, add_hash=False).replace('-', '_')
            sh_output = os.path.join(internal_dir, f"{project_name}_{sh_slug}_ESTIMATION.xlsx")
            sh_qa = os.path.join(internal_dir, f"QA_Audit_Report_{sh_slug}.json")

            print(f"\n[{s_idx}/{len(target_sheets)}] 🚀 [Worker Agent {s_idx}] BẮT ĐẦU XỬ LÝ SHEET: '{sh_name}' ({len(sh_items)} dòng BOQ)")
            print(f"       -> File xuất: {sh_output}")

            rep_sh = process_single_sheet_estimation(
                boq_file=boq_file,
                source_sheet=sh_name,
                sheet_items=sh_items,
                output_workbook=sh_output,
                qa_report_path=sh_qa,
                tech_records=tech_records,
                price_records=price_records,
                acc_rules=acc_rules,
                subtype_rules=subtype_rules,
                fin_policy=fin_policy,
                project_name=f"{project_name}_{sh_slug}",
                dual_options=dual_options,
                template_wb=agent_01.parser.wb,
                include_box=include_box,
                flag_rows=(coverage.get(sh_name) or {}).get("flag_rows")
            )
            return (sh_name, sh_output, (rep_sh or {}).get("_wb"), rep_sh)

        est_wbs = {}
        # Chạy tuần tự: các worker dùng chung template_wb & price_records (openpyxl không an toàn đa luồng,
        # và xử lý thuần Python bị GIL nên đa luồng không nhanh hơn)
        worker_results = [_run_sheet_worker(t) for t in enumerate(target_sheets, 1)]
        generated_files = []
        for res in worker_results:
            if res is not None:
                generated_files.append((res[0], res[1]))
                if res[2] is not None:
                    est_wbs[res[0]] = res[2]
                if res[3]:
                    qa_reports[res[0]] = res[3]
    else:
        # Xử lý 1 sheet hoặc gộp tất cả sheet theo yêu cầu --merge-sheets
        est_wbs = {}
        primary_sheet = target_sheets[0] if target_sheets else None
        internal_dir = os.path.join(project_dir, "internal_estimation")
        os.makedirs(internal_dir, exist_ok=True)
        output_workbook = os.path.join(internal_dir, f"{project_name}_ESTIMATION.xlsx")
        qa_report_path = os.path.join(internal_dir, "QA_Audit_Report.json")

        rep_main = process_single_sheet_estimation(
            boq_file=boq_file,
            source_sheet=primary_sheet,
            sheet_items=all_items,
            output_workbook=output_workbook,
            qa_report_path=qa_report_path,
            tech_records=tech_records,
            price_records=price_records,
            acc_rules=acc_rules,
            subtype_rules=subtype_rules,
            fin_policy=fin_policy,
            project_name=project_name,
            dual_options=dual_options,
            template_wb=agent_01.parser.wb,
            include_box=include_box,
            flag_rows=(coverage.get(primary_sheet) or {}).get("flag_rows")
        )
        if rep_main:
            qa_reports[primary_sheet or "All"] = rep_main
        if primary_sheet and (rep_main or {}).get("_wb") is not None:
            est_wbs[primary_sheet] = rep_main["_wb"]
        generated_files.append((primary_sheet or "All", output_workbook))

    # -------------------------------------------------------------
    # BƯỚC 5: XUẤT CÁC FILE BÁO GIÁ CHUẨN BOQ GỬI KHÁCH HÀNG (GIỮ NGUYÊN 100% BOQ NGOÀI CỬA & VAN)
    # -------------------------------------------------------------
    customer_files = export_customer_boq_quotation_files(
        boq_file=boq_file,
        project_dir=project_dir,
        project_name=project_name,
        target_sheets=target_sheets,
        all_items=all_items,
        template_wb=agent_01.parser.wb,
        orig_boq_file=orig_boq_file,
        est_wbs=est_wbs
    )

    final_customer_file = customer_files[-1][1] if customer_files else ""
    if final_customer_file and os.path.exists(final_customer_file):
        output_dir = resolve_path("output")
        os.makedirs(output_dir, exist_ok=True)
        # Copy toàn bộ thư mục dự án (bao gồm internal_estimation/) sang output/
        out_project_dir = os.path.join(output_dir, project_name)
        if os.path.exists(out_project_dir):
            archive_previous_output(out_project_dir, project_name)
        shutil.copytree(project_dir, out_project_dir, ignore=shutil.ignore_patterns("_fast_boq"))

        # Dọn output: chỉ giữ file BAO_GIA tổng hợp ở gốc, các file thành phần
        # từng sheet đưa vào thư mục con thanh_phan/
        final_basename = os.path.basename(final_customer_file)
        thanh_phan_dir = os.path.join(out_project_dir, "thanh_phan")
        os.makedirs(thanh_phan_dir, exist_ok=True)
        for f in os.listdir(out_project_dir):
            if f.endswith("_BAO_GIA.xlsx") and f != final_basename:
                shutil.move(
                    os.path.join(out_project_dir, f),
                    os.path.join(thanh_phan_dir, f),
                )

        # Cập nhật đường dẫn file báo giá cuối cùng trỏ sang output/
        out_dest = os.path.join(out_project_dir, final_basename)
        final_customer_file = out_dest
        customer_files[-1] = (customer_files[-1][0], out_dest)
    gate = evaluate_quotation_gate(coverage, qa_reports, input_audit, unresolved_items, parse_errors=getattr(agent_01.parser, "parse_errors", {}), all_items=all_items)
    if not (final_customer_file and os.path.exists(final_customer_file)) and not strict:
        gate["blocking"].append("Không xuất được file báo giá gửi khách (xem log phía trên)")
    if n_duct_excluded:
        gate.setdefault("info", []).append(f"Đã bỏ {n_duct_excluded} dòng Ống gió & phụ kiện ống theo mặc định (báo kèm: --include-duct)")
    if strict and gate["blocking"] and final_customer_file and os.path.exists(final_customer_file):
        os.remove(final_customer_file)
        print("\n" + "=" * 75)
        print("⛔ [--strict] KHÔNG XUẤT FILE BÁO GIÁ vì còn lỗi chặn (xem danh sách bên dưới).")
        print("=" * 75 + "\n")
        final_customer_file = ""
        customer_files = []
    else:
        print("\n" + "=" * 75)
        status_txt = "⛔ BẢN NHÁP — CHƯA HOÀN CHỈNH" if gate["blocking"] else "🎉"
        print(f"{status_txt} FILE BÁO GIÁ CUỐI CÙNG GỬI KHÁCH HÀNG: {final_customer_file}")
        print("=" * 75 + "\n")

    print_quotation_summary_table(target_sheets, all_items, customer_files)
    print_quotation_gate(gate)
    return {"project_name": project_name, "project_dir": project_dir, "final_file": final_customer_file, "gate": gate}


def archive_previous_output(out_project_dir, project_name, keep=5):
    """Chuyển bản output cũ vào output/_history/<project>/<timestamp>/ (giữ tối đa `keep` bản gần nhất)."""
    hist_root = os.path.join(os.path.dirname(out_project_dir), "_history", project_name)
    os.makedirs(hist_root, exist_ok=True)
    ts = datetime.fromtimestamp(os.path.getmtime(out_project_dir)).strftime("%Y%m%d_%H%M%S")
    dest = os.path.join(hist_root, ts)
    if os.path.exists(dest):
        shutil.rmtree(dest)
    shutil.move(out_project_dir, dest)
    for old in sorted(os.listdir(hist_root))[:-keep]:
        shutil.rmtree(os.path.join(hist_root, old), ignore_errors=True)


def evaluate_quotation_gate(coverage, qa_reports, input_audit, unresolved_items, parse_errors=None, all_items=None):
    """
    Cổng chặn cuối: gom các lỗi khiến báo giá CHƯA HOÀN CHỈNH (blocking) và các điểm cần User xác nhận (confirm).
    """
    blocking = []
    confirm = []
    unpriced_rows = 0
    for sh, err in (parse_errors or {}).items():
        blocking.append(f"Sheet '{sh}' bóc tách LỖI và bị bỏ qua toàn bộ: {err}")
    if (coverage or {}).get("_error"):
        blocking.append(f"Coverage Audit lỗi, không xác nhận được độ phủ BOQ: {coverage['_error']}")
    for sh, cv in (coverage or {}).items():
        if sh.startswith("_"):
            continue
        if cv.get("missing_dims"):
            unpriced_rows += len(cv["missing_dims"])
            blocking.append(f"Sheet '{sh}': {len(cv['missing_dims'])} dòng Cửa/Van có KL nhưng thiếu kích thước -> CHƯA CÓ GIÁ (đã tô vàng trên Sheet BG)")
        if cv.get("skipped_in_scope"):
            confirm.append(f"Sheet '{sh}': {len(cv['skipped_in_scope'])} dòng có KL thuộc phạm vi Swind bị lọc (lọc G4, ống gió m2, tiêu âm...) -> xác nhận có báo giá không")
        if cv.get("suspect_unparsed"):
            confirm.append(f"Sheet '{sh}': {len(cv['suspect_unparsed'])} dòng có KL/kích thước chưa được bóc tách")
    for sh, rep in (qa_reports or {}).items():
        issues = rep.get("issues", [])
        unpriced_items = [i for i in issues if i.get("error_type") == "UNPRICED_ITEM"]
        unpriced_rows += len(unpriced_items)
        hard = [i for i in issues if i.get("severity") in ("CRITICAL", "HIGH")]
        if hard:
            kinds = sorted({i["error_type"] for i in hard})
            blocking.append(f"Sheet '{sh}': QA_REJECTED — {len(hard)} lỗi chặn ({', '.join(kinds)})")
        zero_p = [i for i in issues if i.get("error_type") == "ZERO_PRICE"]
        if zero_p:
            confirm.append(f"Sheet '{sh}': {len(zero_p)} cấu kiện có đơn giá vật tư = 0 trong Sheet 06")
        outl = [i for i in issues if i.get("error_type") == "PRICE_OUTLIER"]
        if outl:
            confirm.append(f"Sheet '{sh}': {len(outl)} dòng giá KHÔNG tăng theo kích thước (to hơn nhưng rẻ hơn hẳn hàng nhỏ cùng loại, cùng bậc kích thước) — kiểm tra kích thước/ĐVT: " + "; ".join(f"R{i['row']}" for i in outl[:10]))
    crit_in = (input_audit or {}).get("critical_errors", [])
    if crit_in:
        blocking.append(f"Agent 03: {len(crit_in)} lỗi nghiêm trọng đầu vào (VD: van ghi ĐVT m2): " + "; ".join(f"R{c['row']}" for c in crit_in[:10]))
    if unresolved_items:
        confirm.append(f"Agent 02: {len(unresolved_items)} mặt hàng chưa phân loại (giữ KHAC, chưa báo giá)")
    assumed = [it for it in (all_items or []) if it.get("dim_assumption") and float(it.get("qty") or 0) > 0]
    if assumed:
        confirm.append(f"{len(assumed)} dòng BOQ thiếu 1 cạnh kích thước -> đang tính theo kích thước GIẢ ĐỊNH: "
                       + "; ".join(f"R{it.get('source_row')} '{it.get('raw_name')}'={it['dim_assumption']}" for it in assumed[:10]))
    return {"blocking": blocking, "confirm": confirm, "unpriced_rows": unpriced_rows}


def print_quotation_gate(gate):
    for info in gate.get("info", []):
        print(f"ℹ️  {info}")
    if not gate["blocking"] and not gate["confirm"]:
        print("✅ [KIỂM SOÁT CUỐI] Báo giá hoàn chỉnh: không có dòng thiếu giá, QA đạt, không có điểm cần xác nhận.\n")
        return
    print("=" * 95)
    if gate["blocking"]:
        print("⛔ [KIỂM SOÁT CUỐI] BÁO GIÁ CHƯA HOÀN CHỈNH — BẮT BUỘC HỎI LẠI USER TRƯỚC KHI GỬI KHÁCH")
        print(f"   Dòng có KL nhưng CHƯA CÓ ĐƠN GIÁ: {gate['unpriced_rows']}")
        for b in gate["blocking"]:
            print(f"   ⛔ {b}")
    for c in gate["confirm"]:
        print(f"   ⚠️ {c}")
    print("=" * 95 + "\n")


def print_quotation_summary_table(target_sheets, all_items, customer_files=None):
    """
    In trực tiếp Bảng tổng hợp giá trị dự án (Số dòng, Trước VAT, VAT 8%, Tổng sau VAT)
    và đường dẫn File báo giá cuối cùng ra màn hình console ở định dạng Markdown.
    """
    final_file = customer_files[-1][1] if customer_files else ""
    project_summary = []

    for sh_name in target_sheets:
        sh_items = [it for it in all_items if it.get("source_sheet") == sh_name]
        if not sh_items:
            continue

        sub_total = 0
        active_count = 0
        partner_cnt = 0
        partner_sub = 0
        swind_cnt = 0
        swind_sub = 0
        motor_alerts = []
        for it in sh_items:
            qty = float(it.get("qty") or 0)
            is_missing_qty = bool(it.get("is_missing_qty"))
            if not is_missing_qty and qty > 0:
                active_count += 1
            unit_price = int(it.get("calc_sell_unit", 0))
            line_total = 0 if is_missing_qty else int(round(qty * unit_price))
            sub_total += line_total
            if int(it.get("override_price") or 0) > 0:
                partner_cnt += 1
                partner_sub += line_total
            else:
                swind_cnt += 1
                swind_sub += line_total
                sp = it.get("resolved_spec") or {}
                rn_l = str(it.get("raw_name") or "").lower()
                nb_l = str(it.get("note_boq") or "").lower()
                sub_s = str(sp.get("subtype") or "")
                mod_s = str(sp.get("model_std") or "")
                is_note_prio = (it.get("spec_priority") == "note")
                if it.get("category") == "VAN_GIO" and sub_s in ("MFD", "MD", "MFSD", "MSFD"):
                    full_l = nb_l if (is_note_prio and nb_l) else f"{rn_l} {nb_l}"
                    for b_kw in ("kepler", "klb", "viweco", "honeywell", "siemens"):
                        if b_kw in full_l and (sp.get("motor_brand") or "BELIMO").upper() != b_kw.upper():
                            motor_alerts.append(
                                f"[Hãng ĐC] BOQ R{it.get('source_row')} ({sp.get('a1')}x{sp.get('a2')}, SL={qty:.0f}): "
                                f"Ghi chú/Spec ghi '{b_kw.upper()}' nhưng đang áp {sp.get('motor_brand') or 'BELIMO'} ({mod_s}, ĐG={unit_price:,.0f}đ)"
                            )
                            break
                    m_ei_rn = re.search(r'\bei\s*(60|90|120)\b', rn_l)
                    m_ei_nb = re.search(r'\bei\s*(60|90|120)\b', nb_l)
                    if not is_note_prio and m_ei_rn and m_ei_nb and m_ei_rn.group(1) != m_ei_nb.group(1):
                        motor_alerts.append(
                            f"[Van PCCC - EI Tên vs Spec] BOQ R{it.get('source_row')} ({sp.get('a1')}x{sp.get('a2')}, SL={qty:.0f}): "
                            f"Tên ghi EI{m_ei_rn.group(1)} vs Ghi chú/Spec ghi EI{m_ei_nb.group(1)} ('{it.get('note_boq')}') -> Đang áp Model='{mod_s}' (ĐG={unit_price:,.0f}đ)"
                        )
                if not is_note_prio and it.get("category") == "CUA_GIO" and nb_l:
                    if ("sọt trứng" in nb_l or "eggcrate" in nb_l) and not any(k in rn_l for k in ("sọt trứng", "eggcrate", "ecg")):
                        motor_alerts.append(
                            f"[Cửa gió - Tên vs Ghi chú] BOQ R{it.get('source_row')} ({sp.get('a1')}x{sp.get('a2')}, SL={qty:.0f}): "
                            f"Tên='{it.get('raw_name')}' vs Ghi chú='{it.get('note_boq')}' -> Đang áp Model='{mod_s}' (ĐG={unit_price:,.0f}đ)"
                        )
                    elif ("nan z" in nb_l or "louver" in nb_l) and any(k in rn_l for k in ("nan thẳng", "bầu dục", "khuếch tán", "sọt trứng", "mag", "sag", "rag", "fag", "eag", "oag")):
                        motor_alerts.append(
                            f"[Cửa gió - Tên vs Ghi chú] BOQ R{it.get('source_row')} ({sp.get('a1')}x{sp.get('a2')}, SL={qty:.0f}): "
                            f"Tên='{it.get('raw_name')}' vs Ghi chú='{it.get('note_boq')}' -> Đang áp Model='{mod_s}' (ĐG={unit_price:,.0f}đ)"
                        )
                if not is_note_prio and it.get("category") == "VAN_GIO" and nb_l and sub_s in ("NRD", "PRD", "MPRD", "VCD"):
                    if any(k in nb_l for k in ("mfd", "smd", "van ngăn cháy", "van chặn lửa", "bọc chống cháy", "bọc tấm mgo", "tấm chống cháy mgo", "ei 60", "ei60", "ei 90", "ei90", "ei 120", "ei120")):
                        sec_s = str(it.get("section") or "").strip()
                        raw_s = str(it.get("raw_name") or "").strip()
                        name_disp = f"{sec_s} -> {raw_s}" if (sec_s and sec_s != "SẢN PHẨM" and sec_s.lower() not in raw_s.lower()) else raw_s
                        motor_alerts.append(
                            f"[Van gió - Tên vs Ghi chú] BOQ R{it.get('source_row')} ({sp.get('a1')}x{sp.get('a2')}, SL={qty:.0f}): "
                            f"Tên='{name_disp}' vs Ghi chú='{it.get('note_boq')}' -> Đang áp Model='{mod_s}' (ĐG={unit_price:,.0f}đ)"
                        )
                elif it.get("category") == "VAN_GIO" and nb_l and sub_s in ("MFD", "MFSD") and "van fd" in nb_l and not any(k in nb_l for k in ("mfd", "động cơ", "on/off", "on-off")):
                    sec_s = str(it.get("section") or "").strip()
                    raw_s = str(it.get("raw_name") or "").strip()
                    name_disp = f"{sec_s} -> {raw_s}" if (sec_s and sec_s != "SẢN PHẨM" and sec_s.lower() not in raw_s.lower()) else raw_s
                    motor_alerts.append(
                        f"[Van gió - Tên vs Ghi chú] BOQ R{it.get('source_row')} ({sp.get('a1')}x{sp.get('a2')}, SL={qty:.0f}): "
                        f"Tên='{name_disp}' vs Ghi chú='{it.get('note_boq')}' -> Đang áp Model='{mod_s}' (ĐG={unit_price:,.0f}đ)"
                    )

        vat_amt = int(round(sub_total * get_quotation_profile()["vat_rate"]))
        grand_total = sub_total + vat_amt

        project_summary.append({
            "sheet": sh_name,
            "count": active_count if active_count > 0 else len(sh_items),
            "sub_total": sub_total,
            "vat": vat_amt,
            "grand_total": grand_total,
            "partner_cnt": partner_cnt,
            "partner_sub": partner_sub,
            "swind_cnt": swind_cnt,
            "swind_sub": swind_sub,
            "motor_alerts": motor_alerts,
        })

    if project_summary:
        print("=" * 95)
        print("📈 BẢNG TỔNG HỢP GIÁ TRỊ BÁO GIÁ DỰ ÁN")
        if final_file:
            print(f"📁 File Báo Giá Cuối Cùng: {final_file}")
        print("=" * 95)
        print(f"| STT | Tên Sheet | Số dòng có KL | Trước VAT (VNĐ) | VAT {vat_label()} (VNĐ) | Tổng sau VAT (VNĐ) |")
        print("| :---: | :--- | ---: | ---: | ---: | ---: |")
        tot_items = 0
        tot_sub = 0
        tot_vat = 0
        tot_grand = 0
        for s_idx, ps in enumerate(project_summary, 1):
            tot_items += ps["count"]
            tot_sub += ps["sub_total"]
            tot_vat += ps["vat"]
            tot_grand += ps["grand_total"]
            print(f"| {s_idx} | {ps['sheet']} | {ps['count']} | {ps['sub_total']:,} | {ps['vat']:,} | {ps['grand_total']:,} |")
        print(f"| | **TỔNG CỘNG TOÀN DỰ ÁN** | **{tot_items}** | **{tot_sub:,}** | **{tot_vat:,}** | **{tot_grand:,}** |")
        for ps in project_summary:
            if ps["partner_cnt"] > 0:
                p_pct = (ps["partner_sub"] / ps["sub_total"] * 100) if ps["sub_total"] else 0.0
                s_pct = (ps["swind_sub"] / ps["sub_total"] * 100) if ps["sub_total"] else 0.0
                print(
                    f"\n💡 [Phân tách Nguồn giá Sheet '{ps['sheet']}']: "
                    f"Giữ nguyên giá đối tác {ps['partner_cnt']} dòng = {ps['partner_sub']:,}đ ({p_pct:.1f}%) | "
                    f"Swind báo mới {ps['swind_cnt']} dòng = {ps['swind_sub']:,}đ ({s_pct:.1f}%)"
                )
            if ps["motor_alerts"]:
                print(f"⚠️  [PHÁT HIỆN GHI CHÚ / SPEC KHÁC BIỆT CỘT TÊN — BẮT BUỘC HỎI LẠI USER TRƯỚC KHI CHỐT] ({len(ps['motor_alerts'])} dòng trên Sheet '{ps['sheet']}'):")
                for ma in ps["motor_alerts"][:15]:
                    print(f"   - {ma}")
                if len(ps["motor_alerts"]) > 15:
                    print(f"   ... và {len(ps['motor_alerts']) - 15} dòng tương tự khác.")
        print()


def main():
    parser = argparse.ArgumentParser(description="Swind Multi-Agent Estimation Master Runner")
    parser.add_argument("boq_file", nargs="?", default=None, help="Đường dẫn đến file BOQ Excel")
    parser.add_argument("--sheets", default=None, help="Danh sách Sheet kỹ thuật cần xử lý (ngăn cách bằng dấu phẩy)")
    parser.add_argument("--auto-accept", action="store_true", help="Tự động đồng ý tất cả gợi ý phân loại của AI")
    parser.add_argument("--non-interactive", action="store_true", help="Chạy không tương tác (Headless mode)")
    parser.add_argument("--dual-options", action="store_true", help="Tính đồng thời 2 phương án Đơn cánh và Đa cánh (Mặc định: Báo giá chuẩn theo BOQ)")
    parser.add_argument("--merge-sheets", action="store_true", help="Gộp tất cả các sheet vào 1 file duy nhất (Mặc định: Tách riêng từng sheet)")
    parser.add_argument("--only-cua-van", action="store_true", help="Chỉ báo giá Cửa gió & Van gió (loại bỏ Ống gió và Hàng thương mại mua ngoài)")
    parser.add_argument("--motor-brand", default=None, help="Hãng động cơ van chỉ định theo yêu cầu (BELIMO, KLB, HONEYWELL)")
    parser.add_argument("--mfd-model", default=None, help="Mã đốt van MFD chỉ định theo yêu cầu (1.01, 1.02, 1.03, 1.04, 1.05)")
    parser.add_argument("--allow-ei", action="store_true", help=argparse.SUPPRESS)
    parser.add_argument("--from-images", action="store_true", help="Đọc trực tiếp ảnh khách gửi trong 'input picture/' và chạy báo giá")
    parser.add_argument("--duct-formula", choices=["mpq", "og_mb", "both"], default="mpq", help="Công thức tính ống gió: 'mpq' (BG PKV chuẩn), 'og_mb' (Diện tích m2 theo ÔG MB Z3), hoặc 'both' (xuất cả 2)")
    parser.add_argument("--neck-size", action="store_true", help="Quy định kích thước cửa gió trong BOQ là kích thước cổ (Neck Size -> cộng thêm viền ra kích thước mặt)")
    parser.add_argument("--motor-price", type=float, default=None, help="Ghi đè đơn giá gốc động cơ van cho dự án (VD: 2300000)")
    parser.add_argument("--include-flex-duct", action="store_true", help="Cho phép báo giá Ống gió mềm (Mặc định: Hệ thống KHÔNG báo giá ống mềm, chỉ báo khi có yêu cầu)")
    parser.add_argument("--include-box", action="store_true", help="Tính và báo giá thêm Hộp gió (theo công thức sheet BG PKV) cho các Cửa gió có kèm hộp (Mặc định: Không tính hộp)")
    parser.add_argument("--spec-priority", choices=["name", "note"], default="name", help="Thứ tự ưu tiên khi Cột Tên và Cột Ghi chú/Spec mâu thuẫn: 'name' (mặc định ưu tiên Cột Tên) hoặc 'note' (ưu tiên Cột Ghi chú/Spec)")
    parser.add_argument("--override", default=None, help="Ghi đè nhanh theo dòng BOQ (VD: '7:w=600,h=600;10:skip=1'). BOQ nhiều sheet: 'Tên Sheet!7:w=600'")
    parser.add_argument("--include-duct", action="store_true", help="Báo giá cả Ống gió & phụ kiện ống (Mặc định: KHÔNG báo ống gió, chỉ báo khi khách yêu cầu)")
    parser.add_argument("--strict", action="store_true", help="Không xuất file báo giá nếu còn lỗi chặn (dòng có KL chưa có giá, QA_REJECTED...)")

    args = parser.parse_args()
    if args.allow_ei:
        print("  [Lưu ý] Cờ --allow-ei không còn tác dụng: Swind tự động nhận diện EI theo BOQ.")
    row_overrides = {}
    if args.override:
        for rule_str in str(args.override).split(";"):
            if ":" in rule_str:
                r_part, kv_part = rule_str.rsplit(":", 1) if rule_str.count(":") > 1 and "!" not in rule_str else rule_str.split(":", 1)
                r_part = r_part.strip()
                sh_part = None
                if "!" in r_part:
                    sh_part, r_part = r_part.rsplit("!", 1)
                    sh_part = sh_part.strip().strip("'\"")
                if r_part.strip().isdigit():
                    r_num = int(r_part.strip())
                    ov_key = (sh_part, r_num) if sh_part else r_num
                    row_overrides[ov_key] = {}
                    for kv in kv_part.split(","):
                        if "=" in kv:
                            k, v = kv.split("=", 1)
                            row_overrides[ov_key][k.strip()] = v.strip()

    boq_path = args.boq_file
    boq_paths = []
    if args.from_images or (boq_path and os.path.isdir(resolve_path(boq_path))):
        from agent_01b_image_boq_reader import Agent01B_ImageBOQReader
        ws_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        reader = Agent01B_ImageBOQReader(ws_root)
        img_folder = resolve_path(boq_path) if (boq_path and os.path.isdir(resolve_path(boq_path))) else None
        res = reader.process_image_folder(image_dir=img_folder, split_per_image=True)
        boq_paths = res.get("excel_paths") or []
        if not boq_paths:
            print("[LỖI] Không trích xuất được BOQ từ thư mục ảnh.")
            sys.exit(1)
    elif not boq_path:
        boq_paths = [select_input_file()]
    else:
        resolved_bp = resolve_path(boq_path)
        if not os.path.exists(resolved_bp):
            print(f"[LỖI] Không tìm thấy file: {resolved_bp}")
            sys.exit(1)
        if resolved_bp.lower().endswith('.pdf'):
            from swind_pdf_reader import pdf_to_images
            ws_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            pdf_stem = os.path.splitext(os.path.basename(resolved_bp))[0]
            pdf_img_dir = os.path.join(ws_root, "input picture", f"_pdf_{pdf_stem}")
            pdf_result = pdf_to_images(resolved_bp, output_dir=pdf_img_dir, scale=3)
            if pdf_result["status"] != "OK":
                print(f"[LỖI] Không thể đọc file PDF: {pdf_result.get('error', 'Unknown')}")
                sys.exit(1)
            from agent_01b_image_boq_reader import Agent01B_ImageBOQReader
            reader = Agent01B_ImageBOQReader(ws_root)
            res = reader.process_image_folder(image_dir=pdf_img_dir, split_per_image=True)
            boq_paths = res.get("excel_paths") or []
            if not boq_paths:
                print("[LỖI] Không trích xuất được BOQ từ file PDF.")
                sys.exit(1)
        elif resolved_bp.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tiff')):
            from agent_01b_image_boq_reader import Agent01B_ImageBOQReader
            ws_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            reader = Agent01B_ImageBOQReader(ws_root)
            res = reader.process_image_folder(image_dir=resolved_bp, split_per_image=True)
            boq_paths = res.get("excel_paths") or []
        else:
            boq_paths = [resolved_bp]

    sheets = args.sheets.split(",") if args.sheets else None
    interactive = not args.non_interactive

    run_kwargs = dict(
        sheet_names=sheets,
        interactive=interactive,
        auto_accept=args.auto_accept,
        dual_options=args.dual_options,
        merge_sheets=args.merge_sheets,
        only_cua_van=args.only_cua_van,
        motor_brand=args.motor_brand,
        mfd_model=args.mfd_model,
        row_overrides=row_overrides,
        neck_size=args.neck_size,
        motor_price=args.motor_price,
        include_flex_duct=args.include_flex_duct,
        spec_priority=args.spec_priority,
        include_box=args.include_box,
        strict=args.strict,
        include_duct=args.include_duct or args.duct_formula != "mpq"
    )
    if args.duct_formula != "mpq" and not args.include_duct:
        print(f"  [Lưu ý] --duct-formula {args.duct_formula} -> tự động bật --include-duct (báo giá ống gió).")
    any_blocking = False
    for bp in boq_paths:
        if args.duct_formula == "both":
            # Phương án 1: diện tích m2 theo ÔG MB -> lưu bản sao file báo giá cuối với hậu tố _THEO_M2_OG_MB
            Agent04_DuctworkBOM.DUCT_FORMULA_MODE = "OG_MB_M2"
            res_m2 = run_master_pipeline(boq_file=bp, **run_kwargs) or {}
            m2_copy = None
            if res_m2.get("final_file") and os.path.exists(res_m2["final_file"]):
                m2_copy = res_m2["final_file"][:-5] + "_THEO_M2_OG_MB.xlsx"
                shutil.copy2(res_m2["final_file"], m2_copy)
            any_blocking = any_blocking or bool((res_m2.get("gate") or {}).get("blocking"))
            Agent04_DuctworkBOM.DUCT_FORMULA_MODE = "MPQ_STD"
            res = run_master_pipeline(boq_file=bp, **run_kwargs) or {}
            if m2_copy and res.get("final_file"):
                dest = os.path.join(os.path.dirname(res["final_file"]), os.path.basename(m2_copy))
                if os.path.exists(m2_copy) and os.path.abspath(m2_copy) != os.path.abspath(dest):
                    shutil.copy2(m2_copy, dest)
                print(f"  -> Bản báo giá phương án m2 ÔG MB: {dest}")
        else:
            Agent04_DuctworkBOM.DUCT_FORMULA_MODE = "OG_MB_M2" if args.duct_formula == "og_mb" else "MPQ_STD"
            res = run_master_pipeline(boq_file=bp, **run_kwargs) or {}
        any_blocking = any_blocking or bool((res.get("gate") or {}).get("blocking"))
    sys.exit(2 if any_blocking else 0)


if __name__ == "__main__":
    main()
