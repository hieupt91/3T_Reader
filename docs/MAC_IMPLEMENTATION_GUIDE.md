# Tá»•ng há»£p Dá»± Ã¡n 3T Reader - Phase 1 (Báº£n Windows sang Mac)

## 1. Giá»›i thiá»‡u chung
Dá»± Ã¡n 3T Reader (Phase 1) lÃ  má»™t á»©ng dá»¥ng Ä‘á»c vÃ  xá»­ lÃ½ tÃ i liá»‡u PDF Ä‘a nÄƒng, há»— trá»£ kÃ½ sá»‘ Ä‘iá»‡n tá»­, kÃ½ sá»‘ USB Token chuáº©n LTV, OCR, trá»£ lÃ½ AI vÃ  cÆ¡ cháº¿ tá»± Ä‘á»™ng cáº­p nháº­t (OTA Update).
TÃ i liá»‡u nÃ y Ä‘Ã³ng vai trÃ² hÆ°á»›ng dáº«n chi tiáº¿t dÃ nh cho **Team Mac** Ä‘á»ƒ Ä‘áº£m báº£o báº£n Mac khi triá»ƒn khai sáº½ cÃ³ **Ä‘áº§y Ä‘á»§ 100% tÃ­nh nÄƒng vÃ  tráº£i nghiá»‡m tÆ°Æ¡ng Ä‘á»“ng vá»›i báº£n Windows** hiá»‡n táº¡i.

## 2. Kiáº¿n trÃºc vÃ  Giao diá»‡n UI
- **Framework cá»‘t lÃµi**: Sá»­ dá»¥ng **PySide6** (Qt6) lÃ m engine render giao diá»‡n. Cáº§n thiáº¿t káº¿ thanh Ribbon (Tab bar) phÃ­a trÃªn cÃ¹ng giá»‘ng há»‡t báº£n Win Ä‘á»ƒ táº¡o sá»± Ä‘á»“ng nháº¥t vá» máº·t thÆ°Æ¡ng hiá»‡u.
- **Theme**: Há»— trá»£ giao diá»‡n sÃ¡ng/tá»‘i tá»± Ä‘á»™ng (Dark/Light Mode) thÃ´ng qua thÆ° viá»‡n `pyqtdarktheme` hoáº·c CSS/QSS tuá»³ chá»‰nh.

## 3. CÃ¡c chá»©c nÄƒng chÃ­nh cáº§n Ä‘áº£m báº£o trÃªn Mac

### 3.1. Xem vÃ  thao tÃ¡c tÃ i liá»‡u
- **PDF Viewer Engine**: Sá»­ dá»¥ng thÆ° viá»‡n `pypdfium2` (vÃ  `pikepdf`) Ä‘á»ƒ render cÃ¡c trang PDF mÆ°á»£t mÃ  lÃªn mÃ n hÃ¬nh (Canvas). Cáº§n há»— trá»£ thu phÃ³ng (zoom), chuyá»ƒn trang, hiá»ƒn thá»‹ thumbnail.
- **Office Viewer**: Há»— trá»£ ngÆ°á»i dÃ¹ng má»Ÿ xem trá»±c tiáº¿p cÃ¡c file `.docx` vÃ  `.xlsx`. Giáº£i phÃ¡p: dÃ¹ng `pdf2docx` / `openpyxl` Ä‘á»ƒ phÃ¢n tÃ­ch dá»¯ liá»‡u, sau Ä‘Ã³ káº¿t xuáº¥t HTML vÃ  hiá»ƒn thá»‹ qua `PySide6.QtWebEngineWidgets`.

### 3.2. TÃ­nh nÄƒng KÃ½ sá»‘ (Digital Signature)
ÄÃ¢y lÃ  module cá»‘t lÃµi cá»±c ká»³ quan trá»ng, team Mac cáº§n lÆ°u Ã½ thá»±c hiá»‡n chÃ­nh xÃ¡c:
- **KÃ½ báº±ng file má»m (PFX/P12)**: Sá»­ dá»¥ng `pyHanko` Ä‘á»ƒ táº¡o chá»¯ kÃ½ PAdES lÃªn file PDF.
- **KÃ½ báº±ng USB Token / Smartcard**: 
  - Báº£n Windows Ä‘ang dÃ¹ng Certificate Store máº·c Ä‘á»‹nh qua CryptoAPI/SignerSignEx.
  - **TrÃªn Mac**: YÃªu cáº§u team Mac sá»­ dá»¥ng thÆ° viá»‡n `python-pkcs11` káº¿t há»£p module chia sáº» PKCS#11 (.dylib) cá»§a macOS Keychain, hoáº·c thÆ° viá»‡n API native cá»§a macOS Ä‘á»ƒ cÃ³ thá»ƒ gá»i chá»©ng thÆ° sá»‘ tá»« thiáº¿t bá»‹ USB Token.
- **TÃ­nh nÄƒng LTV (Long-Term Validation) vÃ  TSA (Time-Stamping Authority)**:
  - Cho phÃ©p tÃ­ch há»£p Timestamp khi kÃ½ (thÃ´ng qua TSA URL ngÆ°á»i dÃ¹ng cáº¥p).
  - TÃ­ch há»£p báº±ng chá»©ng thu há»“i (CRL/OCSP response) vÃ o bÃªn trong file PDF Ä‘á»ƒ xÃ¡c thá»±c LTV.
  - Sá»­ dá»¥ng module `pyhanko.sign.validation` vÃ  `pyhanko.network.requests` (Pháº£i náº¡p Ä‘áº§y Ä‘á»§ trong file build Ä‘á»ƒ trÃ¡nh lá»—i `ModuleNotFoundError`).
- **Tuá»³ chá»‰nh nháº­n diá»‡n chá»¯ kÃ½**: Hiá»ƒn thá»‹ hÃ¬nh váº½/logo con dáº¥u, vÃ¹ng kÃ©o tháº£ chá»¯ kÃ½, thÃ´ng tin ngÃ y giá», lÃ½ do kÃ½.
- **KÃ½ hÃ ng loáº¡t (Batch Signing)**: KÃ½ tá»± Ä‘á»™ng danh sÃ¡ch nhiá»u file PDF táº¡i má»™t thÆ° má»¥c (cáº§n xá»­ lÃ½ Ä‘a luá»“ng tá»‘t trÃªn Mac).

### 3.3. TÃ­nh nÄƒng In áº¥n áº£o (Virtual Printing)
- Gá»i há»™p thoáº¡i mÃ¡y in há»‡ thá»‘ng.
- Cáº§n cÃ³ ProgressBar hiá»ƒn thá»‹ tiáº¿n trÃ¬nh (Äang in trang 1 / N...). 
- Lá»‡nh in xong (truyá»n tá»‡p vÃ o bá»™ Ä‘á»‡m cá»§a CUPS thÃ nh cÃ´ng) pháº£i tá»± Ä‘á»™ng xoÃ¡ hoÃ n toÃ n ProgressBar Ä‘á»ƒ trÃ¡nh treo app. TrÃªn Mac sá»­ dá»¥ng module `QtPrintSupport` cá»§a PySide6.

### 3.4. TÃ­nh nÄƒng Nháº­n dáº¡ng kÃ½ tá»± quang há»c (OCR)
- DÃ¹ng `pytesseract` (trÃ¬nh bao bá»c cho Tesseract OCR engine).
- **YÃªu cáº§u trÃªn macOS**: YÃªu cáº§u ngÆ°á»i dÃ¹ng hoáº·c trÃ¬nh cÃ i Ä‘áº·t cung cáº¥p gÃ³i `tesseract` vÃ  `tesseract-lang` (thÆ°á»ng cÃ i qua Homebrew `brew install tesseract tesseract-lang`). Trong báº£n build cuá»‘i, team Mac nÃªn Ä‘Ã³ng gÃ³i tháº³ng cÃ¡c thÆ° viá»‡n nhá»‹ phÃ¢n (binary) tesseract vÃ o trong lÃµi App Bundle Ä‘á»ƒ ngÆ°á»i dÃ¹ng táº£i vá» lÃ  dÃ¹ng Ä‘Æ°á»£c luÃ´n khÃ´ng cáº§n gÃµ lá»‡nh cáº¥u hÃ¬nh phá»©c táº¡p.

### 3.5. Trá»£ lÃ½ TrÃ­ tuá»‡ NhÃ¢n táº¡o (AI Assistant)
- Há»— trá»£ trÃ² chuyá»‡n Ä‘a ná»n táº£ng API: OpenAI (ChatGPT), Anthropic (Claude), Google (Gemini).
- App sáº½ Ä‘á»c vÄƒn báº£n trong PDF báº±ng `pdfplumber` hoáº·c `pypdfium2`, sau Ä‘Ã³ truyá»n ngá»¯ cáº£nh cho AI Ä‘á»ƒ thá»±c hiá»‡n lá»‡nh: tÃ³m táº¯t, dá»‹ch thuáº­t, giáº£i nghÄ©a...

### 3.6. CÆ¡ cháº¿ tá»± Ä‘á»™ng cáº­p nháº­t (OTA Update)
- App tá»± Ä‘á»™ng gá»i Ä‘áº¿n file JSON tá»« backend server Ä‘á»ƒ kiá»ƒm tra báº£n má»›i.
- Format server cho Mac:
  ```json
  "update": {
    "mac_version": "1.0.0",
    "mac_url": "https://reader.3tcomputer.com/downloads/3T_Reader_v1.0.0.dmg",
    "mac_sha256": "...",
    "release_notes": "..."
  }
  ```
- **Xá»­ lÃ½ lÆ°u file log/download**: Khi táº£i file báº£n cáº­p nháº­t hoáº·c ghi file log lá»—i (`error_log.txt`), **tuyá»‡t Ä‘á»‘i khÃ´ng ghi cá»©ng (hardcode) vÃ o thÆ° má»¥c Application**. Thay vÃ o Ä‘Ã³ pháº£i dÃ¹ng thÆ° má»¥c Temp cá»¥c bá»™ an toÃ n `os.path.join(tempfile.gettempdir(), "tÃªn_file")` Ä‘á»ƒ khÃ´ng bá»‹ macOS cháº·n quyá»n (PermissionError).

## 4. Danh sÃ¡ch ThÆ° viá»‡n lÃµi (Dependencies)
Team Mac cáº§n dÃ¹ng file `requirements.txt` sau lÃ m cÆ¡ sá»Ÿ chuáº©n Ä‘á»ƒ Ä‘á»“ng bá»™ thÆ° viá»‡n:
- `PySide6==6.11.0`
- `pyqtdarktheme==0.1.7`
- `pypdfium2==5.7.0`
- `pikepdf==10.5.1`
- `pyHanko==0.34.1`
- `python-pkcs11==0.9.4`
- `cryptography==46.0.7`
- `Pillow==12.2.0`
- `requests==2.33.1`
- `pytesseract==0.3.13`
- `pdf2docx==0.5.13`
- `pdfplumber==0.11.9`
- `openpyxl==3.1.5`
- CÃ¡c gÃ³i AI: `openai`, `anthropic`, `google-genai`, `keyring` (quáº£n lÃ½ khoÃ¡ báº£o máº­t Keychain trÃªn Mac).

## 5. ChÃº Ã½ Ä‘áº·c biá»‡t khi ÄÃ³ng gÃ³i (PyInstaller / py2app)
Khi Ä‘Ã³ng gÃ³i thÃ nh á»©ng dá»¥ng macOS (`.app` rá»“i chuyá»ƒn sang `.dmg`), team Mac cáº§n cáº¥u hÃ¬nh cáº©n tháº­n cÃ¡c import áº©n (hidden imports). Náº¿u thiáº¿u, á»©ng dá»¥ng sáº½ cháº¡y lá»—i trÃªn mÃ¡y khÃ¡ch:
- `pypdfium2`, `pikepdf`, `pyhanko`
- `pyhanko.network`, `pyhanko.network.requests`
- `PySide6.QtPrintSupport`, `PySide6.QtWebEngineWidgets`

*(Vui lÃ²ng tham kháº£o tá»‡p `3T_Reader.spec` táº¡i nhÃ¡nh chÃ­nh lÃ m cÆ¡ sá»Ÿ cáº¥u hÃ¬nh PyInstaller).*

---
**ChÃºc Team Mac hoÃ n thÃ nh viá»‡c chuyá»ƒn Ä‘á»•i xuáº¥t sáº¯c!** Má»i tháº¯c máº¯c hÃ£y tham kháº£o mÃ£ nguá»“n trá»±c tiáº¿p trong kho lÆ°u trá»¯ (Repository) nÃ y.


## 9. Critical Optimizations for Large PDFs (100MB+)
- **Viewing Large PDFs:** Do NOT load the entire PDF into memory/RAM for display normalisation if the file is large. In the Windows version, we skip signature widget normalisation for files >30MB and use direct HTTP Range requests to stream the file straight from the disk to the PDF.js webview. This prevents memory exhaustion and black screens.
- **Burning Visual Stamps:** When burning a visual representation (raster image) of a stamp or signature into the PDF document (e.g. using PyMuPDF itz), do NOT rewrite the entire PDF file. Copy the original file first, and use incremental=True to append the stamp. This saves tremendous time (e.g. fractions of a second instead of 10+ seconds for 100MB+ files) and critically, it preserves the integrity of previously existing digital signatures.
- **Invisible PyHanko Widget:** When stamping a new visual signature using PyMuPDF, pass the coordinates of the stamped box to the digital signer (e.g. PyHanko) and instruct it to create a completely transparent interactive Widget (NoOpStampStyle) exactly over the image. This ensures the user can click on the stamped image to verify signature details, without drawing an ugly default text string over the beautiful image.
