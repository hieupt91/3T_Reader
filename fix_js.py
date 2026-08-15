
import re
with open('assets/js/pdfjs_ui_hooks.js', 'r', encoding='utf-8') as f:
    data = f.read()

pattern = r'// --- Hook for editing existing text ---.*?document\.addEventListener\(\'click\'.*?\}, true\);'
data = re.sub(pattern, '', data, flags=re.DOTALL)

with open('assets/js/pdfjs_ui_hooks.js', 'w', encoding='utf-8') as f:
    f.write(data)

