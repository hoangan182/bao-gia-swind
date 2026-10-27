---
description: Sổ tay Chỉ mục Công thức & Tọa độ dòng code (Formula Index & Fast Lookup Rule) của Swind
---

# SỔ TAY CHỈ MỤC CÔNG THỨC & TỌA ĐỘ CODE (03_FORMULA_INDEX) - SWIND

> **QUY TẮC BẮT BUỘC ĐỂ TĂNG TỐC ĐỘ DUYỆT FILE GẤP 10 LẦN:**
> 1. **CẤM ĐỌC TOÀN BỘ FILE LỚN (`read_file` từ dòng 1 đến hết)** khi chỉ cần kiểm tra, giải thích hoặc chỉnh sửa công thức của 1-2 sản phẩm.
> 2. **BƯỚC 1:** Tra bảng chỉ mục bên dưới để lấy chính xác `File`, `Method` và khoảng dòng `StartLine..EndLine`, sau đó chỉ gọi `read_file(Path, StartLine, EndLine)` trong phạm vi **30–70 dòng** của hàm đó.
> 3. **BƯỚC 2:** Dùng công cụ dòng lệnh `src/swind_item_inspector.py` để test tức thì (0.1 giây) 1 mặt hàng bất kỳ hoặc chạy `--self-test` kiểm tra hồi quy toàn bộ 53 mặt hàng chuẩn Swind trước & sau khi sửa công thức.

---

## 1. CÔNG CỤ KIỂM TRA NHANH 1 MẶT HÀNG & REGRESSION TEST (`src/swind_item_inspector.py`)

Trước hoặc sau khi sửa bất kỳ công thức nào, chạy lệnh sau để xem ngay toàn bộ chuỗi:
`BOQ Text -> Subtype/Model -> Kích thước A1,A2,B1,B2,L,Thk -> Diện tích m2 -> Vết công thức -> Từng dòng vật tư BOM -> Giá bán cuối cùng (làm tròn lên hàng trăm)`:

```bash
# Kiểm tra nhanh 1 mặt hàng bất kỳ (chỉ mất ~0.1s, không cần chạy cả dự án Excel):
./venv/bin/python src/swind_item_inspector.py "Cút 90 độ 800x400 tôn 0.75"
./venv/bin/python src/swind_item_inspector.py "Côn thu 1000x500 xuống 600x400 L=800"
./venv/bin/python src/swind_item_inspector.py "Chân rẽ 500x300/400x300" --formula-mode bienia
./venv/bin/python src/swind_item_inspector.py "Van chặn lửa động cơ MFD 1200x800 EI90"
./venv/bin/python src/swind_item_inspector.py "Van chặn lửa động cơ MFD 1200x800 EI90" --motor KLB
./venv/bin/python src/swind_item_inspector.py "Van chặn lửa cầu chì FD 800x600 EI120"
./venv/bin/python src/swind_item_inspector.py "Cửa gió khuếch tán 600x600 kèm OBD"
./venv/bin/python src/swind_item_inspector.py "Miệng gió cấp 1000mm D150"

# Quét nhanh toàn bộ BOQ trong 0.2s để gom nhóm Model/Subtype & kiểm tra dòng thiếu kích thước (không cần viết script phụ):
./venv/bin/python src/swind_item_inspector.py --audit-boq "input/A4_BOQ_Van gió.xlsx"

# 🔎 TRA CỨU TỨC THÌ (0.03s) ĐƠN GIÁ VẬT TƯ, BAREM, MẶT HÀNG CHUẨN & TỪ KHÓA ĐÃ CÓ TRONG HỆ THỐNG:
./venv/bin/python src/swind_item_inspector.py --search "belimo"
./venv/bin/python src/swind_item_inspector.py --search "tôn 1.15"
./venv/bin/python src/swind_item_inspector.py --search "vcd"

# 🧭 ĐỊNH VỊ TỨC THÌ BẰNG AST (0.02s) FILE CODE, HÀM & SỐ DÒNG SỐNG ĐỂ THÊM YÊU CẦU MỚI:
./venv/bin/python src/swind_item_inspector.py --locate "header"
./venv/bin/python src/swind_item_inspector.py --locate "từ khóa"
./venv/bin/python src/swind_item_inspector.py --locate "van mfd"

# 📊 ĐỐI CHIẾU TRỰC TIẾP (0.2s) FILE EXCEL BÁO GIÁ / BOQ VỚI GIÁ & CÔNG THỨC TRONG HỆ THỐNG:
./venv/bin/python src/swind_item_inspector.py --compare "output/Ten_Du_An/Ten_File.xlsx"

# 📐 KIỂM TRA MA TRẬN NHIỀU KÍCH THƯỚC HOẶC NHIỀU MẶT HÀNG TRONG 1 LỆNH DUY NHẤT (IN-MEMORY 0.04s):
./venv/bin/python src/swind_item_inspector.py "Van chặn lửa FD EI60" --sizes "400x200,600x400,800x600,1000x500"
./venv/bin/python src/swind_item_inspector.py "Van VCD 400x200 ; Van NRD 500x300 ; Cửa gió 600x600 kèm OBD"

# Chạy kiểm thử tự động 53 mặt hàng chuẩn (so khớp với data/master_data/formula_regression_baseline.json):
./venv/bin/python src/swind_item_inspector.py --self-test

# Cập nhật lại baseline sau khi chủ đích thay đổi công thức được duyệt:
./venv/bin/python src/swind_item_inspector.py --save-baseline
```

### ⚡ QUY TẮC TÁCH SUBAGENT KHI XỬ LÝ YÊU CẦU MỚI & SO SÁNH DỮ LIỆU LỚN:
1. **Khi thêm yêu cầu mà hệ thống chưa có:**
   - Gọi ngay `./venv/bin/python src/swind_item_inspector.py --locate "<từ_khóa_yêu_cầu>"` để lấy chính xác đường dẫn file JSON và tọa độ dòng `StartLine..EndLine` sống của hàm Python cần sửa (tuyệt đối không đọc dò từ đầu file).
2. **Khi kiểm tra công thức, giá trong hệ thống & so sánh với file dự án:**
   - Gọi ngay `--search "<từ_khóa>"`, `--compare "<file.xlsx>"` hoặc `--sizes "..."` (xử lý trực tiếp trong RAM `< 0.2s`, không viết script Python tạm).
   - Nếu người dùng yêu cầu **đồng thời** đối chiếu nhiều bảng dữ liệu/file dự án VÀ sửa/thêm yêu cầu mới vào hệ thống, hãy dùng `invoke_subagent` tách thành 2 luồng song song:
     + **Subagent 1 (`research` / Role: `"System Price & Formula Comparator"`)**: Chạy `--search` và `--compare` để lập bảng đối chiếu giá/công thức.
     + **Agent chính (hoặc Subagent 2 `self` / Role: `"Requirement Integrator"`)**: Dùng `--locate` sửa đúng hàm/JSON và chạy `--self-test`.

---

## 2. BẢNG CHỈ MỤC CÔNG THỨC ỐNG GIÓ & PHỤ KIỆN (`src/agent_04_bom_duct.py`)

Mỗi loại phụ kiện ống gió đã được tách thành **1 hàm riêng biệt (15–90 dòng)**. Chỉ đọc đúng hàm cần sửa:

| Nhóm / Subtype | Tên hàm trong `Agent04_DuctworkBOM` | Dòng (`StartLine..EndLine`) | Nội dung công thức chính |
| :--- | :--- | :---: | :--- |
| **Bảng tra & Đơn giá m2** | `THICKNESS_RULES` .. `ROUND_FITTING_PRICES` | `20..112` | Quy tắc độ dày TCVN 5687, đơn giá bán 1 m² ống vuông/tròn/Nẹp C/TDF/V30/Bọc EI |
| **Chuẩn hóa độ dày** | `normalize_thickness`, `get_standard_thickness` | `114..152` | Làm tròn độ dày tôn (`0.58, 0.75, 0.95, 1.15`) & tra độ dày theo `max(W,H)` hoặc `D` |
| **Nhận diện Subtype** | `detect_duct_subtype` | `155..197` | Phân loại tên BOQ thành `DUCT_RECT`, `ELBOW_SQ`, `REDUCER_SQ`, `SHOE_TAP`, `OFFSET_Z`, v.v. |
| **Điều phối chính** | `calculate_duct_item` | `200..271` | Hàm gốc điều phối sang các hàm con theo `subtype` |
| **Chụp thông hơi (`VENTCAP`)** | `_calc_ventcap_item` | `274..288` | Chụp thông hơi / chắn mưa gắn tường tôn mạ kẽm hoặc Inox |
| **Khớp nối mềm (`CANVAS_SQ`, `CANVAS_RT`)** | `_calc_canvas_item` | `291..338` | Chu vi `2*(W+H)/1000` (vuông) hoặc `3.14*D/1000` (tròn); đơn giá mét dài Canvas thường/chống cháy |
| **Ống gió mềm (`FLEX_DUCT`)** | `_calc_flex_duct_item` | `341..360` | Ống mềm có bảo ôn (`FLEX-BO`) / không bảo ôn (`FLEX-KBO`) |
| **Tiêu âm (`SILENCER_SQ`, `SILENCER_RT`)** | `_calc_silencer_item` | `363..452` | Hộp tiêu âm vuông (vỏ tôn + vách tiêu âm theo W) & tiêu âm tròn |
| **Ống/PK tính theo m² (`DUCT_M2`, `FITTING_M2`)** | `_calc_m2_duct_or_fitting_item` | `455..475` | Khi BOQ có ĐVT là `m2`: lấy trực tiếp đơn giá m² theo độ dày & kiểu bích |
| **Ống tròn & PK tròn (`SPIRAL_DUCT`, `ELBOW_RT`, `REDUCER_RT`, `TEE_RT`, `WYE_RT`, `TAKEOFF_RT`, `END_CAP_RT`, `COUPLING_RT`)** | `_calc_round_duct_or_fitting_item` | `478..612` | Toàn bộ công thức diện tích & đơn giá ống tròn xoắn, cút tròn, côn thu tròn, tê/y tròn, cổ trích tròn, măng xông |
| **Ống gió vuông thẳng (`DUCT_RECT`)** | `_calc_rect_duct` | `615..637` | `S = 2*(W+H)*L` (`L=1.0m` nếu ĐVT=`md`, `L=1.12m` nếu ĐVT=`cái`/`ống`) |
| **Côn thu vuông (`REDUCER_SQ`)** | `_calc_rect_reducer` | `640..665` | Hỗ trợ 3 chế độ `formula_mode`: `standard` (`(W1+H1+W2+H2)*L`), `bienia` (`+0.1m` gờ), `cand` |
| **Chân rẽ / Cổ trích vuông (`SHOE_TAP`)** | `_calc_rect_shoe_tap` | `668..694` | Hỗ trợ 3 chế độ `formula_mode`: `standard` (`(W1+H1+100+W2+H2)*L`), `bienia`, `cand` |
| **Côn vuông sang tròn (`SQUARE_TO_ROUND`)** | `_calc_square_to_round` | `697..719` | Hỗ trợ `standard` (`1.2*(W+H+2*D)*L`), `bienia`, `cand` |
| **Cút / Chếch vuông (`ELBOW_SQ`)** | `_calc_rect_elbow` | `722..763` | Cút 90° (`standard` vs `bienia` vs `cand`), Chếch 45° (`area_90 * 0.5` hoặc `bienia`/`cand`), Cút lượn |
| **Ống lượn Z / Offset (`OFFSET_Z`)** | `_calc_rect_offset_z` | `766..790` | Hỗ trợ `standard`, `bienia` (`L_cant = sqrt(L^2 + E^2) + 100`), `cand` |
| **Chạc Y vuông (`WYE_SQ`)** | `_calc_rect_wye` | `793..808` | Chạc ba chữ Y ống vuông (`standard` vs `bienia`) |
| **Tê vuông (`TEE_SQ`)** | `_calc_rect_tee` | `811..827` | Tê đều / tê thu ống vuông (`standard`, `bienia`, `cand`) |
| **Bịt đầu ống vuông (`END_CAP_SQ`)** | `_calc_rect_end_cap` | `830..850` | Bịt đầu ống (`standard`, `bienia`, `cand`) |
| **Hộp gió / Plenum Box (`PLENUM_BOX`)** | `_calc_plenum_box` | `853..871` | Hộp tĩnh áp 5 mặt tôn + bích (`standard`, `bienia`, `cand`) |
| **Ghép đơn giá & hệ số phụ kiện vuông** | `_calc_rect_duct_or_fitting_item` | `874..957` | Gọi các hàm `_calc_rect_*`, nhân đơn giá m², áp hệ số `1.12x` (cút/tê/zét/hộp) và bọc chống cháy EI |
| **Quy đổi ra BOM Sheet chi tiết** | `calculate_duct_bom`, `calculate_canvas_bom`, `calculate_acoustic_partition_bom` | `960..1127` | Quy đổi đơn giá bán mục tiêu ngược ra định mức vật tư để xuất sang sheet chi tiết Excel |

---

## 3. BẢNG CHỈ MỤC CÔNG THỨC VAN GIÓ (`src/agent_05_bom_damper.py`)

File `src/agent_05_bom_damper.py` đã được chia nhỏ thành **10 hàm thành phần rõ ràng (16–115 dòng)**:

| Nhóm / Chức năng | Tên hàm trong `Agent05_DamperBOM` | Dòng (`StartLine..EndLine`) | Nội dung công thức chính |
| :--- | :--- | :---: | :--- |
| **Điều phối tổng** | `calculate_damper_bom` | `23..121` | Điều phối luồng tính van gió từ kích thước -> chia modul -> vật tư -> định giá bán mục tiêu |
| **Van OBD độc lập (`OBD`, `SOBD`)** | `_calc_obd_damper` | `124..181` | Van OBD nhôm định hình (`OBD_KHUNG 0.45`, `OBD_CANH 0.10`, `OBD_thanh_lien_ket`, sơn `20,000`, giá mục tiêu `round((Al*160000+Paint+Acc)*1.2, -3)`) |
| **Quy tắc chia Modul van** | `_calculate_damper_modules` | `184..233` | Quy tắc thu côn tối thiểu `150x150` & chia modul theo BCTN (`1.04` `1750x1000`, `1.05` `1700x1000`, `1.01/1.02/1.03/2.01` `1500x800`, MD KLB `1/2/4/8`, MD thường `2000x2000`) |
| **Khung thân & Lá cánh van** | `_calc_body_and_blade_specs` | `236..350` | Tính chiều dài thân `L`, độ dày thân/cánh, khối lượng tôn khung, lá cánh, lá giữa, thanh chống, ke góc, trục & bạc |
| **Động cơ / Cầu chì / Tay gạt** | `_append_actuator_or_mechanism` | `353..455` | Chọn động cơ Belimo (`FSLF24`/`BFN24`/`NM230A`/`SM230A`), KLB (`V6006`/`10Nm`), Honeywell (`MS4609`/`CN4605A-20A`), cầu chì `70-74°C`, lò xo, tay gạt VCD/VCD trục vít |
| **Vật tư chống cháy EI (`FD_EI`, `MFD`)** | `_append_fire_insulation_components` | `458..528` | Tấm chống cháy MGO/CSB/Thạch cao theo BCTN (`1.01..1.05`, `2.01`) hoặc tấm cách nhiệt KSH 10mm (`VCD/NRD/PRD EI`) |
| **Định giá Van tròn (`D > 0`)** | `_price_round_damper` | `531..562` | Công thức giá bán mục tiêu van tròn VCD, VCD trục vít, FD, NRD, MD, MFD |
| **Định giá Van chống cháy EI (`FD_EI`, `MFD`)** | `_price_fire_damper_ei_or_mfd` | `565..585` | Công thức chuẩn 2026 Sheet `'BG VAN'`: `target_sell_price = (O + AQ + AR + AS + AY + 100,000) * 1.25 * modules_count` |
| **Định giá Van cầu chì thường (`FD` non-EI)** | `_price_normal_fd_damper` | `588..603` | Công thức giá bán van cầu chì thường tôn mạ kẽm (`S_m2 <= 0.04` -> `200,000`, hệ số nhân `1.56..1.875`) |
| **Định giá Van vuông thường (`VCD`, `VCD_VIT`, `NRD`, `PRD`, `MD`)** | `_price_square_standard_damper` | `606..637` | Công thức giá bán van vuông VCD, VCD trục vít, NRD, PRD, MD + cộng bọc KSH 10mm nếu có EI |
| **Quy đổi ngược ra hệ số BOM** | `_scale_components_to_target_sell` | `640..665` | Co giãn `calc_qty` phần cơ khí để tổng giá bán qua hệ số tài chính (Labor 25%, Overhead 10%, Margin 18%) khớp đúng `target_sell_price` |

---

## 4. BẢNG CHỈ MỤC CÔNG THỨC CỬA GIÓ (`src/agent_06_bom_diffuser.py`)

File `src/agent_06_bom_diffuser.py` đã được chia nhỏ thành **8 hàm riêng biệt theo từng hệ nhôm (`profile_type`) (16–78 dòng)** với đơn giá nhôm chuẩn Swind (`165,000 đ/kg` giá bán nhôm, `20,000 đ/kg` sơn tĩnh điện, `200,000 đ/m2` LCCT rời):

| Mã hệ (`profile_type`) | Tên hàm trong `Agent06_DiffuserBOM` | Dòng (`StartLine..EndLine`) | Nội dung công thức chính |
| :--- | :--- | :---: | :--- |
| **Điều phối tổng** | `calculate_diffuser_bom` | `28..89` | Chuẩn hóa kích thước cổ -> mặt (`W_face = W_neck + 50`), điều phối sang hàm hệ nhôm và cộng phụ kiện |
| **Lưới chắn côn trùng rời (`LCCT`)** | `_calc_profile_lcct` | `92..107` | Lưới Inox 304 rời tính theo diện tích `S = W * H / 1,000,000`, giá mục tiêu `max(120000, round(S * 200000, -3))` |
| **Lọc bụi G4 rời (`FILTER_G4`)** | `_calc_profile_filter_g4` | `110..125` | Khung lọc bụi G4 rời `max(150000, round((S*150000 + P*60000)*1.3, -3))` |
| **Cửa Louver nan Z (`Z` / `WL`)** | `_calc_profile_louver_z` | `128..200` | Khung Z (`0.55 kg/m`), nan Z (`0.33 kg/m`), bước nan `40mm`, thanh liên kết, sơn `20,000`, công thức giá bán `WL` / `WL+N` (`* 1.2`) |
| **Cửa sọt trứng (`ECG`)** | `_calc_profile_eggcrate` | `203..264` | Khung bầu dục (`0.50` hoặc tháo lắp `0.93 kg/m`), lõi sọt trứng `125,000 đ/m2`, bản lề + chốt nếu tháo lắp |
| **Cửa Linear nan T (`SLB`)** | `_calc_profile_linear_slb` | `267..338` | Khung SLB (`0.42 kg/m`), nan T (`0.23 kg/m`, bước `20mm`), tăng cứng, sơn đen lớp 2 (`+15%`) |
| **Cửa gió kiểu khe hẹp Slot (`SLD` / `DLS`)** | `_calc_profile_slot_sld` | `341..415` | 4 hệ nhôm Slot (`SH8061 0.30`, `SH8060 0.25`, `SH8083 0.15`, `SH8057B 0.22 kg/m`), chia `1 slot` (`<150`), `2 slot` (`150..<200`), `3 slot` (`>=200`), phụ kiện `5,000 + 10,000*N`, hệ số `1.25` |
| **Cửa khuếch tán vuông/tròn (`T` / `SD` / `SRD`)** | `_calc_profile_diffuser_t` | `418..474` | Cửa khuếch tán vuông 4 hướng `SD` (khung KT `0.63 kg/m`, bước nan `37.5mm`) & khuếch tán tròn `SRD` |
| **Cửa nan bầu dục 1 lớp / 2 lớp / cửa thăm (`BD` / `SDG` / `SDGK`)** | `_calc_profile_oval_bd` | `477..554` | Cửa cấp/hồi nan bầu dục 1 lớp, 2 lớp (`is_double_layer`), cửa kiểm tra tháo lắp (`is_removable` -> `SDGK`) |
| **Phụ kiện cửa gió (`+O`, `+N`, `+F`)** | `_append_diffuser_accessories` | `557..630` | Cộng thêm Van OBD gắn kèm (`+O`), Lưới chắn côn trùng Inox 304 (`+N`), Lưới lọc bụi G4 (`+F`) và quy đổi `target_sell` |

---

## 5. BẢNG CHỈ MỤC BÓC TÁCH BOQ, NHẬN DIỆN MODEL & LÀM TRÒN GIÁ CUỐI

| File | Hàm / Khu vực | Dòng (`StartLine..EndLine`) | Chức năng cần tra cứu |
| :--- | :--- | :---: | :--- |
| `src/agent_01_boq_extractor.py` | `_resolve_damper_spec` | `84..331` | Giải mã Model & Ghi chú kỹ thuật nhóm `VAN_GIO` (`SWIND-1.01..1.05`, `SWIND-2.01`, `MD`, `VCD`, `NRD`, `PRD`, `OBD`, Combo Van+Van) |
| `src/agent_01_boq_extractor.py` | `_resolve_diffuser_spec` | `334..623` | Giải mã Model & Ghi chú kỹ thuật nhóm `CUA_GIO` (Rule 1 KTC->KTM `+50mm`, Rule 2..6 `SD`, `SDG`, `SDGK`, `WL`, `SLB`, `ECG`, Combo Cửa+Van) |
| `src/agent_01_boq_extractor.py` | `_resolve_duct_spec` | `626..711` | Giải mã Model & Ghi chú kỹ thuật nhóm `ONG_GIO`, `CANVAS`, `TIEU_AM`, `ONG_MEM` |
| `src/agent_01_boq_extractor.py` | `resolve_item_spec` | `714..835` | Hàm điều phối tổng giải mã `resolved_spec` cho từng dòng BOQ |
| `src/swind_utils.py` | `detect_boq_header` | `79..471` | Tự động tìm dòng Header BOQ và ánh xạ cột (`name`, `w`, `h`, `l`, `unit`, `qty`, `remarks`, phiếu đặt hàng `Lần N`) |
| `src/swind_utils.py` | `extract_duct_fitting_geometry` | `474..657` | Bóc tách hình học phụ kiện ống gió phức tạp từ chuỗi văn bản (`W1xH1`, `W2xH2`, `D`, `L`, `R`, `offset`, góc độ, kiểu bích) |
| `src/swind_boq_parser.py` | `parse_sheet` (Phân loại Category) | `213..344` | Phân loại dòng BOQ vào `ONG_GIO`, `VAN_GIO`, `CUA_GIO`, `TIEU_AM`, `CANVAS`, `ONG_MEM`, `THUONG_MAI` |
| `src/swind_boq_parser.py` | `parse_sheet` (Bóc kích thước & EI) | `345..509` | Bóc tách `W, H, D, L`, độ dày `thickness`, chỉ số `ei_rating`, quy tắc `KTC +50mm` |
| `src/swind_boq_parser.py` | `parse_sheet` (Combo Cửa+Van / Van+Van) | `510..641` | Nhận diện và tách cấu trúc Combo Cửa kèm Van (`SDG + MFD`) hoặc Van kèm Van (`FD + VCD`) |
| `src/swind_master_runner.py` | `process_single_sheet_estimation` (Tạo BOM & Tính giá) | `410..700` | Tính chi phí Vật tư + Nhân công (25%) + Quản lý (10%) + Lợi nhuận (18%, miễn markup trên động cơ) và **làm tròn đơn giá bán cuối cùng lên hàng trăm (`ceil(raw / 100) * 100`)** tại dòng `690..691` |
