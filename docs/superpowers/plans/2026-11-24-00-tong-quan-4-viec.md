# Tổng quan 4 việc giảm sửa code mỗi lần báo giá (2026-11-24)

**Nguồn:** trang đánh giá https://claude.ai/artifact/M4uteukwSX6pyh7zbV3Rof (số liệu đo trên repo, commit 513cdee).

**Mục tiêu chung:** lỗi đọc sai nội dung BOQ được bắt *trước khi* ra giá bằng một bảng User duyệt, thay vì phát hiện sau và sửa code. Yêu cầu mới phần lớn thành một mục JSON, không sửa nhiều file.

| # | Việc | File kế hoạch | Phụ thuộc | Rủi ro đổi giá |
|---|---|---|---|---|
| 1 | Rút gọn AGENTS.md (57 KB → ≤ 8 KB, không mất rule) | `2026-11-24-1-rut-gon-agents-md.md` | — | Không |
| 2 | Bảng "đã hiểu thế nào" + ghi nguồn từng quyết định | `2026-11-24-2-bang-da-hieu-the-nao.md` | — | Không (chỉ thêm báo cáo) |
| 3 | Mặc định lặng lẽ → hỏi lại (theo bảng `default_rules.json`) | `2026-11-24-3-mac-dinh-thanh-hoi-lai.md` | Việc 2 | Có, chỉ ở dòng mặc định chưa chốt |
| 4 | Gom quyết định loại hàng về classifier + test chặn từ khóa | `2026-11-24-4-gom-logic-ve-classifier.md` | Việc 2 (cập nhật nguồn), nên sau 3 | Không (refactor, so mẫu = 0 khác biệt) |

**Thứ tự:** 1 → 2 → 3 → 4. Việc 1 làm độc lập, có thể song song với 2.

## Quyết định cần User chốt trước Việc 3

> **ĐÃ CHỐT 2026-11-24 (User):** mặc định chưa chốt → **báo giá theo mặc định + tô vàng** (`BAO_VA_HOI`). Thực hiện 4 việc theo subagent-driven.

- **Dòng rơi vào mặc định CHƯA chốt** (VD van chỉ ghi kích thước, không nhận ra loại → đang lặng lẽ báo VCD):
  - **(Khuyến nghị) Báo giá theo mặc định + tô vàng `⚠️ ĐÃ HIỂU THEO MẶC ĐỊNH ... — xin xác nhận`**, giống cách xử lý lỗi gõ đã đoán. Không làm rơi doanh thu dòng.
  - Hoặc không báo + tô vàng hỏi lại, giống `TITLE_UNCLEAR`.
- Ngoại lệ đã định sẵn trong kế hoạch: dòng chỉ được xếp **loại hàng** nhờ Title (bước 5 fallback của parser) → **không báo + hỏi lại**, cùng logic `TITLE_UNCLEAR` đã chốt 2026-11-23.
- Mặc định **đã chốt** (cửa không ghi kiểu → SDG 2026-11-24; FD không EI → FD thường 2026-11-13; động cơ Belimo 1.02) giữ nguyên, chỉ ghi vào báo cáo JSON, không tô vàng.

## Kiểm thử chuẩn sau mỗi task có sửa code (dùng chung 4 kế hoạch)

```bash
./venv/bin/python src/swind_item_inspector.py --self-test
./venv/bin/python -m unittest discover -s tests -p "test_swind_*.py"
./venv/bin/python src/swind_pattern_lab.py --check
./venv/bin/python src/swind_e2e_regression.py --modes default,duct --files-from output/_pattern_lab/e2e_files.txt
```
Đạt = self-test 100%, unittest OK, `--check` không có mẫu đổi ngoài phần kế hoạch cho phép, E2E không `DIFF`/`FAIL` ngoài phần cho phép. Task cuối mỗi việc chạy E2E toàn bộ (`swind_e2e_regression.py` không cờ). AI không commit; cuối mỗi task báo User danh sách file để User tự commit.
