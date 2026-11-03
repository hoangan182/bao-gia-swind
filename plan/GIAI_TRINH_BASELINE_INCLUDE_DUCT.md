# GIẢI TRÌNH LỆCH BASELINE `--include-duct` (cuối việc C — 2026-11-03)

Baseline `data/master_data/e2e_baseline_include_duct.json` lưu từ commit `590365b` (30/10), chưa cập nhật qua các đợt sửa rule sau đó (baseline mặc định thì đã cập nhật ở `f6ef0f7`, `eeebc61`, `f31a9d4`, C1).

**Cách truy:** chạy E2E `--include-duct` ở từng commit sau `590365b` (worktree riêng, master data của chính commit đó) + ảnh chụp trước / sau C1 + bản hiện tại (sau C3); file đổi tổng ở bước nào thì quy cho bước đó. Lần chạy lỗi tạm ở `63d9691` / `8fd8193` (tổng = None) bỏ qua.

**Kiểm tra lại:** chạy code `590365b` khớp baseline 40/41 file; file lệch duy nhất `2 KL ĐH TG` (151.747.100 vs 150.626.100) ngay commit sau đã về đúng baseline → nhiễu môi trường lúc lưu.

| File | Baseline cũ | Hiện tại (sau C3) | Đổi ở bước (tổng sau bước) |
|---|---|---|---|
| 01.PYCVT - ĐƠN 69  - VẬT TƯ VAN KÈM ĐỘNG CƠ.xlsx | 660,429,300 (11 dòng) | 666,021,300 (11 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 663,429,300<br>C1 03/11 van (VG-02A, FD và NRD, MD có EI bọc, miệng gio / AAG): 666,021,300 |
| 14. Ống thông gió và pk - Minh Triết.xlsx | 1,639,422,000 (174 dòng) | 3,403,135,850 (238 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 3,381,694,250<br>C1 03/11 van (VG-02A, FD và NRD, MD có EI bọc, miệng gio / AAG): 3,403,135,850 |
| 2 KL ĐH TG.xlsx | 150,626,100 (74 dòng) | 277,925,500 (74 dòng) | (chưa có trong baseline — giá trị lúc `590365b`): 151,747,100<br>63d9691: 150,626,100<br>`7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 276,804,500<br>`eeebc61` 03/11 Agent 00B chỉ đọc, Reader core, nhiều hộp, giữ giá đối tác: 277,925,500 |
| 260910_MKS_BoQ goi thau (BP05a)_Tach cac thap-ham-canh quan (1).xlsx | 9,423,244,700 (124 dòng) | 15,411,128,900 (124 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 11,891,867,500<br>`eeebc61` 03/11 Agent 00B chỉ đọc, Reader core, nhiều hộp, giữ giá đối tác: 15,411,128,900 |
| 26BDCC09-3.VGCG-Lan 1.xlsx | 480,488,100 (51 dòng) | 485,888,100 (51 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 485,888,100 |
| BDKSCT-1.OGIO-26-09-11-Lan 1 - Copy.xlsx | — | 35,971,775,546 (71 dòng) | (chưa có trong baseline — giá trị lúc `590365b`): 42,858,598,401<br>`7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 35,971,775,546 |
| BDKSCT-3.VGCG-26-09-11-Lan 1 - Copy.xlsx | — | 9,013,966,800 (104 dòng) | (chưa có trong baseline — giá trị lúc `590365b`): 6,063,090,300<br>`7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 9,013,966,800 |
| BDKSCT-3.VGEI-26-09-11-Lan 1.xlsx | — | 12,735,629,800 (76 dòng) | (chưa có trong baseline — giá trị lúc `590365b`): 12,577,792,800<br>`7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 12,735,629,800 |
| BG - SLand- BĐ  2026.10.09 - C3Z3 - ĐẶT HÀNG ỐNG GIÓ CĂN HỘ THÁP (đặt ngoài).xlsx | 47,979,700 (352 dòng) | 50,637,100 (351 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 50,749,900<br>`7ebdc48` 03/11 Zét thiếu E, van MDF, MFD + Mã SP: 50,637,100 |
| BG DT C08-  Ago.xlsx | 7,490,390,200 (447 dòng) | 7,357,791,200 (447 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 7,490,990,200<br>`f31a9d4` 03/11 việc A/B + 4 lỗi cửa gió (chỉ lấy hộp, cột STT...): 7,357,791,200 |
| BG ĐHKK-TAHK 12.10 (DT).xlsx | 9,142,359,900 (289 dòng) | 7,247,223,160 (289 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 7,230,977,160<br>C1 03/11 van (VG-02A, FD và NRD, MD có EI bọc, miệng gio / AAG): 7,247,223,160 |
| BG01_SLAND_TBCONS_HAUSDALAT_MIENG GIO VAN GIO_07102026.xlsx | 2,122,938,800 (188 dòng) | 3,397,213,800 (185 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 2,126,470,000<br>`f31a9d4` 03/11 việc A/B + 4 lỗi cửa gió (chỉ lấy hộp, cột STT...): 3,397,213,800 |
| BGĐP - Hoàng Quân - D4, D5 - Ống gió - 20260401.xlsx | 3,695,725,900 (58 dòng) | 2,911,578,900 (58 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 2,911,578,900 |
| BOQ TAHK HH1B HH1A 10102026.xlsx | 8,725,605,000 (408 dòng) | 7,746,734,700 (442 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 7,746,734,700 |
| BOQ THONG GIO.xlsx | 53,652,600 (23 dòng) | 53,887,200 (23 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 53,887,200 |
| BOQ_ANH_KHACH_01.xlsx | — | 121,446,200 (34 dòng) | (chưa có trong baseline — giá trị lúc `590365b`): 89,627,300<br>C1 03/11 van (VG-02A, FD và NRD, MD có EI bọc, miệng gio / AAG): 108,663,600<br>C3 03/11 mã IS → LCCT, MPRD: 121,446,200 |
| Báo giá Cổ bi.xlsx | 4,127,056,320 (183 dòng) | 3,606,998,400 (179 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 3,156,952,200<br>`7ebdc48` 03/11 Zét thiếu E, van MDF, MFD + Mã SP: 3,599,768,400<br>`f31a9d4` 03/11 việc A/B + 4 lỗi cửa gió (chỉ lấy hộp, cột STT...): 3,606,998,400 |
| Báo giá Thanh Liệt gửi NCC.xlsx | 2,931,339,180 (284 dòng) | 5,322,641,300 (336 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 5,322,641,300 |
| DNBG VGCG.xlsx | — | 1,241,154,420 (83 dòng) | (chưa có trong baseline — giá trị lúc `590365b`): 1,226,938,530<br>`7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 1,241,154,420 |
| EZLAND_KL MIỆNG GIÓ.UP.xlsx | 4,787,569,900 (175 dòng) | 4,799,569,900 (175 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 4,799,569,900 |
| Haus_Dalat_BOQ_MEP (NCC).xlsx | 12,577,300,705 (233 dòng) | 11,468,568,201 (194 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 12,641,380,422<br>`f31a9d4` 03/11 việc A/B + 4 lỗi cửa gió (chỉ lấy hộp, cột STT...): 11,468,568,201 |
| KL DHTG.xlsm | 6,571,381,400 (146 dòng) | 4,933,613,800 (128 dòng) | `2c99dba` 02/11 thiết bị cấp nước → không báo: 6,485,689,400<br>`7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 4,933,613,800 |
| KL ong gio cap va hut.xlsx | 256,996,650 (90 dòng) | 322,098,100 (108 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 322,098,100 |
| KL Điều hòa.xlsx | 208,785,900 (75 dòng) | 334,782,100 (75 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 334,782,100 |
| Khối lượng VGCG tòa CC17 (dự tính theo BTVTK 20260922) (1).xlsm | — | 1,194,770,000 (54 dòng) | (chưa có trong baseline — giá trị lúc `590365b`): 1,194,770,000 |
| LỆNH SẢN XUẤT NAM VIỆT ĐƠN SỐ 43.xlsx | 923,434,400 (22 dòng) | 681,661,400 (22 dòng) | `7ebdc48` 03/11 Zét thiếu E, van MDF, MFD + Mã SP: 681,661,400 |
| MPQ ( BAT) OG-056T2810 28.10.xlsx | 6,340,763,500 (375 dòng) | 6,341,363,500 (375 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 6,341,363,500 |
| NOVH_CT0102.HA_DHTG.xlsx | 7,614,742,635 (822 dòng) | 7,789,833,135 (822 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 7,789,833,135 |
| NOVH_CT0304.HA_DHTG.xlsx | 6,283,628,388 (988 dòng) | 6,424,048,588 (988 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 6,424,048,588 |
| NOVH_E1_DHTG.xlsx | 3,514,805,321 (387 dòng) | 3,571,187,521 (387 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 3,571,187,521 |
| NOVH_E2_DHTG.xlsx | 3,529,737,311 (312 dòng) | 3,591,461,411 (312 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 3,591,461,411 |
| NOVH_U_DHTG.xlsx | 2,542,629,153 (306 dòng) | 2,580,390,753 (306 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 2,580,390,753 |
| NOXH Dãn dân phố cổ HN.xlsx | 641,724,800 (62 dòng) | 648,481,800 (62 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 648,481,800 |
| NV- DỰ ÁN NHIÊN LIỆU- VAN, ỐNG GIÓ.xlsx | 31,562,200 (34 dòng) | 32,770,200 (34 dòng) | `eeebc61` 03/11 Agent 00B chỉ đọc, Reader core, nhiều hộp, giữ giá đối tác: 32,770,200 |
| Nếnh-BOQ PCCC 2026.10.03 -OG.xlsx | 1,762,008,400 (89 dòng) | 1,425,788,700 (89 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 1,425,788,700 |
| Q.26.0035.Penta- SWIND Báo giá Thanh Liệt gửi NCC.xlsx | — | 5,358,632,540 (337 dòng) | (chưa có trong baseline — giá trị lúc `590365b`): 5,355,070,140<br>`7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 5,358,632,540 |
| Q.26.0036 Penta- Swind Báo giá Cổ bi.xlsx | — | 3,624,882,300 (183 dòng) | (chưa có trong baseline — giá trị lúc `590365b`): 4,127,056,320<br>`7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 3,156,952,200<br>`7ebdc48` 03/11 Zét thiếu E, van MDF, MFD + Mã SP: 3,617,652,300<br>`f31a9d4` 03/11 việc A/B + 4 lỗi cửa gió (chỉ lấy hộp, cột STT...): 3,624,882,300 |
| TONG HOP HVAC.xlsx | — | 13,193,999,110 (691 dòng) | (chưa có trong baseline — giá trị lúc `590365b`): 168,872,320,660<br>`2c99dba` 02/11 thiết bị cấp nước → không báo: 17,582,751,660<br>`7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 13,185,623,010<br>`7ebdc48` 03/11 Zét thiếu E, van MDF, MFD + Mã SP: 13,184,240,110<br>C1 03/11 van (VG-02A, FD và NRD, MD có EI bọc, miệng gio / AAG): 13,193,999,110 |
| TONG_HOP_KHOI_LUONG_DHKK.xlsx | 176,133,983,294 (503 dòng) | 20,152,200,310 (501 dòng) | `2c99dba` 02/11 thiết bị cấp nước → không báo: 27,782,251,894<br>`7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 20,152,200,310 |
| Tong_hop_PLH_MEP_Goi1.xlsx | — | 3,355,472,400 (236 dòng) | (chưa có trong baseline — giá trị lúc `590365b`): 16,486,548,200<br>`2c99dba` 02/11 thiết bị cấp nước → không báo: 3,930,404,600<br>`7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 3,355,472,400 |
| Xin giá cửa dự án CAND.xlsx | 53,890,322,423 (580 dòng) | 218,274,464,858 (707 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 218,274,154,458<br>`7ebdc48` 03/11 Zét thiếu E, van MDF, MFD + Mã SP: 42,507,947,224<br>`eeebc61` 03/11 Agent 00B chỉ đọc, Reader core, nhiều hộp, giữ giá đối tác: 218,274,154,458<br>C1 03/11 van (VG-02A, FD và NRD, MD có EI bọc, miệng gio / AAG): 218,274,464,858 |
| cửa gió 26102026.xlsx | 245,388,700 (29 dòng) | 250,230,700 (29 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 250,230,700 |
| newstart bắc giang.xlsx | 157,656,500 (31 dòng) | 161,662,800 (31 dòng) | `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 161,662,800 |
| swind02111.xlsx | — | 147,469,200 (39 dòng) | (chưa có trong baseline — giá trị lúc `590365b`): 146,269,200<br>`7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15: 147,469,200 |

## Lệch lớn (> 30%)

- **14. Ống thông gió và pk - Minh Triết.xlsx**: 1,639,422,000 → 3,403,135,850 (+108%) — `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15; C1 03/11 van (VG-02A, FD và NRD, MD có EI bọc, miệng gio / AAG)
- **2 KL ĐH TG.xlsx**: 150,626,100 → 277,925,500 (+85%) — (chưa có trong baseline — giá trị lúc `590365b`); 63d9691; `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15; `eeebc61` 03/11 Agent 00B chỉ đọc, Reader core, nhiều hộp, giữ giá đối tác
- **260910_MKS_BoQ goi thau (BP05a)_Tach cac thap-ham-canh quan (1).xlsx**: 9,423,244,700 → 15,411,128,900 (+64%) — `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15; `eeebc61` 03/11 Agent 00B chỉ đọc, Reader core, nhiều hộp, giữ giá đối tác
- **BG01_SLAND_TBCONS_HAUSDALAT_MIENG GIO VAN GIO_07102026.xlsx**: 2,122,938,800 → 3,397,213,800 (+60%) — `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15; `f31a9d4` 03/11 việc A/B + 4 lỗi cửa gió (chỉ lấy hộp, cột STT...)
- **Báo giá Thanh Liệt gửi NCC.xlsx**: 2,931,339,180 → 5,322,641,300 (+82%) — `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15
- **KL Điều hòa.xlsx**: 208,785,900 → 334,782,100 (+60%) — `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15
- **TONG_HOP_KHOI_LUONG_DHKK.xlsx**: 176,133,983,294 → 20,152,200,310 (-89%) — `2c99dba` 02/11 thiết bị cấp nước → không báo; `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15
- **Xin giá cửa dự án CAND.xlsx**: 53,890,322,423 → 218,274,464,858 (+305%) — `7cdc069` 02/11 rule Kỹ thuật BDKSCT, LCCT/G4 trong ống, tháo lắp ×1.15; `7ebdc48` 03/11 Zét thiếu E, van MDF, MFD + Mã SP; `eeebc61` 03/11 Agent 00B chỉ đọc, Reader core, nhiều hộp, giữ giá đối tác; C1 03/11 van (VG-02A, FD và NRD, MD có EI bọc, miệng gio / AAG)

## Đề xuất
Mọi lệch quy được về commit / bước đã duyệt (cùng các thay đổi đã cập nhật vào baseline mặc định). Lưu baseline `--include-duct` theo bản hiện tại sau khi User rà các file lệch lớn.
