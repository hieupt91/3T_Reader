
import re
with open('app/window.py', 'r', encoding='utf-8') as f:
    data = f.read()
data = re.sub(
    r'self\.viewer\._web_view\.page\(\)\.runJavaScript\(\"window\.__3tExistingTextMode = false;\"\)\n\s*if hasattr\(self, \"_existing_text_bridge\"\):\n\s*from app\.webchannel import unregister_webchannel_object\n\s*unregister_webchannel_object\(self\.viewer\._web_view, \"editExistingTextBridge\"\)\n\s*self\._existing_text_bridge = None\n',
    '', data
)
with open('app/window.py', 'w', encoding='utf-8') as f:
    f.write(data)

