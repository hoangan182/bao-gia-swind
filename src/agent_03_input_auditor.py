import json
import os
import re
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent


def is_odd_edge(v):
    """Cạnh 100..199mm không chia hết cho 50 → nghi BOQ gõ thiếu số 0 (110x350 thay vì 1100x350).
    Cạnh < 100mm (khe cửa gió 60/80mm) là bình thường."""
    try:
        v = float(v or 0)
    except (TypeError, ValueError):
        return False
    return 100 <= v < 200 and v % 50 != 0


_CONFIRMED_SIZES = None


def is_confirmed_size(w, h):
    """Kích thước lẻ User đã xác nhận đúng (data/master_data/odd_size_confirmed.json), so cả 2 chiều."""
    global _CONFIRMED_SIZES
    if _CONFIRMED_SIZES is None:
        _CONFIRMED_SIZES = set()
        try:
            with open(BASE_DIR / "data" / "master_data" / "odd_size_confirmed.json", encoding="utf-8") as f:
                for e in json.load(f).get("kich_thuoc_da_xac_nhan", []):
                    a, b = (int(float(x)) for x in str(e["kt"]).lower().split("x"))
                    _CONFIRMED_SIZES.add((min(a, b), max(a, b)))
        except (OSError, ValueError, KeyError):
            pass
    try:
        a, b = int(float(w or 0)), int(float(h or 0))
    except (TypeError, ValueError):
        return False
    return (min(a, b), max(a, b)) in _CONFIRMED_SIZES


def boq_size(item):
    """Kích thước như BOQ ghi (trước khi cộng viền KTC → mặt). Parser cộng viền ngay khi đọc và giữ
    kích thước cổ ở w_neck/h_neck (dòng thường) hoặc w_damper/h_damper (dòng combo cửa + van)
    — VD Ghi chú 'KT cổ' 1000x135 → mặt 1050x185, kiểm kích thước lẻ vẫn xét 1000x135 (User chốt 2026-11-13, GMS TASEOC)."""
    w, h = item.get("w") or 0, item.get("h") or 0
    if item.get("is_ktc_applied"):
        if item.get("w_neck") or item.get("h_neck"):
            return item.get("w_neck") or 0, item.get("h_neck") or 0
        if item.get("w_damper") or item.get("h_damper"):
            return item.get("w_damper") or 0, item.get("h_damper") or 0
    return w, h


def odd_size_flag(w, h, d=0):
    """Ghi chú tô màu trên Sheet BG cho dòng kích thước lẻ — vẫn báo giá theo kích thước BOQ
    (User chốt 2026-11-13, GMS TASEOC VGCG R57/R58 'Cửa gió nan thẳng 1000x135').
    Hàng tròn (d > 0, VD Ventcap D110 / D160) không xét — đường kính lẻ là bình thường."""
    try:
        w, h, d = float(w or 0), float(h or 0), float(d or 0)
    except (TypeError, ValueError):
        return ""
    if d > 0:
        return ""
    if w > 0 and h > 0 and (is_odd_edge(w) or is_odd_edge(h)) and not is_confirmed_size(w, h):
        return f"⚠️ KÍCH THƯỚC LẺ {int(w)}x{int(h)}: nghi BOQ gõ thiếu số 0 — đang báo theo kích thước BOQ, xin xác nhận"
    return ""


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

    def __init__(self, project_name="Du_An_HDL_A1", out_dir=None):
        self.project_name = project_name
        self.out_dir = out_dir

    def run_audit(self, extracted_items):
        print("[*] [Agent 03 - Input Auditor] Kích hoạt kiểm toán đầu vào 4 trục (rule-based)...")

        audit_report = {
            "project_name": self.project_name,
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

                # Cảnh báo tỷ lệ bất thường
                if w > 0 and h > 0 and h > w * 3:
                    audit_report["warnings"].append({
                        "row": row_idx,
                        "item": name,
                        "issue": f"Tỷ lệ chiều cao vượt trội ({w}x{h}). Thường W > H trong hệ thống gió."
                    })

                # Cảnh báo nghi ngờ gõ thiếu số 0 ở kích thước lẻ (ví dụ 110x350 thay vì 1100x350).
                # Chỉ xét cạnh 100..199mm không chia hết cho 50 (cạnh < 100mm như khe cửa gió 60/80mm là bình thường).
                if w > 0 and h > 0 and (is_odd_edge(w) or is_odd_edge(h)) and not is_confirmed_size(w, h):
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
            name_low = str(name).lower()
            is_fd = std_id == "VAN_GIO" and (re.search(r'\b(fd|mfd|sfd|msfd|mfsd)\b', name_low) or "chặn lửa" in name_low or "ngăn cháy" in name_low)
            if is_fd:
                if not spec.get("fire_rating"):
                    audit_report["warnings"].append({
                        "row": row_idx,
                        "item": name,
                        "issue": "Van chặn lửa chưa ghi tiêu chuẩn PCCC (EI bao nhiêu phút). FD không ghi EI → báo FD thường không bọc (User chốt 2026-11-13); MFD theo mã mặc định."
                    })

            if not std_id:
                audit_report["requires_mapping_items"] += 1
            elif status == "PASS":
                audit_report["pass_items"] += 1

            audit_report["items_detail"].append(item)

        out_dir = Path(self.out_dir) if self.out_dir else BASE_DIR / "output" / self.project_name / "internal_estimation"
        os.makedirs(out_dir, exist_ok=True)
        report_path = out_dir / "INPUT_AUDIT_REPORT.json"

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(audit_report, f, ensure_ascii=False, indent=2)

        print(f"[OK] [Agent 03 - Input Auditor] Đã hoàn thành kiểm toán! Báo cáo lưu tại: {report_path}")
        print(f"     ➔ Tổng: {audit_report['total_items']} dòng | Đạt chuẩn: {audit_report['pass_items']} | Cần ánh xạ: {audit_report['requires_mapping_items']}")
        print(f"     ➔ Cảnh báo: {len(audit_report['warnings'])} | Lỗi nghiêm trọng: {len(audit_report['critical_errors'])}")
        for ce in audit_report["critical_errors"][:10]:
            print(f"     ⛔ [Lỗi nghiêm trọng] Dòng {ce['row']}: '{ce['item']}' — {ce['issue']}")
        warn_groups = {}
        for wn in audit_report["warnings"]:
            key = re.sub(r'\(.*?\)', '(...)', wn["issue"])
            warn_groups.setdefault(key, []).append(wn["row"])
        for key, rows in sorted(warn_groups.items(), key=lambda kv: -len(kv[1]))[:6]:
            rows_s = ", ".join(str(x) for x in rows[:8]) + (" ..." if len(rows) > 8 else "")
            print(f"     ⚠️ [{len(rows)} dòng] {key} — Dòng: {rows_s}")

        return audit_report

    def audit_parsed_boq_items(self, all_items):
        extracted_items = []
        for item in all_items:
            w, h = boq_size(item)
            d = item.get("d", 0)
            dims = {}
            if d > 0:
                dims = {"d": d}
            elif w > 0 or h > 0:
                dims = {"w": w, "h": h}
            cat = item.get("category", "KHAC")
            raw_low = " ".join(str(item.get(k) or "") for k in ("raw_name", "model", "note_boq", "section")).lower()
            m_ei = re.search(r'(?<![a-z])ei\s*[-:]?\s*(\d{2,3})\b', raw_low)
            fire_rating = (f"EI{m_ei.group(1)}" if m_ei else None) or (f"EI{item.get('ei_rating')}" if item.get("ei_rating") else None) \
                or ("72C" if re.search(r'\b7[0-4]\s*(?:°|độ|do)?\s*c\b', raw_low) or "cầu chì" in raw_low else None)
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
