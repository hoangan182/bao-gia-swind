#!/usr/bin/env python3
"""
SWIND BOQ Doctor — Script chẩn đoán BOQ tự động.
Chạy 1 lệnh duy nhất để quét toàn bộ file BOQ và xuất báo cáo tổng hợp
tất cả các điểm bất thường cần hỏi người dùng.

Sử dụng:
    ./venv/bin/python3 src/swind_boq_doctor.py "input/TEN_FILE_BOQ.xls"
    ./venv/bin/python3 src/swind_boq_doctor.py "input/TEN_FILE_BOQ.xlsx"
"""
import sys
import os
import json
import re

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from swind_boq_parser import SwindBOQParser
from agent_01_boq_extractor import Agent01_BOQExtractor
from swind_utils import detect_boq_header, get_subtype_rules


def run_diagnostic(boq_filepath):
    """
    Quét toàn bộ file BOQ và trả về báo cáo chẩn đoán JSON.
    5 kiểm tra:
      1. Cấu trúc cột Header nhận diện được.
      2. Dòng có hình dáng Cửa/Van nhưng trống khối lượng hoặc thiếu kích thước.
      3. Dòng chỉ có 1 kích thước, dòng Combo gộp, hoặc từ khóa chưa từng gặp.
      4. Dòng FD / MFD không ghi rõ EI hoặc chưa rõ loại động cơ.
      5. Thống kê tổng quan.
    """
    if not os.path.exists(boq_filepath):
        return {"error": f"File không tồn tại: {boq_filepath}"}

    parser = SwindBOQParser(boq_filepath)
    subtype_rules = get_subtype_rules()
    detected_sheets = parser.auto_detect_hvac_sheets()
    if not detected_sheets:
        detected_sheets = [s for s in parser.wb.sheetnames if "summary" not in s.lower()][:3]

    report = {
        "file": os.path.basename(boq_filepath),
        "sheets_detected": detected_sheets,
        "header_info": [],
        "missing_qty_or_size": [],
        "single_dim_combo_unknown": [],
        "fd_mfd_no_ei_or_motor": [],
        "summary": {}
    }

    total_items = 0
    total_issues = 0

    for sheet_name in detected_sheets:
        try:
            ws = parser.wb[sheet_name]
            header_row, col_map, hidden_rows, hidden_cols, max_scan_col = detect_boq_header(ws)

            report["header_info"].append({
                "sheet": sheet_name,
                "header_row": header_row,
                "col_map": {k: v for k, v in col_map.items()},
                "detected_columns": list(col_map.keys())
            })

            items = parser.parse_sheet(sheet_name)
            total_items += len(items)

            for idx, item in enumerate(items, 1):
                spec = Agent01_BOQExtractor.resolve_item_spec(item, subtype_rules, idx=idx)
                raw_name = str(item.get("raw_name") or item.get("name", "")).strip()
                name_lower = raw_name.lower()
                cat = item.get("category", "KHAC")
                orig_cat = item.get("orig_category", cat)
                subtype = str(spec.get("subtype") or item.get("model") or "").strip().upper()
                model = str(spec.get("model_std") or item.get("model") or subtype).strip().upper()
                w = float(item.get("w") or 0)
                h = float(item.get("h") or 0)
                d = float(item.get("d") or 0)
                qty = item.get("qty")
                ei = int(item.get("ei_rating") or 0)
                row = item.get("source_row", "?")

                # --- CHECK 2: Trống khối lượng hoặc thiếu kích thước ---
                is_missing_qty = item.get("is_missing_qty", False)
                is_missing_dims = item.get("is_missing_dims", False) or (cat in ("CUA_GIO", "VAN_GIO") and w == 0 and h == 0 and d == 0)

                if cat in ("CUA_GIO", "VAN_GIO") or orig_cat in ("CUA_GIO", "VAN_GIO"):
                    if is_missing_qty:
                        report["missing_qty_or_size"].append({
                            "sheet": sheet_name, "row": row,
                            "name": raw_name, "category": orig_cat,
                            "issue": "TRỐNG KHỐI LƯỢNG",
                            "detail": f"Qty={qty}, giữ dòng và điền đơn giá theo mặc định"
                        })
                        total_issues += 1

                    if is_missing_dims:
                        report["missing_qty_or_size"].append({
                            "sheet": sheet_name, "row": row,
                            "name": raw_name, "category": orig_cat,
                            "issue": "THIẾU KÍCH THƯỚC",
                            "detail": f"W={w}, H={h}, D={d} — chuyển sang THUONG_MAI vì không có kích thước"
                        })
                        total_issues += 1

                # --- CHECK 3: 1 kích thước (tròn D), Combo, từ khóa lạ ---
                if d > 0 and w == d and h == d and not re.search(r'(?:^|[\s_(+-])(?:[dD][nN]?|Ø|phi)\s*\d+', raw_name + " " + str(item.get("note_boq", ""))):
                    report["single_dim_combo_unknown"].append({
                        "sheet": sheet_name, "row": row,
                        "name": raw_name, "category": cat,
                        "issue": "1 KÍCH THƯỚC = TRÒN D",
                        "detail": f"D={int(d)}mm — mặc định tròn"
                    })
                    total_issues += 1

                combo_damper = item.get("combo_damper")
                if combo_damper:
                    report["single_dim_combo_unknown"].append({
                        "sheet": sheet_name, "row": row,
                        "name": raw_name, "category": cat,
                        "issue": f"COMBO GỘP: +{combo_damper}",
                        "detail": f"Dòng gộp Cửa gió + Van {combo_damper} trên 1 dòng BOQ (mã {model})"
                    })
                    total_issues += 1

                if cat == "KHAC":
                    report["single_dim_combo_unknown"].append({
                        "sheet": sheet_name, "row": row,
                        "name": raw_name, "category": cat,
                        "issue": "TỪ KHÓA LẠ — KHÔNG NHẬN DIỆN ĐƯỢC",
                        "detail": "Không khớp catalog sản xuất hay thương mại nào"
                    })
                    total_issues += 1

                # --- CHECK 4: FD/MFD không ghi EI hoặc không rõ động cơ ---
                if cat == "VAN_GIO" and subtype in ("FD", "MFD", "MFSD", "MFD_LOUVER"):
                    if subtype == "FD" and ei == 0:
                        report["fd_mfd_no_ei_or_motor"].append({
                            "sheet": sheet_name, "row": row,
                            "name": raw_name, "model": model,
                            "issue": "FD KHÔNG GHI EI",
                            "detail": f"Độ dày={spec.get('thk_col')}mm, L={spec.get('l_col')}mm (Mặc định Cột O tôn 1.15mm nếu không yêu cầu EI)"
                        })
                        total_issues += 1

                    if subtype in ("MFD", "MFSD", "MFD_LOUVER"):
                        motor_hint = ""
                        search_txt = (name_lower + " " + str(item.get("model", "")).lower() + " " + str(item.get("note_boq", "")).lower())
                        if any(k in search_txt for k in ("klb", "viweco", "v6006", "1.03")):
                            motor_hint = "KLB"
                        elif any(k in search_txt for k in ("honeywell", "honey well", "ms4609", "1.04")):
                            motor_hint = "HONEYWELL"
                        elif any(k in search_txt for k in ("belimo", "bfn", "fslf", "1.01", "1.02")):
                            motor_hint = "BELIMO"

                        if not motor_hint:
                            report["fd_mfd_no_ei_or_motor"].append({
                                "sheet": sheet_name, "row": row,
                                "name": raw_name, "model": model,
                                "issue": "MFD KHÔNG RÕ LOẠI ĐỘNG CƠ",
                                "detail": "Mặc định: BELIMO BFN24 (model 1.02). Cần xác nhận hãng motor nếu khác."
                            })
                            total_issues += 1

                        if ei == 0:
                            report["fd_mfd_no_ei_or_motor"].append({
                                "sheet": sheet_name, "row": row,
                                "name": raw_name, "model": model,
                                "issue": "MFD KHÔNG GHI EI",
                                "detail": f"Motor: {motor_hint or 'BELIMO (mặc định)'}. Mặc định tính chuẩn EI."
                            })
                            total_issues += 1

        except Exception as e:
            report["header_info"].append({
                "sheet": sheet_name,
                "error": str(e)
            })

    report["summary"] = {
        "total_sheets": len(detected_sheets),
        "total_items": total_items,
        "total_issues": total_issues,
        "missing_qty_or_size_count": len(report["missing_qty_or_size"]),
        "single_dim_combo_unknown_count": len(report["single_dim_combo_unknown"]),
        "fd_mfd_no_ei_count": len(report["fd_mfd_no_ei_or_motor"])
    }

    return report


def print_report(report):
    """In báo cáo chẩn đoán ra console theo format dễ đọc."""
    if "error" in report:
        print(f"❌ LỖI: {report['error']}")
        return

    print(f"\n{'='*70}")
    print(f"📋 BÁO CÁO CHẨN ĐOÁN BOQ: {report['file']}")
    print(f"{'='*70}")

    # 1. Header Info
    print(f"\n📌 1. CẤU TRÚC CỘT HEADER")
    for hi in report["header_info"]:
        if "error" in hi:
            print(f"   ❌ Sheet '{hi['sheet']}': LỖI — {hi['error']}")
        else:
            cols_str = ", ".join(f"{k}=Col{v}" for k, v in hi["col_map"].items())
            print(f"   ✅ Sheet '{hi['sheet']}': Header ở dòng {hi['header_row']}")
            print(f"      Cột nhận diện: {cols_str}")

    # 2. Missing qty/size
    items = report["missing_qty_or_size"]
    print(f"\n📌 2. TRỐNG KHỐI LƯỢNG / THIẾU KÍCH THƯỚC ({len(items)} dòng)")
    for it in items:
        print(f"   ⚠️  [{it['sheet']}] Dòng {it['row']}: {it['issue']}")
        print(f"       Tên: {it['name'][:80]}")
        print(f"       Chi tiết: {it['detail']}")

    # 3. Single dim / Combo / Unknown
    items = report["single_dim_combo_unknown"]
    print(f"\n📌 3. KÍCH THƯỚC ĐƠN / COMBO / TỪ KHÓA LẠ ({len(items)} dòng)")
    for it in items:
        print(f"   🔍 [{it['sheet']}] Dòng {it['row']}: {it['issue']}")
        print(f"       Tên: {it['name'][:80]}")
        print(f"       Chi tiết: {it['detail']}")

    # 4. FD/MFD no EI
    items = report["fd_mfd_no_ei_or_motor"]
    print(f"\n📌 4. FD/MFD KHÔNG GHI EI HOẶC CHƯA RÕ ĐỘNG CƠ ({len(items)} dòng)")
    for it in items:
        print(f"   🔥 [{it['sheet']}] Dòng {it['row']}: {it['issue']}")
        print(f"       Tên: {it['name'][:80]}")
        print(f"       Model: {it['model']} — {it['detail']}")

    # Summary
    s = report["summary"]
    print(f"\n{'='*70}")
    print(f"📊 TỔNG KẾT: {s['total_sheets']} sheet, {s['total_items']} hạng mục, {s['total_issues']} điểm cần xác nhận")
    if s['total_issues'] == 0:
        print("✅ Không phát hiện bất thường — có thể chạy báo giá ngay!")
    else:
        print("⚠️  Cần xác nhận các điểm trên trước khi chạy báo giá.")
    print(f"{'='*70}\n")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Sử dụng: ./venv/bin/python3 src/swind_boq_doctor.py \"input/TEN_FILE_BOQ.xlsx\"")
        sys.exit(1)

    boq_path = sys.argv[1]
    report = run_diagnostic(boq_path)
    print_report(report)

    # Lưu JSON report vào thư mục dự án trong data/projects/ (không làm rác thư mục input/)
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    base_name = os.path.splitext(os.path.basename(boq_path))[0]
    proj_dir = os.path.join(base_dir, "data", "projects", base_name)
    os.makedirs(proj_dir, exist_ok=True)
    json_path = os.path.join(proj_dir, "BOQ_DOCTOR_REPORT.json")
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    print(f"💾 Báo cáo JSON đã lưu: {json_path}")
