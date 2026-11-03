# Agent 10 — Old-Quote Price Carrier (On-Demand)

**Module:** `src/agent_10_old_quote_carrier.py`
**Kích hoạt:** CHỈ khi User yêu cầu rõ kiểu *"nhặt giá từ báo giá cũ sang BOQ mới, dòng nào chưa có thì báo mới"*. Không nằm trong luồng báo giá hằng ngày, không thay đổi rule của Agent 01..08.

## Nhiệm vụ
1. Đọc các sheet báo giá cũ do User chỉ định (`--old-sheets`, sheet đứng trước ưu tiên khi trùng giá).
2. Ghép từng dòng BOQ mới với báo giá cũ theo chữ ký: **Loại hàng** (FD / MFD / MD / VCD / NRD / PRD / Louver / LCCT / Cửa gió) + **Kích thước** + **Phụ kiện** (OBD / LCCT / Lọc G4-LLB-phin lọc) + **Kiểu nan cửa gió** (sọt trứng / khe / khuếch tán / nan thẳng).
3. Dòng khớp chắc chắn → nhặt giá cũ (Model, kích thước A1..B2, Modul, L, độ dày, ghi chú lấy theo dòng BG cũ; ĐVT & KL theo BOQ mới).
4. Dòng còn lại → tạo **BOQ tạm rút gọn** (header + dòng hiển thị chưa nhặt giá, giữ nguyên TOÀN BỘ cột kể cả Spec; bỏ Title nhóm chung không mang thông số như "Van, miệng gió" để parser không ghép nhầm combo Cửa + Van; Title có thông số OBD/LCCT/EI/độ dày... vẫn giữ để kế thừa). Mục đích: Agent 00B nhận đúng BOQ chuẩn, không "chuẩn hóa" làm mất cột Spec — xử lý riêng trong nhánh Agent 10, không sửa Agent 00B → gọi `swind_master_runner.py --non-interactive --auto-accept [cờ truyền thêm]` (giữ nguyên mọi rule & Cổng kiểm soát cuối) → ghép lại 1 Sheet `BG` đúng thứ tự BOQ.

## Trạng thái ghép
| Trạng thái | Ý nghĩa | Mặc định |
| :--- | :--- | :--- |
| Khớp chắc chắn | Cùng loại, cùng KT, cùng phụ kiện, cùng kiểu nan | Nhặt giá cũ |
| Cần xác nhận | Đảo chiều KT (600x500 ↔ 500x600) hoặc kiểu nan chưa xác định | Báo mới; nhặt khi có `--accept-review` |
| BG cũ đã đổi loại | Tên giống nhưng BG cũ đã báo loại khác (VD: `FD` → *Chuyển sang MFD*) | Báo mới; nhặt khi có `--accept-converted` |
| Không có trong BG cũ | — (kèm gợi ý dòng cùng KT khác kiểu nan/phụ kiện nếu có) | Báo mới |

**AI bắt buộc hỏi lại User** với nhóm *Cần xác nhận* / *BG cũ đã đổi loại* và nêu các dòng *nhiều đơn giá khác nhau trong BG cũ* trước khi chốt.

## Lệnh
```bash
./venv/bin/python src/agent_10_old_quote_carrier.py "<BOQ.xlsx>" \
    --old-quote "<BG_cu.xlsx>" --old-sheets "<Sheet ưu tiên 1>,<Sheet 2>" \
    [--accept-review] [--accept-converted] [--dry-run] [--boq-sheet "<Sheet BOQ>"] \
    [cờ của swind_master_runner: --only-cua-van, --spec-priority note, --override ...]
```
- `--converted-yellow-only`: nhóm *BG cũ đã đổi loại* chỉ nhặt giá loại mới khi dòng BG cũ được **bôi vàng** (Kỹ thuật chỉ định); dòng không vàng báo mới theo loại ghi trong BOQ.
- `--multi-price-new`: dòng mà BG cũ có ≥2 đơn giá khác nhau cho cùng mặt hàng → Swind báo mới.
- `--force-new "r1,r2"`: bắt buộc Swind báo mới các dòng BOQ chỉ định.
- `--neck-rows "r1,r2"`: dòng báo mới hiểu kích thước là **kích thước cổ** (ghi dấu `(KTC)` vào cột Tên bản BOQ tạm, tên gốc được trả lại trên `BG`). Không dùng `--override` theo số dòng vì BOQ tạm rút gọn có số dòng khác BOQ gốc.
- Không ghi `--old-sheets` → in danh sách sheet có dạng báo giá để hỏi User.
- `--dry-run` → chỉ in kết quả ghép, không báo giá phần còn lại.

## Đầu ra
- `output/<Project>/<Tên file BOQ gốc>.xlsx`: Sheet BOQ gốc + Sheet `BG` (giá cũ + báo mới, đúng thứ tự BOQ).
- `output/<Project>/internal_estimation/OLD_QUOTE_MATCH_REPORT.xlsx|.json`: đối chiếu từng dòng (trạng thái, dòng BG cũ, giá cũ, lý do).
- Lưu ý: `internal_estimation/*_ESTIMATION.xlsx` và Bảng tổng hợp runner in ra chỉ là **phần báo mới**; bảng tổng hợp cuối của Agent 10 mới là tổng toàn bộ.
