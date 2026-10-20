from swind_utils import get_master_bom_rules

class Agent04_DuctworkBOM:
    """
    SWIND-AGENT-04: Kỹ sư Dự toán Xưởng Ống Gió, Khớp Nối Mềm & Tiêu Âm (Ductwork BOM Maker)
    - Chuyên trách bóc tách: Ống gió vuông/tròn, phụ kiện ống gió, khớp nối mềm Canvas, vách/hộp tiêu âm.
    - Đọc định mức kỹ thuật từ file Master Data (master_bom_rules.json) đã giải mã sẵn.
    - Không hardcode đơn giá: chỉ trả về khối lượng vật lý và mã MAT_ID chuẩn.
    """

    @staticmethod
    def get_duct_thickness(max_dim):
        """
        Xác định độ dày tôn ống gió vuông theo TCVN 5687:2010 (từ Master BOM Rules).
        """
        rules = get_master_bom_rules().get("ductwork_rules", {})
        thresholds = rules.get("tcvn_5687_thickness_thresholds", [])
        for th in thresholds:
            if max_dim <= th.get("max_dim", 0):
                return float(th.get("thickness", 0.48))
        if max_dim <= 450: return 0.48
        if max_dim <= 1000: return 0.58
        if max_dim <= 1500: return 0.75
        if max_dim <= 2000: return 0.95
        return float(rules.get("default_max_thickness", 1.15))

    @staticmethod
    def calculate_duct_bom(parent_id, w, h, l=1120, brand="PN", flange_type="TDF", is_fitting=False, unit="m2", specified_thickness=None):
        """
        Bóc tách Ống Gió Vuông đa thứ nguyên (Unit-Normalized):
        - Nếu ĐVT là m²: Tính định mức lượng tôn (kg) cho 1 m² ống thành phẩm.
        - Nếu ĐVT là m/md: Tính định mức lượng tôn (kg) cho 1 mét dài tuyến ống.
        - Nếu ĐVT là cái/đoạn: Tính định mức lượng tôn (kg) cho 1 đoạn ống cụ thể (WxHxL).
        - Nếu ĐVT là lô: Vật tư phụ trọn gói.
        """
        rules = get_master_bom_rules().get("ductwork_rules", {})
        if specified_thickness and specified_thickness > 0:
            thickness = float(specified_thickness)
        else:
            max_dim = max(w, h)
            thickness = Agent04_DuctworkBOM.get_duct_thickness(max_dim if max_dim > 0 else 500)

        if brand.upper() == "PN":
            pn_map_raw = rules.get("pn_nominal_map", {})
            if pn_map_raw:
                thickness = float(pn_map_raw.get(f"{thickness:.2f}", thickness))
            else:
                pn_nominal_map = {0.50: 0.48, 0.60: 0.58, 0.80: 0.75, 1.00: 0.95, 1.20: 1.15, 1.40: 1.38, 1.50: 1.48}
                thickness = pn_nominal_map.get(round(thickness, 2), thickness)

        steel_density = float(rules.get("steel_density", 7.85))
        density = steel_density * thickness
        wastage = float(rules.get("wastage_fitting", 1.15)) if is_fitting else float(rules.get("wastage_straight", 1.05))
        mat_id = f"MAT-STEEL-{brand.upper()}-{thickness:.2f}"

        unit_clean = (unit or "m2").strip().lower()
        components = []

        if unit_clean in ["m2", "m²", "sqm"]:
            flange_seam_ratio = float(rules.get("flange_seam_ratio_m2", 1.08))
            weight_kg = 1.0 * density * flange_seam_ratio * wastage
            components.append({
                "sub_key": f"{parent_id}-BODY",
                "name": f"Tôn mạ kẽm {brand} ({thickness:.2f}mm) - Định mức m²",
                "category": "TÔN_CUỘN_MẠ_KẼM",
                "mat_id": mat_id,
                "calc_qty": weight_kg,
                "unit": "kg",
                "area_m2": 1.0,
                "wastage": wastage,
                "note": f"Định mức tôn cho 1m² ống: phôi x{flange_seam_ratio}, hao hụt x{wastage}"
            })

        elif unit_clean in ["m", "md", "mét", "meter"]:
            w_calc = w if w > 0 else 500
            h_calc = h if h > 0 else 300
            seam_allowance_mm = 30
            flange_allowance_mm = 70 if flange_type == "TDF" else 50
            peri_cut_m = (2 * (w_calc + h_calc) + seam_allowance_mm) / 1000.0
            len_cut_m = (1000.0 + flange_allowance_mm) / 1000.0
            area_m2 = peri_cut_m * len_cut_m
            weight_kg = area_m2 * density * wastage
            components.append({
                "sub_key": f"{parent_id}-BODY",
                "name": f"Tôn mạ kẽm {brand} ({thickness:.2f}mm) - Định mức mét dài",
                "category": "TÔN_CUỘN_MẠ_KẼM",
                "mat_id": mat_id,
                "calc_qty": weight_kg,
                "unit": "kg",
                "area_m2": area_m2,
                "wastage": wastage,
                "note": f"Quy cách {int(w_calc)}x{int(h_calc)}mm, Chu vi phôi {peri_cut_m:.3f}m"
            })

        elif unit_clean in ["lô", "lo", "gói", "goi", "hệ", "he"]:
            weight_kg = 1.0
            components.append({
                "sub_key": f"{parent_id}-ACC",
                "name": f"Gói vật tư phụ gia công ống gió ({thickness:.2f}mm)",
                "category": "VẬT_TƯ_PHỤ",
                "mat_id": f"MAT-ACC-DUCT-{thickness:.2f}",
                "calc_qty": 1.0,
                "unit": "Lô",
                "area_m2": 0.0,
                "wastage": 1.0,
                "note": "Trọn gói theo dự án"
            })

        else:
            w_calc = w if w > 0 else 500
            h_calc = h if h > 0 else 500
            l_calc = l if l > 0 else 1120
            flange_allowance_mm = 70 if flange_type == "TDF" else 50
            seam_allowance_mm = 30
            peri_cut_m = (2 * (w_calc + h_calc) + seam_allowance_mm) / 1000.0
            len_cut_m = (l_calc + flange_allowance_mm) / 1000.0
            area_m2 = peri_cut_m * len_cut_m
            weight_kg = area_m2 * density * wastage
            components.append({
                "sub_key": f"{parent_id}-BODY",
                "name": f"Thân ống gió bích {flange_type} ({thickness:.2f}mm)",
                "category": "TÔN_CUỘN_MẠ_KẼM",
                "mat_id": mat_id,
                "calc_qty": weight_kg,
                "unit": "kg",
                "area_m2": area_m2,
                "wastage": wastage,
                "note": f"Kích thước {int(w_calc)}x{int(h_calc)}x{int(l_calc)}mm, Phôi {peri_cut_m:.3f}x{len_cut_m:.3f}m"
            })

        return {
            "category": "ONG_GIO",
            "thickness": thickness,
            "weight_kg": weight_kg,
            "components": components
        }

    @staticmethod
    def calculate_canvas_bom(parent_id, w, h, l=200):
        """
        Bóc tách Khớp nối mềm (Canvas).
        """
        peri_m = 2 * (w + h) / 1000.0
        len_m = l / 1000.0 if l > 0 else 0.2
        area_m2 = peri_m * len_m * 1.2

        components = [
            {
                "sub_key": f"{parent_id}-CANVAS",
                "name": "Cuộn vải bạt bọc cách nhiệt/chống cháy",
                "category": "VẬT_TƯ_BẠT",
                "mat_id": "CANVAS_FIRE_RESISTANT",
                "calc_qty": area_m2,
                "unit": "m2",
                "note": f"Chu vi {peri_m:.2f}m x Dài {len_m:.2f}m"
            },
            {
                "sub_key": f"{parent_id}-FLANGE",
                "name": "Nẹp bích tôn cố định",
                "category": "TÔN_CUỘN_MẠ_KẼM",
                "mat_id": "MAT-STEEL-PN-0.58",
                "calc_qty": peri_m * 0.1 * 7.85 * 0.58 * 1.1,
                "unit": "kg",
                "note": f"Nẹp viền {peri_m:.2f}m"
            }
        ]
        return {
            "category": "KHAC",
            "components": components
        }

    @staticmethod
    def calculate_acoustic_partition_bom(parent_id, w, h, l=1000, unit="Bộ", brand="PN", include_casing=None):
        """
        Bóc tách Vách ngăn / Hộp tiêu âm (Acoustic Partition / Silencer Box - Cấu tạo 3 lớp).
        """
        unit_clean = (unit or "Bộ").strip().lower()
        if unit_clean in ["m2", "m²", "sqm", "mét vuông"]:
            area_m2 = 1.0
            include_casing = False
        else:
            area_m2 = (w * h) / 1_000_000.0
            if include_casing is None:
                include_casing = True

        components = []
        if include_casing:
            thk = Agent04_DuctworkBOM.get_duct_thickness(max(w, h) if max(w, h) > 0 else 1000)
            components.append({
                "sub_key": f"{parent_id}-BODY",
                "name": f"Vỏ tôn hộp tiêu âm {brand} ({thk:.2f}mm)",
                "category": "TÔN_CUỘN_MẠ_KẼM",
                "mat_id": f"MAT-STEEL-{brand.upper()}-{thk:.2f}",
                "calc_qty": area_m2 * 1.15 * thk * 7.85,
                "unit": "kg",
                "note": f"Vỏ tôn bao ngoài ({area_m2:.2f}m2)"
            })

        components.extend([
            {
                "sub_key": f"{parent_id}-ROCKWOOL",
                "name": "Bông Rockwool tỷ trọng 50kg/m3 dày 50mm",
                "category": "VẬT_LIỆU_TIÊU_ÂM",
                "mat_id": "ROCKWOOL_50MM_50KG",
                "calc_qty": area_m2 * 1.1,
                "unit": "m2",
                "note": f"Diện tích tiêu âm {area_m2:.2f}m2"
            },
            {
                "sub_key": f"{parent_id}-GLASSCLOTH",
                "name": "Vải thủy tinh bọc tiêu âm",
                "category": "VẬT_LIỆU_TIÊU_ÂM",
                "mat_id": "GLASS_CLOTH",
                "calc_qty": area_m2 * 1.1,
                "unit": "m2",
                "note": f"Diện tích tiêu âm {area_m2:.2f}m2"
            },
            {
                "sub_key": f"{parent_id}-PERFORATED",
                "name": "Tôn đục lỗ tiêu âm",
                "category": "VẬT_LIỆU_TIÊU_ÂM",
                "mat_id": "PERFORATED_SHEET",
                "calc_qty": area_m2 * 1.1,
                "unit": "m2",
                "note": "Bọc mặt trong"
            }
        ])
        return {
            "category": "TIEU_AM",
            "components": components
        }
