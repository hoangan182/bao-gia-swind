import os
import sys
import glob
import json
import re
import math
import argparse
import shutil
from datetime import datetime

# Quy trình B: Lập Báo Giá Dự Án từ BOQ Khách Hàng (Agent 01 -> Agent 08)
# Chỉ nhận file BOQ của khách hàng, phân tích và áp giá dựa theo bộ file Master Data đã có sẵn.
# (Quy trình A - Agent 00 giải mã Bảng tính chuẩn 1 lần & Agent 09 cập nhật giá theo yêu cầu được tách độc lập)
from agent_01_boq_extractor import Agent01_BOQExtractor
from agent_02_boq_reviewer import Agent02_BOQReviewer, find_ambiguous_items, resolve_ambiguous_interactive
from agent_03_input_auditor import Agent03_InputAuditor
from agent_04_bom_duct import Agent04_DuctworkBOM
from agent_05_bom_damper import Agent05_DamperBOM
from agent_06_bom_diffuser import Agent06_DiffuserBOM
from agent_07_excel_builder import Agent07_ExcelBuilder
from agent_08_qa_checker import Agent08_QAChecker
from swind_utils import vietnamese_slugify
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
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
    template_wb=None
):
    """
    Quy trình dự toán và xuất file độc lập cho 1 Sheet kỹ thuật (Agent 04 -> Agent 08).
    """
    print("\n" + "-" * 60)
    print(f"[Sheet: {source_sheet}] Bóc tách định mức & Khởi tạo Workbook Dự toán ({len(sheet_items)} dòng BOQ)...")
    print("-" * 60)

    # Agent 01 giải mã tập trung 1 lần duy nhất toàn bộ hồ sơ kỹ thuật cho từng dòng BOQ
    Agent01_BOQExtractor.enrich_all_items(sheet_items, subtype_rules, price_records=price_records)

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
        dim_str = f"D{int(d)}" if d > 0 else (f"{int(w)}x{int(h)}" if w > 0 else "-")

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
                    box_combo_add_price = p_ref
                else:
                    override_price = p_ref
        except:
            override_price = 0
            box_combo_add_price = 0

        note_str = spec.get("note_std") or spec.get("note_fslf") or ""
        if not note_str:
            note_str = "Hàng thương mại" if cat == "THUONG_MAI" else "Ống mềm" if cat == "ONG_MEM" else ""

        if is_box_combo and cat == "CUA_GIO":
            if box_combo_add_price > 0:
                note_str = f"{note_str} (ĐG bao gồm Hộp gió đã báo {box_combo_add_price:,.0f}đ + Cửa gió Swind)" if note_str else f"ĐG bao gồm Hộp gió đã báo {box_combo_add_price:,.0f}đ + Cửa gió Swind"
            else:
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
            bom = Agent04_DuctworkBOM.calculate_duct_bom(
                parent_id=item_id,
                w=w if w > 0 else 500,
                h=h if h > 0 else 500,
                l=l if l > 0 else (300 if is_fitting else 1120),
                brand="PN",
                flange_type="TDF",
                is_fitting=is_fitting,
                unit=unit,
                specified_thickness=thk
            )
            for comp in bom["components"]:
                builder.add_subsheet_component(
                    sheet_type="ONG",
                    sub_key=comp["sub_key"],
                    parent_id=item_id,
                    comp_name=comp["name"],
                    category=comp["category"],
                    mat_id=comp["mat_id"],
                    unit=comp["unit"],
                    calc_qty_per_item=comp["calc_qty"],
                    note=comp.get("note", "")
                )
        elif cat == "VAN_GIO":
            damper_type = spec["subtype"]
            ei_rating = item.get("ei_rating", 0)
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
            for comp in bom["components"]:
                builder.add_subsheet_component(
                    sheet_type="VAN",
                    sub_key=comp["sub_key"],
                    parent_id=item_id,
                    comp_name=comp["name"],
                    category=comp["category"],
                    mat_id=comp["mat_id"],
                    unit=comp["unit"],
                    calc_qty_per_item=comp["calc_qty"],
                    note=comp.get("note", "")
                )
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
                    motor_brand="BELIMO",
                    d=d
                )
                for comp in sec_bom["components"]:
                    builder.add_subsheet_component(
                        sheet_type="VAN",
                        sub_key=comp["sub_key"],
                        parent_id=item_id,
                        comp_name=f"Van {sec_dmp} kèm combo - {comp['name']}",
                        category=comp["category"],
                        mat_id=comp["mat_id"],
                        unit=comp["unit"],
                        calc_qty_per_item=comp["calc_qty"],
                        note=f"Van phụ {sec_dmp} trong combo {damper_type}+{sec_dmp}"
                    )
            if damper_type == "MFD_LOUVER":
                louver_bom = Agent06_DiffuserBOM.calculate_diffuser_bom(
                    parent_id=f"{item_id}-LV",
                    diffuser_type="LOUVER",
                    w=w if w > 0 else 1000,
                    h=h if h > 0 else 1000,
                    profile_type="Z",
                    has_mesh=True
                )
                for comp in louver_bom["components"]:
                    builder.add_subsheet_component(
                        sheet_type="CUA",
                        sub_key=comp["sub_key"],
                        parent_id=item_id,
                        comp_name=f"Louver kèm cửa sổ bù gió - {comp['name']}",
                        category=comp["category"],
                        mat_id=comp["mat_id"],
                        unit=comp["unit"],
                        calc_qty_per_item=comp["calc_qty"],
                        note=comp.get("note", "")
                    )
        elif cat in ["THUONG_MAI", "ONG_MEM", "KHAC"]:
            clean_name = vietnamese_slugify(raw_name, max_len=35)
            mat_id = f"MAT-{cat}-{clean_name}"
            comp_unit = unit
            calc_qty_per_item = 1.0
            if cat == "ONG_MEM" and spec.get("dia_val"):
                mat_id = f"FLEX_DUCT_D{spec['dia_val']}_{spec['subtype']}"
                comp_unit = "ống"
                if unit.lower() in ["m", "md", "mét", "met"]:
                    calc_qty_per_item = 0.125
            builder.add_subsheet_component(
                sheet_type="ONG",
                sub_key=f"{item_id}-TM",
                parent_id=item_id,
                comp_name=name,
                category=cat,
                mat_id=mat_id,
                unit=comp_unit,
                calc_qty_per_item=calc_qty_per_item,
                note="Ống mềm quy đổi chuẩn 8m/ống" if mat_id.startswith("FLEX_DUCT_") and calc_qty_per_item == 0.125 else "Hàng thương mại mua ngoài",
                ref_price=override_price
            )
        elif cat == "CANVAS":
            canvas_w = (math.pi * float(d)) / 4.0 if d > 0 else (w if w > 0 else 500)
            canvas_h = canvas_w if d > 0 else (h if h > 0 else 500)
            bom = Agent04_DuctworkBOM.calculate_canvas_bom(parent_id=item_id, w=canvas_w, h=canvas_h, l=l if l > 0 else 200)
            for comp in bom["components"]:
                builder.add_subsheet_component(
                    sheet_type="ONG",
                    sub_key=comp["sub_key"],
                    parent_id=item_id,
                    comp_name=comp["name"],
                    category=comp["category"],
                    mat_id=comp["mat_id"],
                    unit=comp["unit"],
                    calc_qty_per_item=comp["calc_qty"],
                    note=comp.get("note", "")
                )
        elif cat == "TIEU_AM":
            bom = Agent04_DuctworkBOM.calculate_acoustic_partition_bom(
                parent_id=item_id,
                w=w if w > 0 else 1000,
                h=h if h > 0 else 1000,
                l=l if l > 0 else 1000,
                unit=unit,
                include_casing=("tiêu âm trong" not in raw_name.lower())
            )
            for comp in bom["components"]:
                builder.add_subsheet_component(
                    sheet_type="ONG",
                    sub_key=comp["sub_key"],
                    parent_id=item_id,
                    comp_name=comp["name"],
                    category=comp["category"],
                    mat_id=comp["mat_id"],
                    unit=comp["unit"],
                    calc_qty_per_item=comp["calc_qty"],
                    note=comp.get("note", "")
                )
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
                is_black_2nd_layer=spec["is_black_2nd_layer"]
            )
            for comp in bom["components"]:
                builder.add_subsheet_component(
                    sheet_type="CUA",
                    sub_key=comp["sub_key"],
                    parent_id=item_id,
                    comp_name=comp["name"],
                    category=comp["category"],
                    mat_id=comp["mat_id"],
                    unit=comp["unit"],
                    calc_qty_per_item=comp["calc_qty"],
                    note=comp.get("note", "")
                )
            if item.get("combo_damper"):
                w_dmp = float(item.get("w_damper") or w or 300)
                h_dmp = float(item.get("h_damper") or h or 300)
                d_dmp = float(item.get("d_damper") or 0)
                dmp_bom = Agent05_DamperBOM.calculate_damper_bom(
                    parent_id=f"{item_id}-MD",
                    damper_type=item["combo_damper"],
                    w=w_dmp,
                    h=h_dmp,
                    brand="PN",
                    ei_rating=item.get("ei_rating", 0),
                    model_code="2.01" if item["combo_damper"] == "FD" else None,
                    motor_brand="BELIMO",
                    d=d_dmp
                )
                for comp in dmp_bom["components"]:
                    builder.add_subsheet_component(
                        sheet_type="VAN",
                        sub_key=comp["sub_key"],
                        parent_id=item_id,
                        comp_name=f"Van {item['combo_damper']} kèm cửa gió - {comp['name']}",
                        category=comp["category"],
                        mat_id=comp["mat_id"],
                        unit=comp["unit"],
                        calc_qty_per_item=comp["calc_qty"],
                        note=comp.get("note", "")
                    )

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
                        for comp in box_bom["components"]:
                            builder.add_subsheet_component(
                                sheet_type="ONG",
                                sub_key=comp["sub_key"],
                                parent_id=item_id,
                                comp_name=f"Box cửa gió - {comp['name']}",
                                category=comp["category"],
                                mat_id=comp["mat_id"],
                                unit=comp["unit"],
                                calc_qty_per_item=comp["calc_qty"],
                                note="Bóc tách động Box tôn đi kèm cửa gió"
                            )
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
        diff_sell_unit = math.floor(((m_cost + l_cost + o_cost - mot_cost) * (1 + mg_rate) + mot_cost) + 0.5)
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
        is_mfd = (cat == "VAN_GIO" and "mfd" in raw_name.lower())
        eff_motor_brand = spec.get("motor_brand") or "BELIMO"
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
                    safe_set(out_ws, r, 13, f"=K{r}*8%", "#,##0")
                    safe_set(out_ws, r, 14, f"=L{r}*8%", "#,##0")
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
    builder.build_quotation_sheets(sheet_items, subtype_rules, price_records, dual_options=dual_options)
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
    with open(qa_report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=4)

    print(f"  -> Trạng thái kiểm toán: {report['qa_status']}")
    print(f"  -> Số hạng mục BOQ kiểm toán: {report['total_items_audited']}")
    print(f"  -> Số cấu kiện linh kiện kiểm toán: {report['total_components_audited']}")
    print(f"  -> Số vấn đề phát hiện: {report['total_issues_found']}")

    if report["issues"]:
        print("  -> DANH SÁCH LỖI / CẢNH BÁO:")
        for issue in report["issues"][:5]:
            print(f"     [{issue['severity']}] {issue['sheet']} (Row {issue['row']}): {issue['message']}")
        if len(report["issues"]) > 5:
            print(f"     ... (và {len(report['issues']) - 5} vấn đề khác, xem chi tiết trong file QA report)")
    else:
        print("  -> CHỨNG CHỈ QA_PASSED ĐÃ ĐƯỢC CẤP! Báo cáo hoàn toàn hợp lệ.")

    if new_commercial_items:
        print(f"  ⚠️ Phát hiện {len(new_commercial_items)} mặt hàng mới phát sinh có ĐƠN GIÁ = 0 trong Sheet 06.")

    return report


def export_customer_boq_quotation_files(
    boq_file,
    project_dir,
    project_name,
    target_sheets,
    all_items,
    template_wb=None
):
    """
    Xuất trực tiếp các file Báo giá gửi khách hàng từ Sheet 'BẢNG BÁO GIÁ TIÊU CHUẨN':
    - Tách riêng từng Sheet kỹ thuật thành 1 file Excel báo giá độc lập.
    - File chỉ chứa DUY NHẤT 1 Sheet: 'BẢNG BÁO GIÁ TIÊU CHUẨN' (Format chuẩn 16 cột A..P của Swind).
    - Toàn bộ đầu mục công việc và vị trí dòng khớp với BOQ của khách gửi.
    - Chỉ fill Model, Thương hiệu, Kích thước (A1..B2), Modul, L, Độ dày, Đơn giá, Thành tiền, Ghi chú cho Cửa gió & Van gió.
    """
    print("\n" + "=" * 75)
    print("📦 [SWIND MASTER] XUẤT CÁC FILE BÁO GIÁ TIÊU CHUẨN GỬI KHÁCH HÀNG")
    print("=" * 75)

    customer_files = []

    for sh_name in target_sheets:
        sh_slug = vietnamese_slugify(sh_name, max_len=30, add_hash=False).replace('-', '_')
        est_file = os.path.join(project_dir, "internal_estimation", f"{project_name}_{sh_slug}_ESTIMATION.xlsx")
        out_file = os.path.join(project_dir, f"{project_name}_{sh_slug}_BAO_GIA.xlsx")

        if not os.path.exists(est_file):
            alt_est = os.path.join(project_dir, "internal_estimation", f"{project_name}_ESTIMATION.xlsx")
            if len(target_sheets) == 1 and os.path.exists(alt_est):
                est_file = alt_est
                out_file = os.path.join(project_dir, f"{project_name}_BAO_GIA.xlsx")
            else:
                continue

        wb = openpyxl.load_workbook(est_file)
        keep_sheet = "BẢNG BÁO GIÁ TIÊU CHUẨN" if "BẢNG BÁO GIÁ TIÊU CHUẨN" in wb.sheetnames else wb.sheetnames[0]
        for s in list(wb.sheetnames):
            if s != keep_sheet:
                wb.remove(wb[s])

        ws = wb[keep_sheet]
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

        if wb.worksheets:
            wb.active = 0
            if ws.views.sheetView:
                ws.views.sheetView[0].tabSelected = True

        wb.save(out_file)
        customer_files.append((sh_name, out_file))
        print(f"  -> File Báo giá chuẩn gửi khách: {out_file}")

        # Nếu BOQ gốc là định dạng bảng so sánh nhà thầu (ví dụ Ecoba: có cột ECOBA LỰA CHỌN & PHƯƠNG ÁN 1),
        # đồng thời xuất thêm 1 bản điền trực tiếp trên form gốc của khách hàng
        if boq_file and os.path.exists(boq_file):
            try:
                from collections import defaultdict
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
                                ws_cust.cell(r_c, 34, value=f"=ROUNDUP(AF{r_c}*M{r_c}, -2)").number_format = "#,##0"
                                if ws_cust.cell(r_c, 35).value is None:
                                    ws_cust.cell(r_c, 35, value=f"=AG{r_c}*M{r_c}").number_format = "#,##0"
                                ws_cust.cell(r_c, 36, value=f"=AH{r_c}+AI{r_c}").number_format = "#,##0"
                                ws_cust.cell(r_c, 37, value=n_val)
                                ws_cust.cell(r_c, 16, value=f"=AC{r_c}")
                                ws_cust.cell(r_c, 17, value=f"=AD{r_c}")
                                ws_cust.cell(r_c, 18, value=f"=AE{r_c}")
                                ws_cust.cell(r_c, 19, value=f"=AF{r_c}").number_format = "#,##0"
                                ws_cust.cell(r_c, 21, value=f"=ROUNDUP(S{r_c}*M{r_c}, -2)").number_format = "#,##0"
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
                    else:
                        header_r = None
                        p_col = None
                        t_col = None
                        q_col = None
                        brand_col = None
                        model_col = None
                        note_col = None
                        from openpyxl.utils import get_column_letter

                        for r_chk in range(1, min(30, ws_cust.max_row + 1)):
                            for c_chk in range(1, min(25, ws_cust.max_column + 1)):
                                v_chk = str(ws_cust.cell(r_chk, c_chk).value or "").strip().lower()
                                if "đơn giá" in v_chk and not p_col:
                                    header_r = r_chk
                                    p_col = c_chk
                                elif "thành tiền" in v_chk and not t_col:
                                    t_col = c_chk
                                elif any(k in v_chk for k in ("khối lượng", "số lượng")) and not q_col:
                                    q_col = c_chk
                                elif any(k in v_chk for k in ("nhãn hiệu", "xuất xứ")) and not brand_col:
                                    brand_col = c_chk
                                elif any(k in v_chk for k in ("mã hiệu", "quy cách", "thông số")) and not model_col:
                                    model_col = c_chk
                                elif "ghi chú" in v_chk and not note_col:
                                    note_col = c_chk
                            if p_col and t_col:
                                break

                        if header_r and p_col and t_col:
                            row_map = defaultdict(list)
                            for it in sh_items:
                                if it.get("source_row"):
                                    row_map[it["source_row"]].append(it)

                            col_p_let = get_column_letter(p_col)
                            col_q_let = get_column_letter(q_col) if q_col else "F"
                            col_t_let = get_column_letter(t_col)

                            first_data_r = header_r + 1
                            last_data_r = header_r + 1
                            sum_vat_row = None

                            for r_c in range(header_r + 1, ws_cust.max_row + 1):
                                if ws_cust.row_dimensions[r_c].hidden:
                                    continue
                                c_b = str(ws_cust.cell(r_c, 2).value or "").strip().lower()
                                if any(k in c_b for k in ("tổng trước vat", "tổng cộng", "tổng giá trị")):
                                    sum_vat_row = r_c
                                    last_data_r = r_c - 1
                                    break
                                if r_c in row_map:
                                    last_data_r = r_c
                                    its_c = row_map[r_c]
                                    curr_price = ws_cust.cell(r_c, p_col).value
                                    curr_p_val = 0
                                    try:
                                        if curr_price is not None:
                                            curr_p_val = float(str(curr_price).replace(",", "").strip())
                                    except:
                                        curr_p_val = 0

                                    is_any_box_combo = any(it_c.get("is_box_combo") or it_c.get("resolved_spec", {}).get("is_box_combo") for it_c in its_c)
                                    if is_any_box_combo:
                                        diff_p = sum(int(it_c.get("calc_sell_diffuser_unit", it_c.get("calc_sell_unit", 0))) for it_c in its_c)
                                        diff_models = [it_c.get("resolved_spec", {}).get("model_std") or it_c.get("resolved_spec", {}).get("model_fslf") or "Cửa gió" for it_c in its_c]
                                        m_str = "/".join(filter(None, diff_models)) or "Cửa gió"
                                        if curr_p_val > 0:
                                            total_combo_p = int(curr_p_val + diff_p)
                                            ws_cust.cell(r_c, p_col, value=total_combo_p).number_format = "#,##0"
                                            ws_cust.cell(r_c, t_col, value=f"=ROUNDUP({col_p_let}{r_c}*{col_q_let}{r_c}, -2)").number_format = "#,##0"
                                            if note_col:
                                                curr_n = str(ws_cust.cell(r_c, note_col).value or "").strip()
                                                if curr_n and curr_n != "0":
                                                    if "không gồm cửa gió" in curr_n.lower():
                                                        new_n = curr_n.replace("không gồm cửa gió", f"đã gồm Cửa gió Swind ({m_str})")
                                                    elif "cửa gió" not in curr_n.lower():
                                                        new_n = f"{curr_n} + Cửa gió Swind ({m_str})"
                                                    else:
                                                        new_n = f"{curr_n} (kèm Cửa gió {m_str})"
                                                    ws_cust.cell(r_c, note_col, value=new_n)
                                                else:
                                                    ws_cust.cell(r_c, note_col, value=f"ĐG gồm Hộp gió {curr_p_val:,.0f}đ + Cửa gió Swind ({m_str})")
                                        else:
                                            ws_cust.cell(r_c, p_col, value=diff_p).number_format = "#,##0"
                                            ws_cust.cell(r_c, t_col, value=f"=ROUNDUP({col_p_let}{r_c}*{col_q_let}{r_c}, -2)").number_format = "#,##0"
                                            if note_col:
                                                curr_n = str(ws_cust.cell(r_c, note_col).value or "").strip()
                                                if not curr_n or curr_n == "0":
                                                    ws_cust.cell(r_c, note_col, value=f"Đơn giá chỉ bao gồm phần Cửa gió Swind ({m_str}), chưa gồm hộp gió")
                                        if model_col:
                                            curr_m = str(ws_cust.cell(r_c, model_col).value or "").strip()
                                            if not curr_m or curr_m == "0":
                                                ws_cust.cell(r_c, model_col, value=m_str)
                                        if brand_col:
                                            curr_b = str(ws_cust.cell(r_c, brand_col).value or "").strip()
                                            if not curr_b or curr_b == "0":
                                                ws_cust.cell(r_c, brand_col, value="SWIND")
                                    elif curr_p_val > 0:
                                        ws_cust.cell(r_c, p_col, value=curr_p_val).number_format = "#,##0"
                                        ws_cust.cell(r_c, t_col, value=f"=ROUNDUP({col_p_let}{r_c}*{col_q_let}{r_c}, -2)").number_format = "#,##0"
                                    else:
                                        calc_p = sum(int(it_c.get("calc_sell_unit", 0)) for it_c in its_c)
                                        ws_cust.cell(r_c, p_col, value=calc_p).number_format = "#,##0"
                                        ws_cust.cell(r_c, t_col, value=f"=ROUNDUP({col_p_let}{r_c}*{col_q_let}{r_c}, -2)").number_format = "#,##0"
                                        if brand_col:
                                            curr_b = str(ws_cust.cell(r_c, brand_col).value or "").strip()
                                            if not curr_b or curr_b == "0":
                                                b_tokens = []
                                                for it_c in its_c:
                                                    b_str = it_c.get("calc_brand") or it_c.get("resolved_spec", {}).get("brand")
                                                    if b_str:
                                                        for part in b_str.split("/"):
                                                            p_strip = part.strip()
                                                            if p_strip and p_strip not in b_tokens:
                                                                b_tokens.append(p_strip)
                                                b_val = " / ".join(b_tokens) or "SWIND"
                                                ws_cust.cell(r_c, brand_col, value=b_val)
                                        if model_col:
                                            curr_m = str(ws_cust.cell(r_c, model_col).value or "").strip()
                                            if not curr_m or curr_m == "0":
                                                m_val = " / ".join(filter(None, [it_c.get("resolved_spec", {}).get("model_std") or it_c.get("resolved_spec", {}).get("model_fslf") or it_c.get("model") for it_c in its_c]))
                                                if m_val:
                                                    ws_cust.cell(r_c, model_col, value=m_val)
                                        if note_col:
                                            curr_n = str(ws_cust.cell(r_c, note_col).value or "").strip()
                                            if not curr_n or curr_n == "0":
                                                n_val = " / ".join(filter(None, [it_c.get("calc_note") or it_c.get("resolved_spec", {}).get("note_std") for it_c in its_c]))
                                                if n_val:
                                                    ws_cust.cell(r_c, note_col, value=n_val)

                            if sum_vat_row:
                                ws_cust.cell(sum_vat_row, t_col, value=f"=SUM({col_t_let}{first_data_r}:{col_t_let}{last_data_r})").number_format = "#,##0"
                                for r_chk in range(sum_vat_row + 1, min(sum_vat_row + 10, ws_cust.max_row + 1)):
                                    txt = str(ws_cust.cell(r_chk, 2).value or "").lower()
                                    if "vat(10%)" in txt or "vat (10%)" in txt or "vat 10%" in txt:
                                        ws_cust.cell(r_chk, t_col, value=f"={col_t_let}{sum_vat_row}*0.1").number_format = "#,##0"
                                    elif "vat(8%)" in txt or "vat (8%)" in txt or "vat 8%" in txt:
                                        orig_v8 = ws_cust.cell(r_chk, t_col).value
                                        if orig_v8 and str(orig_v8).strip() not in ("0", ""):
                                            ws_cust.cell(r_chk, t_col, value=f"={col_t_let}{sum_vat_row}*0.08").number_format = "#,##0"
                                        else:
                                            ws_cust.cell(r_chk, t_col, value=0).number_format = "#,##0"
                                    elif "tổng thanh toán" in txt or "tổng cộng thanh toán" in txt:
                                        ws_cust.cell(r_chk, t_col, value=f"=SUM({col_t_let}{sum_vat_row}:{col_t_let}{r_chk-1})").number_format = "#,##0"

                            cust_out = os.path.join(project_dir, f"{project_name}_BAO_GIA_FORM_KHACH.xlsx")
                            wb_cust.save(cust_out)
                            customer_files.append((f"{sh_name} (Form gốc khách hàng)", cust_out))
                            print(f"  -> File Báo giá điền trực tiếp trên Form gốc khách hàng: {cust_out}")
            except Exception as e:
                print(f"  [Cảnh báo] Không thể xuất form gốc khách hàng: {e}")

    print("=" * 75 + "\n")
    return customer_files


def run_master_pipeline(boq_file, sheet_names=None, interactive=True, auto_accept=False, dual_options=False, merge_sheets=False, only_cua_van=False, motor_brand=None, mfd_model=None):
    """
    Hàm điều phối Quy trình B: Nhận file BOQ khách hàng -> Phân tích & Áp giá từ Master Data có sẵn (Agent 01 -> Agent 08).
    """
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = os.path.basename(boq_file)
    project_name = base_name.replace("_BOQ_MEP (NCC).xlsx", "").replace(".xlsm", "").replace(".xlsx", "").replace(".xls", "").strip()
    if "CAND" in project_name.upper():
        project_name = "CAND"

    project_dir = resolve_path(f"data/projects/{project_name}")
    os.makedirs(project_dir, exist_ok=True)

    print("\n" + "=" * 75)
    print(f"🚀 SWIND BOQ ESTIMATION RUNNER (QUY TRÌNH B: AGENT 01..08) - PROJECT: {project_name.upper()}")
    print("=" * 75)
    print(f"  • File BOQ khách hàng: {boq_file}")
    print(f"  • Nguồn đơn giá & định mức: data/master_data/ (Master Data có sẵn - Không giải mã lại file chuẩn)")
    print(f"  • Thư mục dự án: {project_dir}")
    print(f"  • Chế độ báo giá van: {'2 Phương án (Đơn Cánh & Đa Cánh)' if dual_options else 'Báo giá chuẩn theo BOQ (Tiêu Chuẩn)'}")
    print(f"  • Chế độ tách Sheet: {'Gộp tất cả sheet' if merge_sheets else 'Tách riêng từng sheet ra file báo giá độc lập'}")
    print(f"  • Thời gian chạy: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # -------------------------------------------------------------
    # BƯỚC 1: AGENT 01 - BOQ EXTRACTOR & SPEC RESOLVER
    # -------------------------------------------------------------
    print("\n" + "-" * 60)
    print("[Agent 01 - BOQ Extractor] Quét cấu trúc BOQ và nhận diện Sheet kỹ thuật...")
    print("-" * 60)
    agent_01 = Agent01_BOQExtractor(boq_file=boq_file, project_name=project_name)
    target_sheets, all_items = agent_01.detect_and_parse(sheet_names=sheet_names)
    if motor_brand or mfd_model:
        for it in all_items:
            if motor_brand:
                it["motor_brand_override"] = str(motor_brand).strip().upper()
            if mfd_model:
                it["mfd_model_override"] = str(mfd_model).strip()
    print(f"  -> Các sheet được chọn xử lý: {target_sheets}")
    print(f"  -> Tổng số dòng sản phẩm bóc tách: {len(all_items)} dòng.")

    if not all_items:
        print("[LỖI] Không bóc tách được dòng sản phẩm nào từ các sheet trên. Dừng quy trình.")
        return

    if only_cua_van:
        print("\n" + "=" * 75)
        print("🎯 ÁP DỤNG RULE: CHỈ BÁO GIÁ CỬA GIÓ & VAN GIÓ (KHÔNG BÁO ỐNG GIÓ & HÀNG THƯƠNG MẠI)")
        print("=" * 75)
        all_items = [it for it in all_items if it.get("category") in ("CUA_GIO", "VAN_GIO")]
        print(f"  -> Số dòng sản phẩm sau khi lọc: {len(all_items)} dòng (chỉ Cửa gió & Van gió).")

    if not motor_brand and not mfd_model:
        print("  -> [Rule Mặc Định Cố Định] Các van động cơ chưa chỉ định hãng/mã trong BOQ sẽ tự động áp dụng: Mã MFD 1.02 - Động cơ BELIMO.")

    # -------------------------------------------------------------
    # BƯỚC 2: AGENT 02 (BOQ REVIEWER) & AGENT 03 (INPUT AUDITOR)
    # -------------------------------------------------------------
    print("\n" + "-" * 60)
    print("[Agent 02 - BOQ Reviewer] Rà soát phân loại mặt hàng & Học từ khóa ngữ nghĩa...")
    print("-" * 60)
    ambiguous_items = find_ambiguous_items(all_items)

    if ambiguous_items:
        if interactive:
            resolve_ambiguous_interactive(ambiguous_items, auto_accept_all=auto_accept)
        else:
            print(f"  -> [Non-Interactive Mode] Phát hiện {len(ambiguous_items)} mặt hàng lạ. Tạm gán nhóm mặc định.")
    else:
        print("  -> Tuyệt vời! 100% mặt hàng đã được nhận diện và phân nhóm chuẩn xác.")
    Agent03_InputAuditor(project_name=project_name).audit_parsed_boq_items(all_items)
    rep_src = os.path.join(project_dir, "INPUT_AUDIT_REPORT.json")
    rep_dst = os.path.join(project_dir, "internal_estimation", "INPUT_AUDIT_REPORT.json")
    if os.path.exists(rep_src):
        os.makedirs(os.path.join(project_dir, "internal_estimation"), exist_ok=True)
        import shutil
        shutil.move(rep_src, rep_dst)

    # -------------------------------------------------------------
    # BƯỚC 3: NẠP MASTER DATA & THỰC HIỆN DỰ TOÁN THEO RULE
    # -------------------------------------------------------------
    tech_records, price_records, acc_rules, subtype_rules, fin_policy = load_master_data()

    generated_files = []

    if len(target_sheets) > 1 and not merge_sheets:
        print("\n" + "=" * 75)
        print(f"📋 PHÁT HIỆN {len(target_sheets)} SHEET KỸ THUẬT -> ÁP DỤNG RULE: TÁCH RIÊNG TỪNG FILE DỰ TOÁN")
        print("=" * 75)
        for s_idx, sh_name in enumerate(target_sheets, 1):
            sh_items = [it for it in all_items if it.get("source_sheet") == sh_name]
            if not sh_items:
                print(f"  -> [{s_idx}/{len(target_sheets)}] Sheet '{sh_name}': Không có dòng sản phẩm hợp lệ, bỏ qua.")
                continue

            internal_dir = os.path.join(project_dir, "internal_estimation")
            os.makedirs(internal_dir, exist_ok=True)
            sh_slug = vietnamese_slugify(sh_name, max_len=30, add_hash=False).replace('-', '_')
            sh_output = os.path.join(internal_dir, f"{project_name}_{sh_slug}_ESTIMATION.xlsx")
            sh_qa = os.path.join(internal_dir, f"QA_Audit_Report_{sh_slug}.json")

            print(f"\n[{s_idx}/{len(target_sheets)}] 🚀 BẮT ĐẦU XỬ LÝ SHEET: '{sh_name}' ({len(sh_items)} dòng BOQ)")
            print(f"       -> File xuất: {sh_output}")

            process_single_sheet_estimation(
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
                template_wb=agent_01.parser.wb
            )
            generated_files.append((sh_name, sh_output))
    else:
        # Xử lý 1 sheet hoặc gộp tất cả sheet theo yêu cầu --merge-sheets
        primary_sheet = target_sheets[0] if target_sheets else None
        internal_dir = os.path.join(project_dir, "internal_estimation")
        os.makedirs(internal_dir, exist_ok=True)
        output_workbook = os.path.join(internal_dir, f"{project_name}_ESTIMATION.xlsx")
        qa_report_path = os.path.join(internal_dir, f"QA_Audit_Report.json")

        process_single_sheet_estimation(
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
            template_wb=agent_01.parser.wb
        )
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
        template_wb=agent_01.parser.wb
    )

    print("\n" + "=" * 75)
    print("🎉 TỔNG KẾT CÁC FILE BÁO GIÁ GỬI KHÁCH HÀNG (CHỈ CHỨA DUY NHẤT BẢNG BOQ GỐC):")
    for sh_name, sh_out in customer_files:
        print(f"  • Sheet '{sh_name}': {sh_out}")
    print("=" * 75 + "\n")


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

    args = parser.parse_args()

    boq_path = args.boq_file
    if not boq_path:
        boq_path = select_input_file()
    else:
        boq_path = resolve_path(boq_path)
        if not os.path.exists(boq_path):
            print(f"[LỖI] Không tìm thấy file: {boq_path}")
            sys.exit(1)

    sheets = args.sheets.split(",") if args.sheets else None
    interactive = not args.non_interactive

    run_master_pipeline(
        boq_file=boq_path,
        sheet_names=sheets,
        interactive=interactive,
        auto_accept=args.auto_accept,
        dual_options=args.dual_options,
        merge_sheets=args.merge_sheets,
        only_cua_van=args.only_cua_van,
        motor_brand=args.motor_brand,
        mfd_model=args.mfd_model
    )


if __name__ == "__main__":
    main()
