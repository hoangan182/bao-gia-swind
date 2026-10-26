import json
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


class Agent03_InputAuditor:
    """
    Agent 03 - Input Auditor (Kiểm toán viên Đầu vào Đa Mô hình 4 Trục)
    Nhiệm vụ:
    - Thẩm định 4 trục kỹ thuật trước khi tính giá:
      1. Số lượng & Độ toàn vẹn (Quantity & Completeness)
      2. Kích thước hình học & Cảnh báo gõ nhầm kích thước lẻ (ví dụ 110x350 thay vì 1100x350)
      3. Bẫy đơn vị tính (UOM Trap Audit: m2 vs Cái/Bộ)
      4. Phụ kiện & Tiêu chuẩn PCCC (EI60/90/120, Cầu chì 72°C)
    - Xuất biên bản kiểm toán INPUT_AUDIT_REPORT.json.
    """

    def __init__(self, selected_model="Gemini 2.5 Pro", project_name="Du_An_HDL_A1"):
        self.selected_model = selected_model
        self.project_name = project_name

    def run_audit(self, extracted_items):
        print(f"[*] [Agent 03 - Input Auditor] Kích hoạt kiểm toán đầu vào với Model: {self.selected_model}...")

        audit_report = {
            "project_name": self.project_name,
            "model_used": self.selected_model,
            "total_items": len(extracted_items),
            "pass_items": 0,
            "requires_mapping_items": 0,
            "critical_errors": [],
            "warnings": [],
            "items_detail": []
        }

        for item in extracted_items:
            row_idx = item["row_index"]
            name = item["raw_name"]
            dims = item["parsed_dims"]
            qty = item["raw_qty"]
            unit = item["raw_unit"].lower()
            std_id = item["standard_id"]
            spec = item["spec_features"]
            status = item["status"]

            # 1. Trục 1: Kiểm tra Số lượng & Toàn vẹn (Quantity & Completeness)
            clean_qty_str = str(qty).replace(",", ".").strip()
            is_valid_qty = False
            try:
                qty_val = float(clean_qty_str)
                if qty_val >= 0:
                    is_valid_qty = True
            except ValueError:
                is_valid_qty = False

            if not is_valid_qty:
                audit_report["critical_errors"].append({
                    "row": row_idx,
                    "item": name,
                    "issue": f"Số lượng không hợp lệ hoặc bị trống ('{qty}'). Không thể lập dự toán."
                })

            # 2. Trục 2: Kiểm tra Kỹ thuật Kích thước (Geometric & HVAC Logic + Odd Dimension Guard)
            if not dims:
                audit_report["warnings"].append({
                    "row": row_idx,
                    "item": name,
                    "issue": "Không bóc tách được kích thước (W, H hoặc D). Cần bổ sung quy cách."
                })
            else:
                w = dims.get("w", 0)
                h = dims.get("h", 0)
                d = dims.get("d", 0)

                # Cảnh báo tỷ lệ bất thường
                if w > 0 and h > 0 and h > w * 3:
                    audit_report["warnings"].append({
                        "row": row_idx,
                        "item": name,
                        "issue": f"Tỷ lệ chiều cao vượt trội ({w}x{h}). Thường W > H trong hệ thống gió."
                    })

                # Cảnh báo nghi ngờ gõ thiếu số 0 ở kích thước lẻ (ví dụ 110x350 thay vì 1100x350)
                if w > 0 and h > 0 and ((w % 50 != 0 and w < 200) or (h % 50 != 0 and h < 200)):
                    audit_report["warnings"].append({
                        "row": row_idx,
                        "item": name,
                        "issue": f"Kích thước lẻ bất thường ({int(w)}x{int(h)}mm). Nghi ngờ BOQ gốc gõ thiếu số 0 (ví dụ {int(w)*10}x{int(h)}mm)."
                    })

                # Cảnh báo van kích thước lớn cần gia cố / chia modul
                if std_id and ("VCD" in std_id or "VAN_GIO" in std_id) and (w > 1200 or h > 1000):
                    audit_report["warnings"].append({
                        "row": row_idx,
                        "item": name,
                        "issue": f"Van gió quá khổ ({w}x{h}). Theo tiêu chuẩn kỹ thuật cần chia nhiều khoang/modul hoặc tăng độ dày tôn."
                    })

            # 3. Trục 3: Rà soát Đơn vị tính & Bẫy Đơn giá (UOM Trap Audit)
            if unit in ["m2", "m²", "mét vuông"]:
                if std_id and ("VCD" in std_id or "VAN_GIO" in std_id):
                    audit_report["critical_errors"].append({
                        "row": row_idx,
                        "item": name,
                        "issue": "BẪY TÀI CHÍNH: Van gió ghi ĐVT là m2 thay vì Cái/Bộ. Cần xác nhận quy đổi tránh sai giá!"
                    })
                elif std_id and "LOUVER" in std_id:
                    if dims.get("w") and dims.get("h"):
                        area_each = (dims["w"] * dims["h"]) / 1_000_000
                        item["suggested_area_m2"] = round(area_each, 3)

            # 4. Trục 4: Thẩm tra Phụ kiện & PCCC (Spec Check)
            if std_id and "FD" in std_id:
                if not spec.get("fire_rating"):
                    audit_report["warnings"].append({
                        "row": row_idx,
                        "item": name,
                        "issue": "Van dập lửa chưa rõ tiêu chuẩn PCCC (Cầu chì 72°C hay EI bao nhiêu phút). Mặc định tính loại cầu chì 72°C."
                    })

            if not std_id:
                audit_report["requires_mapping_items"] += 1
            elif status == "PASS":
                audit_report["pass_items"] += 1

            audit_report["items_detail"].append(item)

        out_dir = BASE_DIR / "data" / "projects" / self.project_name
        os.makedirs(out_dir, exist_ok=True)
        report_path = out_dir / "INPUT_AUDIT_REPORT.json"

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(audit_report, f, ensure_ascii=False, indent=2)

        print(f"[OK] [Agent 03 - Input Auditor] Đã hoàn thành kiểm toán! Báo cáo lưu tại: {report_path}")
        print(f"     ➔ Tổng: {audit_report['total_items']} dòng | Đạt chuẩn: {audit_report['pass_items']} | Cần ánh xạ: {audit_report['requires_mapping_items']}")
        print(f"     ➔ Cảnh báo: {len(audit_report['warnings'])} | Lỗi nghiêm trọng: {len(audit_report['critical_errors'])}")

        return audit_report

    def audit_parsed_boq_items(self, all_items):
        extracted_items = []
        for item in all_items:
            w = item.get("w", 0)
            h = item.get("h", 0)
            d = item.get("d", 0)
            dims = {}
            if d > 0:
                dims = {"d": d}
            elif w > 0 or h > 0:
                dims = {"w": w, "h": h}
            cat = item.get("category", "KHAC")
            raw_low = (item.get("raw_name", "") + " " + str(item.get("model", ""))).lower()
            fire_rating = "EI60" if "ei60" in raw_low else "EI90" if "ei90" in raw_low else "EI120" if "ei120" in raw_low else "72C" if ("72" in raw_low or "cầu chì" in raw_low) else None
            extracted_items.append({
                "row_index": item.get("source_row", 0),
                "raw_name": item.get("raw_name", item.get("name", "")),
                "parsed_dims": dims,
                "raw_qty": item.get("qty", 0),
                "raw_unit": item.get("unit", ""),
                "standard_id": cat if cat != "KHAC" else None,
                "spec_features": {"fire_rating": fire_rating},
                "status": "PASS" if cat != "KHAC" else "REQUIRES_MAPPING"
            })
        return self.run_audit(extracted_items)
