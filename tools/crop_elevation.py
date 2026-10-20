import fitz
import os, glob

# Crop damper elevation and section from page 5 for each report
pdf_files = sorted(glob.glob("HSKT/*.pdf"))
os.makedirs("scratch/elevations", exist_ok=True)

for pdf_path in pdf_files:
    fname = os.path.basename(pdf_path)
    base = os.path.splitext(fname)[0]
    doc = fitz.open(pdf_path)
    if len(doc) >= 5:
        page = doc[4]
        w, h = page.rect.width, page.rect.height
        
        # In page 5, the damper drawing is usually in the top half:
        # x from 0.05*w to 0.95*w, y from 0.10*h to 0.50*h
        rect_elev = fitz.Rect(0.05 * w, 0.08 * h, 0.95 * w, 0.50 * h)
        pix = page.get_pixmap(dpi=300, clip=rect_elev)
        pix.save(f"scratch/elevations/{base}_elevation.png")
        
        # Detail / Section view: usually around right side or middle
        rect_sect = fitz.Rect(0.50 * w, 0.20 * h, 0.95 * w, 0.55 * h)
        pix_s = page.get_pixmap(dpi=300, clip=rect_sect)
        pix_s.save(f"scratch/elevations/{base}_section.png")

print("Cropped elevations and sections successfully!")
