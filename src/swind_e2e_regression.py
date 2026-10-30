"""
Kiểm thử hồi quy End-to-End toàn bộ file BOQ trong input/.

Chạy swind_master_runner.py trên từng file BOQ, trích Bảng Tổng Hợp (Số dòng, Trước VAT theo từng sheet)
và đối chiếu với baseline đã chốt trong data/master_data/e2e_regression_baseline.json.

    ./venv/bin/python src/swind_e2e_regression.py                 # So sánh với baseline
    ./venv/bin/python src/swind_e2e_regression.py --save-baseline # Chốt baseline mới (khi thay đổi đã được duyệt)
    ./venv/bin/python src/swind_e2e_regression.py --filter "A4_BOQ"
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
RUNNER = os.path.join(BASE_DIR, "src", "swind_master_runner.py")
# Các file học/ghi nhớ mà pipeline có thể ghi vào -> sao lưu & khôi phục để chạy kiểm thử không làm đổi dữ liệu thật
LEARNING_FILES = [os.path.join(BASE_DIR, "data", "master_data", f) for f in
                  ("format_learning_db.json", "boq_keyword_learning.json", "pending_approval_queue.json", "swind_experience_db.json")]
PY = os.path.join(BASE_DIR, "venv", "bin", "python")

ROW_RX = re.compile(r"^\|\s*(\d+)\s*\|\s*(.+?)\s*\|\s*(\d+)\s*\|\s*([\d,]+)\s*\|")


def run_one(boq_path, timeout=300, extra_args=()):
    t0 = time.time()
    # Chạy trong thư mục tạm: KHÔNG ghi vào data/projects/ & output/ thật (tránh đè file báo giá gửi khách)
    import tempfile
    with tempfile.TemporaryDirectory(prefix="swind_e2e_") as tmp:
        env = dict(os.environ, SWIND_PROJECTS_DIR=os.path.join(tmp, "projects"), SWIND_OUTPUT_DIR=os.path.join(tmp, "output"))
        proc = subprocess.run(
            [PY if os.path.exists(PY) else sys.executable, RUNNER, boq_path, "--non-interactive", "--auto-accept", *extra_args],
            cwd=BASE_DIR, capture_output=True, text=True, timeout=timeout, env=env
        )
    out = proc.stdout + proc.stderr
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

    results = {}
    n_diff = 0
    snapshots = {p: open(p, "rb").read() for p in LEARNING_FILES if os.path.exists(p)}
    for idx, fp in enumerate(files, 1):
        name = os.path.basename(fp)
        try:
            res = run_one(fp, extra_args=extra_args)
        finally:
            for p_snap, data in snapshots.items():
                with open(p_snap, "wb") as f:
                    f.write(data)
        results[name] = res
        base = baseline.get(name)
        status = "NEW"
        detail = ""
        if res["traceback"]:
            status = "CRASH"
            detail = " | ".join(res["tail"])
            n_diff += 1
        elif base is not None:
            if base.get("sheets") == res["sheets"]:
                status = "OK"
            else:
                status = "DIFF"
                n_diff += 1
                diffs = []
                for sh in sorted(set(base.get("sheets", {})) | set(res["sheets"])):
                    b = base.get("sheets", {}).get(sh)
                    r = res["sheets"].get(sh)
                    if b != r:
                        diffs.append(f"{sh}: {b} -> {r}")
                detail = "; ".join(diffs)
        print(f"[{idx:>2}/{len(files)}] {status:<5} {res['elapsed_s']:>5.1f}s  {name}  total={res['total']:,}  unpriced={res['unpriced_rows']}  {detail}")

    if args.save_baseline:
        merged = dict(baseline)
        merged.update({k: {"sheets": v["sheets"], "total": v["total"]} for k, v in results.items() if not v["traceback"]})
        with open(baseline_path, "w", encoding="utf-8") as f:
            json.dump(merged, f, ensure_ascii=False, indent=2)
        print(f"\n💾 Đã lưu baseline {len(results)} file -> {baseline_path}")
    else:
        print(f"\n{'✅ E2E PASSED' if n_diff == 0 else f'❌ E2E: {n_diff} file khác baseline / lỗi'} ({len(files)} file)")
    sys.exit(1 if (n_diff and not args.save_baseline) else 0)


if __name__ == "__main__":
    main()
