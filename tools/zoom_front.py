import fitz

# Zoom in on front views of SWIND-1.04 and SWIND-1.05
doc104 = fitz.open("HSKT/kDCC- SWIND-1.04-MFD-EI60 HoneyWell - MFD 1700x1000x200.pdf")
doc105 = fitz.open("HSKT/KDCC- SWIND-1.05-MFD-EI120.pdf")

p104 = doc104[4]
p105 = doc105[4]

# Crop the front elevation box
# x: 0.10 to 0.65, y: 0.10 to 0.45
w4, h4 = p104.rect.width, p104.rect.height
rect4 = fitz.Rect(0.08 * w4, 0.10 * h4, 0.65 * w4, 0.45 * h4)
p104.get_pixmap(dpi=300, clip=rect4).save("scratch/elevations/zoom_104_front.png")

w5, h5 = p105.rect.width, p105.rect.height
rect5 = fitz.Rect(0.08 * w5, 0.10 * h5, 0.65 * w5, 0.45 * h5)
p105.get_pixmap(dpi=300, clip=rect5).save("scratch/elevations/zoom_105_front.png")

print("Saved zoomed crops!")
