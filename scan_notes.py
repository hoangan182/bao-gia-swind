import openpyxl
import glob

file_path = glob.glob("data/projects/Copy of BG01.2_SLAND_NAMVIET*.xlsx")[0]
wb = openpyxl.load_workbook(file_path, data_only=True)

unique_notes = set()

for sheet_name in wb.sheetnames:
    ws = wb[sheet_name]
    for r in range(1, ws.max_row + 1):
        # We assume the note is in the last few columns
        for c in range(max(1, ws.max_column - 5), ws.max_column + 1):
            val = ws.cell(r, c).value
            if isinstance(val, str):
                val_clean = val.strip()
                if len(val_clean) > 20 and not val_clean.isnumeric():
                    # Filter out standard descriptions that are just item names
                    if "Tole" in val_clean or "tiêu chuẩn" in val_clean.lower() or "bích" in val_clean.lower() or "tôn" in val_clean.lower() or "bctn" in val_clean.lower() or "sản xuất" in val_clean.lower():
                        unique_notes.add(val_clean)

for idx, note in enumerate(unique_notes):
    print(f"--- Note {idx+1} ---")
    print(note)
    print("-" * 20)
