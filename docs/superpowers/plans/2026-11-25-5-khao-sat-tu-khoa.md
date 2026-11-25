# Khảo sát từ khóa còn lại sau Việc 4 — NHẬN DIỆN vs HIỂN THỊ (Task 2, chỉ đọc)

> Ngày 2026-11-25. Nguồn đếm: `tests/test_swind_keyword_guard.count_file` (token STRING + FSTRING_MIDDLE, bỏ docstring), chạy trên cây làm việc hiện tại — tổng 191, khớp baseline từng file.
> Phân loại: **NHẬN DIỆN** (quyết định loại hàng / báo hay không / kế thừa Title / kích hoạt hỏi lại / thuộc tính đổi giá), **HIỂN THỊ** (ghi chú BOM / BG, nhãn, console, help CLI), **LẪN** (một literal dùng cho cả hai), **KHÓA** (tên biến / khóa dict / khóa hằng số giá / tên cờ CLI có chứa từ khóa — không phải từ khóa nhận diện; bánh cóc đếm nhầm).
> "Fallback" = giá trị mặc định trong `cfg.get(key, <literal>)` mà key ĐÃ có trong JSON → code chết, không ảnh hưởng hành vi khi JSON đủ.

## 1. Tổng hợp theo file

| File | Đếm | NHẬN DIỆN | HIỂN THỊ | LẪN | KHÓA | Ghi chú |
|---|---:|---:|---:|---:|---:|---|
| `swind_master_runner.py` | 68 | 24 | 41 | 0 | 3 | 14/24 là bộ dò xung đột Tên–Ghi chú |
| `agent_04_bom_duct.py` | 31 | 1 | 20 | 1 | 9 | logic Task 6 chủ yếu dùng chữ KHÔNG nằm trong từ vựng bánh cóc |
| `agent_06_bom_diffuser.py` | 22 | 0 | 21 | 0 | 1 | toàn bộ là tên linh kiện BOM |
| `swind_boq_parser.py` | 17 | 16 | 0 | 0 | 1 | 5/16 là fallback chết (key đã có trong `subtype_rules.json`) |
| `swind_pricing.py` | 13 | 0 | 6 | 0 | 7 | tên động cơ + khóa `obd.*` / `lcct` |
| `agent_00b_input_normalizer.py` | 11 | 10 | 1 | 0 | 0 | NHẬN DIỆN chỉ để in cảnh báo cấu trúc, không quyết định báo giá |
| `agent_01_boq_extractor.py` | 10 | 0 | 2 | 0 | 8 | khóa `has_obd` / `is_fire_canvas` / `lcct_per_m2` |
| `agent_10_old_quote_carrier.py` | 4 | 0 | 4 | 0 | 0 | nhãn nhóm `FAMILY_LABEL` |
| `agent_01b_image_boq_reader.py` | 3 | 3 | 0 | 0 | 0 | sửa lỗi OCR + regex nhận dòng ảnh (luồng phụ) |
| `agent_03_input_auditor.py` | 3 | 1 | 2 | 0 | 0 | `chặn lửa` → cảnh báo PCCC (chỉ cảnh báo) |
| `agent_05_bom_damper.py` | 3 | 0 | 3 | 0 | 0 | |
| `swind_universal_extractor.py` | 3 | 0 | 3 | 0 | 0 | nhãn phụ kiện + ca test `__main__` |
| `agent_08_qa_checker.py` | 1 | 0 | 0 | 0 | 1 | |
| `swind_excel_builder.py` | 1 | 1 | 0 | 0 | 0 | regex bố cục Sheet BG (dòng con / vật tư phụ) — không phải loại hàng |
| `swind_utils.py` | 1 | 1 | 0 | 0 | 0 | regex mã Model trong Reader core (dò cột Model) |
| **Tổng** | **191** | **57** | **103** | **1** | **30** | |

Ngoài số đếm, các mục review có NHẬN DIỆN bằng chữ **không thuộc từ vựng bánh cóc** (0 lần đếm): `fit_kw` (runner `fire_duct_section_rows`), danh sách loại trừ only-cửa/van (runner ~1307), `LINED_DUCT_RX` (thực ra ở `agent_04_bom_duct.py:14`), `FILTER_PREFIXES` / `FINE_FILTER_RX` (category_classifier), `is_fire` canvas + `is_silencer_fitting` + regex phụ kiện Title (agent_04).

## 2. Bảng chi tiết

### 2.1 `swind_master_runner.py`

| Dòng | Chuỗi / nhóm | Loại | Đích đề xuất (JSON + hàm đọc) | Rủi ro / cách hành vi có thể đổi | Kiểm bắt |
|---|---|---|---|---|---|
| 368-371 | `is_box_combo` fallback: `kèm hộp gió/kèm hộp/kèm box/có hộp gió/gắn hộp gió` ∧ `cửa gió/miệng gió/cửa cấp/miệng cấp/cửa hồi/miệng hồi` (2 đếm) | NHẬN DIỆN (giá: tách giá đối tác phần hộp) | `diffuser_rules.json` cờ mới `is_box_combo_raw_name` (điều kiện `tat_ca` 2 `tu_khoa` trên `raw_name`), hàm `diffuser_classifier.box_combo_by_name(raw_name)`; **sửa cả bản sao `swind_item_inspector.py:446-449`** | THẤP — chỉ chạy khi `spec/item.is_box_combo` falsy và có `ref_price`. Đổi nếu DSL chuẩn hóa chữ (typo/không dấu) khác `.lower()` thuần, hoặc quên inspector → inspector lệch runner | line-diff (dòng có giá đối tác + "kèm hộp"); self-test inspector |
| 546 | `"tiêu âm trong" not in raw_name` → `include_casing` (1) | NHẬN DIỆN (thuộc tính giá TIEU_AM) | `duct_rules.json` (bổ sung `_extra` "OG-25 tiêu âm trong — không vỏ"), `duct_classifier.is_lined_inner(raw_name)` | TRUNG BÌNH — KHÔNG được thay bằng `LINED_DUCT_RX` (regex đó khớp cả không dấu `tieu am trong`, `+`, `có` → đổi giá các dòng không dấu). Giữ substring y hệt | line-diff chế độ duct |
| 1187-1188 (+`fit_kw` 1170) | `startswith("ống gió")`, `fit_kw` (cút/côn/chân rẽ/chạc/tê/z chuyển/hộp/…/`co `) (2) | NHẬN DIỆN (phạm vi cờ `--duct-straight-only`) | `duct_rules.json` `_extra` "OG-26 ống thẳng vs phụ kiện (cờ straight-only)": `tien_to_ong`, `tu_khoa_phu_kien`; `duct_classifier.is_straight_duct_title(name)` | THẤP — chỉ khi cờ `--fire-duct-only --duct-straight-only` (1 dự án). Lưu ý `"co "` có dấu cách cuối, `"tê"` substring (khớp cả `"tên"`) — phải chép nguyên | line-diff không bắt (cờ không chạy trong E2E) → test đơn vị với `01. Bang thong ke khoi luong` |
| 1208-1210 | lọc `scope_kws` bỏ `"ống gió"` khi không `--include-duct`, bỏ `"nối mềm","canvas"` khi không `--include-canvas` (2) | NHẬN DIỆN (phạm vi Coverage Audit) | `scope_rules.json` PV-11: `tu_khoa_pham_vi_theo_co: {"include_duct": ["ống gió"], "include_canvas": ["nối mềm","canvas"]}`; `scope_filter.coverage_lists(include_duct=, include_canvas=)` | THẤP — chỉ đổi danh sách cảnh báo sót dòng. Đổi nếu thứ tự tuple khác (không ảnh hưởng `any`) hoặc lọc nhầm phần tử trùng chuỗi | console `[CẢNH BÁO SÓT DÒNG]` / `skipped_in_scope` trước/sau; E2E bất biến |
| 1242 | `is_main_cv`: `louver/luover/louvre/cửa chớp/cửa gió/miệng gió/van ` (3) | NHẬN DIỆN (quyết định LCCT thiếu KT bị bỏ lặng lẽ hay THÔNG BÁO USER) | `scope_rules.json` PV-11 `tu_khoa_hang_chinh_kem_lcct`; `scope_filter.is_main_cv_name(nm_l)` | THẤP — ảnh hưởng danh sách `⚠️ [THÔNG BÁO USER]` dòng thiếu KT, không đổi giá | console Kiểm soát cuối (THÔNG BÁO USER) trên KL TB+VT CT3 |
| ~1307 | only-cửa/van loại trừ: `ống chờ/ống lồng/ống nối mềm/mềm ei/khớp nối mềm/sleeve/flexible` (0 đếm) | NHẬN DIỆN (phạm vi Coverage Audit khi `--only-cua-van`) | `scope_rules.json` PV-11 `tu_khoa_loai_tru_chi_cua_van`; đọc qua `coverage_lists()` | THẤP — chỉ khi `--only-cua-van` | console sót dòng với `--only-cua-van` (không có trong E2E → test đơn vị) |
| 1485 | dùng `LINED_DUCT_RX` (định nghĩa `agent_04_bom_duct.py:14`) để đổi TIEU_AM→ONG_GIO khi `--lined-duct-as-duct` (0 đếm ở runner) | NHẬN DIỆN (đổi loại hàng theo cờ) | `duct_rules.json` OG-04 (đã là rule ống kèm tiêu âm trong) thêm `regex_ong_kem_tieu_am_trong`; `duct_classifier.LINED_DUCT_RX` (compile 1 lần), agent_04 import lại | TRUNG BÌNH — regex dùng ở 2 chỗ: runner (nhận diện) + agent_04:206-207 (xóa cụm khỏi tên trước tính giá). Escape JSON sai → đổi giá. Cờ chỉ 1 dự án | line-diff `--runner-args="--include-duct --lined-duct-as-duct"` trên `Ống thông gió` |
| 2043-2061 | bộ dò xung đột Tên–Ghi chú cửa gió (sọt trứng / nan z / louver / bầu dục / khuếch tán…) + van (`van chặn lửa`, `mfd`, `smd`, `bọc chống cháy`, `van fd`…) (14) | NHẬN DIỆN (kích hoạt `⚠️ PHÁT HIỆN GHI CHÚ / SPEC KHÁC BIỆT — BẮT BUỘC HỎI LẠI`) | Cửa: `diffuser_rules.json` mục mới `xung_dot_ten_ghi_chu` (3 rule có thứ tự: sọt trứng / nan Z / bầu dục, mỗi rule `ghi_chu_co`, `ten_co`, `ten_khong`); hàm `diffuser_classifier.name_note_conflict(rn_l, nb_l)` → mã rule hoặc None. Van: `damper_rules.json` (rule `VG-XD` theo `sub_s`), `damper_classifier.name_note_conflict(sub_s, rn_l, nb_l)`. Runner giữ phần định dạng câu (HIỂN THỊ) | TRUNG BÌNH — thứ tự `if/elif` quyết định 1 cảnh báo / dòng; có chữ gõ sai cố ý `sọt trưng`, mã ngắn substring `mag/sag/rag/fag/eag/oag` (khớp trong chữ khác). DSL phải dùng substring thuần (không `khop_bien`, không chuẩn hóa typo). Không ảnh hưởng giá → **line-diff không bắt** | so danh sách `ask_alerts` console trước/sau (3 file có cảnh báo) + test golden từng nhánh |
| 2026-2034 | hãng ĐC `kepler/klb/viweco/honeywell/siemens` (0 đếm) | NHẬN DIỆN (thông tin, không hỏi — AGENTS 3 ngoại lệ) | có thể để nguyên (không phải loại hàng) | — | — |
| 532, 560, 2163 | `"is_fire_canvas"`, `"has_obd"`, tên cờ `"--include-canvas"` (3) | KHÓA | giữ | — | — |
| 590, 618, 636×2 | `kèm cửa gió - `, `Hộp cửa gió - `, `Box cửa gió - `, note box | HIỂN THỊ (tên BOM) | giữ | — | — |
| 1565-1631, 1698, 1837-1937, 2288 | thông báo console `--duct-only`, ống gió mặc định không báo, canvas, MPRD, EI… (19) | HIỂN THỊ | giữ | — | — |
| 2148-2173 | `help=` argparse (17 + tên cờ 1) | HIỂN THỊ | giữ | — | — |
| 356-361 | `"VÁCH NGĂN / HỘP TIÊU ÂM"`, `"CỬA GIÓ"` (chữ HOA — hiện 0 đếm, sẽ đếm khi Task 7 hạ chữ thường) | HIỂN THỊ | giữ | — | — |

Tổng runner: NHẬN DIỆN 24 (370×2, 546, 1187-88×2, 1208-10×2, 1242×3, 2043-61×14); KHÓA 3 (532 `is_fire_canvas`, 560 `has_obd`, 2163 tên cờ `--include-canvas`); HIỂN THỊ 41 (box BOM 4, console 18, help 18, 2288).

### 2.2 `swind_boq_parser.py`

| Dòng | Chuỗi / nhóm | Loại | Đích đề xuất | Rủi ro | Kiểm bắt |
|---|---|---|---|---|---|
| 118-119 | `cv_kws` fallback `louver…miệng gió, cửa gió…prd` (3) + **phần cộng cứng `+ ("cửa chớp","chớp nhôm")`** + `cv_rx` fallback | NHẬN DIỆN (dòng cửa/van KL trống vẫn giữ / không thành Title) | key đã có ở `subtype_rules.json COMBO_AND_DETECTION_RULES.missing_qty_cv_keywords` (danh sách JSON ≠ fallback: JSON có thêm `miệng hút…ống gió, cút, côn, chân rẽ, tê, hộp gió`). Việc: xóa fallback (dùng `cfg[key]`), **chuyển `cửa chớp`, `chớp nhôm` vào JSON** | THẤP — fallback chết. Phần cộng cứng: nếu nối vào JSON đúng 2 chữ thì không đổi. Nếu tiện tay "đồng bộ" fallback ↔ JSON sẽ đổi (KHÔNG làm) | line-diff 0; pattern lab 0 |
| 233 | `is_lcct_name`: `lưới chắn côn trùng / lcct / insect screen` (2) | NHẬN DIỆN (Title "…kích thước:" ĐVT m2 có KL → báo LCCT theo m²) | `scope_rules.json` PV-11 key RIÊNG `tu_khoa_lcct_theo_m2` (giữ cả `insect screen`); `scope_filter.is_lcct_m2_title(name_lower)`. **Không** dùng lại `tu_khoa_luoi_chan_con_trung` (chỉ có `lcct`, `lưới chắn côn trùng`) và không thêm `insect screen` vào list đó (đổi `is_skip_rule` Coverage Audit runner:1243) | THẤP nếu key riêng; TRUNG BÌNH nếu gộp | line-diff (TONG_HOP_KHOI_LUONG_DHKK R429/R572); console THÔNG BÁO USER |
| 261 | `is_parent_title_kw`: `cửa, miệng, van, ống, louver, luover, louvre, grille, diffuser, damper, khớp nối, tiêu âm` (2) | NHẬN DIỆN (dòng không KL thành Title → kế thừa xuống mọi dòng con, quy tắc 1a) | `title_row_rules.json` mục mới `TR-05 tu_khoa_dong_tieu_de` (substring, `trong: nl_chk` = Tên + Spec + Model); `title_row_resolver.is_title_kw_row(nl_chk)` | TRUNG BÌNH — 1 sai lệch đổi Title của cả khối dòng con. Hàm mới phải so substring trên đúng chuỗi `.lower()` cũ, không qua `typo_normalizer` / bỏ dấu / ranh giới từ (`van` đang khớp cả `vận`… cố ý giữ). Điều kiện `not has_cv_dim` giữ ở parser | line-diff 0 cả 2 chế độ + pattern lab 0 + `test_swind_title_row_rules.py` |
| 523 | `single_dim_damper_regex` fallback (1) | NHẬN DIỆN (fallback chết; JSON có, JSON thiếu `msfd`) | xóa fallback | THẤP | line-diff |
| 597 | `is_makeup_air_z` loại trừ `fag…sdg, obd, nan thẳng, bầu dục` (2) | NHẬN DIỆN (cửa bù khí mặc định nan Z → cộng viền KTC) | `diffuser_rules.json` cờ `is_makeup_air_z` (đã có logic tương tự ở Agent01 Rule 1?) — đọc qua `diffuser_classifier.flag("is_makeup_air_z", text)` | TRUNG BÌNH — đổi kích thước → đổi giá; trùng ý với cờ trong diffuser_rules dễ bị "gộp cho gọn" → lệch | line-diff |
| 606-607 | `is_ktc_diffuser`: `khuếch tán, scd, sad, diffuser`, trừ `cửa thổi khuếch tán` (2) | NHẬN DIỆN (viền cổ +150 vs +50) | `diffuser_rules.json` (cùng nhóm `dong_ghi_khuech_tan`/KTC) — cờ `is_ktc_diffuser_parser` chép nguyên | TRUNG BÌNH — **không** thay bằng cờ `dong_ghi_khuech_tan` (4a-0b, khác danh sách: có `khuyếch tán`, `N hướng`, `SD`…) → đổi KT | line-diff |
| 622 | `combo_diffuser_regex` fallback (1) | NHẬN DIỆN (fallback chết) | xóa fallback | THẤP | line-diff |
| 644 | 1a chiều ngược: Tên bắt đầu `cửa|miệng|louver|luover|louvre|grille|diffuser` (1) | NHẬN DIỆN (không ghép van từ Title) | `subtype_rules.json COMBO_AND_DETECTION_RULES.combo_own_diffuser_prefix_regex` (cạnh `combo_diffuser_regex`) hoặc `damper_rules.json` VG-13 | THẤP-TRUNG BÌNH — regex đơn giản; nguồn AC.OG.CGVG R67-68 | line-diff (AC.OG.CGVG) |
| 880 | dò bảng phụ (side table): `van|mfd|…|obd|cửa|miệng|louver|ống|cút|côn|tê` (2) | NHẬN DIỆN bố cục (Reader), không phải loại hàng | để nguyên trong Task 4 (AGENTS mục 7: sửa đọc cấu trúc → `--build --force` + E2E toàn bộ). Nếu chuyển: `swind_utils` Reader core | CAO so với lợi ích — đổi bố cục cả file | E2E toàn bộ |
| 844 | `"lcct_per_m2"` | KHÓA | giữ | — | — |

### 2.3 `agent_04_bom_duct.py`

| Dòng | Chuỗi | Loại | Đích / ghi chú | Rủi ro |
|---|---|---|---|---|
| 414-418 | `is_silencer_fitting`: danh sách phụ kiện (cút/côn/tê/chạc/chân rẽ/gót giày/zét/ống lượn/bịt đầu, có cả không dấu) + `"phụ kiện tiêu âm"` (1 đếm) | NHẬN DIỆN (giá ×1.3 PK-TA-VUONG) | `duct_rules.json` `_extra` "OG-27 phụ kiện tiêu âm" `tu_khoa_ten`, `tu_khoa_toan_dong`; `duct_classifier.is_silencer_fitting(raw_name, full_text)`; dòng 422/438 (cút vs côn trong tiêu âm) cùng rule | TRUNG BÌNH — đổi giá tiêu âm; danh sách có dấu cách cố ý (`"cut "`, `"co "`, `"te "`) |
| 302-306 | canvas `is_fire`: `chống cháy, chịu nhiệt, silicone, vải thủy tinh, ei, đầu quạt…quạt, fan, hút khói, tăng áp` trừ `loại thường`/`fcu` (0 đếm) | NHẬN DIỆN (giá canvas chống cháy) | `duct_rules.json` rule RIÊNG "OG-24B canvas giá chống cháy" — **khác OG-24** (`chống cháy, chịu nhiệt, tahk, hút khói`). Runner truyền `is_fire_resistant=spec.is_fire_canvas` (OG-24) nhưng `calculate_canvas_bom` **bỏ qua** tham số này (rơi vào `**kwargs`), giá lấy theo danh sách agent_04 | CAO nếu "hợp nhất" với OG-24 (đổi giá canvas có `quạt/fan/tăng áp/ei` hoặc `tahk`). Canvas mặc định không báo → chỉ chế độ `--include-canvas` |
| 320-325 | `không bích / 2 đầu bích…` (0 đếm) | NHẬN DIỆN (số đầu bích) | `duct_rules.json` cùng OG-24B (`dau_bich`) | THẤP |
| 201-204 | regex phụ kiện trong Title khi Tên chỉ kích thước (0 đếm) | NHẬN DIỆN (Title→dòng) | `duct_rules.json` `_extra` hoặc `title_row_rules.json`; chỉ khi Task 6 còn thời gian | TRUNG BÌNH |
| 1120 | default `raw_name or "Hộp tiêu âm"` khi `item is None` | LẪN (chuỗi giả làm đầu vào phân loại; runner luôn truyền `item`) | giữ | — |
| 619, 1003 | `mesh_price(..., "lcct")` | KHÓA | giữ | — |
| 308-318 | `K("ong.canvas.*")` (7) | KHÓA (khóa pricing_constants) | giữ | — |
| 295-296, 346, 465-466, 488, 622, 869, 998, 1006, 1148-1180 | spec_note / trace / tên linh kiện BOM (20) | HIỂN THỊ | giữ | — |

### 2.4 Các file khác

| File:dòng | Chuỗi | Loại | Đề xuất |
|---|---|---|---|
| `agent_06_bom_diffuser.py` 82, 187-278, 331, 409, 451-474, 531-549 (21) | tên linh kiện / ghi chú BOM (sọt trứng, khuếch tán, tháo lắp, bầu dục, ke góc cửa gió) | HIỂN THỊ | giữ; 111 `mesh_price(…,"lcct")` KHÓA |
| `swind_pricing.py` 82-89 (5) | tên động cơ `Động cơ chặn lửa ON/OFF…` | HIỂN THỊ | giữ |
| `swind_pricing.py` 116-120 (6), 139 (1) | `obd.*`, `"lcct"` | KHÓA | giữ; 148 thông báo lỗi = HIỂN THỊ |
| `agent_00b_input_normalizer.py` 45-47 (5), 52 (2), 268 (3) | `SECTION_KEYWORDS`, `DUCT_ITEM_PATTERN`, `is_grille_or_damper` | NHẬN DIỆN-cảnh báo (đếm "dòng giống ống" để in issue Agent 00B; không quyết định báo giá) | Ngoài phạm vi Task 3-6. Nếu làm: `scope_rules.json` PV-13 + `scope_filter`; rủi ro THẤP (chỉ đổi cảnh báo), lợi ích thấp. 324 = HIỂN THỊ |
| `agent_01_boq_extractor.py` 246, 395, 595, 638 / 504, 609, 646 / 657 (8) | `has_obd`, `is_fire_canvas`, `lcct_per_m2` | KHÓA | giữ |
| `agent_01_boq_extractor.py` 489, 616 (2) | ghi chú LCCT / `Bọc chống cháy ống gió chuẩn EI` | HIỂN THỊ | giữ (điều kiện `"chống cháy ei" in raw_search` ở 616 là NHẬN DIỆN nhánh OTHER, 0 đếm, ảnh hưởng ghi chú) |
| `agent_10_old_quote_carrier.py` 46-47 (4) | `FAMILY_LABEL` | HIỂN THỊ | giữ |
| `agent_01b_image_boq_reader.py` 127, 299 (3) | sửa lỗi OCR `lưới chăn→lưới chắn`; regex dòng hàng từ ảnh | NHẬN DIỆN (luồng phụ đọc ảnh) | giữ, EXEMPT hợp lý hơn (đọc OCR, không phải phân loại) |
| `agent_03_input_auditor.py` 176 (1) | `"chặn lửa"` → kiểm EI | NHẬN DIỆN-cảnh báo | giữ (hoặc dùng `damper_classifier` khi tiện); 141, 182 HIỂN THỊ |
| `agent_05_bom_damper.py` 396, 401, 468 | tên linh kiện | HIỂN THỊ | giữ |
| `swind_universal_extractor.py` 138, 346-347 | nhãn phụ kiện + ca test | HIỂN THỊ | giữ |
| `swind_excel_builder.py` 690 | regex `phụ kiện ống gió` để nhận dòng con khi dựng BG | NHẬN DIỆN bố cục BG | giữ |
| `swind_utils.py` 583 | regex mã Model (`obd…`) dò cột Model trong Reader | NHẬN DIỆN bố cục | giữ |
| `agent_08_qa_checker.py` 63 | `has_obd` | KHÓA | giữ |

### 2.5 `src/category_classifier.py` (EXEMPT — không đếm)

| Dòng | Chuỗi | Loại | Đích | Rủi ro |
|---|---|---|---|---|
| 36 | `FILTER_PREFIXES` (`lọc bụi, lọc thô, lọc sơ cấp, lọc g4, phin lọc, lưới lọc, tấm lọc, bộ lọc, khung lọc, filter g4, g4 filter, pre filter, pre-filter`) | NHẬN DIỆN (LH-05 → CUA_GIO / FILTER_G4) | `category_rules.json` `nhom_tu_khoa.loc_tho_tien_to` | THẤP |
| 37 | `FINE_FILTER_RX` (`f5-9, m5-6, e10-12, h10-14, hepa, ulpa` có `\b`; `than hoạt tính, tĩnh điện, túi, carbon, bag` KHÔNG `\b`) | NHẬN DIỆN | `category_rules.json` key `regex_loc_tinh` | THẤP — giữ chính xác regex (escape `\\b` trong JSON); `bag`/`túi` substring cố ý |
| 40-44 | `is_standalone_coarse_filter`: bỏ gạch đầu dòng + động từ `cung cấp/gia công/sản xuất/lắp đặt` rồi `startswith` | NHẬN DIỆN | giữ hàm (danh sách trắng `PREDICATES`), chỉ đọc 2 danh sách trên từ JSON. **Không** viết lại thành DSL `bat_dau` (mất bước bỏ động từ — động từ khác `scope_filter.main_noun` VERB_RX) | THẤP nếu giữ hàm; TRUNG BÌNH nếu đổi sang `main_noun` |

Hàm chỉ có 1 người gọi (LH-05 qua `PREDICATES`). Kiểm: line-diff 0 (dòng lọc G4), test golden các ví dụ `vi_du_dung/vi_du_sai` LH-05 + thêm `Lọc HEPA H13 600x600` (False), `- Cung cấp, lắp đặt lọc bụi G4 500x500` (True), `Bộ lọc túi F7` (False).

## 3. Thứ tự đề xuất Task 3–6 (go / no-go)

1. **Task 3 — FILTER_PREFIXES / FINE_FILTER_RX → `category_rules.json`: GO.** Đã xác nhận NHẬN DIỆN, 1 người gọi, chuyển dữ liệu thuần (giữ hàm). Rủi ro thấp, ít việc; làm đầu để kiểm quy trình line-diff.
2. **Task 4 — parser: GO có giới hạn.**
   - GO: xóa 3 fallback chết (118 `cv_kws`, 523, 622) + chuyển phần cộng cứng `cửa chớp/chớp nhôm` vào `missing_qty_cv_keywords`; `is_lcct_name` → key RIÊNG PV-11; `is_parent_title_kw` → `title_row_rules.json` (substring thuần, không chuẩn hóa); 644 → `subtype_rules.json`.
   - GO tùy chọn (rủi ro trung bình, lợi ích vừa): 597 `is_makeup_air_z`, 606 `is_ktc_diffuser` → `diffuser_rules.json` CHỈ khi chép nguyên danh sách (không gộp với cờ có sẵn).
   - NO-GO: 880 (bảng phụ — đọc cấu trúc, Reader core; cần E2E toàn bộ + `--build --force`; lợi ích 2 đếm).
3. **Task 5 — runner: GO từng phần, theo thứ tự rủi ro tăng dần:** (a) 1208-1210 lọc theo cờ → PV-11; (b) `is_main_cv` + loại trừ only-cửa/van → PV-11; (c) `is_box_combo` fallback → `diffuser_rules.json` + sửa đồng thời `swind_item_inspector.py`; (d) bộ dò xung đột Tên–Ghi chú → `diffuser_rules.json` / `damper_rules.json` với test golden mỗi nhánh + so `ask_alerts` console trên 3 file (line-diff KHÔNG bắt được mục này); (e) `LINED_DUCT_RX` → `duct_rules.json` OG-04 (dùng chung agent_04). `"tiêu âm trong"` (546) gộp vào Task 6 cùng rule tiêu âm, không thay bằng `LINED_DUCT_RX`. `fit_kw` / straight-only: GO nhưng cần test đơn vị riêng vì E2E không chạy cờ đó.
4. **Task 6 — agent_04: GO hẹp / NO-GO phần canvas.**
   - GO: `is_silencer_fitting` (+ 422/438 cút/côn tiêu âm) và `"tiêu âm trong"` → `duct_rules.json` rule tiêu âm mới.
   - **NO-GO hợp nhất canvas `is_fire` với OG-24**: hai danh sách khác nhau và giá thật đang theo agent_04 (tham số `is_fire_resistant` bị bỏ qua) → hợp nhất là đổi giá, cần User chốt; chỉ được chuyển nguyên văn thành rule riêng OG-24B (lợi ích thấp: 0 đếm bánh cóc, canvas mặc định không báo). Ghi bất thường này cho User.
   - Chữ ghi chú BOM (20 đếm) giữ nguyên.

Thứ tự thực hiện: Task 3 → Task 4 (fallback + LCCT + Title) → Task 5 (a→e) → Task 6 (tiêu âm). Mỗi task: line-diff 2 chế độ = 0, pattern lab 0 mẫu đổi; Task 5(d) thêm so console hỏi lại.

## 4. Từ vựng đề xuất cho Task 7

**Phát hiện quan trọng:** đếm trên `tok.string.lower()` (như plan ghi) làm tổng nhảy 196 → 399, và thêm mã van viết hoa → 866 — phần tăng gần như toàn bộ là HIỂN THỊ/KHÓA: Model ra BG (`"+ LCCT"`, `"SDG+O"`, `"MFD"`), mat_id (`MAT-ACTUATOR-…-MPRD`), nhãn nhóm chữ HOA (`"CỬA GIÓ"`, `"VÁCH NGĂN / HỘP TIÊU ÂM"`), help CLI. Code NHẬN DIỆN luôn so chữ thường (`x.lower()` rồi `in`), nên **đề xuất giữ phân biệt hoa/thường** và thay `str.count` bằng regex có ranh giới `(?<![a-z0-9_])kw(?![a-z0-9_])` — loại luôn các KHÓA kiểu `has_obd`, `is_fire_canvas`, `lcct_per_m2` (agent_01: 10 → 2). Nếu vẫn hạ chữ thường thì phải chấp nhận ~+200 đếm HIỂN THỊ trong baseline.

Từ vựng thêm (chữ thường, có ranh giới):
- Van: `van gió`, `van chặn`, `ngăn cháy`, mã `mfd`, `msfd`, `mfsd`, `mprd`, `vcd`, `nrd` (KHÔNG thêm `fd`, `md`, `prd` 2-3 ký tự trần — nhiễu; mã viết thường hiện có: parser 22, agent_05 20, runner 6, utils 5, 01b 3, 03 3).
- Phụ kiện ống: `cút`, `chân rẽ`, `chạc`, `bịt đầu`, `hộp gió`, `côn thu` (không thêm `côn`, `tê`, `co` trần).
- Lọc: `lọc g4`, `lọc bụi`, `lọc thô`, `phin lọc`.
- Khớp nối / chụp / mềm: `khớp nối`, `nối mềm`, `ống mềm`, `chụp thông`.
- Cửa: `nan thẳng`, `cửa chớp`, `eggcrate`, `diffuser`, `grille`, `damper`, `insect screen`, `luover`, `louvre`.
Ước tính (giữ hoa/thường, ranh giới từ, từ vựng cũ + tiếng Việt mới, chưa tính mã van): runner 100, parser 35, agent_04 42, agent_06 26, 00b 19, pricing 16, category_classifier 4, scope_filter 3.

EXEMPT:
- Bỏ khỏi EXEMPT: `category_classifier.py` (≈2–4 sau Task 3 — còn chữ trong docstring/predicate tên), `scope_filter.py` (≈2–3 còn lại là tên khóa JSON / thông báo).
- Giữ EXEMPT: các classifier (`diffuser/damper/duct_classifier`, `typo_normalizer`, `title_row_resolver`, `rule_dsl`), `default_policy.py`, `decision_trace.py` (nhãn hiển thị), công cụ kiểm (`swind_item_inspector`, `swind_e2e_regression`, `swind_pattern_lab`), `agent_00_data_miner`, `extract_master_data`.
- Cân nhắc thêm EXEMPT: `agent_01b_image_boq_reader.py` (bảng sửa lỗi OCR), `swind_universal_extractor.py` / `swind_boq_doctor.py` / `swind_checker.py` (luồng phụ — nếu không, baseline phải ghi rõ là HIỂN THỊ/OCR).

## 5. Số đếm còn lại hợp lệ sau dọn (HIỂN THỊ / KHÓA) — cho docstring Task 7

Theo từ vựng hiện tại, cách đếm hiện tại (sau Task 3-6 nếu làm như mục 3):

| File | Còn lại | Lý do |
|---|---:|---|
| `swind_master_runner.py` | ~44 | 41 console / help CLI / tên linh kiện box + 3 KHÓA (`is_fire_canvas`, `has_obd`, tên cờ `--include-canvas`) |
| `agent_04_bom_duct.py` | ~30 | 20 ghi chú/trace BOM, 9 khóa `ong.canvas.*` / `"lcct"`, 1 tên giả `Hộp tiêu âm` (giảm 1 nếu Task 6 chuyển `phụ kiện tiêu âm`) |
| `agent_06_bom_diffuser.py` | 22 | 21 tên linh kiện BOM + 1 khóa `"lcct"` |
| `swind_pricing.py` | 13 | 5 tên động cơ, 7 khóa hằng số giá, 1 thông báo lỗi |
| `agent_00b_input_normalizer.py` | 11 | cảnh báo cấu trúc (không quyết định báo giá) — giữ hoặc làm task sau |
| `agent_01_boq_extractor.py` | 10 | 8 khóa dict + 2 ghi chú (→ 2 nếu đếm có ranh giới từ) |
| `swind_boq_parser.py` | ~3-5 | 1 khóa `lcct_per_m2`, 2 regex bảng phụ (880) — + 597/606 nếu không chuyển |
| `agent_10_old_quote_carrier.py` | 4 | nhãn nhóm |
| `agent_05_bom_damper.py`, `agent_03_input_auditor.py`, `agent_01b_image_boq_reader.py`, `swind_universal_extractor.py` | 3 mỗi file | tên linh kiện / cảnh báo PCCC / OCR / nhãn |
| `agent_08_qa_checker.py`, `swind_excel_builder.py`, `swind_utils.py` | 1 mỗi file | khóa / regex bố cục |

## Bất thường phát hiện (báo User)

1. Canvas chống cháy có 2 định nghĩa: OG-24 (`duct_classifier.is_fire_canvas`, ghi vào `spec.is_fire_canvas`) và `agent_04._calc_canvas_item.is_fire` (khác danh sách). Runner truyền `is_fire_resistant=…` nhưng `calculate_canvas_bom` không dùng → giá theo agent_04. Không sửa trong plan này (Global Constraint: line-diff 0).
2. `is_box_combo` fallback bị chép ở cả runner (368) và `swind_item_inspector.py` (446) — phải sửa cùng lúc.
3. `LINED_DUCT_RX` nằm ở `agent_04_bom_duct.py`, không ở runner; runner import.
4. Fallback trong parser (`cv_kws`, `single_dim_damper_regex`, `combo_diffuser_regex`) đã lệch khỏi JSON — vô hại khi JSON đủ key, nhưng là bẫy nếu ai "đồng bộ".
5. Plan Task 7 "đếm trên chữ thường" sẽ gấp đôi baseline bằng chữ HIỂN THỊ — xem mục 4.
