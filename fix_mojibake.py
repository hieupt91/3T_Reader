import sys
with open('app/window.py', 'r', encoding='utf-8') as f:
    text = f.read()

fixed = []
for char in text:
    try:
        # Try to encode back to cp1252, if it fails it's a normal char or actual unicode
        cp_bytes = char.encode('cp1252')
        fixed.append(cp_bytes)
    except UnicodeEncodeError:
        # If it's something that can't be encoded as cp1252, it must be something else,
        # but the Windows team saved it as UTF-8, so any non-ascii that survived means
        # it was already messed up or it's genuine unicode that didn't get corrupted?
        # Actually, if they opened UTF-8 as cp1252 and saved as UTF-8, ALL characters
        # in cp1252 map to UTF-8. So encode('cp1252') should succeed for all corrupted chars!
        fixed.append(char.encode('utf-8'))

# Wait, the problem is they opened a UTF-8 file (bytes) using cp1252 decoding -> text
# Then they saved that text as UTF-8.
# So to reverse: read the text, encode it as cp1252 -> bytes, decode as UTF-8 -> correct text!

def fix_text(t):
    try:
        b = t.encode('cp1252')
        return b.decode('utf-8')
    except Exception:
        return t

# But wait, python code contains ASCII chars. They are unchanged.
# Can we just encode the WHOLE text as cp1252 and decode as utf-8?
