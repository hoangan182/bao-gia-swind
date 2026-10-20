import fitz  # PyMuPDF
import subprocess
import os
import glob
import json

def ocr_page(pix_path):
    res = subprocess.run(["./tools/ocr_vision", pix_path], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return res.stdout

pdf_files = sorted(glob.glob("HSKT/*.pdf"))
os.makedirs("scratch/page_images", exist_ok=True)
os.makedirs("scratch/ocr_results", exist_ok=True)

for pdf_path in pdf_files:
    pdf_name = os.path.basename(pdf_path)
    print(f"=== Processing {pdf_name} ===")
    doc = fitz.open(pdf_path)
    print(f"Total pages: {len(doc)}")
    
    # We examine pages 0 to 15
    max_p = min(15, len(doc))
    results = {}
    for p_idx in range(max_p):
        page = doc[p_idx]
        pix = page.get_pixmap(dpi=150)
        img_path = f"scratch/page_images/{pdf_name}_p{p_idx+1}.png"
        pix.save(img_path)
        
        text = ocr_page(img_path)
        results[p_idx+1] = {
            "image": img_path,
            "text": text
        }
        # Print first few lines or keywords found
        lines = [l.strip() for l in text.split("\n") if l.strip()]
        keywords = []
        for l in lines:
            lu = l.upper()
            if any(k in lu for k in ["PHỤ LỤC", "TÓM TẮT", "MÔ TẢ", "2.1", "2.2", "2.3", "BẢN VẼ", "KẾT CẤU"]):
                keywords.append(l)
        print(f"  Page {p_idx+1}: {len(lines)} lines. Hits: {keywords[:3]}")
    
    # Save raw ocr results for this pdf
    json_path = f"scratch/ocr_results/{pdf_name}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"Saved OCR to {json_path}")
