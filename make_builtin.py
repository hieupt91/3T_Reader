import json
import urllib.request

def fetch(code):
    req = urllib.request.Request(
        f"https://reader.3tcomputer.com/downloads/language/{code}.json",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    with urllib.request.urlopen(req) as resp:
        return json.load(resp)["strings"]

try:
    en_dict = fetch("en")
    vi_dict = fetch("vi")
    
    with open("app/language_manager.py", "r", encoding="utf-8") as f:
        text = f.read()
    
    # We will replace BUILTIN_TRANSLATIONS
    start = text.find("BUILTIN_TRANSLATIONS = {")
    end = text.find("def language_pack_dir()")
    
    new_dict_str = "BUILTIN_TRANSLATIONS = {\n"
    
    new_dict_str += '    "vi": {\n'
    for k, v in vi_dict.items():
        new_dict_str += f'        "{k}": "{v}",\n'
    new_dict_str += '    },\n'
    
    new_dict_str += '    "en": {\n'
    for k, v in en_dict.items():
        new_dict_str += f'        "{k}": "{v}",\n'
    new_dict_str += '    }\n}\n\n'
    
    new_text = text[:start] + new_dict_str + text[end:]
    
    with open("app/language_manager.py", "w", encoding="utf-8") as f:
        f.write(new_text)
        
    print("Embedded full en and vi into BUILTIN_TRANSLATIONS")
except Exception as e:
    print(e)
