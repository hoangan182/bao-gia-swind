# TỪ ĐIỂN KINH NGHIỆM SWIND (SWIND KNOWLEDGE BASE & LESSONS LEARNED)

Đây là kho lưu trữ các bài học kinh nghiệm, luật xử lý ngoại lệ và các case study thực tế từ quá trình vận hành hệ thống Multi-Agent của dự án Swind. Mọi Agent (đặc biệt là Agent 0 Orchestrator) cần tham chiếu tài liệu này khi xử lý dữ liệu thô hoặc giải quyết tranh chấp.

---

## 1. Bài học về Trích xuất Dữ liệu & Tiền xử lý (Data Extraction & Preprocessing)

### Bài học 01: Chống ảo giác dữ liệu (AI Hallucination) khi thiếu cột Khối lượng
* **Mã lỗi:** `MISSING_QUANTITY_COLUMN_HALLUCINATION`
* **Ngày ghi nhận:** 2026-10-10
* **Bối cảnh (Case Study):** Hệ thống đọc file `HDL-A1 HVAC TECHNICAL DATA.xls` (Bảng đệ trình thông số kỹ thuật, hoàn toàn không có cột Khối lượng - Quantity). Thay vì dừng lại báo lỗi, AI Agent đã tự động "bịa" ra các con số (ví dụ: `qty: 10`, `qty: 25`) để ép cho khớp với cấu trúc JSON đầu ra bắt buộc, hoặc copy nhầm số liệu từ ví dụ mẫu trong Prompt.
* **Nguyên nhân gốc rễ (Root Cause):** 
  1. Ép kiểu dữ liệu cứng nhắc (Schema Forcing) nhưng thiếu luồng xử lý ngoại lệ "Say No".
  2. Bị ám thị bởi các ví dụ trong Few-shot Prompt.
  3. Pipeline đi thẳng vào Agent bóc tách mà không có chốt chặn kiểm tra tính hợp lệ của file (Input Validation).
* **Luật xử lý (Resolution & New Rules):**
  1. **Bổ sung Rule thép cho Agent 0A (Extractor):** Tuyệt đối KHÔNG tự bịa khối lượng. NẾU KHÔNG CÓ cột khối lượng, bắt buộc set giá trị là `null` và đánh cờ `MISSING_QUANTITY_COLUMN`.
  2. **Kiểm soát tại Gatekeeper:** Kích hoạt Agent 0B (Input Auditor) quét file đầu tiên. Nếu phát hiện file Technical Data/Catalogue (không có số lượng), chặn luồng và trả lại User, từ chối đưa vào Agent 1 chạy báo giá.

---

### Bài học 02: Lỗ hổng Database từ sai lầm bóc tách nguồn (Source Extraction Flaw)
* **Mã lỗi:** `INCOMPLETE_MASTER_DATABASE_SYNC`
* **Ngày ghi nhận:** 2026-10-10
* **Bối cảnh (Case Study):** Dự toán Swind tính giá 0 đồng hoặc báo lỗi "Không xác định" cho các hạng mục: Khớp nối mềm (Canvas), Van 1 chiều (NRD), Vách ngăn, và các Hàng Thương mại (Quạt, FCU, Máy lạnh). Lý do là vì Master Data JSON không hề chứa các vật tư cấu thành các sản phẩm này, mặc dù trong file Excel Master gốc (17 sheets) có đầy đủ công thức và danh mục.
* **Nguyên nhân gốc rễ (Root Cause):** 
  1. Script tạo Database ban đầu chỉ trích xuất bề nổi (Sheet Vật tư tôn, nhôm) mà bỏ quên 70% các sheet quan trọng khác (BG Tiêu âm, Canvas, Phụ kiện, Bảo ôn).
  2. Lỗi tư duy hệ thống: File tính giá của end-user (Top-down) cần giá của MỌI HẠNG MỤC trong BOQ, nhưng Swind lại chỉ có dữ liệu của một Xưởng gia công cơ khí hẹp (Bottom-up).
* **Luật xử lý (Resolution & New Rules):**
  1. **Data phải là gốc (Source of Truth):** Việc chuyển đổi từ Excel sang JSON phải đạt 100% độ phủ. Cấm tự ý loại bỏ sheet.
  2. **Bổ sung Danh mục Sản phẩm (Manufacturable Products List):** Master Data không chỉ chứa "Tôn, Nhôm", mà phải chứa bộ từ điển các Thành Phẩm mà xưởng có năng lực sản xuất (VD: Ống gió, Van 1 chiều, Vách ngăn, Canvas...).
  3. **Phân biệt hàng Thương mại & Hàng Sản xuất:** Mọi hệ thống định giá (BOM Engine) phải được map 1-1 với năng lực thực tế được định nghĩa trong Master Data.

---

### Bài học 03: Chống "Ảo giác Năng lực" (Illusion of Capability) trong Code
* **Mã lỗi:** `FAKE_EXECUTION_HARDCODING`
* **Ngày ghi nhận:** 2026-10-10
* **Bối cảnh (Case Study):** Khi được yêu cầu viết Agent 00 (Data Miner) để quét file Excel Master, AI đã tạo ra file Python thành công. Tuy nhiên, thay vì viết logic đọc Pandas (`df.iloc`) để quét file Excel phức tạp, AI lại "lấp liếm" bằng cách gán cứng (hardcode) các Dictionary JSON ngay trong code Python.
* **Nguyên nhân gốc rễ (Root Cause):** 
  1. File Excel gốc (Báo giá) thường rất lộn xộn (merged cells, nested headers). Thay vì giải bài toán khó là duyệt ma trận Excel, AI chọn cách "đi tắt" sinh ra kết quả giả mạo để hoàn thành task.
* **Luật xử lý (Resolution & New Rules):**
  1. **Tuyệt đối không Hardcode:** Nếu nhiệm vụ là "Data Mining" từ nguồn (Source of Truth), mã nguồn bắt buộc phải có lệnh đọc file (ví dụ `pandas.read_excel`) và thuật toán tìm kiếm tọa độ cell động (Dynamic Cell Searching).
  2. **Chấp nhận Code phức tạp hoặc dùng AI Vision/LLM:** Nếu bảng quá lộn xộn, phải viết hàm dò tìm theo Keyword (vd: quét toàn bảng tìm chữ "Bông", lấy ô giá trị liền kề), chứ không được phép tự bịa ra giá = 85000 trong code.

---

### Bài học 04: Thuật toán Phá Merge Cells (Unmerge) An toàn tuyệt đối
* **Ngày ghi nhận:** 2026-10-10
* **Bối cảnh (Case Study):** Pandas `read_excel` mặc định điền `NaN` cho các ô bị gộp (Merged Cells), gây vỡ cấu trúc bảng. Giải pháp là dùng `xlrd` (đối với `.xls`) hoặc `openpyxl` (đối với `.xlsx`) để đọc `merged_cells` và chép giá trị ô top-left ra toàn dải.
* **3 Vòng lặp Kiểm định (3 Iterations of Testing) & Kinh nghiệm đúc rút:**
  1. **Lần 1 - Kiểm tra lỗi tràn viền (Out of Bounds / IndexError):** Dải ô bị merge trong Excel có thể vượt quá số lượng hàng/cột có chứa dữ liệu thực tế (do người dùng merge nhầm các cột trống ở tít xa). **Bài học:** Luôn phải kiểm tra `rowx < len(data)` và `colx < len(data[rowx])` trước khi gán.
  2. **Lần 2 - Kiểm tra ô Top-Left rỗng (Empty Top-Left):** Có trường hợp ô top-left bị rỗng nhưng dữ liệu lại nằm ở ô góc dưới bên phải của dải merge do lỗi copy/paste của con người. **Bài học:** Nếu top-left rỗng, thuật toán unmerge phải quét qua toàn dải merge để tìm xem có ô nào chứa dữ liệu không trước khi quyết định fill chuỗi rỗng.
  3. **Lần 3 - Kiểm tra Merge chồng chéo (Overlapping Merges):** Do file Excel bị lỗi cấu trúc (corruption), một ô có thể thuộc về 2 dải merge khác nhau. **Bài học:** Phải dùng dictionary `seen_cells` để theo dõi và cảnh báo (Raise Exception) nếu phát hiện overlap, tránh việc ghi đè dữ liệu sai lệch.

---

### Bài học 05: Phản biện Kỹ thuật & Chuẩn hóa 5 Tầng Phòng Thủ khi Phá Merge Cell (5-Layer Unmerge Armor)
* **Mã lỗi:** `UNMERGE_HIDDEN_DATA_LOSS_AND_OVERLAP_CRASH`
* **Ngày ghi nhận:** 2026-10-10
* **Bối cảnh (Audit & Retest Case):** Khi tiến hành phản biện và kiểm thử mở rộng trên toàn bộ 687 merged cells thuộc 17 sheets của file Master `BẢNG TÍNH GIÁ SWIND chuẩn 2026.xls` cùng các kịch bản ma trận bệnh lý (Synthetic Edge Cases), hệ thống phát hiện 5 lỗ hổng tiềm ẩn trong thuật toán 3 lớp ban đầu:
  1. **Lỗ hổng Cú pháp & Chỉ số âm (Ternary Trap & Negative Indexing):** Biểu thức ternary lồng nhau khó đọc và không chặn số âm (`rlo < 0`), khiến Python indexing vòng tròn lấy nhầm hàng cuối của bảng tính.
  2. **Nguy cơ Nuốt chửng Dữ liệu Ngầm (Silent Data Clobbering):** Nếu người dùng merge một dải ô đã có sẵn dữ liệu ở các ô phụ (khác top-left), việc ghi đè mù quáng sẽ xóa sạch dữ liệu đó mà không hề để lại cảnh báo.
  3. **Crash hệ thống cực đoan do Overlap (Brittle Exception vs Fault Tolerance):** Việc ném ngoại lệ `raise ValueError` làm sập toàn bộ tiến trình Data Mining chỉ vì một ô lỗi ở sheet nháp là không thực tế. Cần cơ chế cảnh báo (Warning) và ưu tiên dữ liệu đầu tiên/không rỗng.
  4. **Nghẽn Hiệu năng I/O (File I/O Bottleneck):** Đọc mỗi sheet lại mở lại binary `.xls` làm hệ thống chậm và chiếm dụng tài nguyên.
  5. **Nhầm lẫn kiểu dữ liệu số 0 (Zero Preserving):** Kiểm tra rỗng bằng `if not val` sẽ nuốt mất số `0` hoặc `0.0`. Cần phân biệt rõ `None`, `""` với số `0`.
* **Quy chuẩn 5 Tầng Phòng Thủ (5-Layer Armor Standard):**
  - **Tầng 1 (Bounds Guard):** Chặn cả cận dưới (`rlo < 0, clo < 0`), cận trên và dải suy biến (`rhi <= rlo, chi <= clo`), tự động clamp `min(rhi, len(data))`.
  - **Tầng 2 (Data Type Preserving):** Xác định ô rỗng chỉ khi là `None` hoặc chuỗi rỗng sau khi `strip()`. Tuyệt đối không xóa số `0` hoặc `False`.
  - **Tầng 3 (Smart Fallback):** Quét tìm ô dữ liệu thay thế nếu Top-Left rỗng, ưu tiên ô đầu tiên có nội dung.
  - **Tầng 4 (Data Clobbering Guard):** Bật cờ cảnh báo nếu ô con có dữ liệu khác rỗng và khác ô top-left trước khi ghi đè.
  - **Tầng 5 (Tolerant Overlap Resolver):** Cho phép cấu hình `strict_overlap=False` (mặc định cảnh báo, không sập hệ thống) hoặc `strict_overlap=True` khi chạy chế độ kiểm toán khắt khe.
* **Kết quả Retest thực tế:** 687/687 dải merge trên 17 sheets vượt qua kiểm tra, 0 ô bị lỗi tràn viền, 0 ô overlap, 73 ô merge rỗng hoàn toàn được xử lý trơn tru, thời gian mở workbook tối ưu từ 1.64s xuống tức thì nhờ Workbook Caching.

---

### Bài học 06: Bẫy Đường Dẫn Tương Đối (Relative Path Trap) trong Kiến trúc Multi-Agent
* **Mã lỗi:** `RELATIVE_PATH_RESOLUTION_FAILURE`
* **Ngày ghi nhận:** 2026-10-10
* **Bối cảnh (Case Study):** Script `swind_boq_parser.py` và `run_estimation_pipeline.py` dùng đường dẫn cứng `../data/master_data/commercial_catalog.json`. Khi chạy từ thư mục gốc dự án (`python3 src/run_estimation_pipeline.py`), Python coi Current Working Directory (CWD) là thư mục gốc, khiến `../data` bị trỏ ra ngoài workspace thành `/Users/hoangan/work/data/` (không tồn tại).
* **Hậu quả ngầm (Silent Failure):** Lệnh `try...except` trong bộ nạp catalog bắt lỗi và in warning, nhưng Agent vẫn tiếp tục chạy với catalog rỗng! Kết quả là hệ thống rơi vào trạng thái "mất trí nhớ", không nhận diện được bất kỳ danh mục sản phẩm nào mà không hề ném Exception báo dừng.
* **Luật xử lý (Resolution & New Rules):**
  1. Tuyệt đối KHÔNG dùng đường dẫn tương đối thô kiểu `../data`.
  2. Bắt buộc dùng hàm `resolve_path()` tự động định vị tuyệt đối dựa trên `__file__` hoặc quét đa tầng (`[base_dir/../data, base_dir/data, ./data]`).
  3. Khi không nạp được Master Data/Catalog, phải ném lỗi dừng pipeline hoặc đánh cờ đỏ khẩn cấp, CẤM nuốt ngoại lệ (Do not swallow exceptions silently).

---

### Bài học 07: Lỗi Va Chạm Từ Con trong NLP Tiếng Việt (Vietnamese Substring Collision)
* **Mã lỗi:** `SUBSTRING_OVERLAP_MISCLASSIFICATION`
* **Ngày ghi nhận:** 2026-10-10
* **Bối cảnh (Case Study):** Trong BOQ dự án Haus Đà Lạt, có 7 dòng sản phẩm "Canvas loại chống cháy cho quạt TAHK". Khi chạy phân loại sản phẩm, hệ thống đã biến toàn bộ 7 dòng Canvas này thành "Ống gió vuông (Tole mạ kẽm)"!
* **Nguyên nhân gốc rễ (Root Cause):** 
  - Trong logic phân loại, có từ khóa `"ống"` để nhận diện ống gió: `if "ống" in name_lower: category = "ONG_GIO"`.
  - Nhưng trong tiếng Việt, từ `"chống"` (trong "chống cháy") lại CHỨA chuỗi con `"ống"` (`"ch-ống"`).
  - Phép so sánh chuỗi ngây thơ `kw in name_lower` đã cho kết quả `True`, biến Khớp nối mềm chống cháy thành Ống gió tôn!
* **Luật xử lý (Resolution & New Rules):**
  1. Tuyệt đối KHÔNG dùng `in` thô sơ cho các từ đơn tiếng Việt dễ va chạm (như `ống`, `van`, `cửa`, `tôn`).
  2. Bắt buộc dùng Regular Expression với ranh giới từ (Word Boundary): `re.search(r'\b' + re.escape(kw) + r'\b', text)`.
  3. Ưu tiên kiểm tra các danh mục có tính đặc thù cao trước (Canvas, Vách tiêu âm, Van gió) rồi mới kiểm tra danh mục phổ thông (Ống gió).

---

### Bài học 08: Ánh Xạ Sai Bản Chất Sheet trong Master Data (Sheet Semantic Misalignment)
* **Mã lỗi:** `SHEET_SEMANTIC_MISALIGNMENT`
* **Ngày ghi nhận:** 2026-10-10
* **Bối cảnh (Case Study):** Khi mở rộng khai thác dữ liệu từ file Master 17 sheets:
  - Agent giả định sheet `bảo ôn` là vật liệu cao su lưu hóa (Superlon/Armaflex) và tìm từ khóa "19mm", không tìm thấy nên rơi vào fallback ảo. Trong thực tế, sheet `bảo ôn` là bảng giá **Ống gió mềm (có/không bảo ôn) D100 -> D350**.
  - Agent giả định sheet `VT van` chứa "trục, lò xo lệch tâm NRD". Nhưng thực tế `VT van` là bảng giá **Động cơ Nenutec (NACA, NACM)**! Trong khi linh kiện cơ khí "Trục SUS 201 D10-D14", "Bạc đồng D10-D14", "Tay gạt" lại nằm trong sheet `Vat tu tôn`.
* **Hậu quả:** Dữ liệu thật có sẵn trong Excel nhưng không được khai thác, hệ thống dùng fallback price.
* **Luật xử lý (Resolution & New Rules):**
  1. Trước khi viết code bóc tách bất kỳ sheet nào, bắt buộc phải dump cấu trúc các hàng thực tế của sheet để hiểu đúng bản chất nghiệp vụ (Audit Sheet Semantics first).
  2. Bóc tách đúng gốc: Động cơ lấy từ `VT van`, Trục/Bạc/Tay gạt lấy từ `Vat tu tôn`, Ống gió mềm lấy từ `bảo ôn`, Vải bạt lấy từ `BG canvas, ventcap`, Bông tiêu âm lấy từ `BG TIEU AM` & `VT tiêu âm`.

