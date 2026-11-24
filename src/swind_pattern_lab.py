"""
THƯ VIỆN MẪU DÒNG + CHẠY LẠI THEO MẪU (kiểm thử hồi quy tầng 1 + 2 — User duyệt 2026-11-24)

Vấn đề: E2E chạy đủ pipeline cho MỌI file BOQ → thời gian tăng theo số file (104 → 1.400 → 14.000).
Quan sát: 21.019 dòng hàng của 100 file chỉ có ~2.900 MẪU dòng khác nhau (gộp các dòng chỉ khác số); số mẫu tăng
chậm hơn nhiều so với số file.

TẦNG 1 — Thư viện mẫu dòng (--build):
  Mỗi file BOQ đọc 1 LẦN bằng đúng parser hệ thống (Agent01.detect_and_parse); với MỌI dòng dữ liệu (dòng báo giá +
  dòng bị lọc) lưu nội dung thô các ô theo bố cục cột, Title đang áp dụng → SQLite. Nhận diện file theo SHA-1:
  file không đổi không đọc lại; file mới đọc thêm; file đã xoá bị loại khỏi thư viện.
  Thư viện chứa dữ liệu khách → nằm trong output/_pattern_lab/ (không commit).

TẦNG 2 — Chạy lại theo mẫu (--replay / --check):
  Gom dòng theo chữ ký mẫu (Title + chữ các ô, số thay bằng #, + bố cục cột); mỗi mẫu lấy tối đa 3 dòng đại diện
  (cỡ nhỏ / vừa / lớn). Dựng sheet ảo trong RAM (dòng Title + dòng hàng, đúng bố cục cột gốc) → SwindBOQParser →
  Agent01.resolve_item_spec → tính giá (swind_item_inspector, công thức dùng chung swind_pricing). So với ảnh chụp
  chuẩn → mẫu nào đổi (loại hàng / Model / ghi chú / giá / bị lọc), ảnh hưởng bao nhiêu dòng, file nào → ghi danh sách
  file cho E2E đầy đủ (--files-from).

  KHÔNG thay E2E cho thay đổi phần ĐỌC CẤU TRÚC BOQ (header, cột ẩn, dòng kích thước tách cột, KL ở dòng khác...)
  và form Excel — các thay đổi đó vẫn chạy E2E (bộ file canh gác / toàn bộ).

Lệnh:
  ./venv/bin/python src/swind_pattern_lab.py --build                 # tầng 1 (chỉ đọc file mới / đã đổi)
  ./venv/bin/python src/swind_pattern_lab.py --set-baseline          # chụp kết quả hiện tại làm chuẩn (sau khi duyệt)
  ./venv/bin/python src/swind_pattern_lab.py --check                 # sau khi sửa rule: chạy lại + so chuẩn
  ./venv/bin/python src/swind_pattern_lab.py --stats
  # file bị ảnh hưởng → E2E đầy đủ chỉ các file đó:
  ./venv/bin/python src/swind_e2e_regression.py --modes default,duct --files-from output/_pattern_lab/affected_files.txt
"""
import argparse
import contextlib
import datetime
import hashlib
import io
import json
import os
import re
import sqlite3
import sys
import time
import unicodedata
from collections import defaultdict
from concurrent.futures import ProcessPoolExecutor

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
if SCRIPT_DIR not in sys.path:
    sys.path.insert(0, SCRIPT_DIR)

LAB_DIR = os.environ.get("SWIND_PATTERN_LAB_DIR") or os.path.join(PROJECT_ROOT, "output", "_pattern_lab")
DB_PATH = os.path.join(LAB_DIR, "lab.sqlite")
SNAP_DIR = os.path.join(LAB_DIR, "snapshots")
AFFECTED_PATH = os.path.join(LAB_DIR, "affected_files.txt")
REPORT_PATH = os.path.join(LAB_DIR, "check_report.md")
CANARY_PATH = os.path.join(LAB_DIR, "canary_files.txt")
CANARY_REPORT = os.path.join(LAB_DIR, "canary_report.md")
E2E_FILES_PATH = os.path.join(LAB_DIR, "e2e_files.txt")
INPUT_GLOB_DIR = os.path.join(PROJECT_ROOT, "input")
TEXT_KEYS = ("name", "spec", "model", "unit", "remarks", "material", "brand", "flange")  # ô chữ vào chữ ký mẫu
INSTANCES_PER_PATTERN = 3
CHUNK = 120  # số dòng đại diện / 1 sheet ảo
HEADER_LABELS = {"stt": "STT", "name": "Tên vật tư", "spec": "Quy cách", "model": "Model", "unit": "Đơn vị", "qty": "Khối lượng",
                 "price": "Đơn giá", "total": "Thành tiền", "remarks": "Ghi chú", "brand": "Nhãn hiệu", "material": "Vật liệu",
                 "w": "Rộng", "h": "Cao", "w2": "Rộng 2", "h2": "Cao 2", "l": "Dài", "r_or_d": "Đường kính", "thickness": "Độ dày",
                 "flange": "Kiểu bích", "offset": "Độ lệch", "qty_alt": "Khối lượng 2"}
RESULT_KEYS = ("status", "category", "subtype", "model_std", "note_std", "a1", "a2", "b1", "b2", "modul", "thk_col",
               "effective_sell_unit", "price_source")


def _nfc(v):
    return unicodedata.normalize("NFC", str(v)) if v is not None else ""


def _norm(v):
    s = _nfc(v).lower()
    s = re.sub(r"\d+(?:[.,]\d+)?", "#", s)
    return re.sub(r"\s+", " ", s).strip()


def _jsonable(v):
    if v is None or isinstance(v, (int, float, str, bool)):
        return v
    if isinstance(v, (datetime.date, datetime.datetime, datetime.time)):
        return v.isoformat()
    return str(v)


def _db():
    os.makedirs(LAB_DIR, exist_ok=True)
    con = sqlite3.connect(DB_PATH)
    con.execute("CREATE TABLE IF NOT EXISTS files (name TEXT PRIMARY KEY, sha TEXT, n_rows INTEGER, built_at TEXT, error TEXT)")
    con.execute("CREATE TABLE IF NOT EXISTS rows (file TEXT, sheet TEXT, row INTEGER, sig TEXT, title TEXT, title_aux TEXT, "
                "cells TEXT, layout TEXT, size_key REAL, PRIMARY KEY (file, sheet, row))")
    con.execute("CREATE INDEX IF NOT EXISTS rows_sig ON rows(sig)")
    # Tầng 3: đặc trưng bố cục từng sheet (cột, phiếu đặt hàng, cột/dòng ẩn, bảng phụ, nhiều sheet...)
    con.execute("CREATE TABLE IF NOT EXISTS sheet_feats (file TEXT, sheet TEXT, feats TEXT, PRIMARY KEY (file, sheet))")
    return con


def _sha1(path):
    h = hashlib.sha1()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _signature(title, title_aux, cells, layout):
    parts = {
        "t": _norm(title), "ta": _norm(title_aux),
        "c": {k: _norm(cells.get(k)) for k in TEXT_KEYS if cells.get(k) not in (None, "")},
        # ô số (kích thước, KL): chỉ giữ CÓ / KHÔNG giá trị (giá trị cụ thể nằm ở dòng đại diện)
        "n": sorted(k for k, v in cells.items() if k not in TEXT_KEYS and v not in (None, "", 0)),
        "l": sorted(layout.items()),
    }
    return hashlib.sha1(json.dumps(parts, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()[:16]


def _size_key(cells):
    nums = []
    for k, v in cells.items():
        if k in ("qty", "price", "total", "stt"):
            continue
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            nums.append(float(v))
        elif isinstance(v, str):
            nums += [float(x) for x in re.findall(r"\d{2,5}", v)]
    return max(nums) if nums else 0.0


# ------------------------------------------------------------------ TẦNG 1: trích xuất 1 file
def extract_file(path):
    """Đọc 1 BOQ bằng parser hệ thống → (danh sách dòng kèm Title + bố cục cột, đặc trưng bố cục từng sheet)."""
    from agent_01_boq_extractor import Agent01_BOQExtractor
    from swind_utils import detect_boq_header
    out, feats = [], {}
    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        agent = Agent01_BOQExtractor(boq_file=path, project_name="pattern_lab")
        agent.parser.record_row_context = True
        sheets, items = agent.detect_and_parse()
    p = agent.parser
    for sh in sheets:
        if sh not in p.sheet_layouts:
            continue
        _hdr, cmap = p.sheet_layouts[sh]
        layout = {k: v for k, v in cmap.items() if isinstance(v, bool) or (isinstance(v, int) and v >= 1)}
        ws = p.wb[sh]
        rows = {it.get("source_row") for it in items if it.get("source_sheet") == sh and not it.get("is_side_table")}
        rows |= set(p.skip_reasons.get(sh, {}).keys())
        ctx = p.row_context.get(sh, {})
        try:
            _h, _cm, hid_rows, hid_cols, _mx = detect_boq_header(ws)
        except Exception:  # noqa: BLE001
            hid_rows, hid_cols = set(), set()
        # Có / không từng loại cột (không dùng tổ hợp cột chính xác — số tổ hợp phình theo số file)
        f = {"COT:" + k for k, v in layout.items() if not isinstance(v, bool)}
        if "w" in layout and "h" in layout:
            f.add("BOCUC:kich_thuoc_tach_cot")
        f |= {"FLAG:" + k for k, v in layout.items() if isinstance(v, bool) and v}
        if hid_rows:
            f.add("BOCUC:dong_an")
        if hid_cols:
            f.add("BOCUC:cot_an")
        if any(it.get("is_side_table") and it.get("source_sheet") == sh for it in items):
            f.add("BOCUC:bang_phu")
        if len(sheets) > 1:
            f.add("BOCUC:nhieu_sheet")
        if any(v[1] for v in ctx.values()):
            f.add("BOCUC:title_2_tang")
        if any(it.get("is_missing_qty") and it.get("source_sheet") == sh for it in items):
            f.add("BOCUC:kl_trong")
        feats[sh] = sorted(f)
        for r in sorted(x for x in rows if x):
            cells = {k: _jsonable(ws.cell(r, c).value) for k, c in layout.items() if not isinstance(c, bool)}
            title, title_aux = ctx.get(r, ("", ""))
            out.append((sh, r, title or "", title_aux or "", cells, layout))
    return out, feats


def _worker_init():
    """Tiến trình con của pool: không ghi file học (không đặt ở tiến trình gọi — tránh rò sang test / runner cùng tiến trình)."""
    os.environ["SWIND_NO_LEARNING_WRITE"] = "1"


def _extract_worker(path):
    try:
        rows, feats = extract_file(path)
        return path, rows, feats, None
    except Exception as e:  # noqa: BLE001
        return path, [], {}, f"{type(e).__name__}: {e}"


def build(jobs, force=False):
    con = _db()
    files = sorted(f for f in os.listdir(INPUT_GLOB_DIR) if f.lower().endswith(".xlsx") and not f.startswith("~$"))
    # File đọc lỗi lần trước (error khác NULL) → đọc lại dù SHA không đổi
    known = {n: s for n, s, e in con.execute("SELECT name, sha, error FROM files") if not e}
    known.update({n: None for n, e in con.execute("SELECT name, error FROM files") if e})
    todo, shas = [], {}
    for f in files:
        sha = _sha1(os.path.join(INPUT_GLOB_DIR, f))
        shas[f] = sha
        if force or known.get(_nfc(f)) != sha:
            todo.append(f)
    gone = [n for n in known if n not in {_nfc(f) for f in files}]
    # Thư viện cũ chưa có đặc trưng bố cục (trước tầng 3) → đọc lại các file đó
    have_feats = {n for (n,) in con.execute("SELECT DISTINCT file FROM sheet_feats")}
    todo += [f for f in files if f not in todo and _nfc(f) in known and _nfc(f) not in have_feats]
    for n in gone:
        con.execute("DELETE FROM sheet_feats WHERE file=?", (n,))
        con.execute("DELETE FROM rows WHERE file=?", (n,))
        con.execute("DELETE FROM files WHERE name=?", (n,))
    t0 = time.time()
    print(f"📚 Thư viện mẫu dòng: {len(files)} file trong input/ | đọc mới {len(todo)} | bỏ qua {len(files) - len(todo)} (không đổi) | loại {len(gone)} (đã xoá)")
    if todo:
        with ProcessPoolExecutor(max_workers=max(1, jobs), initializer=_worker_init) as ex:
            for path, rows, feats, err in ex.map(_extract_worker, [os.path.join(INPUT_GLOB_DIR, f) for f in todo]):
                name = _nfc(os.path.basename(path))
                con.execute("DELETE FROM rows WHERE file=?", (name,))
                con.execute("DELETE FROM sheet_feats WHERE file=?", (name,))
                con.executemany("INSERT INTO sheet_feats VALUES (?,?,?)", [(name, sh, json.dumps(fs, ensure_ascii=False)) for sh, fs in feats.items()])
                con.executemany("INSERT INTO rows VALUES (?,?,?,?,?,?,?,?,?)", [
                    (name, sh, r, _signature(t, ta, cells, lay), t, ta, json.dumps(cells, ensure_ascii=False),
                     json.dumps(lay, ensure_ascii=False, sort_keys=True), _size_key(cells))
                    for sh, r, t, ta, cells, lay in rows])
                con.execute("INSERT OR REPLACE INTO files VALUES (?,?,?,?,?)",
                            (name, shas[os.path.basename(path)], len(rows), datetime.datetime.now().isoformat(timespec="seconds"), err))
                if err:
                    print(f"  ⚠️ {name}: {err}")
        con.commit()
    stats(con)
    print(f"⏱️  build {time.time() - t0:.0f}s")


def stats(con=None):
    con = con or _db()
    n_files, = con.execute("SELECT COUNT(*) FROM files").fetchone()
    n_rows, n_sig = con.execute("SELECT COUNT(*), COUNT(DISTINCT sig) FROM rows").fetchone()
    print(f"📊 {n_files} file | {n_rows:,} dòng | {n_sig:,} mẫu dòng ({(n_sig / n_rows if n_rows else 0):.0%})")


# ------------------------------------------------------------------ TẦNG 2: chạy lại theo mẫu
def pick_instances(con):
    """Mỗi mẫu: tối đa 3 dòng đại diện theo cỡ (nhỏ nhất / giữa / lớn nhất)."""
    by_sig = defaultdict(list)
    for row in con.execute("SELECT sig, file, sheet, row, title, title_aux, cells, layout, size_key FROM rows ORDER BY sig, size_key"):
        by_sig[row[0]].append(row)
    picked = []
    for sig, lst in by_sig.items():
        idxs = sorted({0, len(lst) // 2, len(lst) - 1})[:INSTANCES_PER_PATTERN]
        picked += [lst[i] for i in idxs]
    return picked


_TRACE = []  # vết rule của dòng đang tính (tầng 3) — các hàm phân loại được bọc ghi vào đây


def _install_trace_hooks():
    """Bọc hàm phân loại cửa / van / ống để ghi id rule kích hoạt (không sửa code agent; chỉ trong công cụ này)."""
    import damper_classifier
    import diffuser_classifier
    import duct_classifier
    if getattr(duct_classifier, "_lab_hooked", False):
        return
    o_diff, o_damp, o_duct = diffuser_classifier.classify, damper_classifier.classify, duct_classifier.detect_subtype

    def diff_cls(*a, **k):
        r = o_diff(*a, **k)
        _TRACE.append(str(r.get("rule_id")))
        return r

    def damp_cls(*a, **k):
        r = o_damp(*a, **k)
        _TRACE.extend(r.get("trail") or [])
        return r

    def duct_sub(*a, **k):
        tr = k.pop("trail", None)
        own = []
        r = o_duct(*a, trail=own, **k)
        _TRACE.extend(own)
        if tr is not None:
            tr.extend(own)
        return r

    diffuser_classifier.classify, damper_classifier.classify, duct_classifier.detect_subtype = diff_cls, damp_cls, duct_sub
    duct_classifier._lab_hooked = True


def _replay_chunk(chunk):
    """chunk: list instance cùng bố cục cột → 1 sheet ảo → parser + Agent01 + tính giá. Trả {inst_id: kết quả}."""
    import openpyxl
    from swind_boq_parser import SwindBOQParser
    from swind_item_inspector import _evaluate_parsed_item_in_ram
    _install_trace_hooks()
    from swind_utils import get_subtype_rules, get_master_price_map
    layout = {k: v for k, v in json.loads(chunk[0][7]).items() if isinstance(v, bool) or (isinstance(v, int) and v >= 1)}
    new_map = dict(layout)  # giữ nguyên vị trí cột gốc (parser có nhánh đọc cột 1 / cột kề cột Tên)
    name_col = new_map.get("name", 2)  # parser mặc định cột Tên = 2 khi bố cục không có khóa 'name'
    wb = openpyxl.Workbook()
    ws = wb.active
    ws.title = "LAB"
    for k, c in new_map.items():
        if not isinstance(c, bool):
            ws.cell(1, c, HEADER_LABELS.get(k, k))  # nhãn thật để detect_boq_header không lỗi (kết quả dò bị ghi đè bởi bố cục gốc)
    row_of, r = {}, 2
    for (sig, f, sh, rr, title, title_aux, cells_j, _lay, _sk) in chunk:
        cells = json.loads(cells_j)
        r += 1                                                   # dòng trống ngăn cách
        ws.cell(r, name_col, title if title else "SẢN PHẨM")  # dòng Title đang áp dụng
        r += 1
        for k, v in cells.items():
            if k in new_map and not isinstance(new_map[k], bool):
                ws.cell(r, new_map[k], v)
        row_of[r] = (f"{f}|{sh}|{rr}", sig)
        r += 1
    res = {}
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            parser = SwindBOQParser(":memory:", wb=wb)
            items = parser.parse_sheet("LAB", _override_col_map=new_map, _override_header_row=1)
            sub_rules, price_map = get_subtype_rules(), get_master_price_map()
            with open(os.path.join(PROJECT_ROOT, "data", "master_data", "financial_policy.json"), encoding="utf-8") as fh:
                fin = json.load(fh)
            by_row = defaultdict(list)
            for i, it in enumerate(items, 1):
                by_row[it.get("source_row")].append((i, it))
            for rr, (iid, sig) in row_of.items():
                if rr in by_row:
                    outs, trace = [], []
                    for i, it in by_row[rr]:
                        try:
                            _TRACE.clear()
                            ev = _evaluate_parsed_item_in_ram(dict(it), i, sub_rules, price_map, fin)
                            trace += [t for t in _TRACE if t and t not in trace]
                            ev["status"] = "PRICED"
                        except Exception as e:  # noqa: BLE001
                            ev = {"status": f"EVAL_ERROR: {type(e).__name__}: {e}"[:160], "category": it.get("category")}
                        outs.append({k: _jsonable(ev.get(k)) for k in RESULT_KEYS})
                    res[iid] = {"sig": sig, "out": outs, "trace": trace}
                elif rr in parser.skip_reasons.get("LAB", {}):
                    sk = parser.skip_reasons["LAB"][rr]
                    res[iid] = {"sig": sig, "out": [{"status": f"SKIP:{sk.get('reason')}", "category": sk.get("category")}]}
                else:
                    res[iid] = {"sig": sig, "out": [{"status": "NOT_PARSED"}]}
    except Exception as e:  # noqa: BLE001
        for rr, (iid, sig) in row_of.items():
            import traceback
            tb = traceback.extract_tb(e.__traceback__)
            where = ([f for f in tb if f.filename.startswith(SCRIPT_DIR)] or tb)[-1]
            res[iid] = {"sig": sig, "out": [{"status": f"CHUNK_ERROR: {type(e).__name__}: {e} @ {os.path.basename(where.filename)}:{where.lineno}"[:200]}]}
    return res


def replay(jobs):
    con = _db()
    inst = pick_instances(con)
    by_layout = defaultdict(list)
    for x in inst:
        by_layout[x[7]].append(x)
    chunks = [lst[i:i + CHUNK] for lst in by_layout.values() for i in range(0, len(lst), CHUNK)]
    t0 = time.time()
    out = {}
    with ProcessPoolExecutor(max_workers=max(1, jobs), initializer=_worker_init) as ex:
        for part in ex.map(_replay_chunk, chunks):
            out.update(part)
    print(f"🔁 Chạy lại {len(inst):,} dòng đại diện / {len({x[0] for x in inst}):,} mẫu ({len(chunks)} sheet ảo) trong {time.time() - t0:.0f}s")
    return out


def _snap_path(name):
    return os.path.join(SNAP_DIR, f"{name}.json")


def save_snapshot(name, data):
    os.makedirs(SNAP_DIR, exist_ok=True)
    with open(_snap_path(name), "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)


def load_snapshot(name):
    with open(_snap_path(name), encoding="utf-8") as f:
        return json.load(f)


def diff(before, after, con):
    """So 2 ảnh chụp theo dòng đại diện → gom theo mẫu; đếm dòng / file bị ảnh hưởng qua thư viện."""
    changed = {}
    for iid in set(before) | set(after):
        b, a = before.get(iid), after.get(iid)
        if b is None or a is None:
            continue  # dòng đại diện mới (thư viện thay đổi) — không coi là đổi
        if b["out"] != a["out"]:
            changed.setdefault(a["sig"], []).append((iid, b["out"], a["out"]))
    sig_rows = defaultdict(int)
    sig_files = defaultdict(set)
    if changed:
        q = ",".join("?" * len(changed))
        for sig, f in con.execute(f"SELECT sig, file FROM rows WHERE sig IN ({q})", list(changed)):
            sig_rows[sig] += 1
            sig_files[sig].add(f)
    return changed, sig_rows, sig_files


def _fmt_out(o):
    x = o[0] if o else {}
    p = x.get("effective_sell_unit")
    return f"{x.get('status')} {x.get('category') or ''} {x.get('model_std') or ''} {f'{p:,}' if isinstance(p, int) else ''}".strip()


# ------------------------------------------------------------------ TẦNG 3: bộ file canh gác
def _instance_features(v):
    """Đặc trưng 1 dòng đại diện: trạng thái / lý do lọc, loại hàng, gốc Model + hậu tố, nguồn giá, id rule kích hoạt."""
    f = set()
    for o in v.get("out", []):
        st = str(o.get("status") or "")
        f.add("S:" + st.split(":")[0] + (":" + st.split(":")[1] if st.startswith("SKIP:") else ""))
        cat = o.get("category") or "?"
        f.add("C:" + cat)
        for part in ("" if cat in ("THUONG_MAI", "KHAC") else str(o.get("model_std") or "")).split(" + "):  # hàng TM không có Model Swind
            toks = [t for t in part.split("+") if t]
            if toks:
                f.add(f"M:{cat}:{re.sub(r'[0-9.]+', '#', toks[0])}")
                f |= {f"SUF:{cat}:{t}" for t in toks[1:] if len(t) <= 4}
        if o.get("price_source"):
            f.add("P:" + str(o["price_source"]))
    f |= {"R:" + t for t in v.get("trace", [])}
    return f


def canary(snapshot="baseline", con=None, quiet=False):
    """Chọn ÍT file nhất phủ MỌI đặc trưng (rule kích hoạt, loại kết quả, kiểu bố cục) — phủ tập tham lam, ưu tiên file nhẹ."""
    con = con or _db()
    snap = load_snapshot(snapshot)
    sig_feats = defaultdict(set)
    for v in snap.values():
        sig_feats[v["sig"]] |= _instance_features(v)
    file_feats = defaultdict(set)
    for sig, f in con.execute("SELECT DISTINCT sig, file FROM rows"):
        file_feats[f] |= sig_feats.get(sig, set())
    for f, fs in con.execute("SELECT file, feats FROM sheet_feats"):
        file_feats[f] |= set(json.loads(fs))
    sizes = {}
    for f in file_feats:
        p_in = os.path.join(INPUT_GLOB_DIR, f)
        if not os.path.exists(p_in):
            p_in = next((os.path.join(INPUT_GLOB_DIR, x) for x in os.listdir(INPUT_GLOB_DIR) if _nfc(x) == f), p_in)
        sizes[f] = os.path.getsize(p_in) if os.path.exists(p_in) else 1 << 20
    universe = set().union(*file_feats.values()) if file_feats else set()
    left, chosen = set(universe), []
    while left:
        best = max(file_feats, key=lambda f: (len(file_feats[f] & left) / (1 + sizes[f] / 1e6), -sizes[f]))
        gain = file_feats[best] & left
        if not gain:
            break
        chosen.append((best, sorted(gain)))
        left -= gain
    names = sorted(f for f, _ in chosen)
    # Rule có trong bảng JSON mà KHÔNG dòng nào trong input/ kích hoạt → chỗ hở của bộ kiểm thử
    all_rules = set()
    for fn, key in (("diffuser_rules.json", "thu_tu_uu_tien"), ("duct_rules.json", "thu_tu_nhan_dien")):
        try:
            with open(os.path.join(PROJECT_ROOT, "data", "master_data", fn), encoding="utf-8") as fh:
                all_rules |= {"R:" + r["id"] for r in json.load(fh).get(key, []) if isinstance(r, dict) and r.get("id")}
        except Exception:  # noqa: BLE001
            pass
    uncovered_rules = sorted(all_rules - universe)
    with open(CANARY_PATH, "w", encoding="utf-8") as fh:
        fh.write("\n".join(names) + "\n")
    rare = defaultdict(int)
    for fs in file_feats.values():
        for x in fs:
            rare[x] += 1
    lines = ["# Bộ file canh gác (tầng 3)", "", f"**{len(names)} / {len(file_feats)} file phủ {len(universe)} đặc trưng** "
             f"(rule kích hoạt R:, loại kết quả S:/C:/M:/SUF:/P:, bố cục L:/BOCUC:/FLAG:)", "",
             f"⚠️ Rule chưa có file nào kiểm tới ({len(uncovered_rules)}): {', '.join(x[2:] for x in uncovered_rules) or '—'}", "",
             "| File | Đặc trưng mới phủ | Đặc trưng chỉ file này có |", "|---|---|---|"]
    for f, gain in chosen:
        only = [x for x in gain if rare[x] == 1]
        lines.append(f"| {f} | {len(gain)} | {', '.join(only[:8])}{' …' if len(only) > 8 else ''} |")
    with open(CANARY_REPORT, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines) + "\n")
    if not quiet:
        size_all, size_c = sum(sizes.values()), sum(sizes[f] for f in names)
        print(f"🛡️  Bộ canh gác: {len(names)}/{len(file_feats)} file phủ {len(universe)} đặc trưng "
              f"({size_c / size_all:.0%} dung lượng input) → {CANARY_PATH}\n📄 {CANARY_REPORT}")
        if uncovered_rules:
            print(f"⚠️  {len(uncovered_rules)} rule chưa có file nào kiểm tới: {', '.join(x[2:] for x in uncovered_rules)}")
    return names


def check(jobs, baseline="baseline"):
    con = _db()
    if not os.path.exists(_snap_path(baseline)):
        print(f"⛔ Chưa có ảnh chụp chuẩn '{baseline}'. Chạy --set-baseline trên code đã duyệt trước.")
        return 2
    after = replay(jobs)
    save_snapshot("latest", after)
    changed, sig_rows, sig_files = diff(load_snapshot(baseline), after, con)
    files = sorted({f for s in sig_files.values() for f in s})
    n_rows = sum(sig_rows.values())
    print(f"\n📋 {len(changed)} mẫu đổi kết quả | ảnh hưởng {n_rows:,} dòng | {len(files)} file")
    lines = ["# Kiểm thử theo mẫu dòng", "", f"**{len(changed)} mẫu đổi | {n_rows:,} dòng | {len(files)} file**", "",
             "| Dòng đại diện | Số dòng cùng mẫu | Số file | Trước | Sau |", "|---|---|---|---|---|"]
    for sig, lst in sorted(changed.items(), key=lambda kv: -sig_rows[kv[0]]):
        iid, b, a = lst[0]
        name = con.execute("SELECT cells, title FROM rows WHERE file=? AND sheet=? AND row=?", iid.split("|")[:2] + [int(iid.split("|")[2])]).fetchone()
        nm = (json.loads(name[0]).get("name") if name else "") or ""
        lines.append(f"| {iid} — {str(nm)[:60]} | {sig_rows[sig]} | {len(sig_files[sig])} | {_fmt_out(b)} | {_fmt_out(a)} |")
    for ln in lines[6:36]:
        print("  " + ln)
    if len(lines) > 36:
        print(f"  ... (+{len(lines) - 36} mẫu) — xem {REPORT_PATH}")
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    with open(AFFECTED_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(files) + ("\n" if files else ""))
    canary_files = canary(baseline, con, quiet=True)
    e2e = sorted(set(files) | set(canary_files))
    with open(E2E_FILES_PATH, "w", encoding="utf-8") as f:
        f.write("\n".join(e2e) + "\n")
    if files:
        print(f"📄 {REPORT_PATH}")
    else:
        print("✅ Không mẫu nào đổi kết quả so với chuẩn.")
    print(f"🧪 E2E đầy đủ (tầng 3): {len(files)} file bị ảnh hưởng + {len(canary_files)} file canh gác = {len(e2e)} file\n"
          f"   ./venv/bin/python src/swind_e2e_regression.py --modes default,duct --files-from {E2E_FILES_PATH}")
    return 1 if changed else 0


def main():
    ap = argparse.ArgumentParser(description="Thư viện mẫu dòng + chạy lại theo mẫu (kiểm thử hồi quy tầng 1 + 2)")
    ap.add_argument("--build", action="store_true", help="Tầng 1: đọc file BOQ mới / đã đổi vào thư viện")
    ap.add_argument("--force", action="store_true", help="Cùng --build: đọc lại toàn bộ (sau khi sửa phần đọc cấu trúc BOQ)")
    ap.add_argument("--set-baseline", action="store_true", help="Chạy lại theo mẫu và lưu làm ảnh chụp chuẩn")
    ap.add_argument("--check", action="store_true", help="Chạy lại theo mẫu và so với ảnh chụp chuẩn")
    ap.add_argument("--stats", action="store_true")
    ap.add_argument("--canary", action="store_true", help="Tầng 3: chọn bộ file canh gác phủ mọi rule / loại kết quả / bố cục")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2))
    a = ap.parse_args()
    rc = 0
    if a.build:
        build(a.jobs, force=a.force)
    if a.set_baseline:
        save_snapshot("baseline", replay(a.jobs))
        print(f"💾 Đã lưu ảnh chụp chuẩn: {_snap_path('baseline')}")
    if a.check:
        rc = check(a.jobs)
    if a.canary:
        canary()
    if a.stats:
        stats()
    if not (a.build or a.set_baseline or a.check or a.stats or a.canary):
        ap.print_help()
    sys.exit(rc)


if __name__ == "__main__":
    main()
