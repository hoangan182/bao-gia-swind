#!/usr/bin/env python3
"""
Agent 10 — Old-Quote Price Carrier (On-Demand, KHÔNG nằm trong luồng báo giá hằng ngày)

Bài toán: khách gửi BOQ mới, trong khi dự án đã có file báo giá cũ (BG...). Cần:
  1. Nhặt giá từ báo giá cũ sang các dòng BOQ trùng mặt hàng + đúng kích thước.
  2. Các dòng chưa có trong báo giá cũ mới chạy báo giá mới theo hệ thống chuẩn.

Cách làm (không sửa luồng chính):
  - Ghép dòng theo chữ ký: Loại hàng (FD/MFD/MD/VCD/NRD/PRD/Louver/LCCT/Cửa gió) + Kích thước
    + Phụ kiện (OBD / LCCT / Lọc) + Kiểu nan cửa gió (sọt trứng / khe / khuếch tán / nan thẳng).
  - Dòng khớp chắc chắn (EXACT) -> nhặt giá cũ. Dòng khớp chưa chắc (đảo kích thước, kiểu nan không rõ,
    báo giá cũ đã đổi loại hàng, ví dụ "FD -> Chuyển sang MFD") -> KHÔNG tự nhặt, liệt kê để hỏi User
    (chấp nhận bằng --accept-review / --accept-converted).
  - Phần còn lại: tạo BOQ tạm đã xóa trắng các dòng đã nhặt giá -> gọi src/swind_master_runner.py
    (giữ nguyên toàn bộ rule & Cổng kiểm soát cuối) -> ghép lại thành 1 Sheet 'BG' theo đúng thứ tự BOQ.

Sử dụng:
  ./venv/bin/python src/agent_10_old_quote_carrier.py "<BOQ.xlsx>" \
      --old-quote "<BG_cu.xlsx>" --old-sheets "Sheet BG 1,Sheet BG 2" [--accept-review] [--accept-converted] \
      [--dry-run] [các cờ của swind_master_runner, ví dụ --only-cua-van --spec-priority note]
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import unicodedata
from copy import copy

import openpyxl
from openpyxl.formula.translate import Translator
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(BASE_DIR, "src"))
from swind_utils import detect_boq_header  # noqa: E402

RUNNER = os.path.join(BASE_DIR, "src", "swind_master_runner.py")
VALVE_FAMILIES = {"FD", "MFD", "MD", "VCD", "NRD", "PRD", "PRD_MOTOR"}
FAMILY_LABEL = {
    "FD": "Van chặn lửa FD", "MFD": "Van chặn lửa động cơ MFD", "MD": "Van động cơ MD", "VCD": "Van VCD",
    "NRD": "Van 1 chiều NRD", "PRD": "Van xả áp cơ", "PRD_MOTOR": "Van xả áp điện", "LOUVER": "Louver",
    "LCCT": "Lưới chắn côn trùng", "GRILLE": "Cửa gió",
}


# ----------------------------------------------------------------------------------------------
# Chữ ký mặt hàng
# ----------------------------------------------------------------------------------------------
def norm(s):
    s = unicodedata.normalize("NFD", str(s or "")).replace("đ", "d").replace("Đ", "D")
    s = "".join(ch for ch in s if unicodedata.category(ch) != "Mn")
    return re.sub(r"\s+", " ", s).strip().upper()


KTC_MARK = " (KTC)"


def norm_name(s):
    s = str(s or "")
    if s.endswith(KTC_MARK):
        s = s[: -len(KTC_MARK)]
    return re.sub(r"\s+", " ", s).strip().lower()


def parse_size(text):
    t = norm(text)
    m = re.search(r"(\d{2,5})\s*[X×*]\s*(\d{2,5})", t)
    if m:
        return ("R", int(m.group(1)), int(m.group(2)))
    m = re.search(r"(?:\bD|Ø|\bPHI)\s*(\d{2,4})\b", t)
    if m:
        return ("D", int(m.group(1)))
    return None


def family_of(text):
    t = norm(text)
    if "XA AP" in t:
        return "PRD_MOTOR" if ("DIEN" in t or "DONG CO" in t) else "PRD"
    if re.search(r"\bM-?F(S)?D\b|MFSD", t) or (("CHAN LUA" in t or "NGAN CHAY" in t) and ("DONG CO" in t or "MO TO" in t)):
        return "MFD"
    if re.search(r"\bFD\b|\bFSD\b|\bFSS\b", t) or "CHAN LUA" in t or "NGAN CHAY" in t:
        return "FD"
    if re.search(r"\bMD\b", t) or "VAN GIO DONG CO" in t:
        return "MD"
    if "NRD" in t or "1 CHIEU" in t or "MOT CHIEU" in t:
        return "NRD"
    if "VCD" in t or "DIEU CHINH LUU LUONG" in t or "VAN TAY GAT" in t:
        return "VCD"
    if "LOUVER" in t or re.search(r"\b(FAL|EAL|OAL|S?WL)\b", t):
        return "LOUVER"
    if t.startswith("LCCT") or t.startswith("LUOI CHAN CON TRUNG"):
        return "LCCT"
    if re.search(r"\b(CUA GIO|MIENG)\b|\b[A-Z]{1,3}AG\b|\bSEG\b", t):
        return "GRILLE"
    return None


def model_family(model):
    t = norm(model)
    if not t:
        return None
    if "MFD" in t or "MFSD" in t:
        return "MFD"
    if re.search(r"E-FD|\bFD\b|FSD|FSS", t):
        return "FD"
    if "PRD" in t:
        return "PRD_MOTOR" if re.search(r"\bMD\b", t) else "PRD"
    if re.search(r"\bMD\b", t):
        return "MD"
    if "NRD" in t:
        return "NRD"
    if "VCD" in t:
        return "VCD"
    return None


def accessories(text):
    t = norm(text)
    acc = set()
    if re.search(r"\bOBD\b", t):
        acc.add("OBD")
    if re.search(r"LCCT|\bI\.?S\b|CON TRUNG|INSECT", t):
        acc.add("LCCT")
    if re.search(r"\bLLB\b|\bG4\b|PHIN LOC|LOC BUI|LUOI LOC|FILTER", t):
        acc.add("FILTER")
    return frozenset(acc)


def profile_from_text(text):
    t = norm(text)
    if "SOT TRUNG" in t:
        return "EGG"
    if "KHUECH TAN" in t:
        return "DIFF"
    if re.search(r"\bKHE\b", t):
        return "SLOT"
    if "NAN THANG" in t or "BAU DUC" in t or "1 LOP" in t or "MOT LOP" in t:
        return "BAR"
    return None


def profile_from_model(model):
    t = norm(model)
    if not t:
        return None
    if "ECG" in t:
        return "EGG"
    if "DLS" in t or "CLB" in t:
        return "SLOT"
    if "SDG" in t or re.search(r"\bDG\b", t):
        return "BAR"
    if "SKD" in t or re.match(r"^S?SD\b", t):
        return "DIFF"
    return None


def grille_code(text):
    m = re.search(r"\b(EAG|SAG|RAG|FAG|PAG|SEG|MAG|OAG|EXG)\b", norm(text))
    return m.group(1) if m else None


def build_signature(name, extra, model, size_fallback=None):
    """name: cột Tên | extra: Spec/Ghi chú | model: cột Model. Họ hàng xác định theo cột Tên (giống --spec-priority name)."""
    fam_name = family_of(name)
    fam_model = model_family(model)
    fam = fam_name or fam_model or family_of(extra)
    size = parse_size(name)
    size_from_name = size is not None
    if size is None and fam in VALVE_FAMILIES:
        size = size_fallback
    full = f"{name} {extra}"
    sig = {"family": fam, "family_name": fam_name, "family_model": fam_model, "size": size, "size_from_name": size_from_name}
    if fam in ("GRILLE", "LOUVER"):
        sig["acc"] = accessories(full)
    if fam == "GRILLE":
        sig["profile"] = profile_from_text(name) or profile_from_text(extra) or profile_from_model(model)
        sig["code"] = grille_code(name)
    return sig


# ----------------------------------------------------------------------------------------------
# Đọc báo giá cũ
# ----------------------------------------------------------------------------------------------
def _num(v):
    if v is None or isinstance(v, bool):
        return None
    if isinstance(v, (int, float)):
        return float(v)
    try:
        return float(str(v).replace(",", "").strip())
    except ValueError:
        return None


def _old_header(rows):
    for i, row in enumerate(rows[:40]):
        texts = [norm(v) for v in row]
        if any("DANH MUC" in t for t in texts) and any(("PRICE" in t or "DON GIA" in t) for t in texts):
            cmap = {}
            for c, t in enumerate(texts):
                if not t:
                    continue
                if "DANH MUC" in t:
                    cmap.setdefault("name", c)
                elif t.startswith("MODEL"):
                    cmap.setdefault("model", c)
                elif "THUONG HIEU" in t:
                    cmap.setdefault("brand", c)
                elif "KICH THUOC" in t:
                    cmap.setdefault("a1", c)
                elif t.startswith("MODUL"):
                    cmap.setdefault("modul", c)
                elif t == "L":
                    cmap.setdefault("l", c)
                elif "DO DAY" in t:
                    cmap.setdefault("thk", c)
                elif "THANH TIEN" in t or t.startswith("TOTAL"):
                    cmap.setdefault("total", c)
                elif "PRICE" in t or "DON GIA" in t:
                    cmap.setdefault("price", c)
                elif "UNIT" in t or "DON VI" in t:
                    cmap.setdefault("unit", c)
                elif "Q'TY" in t or "SO LUONG" in t:
                    cmap.setdefault("qty", c)
                elif "REMARK" in t or "GHI CHU" in t:
                    cmap.setdefault("remark", c)
            if "name" in cmap and "price" in cmap:
                if cmap["name"] + 1 not in cmap.values() and not texts[cmap["name"] + 1]:
                    cmap["note"] = cmap["name"] + 1
                return i, cmap
    return None, None


def list_quote_sheets(path):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    out = []
    for ws in wb.worksheets:
        rows = [r for r in ws.iter_rows(min_row=1, max_row=40, max_col=25, values_only=True)]
        if _old_header(rows)[0] is not None:
            out.append(ws.title)
    wb.close()
    return out


def load_old_quote(path, sheets):
    wb = openpyxl.load_workbook(path, read_only=True, data_only=True)
    entries = []
    for prio, sh in enumerate(sheets):
        if sh not in wb.sheetnames:
            raise SystemExit(f"⛔ Không tìm thấy sheet '{sh}' trong file báo giá cũ. Các sheet: {wb.sheetnames}")
        rows = [r for r in wb[sh].iter_rows(min_row=1, max_col=25, values_only=True)]
        h_idx, cmap = _old_header(rows)
        if h_idx is None:
            raise SystemExit(f"⛔ Sheet '{sh}' không có header báo giá (cột 'Danh mục sản phẩm' + 'Đơn giá').")

        def g(row, key, off=0):
            c = cmap.get(key)
            return row[c + off] if c is not None and c + off < len(row) else None

        for i in range(h_idx + 1, len(rows)):
            row = rows[i]
            name = g(row, "name")
            price = _num(g(row, "price"))
            if not name or not price or price <= 0:
                continue
            a1, a2 = _num(g(row, "a1")), _num(g(row, "a1", 1))
            fallback = ("R", int(a1), int(a2)) if a1 and a2 else (("D", int(a1)) if a1 else None)
            note = str(g(row, "note") or "")
            remark = str(g(row, "remark") or "")
            model = str(g(row, "model") or "")
            sig = build_signature(str(name), f"{note} {remark}", model, size_fallback=fallback)
            if sig["family"] is None or sig["size"] is None:
                continue
            # Báo giá cũ đã đổi loại (VD: tên 'FD', ghi chú 'Chuyển sang MFD', model MFD) -> loại thực tế theo Model
            sig["family_priced"] = sig["family_model"] or sig["family"]
            entries.append({
                "sheet": sh, "row": i + 1, "prio": prio, "name": str(name).strip(), "note": note.strip(),
                "model": model.strip(), "brand": g(row, "brand"),
                "a1": g(row, "a1"), "a2": g(row, "a1", 1), "b1": g(row, "a1", 2), "b2": g(row, "a1", 3),
                "modul": g(row, "modul"), "l": g(row, "l"), "thk": g(row, "thk"),
                "price": int(round(price)), "remark": remark.strip(), "sig": sig, "name_col": cmap["name"] + 1,
            })
    wb.close()
    return entries


YELLOW = {"FFFFFF00", "00FFFF00"}


def mark_yellow(path, entries):
    """Đánh dấu dòng BG cũ được bôi vàng (ô Tên) — Kỹ thuật dùng màu vàng để chỉ định dòng thật sự đổi loại."""
    wb = openpyxl.load_workbook(path, data_only=True)
    for e in entries:
        fg = wb[e["sheet"]].cell(e["row"], e["name_col"]).fill
        e["yellow"] = bool(fg and fg.fill_type == "solid" and fg.fgColor.type == "rgb" and fg.fgColor.rgb in YELLOW)
    wb.close()


# ----------------------------------------------------------------------------------------------
# Đọc BOQ khách
# ----------------------------------------------------------------------------------------------
def load_boq_rows(path, sheet=None):
    wb = openpyxl.load_workbook(path, data_only=True)
    ws = wb[sheet] if sheet else wb.worksheets[0]
    header_row, cmap, hidden_rows, _, _ = detect_boq_header(ws)
    get = lambda r, k: ws.cell(r, cmap[k]).value if k in cmap else None  # noqa: E731
    rows = []
    for r in range(header_row + 1, ws.max_row + 1):
        if r in hidden_rows:
            continue
        name = get(r, "name")
        if name is None or str(name).strip() == "":
            continue
        unit = get(r, "unit")
        qty = get(r, "qty")
        is_item = unit is not None and str(unit).strip() != ""
        rows.append({
            "row": r, "name": str(name).strip(), "spec": str(get(r, "spec") or ""), "model": str(get(r, "model") or ""),
            "unit": unit, "qty": qty, "is_item": is_item,
        })
    return ws.title, rows


# ----------------------------------------------------------------------------------------------
# Ghép dòng
# ----------------------------------------------------------------------------------------------
def _size_rel(a, b):
    if a is None or b is None or a[0] != b[0]:
        return None
    if a == b:
        return "exact"
    if a[0] == "R" and (a[1], a[2]) == (b[2], b[1]):
        return "swap"
    return None


def match_row(item, entries):
    sig = build_signature(item["name"], item["spec"], item["model"])
    item["sig"] = sig
    fam = sig["family"]
    if fam is None or sig["size"] is None:
        return {"status": "NEW", "reason": "Không nhận diện được loại hàng / kích thước"}

    cands, converted, near = [], [], []
    for e in entries:
        es = e["sig"]
        rel = _size_rel(sig["size"], es["size"])
        if rel is None:
            continue
        if es["family_priced"] != fam:
            if es["family"] == fam:
                converted.append((e, rel))
            continue
        reasons = []
        if rel == "swap":
            reasons.append(f"đảo chiều kích thước ({es['size'][1]}x{es['size'][2]})")
        if fam in ("GRILLE", "LOUVER"):
            if sig["acc"] != es["acc"]:
                near.append((e, f"khác phụ kiện (BOQ={'+'.join(sorted(sig['acc'])) or 'không'}, BG cũ={'+'.join(sorted(es['acc'])) or 'không'})"))
                continue
        if fam == "GRILLE":
            p_new, p_old = sig["profile"], es["profile"]
            if p_new and p_old and p_new != p_old:
                near.append((e, f"khác kiểu nan (BOQ={p_new}, BG cũ={p_old})"))
                continue
            if not (p_new and p_old):
                if not (p_new is None and p_old is None and sig["code"] and sig["code"] == es["code"]):
                    reasons.append(f"kiểu nan chưa xác định (BOQ={p_new or '?'}, BG cũ={p_old or '?'})")
        score = (
            0 if not reasons else 1,
            0 if es["size_from_name"] else 1,  # ưu tiên dòng BG cũ ghi KT ngay trong tên (hơn KT suy từ cột A1/A2)
            0 if (fam != "GRILLE" or sig["code"] == es["code"]) else 1,
            e["prio"], e["row"],
        )
        cands.append((score, e, reasons))

    if cands:
        cands.sort(key=lambda x: x[0])
        best_score, best, reasons = cands[0]
        same_tier = [c for c in cands if c[0][:3] == best_score[:3]]
        prices = sorted({c[1]["price"] for c in same_tier})
        res = {"status": "EXACT" if not reasons else "REVIEW", "entry": best, "reasons": list(reasons)}
        if len(prices) > 1:
            res["reasons"].append(
                "BG cũ có nhiều giá cho cùng mặt hàng: " + ", ".join(f"{p:,}" for p in prices)
                + f" -> lấy {best['sheet']}!{best['row']}"
            )
        return res
    if converted:
        e, rel = sorted(converted, key=lambda x: (x[1] != "exact", x[0]["prio"], x[0]["row"]))[0]
        return {
            "status": "CONVERTED", "entry": e,
            "reasons": [f"BG cũ đã đổi '{e['name']}' sang {FAMILY_LABEL.get(e['sig']['family_priced'], e['sig']['family_priced'])} ({e['model']}{', ' + e['note'] if e['note'] else ''})"],
        }
    if near:
        e, why = sorted(near, key=lambda x: ("kiểu nan" not in x[1], x[0]["prio"], x[0]["row"]))[0]
        return {"status": "NEW", "reason": f"Không có hàng trùng; gợi ý BG cũ cùng KT nhưng {why}: {e['sheet']}!{e['row']} '{e['name']}' {e['price']:,}đ"}
    return {"status": "NEW", "reason": "Không có trong báo giá cũ"}


# ----------------------------------------------------------------------------------------------
# Ghép Sheet BG
# ----------------------------------------------------------------------------------------------
def _copy_style(src, dst):
    if src.has_style:
        dst.font = copy(src.font)
        dst.border = copy(src.border)
        dst.fill = copy(src.fill)
        dst.number_format = src.number_format
        dst.protection = copy(src.protection)
        dst.alignment = copy(src.alignment)


def _footer_start(ws):
    for r in range(14, ws.max_row + 1):
        a = norm(ws.cell(r, 1).value)
        if a.startswith("TOTAL") or a.startswith("TONG TRUOC"):
            return r
    return ws.max_row + 1


def _is_item_bg_row(ws, r):
    return any(ws.cell(r, c).value not in (None, "") for c in (3, 12, 13, 14))


def build_merged_bg(wb_out, ws_runner, boq_rows, carried, bg_title):
    """ws_runner: Sheet 'BG' do runner sinh cho phần còn lại (hoặc None). carried: {row_boq: match}."""
    ws = wb_out.create_sheet(bg_title)
    thin = Side(style="thin", color="000000")
    hair = Side(style="hair", color="000000")
    item_border = Border(left=thin, right=thin, top=hair, bottom=hair)
    yellow = PatternFill("solid", fgColor="FFFF00")

    footer_rows, body_map, tpl_item_row = [], {}, None
    if ws_runner is not None:
        f_start = _footer_start(ws_runner)
        for col_l, dim in ws_runner.column_dimensions.items():
            ws.column_dimensions[col_l].width = dim.width
        for r in range(1, 14):
            if ws_runner.row_dimensions[r].height:
                ws.row_dimensions[r].height = ws_runner.row_dimensions[r].height
            for c in range(1, 17):
                src = ws_runner.cell(r, c)
                dst = ws.cell(r, c, value=src.value)
                _copy_style(src, dst)
        for m in ws_runner.merged_cells.ranges:
            if m.max_row <= 13:
                ws.merge_cells(str(m))
        # Căn dòng BG của runner về dòng BOQ (BG giữ đúng thứ tự BOQ, cột B = tên BOQ)
        remaining = [b for b in boq_rows if b["row"] not in carried]
        ptr, last_row = 0, None
        for r in range(14, f_start):
            b_val = norm_name(ws_runner.cell(r, 2).value)
            if not b_val and not _is_item_bg_row(ws_runner, r):
                continue
            hit = None
            if b_val:
                for k in range(ptr, len(remaining)):
                    if norm_name(remaining[k]["name"]) == b_val:
                        hit = k
                        break
            if hit is not None:
                ptr = hit + 1
                last_row = remaining[hit]["row"]
            body_map.setdefault(last_row, []).append(r)
            if tpl_item_row is None and _is_item_bg_row(ws_runner, r):
                tpl_item_row = r
        footer_rows = list(range(f_start, ws_runner.max_row + 1))
    else:
        widths = {"A": 6, "B": 38, "C": 20, "D": 14, "E": 9, "F": 9, "G": 9, "H": 9, "I": 8, "J": 8, "K": 9, "L": 9, "M": 11, "N": 16, "O": 18, "P": 44}
        for k, v in widths.items():
            ws.column_dimensions[k].width = v
        ws.cell(6, 1, "BẢNG BÁO GIÁ").font = Font(name="Times New Roman", size=14, bold=True)
        hdr = ["STT", "Danh mục sản phẩm", "Model", "Thương hiệu", "A1", "A2", "B1", "B2", "Modul", "L", "Độ dày", "Đơn vị", "Số lượng", "Đơn Giá (VNĐ)", "Thành tiền", "Ghi chú"]
        for c, v in enumerate(hdr, 1):
            cell = ws.cell(11, c, v)
            cell.font = Font(name="Times New Roman", size=10, bold=True)
            cell.border = Border(left=thin, right=thin, top=thin, bottom=thin)

    def write_item(r_out, vals, src_row=None, flag=False):
        for c, v in enumerate(vals, 1):
            cell = ws.cell(r_out, c, value=v)
            if src_row is not None:
                _copy_style(ws_runner.cell(src_row, c), cell)
            else:
                cell.font = Font(name="Times New Roman", size=10)
                cell.border = item_border
                cell.alignment = Alignment(horizontal="left" if c in (2, 16) else ("right" if c in (13, 14, 15) else "center"), vertical="center", wrap_text=True)
                if c in (13, 14, 15):
                    cell.number_format = "#,##0"
            if flag:
                cell.fill = yellow

    out_r, stt = 14, 0
    stats = {"carried_rows": 0, "carried_value": 0.0, "new_rows": 0, "new_value": 0.0, "unpriced_rows": 0, "unpriced_list": []}
    row_source = {}

    def emit_runner_row(rr):
        nonlocal out_r, stt
        vals = [ws_runner.cell(rr, c).value for c in range(1, 17)]
        if isinstance(vals[1], str) and vals[1].endswith(KTC_MARK):
            vals[1] = vals[1][: -len(KTC_MARK)]
        is_item = _is_item_bg_row(ws_runner, rr)
        if is_item:
            stt += 1
            vals[0] = stt
            if vals[13] not in (None, ""):
                vals[14] = f"=N{out_r}*M{out_r}"
        for c, v in enumerate(vals, 1):
            cell = ws.cell(out_r, c, value=v)
            _copy_style(ws_runner.cell(rr, c), cell)
        if ws_runner.row_dimensions[rr].height:
            ws.row_dimensions[out_r].height = ws_runner.row_dimensions[rr].height
        if is_item:
            q, p = _num(vals[12]) or 0.0, _num(vals[13])
            if p:
                stats["new_rows"] += 1
                stats["new_value"] += q * p
            elif q > 0:
                stats["unpriced_rows"] += 1
        out_r += 1

    for rr in body_map.get(None, []):
        emit_runner_row(rr)
    for b in boq_rows:
        if b["row"] in carried:
            e = carried[b["row"]]["entry"]
            stt += 1
            q = _num(b["qty"]) or 0.0
            vals = [stt, b["name"], e["model"] or None, "SWIND", e["a1"], e["a2"], e["b1"], e["b2"], e["modul"], e["l"], e["thk"],
                    b["unit"], b["qty"], e["price"], f"=N{out_r}*M{out_r}", e["remark"] or None]
            write_item(out_r, vals, src_row=tpl_item_row)
            stats["carried_rows"] += 1
            stats["carried_value"] += q * e["price"]
            row_source[b["row"]] = f"BG cũ {e['sheet']}!{e['row']}"
            out_r += 1
        elif b["row"] in body_map:
            for rr in body_map[b["row"]]:
                emit_runner_row(rr)
            row_source[b["row"]] = "Swind báo mới"
        elif b["is_item"]:
            stt += 1
            write_item(out_r, [stt, b["name"], None, None, None, None, None, None, None, None, None, b["unit"], b["qty"], None, None,
                               "Chưa có đơn giá"], src_row=tpl_item_row, flag=True)
            row_source[b["row"]] = "CHƯA CÓ GIÁ (runner không báo dòng này)"
            stats["unpriced_list"].append(b["row"])
            if (_num(b["qty"]) or 0) > 0:
                stats["unpriced_rows"] += 1
            out_r += 1
    last_body = out_r - 1

    # Chân trang: Tổng trước thuế / VAT / Tổng sau thuế + ghi chú (dời dòng, sửa lại công thức)
    if footer_rows:
        off = out_r - footer_rows[0]
        for fr in footer_rows:
            tr = fr + off
            if ws_runner.row_dimensions[fr].height:
                ws.row_dimensions[tr].height = ws_runner.row_dimensions[fr].height
            for c in range(1, 17):
                src = ws_runner.cell(fr, c)
                v = src.value
                if isinstance(v, str) and v.startswith("="):
                    v = Translator(v, origin=src.coordinate).translate_formula(ws.cell(tr, c).coordinate)
                    v = re.sub(r"(SUBTOTAL\(9,\s*)O\d+:O\d+", rf"\g<1>O14:O{last_body}", v)
                dst = ws.cell(tr, c, value=v)
                _copy_style(src, dst)
        for m in ws_runner.merged_cells.ranges:
            if m.min_row >= footer_rows[0]:
                ws.merge_cells(start_row=m.min_row + off, start_column=m.min_col, end_row=m.max_row + off, end_column=m.max_col)
    else:
        bold = Font(name="Times New Roman", size=10, bold=True)
        for i, (lbl, f) in enumerate([
            ("Total/ Tổng Trước thuế", f"=SUBTOTAL(9,O14:O{last_body})"),
            ("VAT 8%", f"=ROUND(O{out_r}*0.08, 0)"),
            ("Total Amount (including VAT 8%)/ Tổng sau thuế", f"=O{out_r}+O{out_r + 1}"),
        ]):
            ws.cell(out_r + i, 1, lbl).font = bold
            c = ws.cell(out_r + i, 15, f)
            c.font = bold
            c.number_format = "#,##0"
    return ws, stats, row_source


INHERIT_TOKENS = (r"\d|\bOBD\b|LCCT|LUOI|CON TRUNG|\bLOC\b|\bG4\b|FILTER|\bEI|DAY|\bTON\b|INOX|\bMM\b|KTC|\bCO\b|"
                  r"\bNAN\b|SOT TRUNG|\bKHE\b|KHUECH TAN|LOUVER|CAU CHI|DONG CO|MO TO|CACH NHIET|BOC|HOP")


def build_compact_boq(src_path, sheet, carried_rows, neck_rows, dest):
    """BOQ tạm RÚT GỌN cho runner: giữ header + các dòng HIỂN THỊ chưa nhặt giá, giữ nguyên TOÀN BỘ CỘT (cả cột Spec).
    Lý do (riêng luồng Agent 10, không sửa Agent 00B): BOQ có hàng nghìn dòng ẩn/trống trước dữ liệu khiến Agent 00B
    đếm 0 dòng -> 'chuẩn hóa' sang bảng chuẩn và bỏ cột Spec. Bản rút gọn được Agent 00B nhận là BOQ chuẩn -> giữ cột.
    Ghép lại BG theo tên dòng nên việc đánh lại số dòng không ảnh hưởng."""
    wb_src = openpyxl.load_workbook(src_path, data_only=True)
    ws_src = wb_src[sheet]
    header_row, cmap, hidden_rows, _, max_scan_col = detect_boq_header(ws_src)
    # Vùng header gồm cả dòng gộp ô bên dưới (VD header merge 6:7)
    header_end = max([header_row] + [m.max_row for m in ws_src.merged_cells.ranges if m.min_row <= header_row <= m.max_row])
    name_col = cmap.get("name", 2)
    max_col = max(ws_src.max_column, max_scan_col)
    wb_new = openpyxl.Workbook()
    ws_new = wb_new.active
    ws_new.title = sheet
    for col_l, dim in ws_src.column_dimensions.items():
        ws_new.column_dimensions[col_l].width = dim.width
        ws_new.column_dimensions[col_l].hidden = dim.hidden
    unit_col = cmap.get("unit")
    qty_col = cmap.get("qty")
    body = []  # (row, is_item) các dòng hiển thị có Tên, chưa nhặt giá
    for r in range(header_end + 1, ws_src.max_row + 1):
        if r in hidden_rows or r in carried_rows or ws_src.cell(r, name_col).value in (None, ""):
            continue
        is_item = any(ws_src.cell(r, c).value not in (None, "") for c in (unit_col, qty_col) if c)
        body.append((r, is_item))
    # Chỉ giữ Title có dòng hàng cần báo mới NGAY bên dưới (trước Title kế tiếp): bỏ các nhóm trống
    # (VD 'Ống gió' không còn dòng nào) để Agent 00B không coi Title là dòng ống gió bị sót.
    keep = set()
    # Dòng phụ của header (VD 'TỔNG CỘNG' dưới cột KL) trước dòng có Tên đầu tiên: giữ để detect_boq_header nhận đúng header
    first_named = body[0][0] if body else ws_src.max_row + 1
    for r in range(header_end + 1, first_named):
        if r not in hidden_rows and any(ws_src.cell(r, c).value not in (None, "") for c in range(1, max_col + 1)):
            keep.add(r)
    dropped_titles = []
    for i, (r, is_item) in enumerate(body):
        if is_item:
            keep.add(r)
            continue
        for r2, it2 in body[i + 1:]:
            if not it2:
                break
            # Title chỉ là tên nhóm chung (VD 'Van, miệng gió') không mang thông số -> bỏ: parser ghép Title vào tên dòng con,
            # chữ 'miệng gió' khiến van FD/NRD/VCD bị hiểu nhầm thành combo Cửa + Van. Title có thông số vẫn giữ để kế thừa.
            title = norm(f"{ws_src.cell(r, name_col).value} {ws_src.cell(r, cmap['spec']).value if cmap.get('spec') else ''}")
            if not re.search(INHERIT_TOKENS, title):
                dropped_titles.append(str(ws_src.cell(r, name_col).value).strip())
                break
            keep.add(r)
            break
    if dropped_titles:
        cnt = {}
        for t in dropped_titles:
            cnt[t] = cnt.get(t, 0) + 1
        print("  -> [BOQ tạm] Bỏ Title nhóm chung không mang thông số (tránh ghép nhầm combo): "
              + "; ".join(f"'{t}' x{n}" for t, n in cnt.items()))
    out_r = 0
    gap_done = False
    for r in range(1, ws_src.max_row + 1):
        if r > header_end and r not in keep:
            continue
        if r > header_end and not gap_done:
            out_r += 2  # 2 dòng trống ngăn cách: detect_boq_header gộp 2 dòng dưới header để dò header nhiều dòng
            gap_done = True
        out_r += 1
        for c in range(1, max_col + 1):
            src = ws_src.cell(r, c)
            v = src.value
            if r in neck_rows and c == name_col and v:
                v = f"{v}{KTC_MARK}"
            dst = ws_new.cell(out_r, c, value=v)
            _copy_style(src, dst)
        if ws_src.row_dimensions[r].height:
            ws_new.row_dimensions[out_r].height = ws_src.row_dimensions[r].height
        if r <= header_end and ws_src.row_dimensions[r].hidden:
            ws_new.row_dimensions[out_r].hidden = True
    for m in ws_src.merged_cells.ranges:
        if m.max_row <= header_end:
            ws_new.merge_cells(str(m))
    wb_new.save(dest)
    wb_src.close()


# ----------------------------------------------------------------------------------------------
# Main
# ----------------------------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Agent 10 — Nhặt giá từ báo giá cũ sang BOQ mới, phần còn lại báo giá mới")
    ap.add_argument("boq_file")
    ap.add_argument("--old-quote", required=True, help="File báo giá cũ (.xlsx)")
    ap.add_argument("--old-sheets", default=None, help="Các sheet báo giá cũ, ngăn cách dấu phẩy; sheet đứng trước được ưu tiên khi trùng giá")
    ap.add_argument("--boq-sheet", default=None, help="Sheet BOQ (mặc định: sheet đầu tiên)")
    ap.add_argument("--accept-review", action="store_true", help="Nhặt cả các dòng khớp CẦN XÁC NHẬN (đảo kích thước / kiểu nan chưa rõ)")
    ap.add_argument("--accept-converted", action="store_true", help="Nhặt cả các dòng mà BG cũ đã đổi loại hàng (VD: FD -> MFD)")
    ap.add_argument("--converted-yellow-only", action="store_true",
                    help="Chỉ nhặt nhóm 'BG cũ đã đổi loại' khi dòng BG cũ được BÔI VÀNG (Kỹ thuật chỉ định); dòng không vàng báo mới theo loại BOQ")
    ap.add_argument("--multi-price-new", action="store_true",
                    help="Dòng mà BG cũ có >=2 đơn giá khác nhau cho cùng mặt hàng -> KHÔNG nhặt giá cũ, Swind báo mới")
    ap.add_argument("--force-new", default=None, help="Danh sách dòng BOQ bắt buộc Swind báo mới (không nhặt giá cũ), VD '2956,2957'")
    ap.add_argument("--neck-rows", default=None,
                    help="Dòng BOQ (báo mới) hiểu kích thước là KÍCH THƯỚC CỔ, VD '2956,2957' (ghi dấu KTC vào cột Spec bản BOQ tạm; "
                         "không dùng --override theo dòng vì Agent 00B có thể đánh lại số dòng)")
    ap.add_argument("--dry-run", action="store_true", help="Chỉ in kết quả ghép giá, không chạy báo giá phần còn lại")
    args, runner_args = ap.parse_known_args()

    boq_path = os.path.abspath(args.boq_file)
    old_path = os.path.abspath(args.old_quote)
    if not args.old_sheets:
        cands = list_quote_sheets(old_path)
        print("⛔ Chưa chỉ định --old-sheets. Các sheet có dạng báo giá trong file cũ:")
        for s in cands:
            print(f"   • {s}")
        print("   -> Hỏi User nên nhặt giá từ sheet nào (thứ tự ưu tiên), rồi chạy lại với --old-sheets \"A,B\".")
        sys.exit(1)
    old_sheets = [s.strip() for s in args.old_sheets.split(",") if s.strip()]

    print("=" * 95)
    print("♻️  [Agent 10 - Old-Quote Price Carrier] Nhặt giá từ báo giá cũ -> phần còn lại báo giá mới")
    print("=" * 95)
    entries = load_old_quote(old_path, old_sheets)
    print(f"  -> Báo giá cũ: {os.path.basename(old_path)} | {len(entries)} dòng có giá đọc được từ {old_sheets}")
    boq_sheet, boq_rows = load_boq_rows(boq_path, args.boq_sheet)
    items = [b for b in boq_rows if b["is_item"]]
    print(f"  -> BOQ: {os.path.basename(boq_path)} [{boq_sheet}] | {len(items)} dòng mặt hàng (dòng hiển thị)")

    results = {b["row"]: match_row(b, entries) for b in items}
    accepted = {"EXACT"} | ({"REVIEW"} if args.accept_review else set()) | ({"CONVERTED"} if args.accept_converted else set())
    if args.converted_yellow_only:
        mark_yellow(old_path, entries)
        accepted.add("CONVERTED")
    carried = {r: m for r, m in results.items() if m["status"] in accepted
               and not (m["status"] == "CONVERTED" and args.converted_yellow_only and not m["entry"].get("yellow"))}
    force_new = {int(x) for x in re.findall(r"\d+", args.force_new or "")}
    is_multi = lambda m: any("nhiều giá" in x for x in m.get("reasons", []))  # noqa: E731
    dropped_multi = [r for r, m in carried.items() if args.multi_price_new and is_multi(m)]
    dropped_force = [r for r in carried if r in force_new]
    for r in set(dropped_multi) | set(dropped_force):
        carried.pop(r)
    if dropped_multi:
        print(f"  -> [--multi-price-new] {len(dropped_multi)} dòng BG cũ có nhiều đơn giá -> Swind báo mới: {', '.join(map(str, sorted(dropped_multi)))}")
    if force_new:
        print(f"  -> [--force-new] Swind báo mới theo yêu cầu: {', '.join(map(str, sorted(force_new)))}")
    pending = [(b, results[b["row"]]) for b in items if results[b["row"]]["status"] in ("REVIEW", "CONVERTED") and b["row"] not in carried
               and not (args.converted_yellow_only and results[b["row"]]["status"] == "CONVERTED")]
    if args.converted_yellow_only:
        conv_all = [b for b in items if results[b["row"]]["status"] == "CONVERTED"]
        conv_y = [b for b in conv_all if b["row"] in carried]
        print(f"  -> [--converted-yellow-only] Nhóm BG cũ đã đổi loại: {len(conv_y)} dòng khớp dòng BÔI VÀNG -> nhặt giá loại mới (VD MFD); "
              f"{len(conv_all) - len(conv_y)} dòng không vàng -> báo mới theo đúng loại BOQ.")
    multi = [(b, results[b["row"]]) for b in items if b["row"] in carried and any("nhiều giá" in x for x in results[b["row"]].get("reasons", []))]

    cnt = {k: sum(1 for m in results.values() if m["status"] == k) for k in ("EXACT", "REVIEW", "CONVERTED", "NEW")}
    print(f"  -> Kết quả ghép: Khớp chắc chắn={cnt['EXACT']} | Cần xác nhận={cnt['REVIEW']} | BG cũ đã đổi loại={cnt['CONVERTED']} | Không có trong BG cũ={cnt['NEW']}")
    print(f"  -> Nhặt giá cũ: {len(carried)} dòng | Báo giá mới bằng hệ thống: {len(items) - len(carried)} dòng")

    def _rows_str(lst, limit=25):
        return ", ".join(str(b["row"]) for b in lst[:limit]) + (f" ... (+{len(lst) - limit})" if len(lst) > limit else "")

    if pending:
        print("\n" + "-" * 95)
        print(f"⚠️ [HỎI LẠI USER] {len(pending)} dòng có mặt hàng tương tự trong BG cũ nhưng CHƯA tự nhặt giá (đang báo mới theo hệ thống):")
        print("-" * 95)
        conv = [(b, m) for b, m in pending if m["status"] == "CONVERTED"]
        if conv:
            groups = {}
            for b, m in conv:
                e = m["entry"]
                groups.setdefault((e["sig"]["family"], e["sig"]["family_priced"], e["model"]), []).append(b)
            for (f_from, f_to, model), lst in groups.items():
                qty = sum(_num(b["qty"]) or 0 for b in lst)
                print(f"  • [BG cũ đã đổi loại] {len(lst)} dòng {FAMILY_LABEL.get(f_from, f_from)} (tổng KL {qty:,.0f}): BG cũ đã báo thành "
                      f"{FAMILY_LABEL.get(f_to, f_to)} ({model}). Dòng BOQ: {_rows_str(lst)}")
            print("    -> Nhặt giá cũ (giá loại đã đổi) cho nhóm này: thêm --accept-converted")
        review = [(b, m) for b, m in pending if m["status"] == "REVIEW"]
        if review:
            print("| Dòng BOQ | Tên BOQ | KL | Dòng BG cũ | Tên BG cũ | Giá cũ | Lý do |")
            print("| ---: | :--- | ---: | :--- | :--- | ---: | :--- |")
            for b, m in review:
                e = m["entry"]
                print(f"| {b['row']} | {b['name'][:55]} | {b['qty']} | {e['sheet']}!{e['row']} | {e['name'][:35]} | {e['price']:,} | {'; '.join(m['reasons'])} |")
            print("    -> Nhặt giá cũ cho các dòng 'Cần xác nhận': thêm --accept-review")
    if multi:
        print(f"\n⚠️ {len(multi)} dòng có nhiều đơn giá khác nhau trong BG cũ (đã nhặt theo sheet ưu tiên / dòng đầu tiên — nêu cho User):")
        for b, m in multi:
            print(f"  • Dòng {b['row']} '{b['name'][:55]}': " + "; ".join(x for x in m["reasons"] if "nhiều giá" in x))
    hints = [(b, results[b["row"]]) for b in items if results[b["row"]]["status"] == "NEW" and "gợi ý" in results[b["row"]].get("reason", "")]
    news = [b for b in items if results[b["row"]]["status"] == "NEW"]
    if news:
        print(f"\nℹ️ {len(news)} dòng không có trong BG cũ -> báo giá mới. Dòng BOQ: {_rows_str(news)}")
        for b, m in hints:
            print(f"   • Dòng {b['row']} '{b['name'][:50]}': {m['reason']}")

    if args.dry_run:
        print("\n[--dry-run] Dừng sau bước ghép giá.")
        return 0

    # ---------------- Chạy runner chuẩn cho phần còn lại ----------------
    stem = os.path.splitext(os.path.basename(boq_path))[0]
    runner_file, rc = None, 0
    tmp_dir = tempfile.mkdtemp(prefix="swind_agent10_")
    try:
        remaining_items = [b for b in items if b["row"] not in carried]
        if remaining_items:
            reduced = os.path.join(tmp_dir, os.path.basename(boq_path))
            neck_rows = {int(x) for x in re.findall(r"\d+", args.neck_rows or "")}
            for r in sorted(neck_rows & set(carried)):
                print(f"  ⚠️ [--neck-rows] Bỏ qua dòng {r} (đã nhặt giá cũ — thêm vào --force-new nếu cần báo mới)")
            build_compact_boq(boq_path, boq_sheet, set(carried), neck_rows - set(carried), reduced)
            if neck_rows - set(carried):
                print(f"  -> [--neck-rows] Hiểu kích thước là KÍCH THƯỚC CỔ cho dòng: {', '.join(map(str, sorted(neck_rows - set(carried))))}")
            cmd = [sys.executable, RUNNER, reduced, "--non-interactive", "--auto-accept"] + runner_args
            print("\n" + "=" * 95)
            print(f"▶️  Báo giá mới {len(remaining_items)} dòng còn lại bằng hệ thống chuẩn (bảng tổng hợp của runner bên dưới CHỈ là phần báo mới)")
            print("=" * 95, flush=True)
            proc = subprocess.Popen(cmd, cwd=BASE_DIR, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, bufsize=1)
            for line in proc.stdout:
                sys.stdout.write(line)
                m = re.search(r"FILE BÁO GIÁ CUỐI CÙNG GỬI KHÁCH HÀNG:\s*(.+\.xlsx)", line)
                if m:
                    runner_file = m.group(1).strip()
            rc = proc.wait()
        else:
            print("\n  -> Toàn bộ dòng BOQ đã nhặt được giá cũ, không cần báo giá mới.")
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)

    project_dir = os.path.dirname(runner_file) if runner_file else os.path.join(BASE_DIR, "output", stem)
    os.makedirs(os.path.join(project_dir, "internal_estimation"), exist_ok=True)
    final_file = os.path.join(project_dir, f"{stem}.xlsx")

    # ---------------- Ghép file báo giá cuối ----------------
    ws_runner = None
    if runner_file and os.path.exists(runner_file):
        wb_r = openpyxl.load_workbook(runner_file)
        ws_runner = wb_r["BG"] if "BG" in wb_r.sheetnames else None
    wb_out = openpyxl.load_workbook(boq_path)
    bg_title = "BG" if "BG" not in wb_out.sheetnames else "BG_SWIND"
    ws_bg, stats, row_source = build_merged_bg(wb_out, ws_runner, boq_rows, carried, bg_title)
    wb_out.active = wb_out.sheetnames.index(bg_title)
    for w in wb_out.worksheets:
        if w.views.sheetView:
            w.views.sheetView[0].tabSelected = (w.title == bg_title)
    wb_out.save(final_file)

    # ---------------- Báo cáo nội bộ ----------------
    report = []
    for b in items:
        m = results[b["row"]]
        e = m.get("entry") or {}
        status = "NHẶT GIÁ CŨ" if b["row"] in carried else {"REVIEW": "CẦN XÁC NHẬN (đang báo mới)", "CONVERTED": "BG CŨ ĐỔI LOẠI (đang báo mới)"}.get(m["status"], "BÁO MỚI")
        report.append({
            "boq_row": b["row"], "name": b["name"], "qty": b["qty"], "status": status,
            "old_ref": f"{e['sheet']}!{e['row']}" if e else "", "old_name": e.get("name", ""), "old_price": e.get("price"),
            "reasons": m.get("reasons") or ([m["reason"]] if m.get("reason") else []), "price_source": row_source.get(b["row"], ""),
        })
    rep_json = os.path.join(project_dir, "internal_estimation", "OLD_QUOTE_MATCH_REPORT.json")
    with open(rep_json, "w", encoding="utf-8") as f:
        json.dump({"boq": boq_path, "old_quote": old_path, "old_sheets": old_sheets, "rows": report}, f, ensure_ascii=False, indent=1, default=str)
    rep_xlsx = os.path.join(project_dir, "internal_estimation", "OLD_QUOTE_MATCH_REPORT.xlsx")
    wb_rep = openpyxl.Workbook()
    ws_rep = wb_rep.active
    ws_rep.title = "DOI_CHIEU"
    ws_rep.append(["Dòng BOQ", "Tên BOQ", "KL", "Trạng thái", "Dòng BG cũ", "Tên BG cũ", "Giá cũ", "Ghi chú ghép"])
    fills = {"NHẶT GIÁ CŨ": "C6EFCE", "CẦN XÁC NHẬN (đang báo mới)": "FFEB9C", "BG CŨ ĐỔI LOẠI (đang báo mới)": "FFC7CE"}
    for x in report:
        ws_rep.append([x["boq_row"], x["name"], x["qty"], x["status"], x["old_ref"], x["old_name"], x["old_price"], "; ".join(x["reasons"])])
        if x["status"] in fills:
            for c in range(1, 9):
                ws_rep.cell(ws_rep.max_row, c).fill = PatternFill("solid", fgColor=fills[x["status"]])
    for col, w in zip("ABCDEFGH", (9, 60, 8, 30, 34, 40, 14, 70)):
        ws_rep.column_dimensions[col].width = w
    ws_rep.freeze_panes = "A2"
    wb_rep.save(rep_xlsx)

    # ---------------- Tổng hợp ----------------
    total = stats["carried_value"] + stats["new_value"]
    vat = round(total * 0.08)
    print("\n" + "=" * 95)
    print("📈 [Agent 10] BẢNG TỔNG HỢP BÁO GIÁ (GIÁ CŨ + BÁO MỚI)")
    print(f"📁 File Báo Giá Cuối Cùng: {final_file}")
    print("=" * 95)
    print("| Phần | Số dòng | Trước VAT (VNĐ) |")
    print("| :--- | ---: | ---: |")
    print(f"| Nhặt giá từ báo giá cũ | {stats['carried_rows']} | {stats['carried_value']:,.0f} |")
    print(f"| Swind báo giá mới | {stats['new_rows']} | {stats['new_value']:,.0f} |")
    print(f"| **TỔNG TRƯỚC VAT** | **{stats['carried_rows'] + stats['new_rows']}** | **{total:,.0f}** |")
    print(f"| VAT 8% | | {vat:,.0f} |")
    print(f"| **TỔNG SAU VAT** | | **{total + vat:,.0f}** |")
    if stats["unpriced_list"]:
        print(f"\n⛔ BÁO GIÁ CHƯA HOÀN CHỈNH: {len(stats['unpriced_list'])} dòng BOQ không có trong BG của runner (tô vàng): "
              + ", ".join(map(str, stats["unpriced_list"][:30])) + " -> kiểm tra log runner ở trên.")
        rc = rc or 2
    elif stats["unpriced_rows"]:
        print(f"\n⛔ Còn {stats['unpriced_rows']} dòng có KL chưa có đơn giá (xem [KIỂM SOÁT CUỐI] của runner ở trên).")
        rc = rc or 2
    if pending:
        print(f"⚠️ {len(pending)} dòng chờ User xác nhận có nhặt giá cũ hay không (bảng HỎI LẠI USER ở trên).")
    print(f"ℹ️ Đối chiếu từng dòng: {rep_xlsx}")
    return rc


if __name__ == "__main__":
    sys.exit(main() or 0)
