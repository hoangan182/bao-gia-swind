import fitz

doc104 = fitz.open("HSKT/kDCC- SWIND-1.04-MFD-EI60 HoneyWell - MFD 1700x1000x200.pdf")
p104 = doc104[4]
w4, h4 = p104.rect.width, p104.rect.height

# Section 1 is on the right side: x from 0.60 to 0.95, y from 0.10 to 0.45
rect_sec = fitz.Rect(0.60 * w4, 0.10 * h4, 0.98 * w4, 0.45 * h4)
p104.get_pixmap(dpi=300, clip=rect_sec).save("scratch/elevations/zoom_104_section.png")

doc105 = fitz.open("HSKT/KDCC- SWIND-1.05-MFD-EI120.pdf")
p105 = doc105[4]
w5, h5 = p105.rect.width, p105.rect.height
rect_sec5 = fitz.Rect(0.60 * w5, 0.10 * h5, 0.98 * w5, 0.45 * h5)
p105.get_pixmap(dpi=300, clip=rect_sec5).save("scratch/elevations/zoom_105_section.png")

print("Saved zoomed sections!")
