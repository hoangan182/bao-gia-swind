import re
from swind_boq_parser import SwindBOQParser
from swind_universal_extractor import SwindUniversalExtractor
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

    def __init__(self, boq_file=None, project_name="Du_An_HDL_A1"):
        self.boq_file = boq_file
        self.project_name = project_name
        self.parser = SwindBOQParser(boq_file) if boq_file else None
        self.extractor = SwindUniversalExtractor(project_name=project_name)

    def detect_and_parse(self, sheet_names=None):
        if not self.parser:
            raise ValueError("[Agent 01] Chưa khởi tạo boq_file cho SwindBOQParser.")

        if sheet_names:
            target_sheets = [s.strip() for s in sheet_names if s.strip() in self.parser.wb.sheetnames]
            if not target_sheets:
                print(f"[Agent 01] Các sheet chỉ định {sheet_names} không tồn tại. Chuyển sang Auto-detect.")
                target_sheets = self.parser.auto_detect_hvac_sheets()
        else:
            target_sheets = self.parser.auto_detect_hvac_sheets()

        if not target_sheets:
            target_sheets = [s for s in self.parser.wb.sheetnames if not any(k in s.lower() for k in ("summary", "cover", "bìa"))]
            if not target_sheets:
                target_sheets = [self.parser.wb.sheetnames[0]]

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
            if any(kw in search_text for kw in rule["keywords"]):
                return rule["subtype"]
        return default

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
        raw_search = (raw_name + " " + str(item.get("model", "")) + " " + note_boq).lower()
        full_search = (name + " " + str(item.get("model", "")) + " " + note_boq).lower()

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
        is_box_combo = False
        dia_val = None
        eff_model_code = None
        req_motor = str(item.get("motor_brand_override") or "").strip().upper()
        req_mfd_model = str(item.get("mfd_model_override") or "").strip()
        is_klb_req = (req_motor == "KLB") or any(k in (raw_search + " " + full_search).lower() for k in ("klb", "viweco", "v6006")) or (req_mfd_model == "1.03")
        is_honeywell_req = (req_motor == "HONEYWELL") or any(k in (raw_search + " " + full_search).lower() for k in ("honeywell", "honey well", "ms4609", "s6061")) or (req_mfd_model == "1.04")
        motor_brand = "KLB" if is_klb_req else ("HONEYWELL" if is_honeywell_req else "BELIMO")

        if cat == "VAN_GIO":
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
            elif model_item == "VCD":
                damper_type = "VCD"
            elif model_item == "MD":
                damper_type = "MD"
            elif model_item == "NRD":
                damper_type = "NRD"
            elif model_item == "PRD":
                damper_type = "PRD"
            else:
                damper_type = cls.get_subtype(subtype_rules, "VAN_GIO", raw_search, cls.get_subtype(subtype_rules, "VAN_GIO", full_search, "VCD"))
                if damper_type in ("FD", "MD", "VCD"):
                    rs_low = raw_search.lower()
                    if any(fk in rs_low for fk in ("chặn lửa", "ngăn cháy", "dập lửa")) and any(mk in rs_low for mk in ("động cơ", "mô tơ", "môtơ", "mo tơ", "motor")):
                        damper_type = "MFD"
            subtype = damper_type
            eff_type = "MFD" if damper_type == "MFD_LOUVER" else damper_type
            w_use = w if w > 0 else (d if d > 0 else 300.0)
            h_use = h if h > 0 else (d if d > 0 else 300.0)
            req_motor = str(item.get("motor_brand_override") or "").strip().upper()
            req_mfd_model = str(item.get("mfd_model_override") or "").strip()
            eff_req_code = model_code or req_mfd_model
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
                        "- 2 đầu bích TDC - Gắn kèm động cơ ON-OFF 3.5Nm, 24V (Type: đóng mở nhanh) BELIMO - Model: FSLF24V US\n"
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
            elif eff_type == "NRD":
                model_fslf = model_bfn = "NRD"
                note_fslf = note_bfn = "Van 1 chiều tôn mạ kẽm. ĐG bao gồm bọc thêm tấm cách nhiệt KSH dày 10mm" if ei_rating > 0 else "Van 1 chiều tôn mạ kẽm"
            elif eff_type == "PRD":
                model_fslf = model_bfn = "PRD"
                note_fslf = note_bfn = "Van xả áp đối trọng tôn mạ kẽm. ĐG bao gồm bọc thêm tấm cách nhiệt KSH dày 10mm" if ei_rating > 0 else "Van xả áp đối trọng tôn mạ kẽm"
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

        elif cat == "CUA_GIO":
            combined_search = (raw_search + " " + full_search).lower()
            combo_cfg = (subtype_rules or {}).get("COMBO_AND_DETECTION_RULES") or get_subtype_rules().get("COMBO_AND_DETECTION_RULES", {})

            # Rule 1: KTC vs KTM check (nếu ghi KTC hoặc cửa bù khí nan Z thì cộng thêm mỗi cạnh 50)
            if not item.get("is_ktc_applied"):
                ktc_rx = combo_cfg.get("ktc_regex", r'\bktc\b|kích\s*thước\s*cổ')
                is_makeup_air_z = (
                    any(k in raw_search for k in ("cấp khí bù", "bù khí", "cấp gió bù", "bù gió"))
                    and not any(k in raw_search for k in ("fag", "sag", "rag", "oag", "pag", "seg", "eag", "sdg", "obd", "nan thẳng", "bầu dục"))
                )
                is_ktc = bool(re.search(ktc_rx, combined_search, re.IGNORECASE)) or is_makeup_air_z
                if is_ktc:
                    if w > 0: w += 50.0
                    if h > 0: h += 50.0
                    if d > 0: d += 50.0
                    item["w"] = w
                    item["h"] = h
                    item["d"] = d
                    a1 = "Ø" if d > 0 else (int(w) if w > 0 else None)
                    a2 = int(d) if d > 0 else (int(h) if h > 0 else None)
                item["is_ktc_applied"] = True

            mesh_kws = tuple(combo_cfg.get("mesh_keywords", ("lưới", "chắn côn trùng", "lcct", "+n", "+ n", "+is", "is")))
            filter_kws = tuple(combo_cfg.get("filter_keywords", ("phin lọc", "lọc bụi", "+f", "g4")))
            louver_kws = tuple(combo_cfg.get("louver_z_keywords", ("nan z", "louver", "luover", "louvre", "chớp", "fal", "oal", "eal", "wl")))

            has_obd = ("obd" in combined_search)
            has_mesh = any(k in combined_search for k in mesh_kws)
            has_filter = any(k in combined_search for k in filter_kws)
            is_double_layer = ("2 lớp" in combined_search or "hai lớp" in combined_search)
            is_black_2nd_layer = ("2nd layer" in combined_search or "black paint" in combined_search or "sơn đen" in combined_search)
            box_note = ". Không tính box do nhà thầu tự thi công" if any(k in raw_search for k in ("box", "hộp gió", "kèm hộp")) else ""

            # Rule 2: Cửa tăng áp, cửa hút khói kèm OBD -> nan thẳng bầu dục kèm van OBD mã SDG+O
            is_press_or_smoke = any(k in combined_search for k in ("tăng áp", "tạo áp", "hút khói", "thải khói", "pag", "seg"))

            # Rule 3: Cửa ghi nan Z, louver hoặc miệng cấp khí bù ngoài trời hoặc cửa nan 1 lớp khổ lớn >= 3000mm -> cửa nan Z mã WL / WL+N
            is_louver_z = (
                any(k in combined_search for k in louver_kws)
                or (any(k in raw_search for k in ("cấp khí bù", "bù khí", "cấp gió bù", "bù gió")) and not any(k in raw_search for k in ("fag", "sag", "rag", "oag", "pag", "seg", "eag", "sdg", "nan thẳng", "bầu dục")))
                or (max(w, h) >= 3000.0 and not has_obd and not is_double_layer and not any(k in combined_search for k in ("nan thẳng", "bầu dục", "linear", "sọt trứng", "khuếch tán")))
                or (has_mesh and not has_obd and not has_filter and not is_double_layer and not any(k in combined_search for k in ("cover", "nan thẳng", "bầu dục", "linear", "sọt trứng", "khuếch tán", "sag", "rag", "oag", "pag", "seg", "eag", "sdg")))
            )
            is_standalone_lcct = has_mesh and not any(k in raw_search for k in louver_kws + ("cửa", "miệng", "sag", "fag", "rag", "oag", "pag", "seg", "eag", "sdg", "cover", "nan "))

            # Rule 4: Cửa hồi là cửa nan thẳng bầu dục kèm lưới lọc bụi mã SDG+F
            is_return_grille = any(k in combined_search for k in ("cửa hồi", "miệng hồi", "hút hồi", "rag", "hồi gió", "gió hồi", "hồi lạnh"))

            # Rule 5: Cửa khuếch tán mã SD:
            # - Mặc định cho cửa vuông hệ điều hòa: 600x600 (cổ 450x450), 450x450 (cổ 300x300), 300x300 (cổ 150x150)
            is_sq_ac_diffuser = (w > 0 and w == h and int(w) in (600, 450, 300) and not is_return_grille and not is_louver_z)
            is_diffuser_sq = any(k in combined_search for k in ("khuếch tán", "scd", "sad", "diffuser")) or is_sq_ac_diffuser or (w == 600 and h == 600 and "sag" in combined_search)

            # Rule 6: Nhận diện Cửa gió / Miệng gió kèm hộp gió
            is_box_combo = any(k in combined_search for k in ("kèm hộp gió", "kèm hộp", "kèm box", "có hộp gió", "gắn hộp gió", "hộp và cửa", "hộp miệng gió", "hộp kèm cửa", "hộp + cửa")) and any(k in combined_search for k in ("cửa gió", "miệng gió", "cửa cấp", "cửa hồi", "miệng cấp", "miệng hồi", "cửa nan", "louver", "luover"))

            if is_standalone_lcct:
                profile_type = "LCCT"
                model_fslf = model_bfn = "LCCT"
                b1, b2 = None, None
                note_fslf = note_bfn = "Lưới chắn côn trùng"

            elif is_press_or_smoke and has_obd:
                profile_type = "BD"
                has_obd = True
                model_fslf = model_bfn = "SDG+O"
                if w > 0 and h > 0:
                    b1, b2 = int(max(50, w - 50)), int(max(50, h - 50))
                note_fslf = note_bfn = "Cửa nan thẳng bầu dục kèm van OBD (tăng áp / hút khói)" + box_note

            elif is_louver_z:
                profile_type = "Z"
                has_mesh = bool(has_mesh or any(k in combined_search for k in ("lưới", "côn trùng", "lcct")))
                model_fslf = model_bfn = "WL+N" if has_mesh else "WL"
                if w > 0 and h > 0:
                    b1, b2 = int(max(50, w - 50)), int(max(50, h - 50))
                note_fslf = note_bfn = ("Louver nan Z ngoài trời kèm lưới chắn côn trùng Inox 304" if has_mesh else "Louver nan Z ngoài trời") + (" kèm lưới lọc bụi" if has_filter else "") + box_note

            elif is_return_grille:
                profile_type = "BD"
                has_filter = True
                model_fslf = model_bfn = "SDG+O+F" if has_obd else "SDG+F"
                if w > 0 and h > 0:
                    b1, b2 = int(max(50, w - 50)), int(max(50, h - 50))
                note_fslf = note_bfn = f"Cửa hồi nan thẳng bầu dục kèm lưới lọc bụi{' và van OBD' if has_obd else ''}" + box_note

            elif is_diffuser_sq:
                profile_type = "T"
                model_fslf = model_bfn = "SD+O" if has_obd else "SD"
                if w > 0 and h > 0:
                    b1, b2 = int(max(50, w - 150)), int(max(50, h - 150))
                note_fslf = note_bfn = f"Cửa khuếch tán vuông 4 hướng{' kèm van OBD' if has_obd else ''}" + box_note

            else:
                if any(k in combined_search for k in ("nan thẳng", "bầu dục", "sag", "rag", "oag", "mag", "pag", "seg", "seag", "sdg")):
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
                    note_fslf = note_bfn = "Cửa nan sọt trứng" + (" kèm van OBD" if has_obd else "") + box_note
                elif profile_type == "SLB":
                    model_fslf = model_bfn = "SLB+O" if has_obd else "SLB"
                    if w > 0 and h > 0:
                        b1, b2 = (int(w), int(h)) if is_black_2nd_layer else (int(max(50, w - 50)), int(max(50, h - 50)))
                    note_fslf = note_bfn = "Cửa gió Linear nan T" + (" sơn đen lớp 2" if is_black_2nd_layer else "") + (" kèm van OBD" if has_obd else "") + box_note
                elif profile_type == "T":
                    model_fslf = model_bfn = "SD+O" if has_obd else "SD"
                    if w > 0 and h > 0:
                        b1, b2 = int(max(50, w - 150)), int(max(50, h - 150))
                    note_fslf = note_bfn = "Cửa khuếch tán vuông" + (" kèm van OBD" if has_obd else "") + box_note
                else:
                    if has_obd and has_filter:
                        model_fslf = model_bfn = "SDG+O+F"
                    elif has_obd:
                        model_fslf = model_bfn = "SDG+O"
                    elif has_filter:
                        model_fslf = model_bfn = "SDG+F"
                    else:
                        model_fslf = model_bfn = "SDG"
                    if w > 0 and h > 0:
                        b1, b2 = int(max(50, w - 50)), int(max(50, h - 50))
                    note_fslf = note_bfn = f"Cửa nan bầu dục {'2 lớp' if is_double_layer else '1 lớp'}" + (" kèm van OBD" if has_obd else "") + (" kèm LCCT" if has_mesh else "") + (" kèm phin lọc bụi" if has_filter else "") + box_note

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

            subtype = profile_type

        elif cat == "ONG_GIO":
            is_fitting = raw_name.lower().startswith(("box ", "hộp "))
            subtype = "BOX" if is_fitting else "DUCT_RECT"
            model_fslf = model_bfn = "BOX" if is_fitting else "DUCT-TDF"
            brand = "SWIND"
            thk_col = thk if thk > 0 else None
            l_col = int(l) if (is_fitting and l > 0) else (1120 if w > 0 else None)
            note_fslf = note_bfn = "Box miệng gió tôn mạ kẽm Phương Nam" if is_fitting else f"Ống gió tôn mạ kẽm Phương Nam dày {thk:.2f}mm"

        elif cat == "ONG_MEM":
            dia_val = int(d) if d > 0 else None
            if not dia_val:
                m = re.search(r'D\s?(\d+)', (raw_name + " " + str(item.get("model", "")) + " " + str(item.get("note_boq", ""))).upper())
                if m:
                    dia_val = int(m.group(1))
            raw_sub = cls.get_subtype(subtype_rules, "ONG_MEM", raw_name.lower(), cls.get_subtype(subtype_rules, "ONG_MEM", name.lower(), "NON_INSUL"))
            subtype = "INSUL" if raw_sub in ("INSUL", "INSULATED") else "NON_INSUL"
            is_insul = (subtype == "INSUL")
            model_fslf = model_bfn = "FLEX-INSUL" if is_insul else "FLEX-BARE"
            note_fslf = note_bfn = "Ống gió mềm có bảo ôn" if is_insul else "Ống gió mềm không bảo ôn"

        elif cat == "CANVAS":
            subtype = "CANVAS"
            model_fslf = model_bfn = "CANVAS"
            l_col = int(l) if l > 0 else 200
            note_fslf = note_bfn = "Khớp nối mềm vải bạt chống cháy"

        elif cat == "TIEU_AM":
            subtype = "SILENCER"
            model_fslf = model_bfn = "SILENCER"
            note_fslf = note_bfn = "Tiêu âm ống gió / hộp gió Rockwool 50kg/m3"

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
            "dia_val": dia_val,
            "has_fslf_formula_diff": has_fslf_formula_diff,
            "fslf_ratio": fslf_ratio,
            "act_unit": act_unit,
            "model_code": eff_model_code,
            "motor_brand": motor_brand,
            "is_box_combo": is_box_combo
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
