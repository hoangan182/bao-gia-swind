import json
from datetime import datetime
from pathlib import Path
from swind_checker import SwindChecker


class Agent08_QAChecker(SwindChecker):
    """
    Agent 08 - Independent 3-Layer QA Checker & Final Quotation Auditor
    Nhiệm vụ:
    - Tầng 1: Kiểm toán toàn vẹn mã vật tư (Zero missing MAT_ID) và cảnh báo đơn giá = 0.
    - Tầng 2: Kiểm toán thứ nguyên kỹ thuật & định mức cơ khí (> 0).
    - Tầng 3: Kiểm toán cấu trúc công thức sống (SUMIF, INDEX/MATCH, ROUND) trên toàn bộ 9 Sheets.
    - Tầng 4: Xuất báo cáo kiểm toán QA_Audit_Report.json & FINAL_QUOTATION_AUDIT_REPORT.json.
    """

    MFG_CATEGORIES = ("ONG_GIO", "CUA_GIO", "VAN_GIO", "CANVAS", "TIEU_AM")
    # Bất thường đơn điệu: hàng có diện tích LỚN HƠN (>= 1/AREA_RATIO lần) nhưng RẺ HƠN hẳn (< 1/PRICE_RATIO) hàng nhỏ cùng nhóm
    AREA_RATIO = 0.8
    PRICE_RATIO = 1.5

    def __init__(self, excel_filepath, project_name="Du_An_HDL_A1", wb=None):
        super().__init__(excel_filepath, wb=wb)
        self.project_name = project_name

    @staticmethod
    def _size_tier(cat, w, h, d):
        """Van có cạnh >= 1000mm / > 2000mm dùng công thức & hệ số riêng -> chỉ so sánh giá trong cùng bậc."""
        if cat != "VAN_GIO":
            return ""
        m = max(w, h, d)
        return "canh_tren_2000" if m > 2000 else ("canh_tu_1000" if m >= 1000 else "duoi_1000")

    def run_value_audit(self, items):
        """
        Tầng 4 - Kiểm toán GIÁ TRỊ (không chỉ cú pháp công thức) trên dữ liệu đã tính giá:
        - UNPRICED_ITEM (CRITICAL): Hàng sản xuất có KL > 0 nhưng đơn giá bán = 0.
        - PRICE_OUTLIER (WARNING): Trong cùng nhóm (Category + Subtype + Model + bậc kích thước van), hàng có diện tích lớn hơn
          nhưng đơn giá thấp hơn hẳn hàng nhỏ hơn -> nghi sai kích thước / ĐVT / mã.
        """
        issues = []
        groups = {}
        for it in items:
            qty = float(it.get("qty") or 0)
            if qty <= 0 or it.get("is_missing_qty"):
                continue
            unit_p = float(it.get("calc_sell_unit") or 0)
            cat = it.get("category")
            if cat in self.MFG_CATEGORIES and unit_p <= 0:
                issues.append({
                    "sheet": it.get("source_sheet"),
                    "row": it.get("source_row"),
                    "severity": "CRITICAL",
                    "error_type": "UNPRICED_ITEM",
                    "message": f"'{it.get('raw_name')}' ({cat}) có KL={qty:g} nhưng đơn giá bán = 0."
                })
                continue
            w, h, d = float(it.get("w") or 0), float(it.get("h") or 0), float(it.get("d") or 0)
            area = (w * h / 1e6) if (w > 0 and h > 0) else ((3.1416 * d * d / 4e6) if d > 0 else 0)
            if cat in ("CUA_GIO", "VAN_GIO") and area > 0 and unit_p > 0 and float(it.get("override_price") or 0) <= 0:
                sp = it.get("resolved_spec") or {}
                key = (cat, sp.get("subtype") or "", sp.get("model_std") or sp.get("model_fslf") or "", bool(d > 0 and not (w > 0 and h > 0)),
                       bool(sp.get("has_obd")), bool(sp.get("has_filter")), bool(sp.get("has_mesh")), bool(sp.get("is_box_combo")),
                       it.get("ei_rating") or sp.get("ei_rating") or 0, sp.get("motor_brand") or "", sp.get("model_code") or "",
                       str(it.get("note_boq") or "").strip().lower(),
                       self._size_tier(cat, w, h, d))
                groups.setdefault(key, []).append((area, unit_p, it))
        for key, lst in groups.items():
            lst.sort(key=lambda x: x[0])
            max_small_p = 0.0
            max_small_it = None
            j = 0
            for area, unit_p, it in lst:
                while j < len(lst) and lst[j][0] <= area * self.AREA_RATIO:
                    if lst[j][1] > max_small_p:
                        max_small_p, max_small_it = lst[j][1], lst[j][2]
                    j += 1
                if max_small_it is not None and max_small_p > unit_p * self.PRICE_RATIO:
                    issues.append({
                        "sheet": it.get("source_sheet"),
                        "row": it.get("source_row"),
                        "severity": "WARNING",
                        "error_type": "PRICE_OUTLIER",
                        "message": (f"'{it.get('raw_name')}' {it.get('w'):g}x{it.get('h'):g} giá {unit_p:,.0f}đ RẺ HƠN hẳn hàng nhỏ hơn cùng nhóm "
                                    f"R{max_small_it.get('source_row')} {max_small_it.get('w'):g}x{max_small_it.get('h'):g} giá {max_small_p:,.0f}đ — kiểm tra kích thước/ĐVT/mã.")
                    })
        return issues

    def run_final_audit(self):
        print("[*] [Agent 08 - QA Checker] Kích hoạt kiểm toán độc lập (rule-based)...")
        print(f"[*] Đang quét toàn bộ file {self.filepath}...")

        checker_report = self.run_full_audit()
        issues = checker_report.get("issues", [])

        formula_issues = [i for i in issues if i.get("error_type") in ("MISSING_FORMULA", "UNLINKED_SUMMARY", "ORPHAN_COMPONENT", "CORRUPTED_FORMULA", "MISSING_SUMIF")]
        price_issues = [i for i in issues if i.get("error_type") in ("MISSING_MAT_ID", "INVALID_MAT_ID", "ZERO_PRICE", "UNPRICED_ITEM", "PRICE_OUTLIER")]
        spec_issues = [i for i in issues if i.get("error_type") in ("ZERO_QTY_PER_ITEM",)]

        audit_report = {
            "project_name": self.project_name,
            "audit_timestamp": datetime.now().isoformat(),
            "qa_status": "PASS" if checker_report["qa_status"] == "QA_PASSED" else "REJECTED",
            "total_items_audited": checker_report["total_items_audited"],
            "total_components_audited": checker_report["total_components_audited"],
            "spec_compliance": {
                "status": "PASS" if not spec_issues else "FAIL",
                "message": "100% định mức khối lượng và thông số kỹ thuật hợp lệ." if not spec_issues else f"Phát hiện {len(spec_issues)} lỗi định mức kỹ thuật."
            },
            "formula_integrity": {
                "status": "PASS" if not formula_issues else "FAIL",
                "message": "100% công thức liên kết giữa các Sheet vẹn toàn, không có ô hard-code, không lỗi #REF!" if not formula_issues else f"Phát hiện {len(formula_issues)} lỗi liên kết công thức."
            },
            "price_consistency": {
                "status": "PASS" if not price_issues else "WARNING",
                "message": "Đơn giá đầu vào vật tư khớp 100% với Master Price Database 2026." if not price_issues else f"Phát hiện {len(price_issues)} cảnh báo thiếu mã hoặc đơn giá = 0."
            },
            "arithmetic_audit": {
                "status": "PASS" if not formula_issues and not spec_issues else "FAIL",
                "message": f"Đã kiểm toán {checker_report['total_items_audited']} hạng mục và {checker_report['total_components_audited']} cấu kiện BOM."
            },
            "issues": issues
        }

        out_dir = Path(self.filepath).parent
        report_path = out_dir / "FINAL_QUOTATION_AUDIT_REPORT.json"

        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(audit_report, f, ensure_ascii=False, indent=2)

        print(f"[OK] [Agent 08 - QA Checker] Báo cáo Final Audit lưu tại: {report_path} (Trạng thái: {audit_report['qa_status']})")
        return audit_report


if __name__ == "__main__":
    import glob
    import sys
    try:
        latest_file = sorted(glob.glob("data/projects/Haus_Dalat/Haus_Dalat_ESTIMATION_*.xlsx"))[-1]
    except IndexError:
        print("Không tìm thấy file kết quả nào để kiểm tra.")
        sys.exit(1)

    checker = Agent08_QAChecker(latest_file, project_name="Haus_Dalat")
    report = checker.run_full_audit()
    print(f"\n--- BÁO CÁO KIỂM TOÁN AGENT 08 (QA STATUS: {report['qa_status']}) ---")
    print(f"- Số lượng hạng mục (Items) đã kiểm tra: {report['total_items_audited']}")
    print(f"- Số lượng cấu kiện (BOM) đã kiểm tra: {report['total_components_audited']}")
    print(f"- Số lỗi phát hiện: {report['total_issues_found']}")
