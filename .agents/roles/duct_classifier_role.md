# DUCT CLASSIFIER: NHẬN DIỆN ỐNG GIÓ & PHỤ KIỆN THEO BẢNG RULE (`ONG_GIO` / `CANVAS` / `TIEU_AM` / `ONG_MEM`)
> **Mã định danh:** `SWIND-DUCT-CLASSIFIER`
> **Module thực thi:** [`src/duct_classifier.py`](file:///Users/hoangan/work/PCCC/swind/src/duct_classifier.py)
> **Bảng rule:** [`data/master_data/duct_rules.json`](file:///Users/hoangan/work/PCCC/swind/data/master_data/duct_rules.json)
> **Vị trí trong luồng:** `Agent04.calculate_duct_item` / `Agent04.detect_duct_subtype` (parser dùng để bắt Zét thiếu độ lệch), `Agent04._parse_note_boxes`, `Agent01._resolve_duct_spec` (LCCT/G4 trong cút, canvas chống cháy, cờ hỏi lại hộp gió).
> **Kế hoạch gốc:** [KE_HOACH_TACH_AGENT_DOC_BOQ.md](file:///Users/hoangan/work/PCCC/swind/plan/KE_HOACH_TACH_AGENT_DOC_BOQ.md) mục 4 · Bảng kiểm kê: [BANG_RULE_ONG_GIO.md](file:///Users/hoangan/work/PCCC/swind/plan/BANG_RULE_ONG_GIO.md)

---

## 1. VAI TRÒ
- **Chỉ phân loại** 1 dòng ống / phụ kiện: loại (`DUCT_RECT`, `ELBOW_SQ`, `REDUCER_SQ`, `SQUARE_TO_ROUND`, `PLENUM_BOX`, `OFFSET_Z`, `CANVAS_SQ`, `SILENCER_SQ`, `FLEX_DUCT`, `VENTCAP`...), các hộp ghi trong Ghi chú, phụ kiện kèm (LCCT / lọc G4 / canvas chống cháy), cờ hỏi lại User.
- Văn bản xét = **Tên gốc + Ghi chú của chính dòng** (không gồm Title cha). Ngoại lệ duy nhất kế thừa Title: dòng nhóm `TIEU_AM` chỉ ghi kích thước (`OG-19`).
- **Không** tính tôn / giá (`Agent04._calc_*`), không quyết định báo hay không báo (phạm vi — việc C3).

## 2. CẤU TRÚC BẢNG RULE
| Khối | Nội dung |
|---|---|
| `ong_tron` | Điều kiện ống tròn (`is_round`) |
| `thu_tu_nhan_dien` | `OG-01..OG-18`, **rule đầu tiên khớp thắng**; khớp theo `tu_khoa` / `regex` / `bat_dau` / `don_vi` / `hoac_hinh_hoc`, lọc bằng `va_hinh_hoc` / `tru_cum` / `tru_bat_dau` (xem `cu_phap`) |
| `quy_tac_bo_sung` | `OG-19` tiêu âm theo Title · `OG-20` Zét thiếu độ lệch E → trống giá · `OG-21` hộp trong Ghi chú (≥ 2 hộp cộng tiền; 1 hộp khác Tên → hỏi lại) · `OG-22` LCCT/G4 trong cút · `OG-23` LCCT trong phụ kiện vuông · `OG-24` canvas chống cháy |

## 3. QUY TẮC SỬA RULE (AGENTS.md mục 7)
1. Đổi từ khóa / thứ tự / thêm rule → sửa JSON. Điều kiện hình học mới → thêm vào `_GEOM` trong `duct_classifier.py` và `cu_phap.hinh_hoc`.
2. `git log -S` tìm nguồn → rẽ nhánh giữ case cũ → ghi `nguon` / `ly_do` → thêm ví dụ (ưu tiên dòng BOQ thật, `nguon_boq`).
3. Chạy `tests/test_swind_duct_rules.py` + self-test + unit + E2E 2 chế độ (phần ống chủ yếu lộ ở `--include-duct`).

## 4. LỊCH SỬ
- 2026-10-20 → 2026-11-03: chuỗi if trong `Agent04.detect_duct_subtype` + từ khóa rải ở Agent 01 / 04.
- 2026-11-03 (việc C2): trích ra bảng JSON + `duct_classifier`. Tương đương 100% so code sau C1: 52 BOQ (9.317 dòng, 46.585 lần giải mã) + 75.000 ca ống ngẫu nhiên (`detect_duct_subtype`, `calculate_duct_item`) → 0 lệch; E2E 2 chế độ không đổi. Rule mới `OG-21` 1 hộp khác Tên → `⚠️ [HỎI LẠI USER]` ở Kiểm soát cuối (User chốt; chưa có dòng nào trong 52 BOQ chạm tới).
- 2026-11-03 (User duyệt): *chụp thông gió* → VENTCAP (mặc định không báo cùng canvas), *flexible connection* → canvas; giá đỡ dưới Title nối mềm → thương mại (parser). Giải trình: `plan/BANG_RULE_ONG_GIO.md` mục 3.
