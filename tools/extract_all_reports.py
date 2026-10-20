import json, glob, os
import fitz

pdf_files = sorted(glob.glob("HSKT/*.pdf"))
os.makedirs("scratch/drawings", exist_ok=True)

for pdf_path in pdf_files:
    fname = os.path.basename(pdf_path)
    base = os.path.splitext(fname)[0]
    json_path = f"scratch/ocr_results/{fname}.json"
    
    print("="*80)
    print(f"REPORT: {base}")
    print("="*80)
    
    with open(json_path, encoding="utf-8") as f:
        ocr_data = json.load(f)
        
    doc = fitz.open(pdf_path)
    
    # Save drawings (pages 4 and 5, and 6 if relevant)
    for p_num in [4, 5, 6]:
        if p_num <= len(doc):
            page = doc[p_num - 1]
            pix = page.get_pixmap(dpi=200)
            img_out = f"scratch/drawings/{base}_page_{p_num}.png"
            pix.save(img_out)
            
    # Print Pages 1, 2, 3, 4, 5 text summary
    for p in [1, 2, 3, 4, 5]:
        p_str = str(p)
        if p_str in ocr_data:
            lines = [l.strip() for l in ocr_data[p_str]["text"].split("\n") if l.strip()]
            print(f"--- PAGE {p} ({len(lines)} lines) ---")
            for l in lines:
                # filter out standard institutional address headers to keep it clean
                if any(k in l for k in ["BỘ XÂY DỰNG", "VIỆN VẬT LIỆU XÂY DỰNG", "VILAS 003", "TRUNG TÂM MÔI TRƯỜNG", "235 đường Nguyễn Trãi", "Fax: (+84)", "Website: http://vibm.vn"]):
                    continue
                if p == 5 and "2.3" in l:
                    print(f"   [STOPPING AT 2.3] {l}")
                    break
                print(f"   {l}")
