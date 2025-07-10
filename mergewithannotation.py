import os
import re
import io
import tempfile
from PyPDF2 import PdfReader, PdfWriter
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import HexColor
import pikepdf

def natural_key(s):
    return [int(text) if text.isdigit() else text.lower()
            for text in re.split(r'(\d+)', s)]

input_dir = input("Masukkan path folder PDF: ").strip()

pdf_files = sorted(
    [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')],
    key=natural_key
)

pdf_list = []
for filename in pdf_files:
    full_path = os.path.join(input_dir, filename)
    title = os.path.splitext(filename)[0]
    pdf_list.append((full_path, title))

if not pdf_list:
    print("❌ Tidak ada file PDF ditemukan di folder!")
    exit()

book_title = input("Masukkan judul buku (opsional): ").strip()
if not book_title:
    book_title = "📑 Daftar Isi"

cover_path = input("Masukkan path file cover image (opsional): ").strip()
add_cover = bool(cover_path and os.path.isfile(cover_path))

width, height = A4
line_height = 22
entries_per_toc_page = int((height - 90) / line_height)

# ====== Step 1: Hitung jumlah halaman tiap file ======
num_pages_list = []
for file, title in pdf_list:
    try:
        reader = PdfReader(file)
        num_pages_list.append(len(reader.pages))
    except Exception as e:
        print(f"⚠️ Gagal membaca {file}: {e}")
        num_pages_list.append(0)

# ====== Step 2: Buat TOC dummy untuk hitung jumlah halaman TOC ======
dummy_packet = io.BytesIO()
can = canvas.Canvas(dummy_packet, pagesize=A4)
can.setFont("Helvetica-Bold", 18)
can.drawString(50, height - 50, book_title)
can.setFont("Helvetica", 12)

y = height - 90
for idx, (file, title) in enumerate(pdf_list):
    if y < 50:
        can.showPage()
        can.setFont("Helvetica", 12)
        y = height - 50
    y -= line_height

can.showPage()
can.save()
dummy_packet.seek(0)

toc_pdf_dummy = PdfReader(dummy_packet)
num_toc_pages = len(toc_pdf_dummy.pages)
dummy_packet.close()

cover_offset = 1 if add_cover else 0

# ====== Step 3: Hitung target_pages yang benar ======
target_pages = []
current_page = num_toc_pages + cover_offset
for num in num_pages_list:
    target_pages.append(current_page + 1)  # human-readable
    current_page += num

# ====== Step 4: Buat TOC final ======
packet = io.BytesIO()
can = canvas.Canvas(packet, pagesize=A4)
can.setFont("Helvetica-Bold", 18)
can.drawString(50, height - 50, book_title)
can.setFont("Helvetica", 12)

y = height - 90
link_rects = []

for idx, (file, title) in enumerate(pdf_list):
    if y < 50:
        can.showPage()
        can.setFont("Helvetica", 12)
        y = height - 50

    # Judul biru
    can.setFillColor(HexColor("#1a73e8"))
    text_y = y
    can.drawString(50, text_y, title)

    # Garis putus-putus
    can.setStrokeColor(HexColor("#000000"))
    can.setDash(1, 2)
    text_width = can.stringWidth(title, "Helvetica", 12)
    start_x = 50 + text_width + 5
    end_x = width - 50 - can.stringWidth(str(target_pages[idx]), "Helvetica", 12) - 10
    line_y = text_y + 3
    can.line(start_x, line_y, end_x, line_y)
    can.setDash()

    # Nomor halaman
    can.setFillColor(HexColor("#000000"))
    can.drawRightString(width - 50, text_y, str(target_pages[idx]))

    # Rect link
    link_rects.append((idx, (50, text_y - 2, width - 50, text_y + 12)))
    y -= line_height

can.showPage()
can.save()
packet.seek(0)

toc_pdf = PdfReader(packet)
real_num_toc_pages = len(toc_pdf.pages)

# ====== Step 5: Buat cover PDF jika ada ======
cover_pdf = None
if add_cover:
    cover_stream = io.BytesIO()
    c = canvas.Canvas(cover_stream, pagesize=A4)
    img = ImageReader(cover_path)
    c.drawImage(img, 0, 0, width=width, height=height)
    c.showPage()
    c.save()
    cover_stream.seek(0)
    cover_pdf = PdfReader(cover_stream)

# ====== Step 6: Gabungkan cover + TOC + PDF ======
writer = PdfWriter()

if add_cover:
    writer.add_page(cover_pdf.pages[0])

for toc_page in toc_pdf.pages:
    writer.add_page(toc_page)

current_page = real_num_toc_pages + cover_offset
for filepath, title in pdf_list:
    reader = PdfReader(filepath)
    for page in reader.pages:
        writer.add_page(page)
    writer.add_outline_item(title, current_page)
    current_page += len(reader.pages)

with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
    temp_pdf_path = tmp.name
    writer.write(tmp)

print(f"✅ PDF gabungan dibuat sementara!")

# ====== Step 7: Tambahkan link annotation ======
parent_dir = os.path.dirname(input_dir)
folder_name = os.path.basename(os.path.normpath(input_dir))
output_file = os.path.join(parent_dir, f"{folder_name}_merged.pdf")

with pikepdf.open(temp_pdf_path) as pdf:
    for idx, target_page in enumerate(target_pages):
        toc_page_index = idx // entries_per_toc_page
        toc_page = pdf.pages[toc_page_index + cover_offset]  # +cover_offset karena cover di depan
        _, rect = link_rects[idx]

        action = pdf.make_indirect({
            '/S': pikepdf.Name('/GoTo'),
            '/D': [target_page - 1, pikepdf.Name('/Fit')]
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

os.remove(temp_pdf_path)
packet.close()
if add_cover:
    cover_stream.close()

print(f"🎉 Selesai! File output: {output_file}")
