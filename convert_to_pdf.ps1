$word = New-Object -ComObject Word.Application
$word.Visible = $false
$docsDir = "C:\Users\HieuPC\Desktop\3T_Reader_Phase1_Win\docs\Ho_So_Phap_Ly"
$files = @("BAN_MO_TA_PHAN_MEM.docx", "EVALUATION_BAN_QUYEN.docx", "HUONG_DAN_SU_DUNG_PHAN_MEM.docx")

foreach ($file in $files) {
    $docxPath = Join-Path $docsDir $file
    $pdfPath = $docxPath -replace "\.docx$", ".pdf"
    
    if (Test-Path $docxPath) {
        Write-Host "Converting $file to PDF..."
        $doc = $word.Documents.Open($docxPath)
        $doc.SaveAs($pdfPath, 17) # 17 is wdFormatPDF
        $doc.Close()
        Write-Host "Done: $pdfPath"
    } else {
        Write-Host "File not found: $docxPath"
    }
}
$word.Quit()
