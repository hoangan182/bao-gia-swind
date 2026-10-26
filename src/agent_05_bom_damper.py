import math


def _excel_round(value, ndigits=0):
    """Excel-compatible ROUND: rounds 0.5 away from zero (not banker's rounding)."""
    if ndigits >= 0:
        factor = 10 ** ndigits
        result = math.floor(value * factor + 0.5) / factor
        return int(result) if ndigits == 0 else result
    else:
        factor = 10 ** (-ndigits)
        return math.floor(value / factor + 0.5) * factor


class Agent05_DamperBOM:
    """
    SWIND-AGENT-05: Kỹ sư Dự toán Xưởng Van Gió & PCCC (Damper BOM Maker)
    - Chuyên trách bóc tách: VCD, MD, NRD, FD, MFD (Phương án đơn cánh FSLF24V & đa cánh BFN 24).
    - Tích hợp chuẩn công thức 'BG VAN ' (BẢNG TÍNH GIÁ SWIND chuẩn 2026).
    """

    @staticmethod
    def calculate_damper_bom(parent_id, damper_type, w, h, brand="PN", ei_rating=0, mfd_mode="multi_bfn24", model_code=None, motor_brand="BELIMO", d=0, raw_name="", allow_ei=None, ei_damper_mode=None, split_module=None):
        """
        Bóc tách Van Gió (VCD, MD, NRD, FD, MFD):
        - Quy tắc kích thước tối thiểu FD/MFD: W, H < 150mm được tính ở 150mm kèm thu côn 2 đầu (BCTN 4761 / 2390).
        - Quy tắc chia Modul van ngăn cháy MFD & FD:
          + MFD 1.04, 1.05 (EI120 đa cánh - BCTN 2390): Tiêu chuẩn 1 thân tối đa 1700x1000mm. Vượt 1700x1000 mới chia modul.
          + MFD 1.02, 1.03 (EI60/EI90 đơn/đa cánh - BCTN 4752) & FD 2.01 (cầu chì - BCTN 4761): Tiêu chuẩn 1 thân tối đa 1500x800mm. Vượt 1500x800 mới chia modul.
        - Chiều dài vỏ van: FD/MFD L=200mm (bọc cách nhiệt L+100=300mm), VCD/MD/NRD L=210mm, Van tròn L=D+50mm (D120 L=175mm).
        - Cánh van FD/MFD: Phương án đơn cánh (mfd_mode='single_fslf24' hoặc H_mod <= 250) vs đa cánh (H_mod - 5)/149.
        - Bọc chống cháy EI cho FD/MFD và VCD/NRD/PRD có chỉ số EI.
        """
        dtype_u = damper_type.upper()
        name_lower = str(raw_name or "").lower()
        if dtype_u in ("OBD", "SOBD"):
            a_m = float(w or 200.0) / 1000.0
            b_m = float(h or 200.0) / 1000.0
            raw_obd_frame_kg = 2.0 * (a_m + b_m) * 0.158
            raw_obd_blade_kg = (a_m / 0.04) * b_m * 0.10
            raw_obd_acc_cost = (a_m / 0.04) * 1500.0 + 5000.0
            unrounded_obd_sell = ((raw_obd_frame_kg + raw_obd_blade_kg) * 160000.0 + raw_obd_acc_cost) * 1.15
            target_obd_sell = _excel_round(unrounded_obd_sell, -3)
            from swind_utils import get_master_price_map, get_master_bom_rules
            mat_price_map = get_master_price_map()
            mfg_markup = float(get_master_bom_rules().get("damper_rules", {}).get("mfg_markup_factor", 1.593))
            p_alu_obd_master = mat_price_map.get("MAT-ALU-KHUNG-OBD", 133000.0)
            p_acc_master = mat_price_map.get("MAT-DOOR-ACCESSORY", 15000.0)
            scale_obd = (target_obd_sell / unrounded_obd_sell) if unrounded_obd_sell > 0 else 1.0
            obd_frame_kg = raw_obd_frame_kg * (160000.0 * 1.15 * scale_obd) / (p_alu_obd_master * mfg_markup)
            obd_blade_kg = raw_obd_blade_kg * (160000.0 * 1.15 * scale_obd) / (p_alu_obd_master * mfg_markup)
            obd_acc_bo = (raw_obd_acc_cost * 1.15 * scale_obd) / (p_acc_master * mfg_markup)
            return {
                "category": "VAN_GIO",
                "modules_count": 1,
                "mod_w": 1,
                "mod_h": 1,
                "w_eff": float(w or 200.0),
                "h_eff": float(h or 200.0),
                "l_body": 56,
                "thickness_body": 0.8,
                "is_single_blade": False,
                "components": [
                    {
                        "sub_key": f"{parent_id}-OBD-FRAME",
                        "name": "Khung nhôm van OBD (SOBD)",
                        "category": "NHÔM_ĐỊNH_HÌNH",
                        "mat_id": "MAT-ALU-KHUNG-OBD",
                        "calc_qty": obd_frame_kg,
                        "unit": "kg",
                        "note": f"Khung OBD {float(w or 200):.0f}x{float(h or 200):.0f}mm"
                    },
                    {
                        "sub_key": f"{parent_id}-OBD-BLADE",
                        "name": "Nan nhôm & thanh truyền van OBD (SOBD)",
                        "category": "NHÔM_ĐỊNH_HÌNH",
                        "mat_id": "MAT-ALU-NAN-OBD",
                        "calc_qty": obd_blade_kg,
                        "unit": "kg",
                        "note": "Nan OBD đối xứng & thanh liên kết"
                    },
                    {
                        "sub_key": f"{parent_id}-OBD-ACC",
                        "name": "Bánh răng nhựa & phụ kiện van OBD",
                        "category": "PHỤ_KIỆN_CỬA",
                        "mat_id": "MAT-DOOR-ACCESSORY",
                        "calc_qty": obd_acc_bo,
                        "unit": "Bộ",
                        "note": "Cơ cấu bánh răng đóng mở OBD"
                    }
                ]
            }

        is_fd = (dtype_u == "FD")
        is_fd_ei = is_fd and (ei_rating > 0 or str(model_code or "") == "2.01")
        is_fd_normal = is_fd and not is_fd_ei
        is_md = (dtype_u in ("MD", "MVD", "MCD"))
        is_nrd = (dtype_u == "NRD")
        is_prd = (dtype_u == "PRD")
        is_vcd_vit = (dtype_u == "VCD_VIT") or (dtype_u == "VCD" and any(k in name_lower for k in ("trục vít", "bánh vít", "tay vặn trục vít")))
        is_fd_vcd = (dtype_u in ("FD_VCD", "VCD+FD"))
        is_mfd = (dtype_u in ["MFD", "MFSD", "MSFD", "MFD_LOUVER"])
        is_round = (float(d or 0) > 0)
        d_eff = float(d or 0)

        if is_round:
            w_eff = d_eff
            h_eff = d_eff
            is_clamped = False
            mod_w, mod_h = 1, 1
        else:
            w_eff = max(150.0, float(w)) if (is_fd_ei or is_mfd) else float(w)
            h_eff = max(150.0, float(h)) if (is_fd_ei or is_mfd) else float(h)
            is_clamped = (w_eff != float(w) or h_eff != float(h))

        if is_mfd and not model_code:
            model_code = "1.03" if motor_brand.upper() == "KLB" else ("1.04" if motor_brand.upper() == "HONEYWELL" else "1.02")

        from swind_utils import get_master_bom_rules
        damper_rules = get_master_bom_rules().get("damper_rules", {})
        split_rules = damper_rules.get("module_split_rules", {})

        if is_round:
            mod_w, mod_h = 1, 1
        elif is_fd_ei or is_mfd:
            is_hw_104 = is_mfd and (model_code == "1.04" or motor_brand.upper() == "HONEYWELL")
            if is_hw_104:
                # SWIND-1.04 (Honeywell, BCTN 1515): Tiêu chuẩn 1 thân tối đa 1750x1000mm
                rule_cfg = split_rules.get("honeywell_104", {})
                max_w_lim = float(rule_cfg.get("max_w_mm", 1750.0))
                max_h_lim = float(rule_cfg.get("max_h_mm", 1000.0))
            elif is_mfd and model_code == "1.05":
                # SWIND-1.05 (Belimo, BCTN 2390): Tiêu chuẩn 1 thân tối đa 1700x1000mm
                rule_cfg = split_rules.get("large_105", {})
                max_w_lim = float(rule_cfg.get("max_w_mm", 1700.0))
                max_h_lim = float(rule_cfg.get("max_h_mm", 1000.0))
            else:
                # SWIND-1.01, 1.02, 1.03 & FD 2.01: Tiêu chuẩn 1 thân tối đa 1500x800mm
                rule_cfg = split_rules.get("standard_101_102_103_201", {})
                max_w_lim = float(rule_cfg.get("max_w_mm", 1500.0))
                max_h_lim = float(rule_cfg.get("max_h_mm", 800.0))
            mod_w = math.ceil(w_eff / max_w_lim) if w_eff > max_w_lim else 1
            mod_h = math.ceil(h_eff / max_h_lim) if h_eff > max_h_lim else 1
        elif is_md and motor_brand.upper() == "KLB":
            # Phân chia modul cho Van MD dùng động cơ KLB/VIWECO (chuẩn dự án Foxcom):
            if w_eff >= 4000.0 and h_eff >= 1500.0:
                mod_w, mod_h = 4, 2  # 8 modul
            elif (w_eff >= 2000.0 and h_eff > 1300.0) or (w_eff >= 4000.0 and h_eff <= 1500.0):
                mod_w, mod_h = 2, 2  # 4 modul
            elif (w_eff > 1300.0 and h_eff <= 1300.0) or (w_eff >= 3000.0 and h_eff <= 600.0) or (w_eff >= 1200.0 and h_eff >= 1000.0 and w_eff < 2000.0 and h_eff <= 1500.0):
                mod_w = 2 if w_eff >= h_eff else 1
                mod_h = 1 if w_eff >= h_eff else 2  # 2 modul
            else:
                mod_w, mod_h = 1, 1  # 1 modul
        elif is_nrd or is_prd or is_fd_normal or is_vcd_vit or is_fd_vcd or damper_type.upper() == "VCD" or (is_md and w_eff <= 2000.0 and h_eff <= 2000.0):
            mod_w = 1
            mod_h = 1
        else:
            md_cfg = split_rules.get("standard_md", {})
            max_w_md = float(md_cfg.get("max_w_mm", 2000.0))
            max_h_md = float(md_cfg.get("max_h_mm", 2000.0))
            mod_w = math.ceil(w_eff / max_w_md) if w_eff > max_w_md else 1
            mod_h = math.ceil(h_eff / max_h_md) if h_eff > max_h_md else 1
        modules_count = mod_w * mod_h
        w_mod = w_eff / mod_w
        h_mod = h_eff / mod_h

        if is_round:
            l_body = 175 if int(round(d_eff)) == 120 else int(round(d_eff + 50.0))
            if is_mfd or is_fd or ei_rating > 0 or d_eff > 500.0:
                thickness_body = 1.15
            elif d_eff <= 300.0:
                thickness_body = 0.75
            else:
                thickness_body = 0.95
        else:
            l_body = 200 if (is_fd or is_mfd) else 210
            if is_mfd or is_fd or is_md or ei_rating > 0:
                thickness_body = 1.15
            elif is_nrd or is_prd or is_vcd_vit or is_fd_vcd or damper_type.upper() == "VCD":
                if w_eff >= 1000.0 or h_eff >= 1000.0 or h_eff > 600.0:
                    thickness_body = 1.15
                elif h_eff > 400.0:
                    thickness_body = 0.95
                else:
                    thickness_body = 0.75
            else:
                thickness_body = 0.75 if max(w_mod, h_mod) <= 800 else 0.95

        flange_allowance = 70
        seam_allowance = 40
        peri_cut_m = (2 * (w_mod + h_mod) + seam_allowance) / 1000.0
        len_cut_m = (l_body + flange_allowance) / 1000.0

        area_body_m2 = peri_cut_m * len_cut_m * 1.05 * modules_count
        weight_body_kg = area_body_m2 * (7.85 * thickness_body)

        mod_note = f" ({modules_count} modul {w_mod:.0f}x{h_mod:.0f}mm)" if modules_count > 1 else ""
        clamp_note = f" (Thu côn từ {w_eff:.0f}x{h_eff:.0f}mm về {w:.0f}x{h:.0f}mm)" if is_clamped else ""

        components = [
            {
                "sub_key": f"{parent_id}-BODY",
                "name": f"Thân vỏ van {damper_type} bích C30/TDF ({thickness_body:.2f}mm)",
                "category": "TÔN_CUỘN_MẠ_KẼM",
                "mat_id": f"MAT-STEEL-{brand.upper()}-{thickness_body:.2f}",
                "calc_qty": weight_body_kg,
                "unit": "kg",
                "area_m2": area_body_m2,
                "note": f"Kích thước vỏ {w_eff:.0f}x{h_eff:.0f}x{l_body}mm{mod_note}{clamp_note}"
            }
        ]

        thickness_blade = 1.15 if (is_mfd or is_fd or is_md or ei_rating > 0) else 0.75
        is_single_blade = (h_mod <= 250.0) or (model_code in ("1.01", "1.02", "1.03", "2.01")) or (is_mfd and (mfd_mode == "single_fslf24" or motor_brand.upper() == "KLB"))
        if is_fd_ei or is_mfd:
            if is_single_blade:
                blade_factor_per_mod = 1.0
                blades_per_mod = 1
            else:
                blade_factor_per_mod = (h_mod - 5.0) / 149.0
                blades_per_mod = max(2, _excel_round(blade_factor_per_mod))
            blades_count = blades_per_mod * modules_count
            area_blades_m2 = (w_mod / 1000.0) * (h_mod / 1000.0) * 2.0 * modules_count
            weight_blades_kg = area_blades_m2 * (7.85 * thickness_blade)
            blade_note = f"Tôn bọc cánh & thân ({blades_per_mod} cánh/modul{mod_note})"
        else:
            blades_per_mod = max(1, math.ceil(h_mod / 180.0))
            blades_count = blades_per_mod * modules_count
            blade_h = (h_mod / blades_per_mod) + 20
            area_blades_m2 = blades_count * (w_mod / 1000.0) * (blade_h / 1000.0) * 1.08
            weight_blades_kg = area_blades_m2 * (7.85 * thickness_blade)
            blade_note = f"{blades_count} cánh cao {blade_h:.0f}mm{mod_note}"

        components.append({
            "sub_key": f"{parent_id}-BLADE",
            "name": f"Lá cánh / Tôn tấm bọc van ({blades_count} cánh)",
            "category": "TÔN_CUỘN_MẠ_KẼM",
            "mat_id": f"MAT-STEEL-{brand.upper()}-{thickness_blade:.2f}",
            "calc_qty": weight_blades_kg,
            "unit": "kg",
            "area_m2": area_blades_m2,
            "note": blade_note
        })

        axle_len_per_blade_m = (w_mod + 60) / 1000.0
        total_axle_len_m = blades_count * axle_len_per_blade_m
        components.append({
            "sub_key": f"{parent_id}-AXLE",
            "name": "Trục Sus 201 D10",
            "category": "PHỤ_KIỆN_VAN",
            "mat_id": "MAT-DAMPER-TRUC-SUS-201-D10",
            "calc_qty": total_axle_len_m,
            "unit": "m",
            "note": f"{blades_count} trục dài {axle_len_per_blade_m*1000:.0f}mm"
        })

        components.append({
            "sub_key": f"{parent_id}-BEARING",
            "name": "Bạc đồng D10",
            "category": "PHỤ_KIỆN_VAN",
            "mat_id": "MAT-DAMPER-BAC-DONG-D10",
            "calc_qty": blades_count,
            "unit": "Đôi",
            "note": f"{blades_count} đôi bạc đỡ 2 bên thân"
        })

        if blades_per_mod > 1:
            components.append({
                "sub_key": f"{parent_id}-GEAR",
                "name": "Bánh răng van nhôm",
                "category": "PHỤ_KIỆN_VAN",
                "mat_id": "MAT-DAMPER-BANH-RANG-VAN-NHOM",
                "calc_qty": modules_count,
                "unit": "Bộ",
                "note": f"Cơ cấu liên động cánh ({modules_count} bộ)"
            })

        cross_section_mod_m2 = (w_mod * h_mod) / 1_000_000.0
        if is_md:
            if motor_brand.upper() == "KLB":
                act_id = "MAT-ACTUATOR-SWIND-VIWECO"
                act_name = "Động cơ van gió KLB/VIWECO 24V - 10Nm ON/OFF"
            elif motor_brand.upper() == "HONEYWELL":
                if cross_section_mod_m2 <= 0.8:
                    act_id = "MAT-ACTUATOR-HONEYWELL-5NM"
                    act_name = "Động cơ van gió HoneyWell ON/OFF 5Nm (Model: CN4605A)"
                elif cross_section_mod_m2 <= 1.8:
                    act_id = "MAT-ACTUATOR-HONEYWELL-10NM"
                    act_name = "Động cơ van gió HoneyWell ON/OFF 10Nm (Model: CN4610A)"
                else:
                    act_id = "MAT-ACTUATOR-HONEYWELL-20NM"
                    act_name = "Động cơ van gió HoneyWell ON/OFF 20Nm (Model: CN4620A)"
            elif cross_section_mod_m2 <= 0.8:
                act_id = "MAT-ACTUATOR-BELIMO-5NM"
                act_name = "Động cơ van gió Belimo ON/OFF 5Nm"
            elif cross_section_mod_m2 <= 1.8:
                act_id = "MAT-ACTUATOR-BELIMO-10NM"
                act_name = "Động cơ van gió Belimo ON/OFF 10Nm"
            else:
                act_id = "MAT-ACTUATOR-BELIMO-20NM"
                act_name = "Động cơ van gió Belimo ON/OFF 20Nm"

            components.append({
                "sub_key": f"{parent_id}-ACTUATOR",
                "name": act_name,
                "category": "ĐỘNG_CƠ_VÀ_CẢM_BIẾN",
                "mat_id": act_id,
                "calc_qty": modules_count,
                "unit": "Cái",
                "note": f"Tiết diện {cross_section_mod_m2:.2f}m2/modul ({modules_count} bộ)"
            })
        elif is_fd:
            fuse_id = "MAT-DAMPER-CAU-CHI-USA-1-400X400" if max(w_mod, h_mod) < 400 else "MAT-DAMPER-CAU-CHI-USA-2-400X400"
            components.append({
                "sub_key": f"{parent_id}-FUSE",
                "name": "Cầu chì nhiệt nóng chảy 70°C/74°C (Elsie/USA)",
                "category": "PHỤ_KIỆN_VAN",
                "mat_id": fuse_id,
                "calc_qty": modules_count,
                "unit": "Cái",
                "note": f"Cầu chì kiểm định PCCC ({modules_count} cái)"
            })
        elif is_mfd:
            s_mod_m2 = (w_mod * h_mod) / 1_000_000.0
            if model_code == "1.03" or motor_brand.upper() == "KLB":
                act_id = "MAT-ACTUATOR-KLB-V6006FS500S"
                act_name = "Động cơ chặn lửa ON/OFF KLB (Swin V6006FS500S EI90) 5Nm"
            elif model_code == "1.04" or motor_brand.upper() == "HONEYWELL":
                act_id = "MAT-ACTUATOR-HONEYWELL"
                act_name = "Động cơ chặn lửa ON/OFF 9Nm, 230V (HONEYWELL MS4609F1010/B)"
            elif model_code == "1.01":
                act_id = "MAT-ACTUATOR-BELIMO-BFN24"
                act_name = "Động cơ chặn lửa ON/OFF 9Nm, 230V/24V (BELIMO BFN24 / BFN230)"
            elif is_single_blade or model_code == "1.02" or mfd_mode == "single_fslf24":
                act_id = "MAT-ACTUATOR-BELIMO-FSLF24"
                act_name = "Động cơ chặn lửa ON/OFF 3.5Nm, 230V/24V (BELIMO FSLF24 / FSLF230)"
            else:
                act_id = "MAT-ACTUATOR-BELIMO-BFN24"
                act_name = "Động cơ chặn lửa ON/OFF 9Nm, 230V/24V (BELIMO BFN24 / BFN230)"

            components.append({
                "sub_key": f"{parent_id}-ACTUATOR",
                "name": act_name,
                "category": "ĐỘNG_CƠ_VÀ_CẢM_BIẾN",
                "mat_id": act_id,
                "calc_qty": modules_count,
                "unit": "Cái",
                "note": f"Động cơ lò xo phản hồi MFD ({modules_count} bộ{mod_note})"
            })
        elif is_nrd or is_prd:
            components.append({
                "sub_key": f"{parent_id}-ECCENTRIC",
                "name": "Cơ cấu đối trọng xả áp (PRD)" if is_prd else "Cơ cấu lệch tâm / Lò xo đóng mở (NRD)",
                "category": "PHỤ_KIỆN_VAN",
                "mat_id": "ECCENTRIC_SHAFT",
                "calc_qty": modules_count,
                "unit": "Bộ",
                "note": "Cơ cấu van xả áp đối trọng" if is_prd else "Cơ cấu đóng mở một chiều"
            })
        else:
            if cross_section_mod_m2 <= 0.5:
                handle_id = "MAT-DAMPER-TAY-GAT-NHO"
                handle_name = "Tay gạt nhỏ"
            elif cross_section_mod_m2 <= 1.0:
                handle_id = "MAT-DAMPER-TAY-GAT-TRUNG-BINH"
                handle_name = "Tay gạt trung bình"
            else:
                handle_id = "MAT-DAMPER-TAY-GAT-1-1M2"
                handle_name = "Tay gạt 1 >1m2"

            components.append({
                "sub_key": f"{parent_id}-HANDLE",
                "name": handle_name,
                "category": "PHỤ_KIỆN_VAN",
                "mat_id": handle_id,
                "calc_qty": modules_count,
                "unit": "Bộ" if "Bộ" in handle_id or "NHO" in handle_id or "TRUNG" in handle_id else "Cái",
                "note": f"Tay gạt khóa vị trí nan (S={cross_section_mod_m2:.2f}m2)"
            })

        z_total_m2 = ((w_eff + h_eff) * 2.0 * 300.0 + w_eff * h_eff) / 1_000_000.0
        if is_fd_ei or is_mfd:
            area_fb10_body = ((w_mod + h_mod) * 2.0 * (l_body + 100.0) / 1_000_000.0) * 2.0 * modules_count
            components.append({
                "sub_key": f"{parent_id}-FB10-BODY",
                "name": "Tấm chống cháy dày 10mm bọc thân van FD/MFD (2 lớp)",
                "category": "VẬT_LIỆU_CÁCH_NHIỆT",
                "mat_id": "MAT-FIREBOARD-10MM-BODY",
                "calc_qty": area_fb10_body,
                "unit": "m2",
                "note": f"Bọc 2 lớp tấm 10mm quanh thân L={l_body+100}mm{mod_note}"
            })

            if is_single_blade:
                area_fb20_blade = (w_mod / 1000.0) * (h_mod / 1000.0) * modules_count
                area_fb10_blade = (w_mod / 1000.0) * (h_mod / 1000.0) * 2.0 * modules_count
                blade_fb_note = f"Cánh đơn {w_mod:.0f}x{h_mod:.0f}mm{mod_note}"
            else:
                area_fb20_blade = ((w_mod - 20.0) / 1000.0 * 0.21 * blade_factor_per_mod) * 1.1 * modules_count
                area_fb10_blade = ((w_mod / 1000.0) * 0.21 * blade_factor_per_mod * 2.0) * 1.1 * modules_count
                blade_fb_note = f"Đa cánh hệ số (H-5)/149={blade_factor_per_mod:.2f}, bản rộng 210mm, hao hụt 10%{mod_note}"

            components.append({
                "sub_key": f"{parent_id}-FB20-BLADE",
                "name": "Tấm chống cháy dày 20mm làm lõi cánh van FD/MFD",
                "category": "VẬT_LIỆU_CÁCH_NHIỆT",
                "mat_id": "MAT-FIREBOARD-20MM-BLADE",
                "calc_qty": area_fb20_blade,
                "unit": "m2",
                "note": f"Lõi cánh tấm 20mm ({blade_fb_note})"
            })
            components.append({
                "sub_key": f"{parent_id}-FB10-BLADE",
                "name": "Tấm chống cháy dày 10mm ốp 2 mặt cánh van FD/MFD",
                "category": "VẬT_LIỆU_CÁCH_NHIỆT",
                "mat_id": "MAT-FIREBOARD-10MM-BLADE",
                "calc_qty": area_fb10_blade,
                "unit": "m2",
                "note": f"Ốp 2 mặt cánh tấm 10mm ({blade_fb_note})"
            })

            components.append({
                "sub_key": f"{parent_id}-SPRING-BOX",
                "name": "Hộp lò xo van chặn lửa FD/MFD",
                "category": "PHỤ_KIỆN_VAN",
                "mat_id": "MAT-DAMPER-HOP-LO-XO",
                "calc_qty": modules_count,
                "unit": "Bộ",
                "note": f"Hộp lò xo cơ cấu đóng sập ({modules_count} bộ)"
            })
            components.append({
                "sub_key": f"{parent_id}-SILICON-BOLT",
                "name": "Silicon chống cháy + bu lông, ốc vít van FD/MFD",
                "category": "PHỤ_KIỆN_VAN",
                "mat_id": "MAT-DAMPER-SILICON-BULONG-VIT",
                "calc_qty": modules_count,
                "unit": "Bộ",
                "note": f"Keo silicon chống cháy & phụ kiện lắp ghép ({modules_count} bộ)"
            })
        elif ei_rating > 0 and not is_md and max(w_eff, h_eff) > 150.0:
            from swind_utils import get_master_price_map
            p_fb10 = get_master_price_map().get("MAT-FIREBOARD-10MM-BODY", 518500.0)
            area_fb10_ei = (z_total_m2 * 320000.0) / (p_fb10 * 1.593)
            components.append({
                "sub_key": f"{parent_id}-FB10-EI",
                "name": f"Tấm chống cháy dày 10mm bọc thân van {damper_type} (EI{ei_rating})",
                "category": "VẬT_LIỆU_CÁCH_NHIỆT",
                "mat_id": "MAT-FIREBOARD-10MM-BODY",
                "calc_qty": area_fb10_ei,
                "unit": "m2",
                "note": f"Bọc chống cháy EI{ei_rating} quanh thân van{mod_note}"
            })

        from swind_utils import get_master_price_map, get_master_bom_rules
        mat_price_map = get_master_price_map()
        damper_rules = get_master_bom_rules().get("damper_rules", {})
        mfg_markup = float(damper_rules.get("mfg_markup_factor", 1.593))

        if is_round:
            round_tbl = damper_rules.get("round_damper_table", {})
            d_key = str(int(round(d_eff)))
            z_round_m2 = (3.14 * d_eff * l_body + d_eff * d_eff) / 1_000_000.0
            if d_key in round_tbl:
                row_t = round_tbl[d_key]
                if is_fd or is_mfd:
                    base_round_sell = float(row_t.get("fd", 192000.0))
                elif is_fd_vcd:
                    base_round_sell = float(row_t.get("fd_vcd", float(row_t.get("vcd", 103000.0)) + 100000.0))
                elif is_vcd_vit:
                    base_round_sell = float(row_t.get("vcd_vit", 245000.0))
                elif is_nrd or is_prd:
                    base_round_sell = float(row_t.get("nrd", 74000.0))
                elif is_md:
                    base_round_sell = float(row_t.get("md_body", 79000.0))
                else:
                    base_round_sell = float(row_t.get("vcd", 103000.0))
            else:
                if d_eff > 500.0:
                    pkv_r = 400200.0
                    c_acc_r = 136000.0 if is_nrd else (152000.0 if is_prd else (270000.0 if is_vcd_vit else (210000.0 if (is_fd or is_mfd) else (160000.0 if is_md else 156000.0))))
                else:
                    pkv_r = 236628.0 if d_eff <= 300.0 else (271026.0 if d_eff <= 400.0 else 321300.0)
                    c_acc_r = 55000.0 if (is_nrd or is_prd) else (220000.0 if is_vcd_vit else (156000.0 if (is_fd or is_mfd) else 86000.0))
                base_round_sell = _excel_round((z_round_m2 * pkv_r + c_acc_r) * 1.15, -3)
                if is_fd_vcd:
                    base_round_sell += 100000.0
            ei_rate = float(damper_rules.get("vcd_nrd_ei_wrapping_rate_per_m2", 320000.0))
            ei_sell = (z_round_m2 * ei_rate) if (ei_rating > 0 and not (is_fd_ei or is_mfd)) else 0.0
            target_mech_sell = base_round_sell + ei_sell
        elif is_fd_ei or is_mfd:
            # Công thức gốc BG VAN chuẩn 2026 (R30..R34, R36..R41)
            # Thay thế đa thức chia 149 (legacy Haus Dalat) bằng tính từng thành phần:
            #   O  = ROUND((Z_m2 × pkv + c_acc) × 1.15, -3)   ← vỏ + phụ kiện
            #   AQ = chu_vi × 4 × 300mm × 700,000               ← tấm 10mm bọc thân (2 lớp)
            #   AR = diện tích tấm 20mm lõi cánh × 800,000
            #   AS = diện tích tấm 10mm ốp 2 mặt cánh × 700,000
            #   AY = pkv × S_m2 × 2                             ← tôn tấm bọc
            #   + 100,000 (hộp lò xo) × 1.25 (mult)
            z_mod_m2 = ((w_mod + h_mod) * 2.0 * 300.0 + w_mod * h_mod) / 1_000_000.0
            o_mod = _excel_round((z_mod_m2 * 321300.0 + 153000.0) * 1.15, -3)
            aq_mod = (w_mod + h_mod) * 4.0 * 300.0 / 1_000_000.0 * 700000.0
            if is_single_blade:
                ar_mod = (w_mod / 1000.0) * (h_mod / 1000.0) * 800000.0
                as_mod = (w_mod / 1000.0) * (h_mod / 1000.0) * 2.0 * 700000.0
            else:
                ar_mod = ((w_mod - 20.0) / 1000.0 * 0.21 * blade_factor_per_mod) * 1.1 * 800000.0
                as_mod = ((w_mod / 1000.0) * 0.21 * blade_factor_per_mod * 2.0) * 1.1 * 700000.0
            ay_mod = 321300.0 * (w_mod / 1000.0) * (h_mod / 1000.0) * 2.0
            target_mech_sell = (o_mod + aq_mod + ar_mod + as_mod + ay_mod + 100000.0) * 1.25 * modules_count
        elif is_fd_normal:
            pkv = 321300.0
            if w_eff > 2000.0 or h_eff > 2000.0:
                c_acc = 566000.0
                mult = 1.50
            elif w_eff >= 1000.0 or h_eff >= 1000.0:
                c_acc = 366000.0
                mult = 1.25
            elif h_eff > 600.0:
                c_acc = 250000.0
                mult = 1.0
            elif h_eff > 400.0:
                c_acc = 242000.0
                mult = 1.0
            elif h_eff > 250.0:
                c_acc = 191000.0
                mult = 1.0
            else:
                c_acc = 153000.0
                mult = 1.0
            target_mech_sell = _excel_round((z_total_m2 * pkv + c_acc) * 1.15, -3) * mult
        else:
            if w_eff > 2000.0 or h_eff > 2000.0:
                pkv = 321300.0
                c_acc = 622000.0 if is_prd else (452000.0 if is_nrd else (676000.0 if is_vcd_vit else (577000.0 if is_md else 545000.0)))
                mult = 1.25 if is_md else 1.50
            elif w_eff >= 1000.0 or h_eff >= 1000.0:
                pkv = 321300.0
                c_acc = 422000.0 if is_prd else (252000.0 if is_nrd else (476000.0 if is_vcd_vit else 345000.0))
                mult = 1.15 if is_prd else (1.25 if (is_nrd or is_vcd_vit or ei_rating > 0 or h_eff > 300.0) else 1.10)
            elif h_eff > 600.0:
                pkv = 321300.0
                c_acc = 252000.0 if is_prd else (152000.0 if is_nrd else (360000.0 if is_vcd_vit else 261000.0))
                mult = 1.0
            elif h_eff > 400.0:
                pkv = 271026.0
                c_acc = 232000.0 if is_prd else (148000.0 if is_nrd else (352000.0 if is_vcd_vit else 224000.0))
                mult = 1.0
            elif h_eff > 250.0:
                pkv = 236628.0
                c_acc = 154000.0 if is_prd else (97000.0 if is_nrd else (301000.0 if is_vcd_vit else (156000.0 if (h_eff >= 400.0 and w_eff >= 400.0) else 146000.0)))
                mult = 1.0
            else:
                pkv = 236628.0
                c_acc = 95000.0 if is_prd else (59000.0 if is_nrd else (213000.0 if is_vcd_vit else 101000.0))
                mult = 1.0
            base_mech_sell = _excel_round((z_total_m2 * pkv + c_acc) * 1.15, -3) * mult
            if is_fd_vcd:
                base_mech_sell += 100000.0
            ei_rate = float(damper_rules.get("vcd_nrd_ei_wrapping_rate_per_m2", 320000.0))
            ei_sell = (z_total_m2 * ei_rate) if (ei_rating > 0 and not is_md and max(w_eff, h_eff) > 150.0) else 0.0
            target_mech_sell = base_mech_sell + ei_sell

        continuous_suffixes = ("-BODY", "-BLADE", "-AXLE", "-FB10-BODY", "-FB20-BLADE", "-FB10-BLADE")
        cont_sell = 0.0
        disc_sell = 0.0
        for comp in components:
            m_id = comp["mat_id"]
            if "MAT-ACTUATOR" in m_id:
                continue
            p_unit = mat_price_map.get(m_id, 21000.0)
            c_sell = comp["calc_qty"] * p_unit * mfg_markup
            if comp["sub_key"].endswith(continuous_suffixes):
                cont_sell += c_sell
            else:
                disc_sell += c_sell

        if cont_sell > 0.0 and target_mech_sell > disc_sell:
            scale_cont = (target_mech_sell - disc_sell) / cont_sell
            for comp in components:
                if comp["sub_key"].endswith(continuous_suffixes):
                    comp["calc_qty"] *= scale_cont
        elif (cont_sell + disc_sell) > 0.0 and target_mech_sell > 0.0:
            scale_all = target_mech_sell / (cont_sell + disc_sell)
            for comp in components:
                if "MAT-ACTUATOR" not in comp["mat_id"]:
                    comp["calc_qty"] *= scale_all

        return {
            "category": "VAN_GIO",
            "modules_count": modules_count,
            "mod_w": mod_w,
            "mod_h": mod_h,
            "w_eff": w_eff,
            "h_eff": h_eff,
            "l_body": l_body,
            "thickness_body": thickness_body,
            "is_single_blade": is_single_blade,
            "components": components
        }
