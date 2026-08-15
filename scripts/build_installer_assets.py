"""Tạo ảnh wizard cho Inno Setup (installer_script.iss) từ asset thương hiệu
sẵn có (assets/brand_appicon_512.png, assets/icon_128.png) - không cần thiết
kế viên, giữ đồng nhất màu cam thương hiệu (#FF7700 -> #FF4400) đã dùng
xuyên suốt UI (xem app/license_dialog.py, app/about_dialog.py).

Chạy 1 lần khi cần cập nhật lại ảnh wizard: python scripts/build_installer_assets.py
"""
from __future__ import annotations

import os
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
OUT_DIR = ASSETS_DIR / "installer"

_BRAND_ORANGE_LIGHT = (255, 246, 238)  # nền gradient nhạt, đồng tông brand_appicon
_BRAND_WHITE = (255, 255, 255)
_BRAND_NAVY = (15, 32, 66)  # khớp màu "READER" trong brand_appicon_512.png
_BRAND_ORANGE = (255, 119, 0)  # #FF7700, dùng xuyên suốt UI


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont:
    candidates = [
        r"C:\Windows\Fonts\segoeuib.ttf" if bold else r"C:\Windows\Fonts\segoeui.ttf",
        r"C:\Windows\Fonts\arialbd.ttf" if bold else r"C:\Windows\Fonts\arial.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return ImageFont.truetype(path, size)
    return ImageFont.load_default()


def _pdf_3t_logo(side: int) -> Image.Image:
    """Use the supplied PDF-3T artwork, trimmed for a small Windows icon."""
    logo = Image.open(OUT_DIR / "pdf_3t_logo.png").convert("RGBA")
    logo = logo.crop((145, 30, 1110, 1165))
    logo.thumbnail((side, side), Image.LANCZOS)
    return logo


def _master_3t_logo(width: int) -> Image.Image:
    """Prepare the supplied 3T logo for the pale installer sidebar."""
    image = Image.open(OUT_DIR / "logo_3t_master.png").convert("RGBA")
    image = image.crop((115, 250, 920, 805))
    pixels = image.load()
    for y in range(image.height):
        for x in range(image.width):
            r, g, b, _ = pixels[x, y]
            # Remove the neutral charcoal studio backdrop but preserve the
            # saturated orange/blue mark and its coloured highlights.
            spread = max(r, g, b) - min(r, g, b)
            brightness = max(r, g, b)
            if spread < 30 and brightness < 125:
                alpha = max(0, min(255, (brightness - 25) * 3))
                pixels[x, y] = (r, g, b, alpha)
    image.thumbnail((width, width), Image.LANCZOS)
    return image


def _vertical_gradient(size: tuple[int, int], top: tuple[int, int, int], bottom: tuple[int, int, int]) -> Image.Image:
    w, h = size
    img = Image.new("RGB", (1, h))
    for y in range(h):
        t = y / max(1, h - 1)
        r = round(top[0] + (bottom[0] - top[0]) * t)
        g = round(top[1] + (bottom[1] - top[1]) * t)
        b = round(top[2] + (bottom[2] - top[2]) * t)
        img.putpixel((0, y), (r, g, b))
    return img.resize((w, h))


def build_wizard_large() -> None:
    """164x314 - ảnh lớn hiện ở trang Welcome/Finish (WizardImageFile)."""
    w, h = 164, 314
    canvas = _vertical_gradient((w, h), _BRAND_WHITE, _BRAND_ORANGE_LIGHT).convert("RGB")

    logo = _master_3t_logo(132)
    logo_w, logo_h = logo.size
    logo_x = (w - logo_w) // 2
    logo_y = 56
    canvas.paste(logo, (logo_x, logo_y), logo)

    draw = ImageDraw.Draw(canvas)
    tagline = "Đọc mọi lúc\nHiểu mọi nơi"
    font = _font(13, bold=True)
    ty = logo_y + logo_h + 18
    for line in tagline.split("\n"):
        bbox = draw.textbbox((0, 0), line, font=font)
        tw = bbox[2] - bbox[0]
        draw.text(((w - tw) / 2, ty), line, fill=_BRAND_NAVY, font=font)
        ty += (bbox[3] - bbox[1]) + 8

    # Thanh nhấn màu cam ở đáy - nhắc thương hiệu, đồng bộ gradient dùng trong app.
    bar_h = 6
    for x in range(w):
        t = x / max(1, w - 1)
        r = round(_BRAND_ORANGE[0] * (1 - t) + 0xFF * t)
        g = round(_BRAND_ORANGE[1] * (1 - t) + 0x44 * t)
        b = round(_BRAND_ORANGE[2] * (1 - t) + 0x00 * t)
        draw.line([(x, h - bar_h), (x, h)], fill=(r, g, b))

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT_DIR / "wizard_large.bmp", "BMP")
    print("wrote", OUT_DIR / "wizard_large.bmp")


def build_wizard_small() -> None:
    """55x58 - icon nhỏ góc trên các trang wizard còn lại (WizardSmallImageFile)."""
    w, h = 55, 58
    canvas = Image.new("RGB", (w, h), _BRAND_WHITE)

    side = min(w, h) - 4
    icon = _pdf_3t_logo(side)
    canvas.paste(icon, ((w - side) // 2, (h - side) // 2), icon)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    canvas.save(OUT_DIR / "wizard_small.bmp", "BMP")
    print("wrote", OUT_DIR / "wizard_small.bmp")


def build_feature_slides() -> None:
    """Ảnh feature carousel hiện trong lúc cài (trang Installing) - mỗi slide
    1 icon feat_*.png + chú thích, dùng trong [Code] custom slideshow."""
    slides = [
        ("feat_pdf.png", "Đọc & chỉnh sửa PDF mượt mà"),
        ("feat_read.png", "Đọc mọi lúc, hiểu mọi nơi"),
        ("feat_secure.png", "Ký số & bảo mật tài liệu"),
        ("feat_sync.png", "Đồng bộ & chia sẻ nhanh chóng"),
    ]
    w, h = 380, 138
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    font = _font(18, bold=True)

    for idx, (icon_name, caption) in enumerate(slides, start=1):
        canvas = _vertical_gradient((w, h), (255, 255, 255), (255, 244, 235)).convert("RGB")
        draw = ImageDraw.Draw(canvas)
        draw.rounded_rectangle((8, 8, w - 8, h - 8), radius=14, fill=(255, 255, 255), outline=(255, 211, 180), width=1)

        icon = Image.open(ASSETS_DIR / icon_name).convert("RGBA")
        icon = icon.resize((88, 88), Image.LANCZOS)
        canvas.paste(icon, (22, (h - 88) // 2), icon)

        bbox = draw.textbbox((0, 0), caption, font=font)
        tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        draw.text((126, (h - th) / 2 - bbox[1]), caption, fill=_BRAND_NAVY, font=font)

        path = OUT_DIR / f"feature_slide_{idx}.bmp"
        canvas.save(path, "BMP")
        print("wrote", path)


if __name__ == "__main__":
    build_wizard_large()
    build_wizard_small()
    build_feature_slides()
