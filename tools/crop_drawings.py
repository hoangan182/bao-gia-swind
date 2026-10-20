import fitz
import os, glob

# Render Page 5 of all 6 PDFs at 300 DPI
pdf_files = sorted(glob.glob("HSKT/*.pdf"))
os.makedirs("scratch/drawing_crops", exist_ok=True)

for pdf_path in pdf_files:
    fname = os.path.basename(pdf_path)
    base = os.path.splitext(fname)[0]
    doc = fitz.open(pdf_path)
    
    # Page 5 is index 4
    if len(doc) >= 5:
        page = doc[4]
        # render full page at 300 dpi
        pix = page.get_pixmap(dpi=300)
        pix.save(f"scratch/drawing_crops/{base}_p5_300dpi.png")
        
        # Crop upper area (drawing itself): top 60% of page
        # In fitz: rect is (x0, y0, x1, y1)
        w, h = page.rect.width, page.rect.height
        
        # Top drawing area
        rect_drawing = fitz.Rect(0, 0.08 * h, w, 0.65 * h)
        pix_draw = page.get_pixmap(dpi=300, clip=rect_drawing)
        pix_draw.save(f"scratch/drawing_crops/{base}_drawing_area.png")
        
        # Bottom specs table
        rect_table = fitz.Rect(0, 0.55 * h, w, 0.95 * h)
        pix_table = page.get_pixmap(dpi=300, clip=rect_table)
        pix_table.save(f"scratch/drawing_crops/{base}_specs_table.png")
        
print("Rendered 300 DPI crops successfully!")
