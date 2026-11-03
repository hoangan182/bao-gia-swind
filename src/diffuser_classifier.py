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


class _Ctx:
    """Trạng thái 1 lần phân loại: biến văn bản, biến số, cờ."""

    def __init__(self, rules, combo_cfg, subtype_rules):
        self.rules = rules
        self.combo_cfg = combo_cfg or {}
        self.subtype_rules = subtype_rules
        self.text = {}
        self.flags = {}
        self.num = {}
        self._groups = {}

    # --- Dữ liệu ---
    def nums(self, name):
        w, h = self.num["w"], self.num["h"]
        if name == "max_wh":
            return max(w, h)
        if name == "min_wh":
            return min(w, h)
        return self.num[name]

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

    def words(self, items):
        out = []
        for it in ([items] if isinstance(items, str) else items):
            if it.startswith("@"):
                out.extend(self.group(it[1:]))
            else:
                out.append(it)
        return out

    def operand(self, v):
        if isinstance(v, (int, float)) and not isinstance(v, bool):
            return v
        if isinstance(v, list):  # [biến, '*', hệ số]
            return self.operand(v[0]) * float(v[2])
        return self.nums(v)

    # --- Điều kiện ---
    def ok(self, cond):
        if cond is True or cond is False:
            return cond
        if isinstance(cond, str):
            if cond.startswith("!"):
                return not self.flags.get(cond[1:], False)
            return bool(self.flags.get(cond, False))
        if "tat_ca" in cond:
            return all(self.ok(c) for c in cond["tat_ca"])
        if "mot_trong" in cond:
            return any(self.ok(c) for c in cond["mot_trong"])
        if "khong" in cond:
            return not self.ok(cond["khong"])
        if "tu_khoa" in cond:
            txt = self.text[cond["trong"]]
            skip = set(cond.get("tru", ()))
            return any(k in txt for k in self.words(cond["tu_khoa"]) if k not in skip)
        if "regex" in cond:
            pat = cond["regex"]
            if cond.get("regex_cau_hinh"):
                pat = self.combo_cfg.get(cond["regex_cau_hinh"], pat)
            return bool(re.search(pat, self.text[cond["trong"]], re.IGNORECASE if cond.get("ignorecase") else 0))
        if "so_sanh" in cond:
            a, op, b = cond["so_sanh"]
            a, b = self.operand(a), self.operand(b)
            return {">": a > b, ">=": a >= b, "<": a < b, "<=": a <= b, "==": a == b, "!=": a != b}[op]
        if "thuoc" in cond:
            var, vals = cond["thuoc"]
            return int(self.nums(var)) in vals
        raise ValueError(f"diffuser_rules: điều kiện không hiểu: {cond}")

    def pick_text(self, options):
        for opt in options:
            if "khi" not in opt or self.ok(opt["khi"]):
                return self.text[opt["lay"]] if "lay" in opt else opt["chuoi"]
        return ""


def _slots_by_edge(w, h):
    b_dim = min(w, h) if (w > 0 and h > 0) else max(w, h)
    return 1 if b_dim < 150.0 else (2 if b_dim < 200.0 else 3)


def _run_step(ctx, step, item, dims):
    if "co" in step:
        if "dat_true_khi" in step:
            if ctx.ok(step["dat_true_khi"]):
                ctx.flags[step["co"]] = True
        else:
            ctx.flags[step["co"]] = ctx.ok(step["dieu_kien"])
    elif "van_ban" in step:
        if "chon" in step:
            ctx.text[step["van_ban"]] = ctx.pick_text(step["chon"])
        else:
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
    """Tra bảng subtype_rules.json CUA_GIO (Tên + Ghi chú trước, rồi toàn bộ ngữ cảnh), mặc định BD."""
    from agent_01_boq_extractor import Agent01_BOQExtractor as A01
    return A01.get_subtype(ctx.subtype_rules, "CUA_GIO", ctx.text["raw_search"],
                           A01.get_subtype(ctx.subtype_rules, "CUA_GIO", ctx.text["full_search"], "BD"))


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
        primary_diff_search=(raw_name + " " + name + " " + str(item.get("model", ""))).lower(),
        note_boq_low=str(item.get("note_boq") or "").lower(),
        note_model_low=(str(item.get("note_boq") or "") + " " + str(item.get("model") or "")).lower(),
        raw_name_low=raw_name.lower(),
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

    rule = next(r for r in rules["thu_tu_uu_tien"] if ctx.ok(r["dieu_kien"]))
    for g in rule.get("gan", []):
        ctx.flags[g["co"]] = g["gia_tri"] if "gia_tri" in g else ctx.ok(g["dieu_kien"])
    if "chon_profile" in rule:
        profile = next(p["profile"] for p in rule["chon_profile"] if "khi" not in p or ctx.ok(p["khi"]))
        if profile == "@subtype_rules":
            profile = _subtype_lookup(ctx)
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

    w_neck = float(item.get("w_neck") or 0)
    h_neck = float(item.get("h_neck") or 0)
    if w_neck > 0 and h_neck > 0 and profile not in rules["co_explicit"]["bo_qua_profile"]:
        b1, b2 = int(w_neck), int(h_neck)

    f = ctx.flags
    return {
        "rule_id": rule["id"],
        "profile_type": profile,
        "model": model,
        "note": note,
        "b1": b1, "b2": b2,
        "a1": dims["a1"], "a2": dims["a2"],
        "w": ctx.num["w"], "h": ctx.num["h"], "d": ctx.num["d"],
        "w_pre_ktc": w_pre_ktc, "h_pre_ktc": h_pre_ktc,
        "has_obd": f["has_obd"], "has_mesh": f["has_mesh"], "has_filter": f["has_filter"],
        "is_double_layer": f["is_double_layer"], "is_black_2nd_layer": f["is_black_2nd_layer"],
        "is_removable": f["is_removable"], "removable_factor": removable_factor,
        "is_box_combo": f["is_box_combo"], "n_slots": ctx.num["n_slots"],
        "combined_search": combined_search,
    }
