# Cửa gió 2 lớp mã DDG — cấu thành & công thức đơn giá bán

> Tài liệu độc lập để agent ở hệ thống khác (Swind) cài đặt lại công thức. Trích từ MPrice:
> `src/agent_06_bom_diffuser.py` (`_calc_profile_oval_bd` nhánh `is_double_layer`, `_append_diffuser_accessories`),
> `data/master_data/diffuser_rules.json` (CG-xx), bộ giá `BG-2026-11-13` (nhôm 155.000 đ/kg).
> Đơn vị tiền: VNĐ. Đơn vị kích thước nhập: mm.

## 1. Sản phẩm

Cửa gió **nan nhôm bầu dục 2 lớp** (profile `BD`, cờ `is_double_layer = true`), Model ghi trên báo giá:

| Model | Ý nghĩa |
|---|---|
| `DDG` | cửa 2 lớp trơn |
| `DDG+O` | kèm van điều chỉnh lưu lượng OBD gắn cửa |
| `DDG+F` | kèm lưới lọc bụi thô G4 |
| `DDG+N` | kèm lưới chắn côn trùng (LCCT) inox 304 (hậu tố `+N` nối vào sau) |
| `DDG+O+F`, `DDG+O+N`, `DDG+F+N`, `DDG+O+F+N` | tổ hợp |

Diễn giải trên BG: "Cửa nan bầu dục 2 lớp".

## 2. Hằng số

| Tên | Giá trị |
|---|---|
| `GIA_NHOM` | 155.000 đ/kg (bộ giá `BG-2026-11-13`; bộ gốc `BG-2026-10-20` là 150.000) |
| `GIA_SON` | 18.000 đ/kg (sơn tĩnh điện, tính theo kg nhôm khung + nan) |
| `PHU_KIEN` | 5.000 đ/cái (ke góc, vít) — cố định cho cửa 2 lớp |
| `HE_SO_BAN` | 1,25 (cửa), 1,15 (OBD) |
| Khung 2 lớp | 0,2547 kg/m dài chu vi |
| Nan bầu dục | 0,058 kg/m |

`round(x, -3)` = làm tròn **half-up** đến nghìn: `floor(x/1000 + 0.5) * 1000` (kiểu ROUND của Excel, không dùng làm tròn chẵn của banker).

## 3. Công thức đơn giá cửa (chưa phụ kiện)

Đầu vào: `W`, `H` = kích thước mặt phủ bì (mm).

```
D = max(50, W - 50)        # cổ, chiều ngang
E = max(50, H - 50)        # cổ, chiều dọc
N = W/1000;  O = H/1000;  d = D/1000;  e = E/1000   # đổi sang mét

n1 = max(1, round((e - 0.015) / 0.02))   # số nan lớp 1, mỗi nan dài d
n2 = max(1, round((d - 0.015) / 0.02))   # số nan lớp 2, mỗi nan dài e
                                         # round = half-up (Excel)

kg_khung = 2 * (N + O) * 0.2547
kg_nan   = (n1 * d + n2 * e) * 0.058

don_gia_chua_lam_tron = ( (kg_khung + kg_nan) * GIA_NHOM
                        + PHU_KIEN
                        + (kg_khung + kg_nan) * GIA_SON ) * 1.25

DON_GIA_CUA = round(don_gia_chua_lam_tron, -3)
```

### Cấu thành đơn giá (4 phần, trước khi làm tròn)

| Phần | Công thức | Ghi chú |
|---|---|---|
| Khung nhôm định hình 2 lớp | `kg_khung * GIA_NHOM * 1.25` | khung bao W×H, cổ D×E |
| Nan nhôm bầu dục | `kg_nan * GIA_NHOM * 1.25` | n1 + n2 nan |
| Phụ kiện lắp ghép | `5.000 * 1.25 = 6.250` | ke góc chìm, vít |
| Sơn tĩnh điện Polyester | `(kg_khung + kg_nan) * 18.000 * 1.25` | |

Tổng 4 phần = `don_gia_chua_lam_tron`. Phần chênh do làm tròn đến nghìn (nhỏ, dưới 500 đ) được phân bổ tỉ lệ đều vào 4 phần
(`scale = DON_GIA_CUA / don_gia_chua_lam_tron`). Nếu chỉ cần đơn giá tổng thì bỏ qua bước phân bổ.

### Ví dụ kiểm tra: DDG 600×300 → **273.000 đ/cái**

```
D=550, E=250 ; n1 = round(11.75)=12 ; n2 = round(26.75)=27
kg_khung = 2*(0.6+0.3)*0.2547            = 0.45846
kg_nan   = (12*0.55 + 27*0.25)*0.058     = 0.77430
tổng kg = 1.23276
khung  = 0.45846*155000*1.25 = 88.825
nan    = 0.77430*155000*1.25 = 150.013
phụ kiện                     =   6.250
sơn    = 1.23276*18000*1.25  =  27.737
cộng = 272.825 -> round(-3) = 273.000   (đã chạy MPrice, ra đúng 273.000)
```

## 4. Phần cộng thêm theo hậu tố (cộng vào đơn giá cửa)

Mỗi phần tự làm tròn `round(-3)` rồi **cộng** vào đơn giá cửa. Dùng cổ `D×E` (mét `d`, `e`) ở trên.

| Hậu tố | Công thức | Ví dụ 600×300 (D=550, E=250) |
|---|---|---|
| `+N` lưới chắn côn trùng inox 304 | `round(d*e * 150.000, -3)` | 0,1375 m² → 20.625 → **21.000** |
| `+F` lưới lọc bụi thô G4 kèm khung | `round(d*e * 200.000, -3)` | 27.500 → **28.000** |
| `+O` van OBD gắn cửa | xem dưới | → **142.000** |

**OBD gắn cửa** (nhôm, hệ số 1,15):

```
kg_khung_obd = 2 * (d + e) * 0.158
kg_nan_obd   = (d / 0.04) * e * 0.11
phu_kien_obd = (d / 0.04) * 1500 + 5000
OBD = round( ((kg_khung_obd + kg_nan_obd) * GIA_NHOM + phu_kien_obd) * 1.15, -3 )
```

Ví dụ 600×300: 0,2528 + 0,3781 = 0,6309 kg → 97.793 + 25.625 = 123.418 → ×1,15 = 141.931 → **142.000**.

> Các ví dụ `+N`, `+F`, `+O` ở bảng trên tớ tính tay từ công thức, **chưa chạy lại qua hệ thống MPrice** để đối chiếu. Chỉ ví dụ DDG trơn 273.000 đã được đối chiếu.
> Chưa kiểm tra ở đây việc có làm tròn thêm tổng cuối của dòng BG sau khi cộng các phần hay không.

## 5. Quy tắc liên quan khi dùng ở dự án MPrice (tham khảo, tùy Swind có áp hay không)

- Cửa **kèm hộp gió**, đối tác chưa báo giá hộp: cộng thêm hộp gió W×H×L200, tôn 0,58 mm (rule `OG-08`/`OG-09` trong `duct_rules.json`). Không có trong công thức trên.
- Bảo ôn hộp: +130.000 đ/m² (`OG-10`); sơn đen phía trong hộp: +10.000 đ/cái (`OG-14`).
- Giá nhôm đổi theo thời gian: đọc từ bộ giá có ngày hiệu lực, không hard-code 155.000.
- Cửa **khuếch tán** (không phải nan bầu dục): công thức khác, không dùng tài liệu này.
