"""Extract brand assets from the brand design sheet."""
from PIL import Image
import os

src = r"C:\Users\HieuPC\Downloads\My Documents [21-05-2026 21_06]\6066af8744a1c5ff9cb0.jpg"
out_dir = r"C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\assets"

img = Image.open(src)
W, H = img.size
print(f"Image size: {W}x{H}")

# The brand sheet layout (estimated from visual inspection):
# Top-left ~55%: large app icon with rounded corners
# Top-right ~45%: brand text + 4 feature icons
# Bottom half: icon variants + size grid

# ---- 1. Main app icon (top-left large rounded square) ----
# Roughly occupies left 52% width, top 58% height with some padding
icon_main = img.crop((
    int(W * 0.02),   # left
    int(H * 0.02),   # top
    int(W * 0.52),   # right
    int(H * 0.60),   # bottom
))
icon_main.save(os.path.join(out_dir, "brand_icon_main.png"))
print(f"Saved brand_icon_main.png  {icon_main.size}")

# ---- 2. Brand logo horizontal (top-right: "3T READER" text + tagline + 4 icons) ----
brand_banner = img.crop((
    int(W * 0.54),   # left
    int(H * 0.02),   # top
    int(W * 0.98),   # right
    int(H * 0.48),   # bottom
))
brand_banner.save(os.path.join(out_dir, "brand_banner.png"))
print(f"Saved brand_banner.png  {brand_banner.size}")

# ---- 3. Four feature icons row (right side of brand sheet) ----
# The 4 icons (book, pdf, cloud, shield) are roughly at y: 32%–48% of height
# and spread across x: 55%–99% in 4 columns
feat_y0 = int(H * 0.30)
feat_y1 = int(H * 0.50)
feat_x0 = int(W * 0.545)
feat_x1 = int(W * 0.990)
feat_row = img.crop((feat_x0, feat_y0, feat_x1, feat_y1))
feat_row.save(os.path.join(out_dir, "brand_features_row.png"))
print(f"Saved brand_features_row.png  {feat_row.size}")

fw = feat_x1 - feat_x0
col_w = fw // 4

labels = ["feat_read", "feat_pdf", "feat_sync", "feat_secure"]
for i, name in enumerate(labels):
    x0 = feat_x0 + i * col_w
    x1 = feat_x0 + (i + 1) * col_w
    icon = img.crop((x0, feat_y0, x1, feat_y1))
    # Resize to 88x88 for use in UI cards
    icon_resized = icon.resize((88, 88), Image.LANCZOS)
    path = os.path.join(out_dir, f"{name}.png")
    icon_resized.save(path)
    print(f"Saved {name}.png  {icon.size} -> 88x88")

# ---- 4. Full app icon cropped to square (just the icon, no padding) ----
# Tight crop of the rounded square icon
icon_tight = img.crop((
    int(W * 0.04),
    int(H * 0.03),
    int(W * 0.50),
    int(H * 0.58),
))
# Make it square
s = min(icon_tight.size)
icon_square = icon_tight.resize((512, 512), Image.LANCZOS)
icon_square.save(os.path.join(out_dir, "brand_appicon_512.png"))
print(f"Saved brand_appicon_512.png  512x512")

print("Done.")
