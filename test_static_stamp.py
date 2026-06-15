import base64
from pyhanko.stamp import StaticStampStyle
with open("transparent.png", "wb") as f:
    f.write(base64.b64decode(b"iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII="))
from PIL import Image
img = Image.open("transparent.png")
try:
    s = StaticStampStyle(background=img, border_width=0)
    print("Success with PIL Image!")
except Exception as e:
    print("Failed with PIL Image:", e)
