import re
from swind_boq_parser import SwindBOQParser
from swind_universal_extractor import SwindUniversalExtractor
from agent_04_bom_duct import Agent04_DuctworkBOM
import damper_classifier
import duct_classifier
from agent_05_bom_damper import Agent05_DamperBOM
from agent_06_bom_diffuser import Agent06_DiffuserBOM
import diffuser_classifier
import typo_normalizer
from swind_utils import get_subtype_rules


class Agent01_BOQExtractor:
    """
    Agent 01 - BOQ Extractor & Technical Spec Resolver
    Nhiệm vụ:
    1. Quét cấu trúc file BOQ Excel, tự động nhận diện Sheet kỹ thuật HVAC, phá merge cell và ghép ngữ cảnh dòng cha-con.
    2. Giải mã tập trung 1 lần duy nhất toàn bộ hồ sơ kỹ thuật (`resolved_spec`) cho từng hạng mục:
       - Phân loại chi tiết (`subtype`: VCD, NRD, MD, FD, MFD, MFD_LOUVER, Z, ECG, SLB, T, BD, INSUL/NON_INSUL)
       - Cột báo giá chuẩn Swind: `model_fslf`, `model_bfn`, `brand`, `a1`, `a2`, `b1`, `b2`, `modul`, `l_col`, `thk_col`
       - Cờ phụ kiện & cấu hình cơ khí: `has_obd`, `has_mesh`, `has_filter`, `is_double_layer`, `is_black_2nd_layer`, `is_fitting`
       - Ghi chú kỹ thuật 2 phương án báo giá (`note_fslf`, `note_bfn`) và hệ số quy đổi động cơ (`fslf_ratio`, `act_unit`).
    """

    INCLUDE_BOX = False

    def __init__(self, boq_file=None, project_name="Du_An_HDL_A1", wb=None, include_flex_duct=False):
        self.boq_file = boq_file
        self.project_name = project_name
        self.parser = SwindBOQParser(boq_file, wb=wb, include_flex_duct=include_flex_duct) if boq_file else None
        self.extractor = SwindUniversalExtractor(project_name=project_name)

    def detect_and_parse(self, sheet_names=None):
        if not self.parser:
            raise ValueError("[Agent 01] Chưa khởi tạo boq_file cho SwindBOQParser.")

        if sheet_names:
            target_sheets = [s.strip() for s in sheet_names if s.strip() in self.parser.wb.sheetnames]
            if not target_sheets:
                for req_s in sheet_names:
                    req_low = req_s.strip().lower()
                    for wb_s in self.parser.wb.sheetnames:
                        if req_low and req_low in wb_s.lower() and wb_s not in target_sheets:
                            target_sheets.append(wb_s)
            if not target_sheets:
                print(f"[Agent 01] Các sheet chỉ định {sheet_names} không tồn tại. Chuyển sang Auto-detect.")
                target_sheets = self.parser.auto_detect_hvac_sheets()
        else:
            target_sheets = self.parser.auto_detect_hvac_sheets()

        if not target_sheets:
            visible_sheets = [s for s in self.parser.wb.sheetnames if getattr(self.parser.wb[s], "sheet_state", "visible") == "visible"]
            cand_sheets = visible_sheets if visible_sheets else list(self.parser.wb.sheetnames)
            target_sheets = [s for s in cand_sheets if not any(k in s.lower() for k in ("summary", "cover", "bìa", "phạm vi", "pham vi", "scope"))]
            if not target_sheets:
                target_sheets = [cand_sheets[0]]

        all_items = self.parser.parse_sheets(target_sheets)
        for it in all_items:
            it["project_name"] = self.project_name
        return target_sheets, all_items

    def extract_from_rows(self, rows, header_map):
        """
        Tương thích ngược với luồng trích xuất từ danh sách dòng thô + header_map.
        """
        extracted_items = []
        for idx, row in enumerate(rows):
            name_idx = header_map.get("name_col", 0)
            if len(row) <= name_idx:
                continue
            raw_name = str(row[name_idx]).strip()
            dim_idx = header_map.get("dim_col")
            raw_dim = str(row[dim_idx]).strip() if dim_idx is not None and len(row) > dim_idx else ""
            unit_idx = header_map.get("unit_col")
            raw_unit = str(row[unit_idx]).strip() if unit_idx is not None and len(row) > unit_idx else ""
            qty_idx = header_map.get("qty_col")
            raw_qty = str(row[qty_idx]).strip() if qty_idx is not None and len(row) > qty_idx else ""

            if not raw_name or "tổng" in raw_name.lower():
                continue

            res = self.extractor.extract_and_sanitize(raw_name, raw_dim, raw_unit, raw_qty)
            res["row_index"] = idx + 1
            extracted_items.append(res)
        return extracted_items

    @staticmethod
    def get_subtype(subtype_rules, category, search_text, default):
        rules = subtype_rules.get(category, [])
        for rule in rules:
            for kw in rule["keywords"]:
                if kw not in search_text:
                    continue
                if kw.isalpha() and kw.isascii():
                    if re.search(r'(?<![a-z])' + re.escape(kw) + r'(?![a-z])', search_text):
                        return rule["subtype"]
                else:
                    return rule["subtype"]
        return default

    @classmethod
    def _resolve_damper_spec(cls, item, subtype_rules, price_map, idx, raw_search, full_search, w, h, d, ei_rating, a1, a2, motor_brand):
        """Giải mã hồ sơ kỹ thuật nhóm VAN_GIO (MFD 1.01-1.05, FD 2.01, MD, VCD, NRD, PRD, OBD & Combo Van+Van)."""
        b1, b2, modul, l_col, thk_col = None, None, None, None, None
        note_fslf, note_bfn = "", ""
        fslf_ratio, act_unit = 1.0, 0.0
        has_fslf_formula_diff = False

        # Phân loại (VG-01..VG-10): bảng rule data/master_data/damper_rules.json — src/damper_classifier.py
        cls_res = damper_classifier.classify(item, subtype_rules, raw_search, full_search, w, h, d, ei_rating, a1, a2)
        damper_type, eff_type = cls_res["damper_type"], cls_res["eff_type"]
        subtype = damper_type
        eff_model_code, motor_brand = cls_res["eff_model_code"], cls_res["motor_brand"]
        ei_rating = cls_res["ei_rating"]
        w, h, d, a1, a2 = cls_res["w"], cls_res["h"], cls_res["d"], cls_res["a1"], cls_res["a2"]
        w_use, h_use = cls_res["w_use"], cls_res["h_use"]
        bom_multi = Agent05_DamperBOM.calculate_damper_bom(
            parent_id=f"Q-{idx}",
            damper_type=eff_type,
            w=w_use,
            h=h_use,
            brand="PN",
            ei_rating=ei_rating,
            mfd_mode="multi_bfn24",
            model_code=eff_model_code,
            motor_brand=motor_brand,
            d=d
        )
        mod_cnt = bom_multi["modules_count"]
        w_eff = bom_multi["w_eff"]
        h_eff = bom_multi["h_eff"]
        w_mod = w_eff / bom_multi["mod_w"]
        h_mod = h_eff / bom_multi["mod_h"]
        is_clamped = (d == 0 and w > 0 and h > 0 and (w_eff != w or h_eff != h))

        l_col = bom_multi["l_body"] if d > 0 else 200
        thk_col = bom_multi["thickness_body"]
        item["l"] = bom_multi["l_body"]
        item["thickness"] = bom_multi["thickness_body"]
        modul = mod_cnt if mod_cnt > 1 else None
        if is_clamped:
            b1, b2 = int(w_eff), int(h_eff)
        elif mod_cnt > 1:
            b1, b2 = int(w_mod), int(h_mod)

        # Model + ghi chú báo giá, mô-men động cơ (VG-11, VG-12)
        model_fslf, model_bfn, note_fslf, note_bfn = damper_classifier.build_model_note(
            cls_res, mod_cnt, is_clamped, w_mod, h_mod, bom_multi["is_single_blade"])

        if eff_type in ("MFD", "MSFD", "MFSD"):
            if not (w_eff <= 150.0 and h_eff <= 150.0) and price_map:
                bom_single = Agent05_DamperBOM.calculate_damper_bom(
                    parent_id=f"QS-{idx}",
                    damper_type=eff_type,
                    w=w_use,
                    h=h_use,
                    brand="PN",
                    ei_rating=ei_rating,
                    mfd_mode="single_fslf24",
                    model_code=eff_model_code,
                    motor_brand=motor_brand,
                    d=d
                )
                multi_mech = sum(c["calc_qty"] * price_map.get(c["mat_id"], 0.0) for c in bom_multi["components"] if c["category"] != "ĐỘNG_CƠ_VÀ_CẢM_BIẾN")
                single_mech = sum(c["calc_qty"] * price_map.get(c["mat_id"], 0.0) for c in bom_single["components"] if c["category"] != "ĐỘNG_CƠ_VÀ_CẢM_BIẾN")
                if damper_type == "MFD_LOUVER":
                    lv_bom = Agent06_DiffuserBOM.calculate_diffuser_bom(f"QL-{idx}", "LOUVER", w_use, h_use, profile_type="Z", has_mesh=True)
                    lv_cost = sum(c["calc_qty"] * price_map.get(c["mat_id"], 0.0) for c in lv_bom["components"])
                    multi_mech += lv_cost
                    single_mech += lv_cost
                act_unit = sum(c["calc_qty"] * price_map.get(c["mat_id"], 0.0) for c in bom_multi["components"] if c["category"] == "ĐỘNG_CƠ_VÀ_CẢM_BIẾN")
                fslf_ratio = (single_mech / multi_mech) if multi_mech > 0 else 1.0
                has_fslf_formula_diff = True

        # Van+Van Combo: Nối thêm model suffix & note cho tất cả van phụ trong combo
        sec_dmps = item.get("secondary_dampers") or ([item.get("secondary_damper")] if item.get("secondary_damper") else [])
        for sec_dmp in sec_dmps:
            sec_item = {
                "category": "VAN_GIO",
                "raw_name": f"Van {sec_dmp}",
                "name": f"Van {sec_dmp}",
                "model": sec_dmp,
                "w": w,
                "h": h,
                "d": d,
                "ei_rating": 0,
                "motor_brand_override": motor_brand
            }
            sec_spec = cls.resolve_item_spec(sec_item, subtype_rules, price_map=price_map, idx=idx)
            model_fslf = f"{model_fslf} + {sec_spec['model_fslf']}"
            model_bfn = f"{model_bfn} + {sec_spec['model_bfn']}"
            note_fslf = f"{note_fslf}\n{sec_spec['note_fslf']}" if sec_spec["note_fslf"].startswith("-") else f"{note_fslf} + {sec_spec['note_fslf']}"
            note_bfn = f"{note_bfn}\n{sec_spec['note_bfn']}" if sec_spec["note_bfn"].startswith("-") else f"{note_bfn} + {sec_spec['note_bfn']}"

        return {
            "subtype": subtype,
            "model_fslf": model_fslf,
            "model_bfn": model_bfn,
            "a1": a1,
            "a2": a2,
            "b1": b1,
            "b2": b2,
            "modul": modul,
            "l_col": l_col,
            "thk_col": thk_col,
            "note_fslf": note_fslf,
            "note_bfn": note_bfn,
            "has_fslf_formula_diff": has_fslf_formula_diff,
            "fslf_ratio": fslf_ratio,
            "act_unit": act_unit,
            "eff_model_code": eff_model_code,
            "motor_brand": motor_brand
        }

    @classmethod
    def _resolve_diffuser_spec(cls, item, subtype_rules, price_map, idx, raw_name, name, raw_search, full_search, w, h, d, l, thk, ei_rating, a1, a2, eff_model_code, motor_brand):
        """Giải mã hồ sơ kỹ thuật nhóm CUA_GIO: phân loại theo bảng rule (diffuser_classifier) rồi ghép Combo Cửa+Van & Hộp gió."""
        modul, l_col, thk_col = None, None, None
        combo_cfg = (subtype_rules or {}).get("COMBO_AND_DETECTION_RULES") or get_subtype_rules().get("COMBO_AND_DETECTION_RULES", {})
        spec_prio = item.get("spec_priority", "name")
        include_box = bool(item.get("include_box") if "include_box" in item else getattr(cls, "INCLUDE_BOX", False))

        # Phân loại cửa gió: bảng rule data/master_data/diffuser_rules.json (thứ tự ưu tiên, nguồn gốc & lý do từng rule)
        cls_res = diffuser_classifier.classify(
            item, subtype_rules, raw_name, name, raw_search, full_search, w, h, d, a1, a2, combo_cfg, include_box
        )
        profile_type = cls_res["profile_type"]
        model_fslf = model_bfn = cls_res["model"]
        note_fslf = note_bfn = cls_res["note"]
        b1, b2, a1, a2 = cls_res["b1"], cls_res["b2"], cls_res["a1"], cls_res["a2"]
        w, h, d = cls_res["w"], cls_res["h"], cls_res["d"]
        w_pre_ktc, h_pre_ktc = cls_res["w_pre_ktc"], cls_res["h_pre_ktc"]
        has_obd, has_mesh, has_filter = cls_res["has_obd"], cls_res["has_mesh"], cls_res["has_filter"]
        is_double_layer, is_black_2nd_layer = cls_res["is_double_layer"], cls_res["is_black_2nd_layer"]
        is_removable, removable_factor = cls_res["is_removable"], cls_res["removable_factor"]
        is_box_combo, n_slots = cls_res["is_box_combo"], cls_res["n_slots"]
        combined_search = cls_res["combined_search"]

        combo_dmps = item.get("combo_dampers") or ([item["combo_damper"]] if item.get("combo_damper") else [])
        if combo_dmps:
            dmp_item = {
                "category": "VAN_GIO",
                "raw_name": raw_name,
                "name": name,
                "note_boq": item.get("note_boq", ""),
                "section": item.get("section", ""),
                "source_sheet": item.get("source_sheet", ""),
                "model": combo_dmps[0],
                "secondary_damper": combo_dmps[1] if len(combo_dmps) > 1 else None,
                "secondary_dampers": combo_dmps[1:],
                "w": float(item.get("w_damper") or w or 300),
                "h": float(item.get("h_damper") or h or 300),
                "d": float(item.get("d_damper") or d or 0),
                "l": l,
                "thickness": thk,
                "ei_rating": ei_rating,
                "motor_brand_override": item.get("motor_brand_override"),
                "mfd_model_override": item.get("mfd_model_override")
            }
            dmp_spec = cls.resolve_item_spec(dmp_item, subtype_rules, price_map=price_map, idx=idx)
            sep_fslf = "" if dmp_spec["model_fslf"] == "MD" else " "
            sep_bfn = "" if dmp_spec["model_bfn"] == "MD" else " "
            model_fslf = f"{model_fslf}{sep_fslf}+{sep_fslf}{dmp_spec['model_fslf']}"
            model_bfn = f"{model_bfn}{sep_bfn}+{sep_bfn}{dmp_spec['model_bfn']}"
            if dmp_spec["note_fslf"].startswith("-"):
                note_fslf = f"- {note_fslf}\n{dmp_spec['note_fslf']}"
            elif dmp_spec["model_fslf"] == "MD":
                note_fslf = f"{note_fslf} kèm {dmp_spec['note_fslf'][0].lower() + dmp_spec['note_fslf'][1:]}"
            else:
                note_fslf = f"{note_fslf} + {dmp_spec['note_fslf']}"
            if dmp_spec["note_bfn"].startswith("-"):
                note_bfn = f"- {note_bfn}\n{dmp_spec['note_bfn']}"
            elif dmp_spec["model_bfn"] == "MD":
                note_bfn = f"{note_bfn} kèm {dmp_spec['note_bfn'][0].lower() + dmp_spec['note_bfn'][1:]}"
            else:
                note_bfn = f"{note_bfn} + {dmp_spec['note_bfn']}"
            modul = dmp_spec["modul"]
            l_col = dmp_spec["l_col"]
            thk_col = dmp_spec["thk_col"]
            eff_model_code = dmp_spec["model_code"]
            motor_brand = dmp_spec["motor_brand"]

        box_spec = None
        if is_box_combo:
            w_box = w_pre_ktc if w_pre_ktc > 0 else (w if w > 0 else 300.0)
            h_box = h_pre_ktc if h_pre_ktc > 0 else (h if h > 0 else 300.0)
            name_txt_src = f"{raw_name} {name}"
            note_txt_src = str(item.get("note_boq") or "")
            box_3d_rx = r'(?:kèm|có|gắn|\+|và|with|including)?\s*(?:hộp(?:\s*(?:gió|cửa\s*gió|miệng\s*gió))?|box(?:\s*(?:gió|miệng\s*gió|cửa\s*gió))?|plenum\s*box)\s*(?:kt|kích\s*thước)?\s*[:=]?\s*(\d{2,4})\s*[xX*]\s*(\d{2,4})(?:\s*[xX*/,-]\s*[hHlLdD]?\s*[:=]?\s*(\d{2,4}))?'
            matches_name_box = list(re.finditer(box_3d_rx, name_txt_src, flags=re.IGNORECASE))
            if matches_name_box:
                chosen_m = None
                for mb in reversed(matches_name_box):
                    if mb.group(3) or re.match(r'^(?:kèm|có|gắn|\+|và|with|including)', mb.group(0).strip(), flags=re.IGNORECASE) or len(matches_name_box) > 1:
                        chosen_m = mb
                        break
                if chosen_m:
                    w_box = float(chosen_m.group(1))
                    h_box = float(chosen_m.group(2))

            def _extract_box_l(txt_val):
                if not txt_val:
                    return 0.0
                m3 = list(re.finditer(r'(?:hộp|box|plenum)[^0-9\n]*?\d{2,4}\s*[xX*]\s*\d{2,4}\s*[xX*/,-]\s*[hHlLdD]?\s*[:=]?\s*(\d{2,4})\b', txt_val, flags=re.IGNORECASE))
                if m3:
                    return float(m3[-1].group(1))
                m1 = list(re.finditer(r'(?:hộp(?:\s*(?:gió|cửa\s*gió|miệng\s*gió))?|box(?:\s*(?:gió|miệng\s*gió|cửa\s*gió))?|plenum\s*box)[^0-9\n]*?[hHlL]\s*[:=]?\s*(\d{2,4})\b', txt_val, flags=re.IGNORECASE))
                if m1:
                    return float(m1[-1].group(1))
                return 0.0

            l_from_name = _extract_box_l(name_txt_src)
            l_from_note = _extract_box_l(note_txt_src)
            if spec_prio == "note":
                l_box = l_from_note or l_from_name
            else:
                l_box = l_from_name or l_from_note
            if l_box <= 0:
                l_box = l if (l > 0 and l not in (1110.0, 1120.0)) else 300.0

            d_box = 0.0
            n_necks = 0
            m_neck = re.search(r'(?:(?<![a-zA-Z0-9Øø])([1-8])\s*)?cổ\s*(?:tròn\s*)?[dDØø]\s*(\d{2,4})\b', combined_search, flags=re.IGNORECASE)
            if m_neck:
                n_necks = int(m_neck.group(1)) if m_neck.group(1) else 1
                d_box = float(m_neck.group(2))
            is_insul_box = any(k in combined_search for k in ("bảo ôn", "bao on", "cách nhiệt", "cach nhiet", "insul"))
            thk_box = Agent04_DuctworkBOM.get_standard_thickness(max(w_box, h_box, d_box), is_round=False, explicit_thk=(thk if thk > 0 else 0.0))
            _, _, box_l_out, box_s_area, box_unit_price, box_spec_label, box_trace = Agent04_DuctworkBOM._calc_plenum_box(
                w_box, h_box, d_box, l_box, True, n_necks,
                "cổ" if n_necks > 0 else "", thk_box, is_insul_box
            )
            box_spec = {
                "w_box": w_box,
                "h_box": h_box,
                "l_box": float(box_l_out),
                "d_box": d_box,
                "n_necks": n_necks,
                "thk_box": thk_box,
                "is_insulated": is_insul_box,
                "area_m2": round(box_s_area, 3),
                "unit_price": box_unit_price,
                "spec_label": box_spec_label,
                "trace": box_trace
            }
            if include_box:
                model_fslf = f"{model_fslf} + Hộp gió"
                model_bfn = f"{model_bfn} + Hộp gió"
                box_desc = f"{box_spec_label}, tôn Hoa Sen dày {thk_box:.2f}mm" + (", có bảo ôn" if is_insul_box else "")
                if note_fslf.startswith("-"):
                    note_fslf = f"{note_fslf}\n- {box_desc}"
                else:
                    note_fslf = f"{note_fslf} + {box_desc}"
                if note_bfn.startswith("-"):
                    note_bfn = f"{note_bfn}\n- {box_desc}"
                else:
                    note_bfn = f"{note_bfn} + {box_desc}"
                if l_col is None:
                    l_col = int(box_l_out)
                if thk_col is None:
                    thk_col = thk_box

        return {
            "subtype": profile_type,
            "model_fslf": model_fslf,
            "model_bfn": model_bfn,
            "a1": a1,
            "a2": a2,
            "b1": b1,
            "b2": b2,
            "modul": modul,
            "l_col": l_col,
            "thk_col": thk_col,
            "note_fslf": note_fslf,
            "note_bfn": note_bfn,
            "has_obd": has_obd,
            "has_mesh": has_mesh,
            "has_filter": has_filter,
            "is_double_layer": is_double_layer,
            "is_black_2nd_layer": is_black_2nd_layer,
            # Đã nhân hệ số tháo lắp thì Agent 06 tính phần cửa theo công thức thường (tránh nhân 2 lần)
            "is_removable": is_removable and removable_factor == 1.0,
            "removable_factor": removable_factor,
            "is_box_combo": is_box_combo,
            "box_spec": box_spec,
            "n_slots": n_slots,
            "eff_model_code": eff_model_code,
            "motor_brand": motor_brand
        }

    @classmethod
    def _resolve_duct_spec(cls, item, cat, raw_name, raw_search, w, h, d, a1, a2):
        """Giải mã hồ sơ kỹ thuật nhóm ONG_GIO, CANVAS, TIEU_AM, ONG_MEM."""
        dia_val = None
        is_fire_canvas = False
        has_mesh, has_filter = False, False

        calc_duct = Agent04_DuctworkBOM.calculate_duct_item(item)
        item["duct_calc"] = calc_duct
        subtype = calc_duct["subtype"]
        if subtype == "PLENUM_BOX":
            # OG-21: Ghi chú ghi 1 hộp khác kích thước Tên -> vẫn tính theo Ghi chú, HỎI LẠI USER (User chốt 2026-11-03)
            box_conflict = duct_classifier.note_box_conflict(raw_name, item.get("note_boq"))
            if box_conflict:
                item["box_note_conflict"] = box_conflict
        is_fitting = subtype not in ("DUCT_RECT", "SPIRAL_DUCT", "DUCT_M2", "FLEX_DUCT")
        brand = "SWIND" if cat == "ONG_GIO" else None

        thk_val = float(calc_duct.get("thickness") or 0.0)
        thk_col = thk_val if thk_val > 0 else None
        l_val = calc_duct.get("l_mm")
        l_col = int(l_val) if l_val else None
        b1 = calc_duct.get("b1")
        b2 = calc_duct.get("b2")

        is_round_main = subtype in (
            "SPIRAL_DUCT", "ELBOW_RT", "REDUCER_RT", "TEE_RT", "WYE_RT",
            "TAKEOFF_RT", "OFFSET_RT", "END_CAP_RT", "COUPLING_RT",
            "CANVAS_RT", "SILENCER_RT", "VENTCAP", "FLEX_DUCT"
        ) or (d > 0 and w == 0)
        if is_round_main and d > 0:
            a1, a2 = "Ø", int(d)
            dia_val = int(d)
        elif w > 0:
            a1, a2 = int(w), int(h)
        elif d > 0:
            a1, a2 = "Ø", int(d)
            dia_val = int(d)

        if l_col:
            item["l"] = float(l_col)
        if thk_col:
            item["thickness"] = thk_val
        if subtype == "COUPLING_RT":
            item["unit"] = "cái"

        if subtype == "FLEX_DUCT":
            is_insul = "BO" in str(calc_duct.get("model_std", "")) and "KBO" not in str(calc_duct.get("model_std", ""))
            if not dia_val:
                m_d = re.search(r'D(\d+)', str(calc_duct.get("model_std", "")))
                if m_d:
                    dia_val = int(m_d.group(1))
                    a1, a2 = "Ø", dia_val
            subtype = "INSUL" if is_insul else "NON_INSUL"
            model_fslf = model_bfn = calc_duct.get("model_std") or ("FLEX-INSUL" if is_insul else "FLEX-BARE")
        elif subtype in ("CANVAS_SQ", "CANVAS_RT"):
            is_fire_canvas = duct_classifier.is_fire_canvas(calc_duct.get("model_std", ""), raw_search)  # OG-24
            model_fslf = model_bfn = calc_duct.get("model_std") or "CANVAS"
        else:
            model_fslf = model_bfn = calc_duct.get("model_std") or subtype
        note_fslf = note_bfn = calc_duct.get("spec_note", "")
        if subtype in ("ELBOW_SQ", "ELBOW_45", "ELBOW_90", "ELBOW_RT"):
            has_mesh, has_filter = duct_classifier.elbow_mesh_filter(raw_name)  # OG-22
            if has_mesh or has_filter:
                model_fslf = model_bfn = model_fslf + (" + LCCT" if has_mesh else "") + (" + G4" if has_filter else "")
                note_fslf = note_bfn = (
                    note_fslf
                    + (" kèm lưới chắn côn trùng Inox 304 (LCCT)" if has_mesh else "")
                    + (" và lưới lọc bụi thô G4" if has_filter else "")
                )

        return {
            "subtype": subtype,
            "is_fitting": is_fitting,
            "brand": brand,
            "a1": a1,
            "a2": a2,
            "b1": b1,
            "b2": b2,
            "l_col": l_col,
            "thk_col": thk_col,
            "dia_val": dia_val,
            "is_fire_canvas": is_fire_canvas,
            "has_mesh": has_mesh,
            "has_filter": has_filter,
            "model_fslf": model_fslf,
            "model_bfn": model_bfn,
            "note_fslf": note_fslf,
            "note_bfn": note_bfn
        }

    @classmethod
    def resolve_item_spec(cls, item, subtype_rules, price_map=None, idx=1):
        """
        Giải mã tập trung 1 lần duy nhất toàn bộ hồ sơ kỹ thuật của 1 dòng BOQ.
        Gắn trực tiếp vào `item["resolved_spec"]` để các Agent 04, 05, 06, 07 tái sử dụng đồng nhất.
        """
        if price_map is None:
            price_map = {}

        cat = item.get("category", "KHAC")
        raw_name = item.get("raw_name") or item.get("name", "")
        name = item.get("name", raw_name)
        w = float(item.get("w") or 0)
        h = float(item.get("h") or 0)
        d = float(item.get("d") or 0)
        l = float(item.get("l") or 0)
        thk = float(item.get("thickness") or 0)
        ei_rating = int(item.get("ei_rating") or 0)
        note_boq = str(item.get("note_boq") or "")
        sec_txt = str(item.get("section") or "")
        aux_txt = str(item.get("aux_text") or "")
        # Chuỗi so khớp qua bộ chuẩn hóa lỗi chính tả (typo_rules.json, phạm vi agent01) — không ghi lại BOQ
        typo_events = item.get("typo_events")
        raw_search = typo_normalizer.normalize_for_match((raw_name + " " + str(item.get("model", "")) + " " + note_boq).lower(), "agent01", typo_events)
        full_search = typo_normalizer.normalize_for_match((sec_txt + " " + name + " " + aux_txt + " " + str(item.get("model", "")) + " " + note_boq).lower(), "agent01", typo_events)

        model_fslf = item.get("model") or None
        model_bfn = model_fslf
        brand = "SWIND"
        a1 = "Ø" if d > 0 else (int(w) if w > 0 else None)
        a2 = int(d) if d > 0 else (int(h) if h > 0 else None)
        b1, b2, modul, l_col, thk_col = None, None, None, None, None
        note_fslf, note_bfn = "", ""
        fslf_ratio = 1.0
        act_unit = 0.0
        has_fslf_formula_diff = False

        subtype = None
        is_fitting = False
        has_obd = False
        has_mesh = False
        has_filter = False
        is_double_layer = False
        is_black_2nd_layer = False
        is_removable = False
        removable_factor = 1.0
        is_fire_canvas = False
        is_box_combo = False
        box_spec = None
        n_slots = 0
        dia_val = None
        eff_model_code = None
        req_motor = str(item.get("motor_brand_override") or "").strip().upper()
        req_mfd_model = str(item.get("mfd_model_override") or "").strip()
        is_klb_req = (req_motor == "KLB") or (req_mfd_model == "1.03")
        is_honeywell_req = (req_motor == "HONEYWELL") or (req_mfd_model == "1.04")
        motor_brand = "KLB" if is_klb_req else ("HONEYWELL" if is_honeywell_req else "BELIMO")

        if cat == "VAN_GIO":
            dmp_res = cls._resolve_damper_spec(item, subtype_rules, price_map, idx, raw_search, full_search, w, h, d, ei_rating, a1, a2, motor_brand)
            subtype = dmp_res["subtype"]
            model_fslf, model_bfn = dmp_res["model_fslf"], dmp_res["model_bfn"]
            a1, a2, b1, b2 = dmp_res["a1"], dmp_res["a2"], dmp_res["b1"], dmp_res["b2"]
            modul, l_col, thk_col = dmp_res["modul"], dmp_res["l_col"], dmp_res["thk_col"]
            note_fslf, note_bfn = dmp_res["note_fslf"], dmp_res["note_bfn"]
            has_fslf_formula_diff = dmp_res["has_fslf_formula_diff"]
            fslf_ratio, act_unit = dmp_res["fslf_ratio"], dmp_res["act_unit"]
            eff_model_code, motor_brand = dmp_res["eff_model_code"], dmp_res["motor_brand"]
        elif cat == "CUA_GIO":
            dif_res = cls._resolve_diffuser_spec(item, subtype_rules, price_map, idx, raw_name, name, raw_search, full_search, w, h, d, l, thk, ei_rating, a1, a2, eff_model_code, motor_brand)
            subtype = dif_res["subtype"]
            model_fslf, model_bfn = dif_res["model_fslf"], dif_res["model_bfn"]
            a1, a2, b1, b2 = dif_res["a1"], dif_res["a2"], dif_res["b1"], dif_res["b2"]
            modul, l_col, thk_col = dif_res["modul"], dif_res["l_col"], dif_res["thk_col"]
            note_fslf, note_bfn = dif_res["note_fslf"], dif_res["note_bfn"]
            has_obd, has_mesh, has_filter = dif_res["has_obd"], dif_res["has_mesh"], dif_res["has_filter"]
            is_double_layer, is_black_2nd_layer, is_removable = dif_res["is_double_layer"], dif_res["is_black_2nd_layer"], dif_res["is_removable"]
            removable_factor = float(dif_res.get("removable_factor") or 1.0)
            is_box_combo = dif_res["is_box_combo"]
            box_spec = dif_res.get("box_spec")
            n_slots = int(dif_res.get("n_slots") or 0)
            eff_model_code, motor_brand = dif_res["eff_model_code"], dif_res["motor_brand"]
        elif cat in ("ONG_GIO", "CANVAS", "TIEU_AM", "ONG_MEM"):
            dct_res = cls._resolve_duct_spec(item, cat, raw_name, raw_search, w, h, d, a1, a2)
            subtype, is_fitting, brand = dct_res["subtype"], dct_res["is_fitting"], dct_res["brand"]
            a1, a2, b1, b2 = dct_res["a1"], dct_res["a2"], dct_res["b1"], dct_res["b2"]
            l_col, thk_col, dia_val = dct_res["l_col"], dct_res["thk_col"], dct_res["dia_val"]
            is_fire_canvas, has_mesh, has_filter = dct_res["is_fire_canvas"], dct_res["has_mesh"], dct_res["has_filter"]
            model_fslf, model_bfn = dct_res["model_fslf"], dct_res["model_bfn"]
            note_fslf, note_bfn = dct_res["note_fslf"], dct_res["note_bfn"]
        else:
            subtype = "OTHER"
            brand = "SWIND" if ("chống cháy" in raw_search or "lưới" in raw_search) else None
            note_fslf = note_bfn = "Bọc chống cháy ống gió chuẩn EI" if "chống cháy ei" in raw_search else "Hạng mục phụ trợ / Nhà thầu tự thực hiện"

        model_std = model_fslf
        note_std = note_fslf

        resolved_spec = {
            "subtype": subtype,
            "model_std": model_std,
            "note_std": note_std,
            "model_fslf": model_fslf,
            "model_bfn": model_bfn,
            "brand": brand,
            "a1": a1,
            "a2": a2,
            "b1": b1,
            "b2": b2,
            "modul": modul,
            "l_col": l_col,
            "thk_col": thk_col,
            "note_fslf": note_fslf,
            "note_bfn": note_bfn,
            "is_fitting": is_fitting,
            "has_obd": has_obd,
            "has_mesh": has_mesh,
            "has_filter": has_filter,
            "is_double_layer": is_double_layer,
            "removable_factor": removable_factor,
            "is_black_2nd_layer": is_black_2nd_layer,
            "is_removable": is_removable,
            "is_fire_canvas": is_fire_canvas,
            "dia_val": dia_val,
            "has_fslf_formula_diff": has_fslf_formula_diff,
            "fslf_ratio": fslf_ratio,
            "act_unit": act_unit,
            "model_code": eff_model_code,
            "motor_brand": motor_brand,
            "is_box_combo": is_box_combo,
            "box_spec": box_spec,
            "n_slots": n_slots
        }
        if item.get("lcct_per_m2") and subtype == "LCCT":
            # LCCT báo theo m² (BOQ ĐVT m2, không có kích thước): BOM quy đổi 1000x1000 = 1 m², BG không ghi kích thước giả
            # (User chốt 2026-11-03, TONG_HOP_KHOI_LUONG_DHKK R429, R572)
            for k_dim in ("a1", "a2", "b1", "b2"):
                resolved_spec[k_dim] = None
            m2_note = "Lưới chắn côn trùng Inox 304 — đơn giá theo m² (BOQ ghi khối lượng theo m²)"
            for k_note in ("note_std", "note_fslf", "note_bfn"):
                resolved_spec[k_note] = m2_note
        item["resolved_spec"] = resolved_spec
        item["is_box_combo"] = is_box_combo
        return resolved_spec

    @classmethod
    def enrich_all_items(cls, all_items, subtype_rules, price_records=None):
        price_map = {p["MAT_ID"]: float(p.get("Price") or 0) for p in (price_records or [])}
        for idx, item in enumerate(all_items, 1):
            cls.resolve_item_spec(item, subtype_rules, price_map=price_map, idx=idx)
        return all_items
