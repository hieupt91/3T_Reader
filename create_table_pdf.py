from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle
from reportlab.lib import colors

doc = SimpleDocTemplate("table_test.pdf", pagesize=letter)
data = [['Column 1', 'Column 2', 'Column 3'],
        ['1', '2', '3'],
        ['4', '5', '6'],
        ['7', '8', '9']]
t = Table(data)
t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,0),colors.grey),
                       ('TEXTCOLOR',(0,0),(-1,0),colors.whitesmoke),
                       ('ALIGN',(0,0),(-1,-1),'CENTER'),
                       ('FONTNAME', (0,0), (-1,0), 'Helvetica-Bold'),
                       ('FONTSIZE', (0,0), (-1,0), 14),
                       ('BOTTOMPADDING', (0,0), (-1,0), 12),
                       ('BACKGROUND',(0,1),(-1,-1),colors.beige),
                       ('GRID',(0,0),(-1,-1),1,colors.black)]))
doc.build([t])
