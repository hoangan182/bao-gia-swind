"""
Bộ nhận diện CỬA GIÓ (diffuser_classifier) — chạy bảng rule `data/master_data/diffuser_rules.json`.

Tách từ chuỗi if/elif cũ trong `Agent01._resolve_diffuser_spec` (kế hoạch tách agent đọc BOQ, việc B, 2026-11-03).
Module chỉ PHÂN LOẠI: tính cờ nhận diện → áp KTC→KTM → chọn rule theo thứ tự ưu tiên → Model / B1,B2 / ghi chú
→ hệ số tháo lắp. Phần ghép combo Cửa + Van và hộp gió vẫn nằm ở Agent 01 (ghép giá, không phải phân loại).

Sửa rule: sửa bảng JSON (không thêm if/elif vào đây), ghi `nguon` / `ly_do`, thêm `vi_du_dung` / `vi_du_sai`
rồi chạy `tests/test_swind_diffuser_rules.py`. Vai trò: `.agents/roles/diffuser_classifier_role.md`.
"""
import os
import re
import json

from swind_utils import remove_vietnamese_accents, K
import typo_normalizer
from decision_trace import TEXT_SOURCE, SOURCES
from rule_dsl import RuleContext

RULES_PATH = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "master_data", "diffuser_rules.json")
_RULES_CACHE = {}

# Ký hiệu hậu tố Model -> cờ phụ kiện
SUFFIX_FLAGS = {"O": "has_obd", "F": "has_filter", "N": "has_mesh"}


def load_rules(path=None):
    path = path or RULES_PATH
    mtime = os.path.getmtime(path)
    cached = _RULES_CACHE.get(path)
    if cached and cached[0] == mtime:
        return cached[1]
    with open(path, "r", encoding="utf-8") as f:
        rules = json.load(f)
    _RULES_CACHE[path] = (mtime, rules)
    return rules


class _Ctx(RuleContext):
    """Trạng thái 1 lần phân loại cửa gió. Bộ điều kiện chung ở `rule_dsl.RuleContext` (Việc 4, 2026-11-24);
    phần riêng cửa: nhóm từ khóa đọc `combo_cfg`, `regex_cau_hinh`, `pick_text`, quy nguồn chữ Tên / Ghi chú / Title."""

    label = "diffuser_rules"

    def __init__(self, rules, combo_cfg, subtype_rules):
        super().__init__(rules)
        self.combo_cfg = combo_cfg or {}
        self.subtype_rules = subtype_rules
        # Bảng 'đã hiểu thế nào' (2026-11-24, chỉ ghi vết — không đổi kết quả): nguồn biến văn bản dẫn xuất (van_ban).
        self.text_src = {}
        self.derive = {}  # biến dẫn xuất -> (biến gốc, hàm biến đổi chữ) để tách phần Tên + Ghi chú

    def group(self, name):
        if name not in self._groups:
            spec = self.rules["nhom_tu_khoa"][name]
            if isinstance(spec, dict):
                base = self.combo_cfg.get(spec["tu_cau_hinh"], spec.get("mac_dinh", []))
                words = tuple(base) + tuple(spec.get("them", []))
            else:
                words = tuple(spec)
            self._groups[name] = words
        return self._groups[name]

    def regex_pattern(self, cond):
        pat = cond["regex"]
        if cond.get("regex_cau_hinh"):
            pat = self.combo_cfg.get(cond["regex_cau_hinh"], pat)
        return pat

    def pick_text(self, options):
        opt = self.pick_opt(options)
        if opt is None:
            return ""
        return self.text[opt["lay"]] if "lay" in opt else opt["chuoi"]

    # --- Nguồn chữ (bảng 'đã hiểu thế nào') ---
    def _add_hit(self, var, matcher):
        """Ghi biến văn bản đã khớp. Biến gộp (Tên + Ghi chú + Title) mà phần Tên + Ghi chú (raw_search) tự khớp
        → ghi raw_search (TEN), không ghi cả chuỗi gộp (TITLE). Chỉ đọc, không đổi kết quả so khớp."""
        own = self._own_text(var)
        self.hits.add("raw_search" if (own is not None and matcher(own)) else var)

    def _own_text(self, var):
        raw = self.text.get("raw_search")
        if raw is None:
            return None
        if var == "combined_search":
            return raw.lower()
        if var == "unaccent_search":
            return re.sub(r'\s+', ' ', remove_vietnamese_accents(raw.lower()).lower())
        if var in self.derive:
            base, fn = self.derive[var]
            own = self._own_text(base)
            return fn(own) if own is not None else None
        return None

    def var_sources(self, var):
        """Biến văn bản → tập nguồn (TEN / GHI_CHU / TITLE ...): biến dẫn xuất theo biến gốc, còn lại theo TEXT_SOURCE."""
        if var in self.text_src:
            return set(self.text_src[var])
        src = TEXT_SOURCE.get(var)
        return {src} if src else set()

    def sources(self, hits):
        out = set()
        for v in hits:
            out |= self.var_sources(v)
        return [s for s in SOURCES if s in out]


def _slots_by_edge(w, h):
    b_dim = min(w, h) if (w > 0 and h > 0) else max(w, h)
    return 1 if b_dim < 150.0 else (2 if b_dim < 200.0 else 3)


def _run_step(ctx, step, item, dims):
    if "co" in step:
        ctx.hits = set()
        if "dat_true_khi" in step:
            if ctx.ok(step["dat_true_khi"]):
                ctx.flags[step["co"]] = True
                ctx.flag_src[step["co"]] = ctx.flag_src.get(step["co"], set()) | ctx.hits
        else:
            val = ctx.ok(step["dieu_kien"])
            ctx.flags[step["co"]] = val
            ctx.flag_src[step["co"]] = set(ctx.hits) if val else set()
    elif "van_ban" in step:
        if "chon" in step:
            opt = ctx.pick_opt(step["chon"])
            ctx.text[step["van_ban"]] = "" if opt is None else (ctx.text[opt["lay"]] if "lay" in opt else opt["chuoi"])
            ctx.text_src[step["van_ban"]] = ctx.var_sources(opt["lay"]) if (opt and "lay" in opt) else set()
            if opt and "lay" in opt:
                ctx.derive[step["van_ban"]] = (opt["lay"], lambda t: t)
            else:
                ctx.derive.pop(step["van_ban"], None)
        else:
            ctx.text_src[step["van_ban"]] = ctx.var_sources(step["tu"])
            _rx, _fl = step["xoa_regex"], re.IGNORECASE if step.get("ignorecase") else 0
            ctx.derive[step["van_ban"]] = (step["tu"], lambda t, _rx=_rx, _fl=_fl: re.sub(_rx, "", t, flags=_fl))
            ctx.text[step["van_ban"]] = re.sub(step["xoa_regex"], "", ctx.text[step["tu"]],
                                               flags=re.IGNORECASE if step.get("ignorecase") else 0)
    elif step.get("tinh") == "dem_khe":
        if ctx.ok(step["khi"]):
            m = re.search(step["regex"], ctx.text[step["trong"]])
            if m:
                ctx.num["n_slots"] = int(next(g for g in m.groups() if g is not None))
            else:
                ctx.num["n_slots"] = _slots_by_edge(ctx.num["w"], ctx.num["h"])
    elif step.get("tinh") == "so_khe_theo_canh":
        if ctx.ok(step["khi"]):
            ctx.num["n_slots"] = _slots_by_edge(ctx.num["w"], ctx.num["h"])
    elif step.get("tinh") == "ap_dung_ktc":
        if ctx.ok(step["khi"]):
            _apply_ktc(ctx, step, item, dims)
    else:
        raise ValueError(f"diffuser_rules: bước không hiểu: {step}")


def _apply_ktc(ctx, step, item, dims):
    """Rule 1 KTC→KTM: cộng viền ra kích thước mặt, ghi lại vào item (giữ kích thước van combo theo cổ)."""
    w, h, d = ctx.num["w"], ctx.num["h"], ctx.num["d"]
    if item.get("combo_dampers") or item.get("combo_damper"):
        if not item.get("w_damper") and w > 0:
            item["w_damper"] = w
        if not item.get("h_damper") and h > 0:
            item["h_damper"] = h
        if not item.get("d_damper") and d > 0:
            item["d_damper"] = d
    offset = next(o["gia_tri"] for o in step["do_lech"] if "khi" not in o or ctx.ok(o["khi"]))
    if w > 0: w += offset
    if h > 0: h += offset
    if d > 0: d += offset
    item["w"], item["h"], item["d"] = w, h, d
    ctx.num.update(w=w, h=h, d=d)
    dims["a1"] = "Ø" if d > 0 else (int(w) if w > 0 else None)
    dims["a2"] = int(d) if d > 0 else (int(h) if h > 0 else None)
    item["is_ktc_applied"] = True


def _build_model(ctx, options):
    for opt in options:
        if "khi" in opt and not ctx.ok(opt["khi"]):
            continue
        if "co_dinh" in opt:
            return opt["co_dinh"]
        base = opt.get("goc")
        if "goc_chon" in opt:
            base = next(g["goc"] for g in opt["goc_chon"] if "khi" not in g or ctx.ok(g["khi"]))
        return base + "".join(f"+{s}" for s in opt.get("hau_to", []) if ctx.flags.get(SUFFIX_FLAGS[s]))
    raise ValueError("diffuser_rules: không có phương án Model nào khớp")


def _build_b(ctx, options):
    w, h, d = ctx.num["w"], ctx.num["h"], ctx.num["d"]
    for opt in options:
        if "khi" in opt and not ctx.ok(opt["khi"]):
            continue
        kind = opt["kieu"]
        if kind == "khong":
            return None, None
        if kind == "tron":
            return ("Ø", int(max(opt["toi_thieu"], d - opt["tru"]))) if d > 0 else (None, None)
        if not (w > 0 and h > 0):
            return None, None
        if kind == "giu":
            return int(w), int(h)
        (tw, th), (mw, mh) = opt["tru"], opt["toi_thieu"]
        return int(max(mw, w - tw)), int(max(mh, h - th))
    return None, None


def _build_note(ctx, parts):
    out = ""
    for p in parts:
        if isinstance(p, str):
            out += p
        elif "bien" in p:
            out += ctx.text[p["bien"]]
        elif "cat_khoang_trang" in p:
            out = out.strip()
        elif "chon" in p:
            out += ctx.pick_text(p["chon"])
        elif "mau" in p:
            if "khi" not in p or ctx.ok(p["khi"]):
                out += p["mau"].format(**ctx.num)
        elif ctx.ok(p["khi"]):
            out += p["chuoi"]
    return out


def _subtype_lookup(ctx):
    """Tra bảng subtype_rules.json CUA_GIO (Tên + Ghi chú trước, rồi toàn bộ ngữ cảnh), mặc định BD.
    Trả (profile, biến văn bản đã khớp — 'raw_search' / 'full_search' — hoặc None khi không khớp từ khóa nào → mặc định)."""
    from agent_01_boq_extractor import Agent01_BOQExtractor as A01
    hit_raw = A01.get_subtype(ctx.subtype_rules, "CUA_GIO", ctx.text["raw_search"], None)
    if hit_raw is not None:
        return hit_raw, "raw_search"
    hit_full = A01.get_subtype(ctx.subtype_rules, "CUA_GIO", ctx.text["full_search"], None)
    if hit_full is not None:
        return hit_full, "full_search"
    return "BD", None


def _nm(text, item):
    return typo_normalizer.normalize_for_match(text, "agent01", item.get("typo_events"))


def classify(item, subtype_rules, raw_name, name, raw_search, full_search, w, h, d, a1, a2, combo_cfg, include_box, rules=None):
    """
    Phân loại 1 dòng CUA_GIO. Ghi lại vào `item` như code cũ (w/h/d sau KTC, w_pre_ktc, is_ktc_applied, *_damper).
    Trả dict: rule_id, profile_type, model, note, b1, b2, a1, a2, w, h, d, cờ phụ kiện, removable_factor, n_slots...
    """
    rules = rules or load_rules()
    ctx = _Ctx(rules, combo_cfg, subtype_rules)
    combined_search = (raw_search + " " + full_search).lower()
    ctx.text.update(
        combined_search=combined_search,
        # Chuỗi so khớp qua bộ chuẩn hóa lỗi chính tả (typo_normalizer, phạm vi agent01) — BOQ không dấu (review 2026-11-03)
        primary_diff_search=_nm((raw_name + " " + name + " " + str(item.get("model", ""))).lower(), item),
        note_boq_low=_nm(str(item.get("note_boq") or "").lower(), item),
        note_model_low=_nm((str(item.get("note_boq") or "") + " " + str(item.get("model") or "")).lower(), item),
        raw_name_low=_nm(raw_name.lower(), item),
        # Title cha riêng (cờ title_ghi_khuech_tan — User chốt 2026-11-24)
        title_low=_nm(str(item.get("section") or "").lower(), item),
        raw_search=raw_search,
        full_search=full_search,
        raw_name=raw_name,
        unaccent_search=re.sub(r'\s+', ' ', remove_vietnamese_accents(combined_search).lower()),
    )
    ctx.flags.update(
        spec_note=(item.get("spec_priority", "name") == "note"),
        has_embedded_image=bool(item.get("has_embedded_image")),
        include_box=bool(include_box),
        neck_size_override=bool(item.get("neck_size_override")),
        is_ktc_applied=bool(item.get("is_ktc_applied")),
    )
    ctx.num.update(w=w, h=h, d=d, n_slots=0)
    w_pre_ktc = float(item.get("w_pre_ktc") or w or 0.0)
    h_pre_ktc = float(item.get("h_pre_ktc") or h or 0.0)
    item["w_pre_ktc"] = w_pre_ktc
    item["h_pre_ktc"] = h_pre_ktc
    dims = {"a1": a1, "a2": a2}

    for step in rules["buoc_nhan_dien"]:
        _run_step(ctx, step, item, dims)

    rule = None
    for r in rules["thu_tu_uu_tien"]:
        ctx.hits = set()
        if ctx.ok(r["dieu_kien"]):
            rule = r
            break
    if rule is None:
        raise StopIteration
    decided_by = set(ctx.hits)
    rule_id, is_default = rule["id"], False
    if rule.get("canh_bao_user"):
        item["rule_alert"] = {"id": rule["id"], "text": rule["canh_bao_user"]}
    for g in rule.get("gan", []):
        ctx.flags[g["co"]] = g["gia_tri"] if "gia_tri" in g else ctx.ok(g["dieu_kien"])
    if "chon_profile" in rule:
        profile = None
        for p in rule["chon_profile"]:
            ctx.hits = set()
            if "khi" not in p or ctx.ok(p["khi"]):
                profile = p["profile"]
                break
        if profile is None:
            raise StopIteration
        decided_by |= ctx.hits
        if profile == "@subtype_rules":
            profile, sub_var = _subtype_lookup(ctx)
            if sub_var is None:
                rule_id, is_default = rule["id"].split("_", 1)[0] + "-MAC-DINH", True
            else:
                decided_by.add(sub_var)
        out = rule["theo_profile"].get(profile) or rule["theo_profile"]["*"]
    else:
        profile, out = rule["profile"], rule
    for step in out.get("truoc", []):
        _run_step(ctx, step, item, dims)

    model = _build_model(ctx, out["model"])
    b1, b2 = _build_b(ctx, out["b"])
    note = _build_note(ctx, out["ghi_chu"])
    box_note = ctx.text["box_note"]

    # Tháo lắp / 2 khung: chỉ nhân PHẦN CỬA (Agent 06 không nhân OBD / LCCT / lọc)
    tl = rules["thao_lap"]
    removable_factor = 1.0
    if ctx.ok(tl["khi"]) and profile not in tl["bo_qua_profile"]:
        removable_factor = float(K(tl["hang_so"], tl["mac_dinh"]))
        if "tháo lắp" not in note:
            door_note = note[:-len(box_note)] if (box_note and note.endswith(box_note)) else note
            note = f"{door_note} (tháo lắp){box_note if door_note != note else ''}"

    # Louver tròn (chỉ ghi D): giá phần louver = 3 x Louver vuông DxD, phụ kiện giữ nguyên (User chốt 2026-11-11)
    lt = rules.get("louver_tron") or {}
    round_factor = 1.0
    d_num = float(ctx.num["d"] or 0)
    if lt and profile in lt.get("profile", []) and d_num > 0 and float(ctx.num["w"] or 0) in (0.0, d_num) and float(ctx.num["h"] or 0) in (0.0, d_num):
        round_factor = float(K(lt["hang_so"], lt["mac_dinh"]))
        ctx.num["w"] = ctx.num["h"] = d_num
        note = note.replace("Louver nan Z", f"Cửa Louver tròn D{int(d_num)} nan Z", 1) if "Louver nan Z" in note else f"Cửa Louver tròn D{int(d_num)} - {note}"
        # Cách tính giá (x3 phần louver) là thông tin NỘI BỘ: chỉ ghi ở BOM dự toán (Agent 06), không đưa vào
        # ghi chú BG gửi khách (User chốt 2026-11-12)

    w_neck = float(item.get("w_neck") or 0)
    h_neck = float(item.get("h_neck") or 0)
    if w_neck > 0 and h_neck > 0 and profile not in rules["co_explicit"]["bo_qua_profile"]:
        b1, b2 = int(w_neck), int(h_neck)

    # Giới hạn kích thước theo loại cửa (diffuser_rules.json -> gioi_han_kich_thuoc): vượt → vẫn báo, ghi chú + tô vàng BG + hỏi lại
    item["size_limit_flag"] = size_limit_flag(model, dims["a1"] or ctx.num["w"], dims["a2"] or ctx.num["h"], rules)

    nguon = ["MAC_DINH"] if is_default else (ctx.sources(decided_by) or ["MAC_DINH"])
    f = ctx.flags
    return {
        "rule_id": rule["id"],
        # Bảng 'đã hiểu thế nào': rule_id giữ nguyên id rule (test ví dụ JSON + vết pattern lab đang dùng);
        # rule_quyet_dinh = "CG-09-MAC-DINH" khi CG-09 tra bảng subtype mà không khớp từ khóa nào (mặc định BD)
        "rule_quyet_dinh": rule_id,
        "nguon": nguon,
        "mac_dinh": "MAC_DINH" in nguon,
        "profile_type": profile,
        "model": model,
        "note": note,
        "b1": b1, "b2": b2,
        "a1": dims["a1"], "a2": dims["a2"],
        "w": ctx.num["w"], "h": ctx.num["h"], "d": ctx.num["d"],
        "w_pre_ktc": w_pre_ktc, "h_pre_ktc": h_pre_ktc,
        "has_obd": f["has_obd"], "has_mesh": f["has_mesh"], "has_filter": f["has_filter"],
        "is_double_layer": f["is_double_layer"], "is_black_2nd_layer": f["is_black_2nd_layer"],
        "is_removable": f["is_removable"], "removable_factor": removable_factor, "round_factor": round_factor,
        "is_box_combo": f["is_box_combo"], "n_slots": ctx.num["n_slots"],
        "combined_search": combined_search,
    }


def size_limit_flag(model, w, h, rules=None):
    """CG-KT-xx: cửa vượt kích thước tối đa của loại (VD khuếch tán vuông SD tối đa 600x600) → chuỗi cảnh báo, không thì ''.
    User chốt 2026-11-13 (KL Swind 1 R21 'KTM 595x1195 + OBD' khuếch tán): vẫn báo giá theo BOQ, chỉ ghi chú + hỏi lại."""
    rules = rules or load_rules()
    m = str(model or "").upper().replace(" ", "")
    try:
        w, h = float(w or 0), float(h or 0)
    except (TypeError, ValueError):
        return ""
    for g in rules.get("gioi_han_kich_thuoc", []):
        if not m.startswith(tuple(g["model_bat_dau"])) or m.startswith(tuple(g.get("model_loai_tru_bat_dau", []))):
            continue
        lim = sorted(g["toi_da"])
        if w > 0 and h > 0 and (min(w, h) > lim[0] or max(w, h) > lim[1]):
            return g["canh_bao"].format(w=int(w), h=int(h))
    return ""


def box_combo_by_name(raw_name, rules=None):
    """`hop_gio_theo_ten`: Tên gốc có từ khóa hộp gió VÀ từ khóa cửa / miệng gió → combo cửa + hộp (dự phòng khi Agent 01
    chưa gắn is_box_combo). Runner + swind_item_inspector gọi (Task B, dọn sạch sau Việc 4, 2026-11-25)."""
    cfg = (rules or load_rules())["hop_gio_theo_ten"]
    rn = str(raw_name or "").lower()
    return any(k in rn for k in cfg["tu_khoa_hop"]) and any(k in rn for k in cfg["tu_khoa_cua"])


def name_note_conflict(raw_name_low, note_low, note_priority=False, rules=None):
    """`xung_dot_ten_ghi_chu`: Ghi chú / Spec ghi kiểu nan khác Cột Tên → id rule (runner in cảnh báo HỎI LẠI USER),
    không thì None. Chuỗi con thuần trên chữ thường như bộ dò cũ của runner (Task B, dọn sạch sau Việc 4, 2026-11-25)."""
    cfg = (rules or load_rules())["xung_dot_ten_ghi_chu"]
    rn, nb = str(raw_name_low or ""), str(note_low or "")
    if not nb or (note_priority and cfg.get("bo_qua_khi_uu_tien_ghi_chu")):
        return None
    for r in cfg["quy_tac"]:
        if (any(k in nb for k in r["ghi_chu_co"])
                and (not r.get("ten_co") or any(k in rn for k in r["ten_co"]))
                and not any(k in rn for k in r.get("ten_khong", ()))):
            return r["id"]
    return None
