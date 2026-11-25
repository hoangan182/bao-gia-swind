---
trigger: always_on
priority: highest
description: Fast-path execution protocol for running Swind BOQ quotations without reading source code or writing post-run Excel reader scripts
---

# QUY TẮC CHẠY BÁO GIÁ TỐC ĐỘ CAO (FAST-PATH QUOTATION EXECUTION)

## 1. Nguyên Tắc "Chạy Ngay — Không Đọc Lại Code"
- Nội dung trùng với `AGENTS.md` (không đọc lại mã nguồn trước khi chạy, không viết script đọc lại file báo giá, kiểm tra chống sót dòng / kế thừa Title, hỏi lại User khi Ghi chú/Spec khác Tên, cách báo cáo kết quả) đã gộp về `AGENTS.md`; bản đầy đủ nguyên văn: `04_QUY_TAC_NGHIEP_VU.md`.

## 2. Câu Lệnh Thực Thi Chuẩn & Đầy Đủ Tham Số CLI

```bash
./venv/bin/python src/swind_master_runner.py "<đường_dẫn_file_BOQ>" --non-interactive --auto-accept [các_cờ_tùy_chọn]
```
*(Ghi chú: Có thể gọi bằng `./venv/bin/python src/swind_master_runner.py`, `python3 src/swind_master_runner.py`, hoặc `./run` — script tự động chuyển sang `./venv/bin/python`).*

### Danh sách các cờ tham số (CLI Flags):
- Danh sách cờ đầy đủ và mới nhất: `AGENTS.md` / `05_CLI_VA_KIEM_THU.md`. Chi tiết mã `--mfd-model` (chỉ có ở file này):
- `--mfd-model <1.01|1.02|1.03|1.04|1.05>`: Chỉ định mã đốt van MFD theo yêu cầu:
  - `1.01`: `SWIND-1.01-MFD-EI120` (Belimo BFN24, BCTN 4751)
  - `1.02`: `SWIND-1.02-MFD-EI90` (Belimo FSLF24V, BCTN 4752 — **Mặc định**)
  - `1.03`: `SWIND-1.03-MFD-EI90` (KLB 5Nm, BCTN 4651)
  - `1.04`: `SWIND-1.04-MFD-EI60` (Honeywell MS4609, BCTN 1515)
  - `1.05`: `SWIND-1.05-MFD-EI120` (Belimo BFN24, BCTN 2390)

## 3. Đường Dẫn File Xuất Chuẩn
- **File báo giá gửi khách hàng (`_BAO_GIA.xlsx`):** xem AGENTS.md (mục 1) và `.agents/rules/04_QUY_TAC_NGHIEP_VU.md` ("THƯ MỤC ĐẦU RA DUY NHẤT").
- **File dự toán nội bộ 9 sheets (`_ESTIMATION.xlsx`):** `output/<Project_Name>/internal_estimation/`.
