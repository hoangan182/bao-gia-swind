import json
import re
import os
import shutil
from pathlib import Path

# Paths
BASE_DIR = Path(__file__).resolve().parent.parent
MASTER_DB_PATH = BASE_DIR / "data" / "master_data" / "swind_experience_db.json"
PENDING_QUEUE_PATH = BASE_DIR / "data" / "master_data" / "pending_approval_queue.json"

class SwindUniversalExtractor:
    """
    Agent 0A: Universal BOQ Extractor (Production Fortified Version)
    - Phòng thủ chống đầu độc dữ liệu (Two-Tier Learning).
    - Phân tích đa chiều: Cổ vs Mặt, Phụ kiện, Vật liệu, Độ dày, EI chống cháy.
    - Longest-Token-First matching chống xung đột từ viết tắt.
    - UOM Sanitizer chống bẫy tài chính Bộ vs m2.
    """
    def __init__(self, project_name=None):
        self.project_name = project_name
        self.project_db_path = None
        if project_name:
            self.project_db_path = BASE_DIR / "data" / "projects" / project_name / "project_learning.json"
        
        self.master_db = {"STANDARD_UNITS": {}}
        self.project_db = {}
        self.load_databases()

    def _safe_load_json(self, path):
        if not path.exists():
            return {}
        try:
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"[CẢNH BÁO] Không đọc được file {path}: {e}")
            return {}

    def _safe_write_json(self, path, data):
        """Atomic write: ghi ra file .tmp rồi rename để chống hỏng file khi crash."""
        os.makedirs(path.parent, exist_ok=True)
        tmp_path = path.with_suffix(".tmp")
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        shutil.move(tmp_path, path)

    def load_databases(self):
        """Tải Bảng Kinh Nghiệm Master và Bảng Kinh Nghiệm Riêng của Dự án."""
        self.master_db = self._safe_load_json(MASTER_DB_PATH)
        if self.project_db_path and self.project_db_path.exists():
            self.project_db = self._safe_load_json(self.project_db_path)
        else:
            self.project_db = {}

    def normalize_text(self, text):
        if not text:
            return ""
        text = str(text).lower()
        # Thay thế ký tự đặc biệt bằng khoảng trắng
        text = re.sub(r'[^\w\s\.\,\-\/]', ' ', text)
        return ' '.join(text.split())

    # =========================================================================
    # 1. BÓC TÁCH THUỘC TÍNH NÂNG CAO (MATERIAL, THICKNESS, EI, ACCESSORIES)
    # =========================================================================
    def extract_spec_features(self, text):
        """
        Trích xuất toàn bộ các thuộc tính ăn tiền:
        - Vật liệu (Inox, Tôn mạ kẽm Z..., Nhôm)
        - Độ dày tôn/nhôm
        - Tiêu chuẩn PCCC (EI, Cầu chì)
        - Động cơ điều khiển (Actuator)
        - Phụ kiện tích hợp (OBD, Phin lọc G4, Lưới côn trùng)
        """
        raw = str(text).upper()
        norm = self.normalize_text(text)
        features = {
            "material": "Tôn mạ kẽm tiêu chuẩn",
            "thickness_mm": None,
            "fire_rating": None,
            "actuator": None,
            "accessories": []
        }

        # 1. Vật liệu
        if "INOX 304" in raw or "SUS 304" in raw or "THÉP KHÔNG GỈ 304" in raw:
            features["material"] = "Inox 304"
        elif "INOX 201" in raw or "SUS 201" in raw:
            features["material"] = "Inox 201"
        elif "NHÔM" in raw or "ALUMINUM" in raw or "A6063" in raw:
            features["material"] = "Nhôm định hình A6063-T5"
        elif "Z275" in raw:
            features["material"] = "Tôn mạ kẽm Z275"
        elif "Z180" in raw:
            features["material"] = "Tôn mạ kẽm Z180"
        elif "Z80" in raw:
            features["material"] = "Tôn mạ kẽm Z80"

        # 2. Độ dày tôn (mm)
        thick_match = re.search(r'(?:DÀY|T\s*=|ĐỘ DÀY)\s*(\d+[.,]\d+)\s*(?:MM)?', raw)
        if not thick_match:
            thick_match = re.search(r'(\d+[.,]\d+)\s*(?:MM)\b', raw)
        if thick_match:
            try:
                features["thickness_mm"] = float(thick_match.group(1).replace(",", "."))
            except ValueError:
                pass

        # 3. Tiêu chuẩn PCCC (EI & Cầu chì)
        ei_match = re.search(r'\b(EI\s*\d{2,3})\b', raw)
        if ei_match:
            features["fire_rating"] = ei_match.group(1).replace(" ", "")
        elif "CẦU CHÌ" in raw or "FUSE" in raw or "72°C" in raw or "70°C" in raw or "280°C" in raw:
            temp_match = re.search(r'(\d+)\s*°?C', raw)
            temp = temp_match.group(1) if temp_match else "72"
            features["fire_rating"] = f"Cầu chì nhiệt {temp}°C"

        # 4. Động cơ điều khiển (Actuator)
        if "BELIMO" in raw or "NENUTEC" in raw or "ĐỘNG CƠ" in raw or "MOTOR" in raw or "GẮN ĐỘNG CƠ" in raw:
            volt = "24V" if "24V" in raw else ("220V" if "220V" in raw or "230V" in raw else "24V/220V")
            spring = " (Lò xo phản hồi)" if ("SPRING" in raw or "LÒ XO" in raw or "PHẢN HỒI" in raw) else ""
            features["actuator"] = f"Động cơ điện {volt}{spring}"
        elif "TAY GẠT" in raw or "MANUAL" in raw:
            features["actuator"] = "Tay gạt trục cơ"

        # 5. Phụ kiện đi kèm
        if "OBD" in raw or "VAN ĐIỀU CHỈNH LƯỢNG GIÓ" in raw:
            features["accessories"].append("Van gió OBD tích hợp")
        if "LƯỚI LỌC" in raw or "PHIN LỌC" in raw or "G4" in raw or "NYLON" in raw:
            features["accessories"].append("Phin lọc bụi G4/Nylon")
        if "CÔN TRÙNG" in raw or "LƯỚI INOX" in raw or "INSECT SCREEN" in raw:
            features["accessories"].append("Lưới chắn côn trùng Inox")
        if "TIÊU ÂM" in raw or "BÔNG KHOÁNG" in raw or "ROCKWOOL" in raw:
            features["accessories"].append("Bọc bông tiêu âm chống ồn")
        if "SƠN TĨNH ĐIỆN" in raw or "POWDER COATING" in raw:
            features["accessories"].append("Sơn tĩnh điện theo màu kiến trúc")

        return features

    # =========================================================================
    # 2. BÓC TÁCH KÍCH THƯỚC NGỮ CẢNH (CỔ VS MẶT, CHỮ NHẬT VS TRÒN)
    # =========================================================================
    def parse_dimensions_contextual(self, text):
        """
        Bóc tách chính xác:
        - Kích thước mặt (Face size): W, H
        - Kích thước cổ (Neck size): W_neck, H_neck hoặc D_neck
        - Loại trừ số nhầm lẫn: kW, m3/h, Pa, RPM, V.
        """
        if not text:
            return {}

        clean_text = str(text).upper()
        # Loại trừ các con số công suất / lưu lượng / điện áp để không nhận nhầm kích thước
        clean_text = re.sub(r'\b\d+(?:\.\d+)?\s*(?:KW|HP|M3\/H|L\/S|PA|RPM|V|DB|HZ|W|A)\b', ' ', clean_text)

        dims = {}

        # 1. Tìm kích thước cổ riêng biệt nếu có ghi rõ "CỔ D..." hoặc "CỔ ...x..."
        neck_d = re.search(r'(?:CỔ|NECK)\s*(?:D|Ø|PHI)\s*(\d+)', clean_text)
        if neck_d:
            dims["neck_d"] = int(neck_d.group(1))

        neck_w_h = re.search(r'(?:CỔ|NECK)\s*(\d+)\s*[X\*]\s*(\d+)', clean_text)
        if neck_w_h:
            dims["neck_w"] = int(neck_w_h.group(1))
            dims["neck_h"] = int(neck_w_h.group(2))

        # 2. Tìm kích thước 3D: WxHxL
        match_3d = re.search(r'\b(\d+)\s*[X\*]\s*(\d+)\s*[X\*]\s*(\d+)\b', clean_text)
        if match_3d:
            dims["w"] = int(match_3d.group(1))
            dims["h"] = int(match_3d.group(2))
            dims["l"] = int(match_3d.group(3))
            return dims

        # 3. Tìm kích thước 2D: WxH
        match_2d = re.search(r'\b(\d+)\s*[X\*]\s*(\d+)\b', clean_text)
        if match_2d:
            dims["w"] = int(match_2d.group(1))
            dims["h"] = int(match_2d.group(2))
            
            # Nếu có thêm thông tin chiều dài L=...
            l_match = re.search(r'\bL\s*[:=]?\s*(\d+)\b', clean_text)
            if l_match:
                dims["l"] = int(l_match.group(1))
            return dims

        # 4. Tìm kích thước tròn: D, Ø, Phi
        match_d = re.search(r'(?:\b|[\s_])(?:D|Ø|PHI)\s*(\d+)\b', clean_text)
        if match_d:
            dims["d"] = int(match_d.group(1))
            l_match = re.search(r'\bL\s*[:=]?\s*(\d+)\b', clean_text)
            if l_match:
                dims["l"] = int(l_match.group(1))
            return dims

        return dims

    # =========================================================================
    # 3. SO KHỚP PHÂN LOẠI AN TOÀN (LONGEST-TOKEN MATCH FIRST)
    # =========================================================================
    def match_product_type_safe(self, raw_name):
        """
        So khớp an toàn:
        - Bước 1: Tra cứu Project-Specific memory trước.
        - Bước 2: Tra cứu Master DB với thứ tự ưu tiên: Cụm từ dài nhất trước.
        - Dùng regex ranh giới từ `\b` cho các từ viết tắt ngắn (MD, FD, VCD) để chống false positive.
        """
        normalized_raw = self.normalize_text(raw_name)

        # 1. Kiểm tra Project-level memory trước
        if self.project_db:
            for alias, target in self.project_db.items():
                if self.normalize_text(alias) == normalized_raw:
                    return target["standard_id"], target["standard_name"], "PROJECT_MEMORY"

        # 2. Gom tất cả alias từ Master DB và sắp xếp theo độ dài giảm dần (Longest first)
        candidates = []
        for std_id, data in self.master_db.get("STANDARD_UNITS", {}).items():
            for alias in data.get("aliases", []):
                candidates.append({
                    "alias": alias,
                    "std_id": std_id,
                    "std_name": data.get("name", std_id),
                    "length": len(alias)
                })
        
        # Sắp xếp từ dài nhất lên đầu
        candidates.sort(key=lambda x: x["length"], reverse=True)

        # 3. So khớp
        for cand in candidates:
            norm_alias = self.normalize_text(cand["alias"])
            if len(norm_alias) <= 3:
                # Từ ngắn (như VCD, NRD, FD, MD) phải có ranh giới từ \b
                pattern = r'\b' + re.escape(norm_alias) + r'\b'
                if re.search(pattern, normalized_raw):
                    return cand["std_id"], cand["std_name"], "MASTER_MATCH"
            else:
                if norm_alias in normalized_raw:
                    return cand["std_id"], cand["std_name"], "MASTER_MATCH"

        return None, None, "UNMATCHED"

    # =========================================================================
    # 4. BẢO VỆ CHỐNG ĐẦU ĐỘC (TWO-TIER LEARNING & APPROVAL QUEUE)
    # =========================================================================
    def record_user_mapping(self, raw_name, std_id, user_id="Engineer"):
        """
        Không ghi đè thẳng vào Master DB!
        1. Ghi vào Project-specific memory (`project_learning.json`).
        2. Đẩy vào `pending_approval_queue.json` chờ Lead duyệt.
        """
        std_name = self.master_db.get("STANDARD_UNITS", {}).get(std_id, {}).get("name", std_id)

        # 1. Lưu vào Project Memory
        if self.project_db_path:
            self.project_db[raw_name] = {
                "standard_id": std_id,
                "standard_name": std_name,
                "mapped_by": user_id
            }
            self._safe_write_json(self.project_db_path, self.project_db)

        # 2. Đẩy vào Hàng đợi phê duyệt Master
        queue = self._safe_load_json(PENDING_QUEUE_PATH)
        if "pending_proposals" not in queue:
            queue["pending_proposals"] = []

        # Kiểm tra xem đề xuất này đã có trong hàng đợi chưa
        exists = any(p["raw_name"] == raw_name and p["proposed_id"] == std_id for p in queue["pending_proposals"])
        if not exists:
            queue["pending_proposals"].append({
                "raw_name": raw_name,
                "proposed_id": std_id,
                "standard_name": std_name,
                "project": self.project_name or "General",
                "proposed_by": user_id,
                "status": "PENDING_APPROVAL"
            })
            self._safe_write_json(PENDING_QUEUE_PATH, queue)
            print(f"[KIỂM SOÁT AN TOÀN] Từ mới '{raw_name}' đã được lưu vào Dự án '{self.project_name}' và gửi vào Hàng đợi Phê duyệt Master.")
            return True
        return False

    # =========================================================================
    # 5. TRÍCH XUẤT TOÀN DIỆN & KIỂM TRA ĐƠN VỊ TÍNH (UOM SANITIZER)
    # =========================================================================
    def extract_and_sanitize(self, raw_name, raw_dim="", raw_unit="", raw_qty=""):
        std_id, std_name, match_source = self.match_product_type_safe(raw_name)
        
        # Bóc tách kích thước
        dims = self.parse_dimensions_contextual(raw_dim)
        if not dims:
            dims = self.parse_dimensions_contextual(raw_name)
            
        # Bóc tách thuộc tính ăn tiền (Spec features)
        spec = self.extract_spec_features(raw_name + " " + raw_dim)
        
        status = "PASS" if std_id else "REQUIRES_USER_MAPPING"
        messages = []

        if not std_id:
            messages.append("Chủng loại chưa nhận diện được, chờ gán trên UI.")
            
        if not dims:
            status = "REQUIRES_USER_MAPPING" if status == "REQUIRES_USER_MAPPING" else "WARNING_MISSING_DIMS"
            messages.append("Thiếu hoặc không nhận dạng được kích thước (W, H, D).")

        # UOM Financial Trap Check
        norm_unit = str(raw_unit).strip().lower()
        if norm_unit in ["m2", "m²", "mét vuông"]:
            if std_id and "LOUVER" in std_id:
                messages.append("LƯU Ý: Khối lượng tính bằng m2. Cần kiểm tra diện tích danh định.")
            elif std_id and "VCD" in std_id:
                status = "WARNING_UOM_MISMATCH"
                messages.append("BẪY ĐƠN GIÁ: Van gió thường tính theo Cái/Bộ, nhưng BOQ ghi m2. Cần quy đổi!")

        return {
            "raw_name": raw_name,
            "raw_dim": raw_dim,
            "raw_unit": raw_unit,
            "raw_qty": raw_qty,
            "standard_id": std_id,
            "standard_name": std_name,
            "match_source": match_source,
            "parsed_dims": dims,
            "spec_features": spec,
            "status": status,
            "message": " | ".join(messages) if messages else "Đã nhận diện chuẩn mực."
        }

# Test trực tiếp
if __name__ == "__main__":
    extractor = SwindUniversalExtractor(project_name="Du_An_HDL_A1")
    
    test_cases = [
        ("Van dập lửa FD 1200x500 tôn dày 1.2mm đạt EI60 gắn động cơ Belimo 24V", "", "Bộ", "10"),
        ("Cửa gió nan T sơn tĩnh điện 800x200 (cổ 750x150) kèm phin lọc G4", "", "Bộ", "25"),
        ("Quạt ly tâm Kruger BDB 500 4P 1.5kW 380V", "D500", "Bộ", "2"),
        ("Cửa louver chắn mưa kèm lưới côn trùng inox", "2000x1500", "m2", "15.0"),
        ("Van chặn lửa gắn cầu chì nhiệt 72°C", "D250 L=200", "Cái", "12")
    ]
    
    print("=== CHẠY THỬ NGHIỆM EXTRACTOR ĐÃ GIA CỐ PHÒNG THỦ ===")
    for name, dim, unit, qty in test_cases:
        res = extractor.extract_and_sanitize(name, dim, unit, qty)
        print(f"\n[RAW] {res['raw_name']}")
        print(f"  ➔ Standard: {res['standard_name']} ({res['standard_id']})")
        print(f"  ➔ Kích thước: {res['parsed_dims']}")
        print(f"  ➔ Vật liệu & PCCC: {res['spec_features']['material']} | {res['spec_features']['fire_rating']} | {res['spec_features']['thickness_mm']}mm")
        print(f"  ➔ Động cơ & Phụ kiện: {res['spec_features']['actuator']} | {res['spec_features']['accessories']}")
        print(f"  ➔ Status: {res['status']} ({res['message']})")
