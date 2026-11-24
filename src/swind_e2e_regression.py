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
import difflib
import unicodedata
import subprocess

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BASELINE_PATH = os.path.join(BASE_DIR, "data", "master_data", "e2e_regression_baseline.json")
DUCT_BASELINE_PATH = os.path.join(BASE_DIR, "data", "master_data", "e2e_baseline_include_duct.json")
# --modes: chạy nhiều chế độ trong 1 lệnh, mỗi chế độ so với baseline riêng (2026-11-24 — trước đây --include-duct bị so
# nhầm với baseline mặc định nên luôn DIFF)
MODES = {"default": ((), BASELINE_PATH), "duct": (("--include-duct",), DUCT_BASELINE_PATH)}
DEFAULT_LIMIT = 50  # E2E mặc định chỉ chạy 50 BOQ mới nhất (User chốt 2026-11-11)
# --jobs: số runner chạy song song (2026-11-24: tuần tự 104 file mất ~21 phút/chế độ). Mỗi runner ghi output vào thư mục
# tạm riêng + SWIND_NO_LEARNING_WRITE=1 (không ghi file học) nên chạy song song không tranh chấp file.
DEFAULT_JOBS = max(1, (os.cpu_count() or 2) - 2)
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
                  ("format_learning_db.json", "boq_keyword_learning.json", "pending_approval_queue.json", "swind_experience_db.json",
                   "typo_rules.json")]
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


# ---------------------------------------------------------------- Chụp & so giá từng dòng Sheet BG
# Ngưỡng lệch lớn (User chốt 2026-11-03, đợt gom giá về swind_pricing): dòng > 2% hoặc > 50.000đ; tổng sheet > 0,5%
LINE_PCT = 0.02
LINE_VND = 50_000
SHEET_PCT = 0.005


def read_bg_lines(xlsx_path):
    """Đọc mọi dòng có Đơn giá > 0 trên các sheet báo giá do hệ thống xuất (header 'Danh mục sản phẩm' | 'Model').
    Cột: B=Tên, C=Model, L=Đơn vị, M=Số lượng, N=Đơn giá (O là công thức -> tự tính amount)."""
    import openpyxl
    lines = []
    wb = openpyxl.load_workbook(xlsx_path, read_only=True, data_only=False)
    try:
        for ws in wb.worksheets:
            rows = list(ws.iter_rows(max_col=14, values_only=True))
            hdr = next((i for i, r in enumerate(rows[:30]) if len(r) >= 3 and str(r[1] or "").strip() == "Danh mục sản phẩm" and str(r[2] or "").strip() == "Model"), None)
            if hdr is None:
                continue
            for r_idx, row in enumerate(rows[hdr + 1:], start=hdr + 2):
                row = tuple(row) + (None,) * (14 - len(row))
                price, qty = row[13], row[12]
                if not isinstance(price, (int, float)) or isinstance(price, bool) or price <= 0:
                    continue
                qty = float(qty) if isinstance(qty, (int, float)) and not isinstance(qty, bool) else 0.0
                lines.append({"sheet": ws.title, "row": r_idx, "name": str(row[1] or "").strip(), "model": str(row[2] or "").strip(),
                              "unit": str(row[11] or "").strip(), "qty": qty, "price": float(price), "amount": qty * float(price)})
    finally:
        wb.close()
    return lines


def classify_line_diff(before, after):
    """So 2 snapshot {file: [dòng]}: trong mỗi (file, sheet) căn dòng theo Tên (difflib), không theo số dòng BG. Trả {'major': [...], 'minor': [...], 'sheet_totals': [...]}."""
    major, minor, sheet_totals = [], [], []

    def rec(f, b, a, ly_do):
        x = a or b
        return {"file": f, "sheet": x["sheet"], "row": x["row"], "name": x["name"],
                "model_truoc": (b or {}).get("model"), "model_sau": (a or {}).get("model"),
                "gia_truoc": (b or {}).get("price"), "gia_sau": (a or {}).get("price"), "ly_do": ly_do}

    for f in sorted(set(before) | set(after)):
        totals = {}
        sheets = sorted({x["sheet"] for x in before.get(f, [])} | {x["sheet"] for x in after.get(f, [])})
        for sh in sheets:
            bl = sorted((x for x in before.get(f, []) if x["sheet"] == sh), key=lambda x: x["row"])
            al = sorted((x for x in after.get(f, []) if x["sheet"] == sh), key=lambda x: x["row"])
            totals[sh] = [sum(x["amount"] for x in bl), sum(x["amount"] for x in al)]
            # Căn dòng theo nội dung (Tên) thay vì số dòng BG: chèn / bớt 1 dòng không làm lệch các dòng phía sau
            sm = difflib.SequenceMatcher(None, [x["name"] for x in bl], [x["name"] for x in al], autojunk=False)
            for op, i1, i2, j1, j2 in sm.get_opcodes():
                pairs = list(zip(bl[i1:i2], al[j1:j2])) if op in ("equal", "replace") else []
                for b, a in pairs:
                    if b["name"] != a["name"]:
                        major.append(rec(f, b, a, "đổi dòng"))
                    elif b["model"] != a["model"]:
                        major.append(rec(f, b, a, "đổi Model"))
                    elif b["price"] != a["price"]:
                        d = abs(a["price"] - b["price"])
                        big = d > LINE_VND or (b["price"] > 0 and d / b["price"] > LINE_PCT)
                        (major if big else minor).append(rec(f, b, a, "lệch giá"))
                n = len(pairs)
                for b in bl[i1 + n:i2]:
                    major.append(rec(f, b, None, "mất dòng"))
                for a in al[j1 + n:j2]:
                    major.append(rec(f, None, a, "dòng mới"))
        for sh, (tb, ta) in sorted(totals.items()):
            if tb != ta:
                pct = abs(ta - tb) / tb if tb else 1.0
                sheet_totals.append({"file": f, "sheet": sh, "tong_truoc": tb, "tong_sau": ta, "pct": pct, "major": pct > SHEET_PCT})
    return {"major": major, "minor": minor, "sheet_totals": sheet_totals}


def write_line_diff_report(res, path):
    def fmt(v):
        return "" if v is None else f"{v:,.0f}"
    out = ["# Đối chiếu giá từng dòng Sheet BG", "",
           f"Ngưỡng lệch lớn: dòng > {LINE_PCT:.0%} hoặc > {LINE_VND:,}đ; tổng sheet > {SHEET_PCT:.1%}.", "",
           f"**{len(res['major'])} lệch lớn / {len(res['minor'])} lệch nhỏ / "
           f"{sum(1 for s in res['sheet_totals'] if s['major'])} sheet lệch tổng > {SHEET_PCT:.1%}**", ""]
    for title, rows in (("Lệch lớn", res["major"]), ("Lệch nhỏ", res["minor"])):
        out += [f"## {title}", "", "| File | Sheet | Dòng | Tên | Model trước → sau | Giá trước | Giá sau | Lý do |", "|---|---|---|---|---|---|---|---|"]
        out += [f"| {r['file']} | {r['sheet']} | {r['row']} | {r['name'][:60]} | {r['model_truoc']} → {r['model_sau']} | {fmt(r['gia_truoc'])} | {fmt(r['gia_sau'])} | {r['ly_do']} |" for r in rows]
        out.append("")
    out += ["## Tổng sheet", "", "| File | Sheet | Tổng trước | Tổng sau | Lệch | Lớn? |", "|---|---|---|---|---|---|"]
    out += [f"| {s['file']} | {s['sheet']} | {fmt(s['tong_truoc'])} | {fmt(s['tong_sau'])} | {s['pct']:.2%} | {'⚠️' if s['major'] else ''} |" for s in res["sheet_totals"]]
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(out) + "\n")


def run_line_diff(before_path, after_path, report_path=None):
    with open(before_path, "r", encoding="utf-8") as f:
        before = json.load(f)
    with open(after_path, "r", encoding="utf-8") as f:
        after = json.load(f)
    res = classify_line_diff(before, after)
    n_sheet = sum(1 for s in res["sheet_totals"] if s["major"])
    print(f"{len(res['major'])} lệch lớn / {len(res['minor'])} lệch nhỏ / {n_sheet} sheet lệch tổng > {SHEET_PCT:.1%}")
    for r in res["major"][:30]:
        print(f"  ⚠️ {r['file']} | {r['sheet']}!R{r['row']} | {r['name'][:50]} | {r['model_truoc']} → {r['model_sau']} | "
              f"{r['gia_truoc'] or 0:,.0f} → {r['gia_sau'] or 0:,.0f} | {r['ly_do']}")
    if report_path:
        write_line_diff_report(res, report_path)
        print(f"📄 Báo cáo: {report_path}")
    return 1 if (res["major"] or n_sheet) else 0


def run_one(boq_path, timeout=300, extra_args=()):
    t0 = time.time()
    # Chạy trong thư mục tạm: KHÔNG ghi vào data/projects/ & output/ thật (tránh đè file báo giá gửi khách)
    import tempfile
    with tempfile.TemporaryDirectory(prefix="swind_e2e_") as tmp:
        env = dict(os.environ, SWIND_OUTPUT_DIR=os.path.join(tmp, "output"), SWIND_NO_LEARNING_WRITE="1")
        proc = subprocess.run(
            [PY if os.path.exists(PY) else sys.executable, RUNNER, boq_path, "--non-interactive", "--auto-accept", *extra_args],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=timeout, env=env
        )
        out = proc.stdout + proc.stderr
        m_file = re.search(r"FILE BÁO GIÁ CUỐI CÙNG GỬI KHÁCH HÀNG:\s*(.+\.xls[xm])", out)
        out_xlsx = m_file.group(1).strip() if m_file else ""
        row_issues = _check_bg_rows(out_xlsx) if out_xlsx and os.path.exists(out_xlsx) else []
        try:
            bg_lines = read_bg_lines(out_xlsx) if out_xlsx and os.path.exists(out_xlsx) else []
        except Exception as e:  # noqa: BLE001
            bg_lines = [{"sheet": "_LOI_DOC_", "row": 0, "name": str(e), "model": "", "unit": "", "qty": 0, "price": 0, "amount": 0}]
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
        "bg_lines": bg_lines,
        "elapsed_s": round(time.time() - t0, 2),
        "traceback": "Traceback" in out,
        "tail": out.strip().splitlines()[-5:] if "Traceback" in out else [],
    }


_OUTPUT_DIRS = None


def _recent_quote_time(fp):
    """Mốc 'báo giá gần nhất' của 1 BOQ = max(thời gian file input, thời gian báo giá trong output/).
    Thư mục output khớp khi trùng tên file, hoặc mọi từ của tên thư mục (>= 2 từ, >= 8 ký tự) đều nằm trong tên file
    (báo giá gộp nhiều BOQ, VD output 'KL TB+VT CT2' <- input 'KL TB+VT DHTG-CT2' + 'KL TB+VT TA,HK-CT2')."""
    global _OUTPUT_DIRS
    out_root = os.path.join(BASE_DIR, "output")
    if _OUTPUT_DIRS is None:
        _OUTPUT_DIRS = [d for d in (os.listdir(out_root) if os.path.isdir(out_root) else [])
                        if not d.startswith((".", "_")) and os.path.isdir(os.path.join(out_root, d))]
    stem = unicodedata.normalize("NFC", os.path.splitext(os.path.basename(fp))[0].strip()).lower()
    t = os.path.getmtime(fp)
    for d in _OUTPUT_DIRS:
        dn = unicodedata.normalize("NFC", d.strip()).lower()
        toks = dn.split()
        if dn == stem or (len(toks) >= 2 and len(dn) >= 8 and all(tk in stem for tk in toks)):
            proj = os.path.join(out_root, d)
            quotes = [os.path.join(proj, f) for f in os.listdir(proj) if f.lower().endswith(".xlsx") and not f.startswith("~$")]
            t = max([t, os.path.getmtime(proj)] + [os.path.getmtime(q) for q in quotes])
    return t


def main():
    ap = argparse.ArgumentParser(description="Swind E2E regression trên toàn bộ BOQ input/")
    ap.add_argument("--save-baseline", action="store_true")
    ap.add_argument("--filter", default=None, help="Chỉ chạy file có tên chứa chuỗi này")
    ap.add_argument("--runner-args", default="", help="Cờ thêm cho swind_master_runner (VD: '--include-duct')")
    ap.add_argument("--baseline", default=None, help="Đường dẫn file baseline (mặc định: e2e_regression_baseline.json)")
    ap.add_argument("--line-snapshot", default=None, help="Ghi giá từng dòng Sheet BG của mọi file vào JSON này")
    ap.add_argument("--line-diff", nargs=2, metavar=("TRUOC", "SAU"), default=None, help="So 2 snapshot giá từng dòng (không chạy runner)")
    ap.add_argument("--report", default=None, help="File Markdown báo cáo cho --line-diff")
    ap.add_argument("--limit", type=int, default=DEFAULT_LIMIT,
                    help=f"Chỉ chạy N BOQ có báo giá gần nhất (theo file báo giá trong output/, chưa báo thì theo file input; mặc định {DEFAULT_LIMIT}; 0 = toàn bộ)")
    ap.add_argument("--jobs", type=int, default=DEFAULT_JOBS,
                    help=f"Số runner chạy song song (mặc định {DEFAULT_JOBS} = số nhân CPU - 2; 1 = tuần tự như cũ)")
    ap.add_argument("--modes", default=None,
                    help="Chạy nhiều chế độ trong 1 lệnh, mỗi chế độ so baseline riêng: 'default', 'duct' hoặc 'default,duct'")
    ap.add_argument("--files-from", default=None,
                    help="Chỉ chạy các file có tên trong file văn bản này (mỗi dòng 1 tên — đầu ra của swind_impact_scan.py)")
    args = ap.parse_args()
    if args.line_diff:
        sys.exit(run_line_diff(args.line_diff[0], args.line_diff[1], args.report))
    if args.modes:
        modes = [(m.strip(), MODES[m.strip()][0], MODES[m.strip()][1]) for m in args.modes.split(",") if m.strip()]
    else:
        modes = [("", tuple(args.runner_args.split()) if args.runner_args else (), args.baseline or BASELINE_PATH)]

    files = sorted(glob.glob(os.path.join(BASE_DIR, "input", "*.xls*")))
    files = [f for f in files if not os.path.basename(f).startswith("~$")]
    if args.filter:
        flt = unicodedata.normalize("NFC", args.filter).lower()
        files = [f for f in files if flt in unicodedata.normalize("NFC", os.path.basename(f)).lower()]
    if args.files_from:
        with open(args.files_from, "r", encoding="utf-8") as fh:
            wanted = {unicodedata.normalize("NFC", ln.strip()) for ln in fh if ln.strip()}
        files = [f for f in files if unicodedata.normalize("NFC", os.path.basename(f)) in wanted]
    # Giới hạn N báo giá gần nhất (User chốt 2026-11-11: chạy toàn bộ input/ quá lâu) — xếp theo lần báo giá gần nhất
    # (file báo giá trong output/<tên file>/), chưa từng báo thì theo thời gian file input; chạy theo thứ tự tên
    if args.limit and args.limit > 0 and len(files) > args.limit and not args.files_from:
        n_all = len(files)
        files = sorted(sorted(files, key=_recent_quote_time, reverse=True)[:args.limit])
        print(f"ℹ️  E2E chỉ chạy {len(files)}/{n_all} BOQ có báo giá gần nhất (--limit {args.limit}; --limit 0 để chạy toàn bộ)")

    # Chạy song song mọi (chế độ, file) trong 1 hàng đợi; file nặng chạy trước để không kéo dài cuối hàng
    from concurrent.futures import ThreadPoolExecutor, as_completed
    tasks = [(m, fp) for (m, _a, _b) in modes for fp in files]
    tasks.sort(key=lambda t: -os.path.getsize(t[1]))
    args_of = {m: a for (m, a, _b) in modes}
    snapshots = {p: open(p, "rb").read() for p in LEARNING_FILES if os.path.exists(p)}
    results_all = {m: {} for (m, _a, _b) in modes}
    t_start = time.time()
    try:
        with ThreadPoolExecutor(max_workers=max(1, args.jobs)) as ex:
            futs = {ex.submit(run_one, fp, 300, args_of[m]): (m, fp) for (m, fp) in tasks}
            done = 0
            for fut in as_completed(futs):
                m, fp = futs[fut]
                try:
                    res = fut.result()
                except Exception as e:  # noqa: BLE001 — timeout / lỗi tiến trình: ghi thành FAIL
                    res = {"exit_code": -1, "sheets": {}, "total": 0, "unpriced_rows": 0, "qa_rejected": 0, "omission_warnings": 0,
                           "blocked": False, "duct_only_stop": False, "price_not_increasing": 0, "row_issues": [], "bg_lines": [],
                           "elapsed_s": 0, "traceback": True, "tail": [str(e)]}
                results_all[m][os.path.basename(fp)] = res
                done += 1
                if done % 10 == 0 or done == len(tasks):
                    print(f"  ... {done}/{len(tasks)} lượt xong ({time.time() - t_start:.0f}s)", flush=True)
    finally:
        # Khôi phục file học (an toàn thêm — runner đã không ghi nhờ SWIND_NO_LEARNING_WRITE=1)
        for p_snap, data in snapshots.items():
            with open(p_snap, "wb") as f:
                f.write(data)
    print(f"⏱️  {len(tasks)} lượt chạy xong trong {time.time() - t_start:.0f}s (--jobs {args.jobs})")

    any_failed = False
    for (m, _a, baseline_path) in modes:
        if len(modes) > 1 or m:
            print(f"\n================ CHẾ ĐỘ: {m}  (baseline: {os.path.basename(baseline_path)}) ================")
        any_failed |= _report_mode(files, results_all[m], baseline_path, args)
    sys.exit(1 if (any_failed and not args.save_baseline) else 0)


def _report_mode(files, results, baseline_path, args):
    """In kết quả 1 chế độ theo thứ tự tên file; lưu baseline / snapshot nếu có cờ. Trả True khi có file DIFF / FAIL."""
    baseline = {}
    if os.path.exists(baseline_path):
        with open(baseline_path, "r", encoding="utf-8") as f:
            baseline = json.load(f)
    excluded = load_excluded(baseline_path)
    counts = {"OK": 0, "INV-OK": 0, "DIFF": 0, "FAIL": 0}
    failed_names = []
    for idx, fp in enumerate(files, 1):
        name = os.path.basename(fp)
        nfc = unicodedata.normalize("NFC", name)
        res = results[name]
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
    if args.line_snapshot:
        snap = args.line_snapshot if len((args.modes or "").split(",")) <= 1 else args.line_snapshot.replace(".json", f"_{os.path.basename(baseline_path).split('.')[0]}.json")
        os.makedirs(os.path.dirname(os.path.abspath(snap)), exist_ok=True)
        with open(snap, "w", encoding="utf-8") as f:
            json.dump({k: v.get("bg_lines", []) for k, v in results.items()}, f, ensure_ascii=False, indent=1)
        print(f"📸 Snapshot giá từng dòng: {snap} ({sum(len(v.get('bg_lines', [])) for v in results.values())} dòng)")
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
    return bool(failed_names)


if __name__ == "__main__":
    main()
