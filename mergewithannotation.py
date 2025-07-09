import os
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor
import io
import pikepdf

# ====== Step 1: Minta input folder ======
input_dir = input("Masukkan path folder PDF: ").strip()

# Ambil dan urutkan file PDF
pdf_files = sorted(
    [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')],
    key=lambda x: int(x.split(".")[0]) if x.split(".")[0].isdigit() else x
)

# Buat daftar file full path + judul (pakai nama file tanpa .pdf)
pdf_list = []
for filename in pdf_files:
    full_path = os.path.join(input_dir, filename)
    title = os.path.splitext(filename)[0]
    pdf_list.append( (full_path, title) )

if not pdf_list:
    print("❌ Tidak ada file PDF ditemukan di folder!")
    exit()

# ====== Step 2: Hitung halaman target ======
page_offset = 1
toc_entries = []
total_pages = page_offset
for file, title in pdf_list:
    reader = PdfReader(file)
    toc_entries.append((title, total_pages))
    total_pages += len(reader.pages)

# ====== Step 3: Buat halaman TOC ======
packet = io.BytesIO()
can = canvas.Canvas(packet, pagesize=A4)
width, height = A4

# Header TOC
can.setFont("Helvetica-Bold", 18)
can.drawString(50, height - 50, "📑 Daftar Isi")

can.setFont("Helvetica", 12)
y = height - 90
link_rects = []

for title, page in toc_entries:
    text = title

    # Judul berwarna biru
    can.setFillColor(HexColor("#1a73e8"))
    text_y = y
    can.drawString(50, text_y, text)

    # Garis putus-putus sejajar
    can.setStrokeColor(HexColor("#000000"))
    can.setDash(1, 2)
    text_width = can.stringWidth(text, "Helvetica", 12)
    start_x = 50 + text_width + 5
    end_x = width - 50 - 20
    line_y = text_y + 3
    can.line(start_x, line_y, end_x, line_y)
    can.setDash()

    # Nomor halaman di kanan
    can.setFillColor(HexColor("#000000"))
    can.drawRightString(width - 50, text_y, str(page))

    # Simpan rect link
    link_rects.append((title, page, (50, text_y - 2, end_x, text_y + 12)))
    y -= 22

can.showPage()
can.save()
packet.seek(0)

# ====== Step 4: Gabungkan TOC + semua PDF jadi temp.pdf ======
writer = PdfWriter()

# Tambahkan halaman TOC
toc_pdf = PdfReader(packet)
writer.add_page(toc_pdf.pages[0])

# Tambahkan semua PDF + bookmark
current_page = 1
for filepath, title in pdf_list:
    reader = PdfReader(filepath)
    for page in reader.pages:
        writer.add_page(page)
    writer.add_outline_item(title, current_page)
    current_page += len(reader.pages)

temp_pdf_path = "temp.pdf"
with open(temp_pdf_path, "wb") as f:
    writer.write(f)

print(f"✅ Berhasil menggabungkan PDF!")

# ====== Step 5: Tambahkan link annotation ke TOC ======
folder_name = os.path.basename(os.path.normpath(input_dir))
output_file = f"{folder_name}_merged.pdf"
with pikepdf.open(temp_pdf_path) as pdf:
    toc_page = pdf.pages[0]

    for title, target_page, rect in link_rects:
        action = pdf.make_indirect({
            '/S': pikepdf.Name('/GoTo'),
            '/D': [target_page, pikepdf.Name('/Fit')]
        })
        link = pdf.make_indirect({
            '/Type': pikepdf.Name('/Annot'),
            '/Subtype': pikepdf.Name('/Link'),
            '/Rect': list(rect),
            '/Border': [0, 0, 0],
            '/A': action
        })

        if '/Annots' in toc_page:
            toc_page.Annots.append(link)
        else:
            toc_page.Annots = pdf.make_indirect([link])

    pdf.save(output_file)

    # Hapus temp file
    os.remove(temp_pdf_path)

print(f"🎉 Selesai! File output: {output_file}")
