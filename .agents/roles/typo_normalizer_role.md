# TYPO NORMALIZER: CHUẨN HÓA LỖI CHÍNH TẢ BOQ (DÙNG CHUNG)
> **Mã định danh:** `SWIND-TYPO-NORMALIZER`
> **Module thực thi:** [`src/typo_normalizer.py`](file:///Users/hoangan/work/PCCC/swind/src/typo_normalizer.py)
> **Bảng rule:** [`data/master_data/typo_rules.json`](file:///Users/hoangan/work/PCCC/swind/data/master_data/typo_rules.json)
> **Vị trí trong luồng:** `SwindBOQParser.parse_sheet` phát hiện lỗi 1 lần mỗi dòng (`detect_code_typos` + `restore_accents`) → gắn `item["typo_events"]` và dùng `normalize_for_match` cho chuỗi Tên / Title / combo; `Agent01.resolve_item_spec` dùng `normalize_for_match(..., "agent01", typo_events)` cho `raw_search` / `full_search`; `damper_classifier.fix_typos` gọi `apply_dictionary(..., "van")`; runner in `gate_lines` ở Kiểm soát cuối, ghi `typo_events` vào `INPUT_COVERAGE_REPORT.json`, gửi đề xuất Agent 02; `swind_excel_builder` tô vàng dòng theo `bg_flag`.
> **Thiết kế:** [2026-11-03-typo-normalizer-design.md](file:///Users/hoangan/work/PCCC/swind/docs/superpowers/specs/2026-11-03-typo-normalizer-design.md) · **Kế hoạch:** [2026-11-03-typo-normalizer.md](file:///Users/hoangan/work/PCCC/swind/docs/superpowers/plans/2026-11-03-typo-normalizer.md)

---

## 1. VAI TRÒ
- Sửa lỗi chính tả BOQ (thiếu dấu, gõ nhầm mã như `ODB` / `MDF` / `RND` / `LCCCT`) ở **một chỗ duy nhất** cho mọi bộ nhận diện cửa / van / ống / phạm vi.
- **Chỉ tạo chuỗi so khớp.** Không đọc / ghi Excel, không ghi lại nội dung BOQ; cột Tên trên Sheet `BG` giữ nguyên chữ khách viết, ghi chú đánh dấu chỉ **thêm vào**.
- Không dùng LLM; cùng đầu vào → cùng kết quả.

## 2. CẤU TRÚC BẢNG RULE
| id | Việc | Đánh dấu `BG` |
|---|---|---|
| `TY-01` | Từ điển lỗi đã duyệt — chạy **theo thứ tự trong file**, mỗi mục chỉ áp cho phạm vi trong `pham_vi` (`ten`, `title`, `full`, `combo`, `van`, `agent01`; `*` = mọi mục, dùng khi phát hiện lỗi) | Không |
| `TY-02` | Khôi phục dấu: cụm ≥ 2 chữ trong text mà bỏ dấu trùng **một** cụm từ vựng Swind (gom từ các file rule + `them` − `bo`; cụm trùng nhiều nghĩa → `uu_tien` hoặc bỏ). **Chỉ thay chữ hoàn toàn không dấu** (`ống luồn` ≠ `ống lượn`); chữ `giu_dau` không bị thay | Không (chỉ ghi báo cáo nội bộ) |
| `TY-03` | Mã chuẩn (`ma_chuan`: nhóm hàng, thuộc tính chống cháy / động cơ của mã van), `loai_tru`, mẫu âm tiết tiếng Việt không dấu (`am_tiet`). Nghi gõ sai chỉ khi **đảo 2 chữ liền nhau** hoặc **lặp thừa 1 chữ** | — |
| `TY-04` | Đoán theo ngữ cảnh: giữ ứng viên hợp nhóm hàng (cửa gió / van) của dòng + Title cha; ≥ 2 ứng viên thì dùng tín hiệu chống cháy / động cơ để phân biệt. Đúng 1 → `DOAN`; 0 hoặc ≥ 2 → `HOI_LAI` | `⚠️ ĐÃ HIỂU: ODB = OBD — xin xác nhận` / `⚠️ CHƯA RÕ: FMD (có thể: ...)` |

## 3. HỌC LỖI MỚI
- Mỗi `DOAN` → `pending_approval_queue.json` (loại `TYPO`). Duyệt: `./venv/bin/python src/agent_02_boq_reviewer.py --approve-pending [--list | --all]` → thêm vào cuối `TY-01` (mọi phạm vi).
- Dòng `HOI_LAI` → User trả lời, AI thêm: `./venv/bin/python src/agent_02_boq_reviewer.py --add-typo "fmd=mfd"`.
- Mã riêng của khách bị nghi nhầm → thêm vào `TY-03.loai_tru`.
- E2E sao lưu & khôi phục `typo_rules.json` (không học trong lúc chạy kiểm thử).

## 4. QUY TẮC SỬA RULE (AGENTS.md mục 7)
1. Không đổi thứ tự / phạm vi mục TY-01 cũ khi chưa chạy E2E 2 chế độ; file nào lệch phải giải thích được.
2. Mỗi rule sửa ghi `nguon` (ngày / dự án / người chốt), thêm `vi_du_dung` / `vi_du_sai`.
3. Chạy: `./venv/bin/python -m unittest tests/test_swind_typo_rules.py` + self-test + unit + E2E 2 chế độ; quét `input/` bằng `swind_item_inspector.py --typo-scan`.
