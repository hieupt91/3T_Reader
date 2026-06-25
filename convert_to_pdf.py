import os
import sys

# Try docx2pdf first
try:
    from docx2pdf import convert
except ImportError:
    os.system('pip install docx2pdf')
    try:
        from docx2pdf import convert
    except ImportError:
        print("Failed to install docx2pdf")
        sys.exit(1)

docs_dir = r"docs\Ho_So_Phap_Ly"
files_to_convert = [
    "BAN_MO_TA_PHAN_MEM.docx",
    "EVALUATION_BAN_QUYEN.docx",
    "HUONG_DAN_SU_DUNG_PHAN_MEM.docx",
    "MA_NGUON_50_TRANG_DAU_VA_CUOI.docx"
]

for filename in files_to_convert:
    docx_path = os.path.join(docs_dir, filename)
    if os.path.exists(docx_path):
        pdf_path = docx_path.replace(".docx", ".pdf")
        print(f"Converting {filename} to PDF...")
        try:
            convert(docx_path, pdf_path)
            print(f"Success: {pdf_path}")
        except Exception as e:
            print(f"Error converting {filename}: {e}")
    else:
        print(f"Warning: {filename} not found.")

