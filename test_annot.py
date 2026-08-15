import pikepdf
pdf = pikepdf.Pdf.new()
page = pdf.add_blank_page()
annot = pikepdf.Dictionary(
    Type=pikepdf.Name("/Annot"),
    Subtype=pikepdf.Name("/FreeText"),
    Rect=[100, 100, 200, 200],
    Contents="1",
    DA="/Helv 12 Tf 0 g", # Default Appearance
    F=4, # Print
    T="3T_PageNum"
)
page.Annots = pdf.make_indirect([annot])
pdf.save("test_annot.pdf")
