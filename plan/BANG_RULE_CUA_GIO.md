# BẢNG KIỂM KÊ RULE NHẬN DIỆN CỬA GIÓ (việc B — 2026-11-03)

Nguồn dữ liệu sống: [`data/master_data/diffuser_rules.json`](../data/master_data/diffuser_rules.json) (bảng dưới là bản tóm tắt để duyệt, chi tiết điều kiện + ví dụ xem JSON).
Bộ chạy: `src/diffuser_classifier.py` · Vai trò: `.agents/roles/diffuser_classifier_role.md` · Test: `tests/test_swind_diffuser_rules.py`.

## 1. Thứ tự ưu tiên (rule đầu tiên khớp thắng)

| # | id | Điều kiện (tóm tắt) | Kết quả | Nguồn | Ví dụ BOQ thật |
|---|---|---|---|---|---|
| 1 | `CG-01_CUA_KIEM_TRA_SDGK` | kiểm tra / cửa thăm / access door / 检查 | SDGK (bỏ OBD/LCCT/lọc), cổ = mặt − 50 | b5bf9c1 26/10 | (chưa có trong input/, mẫu tự dựng) |
| 2 | `CG-02_LCCT_RIENG` | có lưới, không có dấu hiệu cửa/miệng/mã cửa/louver | LCCT / LCCT+F | bd1d662 20/10 | mẫu tự dựng |
| 3 | `CG-03_LOC_G4_RIENG` | có lọc, không lưới/OBD/dấu hiệu cửa | G4 | b5bf9c1 26/10 (AGENTS quy tắc 5) | MKS `Lọc bụi G4 kích thước 200x200` |
| 4 | `CG-04_SOT_TRUNG_ECG` | sọt trứng / dạng lưới / kiểu lưới (xét kiểu nan) | ECG(+O+F+N) | 78741b5 26/10; *kiểu lưới* 7cdc069 02/11 | MKS `Cửa gió thải dạng sọt trưng lõi tháo lắp ... 200x200 kèm van OBD` → ECG+O ×1.15 |
| 5 | `CG-05_TANG_AP_HUT_KHOI_OBD` | tăng áp / hút khói / cấp bù **và** OBD, không slot/linear, **Tên không ghi louver/nan Z** | SDG+O(+N) | bd1d662 20/10; giới hạn Tên 7cdc069 02/11 (User chốt) | BDCC09 `Miệng gió PAG + OBD 600x600` → SDG+O |
| 6 | `CG-06_LOUVER_NAN_Z` | louver/chớp/nan Z; cấp khí bù không ghi mã nan thẳng; cạnh ≥ 3000 (không OBD/2 lớp/nan thẳng); chỉ ghi kèm lưới | WL(+O+N+F) | bd1d662 20/10 | MKS `Louver lấy gió 2500x500`; Minh Triết `Cửa gió Louver 4300x500 ... + LCCT` → WL+N |
| 7 | `CG-07_CUA_HOI_SDG_F` | cửa / miệng hồi (không linear/slot) | SDG+F; đã ghi OBD/LCCT thì không tự thêm lọc | bd1d662 20/10; 78741b5 26/10 | C08 `Miệng gió hồi 450x450` → SDG+F |
| 8a | `CG-08A_KHUECH_TAN_TRON_SRD` | khuếch tán + tròn/round/srd | SRD(+O+N), cổ = D − 150 | b5bf9c1 26/10 | mẫu tự dựng |
| 8b | `CG-08B_KHUECH_TAN_VUONG_SD` | khuếch tán / diffuser, hoặc cửa vuông 600/450/300 hệ điều hòa | SD(+O+N), cổ = mặt − 150 (mặt ≥ 300) | bd1d662; 1805d82 20/10; 7cdc069 02/11 | MKS `Cửa thổi khuếch tán 450x450` → SD+O cổ 300 |
| 9 | `CG-09_DU_PHONG` | còn lại: slot → SLD; linear/ảnh → SLB; mã nan thẳng → BD; tra `subtype_rules.json CUA_GIO` (mặc định BD) | SLD / SLB / WL / SD / SDG(K) | bd1d662; slot 3062d31 27/10 | `2 KL ĐH TG` `Kiểu nan T-1000x400` → SLB+O; MKS `Cửa thổi khuếch tán 1000x150` → SLD 2 khe |

Bước nhận diện dùng chung (trước khi xét thứ tự): `has_obd`, kiểu nan Cột Tên (`has_explicit_*`), mâu thuẫn Tên vs Ghi chú (`note_blade_conflict`, dde7498 28/10), văn bản xét kiểu nan `blade_search` (ff05449 29/10), `has_mesh`, `has_filter`, tháo lắp (7cdc069 02/11), hộp gió, KTC→KTM (+50, khuếch tán +150; bd1d662 / 82d245a), slot dạng dài ≥ 4 lần (7cdc069 02/11).

Hậu xử lý: tháo lắp ×1.15 phần cửa (không áp LCCT/G4); kích thước cổ ghi rõ ghi đè B1/B2.

## 2. Ba lỗi đã biết (mục 1 kế hoạch) — đã sửa từ 02/11, nay khóa bằng `vi_du_sai`

| # | Lỗi | Sửa ở | Ví dụ khóa |
|---|---|---|---|
| 3 | *Cửa thổi khuếch tán* ép sang SDG (cổ 450→300 sai) | 7cdc069 | `CG-08B` vi_du_sai (MKS 450x450 → SD+O cổ 300), `CG-09` vi_du_sai (MKS 1000x150 → SLD 2 khe) |
| 4 | *Cấp bù* → SDG+O dù Tên ghi louver / nan Z | 7cdc069 | `CG-05` vi_du_sai (VGCG `Cửa thổi gió kiểu nan Z ... (CỬA GIÓ CẤP BÙ)` → WL+O) |
| 5 | Không cảnh báo Tên vs Ghi chú cặp `nan bầu dục / nan thẳng` | 7cdc069 (runner + inspector) | ngoài bộ phân loại — cảnh báo ở runner |

## 3. Bốn lỗi phát hiện khi kiểm kê — ĐÃ SỬA 2026-11-03 (User duyệt)

**Nguyên tắc chung chốt khi sửa (AGENTS.md quy tắc 1a):** Title cha truyền **thông số / phụ kiện / chức năng hệ** (OBD, LCCT, G4, EI, độ dày, tăng áp...) xuống dòng con; còn **loại hàng** thì dòng tự ghi (Tên / Ghi chú / cột Model) thắng Title. Dòng không tự ghi loại → theo Title. Rà lại: `CG-05` có 59 dòng nhận *tăng áp* từ Title (21 dòng Tên `SAG+OBD` / `cửa cấp` dưới `HỆ TĂNG ÁP`) — đúng, giữ nguyên.

| # | Lỗi | Sửa | Ảnh hưởng E2E (so ảnh chụp trước khi sửa) |
|---|---|---|---|
| 1 | Cổ bi / Penta R146, R170: Ghi chú `Cửa nan Z`, Model `WL`, Title `HÚT KHÓI ...` → SDG+O+N | `CG-05` thêm cờ `dong_ghi_kieu_nan_khac` (Tên không ghi kiểu nan, Ghi chú/Model ghi louver / nan Z / khuếch tán → nhường rule khác) → **WL+O+N** | Cổ bi & Q.26.0036 Penta: +7.230.000 (cả 2 chế độ), số dòng không đổi |
| 2 | R201 `Cửa gió hồi + ODB` dưới Title `Tủ điện tăng áp hút khói` → ghi chú "(tăng áp / hút khói)" | `CG-05` thêm cờ `chuc_nang_hoi_tai_ten` → `CG-07`, ghi chú *Cửa hồi nan thẳng bầu dục kèm van OBD* | Giá không đổi |
| 3 | C08 R18–22 `Chỉ gồm hộp, không gồm cửa gió` → báo cửa | Parser `BOX_ONLY_RX` → hàng hộp gió `ONG_GIO`: mặc định không báo + `⚠️ HỎI LẠI USER` (lý do riêng); `--include-duct` báo hộp (VD `Hộp gió 450x450xL300`, L từ Ghi chú) | Mặc định −5 dòng, −313.124.000; `--include-duct` số dòng giữ, −133.199.000 (giá hộp thay giá cửa) |
| 4 | BG01_SLAND / Haus_Dalat `DHKK`: mã hạng mục `A1` → cột STT làm cạnh W (cả dòng có KT như `NRD 300x300` cũng đọc w=49) | Reader core `detect_boq_header`: dòng con có chữ dài ở cột Tên mà không có từ khóa tiêu đề → dừng dò tiêu đề phụ; không nhận cột STT làm cột kích thước. Bộ kiểm chứng Agent 00B thêm cảnh báo cột KT/SL trùng cột STT. Kéo theo (cùng nguyên tắc 1a): parser không gán `CUA_GIO` từ Title cho Tên bắt đầu `tole / tôn / box` | BG01_SLAND: 185→182 dòng, 2,05→3,32 tỷ; Haus_Dalat: 222→191 dòng, 11,32→11,39 tỷ. Header đổi đúng 2/130 sheet. **Mỗi file còn 3 dòng van BOQ không ghi kích thước** (`Van xả áp`, `Van chỉnh gió lưu lượng không đổi`) → không báo giá, `⚠️ THÔNG BÁO USER` (User chốt 2026-11-03); dòng `Tole … m²` → ống gió thiếu KT, `Box gió … kW kèm tiêu âm` → tiêu âm thiếu KT (⚠️ cần xác nhận) |
