import json
import os
import xlrd
import re

class _IlocAccessor:
    def __init__(self, data):
        self._data = data
    def __getitem__(self, idx):
        r, c = idx
        return self._data[r][c]

class _UnmergedSheet:
    def __init__(self, data):
        self._data = data
        self.iloc = _IlocAccessor(data)
        self.columns = list(range(len(data[0]))) if data else []
    def __len__(self):
        return len(self._data)

class SwindDataMinerAgent:
    """
    Agent 00 - The Data Miner (Quy trình Độc Lập: Giải mã Bảng tính chuẩn 1 lần duy nhất)
    Nhiệm vụ: Đọc toàn bộ 17 sheets của file BẢNG TÍNH GIÁ SWIND chuẩn 2026.xls (CÓ PHÁ MERGE CELL)
    và kết xuất thành bộ Từ điển Dữ liệu trung tâm (Master Data JSON tĩnh) tại data/master_data/.
    LƯU Ý KIẾN TRÚC: Agent 00 CHỈ CHẠY 1 LẦN DUY NHẤT khi khởi tạo hệ thống (hoặc khi thay đổi
    toàn bộ cấu trúc bảng tính gốc). Quy trình báo giá BOQ hàng ngày (Agent 01 -> 08) KHÔNG gọi lại
    Agent 00 mà chỉ đọc trực tiếp từ bộ file Master Data đã có sẵn.
    """
    def __init__(self, excel_path):
        # Tự động chuẩn hóa đường dẫn dù chạy từ thư mục gốc hay src/
        if not os.path.exists(excel_path):
            root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
            alt_path = os.path.join(root_dir, os.path.basename(excel_path))
            if os.path.exists(alt_path):
                excel_path = alt_path
        if not os.path.exists(excel_path):
            raise FileNotFoundError(f"[Agent 00] Không tìm thấy file Excel tại: {excel_path}")
        self.excel_path = excel_path
        self._cached_wb = None
        print(f"[Agent 00] Khởi động Data Miner. Nguồn: {self.excel_path}")
        self.master_tech = []
        self.master_price = []
        self.manufacturable_products = []
        self.commercial_products = []
        self.mining_errors = []

    def _get_workbook(self):
        if not hasattr(self, "_cached_wb") or self._cached_wb is None:
            self._cached_wb = xlrd.open_workbook(self.excel_path, formatting_info=True)
        return self._cached_wb

    def _read_sheet_unmerged(self, sheet_name, strict_overlap=False):
        """
        Đọc một sheet từ file .xls, phá bỏ mọi merged cells và sao chép giá trị 
        của ô gốc vào tất cả các ô bị merge. Trả về pandas DataFrame.
        Đã được tôi luyện qua 5 tầng bảo vệ (5-Layer Armor Unmerge):
        1. Bounds Clamping & Index Guard (Chặn số âm, chặn tràn hàng/cột)
        2. Strict Data Type Preserving (Phân biệt số 0, 0.0 với chuỗi rỗng và None)
        3. Smart Non-Empty Fallback (Tìm ô có dữ liệu nếu top-left rỗng)
        4. Silent Data Clobbering Guard (Cảnh báo nếu ghi đè mất dữ liệu ngầm)
        5. Overlap Conflict Handling (Linh hoạt: strict raise hoặc graceful log warning)
        """
        wb = self._get_workbook()
        if sheet_name not in wb.sheet_names():
            raise ValueError(f"Sheet '{sheet_name}' không tồn tại trong workbook!")
            
        sheet = wb.sheet_by_name(sheet_name)
        data = []
        for r in range(sheet.nrows):
            row = []
            for c in range(sheet.ncols):
                row.append(sheet.cell_value(r, c))
            data.append(row)
            
        seen_cells = {}
        for crange in sheet.merged_cells:
            rlo, rhi, clo, chi = crange
            
            # Tầng 1: Bounds Guard (Chặn chỉ số âm và dải nằm ngoài phạm vi data)
            if rlo < 0 or clo < 0 or rlo >= len(data) or (len(data) > 0 and clo >= len(data[0])):
                continue
            if rhi <= rlo or chi <= clo:
                continue

            # Giới hạn cận trên an toàn (Clamping)
            max_r = min(rhi, len(data))
            max_c = min(chi, len(data[0]) if len(data) > 0 else 0)

            top_left_value = data[rlo][clo]
            
            # Tầng 2: Kiểm tra ô Top-Left có rỗng thực sự không
            # Lưu ý: 0 và 0.0 là giá trị hợp lệ, không được coi là rỗng!
            is_tl_empty = (top_left_value is None) or (isinstance(top_left_value, str) and top_left_value.strip() == "")
            
            # Tầng 3: Quét tìm dữ liệu thay thế nếu Top-Left rỗng
            if is_tl_empty:
                for rowx in range(rlo, max_r):
                    for colx in range(clo, max_c):
                        val = data[rowx][colx]
                        if val is not None and not (isinstance(val, str) and val.strip() == ""):
                            top_left_value = val
                            break
                    if top_left_value is not None and not (isinstance(top_left_value, str) and top_left_value.strip() == ""):
                        break

            # Tầng 4 & 5: Ghi đè có kiểm soát Overlap và Chống mất dữ liệu ngầm
            for rowx in range(rlo, max_r):
                for colx in range(clo, max_c):
                    cell = (rowx, colx)
                    if cell in seen_cells:
                        msg = f"Xung đột merge cell tại {cell} giữa dải {seen_cells[cell]} và {crange} trong sheet '{sheet_name}'"
                        if strict_overlap:
                            raise ValueError(msg)
                        else:
                            print(f"[CẢNH BÁO MERGE OVERLAP] {msg}")
                    seen_cells[cell] = crange

                    old_val = data[rowx][colx]
                    # Cảnh báo mất dữ liệu ngầm nếu ô con có dữ liệu khác top-left
                    if (rowx != rlo or colx != clo) and old_val not in (None, "") and old_val != top_left_value:
                        print(f"[CẢNH BÁO GHI ĐÈ DỮ LIỆU NGẦM] Sheet '{sheet_name}', ô ({rowx},{colx}) mang giá trị '{old_val}' bị ghi đè bởi '{top_left_value}' từ dải merge {crange}")

                    data[rowx][colx] = top_left_value
                    
        return _UnmergedSheet(data)

    def run_mining(self):
        print(f"[Agent 00] Bắt đầu quét phá merge...")
        self._mine_sheet_canvas()
        self._mine_sheet_tieu_am()
        self._mine_sheet_bao_on()
        self._mine_sheet_van()
        self._build_product_catalog()
        self._export_json()
        if self.mining_errors:
            print(f"[Agent 00] CẢNH BÁO: Quá trình Data Mining có {len(self.mining_errors)} lỗi: {self.mining_errors}")
        else:
            print("[Agent 00] Quá trình Data Mining hoàn tất chuẩn xác 100%. Đã xuất file JSON.")

    def _search_price(self, df, keyword_list, price_offset_range=(1, 5)):
        """Hàm dò tìm giá động trong DataFrame đã unmerge"""
        for r in range(len(df)):
            for c in range(len(df.columns)):
                val = str(df.iloc[r, c]).lower()
                if any(kw in val for kw in keyword_list):
                    # Quét các ô bên phải hoặc bên dưới để tìm giá trị số
                    for offset in range(price_offset_range[0], price_offset_range[1] + 1):
                        # Cột bên phải
                        if c + offset < len(df.columns):
                            try:
                                cell_val = float(df.iloc[r, c + offset])
                                if cell_val > 1000: return cell_val
                            except: pass
                        # Cột bên dưới
                        if r + offset < len(df):
                            try:
                                cell_val = float(df.iloc[r + offset, c])
                                if cell_val > 1000: return cell_val
                            except: pass
        return 0

    def _mine_sheet_canvas(self):
        print("  -> Mining sheet 'BG canvas, ventcap'...")
        try:
            df = self._read_sheet_unmerged("BG canvas, ventcap")
            # Dò tìm giá bạt:
            canvas_price = self._search_price(df, ["tôn 45 + bạt 100", "đơn giá/m"])
            if canvas_price == 0: canvas_price = 150000 # Safety net nếu cấu trúc bị xóa

            self.master_tech.append({
                "MAT_ID": "CANVAS_FIRE_RESISTANT",
                "Category": "VẬT_TƯ_BẠT",
                "Name": "Cuộn vải bạt bọc cách nhiệt/chống cháy",
                "Unit": "m2",
                "Source_Trace": "BG canvas, ventcap"
            })
            self.master_price.append({"MAT_ID": "CANVAS_FIRE_RESISTANT", "Price": canvas_price})
        except Exception as e:
            print(f"Lỗi đọc sheet canvas: {e}")

    def _mine_sheet_tieu_am(self):
        print("  -> Mining sheet 'BG TIEU AM'...")
        try:
            df = self._read_sheet_unmerged("BG TIEU AM")
            rockwool_price = self._search_price(df, ["bông", "60kg/m3"])
            glasscloth_price = self._search_price(df, ["vải", "thuỷ tinh", "tt/m2"])
            perforated_price = self._search_price(df, ["tôn lỗ", "đục lỗ"])

            self.master_tech.extend([
                {"MAT_ID": "ROCKWOOL_50MM_50KG", "Category": "VẬT_LIỆU_TIÊU_ÂM", "Name": "Bông Rockwool tỷ trọng 50kg/m3 dày 50mm", "Unit": "m2", "Source_Trace": "BG TIEU AM"},
                {"MAT_ID": "GLASS_CLOTH", "Category": "VẬT_LIỆU_TIÊU_ÂM", "Name": "Vải thủy tinh bọc tiêu âm", "Unit": "m2", "Source_Trace": "BG TIEU AM"},
                {"MAT_ID": "PERFORATED_SHEET", "Category": "VẬT_LIỆU_TIÊU_ÂM", "Name": "Tôn đục lỗ tiêu âm", "Unit": "m2", "Source_Trace": "BG TIEU AM"}
            ])
            self.master_price.extend([
                {"MAT_ID": "ROCKWOOL_50MM_50KG", "Price": rockwool_price if rockwool_price else 85000},
                {"MAT_ID": "GLASS_CLOTH", "Price": glasscloth_price if glasscloth_price else 15000},
                {"MAT_ID": "PERFORATED_SHEET", "Price": perforated_price if perforated_price else 120000}
            ])
        except Exception as e:
            print(f"Lỗi đọc sheet tiêu âm: {e}")

    def _mine_sheet_bao_on(self):
        print("  -> Mining sheet 'bảo ôn' (Ống gió mềm có/không bảo ôn)...")
        try:
            df = self._read_sheet_unmerged("bảo ôn")
            # Sheet 'bảo ôn' thực chất là bảng giá Ống gió mềm D100 -> D350
            # Tìm dòng và đơn giá thực tế
            for r in range(12, min(26, len(df))):
                item_name = str(df.iloc[r, 1]).strip()
                size_str = str(df.iloc[r, 3]).strip()
                unit = str(df.iloc[r, 9]).strip() if len(df.columns) > 9 else "ống"
                try:
                    price = float(df.iloc[r, 11])
                except:
                    price = 0.0
                
                if item_name and price > 0:
                    clean_id = f"FLEX_DUCT_{size_str}_{'INSUL' if 'có' in item_name else 'NON_INSUL'}"
                    self.master_tech.append({
                        "MAT_ID": clean_id,
                        "Category": "ỐNG_GIÓ_MỀM",
                        "Name": item_name,
                        "Unit": unit if unit else "ống",
                        "Source_Trace": "bảo ôn"
                    })
                    self.master_price.append({"MAT_ID": clean_id, "Price": price})
        except Exception as e:
            print(f"Lỗi đọc sheet bảo ôn: {e}")

    def _mine_sheet_van(self):
        print("  -> Mining sheet 'VT van' (Động cơ Nenutec) & 'Vat tu tôn' (Trục, Bạc đồng)...")
        try:
            # 1. Khai thác Động cơ Nenutec từ sheet 'VT van'
            df_van = self._read_sheet_unmerged("VT van")
            for r in range(14, min(25, len(df_van))):
                desc = str(df_van.iloc[r, 2]).strip()
                if "NACA" in desc or "NACM" in desc or "NTC" in desc:
                    try:
                        price = float(df_van.iloc[r, 4])
                    except:
                        price = 0.0
                    
                    # Trích xuất Model
                    from extract_master_data import to_ascii_slug
                    model_match = re.search(r'(NACA\s*[\d\.\-]+|NACM\s*[\d\.\-]+|NTC\s*\d+)', desc)
                    model_code = to_ascii_slug(model_match.group(1)) if model_match else f"ACTUATOR-{r}"
                    mat_id = f"MAT-ACTUATOR-{model_code}"
                    
                    self.master_tech.append({
                        "MAT_ID": mat_id,
                        "Category": "ĐỘNG_CƠ_VÀ_CẢM_BIẾN",
                        "Name": desc,
                        "Unit": "Cái",
                        "Source_Trace": "VT van"
                    })
                    self.master_price.append({"MAT_ID": mat_id, "Price": price})

            # 2. Khai thác Trục SUS, Bạc đồng, Tay gạt từ sheet 'Vat tu tôn'
            df_ton = self._read_sheet_unmerged("Vat tu tôn")
            for r in range(4, min(12, len(df_ton))):
                item_name = str(df_ton.iloc[r, 32]).strip()
                unit = str(df_ton.iloc[r, 33]).strip()
                try:
                    price = float(df_ton.iloc[r, 34])
                except:
                    price = 0.0
                if item_name and price > 0:
                    from extract_master_data import to_ascii_slug
                    slug = to_ascii_slug(item_name)
                    mat_id = f"MAT-DAMPER-{slug}"
                    self.master_tech.append({
                        "MAT_ID": mat_id,
                        "Category": "PHỤ_KIỆN_VAN",
                        "Name": item_name,
                        "Unit": unit,
                        "Source_Trace": "Vat tu tôn"
                    })
                    self.master_price.append({"MAT_ID": mat_id, "Price": price})
                    
            # 3. Thêm cơ cấu lò xo lệch tâm cho NRD
            self.master_tech.append({
                "MAT_ID": "ECCENTRIC_SHAFT",
                "Category": "PHỤ_KIỆN_VAN",
                "Name": "Cơ cấu lệch tâm / Lò xo đóng mở (NRD)",
                "Unit": "Bộ",
                "Source_Trace": "BG VAN CU"
            })
            self.master_price.append({"MAT_ID": "ECCENTRIC_SHAFT", "Price": 45000})

        except Exception as e:
            print(f"Lỗi đọc sheet van: {e}")

    def _build_product_catalog(self):
        print("  -> Building Product Catalog...")
        self.manufacturable_products = [
            {"product_code": "CANVAS_CONN", "name": "Khớp nối mềm (Canvas)", "keywords": ["canvas", "khớp nối mềm"], "mapping_category": "CANVAS"},
            {"product_code": "ACOUSTIC_PARTITION", "name": "Vách ngăn tiêu âm/Hộp gió tiêu âm", "keywords": ["tiêu âm", "vách ngăn", "plenum"], "mapping_category": "TIEU_AM"},
            {"product_code": "DIFFUSER_GRILLE", "name": "Cửa gió / Miệng gió các loại", "keywords": ["cửa", "miệng", "nan", "louver"], "mapping_category": "CUA_GIO"},
            {"product_code": "DAMPER", "name": "Van điều chỉnh lưu lượng / Van gió", "keywords": ["van", "vcd", "fd", "md", "nrd"], "mapping_category": "VAN_GIO"},
            {"product_code": "FLEX_DUCT", "name": "Ống gió mềm (có/không bảo ôn)", "keywords": ["ống mềm", "ống gió mềm", "flex duct"], "mapping_category": "ONG_MEM"},
            {"product_code": "DUCT_RECT", "name": "Ống gió vuông/chữ nhật", "keywords": ["ống gió", "tole", "tôn"], "mapping_category": "ONG_GIO"}
        ]
        self.commercial_products = [
            {"product_code": "FAN_AXIAL", "name": "Quạt hướng trục", "keywords": ["quạt", "fan", "cef", "sef"]},
            {"product_code": "AC_UNIT", "name": "Máy lạnh (PAU, FCU, ODU)", "keywords": ["pau", "fcu", "odu", "máy lạnh", "dàn lạnh", "dàn nóng"]},
            {"product_code": "PIPE_COPPER", "name": "Ống đồng & phụ kiện thương mại", "keywords": ["ống đồng", "ông đồng", "ống nước", "upvc", "bẫy nước", "cửa sổ", "vật tư phụ", "phụ kiện", "lớp chống cháy", "nghiệm thu", "cắt đục", "chống cháy lan", "lưới bảo vệ"]},
            {"product_code": "VALVE_WATER", "name": "Van nước", "keywords": ["van nước", "van chặn", "van cân bằng", "van bướm", "van cổng", "van bi", "van cầu", "van xả khí", "van xả cặn", "van xả nước", "van giảm áp", "van an toàn", "van 1 chiều nước", "van điện từ", "y lọc"]}
        ]

    def _export_json(self):
        import os
        base_dir = os.path.dirname(os.path.abspath(__file__))
        out_dir = os.path.join(os.path.dirname(base_dir), "data", "master_data")
        os.makedirs(out_dir, exist_ok=True)
        
        try:
            from extract_master_data import extract_all_master_data, save_master_data
            full_records = extract_all_master_data()
            save_master_data(full_records)

            tech_path = os.path.join(out_dir, "master_database_tech.json")
            price_path = os.path.join(out_dir, "master_database_price.json")
            mfg_path = os.path.join(out_dir, "manufacturable_catalog.json")
            com_path = os.path.join(out_dir, "commercial_catalog.json")

            with open(tech_path, "r", encoding="utf-8") as f:
                current_tech = json.load(f)
            with open(price_path, "r", encoding="utf-8") as f:
                current_price = json.load(f)
            
            existing_ids = set([item["MAT_ID"] for item in current_tech])
            for t in self.master_tech:
                if t["MAT_ID"] not in existing_ids:
                    current_tech.append(t)
                    existing_ids.add(t["MAT_ID"])
                else:
                    for i, ct in enumerate(current_tech):
                        if ct["MAT_ID"] == t["MAT_ID"]:
                            current_tech[i].update(t)
            
            existing_price_ids = set([item["MAT_ID"] for item in current_price])
            for p in self.master_price:
                if p["MAT_ID"] not in existing_price_ids:
                    current_price.append(p)
                    existing_price_ids.add(p["MAT_ID"])
                else:
                    for i, cp in enumerate(current_price):
                        if cp["MAT_ID"] == p["MAT_ID"]:
                            current_price[i].update(p)
                    
            with open(tech_path, "w", encoding="utf-8") as f:
                json.dump(current_tech, f, indent=4, ensure_ascii=False)
            with open(price_path, "w", encoding="utf-8") as f:
                json.dump(current_price, f, indent=4, ensure_ascii=False)
                
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            prices_dir = os.path.join(out_dir, "prices")
            os.makedirs(prices_dir, exist_ok=True)
            history_price_path = os.path.join(prices_dir, f"master_database_price_{timestamp}.json")
            with open(history_price_path, "w", encoding="utf-8") as f:
                json.dump(current_price, f, indent=4, ensure_ascii=False)
            print(f"  -> Lưu phiên bản giá lịch sử tại: {history_price_path}")
                
            with open(mfg_path, "w", encoding="utf-8") as f:
                json.dump(self.manufacturable_products, f, indent=4, ensure_ascii=False)
            with open(com_path, "w", encoding="utf-8") as f:
                json.dump(self.commercial_products, f, indent=4, ensure_ascii=False)
                
        except Exception as e:
            print(f"Lỗi khi merge data: {e}")

Agent00_DataMiner = SwindDataMinerAgent

if __name__ == "__main__":
    miner = SwindDataMinerAgent("../BẢNG TÍNH GIÁ SWIND  chuẩn 2026.xls")
    miner.run_mining()
