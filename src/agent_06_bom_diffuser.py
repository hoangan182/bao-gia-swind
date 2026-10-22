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


class Agent06_DiffuserBOM:
    """
    SWIND-AGENT-06: Kỹ sư Dự toán Xưởng Cửa Gió Nhôm Định Hình (Diffuser BOM Maker)
    - Chuyên trách bóc tách 5 hệ profile cửa gió nhôm theo chuẩn 'BG Cửa ':
      + 'Z' (SWL Louver ngoài trời + Lưới chắn côn trùng Inox 304)
      + 'ECG' (SEEG Cửa gió sọt trứng Eggcrate)
      + 'SLB' (SLB Cửa gió Linear Bar Grille / Khe nan T)
      + 'T' (SCD Cửa gió khuếch tán 4 hướng 600x600)
      + 'BD' (SAG/DAG Cửa gió nan bầu dục 1 lớp / 2 lớp)
    - Tích hợp van OBD nhôm ('SOBD'), lưới chắn côn trùng Inox 304 ('LCCT') và phin lọc bụi G4.
    """

    @staticmethod
    def calculate_diffuser_bom(parent_id, diffuser_type, w, h, profile_type="BD", has_obd=False, has_mesh=False, has_filter=False, is_double_layer=False, is_black_2nd_layer=False):
        from swind_utils import get_master_price_map, get_master_bom_rules
        mat_price_map = get_master_price_map()
        diffuser_rules = get_master_bom_rules().get("diffuser_rules", {})
        mfg_markup = float(diffuser_rules.get("mfg_markup_factor", 1.593))
        p_alu_bd_master = mat_price_map.get("MAT-ALU-KHUNG-BD", 126000.0)
        p_alu_obd_master = mat_price_map.get("MAT-ALU-KHUNG-OBD", 133000.0)
        p_paint_master = mat_price_map.get("MAT-PAINT-POWDER", 75000.0)
        p_acc_master = mat_price_map.get("MAT-DOOR-ACCESSORY", 15000.0)
        p_core_master = mat_price_map.get("MAT-ALU-EGGCRATE-CORE", 750000.0)

        w_val = float(w) if w > 0 else 300.0
        h_val = float(h) if h > 0 else 300.0
        components = []

        k_swl = (1.28 * 1.25) / mfg_markup
        k_std = (1.33 * 1.25) / mfg_markup

        if profile_type == "LCCT":
            F, G = w_val, h_val
            D, E = w_val, h_val
            p_mesh_master = mat_price_map.get("MAT-MESH-INOX-304", 150000.0)
            target_lcct_sell = _excel_round((F / 1000.0) * (G / 1000.0) * 200000.0, 0)
            mesh_qty = max(0.001, target_lcct_sell / (p_mesh_master * mfg_markup))
            components.append({
                "sub_key": f"{parent_id}-MESH",
                "name": "Lưới chắn côn trùng Inox 304 (LCCT)",
                "category": "PHỤ_KIỆN_CỬA",
                "mat_id": "MAT-MESH-INOX-304",
                "calc_qty": mesh_qty,
                "unit": "m2",
                "note": f"Lưới chắn côn trùng {F:.0f}x{G:.0f}mm"
            })
            total_alu_kg = 0.0
            has_mesh = False
            has_obd = False
            has_filter = False

        elif profile_type == "Z":
            F, G = w_val, h_val
            D, E = max(50.0, w_val - 50.0), max(50.0, h_val - 50.0)
            N, O = F / 1000.0, G / 1000.0
            d_m, e_m = D / 1000.0, E / 1000.0
            n_nan = max(1, _excel_round((O - 0.05) / 0.045, 0))

            raw_frame_kg = 2.0 * (N + O) * 0.227
            raw_nan_only_kg = n_nan * max(0.05, N - 0.06) * 0.217
            raw_blade_kg = raw_nan_only_kg + 2.0 * (O * 1.1) * 0.08
            unrounded_swl_sell = ((raw_frame_kg + raw_blade_kg) * 165000.0 + n_nan * 170.0 + (raw_frame_kg + raw_nan_only_kg) * 20000.0) * 1.25
            target_swl_sell = _excel_round(unrounded_swl_sell, -3)
            scale_swl = (target_swl_sell / unrounded_swl_sell) if unrounded_swl_sell > 0 else 1.0
            p_alu_z_master = mat_price_map.get("MAT-ALU-KHUNG-Z-2-LOP", 126000.0)
            p_alu_nan_z_master = mat_price_map.get("MAT-ALU-NAN-Z-DAY", 126000.0)
            p_mesh_master = mat_price_map.get("MAT-MESH-INOX-304", 150000.0)

            frame_kg = raw_frame_kg * (165000.0 * 1.25 * scale_swl) / (p_alu_z_master * mfg_markup)
            blade_kg = raw_blade_kg * (165000.0 * 1.25 * scale_swl) / (p_alu_nan_z_master * mfg_markup)
            paint_m2 = (raw_frame_kg + raw_nan_only_kg) * (20000.0 * 1.25 * scale_swl) / (p_paint_master * mfg_markup)
            acc_bo = (n_nan * 170.0 * 1.25 * scale_swl) / (p_acc_master * mfg_markup)

            components.extend([
                {
                    "sub_key": f"{parent_id}-FRAME",
                    "name": "Khung nhôm định hình Louver (SWL)",
                    "category": "NHÔM_ĐỊNH_HÌNH",
                    "mat_id": "MAT-ALU-KHUNG-Z-2-LOP",
                    "calc_qty": frame_kg,
                    "unit": "kg",
                    "note": f"Khung Louver phủ bì {F:.0f}x{G:.0f}mm"
                },
                {
                    "sub_key": f"{parent_id}-BLADE",
                    "name": f"Nan Z Louver & thanh tăng cứng ({n_nan} nan)",
                    "category": "NHÔM_ĐỊNH_HÌNH",
                    "mat_id": "MAT-ALU-NAN-Z-DAY",
                    "calc_qty": blade_kg,
                    "unit": "kg",
                    "note": f"{n_nan} nan Z dày @ 0.217kg/m + thanh giằng"
                },
                {
                    "sub_key": f"{parent_id}-ACCESSORY",
                    "name": "Phụ kiện lắp ghép / Ke góc cửa gió",
                    "category": "PHỤ_KIỆN_CỬA",
                    "mat_id": "MAT-DOOR-ACCESSORY",
                    "calc_qty": acc_bo,
                    "unit": "Bộ",
                    "note": "Ke góc và vít ghép khung Louver"
                },
                {
                    "sub_key": f"{parent_id}-PAINT",
                    "name": "Sơn tĩnh điện tiêu chuẩn Polyester",
                    "category": "SƠN_TĨNH_ĐIỆN",
                    "mat_id": "MAT-PAINT-POWDER",
                    "calc_qty": paint_m2,
                    "unit": "m2",
                    "note": "Sơn tĩnh điện khung và nan Louver"
                }
            ])
            if has_mesh or diffuser_type.upper() == "LOUVER":
                target_mesh_sell = _excel_round(d_m * e_m * 150000.0, -3)
                mesh_qty = max(0.001, target_mesh_sell / (p_mesh_master * mfg_markup))
                components.append({
                    "sub_key": f"{parent_id}-MESH",
                    "name": "Lưới chắn côn trùng Inox 304 (LCCT)",
                    "category": "PHỤ_KIỆN_CỬA",
                    "mat_id": "MAT-MESH-INOX-304",
                    "calc_qty": mesh_qty,
                    "unit": "m2",
                    "note": f"Lưới chắn côn trùng cổ {D:.0f}x{E:.0f}mm"
                })
            total_alu_kg = frame_kg + blade_kg

        elif profile_type == "ECG":
            F, G = w_val, h_val
            D, E = max(50.0, w_val - 50.0), max(50.0, h_val - 50.0)
            N, O = F / 1000.0, G / 1000.0
            d_m, e_m = D / 1000.0, E / 1000.0

            raw_frame_kg = 2.0 * (N + O) * 0.202 + 2.0 * (d_m + e_m) * 0.14
            wt_luoi = d_m * e_m * (1.32 / 0.3025)
            frame_kg = raw_frame_kg * (160000.0 * 1.25) / (p_alu_bd_master * mfg_markup)
            core_m2 = (d_m * e_m) * (750000.0 * 1.25) / (p_core_master * mfg_markup)
            paint_m2 = (raw_frame_kg + wt_luoi) * (20000.0 * 1.25) / (p_paint_master * mfg_markup)
            acc_bo = (5000.0 * 1.25) / (p_acc_master * mfg_markup)

            components.extend([
                {
                    "sub_key": f"{parent_id}-FRAME",
                    "name": "Khung nhôm & nẹp U cửa sọt trứng (SEEG)",
                    "category": "NHÔM_ĐỊNH_HÌNH",
                    "mat_id": "MAT-ALU-KHUNG-BD",
                    "calc_qty": frame_kg,
                    "unit": "kg",
                    "note": f"Khung bao {F:.0f}x{G:.0f}mm + U bọc lõi"
                },
                {
                    "sub_key": f"{parent_id}-CORE",
                    "name": "Lõi nhôm sọt trứng (Eggcrate Core 12.7x12.7mm)",
                    "category": "NHÔM_ĐỊNH_HÌNH",
                    "mat_id": "MAT-ALU-EGGCRATE-CORE",
                    "calc_qty": core_m2,
                    "unit": "m2",
                    "note": f"Diện tích lõi sọt trứng {d_m*e_m:.3f}m2"
                },
                {
                    "sub_key": f"{parent_id}-ACCESSORY",
                    "name": "Phụ kiện lắp ghép / Ke góc cửa gió",
                    "category": "PHỤ_KIỆN_CỬA",
                    "mat_id": "MAT-DOOR-ACCESSORY",
                    "calc_qty": acc_bo,
                    "unit": "Bộ",
                    "note": "Ke góc chìm và vít ghép khung"
                },
                {
                    "sub_key": f"{parent_id}-PAINT",
                    "name": "Sơn tĩnh điện tiêu chuẩn Polyester",
                    "category": "SƠN_TĨNH_ĐIỆN",
                    "mat_id": "MAT-PAINT-POWDER",
                    "calc_qty": paint_m2,
                    "unit": "m2",
                    "note": "Sơn tĩnh điện khung cửa sọt trứng"
                }
            ])
            total_alu_kg = frame_kg

        elif profile_type == "SLB":
            if is_black_2nd_layer:
                D, E = max(50.0, w_val - 50.0), h_val
                F, G = w_val, h_val + 50.0
                has_obd = True
                mult_slb = 1.75 if w_val >= 5000.0 else 1.5
            else:
                F, G = w_val, h_val
                D, E = max(50.0, w_val - 50.0), max(50.0, h_val - 50.0)
                mult_slb = 1.0
            N, O = F / 1000.0, G / 1000.0
            d_m, e_m = D / 1000.0, E / 1000.0
            n_nan = max(1, _excel_round((e_m - 0.015) / 0.02))
            n_suot = max(1, _excel_round(d_m / 0.8))

            raw_frame_kg = 2.0 * (N + O) * 0.20
            raw_blade_kg = n_nan * d_m * 0.08 + n_suot * e_m * 0.07
            p_alu_slb = float(diffuser_rules.get("aluminum_selling_price_per_kg", 165000.0))
            if not is_black_2nd_layer:
                unrounded_slb_sell = ((raw_frame_kg + raw_blade_kg) * p_alu_slb + 5000.0 + (raw_frame_kg + raw_blade_kg) * 20000.0) * 1.25
                target_slb_sell = _excel_round(unrounded_slb_sell, -3)
                mult_slb = (target_slb_sell / unrounded_slb_sell) if unrounded_slb_sell > 0 else 1.0
            frame_kg = raw_frame_kg * (p_alu_slb * 1.25 * mult_slb) / (p_alu_bd_master * mfg_markup)
            blade_kg = raw_blade_kg * (p_alu_slb * 1.25 * mult_slb) / (p_alu_bd_master * mfg_markup)
            paint_m2 = (raw_frame_kg + raw_blade_kg) * (20000.0 * 1.25 * mult_slb) / (p_paint_master * mfg_markup)
            acc_bo = (5000.0 * 1.25 * mult_slb) / (p_acc_master * mfg_markup)

            components.extend([
                {
                    "sub_key": f"{parent_id}-FRAME",
                    "name": "Khung nhôm định hình Linear (SLB)",
                    "category": "NHÔM_ĐỊNH_HÌNH",
                    "mat_id": "MAT-ALU-KHUNG-BD",
                    "calc_qty": frame_kg,
                    "unit": "kg",
                    "note": f"Khung Linear {F:.0f}x{G:.0f}mm"
                },
                {
                    "sub_key": f"{parent_id}-BLADE",
                    "name": f"Nan T nhôm định hình & ty suốt ({n_nan} nan)",
                    "category": "NHÔM_ĐỊNH_HÌNH",
                    "mat_id": "MAT-ALU-NAN-T",
                    "calc_qty": blade_kg,
                    "unit": "kg",
                    "note": f"{n_nan} nan T + {n_suot} suốt liên kết"
                },
                {
                    "sub_key": f"{parent_id}-ACCESSORY",
                    "name": "Phụ kiện lắp ghép / Ke góc cửa gió",
                    "category": "PHỤ_KIỆN_CỬA",
                    "mat_id": "MAT-DOOR-ACCESSORY",
                    "calc_qty": acc_bo,
                    "unit": "Bộ",
                    "note": "Ke góc chìm và vít ghép khung"
                },
                {
                    "sub_key": f"{parent_id}-PAINT",
                    "name": "Sơn tĩnh điện tiêu chuẩn Polyester",
                    "category": "SƠN_TĨNH_ĐIỆN",
                    "mat_id": "MAT-PAINT-POWDER",
                    "calc_qty": paint_m2,
                    "unit": "m2",
                    "note": "Sơn tĩnh điện hoàn thiện (kèm sơn đen lớp 2 nếu có)"
                }
            ])
            total_alu_kg = frame_kg + blade_kg

        elif profile_type == "T":
            F, G = w_val, h_val
            D, E = (w_val - 150.0 if w_val >= 300.0 else w_val), (h_val - 150.0 if h_val >= 300.0 else h_val)
            N, O = F / 1000.0, G / 1000.0
            n_chao = max(1, int((N - 0.185) / 0.09 + 0.5))
            k_scd = float(diffuser_rules.get("scd_markup_ratio", 1.19587))

            raw_frame_kg = 2.0 * (N + O) * 0.258 + 2.0 * (1.2 * N) * 0.106
            raw_blade_kg = max(0.2, 2.0 * (0.28 * n_chao * (N + O - 0.43 * n_chao)))
            frame_kg = raw_frame_kg * k_scd
            blade_kg = raw_blade_kg * k_scd
            paint_m2 = (raw_frame_kg + raw_blade_kg) * (23100.0 / p_paint_master) * k_scd
            acc_bo = ((24000.0 + (0.0 if D * E < 1_000_000.0 else 10000.0)) / p_acc_master) * k_scd

            components.extend([
                {
                    "sub_key": f"{parent_id}-FRAME",
                    "name": "Khung nhôm cửa khuếch tán (SCD)",
                    "category": "NHÔM_ĐỊNH_HÌNH",
                    "mat_id": "MAT-ALU-KHUNG-BD",
                    "calc_qty": frame_kg,
                    "unit": "kg",
                    "note": f"Khung khuếch tán {F:.0f}x{G:.0f}mm (cổ {D:.0f}x{E:.0f}mm)"
                },
                {
                    "sub_key": f"{parent_id}-BLADE",
                    "name": f"Chao nhôm khuếch tán ({n_chao} chao)",
                    "category": "NHÔM_ĐỊNH_HÌNH",
                    "mat_id": "MAT-ALU-NAN-T",
                    "calc_qty": blade_kg,
                    "unit": "kg",
                    "note": f"{n_chao} lớp chao khuếch tán"
                },
                {
                    "sub_key": f"{parent_id}-ACCESSORY",
                    "name": "Phụ kiện lắp ghép / Ke góc cửa gió",
                    "category": "PHỤ_KIỆN_CỬA",
                    "mat_id": "MAT-DOOR-ACCESSORY",
                    "calc_qty": acc_bo,
                    "unit": "Bộ",
                    "note": "Ke góc và chốt tháo lắp lõi khuếch tán"
                },
                {
                    "sub_key": f"{parent_id}-PAINT",
                    "name": "Sơn tĩnh điện tiêu chuẩn Polyester",
                    "category": "SƠN_TĨNH_ĐIỆN",
                    "mat_id": "MAT-PAINT-POWDER",
                    "calc_qty": paint_m2,
                    "unit": "m2",
                    "note": "Sơn tĩnh điện hoàn thiện"
                }
            ])
            total_alu_kg = frame_kg + blade_kg

        else:
            F, G = w_val, h_val
            D, E = max(50.0, w_val - 50.0), max(50.0, h_val - 50.0)
            N, O = F / 1000.0, G / 1000.0
            d_m, e_m = D / 1000.0, E / 1000.0
            n_nan_1 = max(1, _excel_round((e_m - 0.015) / 0.02))

            if is_double_layer:
                n_nan_2 = max(1, _excel_round((d_m - 0.015) / 0.02))
                raw_frame_only_kg = 2.0 * (N + O) * 0.2547
                raw_frame_kg = raw_frame_only_kg
                raw_blade_kg = (n_nan_1 * d_m + n_nan_2 * e_m) * 0.058
                frame_mat_id = "MAT-ALU-KHUNG-Z-2-LOP"
                p_alu_bd = float(diffuser_rules.get("aluminum_selling_price_per_kg", 165000.0))
                raw_acc_cost = 5000.0
            else:
                raw_frame_only_kg = 2.0 * (N + O) * 0.18
                raw_frame_kg = raw_frame_only_kg + 1.0 * (O * 1.1) * 0.08
                raw_blade_kg = n_nan_1 * d_m * 0.058
                frame_mat_id = "MAT-ALU-KHUNG-BD"
                p_alu_bd = float(diffuser_rules.get("aluminum_selling_price_per_kg", 165000.0))
                raw_acc_cost = n_nan_1 * 85.0

            unrounded_bd_sell = ((raw_frame_kg + raw_blade_kg) * p_alu_bd + raw_acc_cost + (raw_frame_only_kg + raw_blade_kg) * 20000.0) * 1.25
            target_bd_sell = _excel_round(unrounded_bd_sell, -3)
            scale_bd = (target_bd_sell / unrounded_bd_sell) if unrounded_bd_sell > 0 else 1.0
            frame_kg = raw_frame_kg * (p_alu_bd * 1.25 * scale_bd) / (p_alu_bd_master * mfg_markup)
            blade_kg = raw_blade_kg * (p_alu_bd * 1.25 * scale_bd) / (p_alu_bd_master * mfg_markup)
            acc_bo = (raw_acc_cost * 1.25 * scale_bd) / (p_acc_master * mfg_markup)
            paint_m2 = (raw_frame_only_kg + raw_blade_kg) * (20000.0 * 1.25 * scale_bd) / (p_paint_master * mfg_markup)

            components.extend([
                {
                    "sub_key": f"{parent_id}-FRAME",
                    "name": f"Khung nhôm định hình ({'2 lớp' if is_double_layer else '1 lớp'} BD)",
                    "category": "NHÔM_ĐỊNH_HÌNH",
                    "mat_id": frame_mat_id,
                    "calc_qty": frame_kg,
                    "unit": "kg",
                    "note": f"Khung bao {F:.0f}x{G:.0f}mm (cổ {D:.0f}x{E:.0f}mm)"
                },
                {
                    "sub_key": f"{parent_id}-BLADE",
                    "name": f"Nan nhôm bầu dục ({n_nan_1} nan)",
                    "category": "NHÔM_ĐỊNH_HÌNH",
                    "mat_id": "MAT-ALU-NAN-BD",
                    "calc_qty": blade_kg,
                    "unit": "kg",
                    "note": "Nan bầu dục @ 0.058kg/m"
                },
                {
                    "sub_key": f"{parent_id}-ACCESSORY",
                    "name": "Phụ kiện lắp ghép / Ke góc cửa gió",
                    "category": "PHỤ_KIỆN_CỬA",
                    "mat_id": "MAT-DOOR-ACCESSORY",
                    "calc_qty": acc_bo,
                    "unit": "Bộ",
                    "note": "4 ke góc chìm và vít ghép khung"
                },
                {
                    "sub_key": f"{parent_id}-PAINT",
                    "name": "Sơn tĩnh điện tiêu chuẩn Polyester",
                    "category": "SƠN_TĨNH_ĐIỆN",
                    "mat_id": "MAT-PAINT-POWDER",
                    "calc_qty": paint_m2,
                    "unit": "m2",
                    "note": "Sơn tĩnh điện hoàn thiện"
                }
            ])
            total_alu_kg = frame_kg + blade_kg

        if has_mesh and profile_type != "Z":
            components.append({
                "sub_key": f"{parent_id}-MESH",
                "name": "Lưới chắn côn trùng Inox 304 (LCCT)",
                "category": "PHỤ_KIỆN_CỬA",
                "mat_id": "MAT-MESH-INOX-304",
                "calc_qty": max(0.01, (D * E / 1_000_000.0) * k_std),
                "unit": "m2",
                "note": f"Lưới chắn côn trùng cổ {D:.0f}x{E:.0f}mm"
            })

        if has_filter:
            components.append({
                "sub_key": f"{parent_id}-FILTER",
                "name": "Lưới lọc bụi sơ cấp G4 kèm khung nhôm",
                "category": "PHỤ_KIỆN_CỬA",
                "mat_id": "MAT-FILTER-G4",
                "calc_qty": max(0.01, (D * E / 1_000_000.0) * k_std),
                "unit": "m2",
                "note": f"Phin lọc bụi cổ {D:.0f}x{E:.0f}mm"
            })

        if has_obd:
            d_m, e_m = D / 1000.0, E / 1000.0
            obd_mult = (1.75 if w_val >= 5000.0 else 1.5) if (profile_type == "SLB" and is_black_2nd_layer) else 1.0
            raw_obd_frame_kg = 2.0 * (d_m + e_m) * 0.158
            raw_obd_blade_kg = (d_m / 0.04) * e_m * 0.10
            raw_obd_acc_cost = (d_m / 0.04) * 1500.0 + 5000.0
            unrounded_obd_sell = ((raw_obd_frame_kg + raw_obd_blade_kg) * 160000.0 + raw_obd_acc_cost) * 1.15 * obd_mult
            target_obd_sell = _excel_round(unrounded_obd_sell, -3)
            scale_obd = (target_obd_sell / unrounded_obd_sell) if unrounded_obd_sell > 0 else 1.0
            obd_frame_kg = raw_obd_frame_kg * (160000.0 * 1.15 * obd_mult * scale_obd) / (p_alu_obd_master * mfg_markup)
            obd_blade_kg = raw_obd_blade_kg * (160000.0 * 1.15 * obd_mult * scale_obd) / (p_alu_obd_master * mfg_markup)
            obd_acc_bo = (raw_obd_acc_cost * 1.15 * obd_mult * scale_obd) / (p_acc_master * mfg_markup)

            components.extend([
                {
                    "sub_key": f"{parent_id}-OBD-FRAME",
                    "name": "Khung nhôm van OBD gắn cửa (SOBD)",
                    "category": "NHÔM_ĐỊNH_HÌNH",
                    "mat_id": "MAT-ALU-KHUNG-OBD",
                    "calc_qty": obd_frame_kg,
                    "unit": "kg",
                    "note": f"Khung OBD {D:.0f}x{E:.0f}mm"
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
            ])
            total_alu_kg += (obd_frame_kg + obd_blade_kg)

        return {
            "category": "CUA_GIO",
            "total_aluminum_kg": total_alu_kg,
            "components": components
        }
