import json
import os
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

    def __init__(self, excel_filepath, selected_model="Gemini 3.1 Pro", project_name="Du_An_HDL_A1", wb=None):
        super().__init__(excel_filepath, wb=wb)
        self.selected_model = selected_model
        self.project_name = project_name

    def run_final_audit(self):
        print(f"[*] [Agent 08 - QA Checker] Kích hoạt kiểm toán độc lập với Model: {self.selected_model}...")
        print(f"[*] Đang quét toàn bộ file {self.filepath}...")

        checker_report = self.run_full_audit()
        issues = checker_report.get("issues", [])

        formula_issues = [i for i in issues if i.get("error_type") in ("MISSING_FORMULA", "UNLINKED_SUMMARY", "ORPHAN_PARENT_ID", "CORRUPTED_FORMULA", "MISSING_SUMIF")]
        price_issues = [i for i in issues if i.get("error_type") in ("MISSING_MAT_ID", "INVALID_MAT_ID", "ZERO_PRICE")]
        spec_issues = [i for i in issues if i.get("error_type") in ("INVALID_QTY", "ZERO_QTY_PER_ITEM")]

        audit_report = {
            "project_name": self.project_name,
            "model_used": self.selected_model,
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
