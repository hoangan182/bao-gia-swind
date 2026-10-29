#!/usr/bin/env python3
"""
Swind Single-Item Formula Inspector & Regression Tester (`swind_item_inspector.py`).
Dùng để:
  1. Kiểm tra tức thì (0.05s) cách bóc tách kích thước, phân loại, công thức diện tích S (m2),
     chia modul, BOM và đơn giá bán của 1 hoặc nhiều dòng mô tả vật tư bất kỳ mà không cần chạy cả file Excel.
  2. Chạy bộ Regression Test (--self-test / --save-baseline) cho 52 mặt hàng đại diện tất cả
     các nhóm công thức của Swind (Ống vuông, Ống tròn, Phụ kiện, Tiêu âm, Canvas, Ống mềm,
     Van gió VCD/NRD/PRD/OBD/FD/MD/MFD Belimo-KLB-Honeywell, Cửa gió nhôm định hình)
     để đảm bảo độ chính xác 100% khi kiểm tra hoặc chỉnh sửa công thức.

Cách dùng:
  ./venv/bin/python src/swind_item_inspector.py "Côn thu 400x200/250x150 L=300"
  ./venv/bin/python src/swind_item_inspector.py "Van MFD EI90 600x400" --motor-brand KLB
  ./venv/bin/python src/swind_item_inspector.py --self-test
"""
import argparse
import contextlib
import io
import json
import math
import os
import sys
import openpyxl

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

from swind_boq_parser import SwindBOQParser
from swind_utils import get_subtype_rules, get_master_price_map
from agent_01_boq_extractor import Agent01_BOQExtractor
from agent_04_bom_duct import Agent04_DuctworkBOM
from agent_05_bom_damper import Agent05_DamperBOM
from agent_06_bom_diffuser import Agent06_DiffuserBOM


BASELINE_PATH = os.path.join(PROJECT_ROOT, "data", "master_data", "formula_regression_baseline.json")

SELF_TEST_CASES = [
    # 1. Ống gió vuông & Phụ kiện vuông (Agent 04 - BG PKV)
    {"name": "Ống gió tôn mạ kẽm 500x300 dày 0.58mm", "unit": "m"},
    {"name": "Ống gió vuông 800x400xL1110", "unit": "cái"},
    {"name": "Ống gió vuông 1200x600 nẹp C", "unit": "m2"},
    {"name": "Côn thu vuông 600x400/400x300 L=500", "unit": "cái"},
    {"name": "Chân rẽ 400x200/300x150 L=300", "unit": "cái"},
    {"name": "Côn thu vuông tròn 400x200/D200 L=300", "unit": "cái"},
    {"name": "Cút vuông 90 độ 500x300 R=250", "unit": "cái"},
    {"name": "Cút vuông 45 độ 400x200", "unit": "cái"},
    {"name": "Zét lượn 400x200 L=600 E=200", "unit": "cái"},
    {"name": "Chạc 3 Y vuông 500x300/300x300", "unit": "cái"},
    {"name": "Tê vuông 600x300/400x200", "unit": "cái"},
    {"name": "Bịt đầu ống gió 400x200", "unit": "cái"},
    {"name": "Hộp gió 600x600xL300 (1 cổ D200)", "unit": "cái"},
    {"name": "Hộp gió 600x600xL300 có bảo ôn (2 cổ D150)", "unit": "cái"},
    # 2. Ống gió tròn & Phụ kiện tròn (Agent 04 - TINH VT PK TRON / BG PKT)
    {"name": "Ống gió tròn xoắn D300", "unit": "m"},
    {"name": "Măng xông ống tròn D250", "unit": "cái"},
    {"name": "Cút tròn 90 độ D300", "unit": "cái"},
    {"name": "Cút tròn 45 độ D250", "unit": "cái"},
    {"name": "Côn thu tròn D300/D200", "unit": "cái"},
    {"name": "Tê tròn D300/D200", "unit": "cái"},
    {"name": "Chạc Y tròn D300/D200", "unit": "cái"},
    {"name": "Chân rẽ tròn D200", "unit": "cái"},
    {"name": "Bịt đầu ống tròn D200", "unit": "cái"},
    # 3. Canvas, Ventcap, Ống mềm, Tiêu âm (Agent 04)
    {"name": "Chụp thông hơi Inox 304 DN200 kèm lưới chắn côn trùng", "unit": "cái"},
    {"name": "Khớp nối mềm Canvas 500x300", "unit": "cái"},
    {"name": "Khớp nối mềm chống cháy đầu quạt 600x400 2 đầu bích", "unit": "cái"},
    {"name": "Ống gió mềm có bảo ôn D200", "unit": "m"},
    {"name": "Ống gió mềm không bảo ôn D150", "unit": "ống"},
    {"name": "Hộp tiêu âm ống gió vuông 600x400xL1000", "unit": "cái"},
    {"name": "Tiêu âm ống tròn D300xL1000", "unit": "cái"},
    # 4. Van gió & Van PCCC EI (Agent 05 - BG VAN Swind)
    {"name": "Van điều chỉnh lưu lượng VCD 400x200", "unit": "cái"},
    {"name": "Van VCD tay vặn trục vít 800x500", "unit": "cái"},
    {"name": "Van một chiều NRD 500x300", "unit": "cái"},
    {"name": "Van xả áp PRD 600x400", "unit": "cái"},
    {"name": "Van chặn lửa cầu chì FD 400x200", "unit": "cái"},
    {"name": "Van chặn lửa cầu chì FD EI120 600x400", "unit": "cái"},
    {"name": "Van chặn lửa động cơ MFD EI90 600x400", "unit": "cái"},
    {"name": "Van chặn lửa động cơ MFD EI120 1800x1000", "unit": "cái", "mfd_model": "1.05"},
    {"name": "Van chặn lửa động cơ MFD EI90 1200x400", "unit": "cái", "motor_brand": "KLB"},
    {"name": "Van chặn lửa động cơ MFD EI60 800x500", "unit": "cái", "motor_brand": "HONEYWELL"},
    {"name": "Van gió động cơ MD 500x300", "unit": "cái"},
    {"name": "Van gió động cơ MD 2000x1000", "unit": "cái", "motor_brand": "KLB"},
    {"name": "Van gió động cơ MD 1000x600", "unit": "cái", "motor_brand": "HONEYWELL"},
    {"name": "Van VCD D200", "unit": "cái"},
    {"name": "Van OBD 400x200", "unit": "cái"},
    # 5. Cửa gió nhôm định hình (Agent 06 - BG Cửa Swind)
    {"name": "Cửa gió cấp nan bầu dục 1 lớp 600x300 kèm OBD", "unit": "cái"},
    {"name": "Cửa gió hồi 600x400 kèm lọc bụi G4", "unit": "cái"},
    {"name": "Cửa gió khuếch tán 600x600 (cổ 450x450) kèm OBD", "unit": "cái"},
    {"name": "Cửa gió Louver nan Z ngoài trời 800x600 kèm lưới chắn côn trùng", "unit": "cái"},
    {"name": "Cửa gió sọt trứng 600x600", "unit": "cái"},
    {"name": "Cửa gió Linear SLB 1000x150", "unit": "cái"},
    {"name": "Cửa kiểm tra ống gió 400x300", "unit": "cái"},
    {"name": "Lưới chắn côn trùng Inox 304 500x300", "unit": "cái"},
]


DUCT_METHOD_MAP = {
    "VENTCAP": "_calc_ventcap_item (L274-288)",
    "CANVAS_SQ": "_calc_canvas_item (L291-338)",
    "CANVAS_RT": "_calc_canvas_item (L291-338)",
    "FLEX_DUCT": "_calc_flex_duct_item (L341-360)",
    "SILENCER_SQ": "_calc_silencer_item (L363-452)",
    "SILENCER_RT": "_calc_silencer_item (L363-452)",
    "DUCT_M2": "_calc_m2_duct_or_fitting_item (L455-475)",
    "FITTING_M2": "_calc_m2_duct_or_fitting_item (L455-475)",
    "SPIRAL_DUCT": "_calc_round_duct_or_fitting_item (L478-612)",
    "COUPLING_RT": "_calc_round_duct_or_fitting_item (L478-612)",
    "ELBOW_RT": "_calc_round_duct_or_fitting_item (L478-612)",
    "REDUCER_RT": "_calc_round_duct_or_fitting_item (L478-612)",
    "TEE_RT": "_calc_round_duct_or_fitting_item (L478-612)",
    "WYE_RT": "_calc_round_duct_or_fitting_item (L478-612)",
    "TAKEOFF_RT": "_calc_round_duct_or_fitting_item (L478-612)",
    "END_CAP_RT": "_calc_round_duct_or_fitting_item (L478-612)",
    "DUCT_RECT": "_calc_rect_duct (L615-637)",
    "REDUCER_SQ": "_calc_rect_reducer (L640-665)",
    "SHOE_TAP": "_calc_rect_shoe_tap (L668-694)",
    "SQUARE_TO_ROUND": "_calc_square_to_round (L697-719)",
    "ELBOW_SQ": "_calc_rect_elbow (L722-763)",
    "OFFSET_Z": "_calc_rect_offset_z (L766-790)",
    "WYE_SQ": "_calc_rect_wye (L793-808)",
    "TEE_SQ": "_calc_rect_tee (L811-827)",
    "END_CAP_SQ": "_calc_rect_end_cap (L830-850)",
    "PLENUM_BOX": "_calc_plenum_box (L853-871)",
}

DIFFUSER_METHOD_MAP = {
    "LCCT": "_calc_profile_lcct (L92-107)",
    "FILTER_G4": "_calc_profile_filter_g4 (L110-125)",
    "Z": "_calc_profile_louver_z (L128-200)",
    "ECG": "_calc_profile_eggcrate (L203-264)",
    "SLB": "_calc_profile_linear_slb (L267-338)",
    "SLD": "_calc_profile_slot_sld (L341-415)",
    "T": "_calc_profile_diffuser_t (L418-474)",
    "BD": "_calc_profile_oval_bd (L477-554)",
}


def _get_fin_rates(category, fin_policy):
    comm_cats = fin_policy.get("COMMERCIAL", {}).get("categories", ["THUONG_MAI", "ONG_MEM", "KHAC"])
    mfg_cats = fin_policy.get("MANUFACTURING", {}).get("categories", ["ONG_GIO", "CUA_GIO", "VAN_GIO", "CANVAS", "TIEU_AM"])
    if category in comm_cats:
        cfg = fin_policy.get("COMMERCIAL", {})
        return cfg.get("labor_rate", 0.0), cfg.get("overhead_rate", 0.02), cfg.get("margin", 0.10)
    elif category in mfg_cats:
        cfg = fin_policy.get("MANUFACTURING", {})
        return cfg.get("labor_rate", 0.25), cfg.get("overhead_rate", 0.10), cfg.get("margin", 0.18)
    cfg = fin_policy.get("COMMERCIAL", {})
    return cfg.get("labor_rate", 0.0), cfg.get("overhead_rate", 0.02), cfg.get("margin", 0.10)


def inspect_single_item(raw_text, unit="cái", note="", motor_brand=None, mfd_model=None, formula_mode=None, include_box=False):
    """
    Chạy chuẩn xác qua toàn bộ chuỗi xử lý của Swind cho 1 dòng mô tả vật tư:
    SwindBOQParser -> Agent01_BOQExtractor -> Agent04/05/06 -> Tính giá bán.
    """
    return inspect_batch_items(
        [{"name": raw_text, "unit": unit, "note": note, "motor_brand": motor_brand, "mfd_model": mfd_model}],
        formula_mode=formula_mode,
        include_box=include_box
    )


def inspect_batch_items(cases, formula_mode=None, include_box=False):
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "BOQ"
    ws.append(["STT", "Mô tả vật tư", "ĐVT", "Khối lượng", "Đơn giá", "Thành tiền", "Ghi chú"])
    for i, c in enumerate(cases, 1):
        ws.append([i, c["name"], c.get("unit", "cái"), 1, None, None, c.get("note", "")])

    with contextlib.redirect_stdout(io.StringIO()):
        parser = SwindBOQParser(":memory:", wb=wb, include_flex_duct=True)
        items = parser.parse_sheet("BOQ")
    if not items:
        return []

    subtype_rules = get_subtype_rules()
    price_map = get_master_price_map()
    fin_path = os.path.join(PROJECT_ROOT, "data", "master_data", "financial_policy.json")
    with open(fin_path, "r", encoding="utf-8") as f:
        fin_policy = json.load(f)

    results = []
    for idx, item in enumerate(items, 1):
        case_cfg = cases[idx - 1] if (idx - 1) < len(cases) else {}
        if case_cfg.get("motor_brand"):
            item["motor_brand_override"] = case_cfg["motor_brand"]
        if case_cfg.get("mfd_model"):
            item["mfd_model_override"] = case_cfg["mfd_model"]
        if formula_mode:
            item["duct_formula_mode"] = formula_mode
        if include_box or case_cfg.get("include_box"):
            item["include_box"] = True
        for dim_k in ("w", "h", "l", "d", "thickness"):
            if case_cfg.get(dim_k) and not item.get(dim_k):
                item[dim_k] = case_cfg[dim_k]

        results.append(
            _evaluate_parsed_item_in_ram(item, idx, subtype_rules, price_map, fin_policy, include_box=include_box or bool(case_cfg.get("include_box")))
        )

    return results


def _evaluate_parsed_item_in_ram(
    item,
    idx,
    subtype_rules,
    price_map,
    fin_policy,
    include_box=False,
):
    if include_box:
        item["include_box"] = True
    spec = Agent01_BOQExtractor.resolve_item_spec(item, subtype_rules, price_map=price_map, idx=idx)
    cat = item["category"]
    w = item["w"]
    h = item["h"]
    l = item["l"]
    d = item.get("d", 0)
    thk = item["thickness"]
    item_id = f"INSP-{idx:03d}"

    components = []
    formula_trace = ""
    area_m2 = 0.0
    code_location = ""

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
            unit=item["unit"],
            specified_thickness=thk,
            d=d,
            subtype=sub_t,
            item=item
        )
        components.extend(bom["components"])
        duct_calc = item.get("duct_calc") or {}
        formula_trace = duct_calc.get("trace", "")
        area_m2 = float(duct_calc.get("area_m2") or bom.get("area_m2") or 0.0)
        m_loc = DUCT_METHOD_MAP.get(sub_t, f"calculate_duct_item (subtype={sub_t})")
        code_location = f"src/agent_04_bom_duct.py :: Agent04_DuctworkBOM.{m_loc}"
        if spec.get("has_mesh"):
            w_m = w if w > 0 else (d if d > 0 else 300)
            h_m = h if h > 0 else (d if d > 0 else 300)
            lcct_bom = Agent06_DiffuserBOM.calculate_diffuser_bom(f"{item_id}-LCCT", "LCCT", w_m, h_m, profile_type="LCCT")
            components.extend(lcct_bom["components"])
        if spec.get("has_filter"):
            w_f = w if w > 0 else (d if d > 0 else 300)
            h_f = h if h > 0 else (d if d > 0 else 300)
            flt_bom = Agent06_DiffuserBOM.calculate_diffuser_bom(f"{item_id}-G4", "FILTER_G4", w_f, h_f, profile_type="FILTER_G4")
            components.extend(flt_bom["components"])

    elif cat == "CANVAS":
        bom = Agent04_DuctworkBOM.calculate_canvas_bom(
            parent_id=item_id, w=w, h=h, l=l if l > 0 else 200, d=d,
            raw_name=f"{item.get('raw_name', '')} {item.get('note_boq', '')}".strip(),
            unit=item["unit"], item=item
        )
        components.extend(bom["components"])
        duct_calc = item.get("duct_calc") or {}
        formula_trace = duct_calc.get("trace", "")
        area_m2 = float(duct_calc.get("area_m2") or 0.0)
        m_loc = DUCT_METHOD_MAP.get(spec.get("subtype"), "_calc_canvas_item")
        code_location = f"src/agent_04_bom_duct.py :: Agent04_DuctworkBOM.{m_loc}"

    elif cat == "TIEU_AM":
        bom = Agent04_DuctworkBOM.calculate_acoustic_partition_bom(
            parent_id=item_id, w=w if w > 0 else 1000, h=h if h > 0 else 1000, l=l if l > 0 else 1000,
            unit=item["unit"], include_casing=("tiêu âm trong" not in item.get("raw_name", "").lower()),
            d=d, raw_name=f"{item.get('raw_name', '')} {item.get('note_boq', '')}".strip(), item=item
        )
        components.extend(bom["components"])
        duct_calc = item.get("duct_calc") or {}
        formula_trace = duct_calc.get("trace", "")
        area_m2 = float(duct_calc.get("area_m2") or bom.get("area_m2") or 0.0)
        m_loc = DUCT_METHOD_MAP.get(spec.get("subtype"), "_calc_silencer_item")
        code_location = f"src/agent_04_bom_duct.py :: Agent04_DuctworkBOM.{m_loc}"

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
            d=d,
            raw_name=f"{item.get('raw_name', '')} {item.get('note_boq', '')}".strip()
        )
        components.extend(bom["components"])
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
            components.extend(sec_bom["components"])
        if damper_type == "MFD_LOUVER":
            louver_bom = Agent06_DiffuserBOM.calculate_diffuser_bom(
                parent_id=f"{item_id}-LV",
                diffuser_type="LOUVER",
                w=w if w > 0 else 1000,
                h=h if h > 0 else 1000,
                profile_type="Z",
                has_mesh=True
            )
            components.extend(louver_bom["components"])
        formula_trace = " | ".join(c.get("note", "") for c in components if c.get("note"))
        if damper_type in ("OBD", "SOBD"):
            dmp_fn = "_calc_obd_damper (L124-181)"
        elif d > 0:
            dmp_fn = "_price_round_damper (L531-562)"
        elif damper_type in ("MFD", "MFSD", "MSFD", "MFD_LOUVER") or (damper_type == "FD" and (ei_rating > 0 or str(m_code or "") == "2.01")):
            dmp_fn = "_price_fire_damper_ei_or_mfd (L565-585)"
        elif damper_type == "FD":
            dmp_fn = "_price_normal_fd_damper (L588-603)"
        else:
            dmp_fn = "_price_square_standard_damper (L606-637)"
        code_location = f"src/agent_05_bom_damper.py :: Agent05_DamperBOM.{dmp_fn}"

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
        components.extend(bom["components"])
        combo_dmps = item.get("combo_dampers") or ([item["combo_damper"]] if item.get("combo_damper") else [])
        if combo_dmps:
            w_dmp = float(item.get("w_damper") or w or 300)
            h_dmp = float(item.get("h_damper") or h or 300)
            d_dmp = float(item.get("d_damper") or 0)
            for d_idx, c_dmp in enumerate(combo_dmps):
                dmp_bom = Agent05_DamperBOM.calculate_damper_bom(
                    parent_id=f"{item_id}-{c_dmp}" if d_idx == 0 else f"{item_id}-{c_dmp}{d_idx}",
                    damper_type=c_dmp, w=w_dmp, h=h_dmp, brand="PN",
                    ei_rating=item.get("ei_rating", 0) if d_idx == 0 else 0,
                    model_code=spec.get("model_code") if d_idx == 0 else None,
                    motor_brand=spec.get("motor_brand", "BELIMO"), d=d_dmp
                )
                components.extend(dmp_bom["components"])
        formula_trace = f"Profile={spec['subtype']}, Phủ bì={int(w)}x{int(h)}, Cổ={spec.get('b1')}x{spec.get('b2')}, OBD={spec['has_obd']}, Mesh={spec['has_mesh']}, Filter={spec['has_filter']}"
        diff_fn = DIFFUSER_METHOD_MAP.get(spec["subtype"], "_calc_profile_oval_bd")
        code_location = f"src/agent_06_bom_diffuser.py :: Agent06_DiffuserBOM.{diff_fn}"
        if include_box and spec.get("is_box_combo") and spec.get("box_spec"):
            bs = spec["box_spec"]
            box_synth = {
                "raw_name": f"Hộp gió {int(bs['w_box'])}x{int(bs['h_box'])}xL{int(bs['l_box'])}" + (f" ({bs['n_necks']} cổ D{int(bs['d_box'])})" if bs.get("n_necks", 0) > 0 else ""),
                "w": bs["w_box"],
                "h": bs["h_box"],
                "d": bs.get("d_box", 0.0),
                "l": bs["l_box"],
                "thickness": bs["thk_box"],
                "neck_count": bs.get("n_necks", 0),
                "is_insulated": bs.get("is_insulated", False),
                "unit": "cái",
            }
            box_bom = Agent04_DuctworkBOM.calculate_duct_bom(
                parent_id=f"{item_id}-BOX",
                w=float(bs.get("w_box") or w or 300),
                h=float(bs.get("h_box") or h or 300),
                l=float(bs.get("l_box") or 300),
                brand="HOASEN",
                flange_type="TDC",
                is_fitting=True,
                unit="cái",
                specified_thickness=float(bs.get("thk_box") or 0.58),
                d=float(bs.get("d_box") or 0),
                subtype="PLENUM_BOX",
                item=box_synth,
            )
            components.extend(box_bom["components"])
            area_m2 = float(bs.get("area_m2") or 0.0)
            formula_trace += f" | +Hộp gió ({bs.get('spec_label')}): {bs.get('trace')}"
            code_location += " + src/agent_04_bom_duct.py :: Agent04_DuctworkBOM._calc_plenum_box"

    elif cat in ("ONG_MEM", "THUONG_MAI", "KHAC"):
        l_rate, o_rate, mg_rate = _get_fin_rates(cat, fin_policy)
        comm_markup = (1.0 + o_rate + l_rate) * (1.0 + mg_rate)
        if cat == "ONG_MEM" and spec.get("dia_val"):
            nearest_d = min((100, 150, 200, 250, 300, 350, 400), key=lambda k: abs(k - int(spec["dia_val"])))
            mat_id = f"FLEX_DUCT_D{nearest_d}_{spec['subtype']}"
            base_factor = 0.125 if item["unit"].lower() in ["m", "md", "mét", "met"] else 1.0
            calc_qty_per_item = base_factor / comm_markup if comm_markup > 0 else base_factor
            components.append({
                "sub_key": f"{item_id}-TM",
                "name": item["name"],
                "category": cat,
                "mat_id": mat_id,
                "unit": "ống",
                "calc_qty": calc_qty_per_item,
                "note": "Ống mềm quy đổi chuẩn 8m/ống"
            })
        formula_trace = (item.get("duct_calc") or {}).get("trace", "Hàng thương mại / Ống mềm")
        code_location = f"src/agent_04_bom_duct.py & src/swind_master_runner.py (cat={cat})"

    # Tính giá bán cuối cùng giống hệt swind_master_runner.py
    m_cost = 0.0
    mot_cost = 0.0
    comp_details = []
    for c in components:
        m_id = c["mat_id"]
        p = price_map.get(m_id, 0.0) or c.get("ref_price", 0.0)
        cost = c["calc_qty"] * p
        m_cost += cost
        if c.get("category") == "ĐỘNG_CƠ_VÀ_CẢM_BIẾN":
            mot_cost += cost
        comp_details.append({
            "mat_id": m_id,
            "name": c["name"],
            "unit": c["unit"],
            "calc_qty": round(c["calc_qty"], 6),
            "mat_price": p,
            "raw_cost": round(cost, 2)
        })

    l_rate, o_rate, mg_rate = _get_fin_rates(cat, fin_policy)
    l_cost = (m_cost - mot_cost) * l_rate
    o_cost = (m_cost - mot_cost) * o_rate
    raw_sell_unit = math.floor(((m_cost + l_cost + o_cost - mot_cost) * (1 + mg_rate) + mot_cost) + 0.5)
    sell_unit = int(math.ceil(raw_sell_unit / 100.0) * 100) if raw_sell_unit > 0 else 0

    raw_name_s = item.get("raw_name") or item.get("name") or ""
    is_box_combo = spec.get("is_box_combo") or item.get("is_box_combo") or (
        any(k in raw_name_s.lower() for k in ("kèm hộp gió", "kèm hộp", "kèm box", "có hộp gió", "gắn hộp gió"))
        and any(k in raw_name_s.lower() for k in ("cửa gió", "miệng gió", "cửa cấp", "miệng cấp", "cửa hồi", "miệng hồi"))
    )
    p_ref = float(item.get("ref_price") or 0)
    has_standalone_cv_ref = bool(item.get("_has_standalone_cv_ref"))
    price_source = "SWIND_CALC"
    effective_sell_unit = int(sell_unit)
    if p_ref > 0:
        if is_box_combo and cat == "CUA_GIO":
            if include_box:
                effective_sell_unit = int(sell_unit)
                price_source = "SWIND_CALC_WITH_BOX"
            elif not has_standalone_cv_ref:
                box_add = int(math.ceil(p_ref / 100.0) * 100)
                effective_sell_unit = int(sell_unit) + box_add
                price_source = "BOX_PARTNER_PLUS_SWIND"
        elif cat not in ("CUA_GIO", "VAN_GIO") and (not has_standalone_cv_ref or cat in ("THUONG_MAI", "KHAC")):
            effective_sell_unit = int(round(p_ref))
            price_source = "PARTNER_KEPT"

    return {
        "input_text": raw_name_s,
        "section": item.get("section", ""),
        "note_boq": item.get("note_boq", ""),
        "source_row": item.get("source_row", 0),
        "qty": float(item.get("qty") or 0),
        "unit": item["unit"],
        "category": cat,
        "subtype": spec.get("subtype"),
        "model_std": spec.get("model_std"),
        "motor_brand": spec.get("motor_brand"),
        "a1": spec.get("a1"),
        "a2": spec.get("a2"),
        "b1": spec.get("b1"),
        "b2": spec.get("b2"),
        "modul": spec.get("modul"),
        "l_col": spec.get("l_col"),
        "thk_col": spec.get("thk_col"),
        "area_m2": round(area_m2, 4),
        "sell_unit_price": int(sell_unit),
        "effective_sell_unit": int(effective_sell_unit),
        "ref_price": int(round(p_ref)) if p_ref > 0 else 0,
        "price_source": price_source,
        "note_std": spec.get("note_std"),
        "formula_trace": formula_trace,
        "code_location": code_location,
        "components": comp_details
    }


def run_self_test(save_baseline=False):
    all_snapshots = []
    res_list = inspect_batch_items(SELF_TEST_CASES)
    for r in res_list:
        all_snapshots.append({
            "input_text": r["input_text"],
            "unit": r["unit"],
            "category": r["category"],
            "subtype": r["subtype"],
            "model_std": r["model_std"],
            "a1": r["a1"],
            "a2": r["a2"],
            "b1": r["b1"],
            "b2": r["b2"],
            "modul": r["modul"],
            "l_col": r["l_col"],
            "thk_col": r["thk_col"],
            "area_m2": r["area_m2"],
            "sell_unit_price": r["sell_unit_price"],
        })

    if save_baseline or not os.path.exists(BASELINE_PATH):
        os.makedirs(os.path.dirname(BASELINE_PATH), exist_ok=True)
        with open(BASELINE_PATH, "w", encoding="utf-8") as f:
            json.dump(all_snapshots, f, ensure_ascii=False, indent=2)
        print(f"✅ Đã lưu baseline gồm {len(all_snapshots)} test cases tại: {BASELINE_PATH}")
        return True

    with open(BASELINE_PATH, "r", encoding="utf-8") as f:
        baseline = json.load(f)

    if len(all_snapshots) != len(baseline):
        print(f"❌ LỆCH SỐ LƯỢNG TEST CASES: Hiện tại={len(all_snapshots)}, Baseline={len(baseline)}")
        return False

    mismatches = []
    for idx, (cur, base) in enumerate(zip(all_snapshots, baseline), 1):
        for k in base.keys():
            if cur.get(k) != base.get(k):
                mismatches.append((idx, cur["input_text"], k, base.get(k), cur.get(k)))

    if mismatches:
        print(f"❌ PHÁT HIỆN {len(mismatches)} SAI LỆCH SO VỚI BASELINE:")
        for idx, name, field, expected, actual in mismatches:
            print(f"  - Case #{idx} [{name}] trường '{field}': Chuẩn={expected!r} != Mới={actual!r}")
        return False

    print(f"✅ REGRESSION TEST PASSED 100% ({len(all_snapshots)}/{len(baseline)} mặt hàng chuẩn Swind khớp tuyệt đối 100% diện tích, quy cách & đơn giá!)")
    return True


def _strip_accents(s):
    import unicodedata
    if not s:
        return ""
    s = str(s).replace("đ", "d").replace("Đ", "D")
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn").lower()


def search_system_data(query):
    """
    Tra cứu tức thì (<0.03s) toàn bộ giá vật tư, barem công thức, mặt hàng chuẩn và từ khóa đã có trong hệ thống.
    """
    q_raw = query.strip().lower()
    q_norm = _strip_accents(q_raw)
    tokens = [t for t in q_norm.split() if t]

    def _match(text):
        t_norm = _strip_accents(text)
        return (q_norm in t_norm) or (all(tok in t_norm for tok in tokens) if tokens else False)

    md_dir = os.path.join(PROJECT_ROOT, "data", "master_data")
    print(f"🔎 KẾT QUẢ TRA CỨU HỆ THỐNG SWIND CHO TỪ KHÓA: {query!r}")
    print("=" * 80)

    # 1. Tra cứu Master Price & Tech Database
    price_map = get_master_price_map()
    tech_path = os.path.join(md_dir, "master_database_tech.json")
    tech_list = []
    if os.path.exists(tech_path):
        with open(tech_path, "r", encoding="utf-8") as f:
            tech_list = json.load(f)
    tech_by_id = {t.get("MAT_ID"): t for t in tech_list if isinstance(t, dict) and t.get("MAT_ID")}

    matched_mats = []
    all_mat_ids = sorted(set(list(price_map.keys()) + list(tech_by_id.keys())))
    for mid in all_mat_ids:
        t_info = tech_by_id.get(mid, {})
        m_name = t_info.get("Name") or t_info.get("name") or ""
        m_unit = t_info.get("Unit") or t_info.get("unit") or ""
        m_cat = t_info.get("Category") or t_info.get("category") or ""
        p_val = price_map.get(mid, 0.0)
        blob = f"{mid} {m_name} {m_cat} {p_val}"
        if _match(blob):
            matched_mats.append((mid, m_name, m_unit, p_val, m_cat))

    print(f"1️⃣ ĐƠN GIÁ VẬT TƯ GỐC (`master_database_price.json` & `tech.json`): {len(matched_mats)} kết quả")
    for mid, m_name, m_unit, p_val, m_cat in matched_mats[:30]:
        sell_mfg = math.ceil((p_val * 1.35 * 1.18) / 100.0) * 100 if p_val else 0
        print(f"   • [{mid}] {m_name} ({m_unit}) | Giá gốc: {p_val:,.0f} đ | Quy đổi SX (~x1.593): {sell_mfg:,.0f} đ | Nhóm: {m_cat}")

    # 2. Tra cứu Barem & Hệ số định mức trong master_bom_rules.json
    bom_rules_path = os.path.join(md_dir, "master_bom_rules.json")
    matched_rules = []
    if os.path.exists(bom_rules_path):
        with open(bom_rules_path, "r", encoding="utf-8") as f:
            bom_rules = json.load(f)
        for sec_k, sec_v in bom_rules.items():
            if sec_k.startswith("_"):
                continue
            if isinstance(sec_v, dict):
                for sub_k, sub_v in sec_v.items():
                    blob = f"{sec_k}.{sub_k} {json.dumps(sub_v, ensure_ascii=False)}"
                    if _match(blob):
                        matched_rules.append((f"{sec_k}.{sub_k}", sub_v))
    print(f"\n2️⃣ BAREM & HỆ SỐ ĐỊNH MỨC (`data/master_data/master_bom_rules.json`): {len(matched_rules)} kết quả")
    for r_path, r_val in matched_rules[:15]:
        val_str = json.dumps(r_val, ensure_ascii=False)
        if len(val_str) > 160:
            val_str = val_str[:157] + "..."
        print(f"   • {r_path}: {val_str}")

    # 3. Tra cứu 53 Mặt hàng chuẩn trong Baseline & Experience DB
    matched_base = []
    if os.path.exists(BASELINE_PATH):
        with open(BASELINE_PATH, "r", encoding="utf-8") as f:
            base_list = json.load(f)
        for b in base_list:
            blob = f"{b.get('input_text')} {b.get('category')} {b.get('subtype')} {b.get('model_std')}"
            if _match(blob):
                matched_base.append(b)
    print(f"\n3️⃣ MẶT HÀNG CHUẨN TRONG BASELINE (`formula_regression_baseline.json`): {len(matched_base)} kết quả")
    for b in matched_base[:20]:
        print(f"   • {b['input_text']!r} ({b['unit']}) -> [{b['category']}/{b['subtype']}] Model={b['model_std']} | S={b['area_m2']}m2 | Giá bán chuẩn: {b['sell_unit_price']:,.0f} đ")

    # 4. Tra cứu Từ khóa nhận diện trong subtype_rules.json & boq_keyword_learning.json
    subtype_rules = get_subtype_rules()
    matched_kw = []
    for sec_k, sec_v in subtype_rules.items():
        blob = f"{sec_k} {json.dumps(sec_v, ensure_ascii=False)}"
        if _match(blob):
            matched_kw.append((f"subtype_rules.json :: {sec_k}", sec_v))
    learn_path = os.path.join(md_dir, "boq_keyword_learning.json")
    if os.path.exists(learn_path):
        with open(learn_path, "r", encoding="utf-8") as f:
            learn_db = json.load(f)
        for lk, lv in learn_db.items():
            if _match(f"{lk} {json.dumps(lv, ensure_ascii=False)}"):
                matched_kw.append((f"boq_keyword_learning.json :: {lk}", lv))
    print(f"\n4️⃣ TỪ KHÓA NHẬN DIỆN & QUY TẮC (`subtype_rules.json` / `boq_keyword_learning.json`): {len(matched_kw)} kết quả")
    for k_path, k_val in matched_kw[:15]:
        val_str = json.dumps(k_val, ensure_ascii=False)
        if len(val_str) > 150:
            val_str = val_str[:147] + "..."
        print(f"   • {k_path}: {val_str}")
    print("=" * 80)


def locate_requirement_target(topic):
    """
    Quét trực tiếp AST (0.02s) toàn bộ `src/*.py` và `data/master_data/*.json` để chỉ ra chính xác
    File + Hàm + Tọa độ dòng `StartLine..EndLine` sống khi cần thêm yêu cầu mới hoặc sửa công thức.
    """
    import ast
    import re
    t_norm = _strip_accents(topic)
    tokens = [t for t in t_norm.split() if t]

    # Bản đồ định tuyến kiến trúc theo chủ đề yêu cầu
    arch_guides = [
        {
            "tags": ["header", "cot", "column", "ten vat tu", "khoi luong", "dvt", "don vi", "boq"],
            "title": "Nhận diện dòng Tiêu đề (Header) & Ánh xạ cột BOQ",
            "json_targets": ["data/master_data/subtype_rules.json -> key 'HEADER_ALIASES'"],
            "py_targets": [("src/swind_utils.py", "detect_boq_header"), ("src/agent_00b_input_normalizer.py", "normalize_sheet")]
        },
        {
            "tags": ["tu khoa", "keyword", "phan loai", "category", "subtype", "khac", "nhan dien", "model"],
            "title": "Thêm từ khóa nhận diện mặt hàng mới / Phân loại Category & Subtype",
            "json_targets": [
                "data/master_data/subtype_rules.json -> keys 'CATEGORY_KEYWORDS', 'DUCT_FITTING_SUBTYPES', 'DAMPER_SUBTYPES', 'DIFFUSER_SUBTYPES'",
                "data/master_data/boq_keyword_learning.json"
            ],
            "py_targets": [("src/swind_boq_parser.py", "parse_sheet"), ("src/agent_01_boq_extractor.py", "resolve_item_spec")]
        },
        {
            "tags": ["title", "ke thua", "cha con", "kich thuoc", "do day", "thickness", "obd", "luoi", "loc", "combo"],
            "title": "Kế thừa thông số từ Title cha / Bóc tách kích thước, độ dày & phụ kiện đi kèm",
            "json_targets": ["data/master_data/master_bom_rules.json -> 'ductwork_rules.tcvn_5687_thickness_mm'"],
            "py_targets": [
                ("src/swind_boq_parser.py", "parse_sheet"),
                ("src/swind_utils.py", "extract_duct_fitting_geometry"),
                ("src/agent_01_boq_extractor.py", "resolve_item_spec")
            ]
        },
        {
            "tags": ["ong", "cut", "con", "te", "chan re", "zet", "chac", "bit dau", "hop gio", "tieu am", "canvas", "ventcap", "ong mem", "dien tich"],
            "title": "Công thức tính diện tích S (m2) & BOM Ống gió, Phụ kiện, Tiêu âm, Canvas (Agent 04)",
            "json_targets": ["data/master_data/master_bom_rules.json -> 'ductwork_rules'"],
            "py_targets": [("src/agent_04_bom_duct.py", None)]
        },
        {
            "tags": ["van", "vcd", "mfd", "fd", "nrd", "prd", "md", "ei", "ei60", "ei90", "ei120", "belimo", "klb", "honeywell", "dong co", "modul"],
            "title": "Công thức & Barem giá Van gió, Van chặn lửa EI, Chia Modul & Động cơ (Agent 05)",
            "json_targets": ["data/master_data/master_bom_rules.json -> 'damper_rules'"],
            "py_targets": [("src/agent_05_bom_damper.py", None), ("src/agent_01_boq_extractor.py", "_resolve_damper_spec")]
        },
        {
            "tags": ["cua", "mieng gio", "louver", "linear", "slot", "sld", "slb", "khuech tan", "sot trung", "nan z", "bau duc", "nhom"],
            "title": "Công thức định mức nhôm, sơn, nhân công & phụ kiện Cửa gió (Agent 06)",
            "json_targets": ["data/master_data/master_bom_rules.json -> 'diffuser_rules'"],
            "py_targets": [("src/agent_06_bom_diffuser.py", None), ("src/agent_01_boq_extractor.py", "_resolve_diffuser_spec")]
        },
        {
            "tags": ["gia", "price", "vat tu", "markup", "loi nhuan", "nhan cong", "lam tron"],
            "title": "Cập nhật Đơn giá vật tư gốc / Hệ số Nhân công - Quản lý - Lợi nhuận / Làm tròn giá bán",
            "json_targets": [
                "data/master_data/master_database_price.json",
                "data/master_data/financial_policy.json"
            ],
            "py_targets": [
                ("src/tool_price_updater.py", None),
                ("src/swind_master_runner.py", "process_single_sheet_estimation")
            ]
        },
        {
            "tags": ["excel", "sheet", "bg", "copy", "format", " cli", "flag", "xuat file"],
            "title": "Xuất file Excel Báo giá khách hàng (Sheet BG), Đóng khung & Tham số CLI",
            "json_targets": ["data/master_data/format_learning_db.json"],
            "py_targets": [
                ("src/swind_master_runner.py", "export_customer_boq_quotation_files"),
                ("src/agent_07_excel_builder.py", None)
            ]
        }
    ]

    # Quét AST toàn bộ src/*.py để lấy tọa độ dòng thực tế
    src_files = [
        "src/agent_01_boq_extractor.py",
        "src/agent_04_bom_duct.py",
        "src/agent_05_bom_damper.py",
        "src/agent_06_bom_diffuser.py",
        "src/agent_07_excel_builder.py",
        "src/swind_boq_parser.py",
        "src/swind_utils.py",
        "src/swind_master_runner.py",
        "src/agent_00b_input_normalizer.py",
    ]
    ast_index = {}
    for rel_path in src_files:
        abs_path = os.path.join(PROJECT_ROOT, rel_path)
        if not os.path.exists(abs_path):
            continue
        with open(abs_path, "r", encoding="utf-8") as f:
            source = f.read()
        tree = ast.parse(source, filename=rel_path)
        funcs = []
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                doc = ast.get_docstring(node) or ""
                funcs.append({
                    "name": node.name,
                    "start": node.lineno,
                    "end": getattr(node, "end_lineno", node.lineno + 30),
                    "doc": doc.strip().splitlines()[0] if doc.strip() else ""
                })
        funcs.sort(key=lambda x: x["start"])
        ast_index[rel_path] = funcs

    print(f"🧭 ĐỊNH VỊ TỨC THÌ VỊ TRÍ CODE & DATA CHO YÊU CẦU: {topic!r}")
    print("=" * 80)

    matched_guides = []
    for g in arch_guides:
        if any(tag in t_norm for tag in g["tags"]) or any(tok in " ".join(g["tags"]) for tok in tokens):
            matched_guides.append(g)
    if not matched_guides:
        matched_guides = arch_guides

    for g in matched_guides:
        print(f"📌 {g['title']}:")
        for jt in g["json_targets"]:
            print(f"   • [DATA JSON] {jt}")
        for rel_p, fn_filter in g["py_targets"]:
            fn_list = ast_index.get(rel_p, [])
            if fn_filter:
                fn_list = [fn for fn in fn_list if fn["name"] == fn_filter]
            for fn in fn_list:
                doc_sfx = f" — {fn['doc']}" if fn["doc"] else ""
                print(f"   • [CODE PY]   {rel_p} :: def {fn['name']} (StartLine={fn['start']}, EndLine={fn['end']}){doc_sfx}")
        print("-" * 80)


def compare_excel_with_system(excel_path, sheet_filter=None, motor_brand=None, mfd_model=None, formula_mode=None, include_box=False):
    """
    Đối chiếu trực tiếp (0.2s) công thức & đơn giá trong 1 file Excel (BOQ hoặc Báo giá đã có giá)
    với kết quả tính toán chuẩn trong hệ thống Swind.
    """
    if not os.path.exists(excel_path):
        print(f"❌ Không tìm thấy file: {excel_path}")
        return

    wb = openpyxl.load_workbook(excel_path, data_only=True)
    with contextlib.redirect_stdout(io.StringIO()):
        parser = SwindBOQParser(excel_path, wb=wb)

    target_sheets = [s.strip() for s in sheet_filter.split(",")] if sheet_filter else [
        sh for sh in wb.sheetnames if getattr(wb[sh], "sheet_state", "visible") == "visible"
    ]

    for sh in target_sheets:
        if sh not in wb.sheetnames:
            continue
        ws = wb[sh]
        with contextlib.redirect_stdout(io.StringIO()):
            items = parser.parse_sheet(sh)
        if not items:
            continue

        # Tìm cột Đơn giá tham chiếu trong file (nếu có)
        ref_price_col = None
        for r_idx in range(1, min(25, ws.max_row + 1)):
            for c_idx in range(1, min(30, ws.max_column + 1)):
                val = _strip_accents(ws.cell(r_idx, c_idx).value or "")
                if any(k in val for k in ("don gia", "unit price", "rate", "gia ban")):
                    ref_price_col = c_idx
                    break
            if ref_price_col:
                break

        subtype_rules = get_subtype_rules()
        price_map = get_master_price_map()
        fin_path = os.path.join(PROJECT_ROOT, "data", "master_data", "financial_policy.json")
        with open(fin_path, "r", encoding="utf-8") as f:
            fin_policy = json.load(f)

        sys_results = []
        for idx_i, it in enumerate(items, 1):
            if motor_brand:
                it["motor_brand_override"] = motor_brand
            if mfd_model:
                it["mfd_model_override"] = mfd_model
            if formula_mode:
                it["duct_formula_mode"] = formula_mode
            sys_results.append(_evaluate_parsed_item_in_ram(it, idx_i, subtype_rules, price_map, fin_policy, include_box=include_box))

        print(f"\n📊 BẢNG ĐỐI CHIẾU SHEET '{sh}' ({len(items)} dòng mặt hàng) | Cột Đơn giá File: {ref_price_col or 'Chưa có'}")
        print("=" * 105)
        exact_cnt = 0
        diff_rows = []
        unrecognized_rows = []

        for it, sys_r in zip(items, sys_results):
            src_row = it.get("source_row", 0)
            sys_price = sys_r["sell_unit_price"]
            file_price = None
            if ref_price_col and src_row:
                raw_p = ws.cell(src_row, ref_price_col).value
                if isinstance(raw_p, (int, float)) and not isinstance(raw_p, bool) and raw_p > 0:
                    file_price = int(round(float(raw_p)))

            if sys_r["category"] == "KHAC" or sys_price == 0:
                unrecognized_rows.append((src_row, sys_r["input_text"], sys_r["category"], sys_r["subtype"]))

            if file_price is not None:
                if abs(file_price - sys_price) <= 100:
                    exact_cnt += 1
                else:
                    diff_rows.append((src_row, sys_r, file_price, sys_price))
            else:
                diff_rows.append((src_row, sys_r, None, sys_price))

        if ref_price_col and (exact_cnt > 0 or diff_rows):
            print(f"✅ Khớp 100% với giá hệ thống: {exact_cnt}/{len(items)} dòng | ⚠️ Lệch giá hoặc chưa có giá: {len(diff_rows)} dòng")
            for src_row, sys_r, f_p, s_p in diff_rows[:40]:
                f_str = f"{f_p:,.0f}đ" if f_p is not None else "Trống"
                delta = f"{(s_p - f_p):+,.0f}đ" if f_p is not None else "N/A"
                print(
                    f"  • R{src_row:<3d} | {sys_r['input_text'][:40]:<40s} | [{sys_r['category']}/{sys_r['subtype']}] "
                    f"A=({sys_r['a1']},{sys_r['a2']}) | File={f_str:>11s} vs HệThống={s_p:>11,.0f}đ (Lệch: {delta}) | {sys_r['code_location']}"
                )
        else:
            for src_row, sys_r, _, s_p in diff_rows[:30]:
                print(
                    f"  • R{src_row:<3d} | {sys_r['input_text'][:42]:<42s} | [{sys_r['category']}/{sys_r['subtype']}] "
                    f"A=({sys_r['a1']},{sys_r['a2']}) | S={sys_r['area_m2']:.3f}m2 | Giá HệThống={s_p:>11,.0f}đ | {sys_r['code_location']}"
                )

        if unrecognized_rows:
            print(f"\n⚠️ PHÁT HIỆN {len(unrecognized_rows)} DÒNG CHƯA CÓ GIÁ / CHƯA NHẬN DIỆN TRONG HỆ THỐNG:")
            for r_no, txt, cat, sub in unrecognized_rows[:20]:
                print(f"  - Dòng R{r_no}: {txt!r} (Category={cat}, Subtype={sub})")
        print("=" * 105)


def audit_boq_fast(
    excel_path,
    sheet_filter=None,
    kw_filter=None,
    motor_brand=None,
    mfd_model=None,
    formula_mode=None,
    include_box=False,
):
    """
    Quét & kiểm toán siêu tốc (0.25s, 1 lệnh duy nhất) toàn bộ file BOQ hoặc file Báo giá:
    1. Phân tách Giá đối tác đã báo (giữ nguyên) vs Giá Swind tính mới theo Nhóm & Model.
    2. Phát hiện xung đột Mã hiệu / Quy cách giữa Cột Tên (Col B) và Cột Spec/Mô tả (Col D):
       - Xung đột hãng động cơ (Kepler / KLB / Honeywell vs Belimo)
       - Khác biệt từ khóa kiểu nan cửa gió / loại van / ghi chú bọc chống cháy EI
    3. Liệt kê Top các dòng có đơn giá & thành tiền cao nhất để kiểm tra bất thường giá.
    4. Tra cứu / soi vết tức thì theo từ khóa (--filter) kèm cả tọa độ dòng BOQ R... và BG R...
    """
    if not os.path.exists(excel_path):
        print(f"❌ Không tìm thấy file: {excel_path}")
        return

    from swind_utils import detect_boq_header
    from openpyxl.utils import get_column_letter

    with contextlib.redirect_stdout(io.StringIO()):
        parser = SwindBOQParser(excel_path)
        subtype_rules = get_subtype_rules()
        price_map = get_master_price_map()
        fin_path = os.path.join(PROJECT_ROOT, "data", "master_data", "financial_policy.json")
        with open(fin_path, "r", encoding="utf-8") as f:
            fin_policy = json.load(f)

        if sheet_filter:
            target_sheets = [s.strip() for s in sheet_filter.split(",") if s.strip() in parser.wb.sheetnames]
        else:
            detected = parser.auto_detect_hvac_sheets()
            non_bg = [s for s in detected if s.strip().upper() != "BG"]
            target_sheets = non_bg if non_bg else detected

    for sh in target_sheets:
        ws_orig = parser.wb[sh]
        with contextlib.redirect_stdout(io.StringIO()):
            items = parser.parse_sheet(sh)
        if not items:
            continue

        # Tính ánh xạ CHÍNH XÁC BOQ R... -> BG R... bằng cách mô phỏng logic build_quotation_sheets
        header_row, col_map, hidden_rows, hidden_cols, max_scan_col = detect_boq_header(ws_orig)
        name_col = col_map.get("name", 2)
        stt_col = col_map.get("stt", 1) if col_map.get("name", 2) != 1 else col_map.get("stt")
        unit_col = col_map.get("unit", 5)
        qty_col = col_map.get("qty", 6)
        start_boq_row = header_row + 1
        while start_boq_row <= min(header_row + 3, ws_orig.max_row):
            r_texts = [
                str(ws_orig.cell(start_boq_row, c).value or "").strip().lower()
                for c in range(1, max_scan_col + 1)
                if get_column_letter(c) not in hidden_cols
            ]
            name_cell_v = ws_orig.cell(start_boq_row, name_col).value
            if any(k in r_texts for k in ("boq", "nhà thầu", "a1", "face size", "neck size")) or (
                name_cell_v in (None, "")
                and (
                    any(k in r_texts for k in ("model", "modul", "thương hiệu", "đơn giá", "thành tiền", "vật liệu", "nhân công", "vật tư", "material / vt", "labor / nc", "material / vật liệu"))
                    or (start_boq_row > header_row + 1 and not any(r_texts))
                )
            ):
                start_boq_row += 1
            else:
                break

        # Detect end_boq_row (giống hệt build_quotation_sheets: dừng tại "tổng cộng" hoặc 40 dòng trống liên tiếp)
        end_boq_row = ws_orig.max_row
        empty_streak = 0
        for r_chk in range(start_boq_row, ws_orig.max_row + 1):
            if r_chk in hidden_rows:
                continue
            b_chk = str(ws_orig.cell(r_chk, name_col).value or "").strip().lower()
            a_chk = str(ws_orig.cell(r_chk, stt_col).value or "").strip().lower() if stt_col else ""
            if any(k in b_chk or k in a_chk for k in ("tổng cộng", "tổng giá trị", "trước vat", "trước thuế vat", "total amount", "đại diện ban", "đại diện chủ đầu tư", "đại diện nhà thầu")):
                end_boq_row = r_chk - 1
                break
            if not b_chk and not a_chk and ws_orig.cell(r_chk, qty_col).value is None and ws_orig.cell(r_chk, unit_col).value is None:
                empty_streak += 1
                if empty_streak >= 40:
                    end_boq_row = r_chk - empty_streak
                    break
            else:
                empty_streak = 0
        # Trim trailing empty rows
        while end_boq_row >= start_boq_row:
            if end_boq_row not in hidden_rows and any(
                get_column_letter(c) not in hidden_cols and ws_orig.cell(end_boq_row, c).value is not None
                and str(ws_orig.cell(end_boq_row, c).value).strip() != ""
                for c in range(1, max(7, name_col + 1, qty_col + 1))
            ):
                break
            end_boq_row -= 1

        has_side_table = any(it.get("is_side_table") for it in items)
        first_main_sec = next(
            (it.get("section", "").strip() for it in items if not it.get("is_side_table") and it.get("section") and it.get("section") != "SẢN PHẨM"),
            ""
        ) if has_side_table else ""

        # Build source_row -> list of item indices (0-based) cho các item NON-side-table
        item_src_map = {}
        for i_idx, it in enumerate(items):
            if not it.get("is_side_table"):
                sr = it.get("source_row")
                if sr:
                    item_src_map.setdefault(sr, []).append(i_idx)

        # Walk visible BOQ rows và gán chính xác BG row cho từng item
        # Logic giống hệt build_quotation_sheets: mỗi visible BOQ row = 1 BG row,
        # NGOẠI TRỪ source_row có nhiều item → N BG rows cho N items tại source_row đó
        bg_curr = 14 + (1 if first_main_sec else 0)
        item_idx_to_bg = {}
        for r_i in range(start_boq_row, end_boq_row + 1):
            if r_i in hidden_rows:
                continue
            if r_i in item_src_map:
                for i_idx in item_src_map[r_i]:
                    item_idx_to_bg[i_idx] = bg_curr
                    bg_curr += 1
            else:
                bg_curr += 1  # Dòng section header / dòng trống / dòng chưa báo giá — đều chiếm 1 BG row

        has_standalone_cv_ref = any(
            float(it.get("ref_price") or 0) > 0
            and it.get("category") in ("CUA_GIO", "VAN_GIO")
            and not any(k in f"{it.get('raw_name', '')} {it.get('name', '')}".lower() for k in ("kèm hộp", "kèm box", "có hộp", "gắn hộp"))
            for it in items
        )
        eval_rows = []
        for idx_i, it in enumerate(items, 1):
            it["_has_standalone_cv_ref"] = has_standalone_cv_ref
            if motor_brand:
                it["motor_brand_override"] = motor_brand
            if mfd_model:
                it["mfd_model_override"] = mfd_model
            if formula_mode:
                it["duct_formula_mode"] = formula_mode
            ev = _evaluate_parsed_item_in_ram(it, idx_i, subtype_rules, price_map, fin_policy, include_box=include_box)
            ev["bg_row"] = item_idx_to_bg.get(idx_i - 1, 0)
            ev["line_total"] = int(round(ev["effective_sell_unit"] * ev["qty"]))
            eval_rows.append(ev)

        total_all = sum(r["line_total"] for r in eval_rows)
        partner_rows = [r for r in eval_rows if r["price_source"] == "PARTNER_KEPT"]
        swind_rows = [r for r in eval_rows if r["price_source"] != "PARTNER_KEPT"]
        tot_partner = sum(r["line_total"] for r in partner_rows)
        tot_swind = sum(r["line_total"] for r in swind_rows)

        print("=" * 115)
        print(f"⚡ BÁO CÁO KIỂM TOÁN SIÊU TỐC MÃ HIỆU & GIÁ TRỊ — SHEET '{sh}' ({len(eval_rows)} dòng mặt hàng)")
        print("=" * 115)
        pct_p = (tot_partner / total_all * 100) if total_all else 0.0
        pct_s = (tot_swind / total_all * 100) if total_all else 0.0
        print("1️⃣  PHÂN TÁCH NGUỒN GIÁ (GIÁ ĐỐI TÁC ĐÃ BÁO GIỮ NGUYÊN vs GIÁ SWIND BÁO MỚI):")
        print(f"  • Tổng cộng toàn Sheet (Trước VAT) : {total_all:>15,.0f} VNĐ ({len(eval_rows)} dòng)")
        print(f"  • Giá đối tác đã báo (Giữ nguyên)  : {tot_partner:>15,.0f} VNĐ ({len(partner_rows)} dòng — chiếm {pct_p:.1f}%)")
        print(f"  • Giá Swind tính mới (Cửa/Van/PK)  : {tot_swind:>15,.0f} VNĐ ({len(swind_rows)} dòng — chiếm {pct_s:.1f}%)")

        if swind_rows:
            print("\n  [Chi tiết Nhóm & Model do Swind tính giá mới]:")
            by_mod = {}
            for r in swind_rows:
                k = (r["category"], r["model_std"] or r["subtype"] or "KHAC")
                g = by_mod.setdefault(k, {"cnt": 0, "qty": 0.0, "min_u": r["effective_sell_unit"], "max_u": r["effective_sell_unit"], "tot": 0, "note": r["note_std"]})
                g["cnt"] += 1
                g["qty"] += r["qty"]
                g["min_u"] = min(g["min_u"], r["effective_sell_unit"])
                g["max_u"] = max(g["max_u"], r["effective_sell_unit"])
                g["tot"] += r["line_total"]
            for (cat_k, mod_k), g in sorted(by_mod.items(), key=lambda x: -x[1]["tot"]):
                share = (g["tot"] / tot_swind * 100) if tot_swind else 0.0
                print(
                    f"    - [{cat_k:<8s} | {str(mod_k):<18s}] {g['cnt']:>3d} dòng (SL={g['qty']:>6.0f}) | "
                    f"ĐG: {g['min_u']:>9,.0f}..{g['max_u']:>9,.0f}đ | Thành tiền: {g['tot']:>13,.0f}đ ({share:>4.1f}%) | {g['note']}"
                )

        # 2. Quét xung đột Mã hiệu / Quy cách giữa Cột Tên và Cột Spec/Ghi chú
        conflicts = []
        for r in eval_rows:
            if r["price_source"] == "PARTNER_KEPT":
                continue
            rn_low = (r["input_text"] or "").lower()
            nb_low = (r["note_boq"] or "").lower()
            mod_s = str(r["model_std"] or "")
            sub_s = str(r["subtype"] or "")

            # 2a. Xung đột hãng động cơ trong Spec vs Mặc định Belimo
            if r["category"] == "VAN_GIO" and sub_s in ("MFD", "MD", "MFSD", "MSFD"):
                for br_kw, br_label in (("kepler", "KEPLER/KLB"), ("klb", "KLB"), ("viweco", "VIWECO/KLB"), ("honeywell", "HONEYWELL"), ("siemens", "SIEMENS")):
                    if br_kw in nb_low or br_kw in rn_low:
                        if (r["motor_brand"] or "BELIMO").upper() != br_label.split("/")[0]:
                            conflicts.append((
                                "⚠️ HÃNG ĐỘNG CƠ",
                                r,
                                f"Spec ghi hãng '{br_kw.upper()}' nhưng đang áp {r['motor_brand'] or 'BELIMO'} ({mod_s}) -> ĐG={r['effective_sell_unit']:,.0f}đ"
                            ))
                        break

            # 2b. Khác biệt từ khóa kiểu nan giữa Cột Tên và Cột Spec
            if r["category"] == "CUA_GIO" and nb_low:
                spec_diff_notes = []
                if ("sọt trứng" in nb_low or "egg" in nb_low) and not any(k in rn_low for k in ("sọt trứng", "egg", "ecg")):
                    spec_diff_notes.append("Spec ghi 'nan sọt trứng'")
                if ("nan z" in nb_low or "louver" in nb_low) and not any(k in rn_low for k in ("nan z", "louver", "cửa chớp", "lấy gió", "thải gió")):
                    spec_diff_notes.append("Spec ghi 'nan Z/Louver'")
                if ("khuếch tán" in nb_low) and not any(k in rn_low for k in ("khuếch tán", "4 hướng")):
                    spec_diff_notes.append("Spec ghi 'khuếch tán'")
                if spec_diff_notes:
                    conflicts.append((
                        "ℹ️  KHÁC BIỆT CỘT TÊN vs SPEC (CỬA GIÓ)",
                        r,
                        f"{', '.join(spec_diff_notes)} vs Tên '{r['input_text']}' -> Đã chốt Model='{mod_s}' ({r['note_std']})"
                    ))

            # 2c. Khác biệt từ khóa Loại Van / Bọc EI giữa Cột Tên và Cột Spec
            if r["category"] == "VAN_GIO" and nb_low:
                dmp_notes = []
                if any(k in nb_low for k in ("mfd", "smd", "van ngăn cháy", "van chặn lửa")) and sub_s in ("NRD", "PRD", "MPRD", "VCD"):
                    dmp_notes.append("Spec có từ 'van ngăn cháy/MFD/SMD'")
                if any(k in nb_low for k in ("ei 60", "ei60", "ei 90", "ei90", "ei 120", "ei120", "bọc chống cháy")) and sub_s in ("NRD", "PRD", "MPRD", "VCD"):
                    dmp_notes.append("Spec ghi 'bọc chống cháy EI'")
                if sub_s in ("MFD", "MFSD") and "van fd" in nb_low and not any(k in nb_low for k in ("mfd", "động cơ", "on/off", "on-off")):
                    dmp_notes.append("Spec ghi 'Van FD'")
                if dmp_notes:
                    sec_s = str(r.get("section") or "").strip()
                    raw_s = str(r.get("input_text") or "").strip()
                    nm_disp = f"{sec_s} -> {raw_s}" if (sec_s and sec_s != "SẢN PHẨM" and sec_s.lower() not in raw_s.lower()) else raw_s
                    conflicts.append((
                        "ℹ️  KHÁC BIỆT CỘT TÊN vs SPEC (VAN GIÓ)",
                        r,
                        f"{', '.join(dmp_notes)} vs Tên '{nm_disp}' -> Đã chốt Model='{mod_s}' (ĐG={r['effective_sell_unit']:,.0f}đ)"
                    ))

        print(f"\n2️⃣  KIỂM TOÁN XUNG ĐỘT MÃ HIỆU & QUY CÁCH (CỘT TÊN vs CỘT SPEC/MÔ TẢ): {len(conflicts)} điểm lưu ý")
        if conflicts:
            for c_type, r, msg in conflicts:
                print(
                    f"  • {c_type} | BG R{r['bg_row']:<3d} (BOQ R{r['source_row']:<3d}) | "
                    f"KT=({r['a1']}x{r['a2']}) SL={r['qty']:.0f} | {msg}"
                )
        else:
            print("  ✅ Không phát hiện xung đột mã hiệu giữa Cột Tên và Cột Spec.")

        # 3. Top các dòng có Thành tiền / Đơn giá cao nhất (do Swind tính giá)
        print("\n3️⃣  TOP 12 DÒNG DO SWIND BÁO GIÁ CÓ GIÁ TRỊ LỚN NHẤT / ĐƠN GIÁ CAO NHẤT:")
        top_swind = sorted(swind_rows, key=lambda x: (-x["line_total"], -x["effective_sell_unit"]))[:12]
        for r in top_swind:
            spec_short = (r["note_boq"] or "").replace("\n", " ")[:42]
            print(
                f"  • BG R{r['bg_row']:<3d} (BOQ R{r['source_row']:<3d}) | {r['input_text'][:32]:<32s} | "
                f"Model={str(r['model_std']):<16s} | KT=({str(r['a1'])}x{str(r['a2'])}) | "
                f"SL={r['qty']:>4.0f} | ĐG={r['effective_sell_unit']:>10,.0f}đ | TT={r['line_total']:>12,.0f}đ | Spec: {spec_short}"
            )

        # 4. Nếu có --filter: In chi tiết toàn bộ các dòng khớp từ khóa
        if kw_filter:
            kw_low = kw_filter.strip().lower()
            matched = [
                r for r in eval_rows
                if kw_low in (r["input_text"] or "").lower()
                or kw_low in (r["note_boq"] or "").lower()
                or kw_low in str(r["model_std"] or "").lower()
                or kw_low in str(r["subtype"] or "").lower()
                or kw_low in f"{r['a1']}x{r['a2']}".lower()
                or kw_low in f"r{r['bg_row']}"
                or kw_low in f"r{r['source_row']}"
            ]
            print(f"\n4️⃣  KẾT QUẢ TRA CỨU CHI TIẾT THEO TỪ KHÓA --filter='{kw_filter}' ({len(matched)} dòng khớp):")
            for r in matched:
                print(
                    f"  🔎 BG R{r['bg_row']:<3d} (BOQ R{r['source_row']:<3d}) | Tên: {r['input_text']!r} | "
                    f"Model='{r['model_std']}' ({r['category']}/{r['subtype']}) | "
                    f"A=({r['a1']},{r['a2']}) B=({r['b1']},{r['b2']}) | SL={r['qty']:.0f} | "
                    f"ĐG={r['effective_sell_unit']:,.0f}đ (Swind={r['sell_unit_price']:,.0f}đ, Ref={r['ref_price']:,.0f}đ, Nguồn={r['price_source']})"
                )
                if r.get("section") and r.get("section") != "SẢN PHẨM":
                    print(f"     - Title cha BOQ: {r['section']!r}")
                if r["note_boq"]:
                    print(f"     - Cột Spec BOQ : {r['note_boq']!r}")
                print(f"     - Diễn giải BG : {r['note_std']!r} | Code: {r['code_location']}")
        print("=" * 115)


def refresh_formula_index(index_path=None):
    """
    Cập nhật lại cột 'Dòng (StartLine..EndLine)' trong .agents/rules/03_FORMULA_INDEX.md theo vị trí hàm thực tế (AST),
    để bảng chỉ mục không bị lệch sau mỗi lần sửa code. Bỏ qua dòng tham chiếu vùng con (VD: 'parse_sheet (Phân loại...)').
    """
    import ast
    import re
    index_path = index_path or os.path.join(PROJECT_ROOT, ".agents", "rules", "03_FORMULA_INDEX.md")
    with open(index_path, "r", encoding="utf-8") as f:
        lines = f.read().split("\n")
    ast_cache = {}

    def _func_ranges(rel_file):
        if rel_file not in ast_cache:
            full = os.path.join(PROJECT_ROOT, rel_file)
            ranges = {}
            if os.path.exists(full):
                with open(full, "r", encoding="utf-8") as f:
                    tree = ast.parse(f.read())
                for node in ast.walk(tree):
                    if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                        start = node.lineno
                        ranges.setdefault(node.name, (start, node.end_lineno))
            ast_cache[rel_file] = ranges
        return ast_cache[rel_file]

    section_file = None
    n_upd = 0
    for i, line in enumerate(lines):
        m_sec = re.match(r'^##\s.*\(`(src/[\w./]+\.py)`\)', line)
        if m_sec:
            section_file = m_sec.group(1)
            continue
        if line.startswith("## "):
            section_file = None
        if not line.startswith("|") or ":---" in line:
            continue
        cols = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cols) < 4:
            continue
        m_file = re.fullmatch(r'`(src/[\w./]+\.py)`', cols[0])
        rel_file, func_col, line_col_idx = (m_file.group(1), cols[1], 2) if m_file else (section_file, cols[1], 2)
        if not rel_file or not re.search(r'`\d+\.\.\d+`', cols[line_col_idx]) or re.search(r'`\s*\(', func_col) or "(" in func_col.replace("`", "").split("`")[0]:
            continue
        names = re.findall(r'`([A-Za-z_]\w*)`', func_col)
        rng = [r for r in (_func_ranges(rel_file).get(n) for n in names) if r]
        if not rng or len(rng) != len(names):
            continue
        new_rng = f"`{min(r[0] for r in rng)}..{max(r[1] for r in rng)}`"
        if cols[line_col_idx] != new_rng:
            cols[line_col_idx] = new_rng
            lines[i] = "| " + " | ".join(cols) + " |"
            n_upd += 1
    with open(index_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"[Formula Index] Đã cập nhật {n_upd} dòng tọa độ trong {os.path.relpath(index_path, PROJECT_ROOT)}")
    return n_upd


def main():
    ap = argparse.ArgumentParser(description="Công cụ kiểm tra nhanh công thức, tra cứu dữ liệu & đối chiếu giá Swind")
    ap.add_argument("items", nargs="*", help="Một hoặc nhiều chuỗi mô tả vật tư (có thể ngăn cách bằng dấu ';')")
    ap.add_argument("--unit", default="cái", help="Đơn vị tính (mặc định: cái)")
    ap.add_argument("--note", default="", help="Ghi chú BOQ đi kèm (nếu có)")
    ap.add_argument("--sizes", default=None, help="Danh sách kích thước kiểm tra hàng loạt (VD: '400x200,600x400,800x600')")
    ap.add_argument("--motor-brand", default=None, help="Chỉ định hãng động cơ: BELIMO, KLB, HONEYWELL")
    ap.add_argument("--mfd-model", default=None, help="Chỉ định mã đốt van MFD: 1.01, 1.02, 1.03, 1.04, 1.05")
    ap.add_argument("--formula-mode", default=None, help="Chế độ công thức ống gió: MPQ_STD, BIENIA, CAND, OG_MB_M2")
    ap.add_argument("--search", default=None, help="Tra cứu tức thì (0.03s) đơn giá vật tư, barem, mặt hàng chuẩn & từ khóa trong hệ thống")
    ap.add_argument("--locate", default=None, help="Định vị tức thì bằng AST (0.02s) file code, hàm & tọa độ dòng để thêm yêu cầu mới")
    ap.add_argument("--compare", default=None, help="Đối chiếu trực tiếp (0.2s) giá & công thức trong 1 file Excel với dữ liệu hệ thống Swind")
    ap.add_argument("--sheet", default=None, help="Chỉ định tên sheet khi dùng --compare hoặc --audit-boq")
    ap.add_argument("--filter", default=None, help="Lọc dòng theo từ khóa/kích thước/số dòng khi dùng --audit-boq (VD: '250x250', 'MFD', 'R434')")
    ap.add_argument("--json", action="store_true", help="Xuất kết quả dạng JSON")
    ap.add_argument("--self-test", action="store_true", help="Chạy kiểm thử 100% công thức đối chiếu với baseline")
    ap.add_argument("--save-baseline", action="store_true", help="Cập nhật file baseline chuẩn")
    ap.add_argument("--audit-boq", default=None, help="Kiểm toán siêu tốc (0.25s) sai mã hiệu, xung đột Spec & bất thường giá trong file BOQ/Báo giá")
    ap.add_argument("--include-box", action="store_true", help="Tính thêm hộp gió (Plenum Box theo công thức sheet PKV) cho các cửa gió kèm hộp")
    ap.add_argument("--refresh-index", action="store_true", help="Cập nhật lại tọa độ dòng trong .agents/rules/03_FORMULA_INDEX.md theo AST sống")
    args = ap.parse_args()

    if args.refresh_index:
        refresh_formula_index()
        sys.exit(0)

    if args.search:
        search_system_data(args.search)
        sys.exit(0)

    if args.locate:
        locate_requirement_target(args.locate)
        sys.exit(0)

    if args.compare:
        compare_excel_with_system(
            args.compare, sheet_filter=args.sheet,
            motor_brand=args.motor_brand, mfd_model=args.mfd_model, formula_mode=args.formula_mode,
            include_box=args.include_box,
        )
        sys.exit(0)

    if args.audit_boq:
        audit_boq_fast(
            args.audit_boq,
            sheet_filter=args.sheet,
            kw_filter=args.filter,
            motor_brand=args.motor_brand,
            mfd_model=args.mfd_model,
            formula_mode=args.formula_mode,
            include_box=args.include_box,
        )
        sys.exit(0)

    if args.self_test or args.save_baseline:
        ok = run_self_test(save_baseline=args.save_baseline)
        sys.exit(0 if ok else 1)

    if not args.items:
        ap.print_help()
        sys.exit(0)

    batch_cases = []
    for raw_arg in args.items:
        sub_items = [s.strip() for s in raw_arg.split(";") if s.strip()]
        for text in sub_items:
            if args.sizes:
                for sz in [z.strip() for z in args.sizes.split(",") if z.strip()]:
                    batch_cases.append({
                        "name": f"{text} {sz}",
                        "unit": args.unit,
                        "note": args.note,
                        "motor_brand": args.motor_brand,
                        "mfd_model": args.mfd_model,
                        "include_box": args.include_box,
                    })
            else:
                batch_cases.append({
                    "name": text,
                    "unit": args.unit,
                    "note": args.note,
                    "motor_brand": args.motor_brand,
                    "mfd_model": args.mfd_model,
                    "include_box": args.include_box,
                })

    all_out = inspect_batch_items(batch_cases, formula_mode=args.formula_mode, include_box=args.include_box)

    if args.json:
        print(json.dumps(all_out, ensure_ascii=False, indent=2))
        return

    for r in all_out:
        print("=" * 75)
        print(f"🔍 ĐẦU VÀO      : {r['input_text']}  (ĐVT: {r['unit']})")
        print(f"📂 PHÂN LOẠI    : Category={r['category']} | Subtype={r['subtype']} | Model={r['model_std']}")
        print(f"📐 KÍCH THƯỚC   : A=({r['a1']}, {r['a2']}) | B=({r['b1']}, {r['b2']}) | Modul={r['modul']} | L={r['l_col']} | Dày={r['thk_col']}mm")
        if r["area_m2"] > 0:
            print(f"📏 DIỆN TÍCH S  : {r['area_m2']:.3f} m2")
        print(f"🧮 CÔNG THỨC    : {r['formula_trace']}")
        print(f"📍 VỊ TRÍ CODE  : {r['code_location']}")
        print(f"📝 DIỄN GIẢI BG : {r['note_std']}")
        print(f"💰 ĐƠN GIÁ BÁN  : {r['sell_unit_price']:,.0f} VNĐ")
        if r["components"]:
            print("🔩 CHI TIẾT BOM :")
            for c in r["components"]:
                print(f"   - [{c['mat_id']}] {c['name']}: {c['calc_qty']:.4f} {c['unit']} x {c['mat_price']:,.0f}đ")
    print("=" * 75)


if __name__ == "__main__":
    main()
