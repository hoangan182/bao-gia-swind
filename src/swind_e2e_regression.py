"""
Kiểm thử hồi quy End-to-End toàn bộ file BOQ trong input/.

Chạy swind_master_runner.py trên từng file BOQ, trích Bảng Tổng Hợp (Số dòng, Trước VAT theo từng sheet)
và đối chiếu với baseline đã chốt trong data/master_data/e2e_regression_baseline.json.

    ./venv/bin/python src/swind_e2e_regression.py                 # So sánh với baseline
    ./venv/bin/python src/swind_e2e_regression.py --save-baseline # Chốt baseline mới (khi thay đổi đã được duyệt)
    ./venv/bin/python src/swind_e2e_regression.py --filter "A4_BOQ"

Mọi file đều qua KIỂM BẤT BIẾN (không cần baseline): không crash, có Bảng Tổng Hợp, không dòng KL thiếu giá,
không QA_REJECTED, không cảnh báo SÓT DÒNG, loại hàng trong Model không trái Tên (VD van bị ghép mã cửa gió).
File chưa có baseline duyệt (dự án mới / baseline cũ sai trong e2e_excluded_files.json) -> trạng thái INV-OK,
không còn NEW / SKIP mặc định đạt (User chốt 2026-11-03).
"""
import os
import re
import sys
import json
import glob
import time
import argparse
import unicodedata
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE_PATH = os.path.join(BASE_DIR, "data", "master_data", "e2e_regression_baseline.json")
# Dự án cũ có baseline sai (lưu trước đợt cải tiến 02-03/11/2026) -> bỏ qua, không check / không lưu lại (User chốt 2026-11-03)
EXCLUDED_PATH = os.path.join(BASE_DIR, "data", "master_data", "e2e_excluded_files.json")


def load_excluded(baseline_path):
    if not os.path.exists(EXCLUDED_PATH):
        return {}
    with open(EXCLUDED_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    lst = data.get(os.path.basename(baseline_path)) or {}
    return {unicodedata.normalize("NFC", k): v for k, v in lst.items()}
RUNNER = os.path.join(BASE_DIR, "src", "swind_master_runner.py")
# Các file học/ghi nhớ mà pipeline có thể ghi vào -> sao lưu & khôi phục để chạy kiểm thử không làm đổi dữ liệu thật
LEARNING_FILES = [os.path.join(BASE_DIR, "data", "master_data", f) for f in
                  ("format_learning_db.json", "boq_keyword_learning.json", "pending_approval_queue.json", "swind_experience_db.json")]
PY = os.path.join(BASE_DIR, "venv", "bin", "python")

ROW_RX = re.compile(r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(\d+)\s*\|\s*([\d,]+)\s*\|")


# ---------------------------------------------------------------- Kiểm bất biến (không cần baseline)
# User chốt 2026-11-03: "Bỏ mặc định đạt, phải có cơ chế kiểm thử" -> mọi file (kể cả chưa có baseline / baseline sai đã loại)
# đều phải qua bộ kiểm bất biến; không còn trạng thái NEW / SKIP được tính là đạt.
DIFFUSER_CODE_RX = re.compile(r"(?:^|[\s+])(?:SDG|SDGK|WL|ECG|SLB|SLD|SD|SRD|SCD|LCCT|SEEG|SWL)(?=$|[\s+\-])")
DAMPER_CODE_RX = re.compile(r"\b(?:FD|MFD|NRD|VCD|MD|PRD|MPRD|M-PRD|OBD)\b|SWIND-\d\.\d{2}")
NAME_DIFFUSER_RX = re.compile(r"cửa|miệng|louver|luover|louvre|grille|diffuser|lưới|lcct|\bis\b|\bal\b|chớp|khe|slot|hộp|box|lọc|filter|g4", re.I)
NAME_DAMPER_RX = re.compile(r"\bvan\b|damper|\b(?:fd|mfd|nrd|vcd|md|prd|mprd|obd)\b", re.I)


def _check_bg_rows(xlsx_path):
    """Bất biến dòng trên sheet BG đầu ra: loại hàng trong Model không được trái với Tên dòng."""
    issues = []
    try:
        import openpyxl
        wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=False)
    except Exception as e:  # noqa: BLE001
        return [f"không mở được file đầu ra: {e}"]
    for ws in wb.worksheets:
        rows = list(ws.iter_rows(max_col=3, values_only=True))
        # Chỉ sheet báo giá do hệ thống xuất (header 'Danh mục sản phẩm' | 'Model'), không đụng sheet gốc của khách
        hdr = next((i for i, r in enumerate(rows[:30]) if str(r[1] or "").strip() == "Danh mục sản phẩm" and str(r[2] or "").strip() == "Model"), None)
        if hdr is None:
            continue
        for r_idx, row in enumerate(rows[hdr + 1:], start=hdr + 2):
            name, model = str(row[1] or "").strip(), str(row[2] or "").strip()
            if not name or not model:
                continue
            nl = name.lower()
            if nl.startswith(("van ", "van:", "damper")) and not NAME_DIFFUSER_RX.search(nl) and DIFFUSER_CODE_RX.search(model):
                issues.append(f"{ws.title}!R{r_idx}: Tên là van nhưng Model có mã cửa gió '{model}' ({name[:50]})")
            elif nl.startswith(("cửa", "miệng", "louver")) and not nl.startswith("cửa sổ") and not NAME_DAMPER_RX.search(nl) and not DIFFUSER_CODE_RX.search(model) and DAMPER_CODE_RX.search(model):
                issues.append(f"{ws.title}!R{r_idx}: Tên là cửa gió nhưng Model chỉ có mã van '{model}' ({name[:50]})")
    wb.close()
    return issues


def check_invariants(res):
    """Trả về (lỗi, cảnh báo). Lỗi -> FAIL dù có baseline hay không."""
    fails, warns = [], []
    if res["traceback"]:
        fails.append("CRASH: " + " | ".join(res["tail"]))
    if not res["sheets"] and not res["duct_only_stop"]:
        # BOQ chỉ có ống gió ở chế độ mặc định -> runner dừng ⛔ là ĐÚNG (AGENTS quy tắc 4), không tính lỗi
        fails.append("không in Bảng Tổng Hợp (không có sheet nào được báo giá)")
    if res["unpriced_rows"]:
        fails.append(f"{res['unpriced_rows']} dòng có KL nhưng chưa có đơn giá")
    if res["qa_rejected"]:
        fails.append(f"QA_REJECTED ở {res['qa_rejected']} sheet")
    if res["omission_warnings"]:
        fails.append(f"Coverage Audit: {res['omission_warnings']} cảnh báo SÓT DÒNG")
    fails.extend(res["row_issues"])
    if res["blocked"]:
        warns.append("Kiểm soát cuối ⛔ (cần hỏi lại User)")
    if res["price_not_increasing"]:
        warns.append(f"{res['price_not_increasing']} sheet có giá không tăng theo kích thước")
    return fails, warns


def run_one(boq_path, timeout=300, extra_args=()):
    t0 = time.time()
    # Chạy trong thư mục tạm: KHÔNG ghi vào data/projects/ & output/ thật (tránh đè file báo giá gửi khách)
    import tempfile
    with tempfile.TemporaryDirectory(prefix="swind_e2e_") as tmp:
        env = dict(os.environ, SWIND_OUTPUT_DIR=os.path.join(tmp, "output"))
        proc = subprocess.run(
            [PY if os.path.exists(PY) else sys.executable, RUNNER, boq_path, "--non-interactive", "--auto-accept", *extra_args],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=timeout, env=env
        )
        out = proc.stdout + proc.stderr
        m_file = re.search(r"FILE BÁO GIÁ CUỐI CÙNG GỬI KHÁCH HÀNG:\s*(.+\.xls[xm])", out)
        row_issues = _check_bg_rows(m_file.group(1).strip()) if m_file and os.path.exists(m_file.group(1).strip()) else []
    sheets = {}
    for line in out.splitlines():
        m = ROW_RX.match(line.strip())
        if m:
            sheets[m.group(2)] = {"count": int(m.group(3)), "sub_total": int(m.group(4).replace(",", ""))}
    unpriced = re.findall(r"Dòng có KL nhưng CHƯA CÓ ĐƠN GIÁ: (\d+)", out)
    return {
        "exit_code": proc.returncode,
        "sheets": sheets,
        "total": sum(s["sub_total"] for s in sheets.values()),
        "unpriced_rows": sum(int(x) for x in unpriced),
        "qa_rejected": len(re.findall(r"Trạng thái kiểm toán: QA_REJECTED", out)),
        "omission_warnings": out.count("[CẢNH BÁO SÓT DÒNG]"),
        "blocked": "⛔ [KIỂM SOÁT CUỐI]" in out,
        "duct_only_stop": "⛔ BOQ chỉ gồm Ống gió" in out,
        "price_not_increasing": len(re.findall(r"giá KHÔNG tăng theo kích thước", out)),
        "row_issues": row_issues,
        "elapsed_s": round(time.time() - t0, 2),
        "traceback": "Traceback" in out,
        "tail": out.strip().splitlines()[-5:] if "Traceback" in out else [],
    }


def main():
    ap = argparse.ArgumentParser(description="Swind E2E regression trên toàn bộ BOQ input/")
    ap.add_argument("--save-baseline", action="store_true")
    ap.add_argument("--filter", default=None, help="Chỉ chạy file có tên chứa chuỗi này")
    ap.add_argument("--runner-args", default="", help="Cờ thêm cho swind_master_runner (VD: '--include-duct')")
    ap.add_argument("--baseline", default=None, help="Đường dẫn file baseline (mặc định: e2e_regression_baseline.json)")
    args = ap.parse_args()
    baseline_path = args.baseline or BASELINE_PATH
    extra_args = tuple(args.runner_args.split()) if args.runner_args else ()

    files = sorted(glob.glob(os.path.join(BASE_DIR, "input", "*.xls*")))
    files = [f for f in files if not os.path.basename(f).startswith("~$")]
    if args.filter:
        flt = unicodedata.normalize("NFC", args.filter).lower()
        files = [f for f in files if flt in unicodedata.normalize("NFC", os.path.basename(f)).lower()]

    baseline = {}
    if os.path.exists(baseline_path):
        with open(baseline_path, "r", encoding="utf-8") as f:
            baseline = json.load(f)

    excluded = load_excluded(baseline_path)
    results = {}
    counts = {"OK": 0, "INV-OK": 0, "DIFF": 0, "FAIL": 0}
    failed_names = []
    snapshots = {p: open(p, "rb").read() for p in LEARNING_FILES if os.path.exists(p)}
    for idx, fp in enumerate(files, 1):
        name = os.path.basename(fp)
        nfc = unicodedata.normalize("NFC", name)
        try:
            res = run_one(fp, extra_args=extra_args)
        finally:
            for p_snap, data in snapshots.items():
                with open(p_snap, "wb") as f:
                    f.write(data)
        results[name] = res
        fails, warns = check_invariants(res)
        res["invariant_fails"] = fails
        base = None if nfc in excluded else baseline.get(name)
        detail = ""
        if fails:
            status = "FAIL"
            detail = " | ".join(fails[:5]) + (f" | (+{len(fails) - 5} lỗi)" if len(fails) > 5 else "")
        elif res["duct_only_stop"] and not res["sheets"]:
            status = "INV-OK"
            detail = "dừng đúng: BOQ chỉ có ống gió (mặc định không báo)"
        elif base is None:
            # Không có baseline đã duyệt (dự án mới / baseline cũ sai đã loại) -> chỉ đạt khi qua kiểm bất biến
            status = "INV-OK"
            detail = "chưa có baseline duyệt" + (" (baseline cũ sai, đã loại)" if nfc in excluded else "")
        elif base.get("sheets") == res["sheets"]:
            status = "OK"
        else:
            status = "DIFF"
            diffs = []
            for sh in sorted(set(base.get("sheets", {})) | set(res["sheets"])):
                b = base.get("sheets", {}).get(sh)
                r = res["sheets"].get(sh)
                if b != r:
                    diffs.append(f"{sh}: {b} -> {r}")
            detail = "; ".join(diffs)
        counts[status] += 1
        if status in ("FAIL", "DIFF"):
            failed_names.append(name)
        warn_txt = f"  ⚠️ {'; '.join(warns)}" if warns else ""
        print(f"[{idx:>2}/{len(files)}] {status:<6} {res['elapsed_s']:>5.1f}s  {name}  total={res['total']:,}  unpriced={res['unpriced_rows']}  {detail}{warn_txt}")

    print(f"\n📋 Kết quả: {counts['OK']} khớp baseline | {counts['INV-OK']} chỉ đạt kiểm bất biến (chưa có baseline duyệt) | "
          f"{counts['DIFF']} lệch baseline | {counts['FAIL']} lỗi bất biến  ({len(files)} file)")
    if args.save_baseline:
        # Chỉ lưu file qua kiểm bất biến; không lưu lại dự án cũ đã loại (baseline sai) — User chốt 2026-11-03
        merged = dict(baseline)
        saved = {k: {"sheets": v["sheets"], "total": v["total"]} for k, v in results.items()
                 if not v["invariant_fails"] and unicodedata.normalize("NFC", k) not in excluded}
        merged.update(saved)
        with open(baseline_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        refused = [k for k in results if k not in saved]
        print(f"💾 Đã lưu baseline {len(saved)} file -> {baseline_path}" + (f" | KHÔNG lưu {len(refused)} file (lỗi bất biến / đã loại): {refused}" if refused else ""))
    else:
        if failed_names:
            print(f"❌ E2E CHƯA ĐẠT: {len(failed_names)} file lệch baseline / lỗi bất biến: {failed_names}")
        else:
            print(f"✅ E2E ĐẠT: mọi file qua kiểm bất biến; {counts['OK']} file khớp baseline đã duyệt.")
    sys.exit(1 if (failed_names and not args.save_baseline) else 0)


if __name__ == "__main__":
    main()
