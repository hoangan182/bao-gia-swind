import pytest
from playwright.sync_api import sync_playwright, expect
import os

# Đường dẫn tuyệt đối đến file index.html
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
HTML_PATH = f"file://{os.path.join(BASE_DIR, 'frontend', 'index.html')}"

def test_swind_mas_full_flow():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context()
        page = context.new_page()
        
        # Thiết lập tự động chấp nhận các hộp thoại (alert)
        page.on("dialog", lambda dialog: dialog.accept())

        print(f"\n1. Mở trang: {HTML_PATH}")
        page.goto(HTML_PATH)
        
        # 1. Kiểm tra UI cơ bản
        expect(page).to_have_title("Swind HVAC Estimation MAS")
        expect(page.locator("text=Agent 01: BOQ Extractor")).to_be_visible()
        expect(page.locator("text=Agent 03: Input Auditor")).to_be_visible()
        
        # 2. Chạy Giai đoạn 1 (Mở Data Grid Audit)
        print("2. Chạy Bóc tách & Audit Đầu vào (Giai đoạn 1)...")
        page.locator("button:has-text('BÓC TÁCH & KIỂM TOÁN ĐẦU VÀO')").click()
        audit_grid = page.locator("#auditGrid")
        expect(audit_grid).to_be_visible()
        
        # 3. Kiểm tra tính năng Resolve UOM (Bẫy đơn vị tính)
        print("3. Kiểm tra và sửa lỗi bẫy Đơn vị tính (UOM)...")
        # Dòng 4 ban đầu có nút "Đổi sang Cái/Bộ"
        resolve_btn = page.locator("button:has-text('Đổi sang Cái/Bộ')")
        expect(resolve_btn).to_be_visible()
        resolve_btn.click()
        
        # Kiểm tra trạng thái dòng 4 chuyển thành PASS
        row4 = page.locator("#auditGrid tbody tr:nth-child(4)")
        expect(row4.locator("td:nth-child(5)")).to_contain_text("Bộ")
        expect(row4.locator(".status-badge")).to_have_text("PASS")
        
        # 4. Kiểm tra tính năng Ánh xạ chủng loại & Lưu Bảng kinh nghiệm (Two-Tier Learning)
        print("4. Ánh xạ từ vựng mới & Duyệt đưa vào Bảng kinh nghiệm...")
        # Dòng 5 (Mã mới lạ)
        mapping_select = page.locator("#mappingSelect")
        mapping_select.select_option("GRILLE_LINEAR")
        
        # Click Duyệt khối lượng
        confirm_btn = page.locator("button:has-text('Duyệt Dữ Liệu Đầu Vào & Chuyển Sang GĐ2')")
        confirm_btn.click()
        
        # Kiểm tra trạng thái dòng 5 chuyển thành PASS
        row5 = page.locator("#mappingRow")
        expect(row5.locator(".status-badge")).to_have_text("PASS")
        expect(row5.locator("td:nth-child(8)")).to_contain_text("Đã gán vào GRILLE_LINEAR")
        
        # 5. Giai đoạn 2 đã được mở khóa
        print("5. Kiểm tra Giai đoạn 2 đã mở khóa...")
        stage2_card = page.locator("#stage2Card")
        expect(stage2_card).to_have_attribute("style", "opacity: 1; pointer-events: auto;")
        
        # 6. Chạy Pipeline Giai đoạn 2 (Maker & Checker)
        print("6. Kích hoạt Pipeline Giai đoạn 2...")
        run_stage2_btn = page.locator("#runStage2Btn")
        run_stage2_btn.click()
        
        # Chờ nút cập nhật văn bản báo hoàn thành (khoảng 3 giây theo logic timeout trong JS)
        print("7. Chờ Agent 1 (Maker) và Agent 2 (Checker) hoàn tất tính toán...")
        expect(run_stage2_btn).to_contain_text("ĐÃ HOÀN TẤT BÁO GIÁ", timeout=5000)
        
        print("=> TOÀN BỘ AUTOMATION TEST CHO UI/UX ĐÃ PASS THÀNH CÔNG!")
        
        browser.close()

if __name__ == "__main__":
    test_swind_mas_full_flow()
