import re
from swind_boq_parser import SwindBOQParser
from swind_universal_extractor import SwindUniversalExtractor
from agent_04_bom_duct import Agent04_DuctworkBOM
from agent_05_bom_damper import Agent05_DamperBOM
from agent_06_bom_diffuser import Agent06_DiffuserBOM
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
            target_sheets = [s for s in cand_sheets if not any(k in s.lower() for k in ("summary", "cover", "bìa"))]
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

        model_item = str(item.get("model") or "").strip().upper()
        model_code = None
        for mc in ("1.01", "1.02", "1.03", "1.04", "1.05", "2.01"):
            if mc in model_item:
                model_code = mc
                break

        if model_item == "FD" or "2.01" in model_item or "E-FD" in model_item:
            damper_type = "FD"
        elif "1.01" in model_item or "MFSD" in model_item:
            damper_type = "MFSD"
        elif model_item == "MFD" or any(k in model_item for k in ("1.02", "1.03", "1.04", "1.05")):
            damper_type = "MFD"
        elif model_item in ("MPRD", "M-PRD", "MRD") or any(k in raw_search.lower() for k in ("mprd", "m-prd", "mrd", "xả áp điện", "xả áp điều khiển")):
            damper_type = "MPRD"
        elif model_item in ("OBD", "VCD", "MD", "NRD", "PRD"):
            damper_type = model_item
        else:
            name_model_search = (str(item.get("raw_name") or item.get("name", "")) + " " + str(item.get("model", ""))).lower()
            note_only_search = str(item.get("note_boq") or "").lower()
            if item.get("spec_priority") == "note" and note_only_search:
                damper_type = cls.get_subtype(
                    subtype_rules, "VAN_GIO", note_only_search,
                    cls.get_subtype(subtype_rules, "VAN_GIO", name_model_search, cls.get_subtype(subtype_rules, "VAN_GIO", full_search, "VCD"))
                )
            else:
                damper_type = cls.get_subtype(
                    subtype_rules, "VAN_GIO", name_model_search,
                    cls.get_subtype(subtype_rules, "VAN_GIO", raw_search, cls.get_subtype(subtype_rules, "VAN_GIO", full_search, "VCD"))
                )
            if damper_type in ("FD", "MD", "VCD"):
                rs_low = (note_only_search + " " + raw_search.lower()) if item.get("spec_priority") == "note" else raw_search.lower()
                if any(fk in rs_low for fk in ("chặn lửa", "ngăn cháy", "dập lửa")) and any(mk in rs_low for mk in ("động cơ", "mô tơ", "môtơ", "mo tơ", "motor", "mfd")):
                    damper_type = "MFD"
        if damper_type == "PRD" and any(k in raw_search.lower() for k in ("mprd", "m-prd", "mrd", "xả áp động cơ", "xả áp điện", "xả áp điều khiển")):
            damper_type = "MPRD"
        subtype = damper_type
        eff_type = "MFD" if damper_type == "MFD_LOUVER" else damper_type
        w_use = w if w > 0 else (d if d > 0 else 300.0)
        h_use = h if h > 0 else (d if d > 0 else 300.0)
        req_motor = str(item.get("motor_brand_override") or "").strip().upper()
        req_mfd_model = str(item.get("mfd_model_override") or "").strip()
        eff_req_code = model_code or (req_mfd_model if eff_type in ("MFD", "MFSD") else "")
        is_klb_req = (req_motor == "KLB") or any(k in (raw_search + " " + full_search).lower() for k in ("klb", "viweco", "v6006")) or (eff_req_code == "1.03")
        is_honeywell_req = (req_motor == "HONEYWELL") or any(k in (raw_search + " " + full_search).lower() for k in ("honeywell", "honey well", "ms4609", "s6061")) or (eff_req_code == "1.04")
        motor_brand = "KLB" if is_klb_req else ("HONEYWELL" if is_honeywell_req else "BELIMO")
        if eff_type == "MD":
            ei_rating = 0
            item["ei_rating"] = 0
        is_fd_ei = (eff_type == "FD") and (
            (ei_rating > 0)
            or (eff_req_code == "2.01")
            or any(k in (raw_search + " " + full_search + " " + str(item.get("source_sheet", ""))).lower() for k in ("ei", "vgei", "pccc", "hút khói", "tăng áp", "bctn", "chống cháy"))
        )
        if is_fd_ei and d > 0:
            w = d
            h = d
            d = 0.0
            w_use = w
            h_use = h
            item["w"] = w
            item["h"] = h
            item["d"] = 0.0
            a1 = int(w)
            a2 = int(h)
        eff_model_code = eff_req_code or (("2.01" if is_fd_ei else "FD") if eff_type == "FD" else ("1.03" if is_klb_req else ("1.04" if is_honeywell_req else "1.02")))
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

        if eff_type in ("MFD", "MFSD"):
            mod_txt = f"\n- Chia {mod_cnt} modul khi sản xuất" if mod_cnt > 1 else ""
            clamp_txt = "\n- Van thu côn 2 đầu" if is_clamped else ""
            lv_txt = "\n- Kết hợp cửa Louver nan Z ngoài trời + LCCT" if damper_type == "MFD_LOUVER" else ""

            if eff_model_code == "1.03":
                model_fslf = "SWIND-1.03-MFD-EI90"
                note_fslf = (
                    "- Van ngăn cháy động cơ - Tiêu chuẩn EI 90\n"
                    "- 2 đầu bích TDC - Gắn kèm động cơ ON-OFF 5Nm, Hãng KLB\n"
                    "- Sản xuất theo BCTN số 4651/VLXD-TBMT"
                    f"{mod_txt}{clamp_txt}{lv_txt}"
                )
            elif eff_model_code == "1.04":
                mod_hw_txt = f"\n- Chia {mod_cnt} modul theo bản vẽ chi tiết" if mod_cnt > 1 else ""
                model_fslf = "MFD + Louver" if damper_type == "MFD_LOUVER" else "SWIND-1.04-MFD-EI60"
                note_fslf = (
                    "- Van động cơ MFD - Tiêu chuẩn EI 60\n"
                    "- 2 đầu bích TDC - HoneyWell, 9Nm, 230V, Type đóng mở nhanh: 15s - Model: MS4609F1010/B\n"
                    "- Sản xuất theo BCTN số 1515/VLXD-TBMT"
                    f"{mod_hw_txt}{clamp_txt}{lv_txt}"
                )
            elif eff_model_code == "1.01":
                model_fslf = "MFD + Louver" if damper_type == "MFD_LOUVER" else "SWIND-1.01-MFD-EI120"
                note_fslf = (
                    "- Van chống cháy động cơ - Tiêu chuẩn EI 120\n"
                    "- 2 đầu bích TDC - Gắn kèm động cơ ON-OFF 9Nm, 24V/230V BELIMO - Model: BFN 24\n"
                    "- Sản xuất theo BCTN số 4751/VLXD-TBMT"
                    f"{mod_txt}{clamp_txt}{lv_txt}"
                )
            elif eff_model_code == "1.05":
                model_fslf = "MFD + Louver" if damper_type == "MFD_LOUVER" else "SWIND-1.05-MFD-EI120"
                note_fslf = (
                    "- Van động cơ SWIND-MFD - Tiêu chuẩn EI 120\n"
                    "- 2 đầu bích TDC - Gắn kèm động cơ ON-OFF 9Nm, 24V BELIMO - Model: BFN 24\n"
                    "- Sản xuất theo BCTN số 2390/VLXD-TBMT"
                    f"{mod_txt}{clamp_txt}{lv_txt}"
                )
            else:
                model_fslf = "MFD + Louver" if damper_type == "MFD_LOUVER" else "SWIND-1.02-MFD-EI90"
                note_fslf = (
                    "- Van chống cháy động cơ - Tiêu chuẩn EI 90\n"
                    "- 2 đầu bích TDC - Gắn kèm động cơ ON-OFF 3.5Nm, 24V (Type: đóng mở nhanh) BELIMO - Model: FSLF US\n"
                    "- Sản xuất theo BCTN số 4752/VLXD-TBMT"
                    f"{mod_txt}{clamp_txt}{lv_txt}"
                )
            model_bfn = "MFD + Louver" if damper_type == "MFD_LOUVER" else "SWIND-1.05-MFD-EI120"
            note_bfn = (
                "- Van động cơ SWIND-MFD - Tiêu chuẩn EI 120\n"
                "- 2 đầu bích TDC - Gắn kèm động cơ ON-OFF 9Nm, 24V BELIMO - Model: BFN 24\n"
                "- Sản xuất theo BCTN số 2390/VLXD-TBMT\n"
                f"- {'Van 1 cánh' if bom_multi['is_single_blade'] else 'Van chia đa cánh'}"
                f"{mod_txt}{clamp_txt}{lv_txt}"
            )
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

        elif eff_type == "FD":
            mod_txt = f"\n- Chia {mod_cnt} modul khi sản xuất" if mod_cnt > 1 else ""
            clamp_txt = "\n- Van thu côn 2 đầu" if is_clamped else ""
            if is_fd_ei:
                model_fslf = model_bfn = "SWIND-2.01- E-FD-EI120"
                note_fslf = note_bfn = (
                    "- Van chặn lửa cầu chì - Tiêu chuẩn EI 120\n"
                    "- 2 đầu bích TDC - gắn cầu chì 70-74 độ C\n"
                    "- Sản xuất theo BCTN số: 4761/VLXD-TBMT"
                    f"{mod_txt}{clamp_txt}"
                )
            else:
                model_fslf = model_bfn = "FD"
                note_fslf = note_bfn = "Van chặn lửa cầu chì tôn mạ kẽm"
        elif eff_type == "MD":
            model_fslf = model_bfn = "MD"
            s_mod = (w_mod * h_mod) / 1_000_000.0
            if is_klb_req:
                if mod_cnt > 1:
                    note_fslf = note_bfn = f"Van MD chia {mod_cnt} modul,  {mod_cnt} động cơ KLB/VIWECO 24V - 10Nm ON/OFF"
                else:
                    note_fslf = note_bfn = "Van MD, động cơ KLB/VIWECO 24V - 10Nm ON/OFF"
            elif is_honeywell_req or motor_brand == "HONEYWELL":
                act_nm = "5Nm" if s_mod <= 0.8 else ("10Nm" if s_mod <= 1.8 else "20Nm")
                act_md = "CN4605A" if s_mod <= 0.8 else ("CN4610A" if s_mod <= 1.8 else "CN4620A")
                mod_dmp_txt = f", chia {mod_cnt} modul ({mod_cnt} động cơ)" if mod_cnt > 1 else ""
                note_fslf = note_bfn = f"Van động cơ ON-OFF HoneyWell {act_nm}, 230V, đóng mở 90s-150s (Model: {act_md}/tđ){mod_dmp_txt}"
            else:
                act_nm = "5Nm" if s_mod <= 0.8 else ("10Nm" if s_mod <= 1.8 else "20Nm")
                mod_dmp_txt = f", chia {mod_cnt} modul ({mod_cnt} động cơ)" if mod_cnt > 1 else ""
                note_fslf = note_bfn = f"Van động cơ ON-OFF BELIMO {act_nm} (đóng mở 150s), điện áp 230V, xuất xứ Thụy Sỹ{mod_dmp_txt}"
        elif eff_type == "MPRD":
            model_fslf = model_bfn = "M-PRD"
            s_mod = (w_mod * h_mod) / 1_000_000.0
            act_nm = "5Nm" if s_mod <= 0.8 else ("10Nm" if s_mod <= 1.8 else "20Nm")
            if ei_rating > 0:
                note_fslf = note_bfn = f"Van xả áp động cơ, thân van bọc tấm KSH 10mm, không có kiểm định. Động cơ Belimo On/Off {act_nm}"
            else:
                note_fslf = note_bfn = f"Van xả áp động cơ tôn mạ kẽm. Động cơ Belimo On/Off {act_nm}"
        elif eff_type == "NRD":
            model_fslf = model_bfn = "NRD"
            note_fslf = note_bfn = "Van 1 chiều tôn mạ kẽm. ĐG bao gồm bọc thêm tấm cách nhiệt KSH dày 10mm" if ei_rating > 0 else "Van 1 chiều tôn mạ kẽm"
        elif eff_type == "PRD":
            model_fslf = model_bfn = "PRD"
            note_fslf = note_bfn = "Van xả áp đối trọng tôn mạ kẽm. ĐG bao gồm bọc thêm tấm cách nhiệt KSH dày 10mm" if ei_rating > 0 else "Van xả áp đối trọng tôn mạ kẽm"
        elif eff_type == "OBD":
            model_fslf = model_bfn = "OBD"
            note_fslf = note_bfn = "Van điều chỉnh lưu lượng OBD tôn mạ kẽm"
        else:
            model_fslf = model_bfn = "VCD"
            note_fslf = note_bfn = "Van điều chỉnh lưu lượng tay gạt tôn mạ kẽm. ĐG bao gồm bọc thêm tấm cách nhiệt KSH dày 10mm" if ei_rating > 0 else "Van điều chỉnh lưu lượng tay gạt tôn mạ kẽm"

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
        """Giải mã hồ sơ kỹ thuật nhóm CUA_GIO (Rule 1 KTC->KTM, Rule 2-6 SD/SDG/WL/SLB/ECG/LCCT/G4 & Combo Cửa+Van)."""
        b1, b2, modul, l_col, thk_col = None, None, None, None, None
        note_fslf, note_bfn = "", ""
        combined_search = (raw_search + " " + full_search).lower()
        combo_cfg = (subtype_rules or {}).get("COMBO_AND_DETECTION_RULES") or get_subtype_rules().get("COMBO_AND_DETECTION_RULES", {})

        mesh_kws = tuple(combo_cfg.get("mesh_keywords", ("lưới", "chắn côn trùng", "côn trùng", "lcct", "+n", "+ n", "+is", "+ is", "i.s", "insect screen", "c/w is", "c/w i.s", "is"))) + ("lccct", "c/w ls", "c/w l.s", "chắn chim", "against bird", "bird screen")
        filter_kws = tuple(combo_cfg.get("filter_keywords", ("phin lọc", "lọc bụi", "lọc sơ cấp", "lưới lọc", "+f", "g4"))) + ("filter", "lọc thô", "lọc sơ cấp", "lưới lọc")
        louver_kws = tuple(combo_cfg.get("louver_z_keywords", ("nan z", "louver", "luover", "louvre", "chớp", "fal", "oal", "eal", "wl"))) + ("cửa chớp", "chớp nhôm")

        has_obd = (
            "obd" in combined_search
            or bool(re.search(r'\+\s*o\b|(?:c/w|\+|kèm|gắn|with)\s*obd\b|van\s+điều\s*ch[ỉi]nh\s*lưu\s*lượng|van\s+ch[ỉi]nh\s*lưu\s*lượng', combined_search))
        )
        primary_diff_search = (raw_name + " " + name + " " + str(item.get("model", ""))).lower()
        note_boq_low = str(item.get("note_boq") or "").lower()
        spec_prio = item.get("spec_priority", "name")

        has_explicit_straight = any(k in primary_diff_search for k in ("nan thẳng", "gió thẳng", "miệng thẳng", "cửa thẳng", "bầu dục", "nan bd"))
        has_explicit_egg = any(k in primary_diff_search for k in ("sọt trứng", "sọt trưng", "dạng lưới", "eggcrate", "egg crate", "ecg", "seeg"))
        has_explicit_louver = any(k in primary_diff_search for k in ("nan z", "louver", "luover", "louvre", "cửa chớp", "chớp nhôm"))
        has_explicit_slot = any(k in primary_diff_search for k in ("slot", "sld", "lsd", "dls", "khe hẹp", "kiểu khe"))
        has_explicit_linear = any(k in primary_diff_search for k in ("linear", "slb", "nan t ", "nan t-", "khe dài", "tuyến tính"))
        has_explicit_sq_diff = any(k in primary_diff_search for k in ("khuếch tán", "scd", "sad"))
        has_any_explicit_blade = (
            has_explicit_straight or has_explicit_egg or has_explicit_louver
            or has_explicit_slot or has_explicit_linear or has_explicit_sq_diff
        )

        note_blade_conflict = (spec_prio != "note") and (
            (has_explicit_straight and any(k in note_boq_low for k in ("nan z", "louver", "sọt trứng", "sọt trưng", "eggcrate", "khuếch tán", "slot", "linear")))
            or (has_explicit_louver and any(k in note_boq_low for k in ("nan thẳng", "bầu dục", "nan bd", "sọt trứng", "sọt trưng", "eggcrate", "khuếch tán", "slot", "linear")))
            or (has_explicit_egg and any(k in note_boq_low for k in ("nan thẳng", "bầu dục", "nan bd", "nan z", "louver", "khuếch tán", "slot", "linear")))
            or (has_explicit_sq_diff and any(k in note_boq_low for k in ("nan thẳng", "bầu dục", "nan bd", "nan z", "louver", "sọt trứng", "sọt trưng", "eggcrate", "slot", "linear")))
        )
        note_has_any_blade = any(k in note_boq_low for k in ("nan thẳng", "bầu dục", "nan bd", "nan z", "louver", "sọt trứng", "sọt trưng", "eggcrate", "khuếch tán", "slot", "linear"))
        blade_search = (note_boq_low if (spec_prio == "note" and note_has_any_blade) else (primary_diff_search if has_any_explicit_blade else combined_search))

        filter_search = re.sub(r'không\s+kèm\s+lọc[^\.,\n]*', '', combined_search)
        mesh_base = primary_diff_search if note_blade_conflict else combined_search
        mesh_search = re.sub(r'(?:dạng\s+lưới|lưới\s+(?:lọc|gió))', '', mesh_base)
        has_mesh = (
            any(k in mesh_search for k in mesh_kws if k != "is")
            or bool(re.search(r'\b(?:i\.s\.?|l\.s\.?|lc+t)\b|(?:c/w|\+|kèm|with)\s*(?:is|ls)\b', mesh_search))
        )
        has_filter = any(k in filter_search for k in filter_kws)
        is_double_layer = ("2 lớp" in combined_search or "hai lớp" in combined_search)
        is_black_2nd_layer = ("2nd layer" in combined_search or "black paint" in combined_search or "sơn đen" in combined_search)
        is_removable = any(k in combined_search for k in ("tháo lắp", "thao lap"))
        w_pre_ktc = float(item.get("w_pre_ktc") or w or 0.0)
        h_pre_ktc = float(item.get("h_pre_ktc") or h or 0.0)
        item["w_pre_ktc"] = w_pre_ktc
        item["h_pre_ktc"] = h_pre_ktc
        include_box = bool(item.get("include_box") if "include_box" in item else getattr(cls, "INCLUDE_BOX", False))
        box_clean_search = re.sub(
            r'không\s+(?:kèm|có|gồm|tính)\s*(?:hộp|box)[^\.,\n]*|\bthép\s+hộp\b|\bhộp\s+(?:kỹ\s*thuật|đấu\s*dây|điện|công\s*tắc|cứu\s*hỏa|chữa\s*cháy|quạt)\b',
            '',
            combined_search
        )
        has_box_kw = (
            any(k in box_clean_search for k in (
                "hộp gió", "hộp cửa gió", "hộp miệng gió", "kèm hộp", "kèm box",
                "có hộp", "có box", "gắn hộp", "gắn box", "+ hộp", "+hộp", "+ box", "+box",
                "và hộp", "hộp và cửa", "hộp kèm cửa", "hộp + cửa", "box gió",
                "box miệng", "box cửa", "plenum box", "with box", "c/w box",
                "including box", "including plenum"
            ))
            or bool(re.search(r'\bhộp\s*[hHlL=]?\s*\d{2,4}\b|\bbox\b', box_clean_search))
        )
        box_note = (". Không tính box do nhà thầu tự thi công" if (has_box_kw and not include_box) else "")

        # Rule 2: Cửa tăng áp, cửa hút khói kèm OBD -> nan thẳng bầu dục kèm van OBD mã SDG+O
        is_press_or_smoke = any(k in combined_search for k in ("tăng áp", "tạo áp", "hút khói", "thải khói", "cấp bù", "pag", "seg", "spg", "seag", "smoke"))
        is_eggcrate = any(k in blade_search for k in ("sọt trứng", "sọt trưng", "dạng lưới", "eggcrate", "egg crate", "ecg", "seeg"))

        # Rule 3: Cửa ghi nan Z, louver hoặc miệng cấp khí bù ngoài trời hoặc cửa nan 1 lớp khổ lớn >= 3000mm -> cửa nan Z mã WL / WL+N
        is_louver_z = (
            any(k in blade_search for k in louver_kws)
            or (any(k in raw_search for k in ("cấp khí bù", "bù khí", "cấp gió bù", "bù gió")) and not any(k in raw_search for k in ("fag", "sag", "rag", "oag", "mag", "pag", "seg", "spg", "eag", "sdg", "nan thẳng", "bầu dục", "nan bd")))
            or (max(w, h) >= 3000.0 and not has_obd and not is_double_layer and not is_eggcrate and not any(k in blade_search for k in ("nan thẳng", "bầu dục", "nan bd", "linear", "sọt trứng", "sọt trưng", "khuếch tán")))
            or (has_mesh and not has_obd and not has_filter and not is_double_layer and not is_eggcrate and not any(k in blade_search for k in ("cover", "nan thẳng", "bầu dục", "nan bd", "linear", "sọt trứng", "sọt trưng", "khuếch tán", "fag", "sag", "rag", "oag", "mag", "pag", "seg", "spg", "eag", "kag", "seag", "sdg", "grille", "grilles", "diffuser", "return", "supply", "insect screen", "i.s", "lcct")))
        )
        is_standalone_lcct = has_mesh and not any(k in raw_search for k in louver_kws + ("cửa", "miệng", "mặt gió", "sag", "fag", "rag", "oag", "mag", "pag", "seg", "spg", "eag", "kag", "seag", "sdg", "grille", "grilles", "diffuser", "cover", "nan "))
        is_standalone_filter = has_filter and not has_mesh and not has_obd and not any(k in raw_search for k in louver_kws + ("cửa", "miệng", "mặt gió", "sag", "fag", "rag", "oag", "mag", "pag", "seg", "spg", "eag", "kag", "seag", "sdg", "grille", "grilles", "diffuser", "cover", "nan "))

        is_slot_sld = (
            any(k in blade_search for k in ("slot", "sld", "lsd", "dls", "khe hẹp", "kiểu khe"))
            or bool(re.search(r'\b(?:lb\s*\d{2,3}|sl\s*\d|ls\s*\d|\d{3,4}\s*mm\s*[,;-]?\s*[dD]\d{2,3})\b', blade_search))
        )
        # Rule 4: Cửa hồi là cửa nan thẳng bầu dục kèm lưới lọc bụi thô mã SDG+F (nếu khách đã ghi kèm OBD thì không tự báo thêm lưới)
        is_return_grille = any(k in combined_search for k in ("cửa hồi", "miệng hồi", "hút hồi", "rag", "hồi gió", "gió hồi", "hồi lạnh", "cửa gió hồi", "cửa gió hôi", "return air", "return grille"))
        if is_return_grille and not has_mesh and not has_obd and not is_eggcrate and not is_slot_sld:
            has_filter = True
        has_img_slb = not is_slot_sld and (bool(item.get("has_embedded_image")) or any(k in blade_search for k in ("linear", "slb", "nan t ", "nan t-", "khe dài", "tuyến tính")))
        n_slots = 0
        if is_slot_sld:
            m_slot_cnt = re.search(r'(?:\b(?:sl|ls|sld[-_]?a?)\s*(\d)\s*s?\b|(\d)\s*(?:slot|khe)\b)', combined_search)
            if m_slot_cnt:
                n_slots = int(next(g for g in m_slot_cnt.groups() if g is not None))
            else:
                b_dim = min(w, h) if (w > 0 and h > 0) else max(w, h)
                if b_dim < 150.0:
                    n_slots = 1
                elif b_dim < 200.0:
                    n_slots = 2
                else:
                    n_slots = 3

        # Rule 5: Cửa khuếch tán mã SD (vuông 600x600, 450x450, 300x300 hoặc khuếch tán)
        is_thoi_kt = ("cửa thổi khuếch tán" in combined_search)
        is_sq_ac_diffuser = (
            not is_thoi_kt and not is_standalone_lcct and not is_standalone_filter
            and w > 0 and w == h and int(w) in (600, 450, 300)
            and not is_return_grille and not is_louver_z and not is_press_or_smoke and not is_eggcrate
            and (not has_obd or any(k in combined_search for k in ("cấp", "lạnh", "điều hòa", "sag", "sad", "scd", "khuếch tán", "450", "150")))
            and not any(k in blade_search for k in ("nan thẳng", "gió thẳng", "miệng thẳng", "cửa thẳng", "bầu dục", "nan bd", "sọt trứng", "sọt trưng", "eggcrate", "ecg", "linear", "nan t", "dạng nan", "格栅", "kiểm tra", "检查", "access door", "cửa công tác", "cửa thăm", "tháo lắp", "inspection", "oag", "eag", "mag", "fag", "ngoài trời", "gió thải"))
        )
        is_diffuser_sq = (not is_thoi_kt and not is_standalone_lcct and not is_standalone_filter) and (any(k in blade_search for k in ("khuếch tán", "scd", "sad", "diffuser")) or is_sq_ac_diffuser or (w == 600 and h == 600 and "sag" in blade_search))

        # Rule 1: KTC vs KTM check (nếu ghi KTC, --neck-size, hoặc cửa bù khí nan Z thì cộng thêm viền ra kích thước mặt)
        if not item.get("is_ktc_applied"):
            ktc_rx = combo_cfg.get("ktc_regex", r'\bktc\b|kích\s*thước\s*cổ')
            is_makeup_air_z = (
                any(k in raw_search for k in ("cấp khí bù", "bù khí", "cấp gió bù", "bù gió"))
                and not any(k in raw_search for k in ("fag", "sag", "rag", "oag", "pag", "seg", "eag", "sdg", "obd", "nan thẳng", "bầu dục"))
            )
            is_area_inferred = bool(re.search(r'\d+(?:\.\d+)?\s*(?:m2|m²)\b', raw_search)) and not bool(re.search(r'\d+\s*[xX*×]\s*\d+', raw_search))
            is_ktc = bool(re.search(ktc_rx, combined_search, re.IGNORECASE)) or is_makeup_air_z or bool(item.get("neck_size_override"))
            if is_ktc and not is_standalone_lcct and not is_standalone_filter and not is_area_inferred:
                if (item.get("combo_dampers") or item.get("combo_damper")):
                    if not item.get("w_damper") and w > 0:
                        item["w_damper"] = w
                    if not item.get("h_damper") and h > 0:
                        item["h_damper"] = h
                    if not item.get("d_damper") and d > 0:
                        item["d_damper"] = d
                ktc_offset = 150.0 if (is_diffuser_sq and ((w >= 150.0 and h >= 150.0) or d >= 150.0)) else 50.0
                if w > 0: w += ktc_offset
                if h > 0: h += ktc_offset
                if d > 0: d += ktc_offset
                item["w"] = w
                item["h"] = h
                item["d"] = d
                a1 = "Ø" if d > 0 else (int(w) if w > 0 else None)
                a2 = int(d) if d > 0 else (int(h) if h > 0 else None)
                item["is_ktc_applied"] = True

        # Rule 5b: Cửa gió kiểm tra / cửa tháo lắp (检查风门) → SDGK
        is_inspection_door = any(k in combined_search for k in ("kiểm tra", "检查", "检查风门", "inspection", "access door", "cửa công tác", "cửa thăm", "sdgk"))

        # Rule 6: Nhận diện Cửa gió / Miệng gió kèm hộp gió
        is_box_combo = bool(has_box_kw and not is_standalone_lcct and not is_standalone_filter and not is_inspection_door)

        if is_inspection_door:
            profile_type = "BD"
            is_removable = True
            has_mesh = False
            has_obd = False
            has_filter = False
            model_fslf = model_bfn = "SDGK"
            if w > 0 and h > 0:
                b1, b2 = int(max(50, w - 50)), int(max(50, h - 50))
            note_fslf = note_bfn = "Cửa kiểm tra nan bầu dục tháo lắp (bản lề + chốt)" + box_note

        elif is_standalone_lcct:
            profile_type = "LCCT"
            model_fslf = model_bfn = "LCCT+F" if has_filter else "LCCT"
            b1, b2 = None, None
            note_fslf = note_bfn = "Lưới chắn côn trùng Inox 304 kèm lọc bụi thô" if has_filter else "Lưới chắn côn trùng"

        elif is_standalone_filter:
            profile_type = "FILTER_G4"
            model_fslf = model_bfn = "G4"
            b1, b2 = None, None
            note_fslf = note_bfn = "Lưới lọc bụi thô G4 kèm khung nhôm"

        elif is_eggcrate:
            profile_type = "ECG"
            if has_obd and has_filter:
                model_fslf = model_bfn = "ECG+O+F+N" if has_mesh else "ECG+O+F"
            elif has_obd:
                model_fslf = model_bfn = "ECG+O+N" if has_mesh else "ECG+O"
            elif has_filter:
                model_fslf = model_bfn = "ECG+F+N" if has_mesh else "ECG+F"
            else:
                model_fslf = model_bfn = "ECG+N" if has_mesh else "ECG"
            if w > 0 and h > 0:
                b1, b2 = int(max(50, w - 50)), int(max(50, h - 50))
            note_fslf = note_bfn = "Cửa nan sọt trứng" + (" lõi tháo lắp" if is_removable else "") + (" kèm van OBD" if has_obd else "") + (" kèm LCCT" if has_mesh else "") + (" kèm lưới lọc bụi thô" if has_filter else "") + box_note

        elif is_press_or_smoke and has_obd and not has_img_slb and not is_slot_sld:
            profile_type = "BD"
            has_obd = True
            model_fslf = model_bfn = "SDG+O+N" if has_mesh else "SDG+O"
            if w > 0 and h > 0:
                b1, b2 = int(max(50, w - 50)), int(max(50, h - 50))
            note_fslf = note_bfn = "Cửa nan thẳng bầu dục kèm van OBD (tăng áp / hút khói)" + (" kèm LCCT" if has_mesh else "") + box_note

        elif is_louver_z and not is_slot_sld:
            profile_type = "Z"
            has_mesh = bool(has_mesh or any(k in mesh_search for k in ("lưới", "côn trùng", "chắn chim", "against bird", "bird screen", "lcct", "i.s", "insect screen")))
            if has_obd and has_mesh:
                model_fslf = model_bfn = "WL+O+N"
            elif has_obd:
                model_fslf = model_bfn = "WL+O"
            elif has_mesh:
                model_fslf = model_bfn = "WL+N"
            else:
                model_fslf = model_bfn = "WL"
            if w > 0 and h > 0:
                b1, b2 = int(max(50, w - 50)), int(max(50, h - 50))
            note_fslf = note_bfn = ("Louver nan Z ngoài trời kèm lưới chắn côn trùng Inox 304" if has_mesh else "Louver nan Z ngoài trời") + (" kèm van OBD" if has_obd else "") + (" kèm lưới lọc bụi thô" if has_filter else "") + box_note

        elif is_return_grille and not has_img_slb and not is_slot_sld:
            profile_type = "BD"
            if not has_mesh and not has_obd:
                has_filter = True
            if has_obd and has_filter and has_mesh:
                model_fslf = model_bfn = "SDG+O+F+N"
            elif has_obd and has_filter:
                model_fslf = model_bfn = "SDG+O+F"
            elif has_obd and has_mesh:
                model_fslf = model_bfn = "SDG+O+N"
            elif has_obd:
                model_fslf = model_bfn = "SDG+O"
            elif has_filter and has_mesh:
                model_fslf = model_bfn = "SDG+F+N"
            elif has_mesh:
                model_fslf = model_bfn = "SDG+N"
            else:
                model_fslf = model_bfn = "SDG+F"
            if w > 0 and h > 0:
                b1, b2 = int(max(50, w - 50)), int(max(50, h - 50))
            rem_txt = " khung tháo lắp" if is_removable else ""
            if has_filter and has_mesh:
                ret_acc = "kèm lưới lọc bụi thô và LCCT Inox 304" + (" và van OBD" if has_obd else "")
            elif has_mesh:
                ret_acc = "kèm lưới chắn côn trùng Inox 304" + (" và van OBD" if has_obd else "")
            elif has_filter:
                ret_acc = "kèm lưới lọc bụi thô" + (" và van OBD" if has_obd else "")
            elif has_obd:
                ret_acc = "kèm van OBD"
            else:
                ret_acc = ""
            note_fslf = note_bfn = f"Cửa hồi nan thẳng bầu dục{rem_txt} {ret_acc}".strip() + box_note

        elif is_diffuser_sq:
            profile_type = "T"
            is_round_diff = any(k in combined_search for k in ("round", "tròn", "srd"))
            if is_round_diff:
                model_fslf = model_bfn = ("SRD+O+N" if has_mesh else "SRD+O") if has_obd else ("SRD+N" if has_mesh else "SRD")
                if d > 0:
                    b1, b2 = "Ø", int(max(50, d - 150))
                note_fslf = note_bfn = f"Cửa khuếch tán tròn{' kèm van OBD' if has_obd else ''}{' kèm LCCT' if has_mesh else ''}" + box_note
            else:
                model_fslf = model_bfn = ("SD+O+N" if has_mesh else "SD+O") if has_obd else ("SD+N" if has_mesh else "SD")
                if w > 0 and h > 0:
                    if w >= 300 and h >= 300:
                        b1, b2 = int(max(50, w - 150)), int(max(50, h - 150))
                    else:
                        b1, b2 = int(max(50, w - 50)), int(max(50, h - 50))
                note_fslf = note_bfn = f"Cửa khuếch tán vuông 4 hướng{' kèm van OBD' if has_obd else ''}{' kèm LCCT' if has_mesh else ''}" + box_note

        else:
            if is_slot_sld and not any(k in combined_search for k in ("nan thẳng", "gió thẳng", "miệng thẳng", "cửa thẳng", "bầu dục", "nan bd", "sọt trứng", "sọt trưng")):
                profile_type = "SLD"
            elif has_img_slb and not any(k in combined_search for k in ("nan thẳng", "gió thẳng", "miệng thẳng", "cửa thẳng", "bầu dục", "nan bd", "sọt trứng", "sọt trưng")):
                profile_type = "SLB"
            elif is_thoi_kt or any(k in combined_search for k in ("nan thẳng", "gió thẳng", "miệng thẳng", "cửa thẳng", "bầu dục", "nan bd", "fag", "sag", "rag", "oag", "mag", "pag", "seg", "spg", "seag", "sdg")):
                profile_type = "BD"
            else:
                profile_type = cls.get_subtype(subtype_rules, "CUA_GIO", raw_search, cls.get_subtype(subtype_rules, "CUA_GIO", full_search, "BD"))
            if profile_type == "Z":
                model_fslf = model_bfn = "WL+N" if has_mesh else "WL"
                if w > 0 and h > 0:
                    b1, b2 = int(max(50, w - 50)), int(max(50, h - 50))
                note_fslf = note_bfn = "Louver nan Z ngoài trời" + (" kèm lưới chắn côn trùng" if has_mesh else "")
            elif profile_type == "ECG":
                model_fslf = model_bfn = "ECG+O" if has_obd else "ECG"
                if w > 0 and h > 0:
                    b1, b2 = int(max(50, w - 50)), int(max(50, h - 50))
                note_fslf = note_bfn = "Cửa nan sọt trứng" + (" lõi tháo lắp" if is_removable else "") + (" kèm van OBD" if has_obd else "") + box_note
            elif profile_type == "SLD":
                if n_slots <= 0:
                    b_dim = min(w, h) if (w > 0 and h > 0) else max(w, h)
                    n_slots = 1 if b_dim < 150.0 else (2 if b_dim < 200.0 else 3)
                base_sld = "DLS" if "dls" in combined_search else "SLD"
                if has_obd and has_filter:
                    model_fslf = model_bfn = f"{base_sld}+O+F+N" if has_mesh else f"{base_sld}+O+F"
                elif has_obd:
                    model_fslf = model_bfn = f"{base_sld}+O+N" if has_mesh else f"{base_sld}+O"
                elif has_filter:
                    model_fslf = model_bfn = f"{base_sld}+F+N" if has_mesh else f"{base_sld}+F"
                elif has_mesh:
                    model_fslf = model_bfn = f"{base_sld}+N"
                else:
                    model_fslf = model_bfn = base_sld
                if w > 0 and h > 0:
                    b1, b2 = int(max(50, w - 50)), int(max(30, h - 50))
                note_fslf = note_bfn = "Cửa gió kiểu khe hẹp" + (" kèm van OBD" if has_obd else "") + (" kèm LCCT" if has_mesh else "") + (" kèm lưới lọc bụi thô" if has_filter else "") + f" - {n_slots} slot" + box_note
            elif profile_type == "SLB":
                if has_obd and has_filter:
                    model_fslf = model_bfn = "SLB+O+F"
                elif has_obd:
                    model_fslf = model_bfn = "SLB+O"
                elif has_filter:
                    model_fslf = model_bfn = "SLB+F"
                else:
                    model_fslf = model_bfn = "SLB"
                if w > 0 and h > 0:
                    b1, b2 = (int(w), int(h)) if is_black_2nd_layer else (int(max(50, w - 50)), int(max(50, h - 50)))
                note_fslf = note_bfn = "Cửa gió Linear nan T" + (" sơn đen lớp 2" if is_black_2nd_layer else "") + (" kèm van OBD" if has_obd else "") + (" kèm LCCT" if has_mesh else "") + (" kèm lưới lọc bụi thô" if has_filter else "") + box_note
            elif profile_type == "T":
                model_fslf = model_bfn = ("SD+O+N" if has_mesh else "SD+O") if has_obd else ("SD+N" if has_mesh else "SD")
                if w > 0 and h > 0:
                    if w >= 300 and h >= 300:
                        b1, b2 = int(max(50, w - 150)), int(max(50, h - 150))
                    else:
                        b1, b2 = int(max(50, w - 50)), int(max(50, h - 50))
                note_fslf = note_bfn = "Cửa khuếch tán vuông" + (" kèm van OBD" if has_obd else "") + (" kèm LCCT" if has_mesh else "") + box_note
            else:
                if is_removable and not has_obd and not has_filter and not has_mesh:
                    model_fslf = model_bfn = "SDGK"
                elif has_obd and has_filter:
                    model_fslf = model_bfn = "SDG+O+F+N" if has_mesh else "SDG+O+F"
                elif has_obd:
                    model_fslf = model_bfn = "SDG+O+N" if has_mesh else "SDG+O"
                elif has_filter:
                    model_fslf = model_bfn = "SDG+F+N" if has_mesh else "SDG+F"
                else:
                    model_fslf = model_bfn = "SDG+N" if has_mesh else "SDG"
                if w > 0 and h > 0:
                    b1, b2 = int(max(50, w - 50)), int(max(50, h - 50))
                note_fslf = note_bfn = f"Cửa nan bầu dục {'2 lớp' if is_double_layer else '1 lớp'}" + (" khung tháo lắp" if is_removable else "") + (" kèm van OBD" if has_obd else "") + (" kèm LCCT" if has_mesh else "") + (" kèm lưới lọc bụi thô" if has_filter else "") + box_note

        w_neck_explicit = float(item.get("w_neck") or 0)
        h_neck_explicit = float(item.get("h_neck") or 0)
        if w_neck_explicit > 0 and h_neck_explicit > 0 and profile_type not in ("LCCT", "FILTER_G4"):
            b1, b2 = int(w_neck_explicit), int(h_neck_explicit)

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
            "is_removable": is_removable,
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
            is_fire_canvas = ("CHONG-CHAY" in str(calc_duct.get("model_std", ""))) or any(k in raw_search for k in ("chống cháy", "chịu nhiệt", "tahk", "hút khói"))
            model_fslf = model_bfn = calc_duct.get("model_std") or "CANVAS"
        else:
            model_fslf = model_bfn = calc_duct.get("model_std") or subtype
        note_fslf = note_bfn = calc_duct.get("spec_note", "")
        if subtype in ("ELBOW_SQ", "ELBOW_45", "ELBOW_90", "ELBOW_RT"):
            raw_low = raw_name.lower()
            has_mesh = any(k in raw_low for k in ("lcct", "lưới chắn côn trùng"))
            has_filter = any(k in raw_low for k in ("lọc g4", "bộ lọc g4", "lọc bụi"))
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
        raw_search = (raw_name + " " + str(item.get("model", "")) + " " + note_boq).lower()
        full_search = (sec_txt + " " + name + " " + aux_txt + " " + str(item.get("model", "")) + " " + note_boq).lower()

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
        is_fire_canvas = False
        is_box_combo = False
        box_spec = None
        n_slots = 0
        dia_val = None
        eff_model_code = None
        req_motor = str(item.get("motor_brand_override") or "").strip().upper()
        req_mfd_model = str(item.get("mfd_model_override") or "").strip()
        is_klb_req = (req_motor == "KLB") or any(k in (raw_search + " " + full_search).lower() for k in ("klb", "viweco", "v6006")) or (req_mfd_model == "1.03")
        is_honeywell_req = (req_motor == "HONEYWELL") or any(k in (raw_search + " " + full_search).lower() for k in ("honeywell", "honey well", "ms4609", "s6061")) or (req_mfd_model == "1.04")
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
        item["resolved_spec"] = resolved_spec
        item["is_box_combo"] = is_box_combo
        return resolved_spec

    @classmethod
    def enrich_all_items(cls, all_items, subtype_rules, price_records=None):
        price_map = {p["MAT_ID"]: float(p.get("Price") or 0) for p in (price_records or [])}
        for idx, item in enumerate(all_items, 1):
            cls.resolve_item_spec(item, subtype_rules, price_map=price_map, idx=idx)
        return all_items
