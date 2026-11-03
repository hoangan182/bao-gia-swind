# DIFFUSER CLASSIFIER: NHẬN DIỆN CỬA GIÓ THEO BẢNG RULE (`CUA_GIO`)
> **Mã định danh:** `SWIND-DIFFUSER-CLASSIFIER`
> **Module thực thi:** [`src/diffuser_classifier.py`](file:///Users/hoangan/work/PCCC/swind/src/diffuser_classifier.py)
> **Bảng rule (nguồn dữ liệu duy nhất):** [`data/master_data/diffuser_rules.json`](file:///Users/hoangan/work/PCCC/swind/data/master_data/diffuser_rules.json)
> **Vị trí trong luồng:** được `Agent01._resolve_diffuser_spec` gọi cho mọi dòng `CUA_GIO` (kể cả combo Cửa + Van).
> **Kế hoạch gốc:** [KE_HOACH_TACH_AGENT_DOC_BOQ.md](file:///Users/hoangan/work/PCCC/swind/plan/KE_HOACH_TACH_AGENT_DOC_BOQ.md) mục 3 · Bảng kiểm kê: [BANG_RULE_CUA_GIO.md](file:///Users/hoangan/work/PCCC/swind/plan/BANG_RULE_CUA_GIO.md)

---

## 1. VAI TRÒ
- **Chỉ phân loại** 1 dòng cửa gió: tính cờ nhận diện → cộng KTC→KTM → chọn rule theo thứ tự ưu tiên → Model (`SDG+O+F+N`, `WL+N`, `SD`, `SLD`...), B1/B2 (kích thước cổ), ghi chú báo giá, hệ số tháo lắp.
- **Không** ghép giá: combo Cửa + Van (gọi lại Agent 01 cho phần van) và hộp gió (`Agent04._calc_plenum_box`) vẫn nằm ở `Agent01._resolve_diffuser_spec`.
- **Không** đọc file BOQ, không sửa dữ liệu ngoài các trường Agent 01 trước đây đã ghi (`w/h/d` sau KTC, `w_pre_ktc`, `h_pre_ktc`, `is_ktc_applied`, `w_damper`...).

## 2. CẤU TRÚC BẢNG RULE
| Khối | Nội dung |
|---|---|
| `nhom_tu_khoa` | Nhóm từ khóa dùng chung (`@mesh_kws`, `@louver_kws`...). Nhóm có `tu_cau_hinh` lấy danh sách từ `subtype_rules.json -> COMBO_AND_DETECTION_RULES` rồi cộng `them`. |
| `buoc_nhan_dien` | Chạy **theo thứ tự**: tính cờ (`co`), văn bản xét (`van_ban`, VD `blade_search` = văn bản xét kiểu nan), bước đặc biệt (`tinh`: đếm khe slot, áp KTC). Cờ có thể bị bước sau bật thêm (`dat_true_khi`). |
| `thu_tu_uu_tien` | Danh sách rule, **rule đầu tiên khớp thắng**. Mỗi rule: `id`, `ten`, `dieu_kien`, `gan` (đổi cờ khi rule thắng), `profile`, `model`, `b`, `ghi_chu`, `nguon`, `ly_do`, `vi_du_dung`, `vi_du_sai`. Rule cuối `CG-09_DU_PHONG` (`dieu_kien: true`) chọn profile qua `chon_profile` rồi lấy kết quả ở `theo_profile`. |
| `thao_lap` / `co_explicit` | Hậu xử lý: hệ số tháo lắp (`cua.he_so_thao_lap`), kích thước cổ ghi rõ ghi đè B1/B2. |

Cú pháp điều kiện ghi ở khóa `cu_phap` trong JSON (`tat_ca` / `mot_trong` / `khong` / `tu_khoa` / `regex` / `so_sanh` / `thuoc`, cờ `"ten_co"` / `"!ten_co"`).

Thứ tự ưu tiên hiện tại: `CG-01` cửa kiểm tra SDGK → `CG-02` LCCT rời → `CG-03` lọc G4 rời → `CG-04` sọt trứng ECG → `CG-05` tăng áp / hút khói / cấp bù kèm OBD (Tên không ghi louver) → `CG-06` louver nan Z → `CG-07` cửa hồi SDG+F → `CG-08A` khuếch tán tròn SRD → `CG-08B` khuếch tán vuông SD → `CG-09` dự phòng (slot SLD → linear SLB → mã nan thẳng BD → `subtype_rules.json CUA_GIO`, mặc định SDG).

## 3. QUY TẮC SỬA RULE (AGENTS.md mục 7)
1. **Sửa trong JSON, không thêm `if/elif` vào code.** Cú pháp chưa đủ diễn tả → mở rộng bộ chạy điều kiện trong `diffuser_classifier.py` (hàm `_Ctx.ok`), không viết nhánh riêng cho 1 dự án.
2. Trước khi sửa: `git log -S "<từ khóa>"` tìm commit / dự án sinh ra rule (đã ghi ở `nguon`). Rẽ nhánh giữ case cũ; chỉ xóa khi rule được xác nhận sai.
3. Ghi `nguon` (commit / ngày / dự án / người chốt) và `ly_do`. Case từng sai → thêm vào `vi_du_sai` kèm `loi_cu`.
4. Mỗi rule ≥ 1 `vi_du_dung` (ưu tiên dòng BOQ thật trong `input/`, ghi `nguon_boq`). Ví dụ có thể kiểm `model`, `b`, `rule` (rule mong đợi khác rule đang chứa ví dụ), `he_so_thao_lap`, `ghi_chu_bg_chua`.
5. Chạy: `./venv/bin/python -m unittest tests/test_swind_diffuser_rules.py` + self-test + unit + E2E 2 chế độ; file nào lệch phải giải thích được.

## 4. LỊCH SỬ
- 2026-10-20 → 2026-11-02: rule nằm trong chuỗi `if/elif` ~370 dòng của `Agent01._resolve_diffuser_spec` (xem `nguon` từng rule).
- 2026-11-03 (việc B tách agent đọc BOQ): trích ra bảng JSON + bộ chạy `diffuser_classifier`. Kiểm chứng tương đương 100%: phát lại 3.850 lần gọi ghi từ 52 BOQ `input/` (mặc định & `--include-duct --include-box`) và 45.000 ca ngẫu nhiên so code cũ — 0 lệch; E2E 2 chế độ không đổi. Nhánh dự phòng `ECG` trong `CG-09` hiện không thể chạm tới (giữ để tương đương code cũ).
- 2026-11-03 (User duyệt): `CG-05` nhường rule khác khi **chính dòng** ghi loại khác Title cha — Ghi chú / Model ghi louver / nan Z / khuếch tán khi Tên không ghi kiểu nan (cờ `dong_ghi_kieu_nan_khac`), Tên ghi cửa hồi mà tăng áp chỉ ở Title (`chuc_nang_hoi_tai_ten`). Đổi đúng 6 dòng (Cổ bi / Q.26.0036 Penta R146, R170, R201); 57 dòng khác kế thừa tăng áp từ Title giữ nguyên.
