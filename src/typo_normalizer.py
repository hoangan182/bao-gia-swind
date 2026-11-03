"""
Bộ chuẩn hóa LỖI CHÍNH TẢ BOQ (typo_normalizer) — chạy bảng rule `data/master_data/typo_rules.json`.

Dùng chung cho parser, Agent 01 và các bộ phân loại cửa / van / ống / phạm vi để mọi lỗi gõ được sửa ở MỘT chỗ.
Module chỉ tạo CHUỖI SO KHỚP: không đọc / ghi Excel, không ghi lại nội dung BOQ.

Phạm vi (scope) — xem `pham_vi` trong JSON: ten, title, full, combo, van, agent01.
Thiết kế: docs/superpowers/specs/2026-11-03-typo-normalizer-design.md. Vai trò: `.agents/roles/typo_normalizer_role.md`.
"""
import os
import re
import json
import unicodedata

from swind_utils import remove_vietnamese_accents

MASTER_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "master_data")
# SWIND_TYPO_RULES: đường dẫn thay thế (test) — mặc định data/master_data/typo_rules.json
RULES_PATH = os.environ.get("SWIND_TYPO_RULES") or os.path.join(MASTER_DIR, "typo_rules.json")
ALL_SCOPES = ("ten", "title", "full", "combo", "van", "agent01")
_RULES_CACHE = {}
_VOCAB_CACHE = {}


def load_rules(path=None):
    """{ 'TY-01': rule, ..., '_all': data } — cache theo mtime (sửa JSON có hiệu lực ngay)."""
    path = path or RULES_PATH
    mtime = os.path.getmtime(path)
    cached = _RULES_CACHE.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    rules = {r["id"].split("_", 1)[0]: r for r in data["quy_tac"]}
    rules["_all"] = data
    rules["_compiled_tu_dien"] = [(re.compile(e["mau"]), e["thay"], frozenset(e["pham_vi"]))
                                  for e in rules["TY-01"]["tu_dien"]]
    _RULES_CACHE[path] = (mtime, rules)
    return rules


def apply_dictionary(text, scope):
    """TY-01: chạy các mục từ điển theo thứ tự trong file, chỉ mục có `scope` trong pham_vi ('*' = mọi mục)."""
    for rx, rep, scopes in load_rules()["_compiled_tu_dien"]:
        if scope == "*" or scope in scopes:
            text = rx.sub(rep, text)
    return text


def _fold(text):
    return remove_vietnamese_accents(text).lower()


def _collect_strings(obj, key_rx, meta, out, key=None):
    if isinstance(obj, dict):
        for k, v in obj.items():
            _collect_strings(v, key_rx, meta, out, k)
    elif isinstance(obj, list):
        if key and key_rx.search(key) and obj and all(isinstance(x, str) for x in obj):
            out.update(unicodedata.normalize("NFC", x).strip().lower() for x in obj if not (meta & set(x)))
        else:
            for x in obj:
                _collect_strings(x, key_rx, meta, out, key)


def vocabulary_phrases():
    """TY-02: {cụm_bỏ_dấu: cụm_có_dấu} — cụm ≥ 2 chữ có dấu từ các file rule; trùng nhiều cụm → bỏ trừ khi có 'uu_tien'."""
    r = load_rules()["TY-02"]
    src = r["nguon_tu_vung"]
    paths = [os.path.join(MASTER_DIR, f) for f in src["files"]] + [RULES_PATH]  # RULES_PATH đọc lúc gọi (test vá được)
    key = tuple((p, os.path.getmtime(p)) for p in paths)
    if _VOCAB_CACHE.get("key") == key:
        return _VOCAB_CACHE["map"]
    phrases = set()
    key_rx, meta = re.compile(src["khoa_regex"]), set("\\()[]|?*+^$")
    for p in paths[:-1]:
        with open(p, "r", encoding="utf-8") as f:
            _collect_strings(json.load(f), key_rx, meta, phrases)
    phrases |= {unicodedata.normalize("NFC", x).lower() for x in r.get("them", [])}
    phrases -= {unicodedata.normalize("NFC", x).lower() for x in r.get("bo", [])}
    groups = {}
    for ph in phrases:
        if len(ph.split()) >= 2 and _fold(ph) != ph:
            groups.setdefault(_fold(ph), set()).add(ph)
    uu_tien = {k: unicodedata.normalize("NFC", v) for k, v in r.get("uu_tien", {}).items()}
    vocab = {f: next(iter(g)) for f, g in groups.items() if len(g) == 1}
    vocab.update(uu_tien)
    alts = sorted(vocab, key=len, reverse=True)
    rx = re.compile(r"(?<![a-z0-9])(?:" + "|".join(re.escape(a) for a in alts) + r")(?![a-z0-9])") if alts else None
    _VOCAB_CACHE.update(key=key, map=vocab, rx=rx)
    return vocab


def restore_accents(text):
    """TY-02: khôi phục dấu cụm từ vựng Swind trong chuỗi so khớp → (chuỗi, sự kiện KHOI_PHUC_DAU)."""
    if not text:
        return text, []
    vocab = vocabulary_phrases()
    rx = _VOCAB_CACHE["rx"]
    folded = _fold(text)
    if rx is None or len(folded) != len(text):
        return text, []
    giu_dau = set(load_rules()["TY-02"].get("giu_dau", []))
    chars, events = list(text), []
    for m in rx.finditer(folded):
        span, phrase = text[m.start():m.end()], vocab[m.group()]
        if span == phrase or len(phrase) != len(span):
            continue
        diff = [(o, p) for o, p in zip(span.split(" "), phrase.split(" ")) if o != p]
        # Chỉ thay chữ HOÀN TOÀN KHÔNG DẤU: chữ đã có dấu có thể là chữ đúng khác nghĩa
        # ('ống luồn' dây điện ≠ 'ống lượn', TONG HOP HVAC R715 — E2E 2026-11-03)
        if any(o in giu_dau or _fold(o) != o for o, _ in diff):
            continue
        chars[m.start():m.end()] = phrase
        events.append({"loai": "KHOI_PHUC_DAU", "goc": span, "sua": phrase, "rule": "TY-02"})
    return "".join(chars), events


_TOKEN_RX = re.compile(r"(?<![a-z0-9])[a-z][a-z0-9]{1,4}(?![a-z0-9])")


def _one_edit(tok, code):
    """Lỗi gõ mã được nhận: ĐẢO 2 chữ liền nhau (ODB→OBD, RND→NRD) hoặc LẶP THỪA 1 chữ (LCCCT→LCCT).
    Không nhận thay / thêm / bớt chữ tùy ý: quét input/ 2026-11-03 cho thấy đó là mã riêng của khách
    (EAG / PAG / SEG họ miệng gió, FSD van khói-lửa) chứ không phải lỗi gõ."""
    if tok == code:
        return False
    if len(tok) == len(code):
        diff = [i for i in range(len(tok)) if tok[i] != code[i]]
        return (len(diff) == 2 and diff[1] == diff[0] + 1
                and tok[diff[0]] == code[diff[1]] and tok[diff[1]] == code[diff[0]])
    if len(tok) == len(code) + 1:
        return any(tok[i] == tok[i - 1] and tok[:i] + tok[i + 1:] == code for i in range(1, len(tok)))
    return False


def _has_signal(words, folded_ctx):
    return any(re.search(r"(?<![a-z0-9])" + re.escape(_fold(w)) + r"(?![a-z0-9])", folded_ctx) for w in words)


def detect_code_typos(row_text, context_text):
    """TY-03/04: mã viết tắt nghi gõ sai trong CHÍNH dòng (Tên + Ghi chú + Model) → sự kiện DOAN / HOI_LAI."""
    R = load_rules()
    r3, r4 = R["TY-03"], R["TY-04"]
    codes, skip = r3["ma_chuan"], set(r3["loai_tru"])
    syllable = re.compile(r3["am_tiet"])
    # Lỗi đã có trong từ điển (mọi phạm vi) được sửa trước → không sinh sự kiện lại
    folded_row = _fold(apply_dictionary(str(row_text or "").lower(), "*"))
    folded_ctx = _fold(apply_dictionary(str(context_text or "").lower(), "*"))
    groups = set()
    if _has_signal(r4["tin_hieu_cua"], folded_ctx):
        groups.add("CUA_GIO")
    if _has_signal(r4["tin_hieu_van"], folded_ctx):
        groups.add("VAN_GIO")
    fire = _has_signal(r4["tin_hieu_chay"], folded_ctx) or bool(re.search(r4["regex_chay"], folded_ctx))
    motor = _has_signal(r4["tin_hieu_dong_co"], folded_ctx)
    events, seen = [], set()
    for tok in _TOKEN_RX.findall(folded_row):
        if tok in seen or tok in codes or tok in skip or syllable.match(tok):
            continue
        seen.add(tok)
        cands = sorted(c for c in codes if _one_edit(tok, c))
        if not cands:
            continue
        fit = [c for c in cands if groups & set(codes[c]["nhom"])]
        if len(fit) >= 2:
            # Tín hiệu chống cháy / động cơ chỉ để PHÂN BIỆT các mã van còn lại, không loại ứng viên duy nhất
            # (NRD / MD ghi EI là hợp lệ — bọc KSH; LUXQV R29 'Van gió một chiều RND ... chống cháy EI60')
            fit = [c for c in fit if "chay" not in codes[c]
                   or (codes[c]["chay"] == fire and codes[c]["dong_co"] == motor)]
        if len(fit) == 1:
            events.append({"loai": "DOAN", "goc": tok, "sua": fit[0], "ung_vien": cands, "rule": "TY-04"})
        else:
            events.append({"loai": "HOI_LAI", "goc": tok, "sua": None, "ung_vien": cands, "rule": "TY-04"})
    return events


def apply_guesses(text, events):
    """Áp các sự kiện DOAN vào chuỗi so khớp (thay nguyên chữ, không phân biệt hoa thường)."""
    for e in events or ():
        if e.get("loai") == "DOAN" and e.get("sua"):
            text = re.sub(r"(?<![a-z0-9])" + re.escape(e["goc"]) + r"(?![a-z0-9])", e["sua"], text, flags=re.IGNORECASE)
    return text


def normalize_for_match(text, scope, events=None):
    """Chuỗi CHỈ dùng để so khớp phân loại (không ghi lại BOQ): TY-01 từ điển → TY-02 khôi phục dấu → TY-04 mã đã đoán."""
    text = apply_dictionary(text, scope)
    if scope in load_rules()["TY-02"]["pham_vi"]:
        text = restore_accents(text)[0]
    return apply_guesses(text, events)


# ---------------------------------------------------------------- Báo cáo (Kiểm soát cuối / Sheet BG)

def _flagged(events):
    return [e for e in events or () if e.get("loai") in ("DOAN", "HOI_LAI")]


def _short(e):
    if e["loai"] == "DOAN":
        return f"{e['goc'].upper()}→{e['sua'].upper()}"
    return f"{e['goc'].upper()}? ({' / '.join(c.upper() for c in e['ung_vien'])})"


def bg_flag(events):
    """Chữ đánh dấu cột Ghi chú Sheet BG (User chốt 2026-11-03); khôi phục dấu / từ điển → None."""
    parts = []
    for e in _flagged(events):
        if e["loai"] == "DOAN":
            parts.append(f"⚠️ ĐÃ HIỂU: {e['goc'].upper()} = {e['sua'].upper()} — xin xác nhận")
        else:
            parts.append(f"⚠️ CHƯA RÕ: {e['goc'].upper()} (có thể: {' / '.join(c.upper() for c in e['ung_vien'])})")
    return "; ".join(parts) or None


def gate_lines(all_items, limit=10):
    """Dòng cho [KIỂM SOÁT CUỐI]: đã đoán (xác nhận) và không đoán được (hỏi lại) — chỉ dòng có KL > 0."""
    guessed, asks, seen = [], [], set()
    for it in all_items or ():
        evs = _flagged(it.get("typo_events"))
        key = (it.get("source_sheet"), it.get("source_row"))
        if not evs or float(it.get("qty") or 0) <= 0 or key in seen:
            continue
        seen.add(key)
        desc = f"R{it.get('source_row')} '{it.get('raw_name')}': " + ", ".join(_short(e) for e in evs)
        (asks if any(e["loai"] == "HOI_LAI" for e in evs) else guessed).append(desc)
    out = []
    if guessed:
        out.append(f"[ĐÃ ĐOÁN — XÁC NHẬN] {len(guessed)} dòng hệ thống tự hiểu lỗi gõ mã (tô vàng trên Sheet BG): " + "; ".join(guessed[:limit]))
    if asks:
        out.append(f"[HỎI LẠI USER] {len(asks)} dòng có mã nghi gõ sai, không đoán được (đang đọc nguyên chữ, tô vàng trên Sheet BG): " + "; ".join(asks[:limit]))
    return out


# ---------------------------------------------------------------- Học lỗi mới (Agent 02 duyệt)

def add_dictionary_entry(goc, sua, nguon, pham_vi=None):
    """Thêm 1 lỗi đã duyệt vào cuối TY-01 (mọi phạm vi mặc định). Đã có cùng mẫu → False, không ghi."""
    path = RULES_PATH
    mau = r"\b" + re.escape(goc.strip().lower()) + r"\b"
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    tu_dien = next(r for r in data["quy_tac"] if r["id"].startswith("TY-01"))["tu_dien"]
    if any(e["mau"] == mau for e in tu_dien):
        return False
    tu_dien.append({"mau": mau, "thay": sua.strip().lower(), "pham_vi": list(pham_vi or ALL_SCOPES), "nguon": nguon})
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    _RULES_CACHE.pop(path, None)
    _VOCAB_CACHE.clear()
    return True


def add_exclusion(goc, nguon):
    """Đoán bị User từ chối → thêm chữ vào TY-03.loai_tru (không bao giờ nghi lại). Đã có → False."""
    path = RULES_PATH
    tok = goc.strip().lower()
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    r3 = next(r for r in data["quy_tac"] if r["id"].startswith("TY-03"))
    if tok in r3["loai_tru"]:
        return False
    r3["loai_tru"].append(tok)
    r3.setdefault("loai_tru_nguon", {})[tok] = nguon
    with open(path, "w", encoding="utf-8") as f:
        f.write(json.dumps(data, ensure_ascii=False, indent=1) + "\n")
    _RULES_CACHE.pop(path, None)
    return True
