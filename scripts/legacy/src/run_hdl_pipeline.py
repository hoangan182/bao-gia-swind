import json
import os
from swind_excel_builder import SwindExcelBuilder
from swind_bom_engine import SwindBOMEngine
from swind_checker import SwindChecker

BOQ_CLEAN_JSON = "data/projects/Du_An_HDL_A1/JSON_BOQ_Clean.json"
MASTER_DATA_TECH_JSON = "data/master_data/master_database_tech.json"
MASTER_DATA_PRICE_JSON = "data/master_data/master_database_price.json"
OUTPUT_WORKBOOK = "data/projects/Du_An_HDL_A1/HDL_A1_ESTIMATION.xlsx"

def load_master_data():
    with open(MASTER_DATA_TECH_JSON, 'r', encoding='utf-8') as f:
        tech = json.load(f)
    with open(MASTER_DATA_PRICE_JSON, 'r', encoding='utf-8') as f:
        price = json.load(f)
    return tech, price

def run_pipeline():
    print("=" * 70)
    print("SWIND MULTI-AGENT ESTIMATION PIPELINE (HDL A1)")
    print("=" * 70)
    
    # 1. ORCHESTRATOR
    builder = SwindExcelBuilder(OUTPUT_WORKBOOK)
    tech_records, price_records = load_master_data()
    
    for idx, item in enumerate(tech_records, 1):
        barem = item.get("Weight_kg_m") or item.get("Density_kg_m2") or ""
        barem_str = f"{barem} kg/m" if item.get("Weight_kg_m") else f"{barem} kg/m2" if item.get("Density_kg_m2") else ""
        builder.add_tech_master_data(idx=idx, mat_id=item["MAT_ID"], category=item["Category"], name=item["Name"], unit=item["Unit"], barem=barem_str, source_trace=item["Source_Trace"])
    tech_map = {item["MAT_ID"]: item for item in tech_records}
    for idx, item in enumerate(price_records, 1):
        t_info = tech_map.get(item["MAT_ID"], {})
        builder.add_price_master_data(idx=idx, mat_id=item["MAT_ID"], name=item.get("Name") or t_info.get("Name", ""), category=item.get("Category") or t_info.get("Category", "THUONG_MAI"), price=item["Price"])

    # 2. MAKER (Agent 1)
    print("\n[Agent 1 - Maker] Bắt đầu quét BOQ và bóc tách định mức chi tiết...")
    with open(BOQ_CLEAN_JSON, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    items = data.get("items", [])
    for item_counter, item in enumerate(items, 1):
        cat = item["category"]
        name = item["raw_text"]
        unit = item["unit"]
        qty = item["qty"]
        w = item.get("w", 0) or 0
        h = item.get("h", 0) or 0
        l = item.get("l", 0) or 0
        thk = 0.75 # Default
        
        if cat == "ONG_GIO":
            prefix, group_name = "SW-DUCT", "ỐNG GIÓ"
            size_str = f"{thk:.2f}mm"
        elif cat == "VAN_GIO":
            prefix, group_name = "SW-DAMPER", "VAN GIÓ"
            size_str = f"{int(w)}x{int(h)}" if w > 0 and h > 0 else f"D{w}" if w > 0 else "-"
        else:
            prefix, group_name = "SW-DIFF", "CỬA GIÓ"
            size_str = f"{int(w)}x{int(h)}" if w > 0 and h > 0 else "-"
            
        item_id = f"{prefix}-{item_counter:03d}"
        builder.add_boq_summary_row(stt=item_counter, item_id=item_id, group=group_name, name=name, size=size_str, unit=unit, qty=qty, margin=0.18)
        
        if cat == "VAN_GIO":
            damper_type = "FD" if "FD" in item.get("product_code", "") else "VCD"
            bom = SwindBOMEngine.calculate_damper_bom(parent_id=item_id, damper_type=damper_type, w=w if w > 0 else 300, h=h if h > 0 else 300, brand="PN")
            for comp in bom["components"]:
                builder.add_subsheet_component(sheet_type="VAN", sub_key=comp["sub_key"], parent_id=item_id, comp_name=comp["name"], category=comp["category"], mat_id=comp["mat_id"], unit=comp["unit"], calc_qty_per_item=comp["calc_qty"], note=comp.get("note", ""))
        elif cat == "CUA_GIO":
            profile_type = "T" if "nan T" in name else "Z" if "louver" in name.lower() else "BD"
            bom = SwindBOMEngine.calculate_diffuser_bom(parent_id=item_id, diffuser_type="DIFFUSER", w=w if w > 0 else 300, h=h if h > 0 else 300, profile_type=profile_type)
            for comp in bom["components"]:
                builder.add_subsheet_component(sheet_type="CUA", sub_key=comp["sub_key"], parent_id=item_id, comp_name=comp["name"], category=comp["category"], mat_id=comp["mat_id"], unit=comp["unit"], calc_qty_per_item=comp["calc_qty"], note=comp.get("note", ""))
                
    builder.save()

    # 3. CHECKER (Agent 2)
    print("\n[Agent 2 - Checker] Kích hoạt kiểm toán độc lập trên Workbook...")
    checker = SwindChecker(OUTPUT_WORKBOOK)
    report = checker.run_full_audit()
    
    with open("data/projects/Du_An_HDL_A1/QA_Audit_Report.json", "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=4)
        
    print(f"  -> Trạng thái kiểm toán: {report['qa_status']}")
    print(f"  -> Số hạng mục: {report['total_items_audited']}")
    if report["issues"]:
        print("  -> DANH SÁCH LỖI:")
        for issue in report["issues"]:
            print(f"     [{issue['severity']}] {issue['sheet']} (Row {issue['row']}): {issue['message']}")

if __name__ == "__main__":
    run_pipeline()
