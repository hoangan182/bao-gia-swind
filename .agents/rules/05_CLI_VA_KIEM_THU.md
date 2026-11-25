> Chuyển nguyên văn từ AGENTS.md ngày 2026-11-24. AGENTS.md giữ bản tóm tắt.

### Bảng tham số CLI đầy đủ của `src/swind_master_runner.py`:
- `--non-interactive`: **(Bắt buộc khi AI chạy)** Chạy tự động hoàn toàn (Headless mode), không chờ nhập từ bàn phím.
- `--auto-accept`: **(Bắt buộc khi AI chạy)** Tự động đồng ý gợi ý phân loại mặt hàng của Agent 02.
- `--sheets "Sheet1,Sheet2"`: Chỉ định danh sách Sheet kỹ thuật cần xử lý (ngăn cách bằng dấu phẩy). Mặc định: Tự động dò tất cả Sheet kỹ thuật HVAC.
- `--only-cua-van`: Chỉ lọc và báo giá **Cửa gió & Van gió** (`CUA_GIO`, `VAN_GIO`), loại bỏ Ống gió và Hàng thương mại mua ngoài.
- `--motor-brand <BELIMO|KLB|HONEYWELL>`: Chỉ định hãng động cơ van theo yêu cầu (Mặc định: `BELIMO` nếu BOQ không ghi rõ).
- `--mprd-motor-price <số_tiền_VNĐ>`: Ghi đè giá gốc **động cơ van xả áp MPRD** (cả 3 mã MPRD 5/10/20Nm) cho dự án đang chạy, **chỉ áp cho MPRD** — không đụng MFD/MD, không sửa Master Data (VD: `--mprd-motor-price 4000000`).
- `--mprd-onoff`: **(Không còn tác dụng từ 2026-11-17 — ON/OFF thường là mặc định)** Van xả áp MPRD dùng **động cơ Belimo ON/OFF thường** (như van MD: mã `MAT-ACTUATOR-BELIMO-{5/10/20}NM`, mô-men theo cùng rule) thay động cơ tuyến tính; ghi chú *"Động cơ van gió Belimo ON/OFF {nm}, 230V"* (User yêu cầu 2026-11-11, dự án KL TB+VT CT2). Khi bật cờ này, `--mprd-motor-price` không còn tác dụng — đổi giá bằng `--motor-price`.
- `--md-shaft-only`: Van MD báo **trục chờ** (không gồm động cơ) cho dự án đang chạy — bỏ động cơ khỏi BOM, ghi chú *"Van MD tôn mạ kẽm, trục chờ lắp động cơ (không gồm động cơ)"*; số modul vẫn theo hãng `--motor-brand` (User yêu cầu 2026-11-03, dự án 150-YCVT LUXQV).
- `--motor-price <số_tiền_VNĐ>`: Rẽ nhánh áp đơn giá gốc động cơ tùy chỉnh riêng cho dự án đang chạy (VD: `--motor-price 2300000`), tuyệt đối không sửa giá gốc trong Master Data chuẩn.
- `--mfd-model <1.01|1.02|1.03|1.04|1.05>`: Chỉ định mã đốt van MFD theo yêu cầu (`1.01`: Belimo BFN24 EI120, `1.02`: Belimo FSLF24V EI90 [Mặc định], `1.03`: KLB 5Nm EI90, `1.04`: Honeywell MS4609 EI60, `1.05`: Belimo BFN24 EI120).
- `--dual-options`: Tính đồng thời 2 phương án Đơn cánh và Đa cánh (Mặc định: Báo giá chuẩn theo BOQ).
- `--merge-sheets`: Gộp tất cả các sheet vào 1 file duy nhất (Mặc định: Tách riêng từng sheet).
- `--strict`: Không xuất file báo giá nếu còn lỗi chặn (dòng có KL chưa có giá, sheet bóc tách lỗi, QA_REJECTED). Mặc định: vẫn xuất file nhưng in `⛔ BẢN NHÁP — CHƯA HOÀN CHỈNH` và trả mã thoát `2`.
- `--override "<Dòng>:k=v,...;..."`: Ghi đè nhanh theo dòng BOQ (`w,h,d,l,thickness,qty,ref_price,skip`, `ok=1` = duyệt dòng báo theo MẶC ĐỊNH — bỏ tô vàng / hỏi lại, `loai=<mã>` = chỉ rõ loại hàng như cột Model, VD `loai=MD` / `MFD` / `FD` / `SD` / `SDG`; Việc 3, 2026-11-25). BOQ nhiều sheet bắt buộc ghi tên sheet: `--override "Tên Sheet!7:w=600,h=600"`. **Nhiều khóa cho cùng 1 dòng phải gộp trong MỘT đoạn**, VD `"Sheet!204:ok=1,loai=MD"` — 2 đoạn cùng dòng ghi đè lẫn nhau. Dòng SL = 0 không tô vàng, không liệt kê ở Kiểm soát cuối (MẶC ĐỊNH → hỏi lại).
- `--title-wins "<Sheet>!<dòng>,<dòng>;<Sheet2>!<dòng>"`: User duyệt dòng **Loại 4** (dòng không rõ loại hàng dưới Title loại hàng — quy tắc 1c) báo theo Title cha; tương đương `--override "<Sheet>!<dòng>:title=1"`.
- `--duct-formula <mpq|og_mb|both>`: Bộ công thức ống gió (`mpq` mặc định = BG PKV chuẩn; `og_mb` = diện tích m² theo ÔG MB; `both` = xuất cả 2, bản m² có hậu tố `_THEO_M2_OG_MB`).
- `--include-canvas`: Báo giá cả Khớp nối mềm / Canvas (Mặc định: Swind **KHÔNG** báo giá canvas).
- `--include-duct`: Cho phép báo giá **Ống gió & phụ kiện ống (`ONG_GIO`)** (Mặc định: Hệ thống **KHÔNG** báo giá ống gió, chỉ báo khi User yêu cầu rõ). `--duct-formula og_mb|both` tự động bật cờ này.
- `--duct-only`: **Chỉ báo Ống gió & phụ kiện ống** (tự bật `--include-duct`): bỏ cửa / van / tiêu âm / canvas / ống mềm / hàng thương mại và dòng ống kèm LCCT / lọc G4 (không báo cả phần ống lẫn phần LCCT); giữ hộp gió. Chốt chặn theo **loại ống do Agent 04 xác định**: chỉ giữ ống thẳng / cút / côn / chân rẽ / tê / zét / bịt đầu / chuyển vuông-tròn / hộp gió, loại `CANVAS*`, `FLEX_DUCT`, `VENTCAP`, `SILENCER*` kể cả khi nhóm là `ONG_GIO`; console in danh sách loại dòng được báo (User chốt 2026-11-19, GMS TASEOC). Không đổi rule mặc định của các cờ khác.
- `--duct-uplift <N>`: Cộng thêm N% vào đơn giá ống gió & phụ kiện (làm tròn 100đ) — điều kiện riêng từng dự án (VD `--duct-uplift 7`). `--duct-coating <Z18>`: nối ", tôn Z18" vào ghi chú dòng ống. Không tiêu âm / canvas.
- `--lined-duct-as-duct`: dòng *"Ống gió ... ( kèm tiêu âm trong dày 50mm)"* báo **như ống gió thường** (giá ống kỳ hiện hành, nhận `--duct-uplift`), không tính tiêu âm `TA-VUONG`; mặc định vẫn là tiêu âm (OG-04). Dùng kèm `--include-duct` (User chốt 2026-11-21, dự án Ống thông gió).
- `--duct-steel-brand "<tên>"`: ghi chú ống gió / tiêu âm và dòng vật liệu cuối BG ghi `tôn <tên>` thay `Hoa Sen` (VD `--duct-steel-brand "Hòa Phát"`, dự án tien luong moi thau V1_18t11, 2026-11-20); không đổi giá.
- `--duct-ei-note "30=<ghi chú>|45,60=<ghi chú>"`: ghi đè **ghi chú cấu tạo ống gió EI** cho 1 dự án (mặc định lấy bảng `pricing_constants.json -> ong.ghi_chu_cau_tao_ei`).
- `--price-zero-qty`: dòng Cửa/Van **KL trống / 0** vẫn ghi **Model + Đơn giá + Ghi chú** (SL = 0, không cộng tiền), kể cả sheet có cột `Tổng khối lượng` / phiếu đặt hàng — mặc định các sheet đó bỏ dòng KL=0 (User yêu cầu 2026-11-24, dự án Cửa gió NTL; `SwindBOQParser.keep_zero_qty`).
- `--include-flex-duct`: Cho phép báo giá **Ống gió mềm (`ONG_MEM`)** (Mặc định: Hệ thống **KHÔNG** báo giá ống mềm, chỉ báo khi có yêu cầu).
- `--include-box`: Cho phép tính và báo giá thêm **Hộp gió (`PLENUM_BOX` theo công thức sheet `BG PKV`)** cho các cửa gió kèm hộp (Mặc định: Chỉ báo giá cửa gió và ghi chú `. Không tính box do nhà thầu tự thi công`, chỉ cộng thêm hộp khi User yêu cầu).
- `--spec-priority <name|note>`: Chọn cột ưu tiên khi `Cột Tên` và `Cột Ghi chú/Spec` mâu thuẫn (`name` [Mặc định]: khóa chủng loại theo Cột Tên; `note`: ưu tiên theo Cột Ghi chú/Spec).

### ♻️ LUỒNG RẼ (ON-DEMAND) — NHẶT GIÁ TỪ BÁO GIÁ CŨ (`Agent 10`)
Chỉ dùng khi User yêu cầu rõ *"nhặt giá từ báo giá cũ sang BOQ, dòng nào chưa có mới báo"* (không đổi rule luồng chính). Agent 10 tự gọi `swind_master_runner.py` cho phần còn lại — cờ runner truyền thẳng vào lệnh:
```bash
./venv/bin/python src/agent_10_old_quote_carrier.py "<BOQ.xlsx>" --old-quote "<BG_cu.xlsx>" --old-sheets "<Sheet ưu tiên>,<Sheet 2>" [--accept-review] [--accept-converted] [--dry-run] [cờ runner]
```
- Mặc định chỉ nhặt dòng **khớp chắc chắn**; nhóm `Cần xác nhận` / `BG cũ đã đổi loại` (VD FD → *Chuyển sang MFD*) và dòng *nhiều đơn giá trong BG cũ* → **AI bắt buộc hỏi lại User**. Chưa rõ sheet nào → bỏ `--old-sheets` để liệt kê rồi hỏi User.
- Báo cáo cho User: dùng **Bảng tổng hợp của Agent 10** (giá cũ + báo mới), không dùng bảng tổng hợp runner (chỉ là phần báo mới). Chi tiết: [agent_10_old_quote_carrier_role.md](file:///Users/hoangan/work/PCCC/swind/.agents/roles/agent_10_old_quote_carrier_role.md).
- **Chạy qua skill `bao-gia-tu-bg-cu` (User chốt 2026-11-23, dự án 261123_HH3_RFQ):** trợ lý dẫn từng bước (chọn sheet BG cũ → ghép thử `--plan-json` → hỏi theo nhóm *kiểu nan / khác hộp gió / khác cấp EI / nhiều giá* → tuỳ chọn phần báo mới theo Model BG cũ → chạy `--decisions`), **nhớ quyết định theo dự án** ở `data/old_quote_memory/<mã dự án>.json` (không commit; khoá theo nội dung dòng, không theo số dòng) — báo lại chỉ hỏi dòng mới / dòng đổi. Combo (`VCD + FD`, `Louver + FD`...) chỉ khớp combo cùng loại; khác cấp EI / khác hộp gió không còn tự nhặt. Skill: [.agents/skills/bao-gia-tu-bg-cu/SKILL.md](file:///Users/hoangan/work/PCCC/swind/.agents/skills/bao-gia-tu-bg-cu/SKILL.md).

---

## 🛠️ QUY TẮC TỐC ĐA KHI KIỂM TRA / SỬA / THÊM CÔNG THỨC TÍNH (`03_FORMULA_INDEX.md` + `swind_item_inspector.py`)

Khi người dùng hỏi *"Sao mặt hàng X ra diện tích/giá như vậy?"* hoặc yêu cầu *"Điều chỉnh/thêm công thức tính cho phụ kiện/cửa/van Y"*:
1. **KHÔNG ĐỌC TOÀN BỘ FILE LỚN:** Các công thức trong `src/agent_04_bom_duct.py`, `src/agent_05_bom_damper.py`, `src/agent_06_bom_diffuser.py` và `src/agent_01_boq_extractor.py` đã được chia nhỏ thành từng hàm độc lập (15–115 dòng/hàm). Hãy tra bảng tọa độ dòng trong [`.agents/rules/03_FORMULA_INDEX.md`](file:///Users/hoangan/work/PCCC/swind/.agents/rules/03_FORMULA_INDEX.md) và chỉ gọi `read_file(Path, StartLine, EndLine)` đúng hàm cần sửa.
2. **DÙNG NGAY `src/swind_item_inspector.py` ĐỂ SOI VẾT CÔNG THỨC, TRA CỨU GIÁ HỆ THỐNG & ĐỊNH VỊ CODE TRONG 0.03 GIÂY** (xử lý trực tiếp trong RAM, không ghi file tạm, không cần viết script phụ):
   ```bash
   # Soi vết 1 hoặc nhiều mặt hàng / dải kích thước cùng lúc (0.04s):
   ./venv/bin/python src/swind_item_inspector.py "Cút 90 độ 800x400 tôn 0.75 ; Van MFD 1200x800 EI90"
   ./venv/bin/python src/swind_item_inspector.py "Van chặn lửa FD EI60" --sizes "400x200,600x400,800x600"

   # Tra cứu tức thì đơn giá vật tư, barem định mức, 53 mặt hàng chuẩn & từ khóa đã có trong hệ thống (0.03s):
   ./venv/bin/python src/swind_item_inspector.py --search "<từ_khóa_vật_tư_hoặc_sản_phẩm>"

   # Kiểm toán siêu tốc (0.5s, 1 lệnh duy nhất) toàn bộ file BOQ/Báo giá khi cần quét sai mã, xung đột Cột Tên vs Spec, hoặc kiểm tra bất thường giá (TUYỆT ĐỐI KHÔNG viết nhiều script Python nhỏ lẻ để đọc dò file Excel):
   ./venv/bin/python src/swind_item_inspector.py --audit-boq "<đường_dẫn_file.xlsx>" --sheet "<Tên_Sheet>" [--filter "<từ_khóa_hoặc_KT_hoặc_R...>"]

   # Đối chiếu trực tiếp giá & công thức trong 1 file Excel với dữ liệu chuẩn hệ thống Swind (0.2s):
   ./venv/bin/python src/swind_item_inspector.py --compare "<đường_dẫn_file.xlsx>" --sheet "<Tên_Sheet>"

   # Định vị tức thì bằng AST đúng File + Hàm + Số dòng (StartLine..EndLine sống) khi cần thêm yêu cầu mới (0.02s):
   ./venv/bin/python src/swind_item_inspector.py --locate "<chủ_đề_yêu_cầu_mới>"
   ```
   **Bảng "đã hiểu thế nào" (2026-11-24):** runner ghi `output/<Project>/internal_estimation/DECISION_TRACE.json` + `DECISION_REVIEW.md` và in mục `📋 [ĐÃ HIỂU THẾ NÀO]` — mỗi dòng báo giá ghi hệ thống hiểu loại hàng / kiểu / model dựa trên chữ nào. "Cần xem" = dòng hệ thống phải dùng giá trị mặc định hoặc chưa chắc; không đổi giá, không chặn báo giá.
   `swind_item_inspector.py "<mô tả>"` in thêm dòng `🧭 ĐÃ HIỂU` (và khóa `decisions` trong `--json`).
3. **TÁCH SUBAGENT SONG SONG (`invoke_subagent`) KHI VỪA SO SÁNH DỮ LIỆU LỚN VỪA THÊM YÊU CẦU MỚI:**
   - Khi người dùng yêu cầu đồng thời kiểm tra/so sánh nhiều bảng giá hoặc nhiều mặt hàng với dữ liệu hệ thống VÀ bổ sung yêu cầu mới chưa có trong hệ thống, hãy tách Subagent (`research` cho luồng chạy `--search` / `--compare` đối chiếu dữ liệu; Agent chính dùng `--locate` nhảy thẳng tới đúng hàm code/JSON để thêm yêu cầu mới) nhằm tránh đọc dò tuần tự.
4. **CHẠY KIỂM THỬ HỒI QUY TRƯỚC & SAU KHI SỬA CÔNG THỨC / BÓC TÁCH:**
   ```bash
   # 53 mặt hàng chuẩn (0.2s)
   ./venv/bin/python src/swind_item_inspector.py --self-test
   # End-to-End — MẶC ĐỊNH (User chốt 2026-11-24, thay "chỉ 50 BOQ gần nhất" 2026-11-11): TOÀN BỘ input/, CẢ 2 chế độ,
   # chạy song song (~80 giây thay vì ~40 phút). Mỗi chế độ so baseline riêng (default -> e2e_regression_baseline.json,
   # duct -> e2e_baseline_include_duct.json); --jobs N (mặc định số nhân CPU - 2). Runner trong E2E chạy với
   # SWIND_NO_LEARNING_WRITE=1 (không ghi file học). So tổng tiền & số dòng từng sheet với baseline.
   ./venv/bin/python src/swind_e2e_regression.py [--filter "<tên_file>"]
   # 1 chế độ: --modes default | --modes duct; cờ runner riêng (1 chế độ, baseline mặc định): --runner-args="--price-zero-qty";
   # N BOQ có báo giá gần nhất: --limit N
   # KIỂM THỬ THEO MẪU DÒNG (tầng 1 + 2, 2026-11-24 — thời gian tăng theo SỐ MẪU, không theo số file):
   # sửa RULE nhận diện / bộ phân loại / hằng số giá → --check (~3 giây) thay vì E2E toàn bộ; chỉ E2E đầy đủ các file bị ảnh hưởng.
   ./venv/bin/python src/swind_pattern_lab.py --build          # đọc file BOQ mới / đã đổi vào thư viện (output/_pattern_lab/, không commit)
   ./venv/bin/python src/swind_pattern_lab.py --check          # chạy lại theo mẫu, so ảnh chụp chuẩn → mẫu đổi / dòng / file + e2e_files.txt
   # TẦNG 3: E2E đầy đủ chỉ (file bị ảnh hưởng ∪ BỘ FILE CANH GÁC) — canh gác = ít file nhất phủ mọi rule kích hoạt (CG/OG/VG),
   # mọi loại kết quả / lý do lọc / gốc Model, mọi kiểu bố cục (loại cột, phiếu đặt hàng, cột/dòng ẩn, bảng phụ...): 19/100 file, ~21 giây
   ./venv/bin/python src/swind_e2e_regression.py --modes default,duct --files-from output/_pattern_lab/e2e_files.txt
   ./venv/bin/python src/swind_pattern_lab.py --canary         # xem bộ canh gác + rule CHƯA có file nào kiểm tới (canary_report.md)
   ./venv/bin/python src/swind_pattern_lab.py --set-baseline   # sau khi User duyệt thay đổi
   # Sửa phần ĐỌC CẤU TRÚC BOQ (header, cột / dòng ẩn, KL ở dòng khác, side table) → --build --force + E2E bộ canh gác,
   # trước khi chốt chạy E2E toàn bộ (mẫu dòng không bắt được lỗi bố cục cả file). Sửa form Excel → chạy thử 3–5 file.
   # Unit test các cơ chế kiểm soát (cổng chặn, QA giá trị, học từ khóa, hằng số giá)
   ./venv/bin/python -m unittest discover -s tests -p "test_swind_*.py"
   # Cập nhật tọa độ dòng trong .agents/rules/03_FORMULA_INDEX.md sau khi sửa code
   ./venv/bin/python src/swind_item_inspector.py --refresh-index
   ```
   *(Nếu chủ đích thay đổi đã được duyệt, cập nhật baseline: `swind_item_inspector.py --save-baseline` và `swind_e2e_regression.py --save-baseline`).*
   **E2E không còn mặc định đạt (User chốt 2026-11-03):** mọi file trong `input/` đều qua **kiểm bất biến** (không crash, có Bảng Tổng Hợp, không dòng KL thiếu giá, không QA_REJECTED, không `⚠️ [CẢNH BÁO SÓT DÒNG]`, Model không trái loại hàng của Tên — VD van bị ghép mã cửa `SDG + ...`) rồi mới so baseline. Trạng thái: `OK` (khớp baseline duyệt) / `INV-OK` (chưa có baseline duyệt — dự án mới hoặc baseline cũ sai trong `data/master_data/e2e_excluded_files.json`, chỉ đạt bất biến) / `DIFF` / `FAIL`. `--save-baseline` chỉ lưu file qua bất biến và không lưu lại dự án đã loại. Baseline làm giàu dần bằng dự án mới đã duyệt (`--filter "<tên>" --save-baseline`). Test bộ kiểm: `tests/test_swind_e2e_invariants.py`.
5. **HẰNG SỐ GIÁ CÔNG THỨC XƯỞNG (tôn/m², phụ kiện theo bậc kích thước van, tấm chống cháy, sơn, lưới, lọc G4, bảng giá ống theo độ dày...)** nằm tại `data/master_data/pricing_constants.json` (KHÔNG sửa số trong code):
   ```bash
   ./venv/bin/python src/tool_semantic_price_updater.py --list-constants van.vuong_phu_kien
   ./venv/bin/python src/tool_semantic_price_updater.py --constant van.ton_m2.bac_lon 330000   # lưu bản cũ vào data/master_data/prices/
   ```
6. **TỪ KHÓA TỰ HỌC (Agent 02):** Gợi ý tự động (`--auto-accept`, độ tin cậy ≥ 60%) chỉ áp cho lần chạy hiện tại và vào hàng chờ; duyệt vào từ điển sống bằng `./venv/bin/python src/agent_02_boq_reviewer.py --approve-pending [--list | --all]`. Lỗi gõ mã đã đoán (loại `TYPO`) cũng vào hàng chờ này; duyệt xong ghi vào `typo_rules.json` TY-01 (không ghi từ điển từ khóa); thêm trực tiếp: `agent_02_boq_reviewer.py --add-typo "fmd=mfd"`.
7. **QUY TRÌNH SỬA RULE BÓC TÁCH / NHẬN DIỆN (chống "rule chồng rule"):** trước khi sửa → `git log -S "<đoạn code>"` tìm commit sinh ra rule + quét `input/` tìm dự án gây ra → **rẽ nhánh theo điều kiện** để giữ đúng case cũ, chỉ xóa khi rule đã được xác nhận sai → ghi lý do + nguồn (ngày / dự án / người chốt) cạnh rule → chạy self-test + unit + E2E cả 2 baseline (mặc định & `--include-duct`), file nào lệch phải giải thích được. Mọi đường đọc file BOQ dùng Reader core `swind_utils` (rule bỏ cột/dòng ẩn chỉ ở 1 chỗ), cấm chèn/bịa nội dung vào BOQ. Kế hoạch: [KE_HOACH_TACH_AGENT_DOC_BOQ.md](file:///Users/hoangan/work/PCCC/swind/plan/KE_HOACH_TACH_AGENT_DOC_BOQ.md).

---

#### Cờ chưa có trong bảng (bổ sung 2026-11-24)
- `--allow-ei`: không còn tác dụng (ẩn khỏi `--help`); Swind tự động nhận diện EI theo BOQ.
- `--duct-ei <N>`: Điều kiện dự án: toàn bộ Ống gió & phụ kiện ống bọc chống cháy EI<N> (VD 60) và van FD báo có bọc. Dùng kèm `--include-duct`.
- `--duct-straight-only`: Dùng với `--fire-duct-only`: chỉ báo ống gió thẳng, bỏ phụ kiện ống (cút, côn, chân rẽ, chạc, Z, hộp...).
- `--fire-duct-only`: Chỉ báo Ống gió & phụ kiện thuộc mục `+ Đường ống gió ... chống cháy` của BOQ, bỏ ống thường (không cần `--include-duct`). Kèm `--duct-ei N` để báo bọc EI<N>.
- `--from-images`: Đọc trực tiếp ảnh khách gửi trong `input picture/` và chạy báo giá.
- `--neck-size`: Quy định kích thước cửa gió trong BOQ là kích thước cổ (Neck Size -> cộng thêm viền ra kích thước mặt).
- `--skip-fire-duct`: Dùng với `--include-duct`: bỏ Ống gió & phụ kiện thuộc mục `+ Đường ống gió ... chống cháy`, chỉ báo ống thường.

## Bánh cóc từ khóa & phạm vi import (2026-11-25)
- `tests/test_swind_keyword_guard.py`: đếm từ khóa loại hàng trong chuỗi `src/*.py` **phân biệt hoa/thường, theo ranh giới từ** (`has_obd` / `is_louver` không đếm; `"obd"` đếm), kể cả f-string; bỏ docstring / chú thích. Số đếm từng file **chỉ được giảm** so với `tests/fixtures/keyword_guard_baseline.json`. `--update` (từ chối nếu có số tăng) sau khi giảm; `--init` chỉ để tạo baseline lần đầu / đổi cách đếm — **không** dùng để hấp thụ từ khóa mới. Docstring đầu file nêu số còn lại hợp lệ theo file (HIỂN THỊ / KHÓA / đã khảo sát).
- `tests/test_swind_import_scope.py`: chặn `import` cục bộ trong hàm che tên import đầu file rồi dùng trước dòng import (`UnboundLocalError`; sự cố `--lined-duct-as-duct` + `decision_trace` 2026-11-25).

