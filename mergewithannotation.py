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
    return [int(text) if text.isdigit() else text.lower() for text in re.split(r'(\d+)', s)]

def draw_toc_header(can, width, y_pos):
    # Judul
    can.setFont("Helvetica-Bold", 22)
    can.drawString(50, y_pos, "📑 Daftar Isi")
    
    # Garis horizontal di bawah judul
    can.setStrokeColor(HexColor("#000000"))
    can.setLineWidth(0.5)
    can.line(50, y_pos - 5, width - 50, y_pos - 5)
    
    # Turunkan y untuk memberi jarak (newline)
    y_pos -= 10
    
    # Set font normal untuk entri berikutnya
    can.setFont("Helvetica", 12)
    
    return y_pos

def draw_toc_entry(can, title, page_number, width, text_y):
    max_title_width = width - 50 - 50 - can.stringWidth(str(page_number), "Helvetica", 12) - 30
    real_title = title
    while can.stringWidth(real_title, "Helvetica", 12) > max_title_width and len(real_title) > 3:
        real_title = real_title[:-1]
    if real_title != title:
        real_title = real_title.rstrip() + "…"

    can.setFillColor(HexColor("#1a73e8"))
    can.drawString(50, text_y, real_title)

    can.setStrokeColor(HexColor("#000000"))
    can.setDash(1, 2)
    text_width = can.stringWidth(real_title, "Helvetica", 12)
    start_x = 50 + text_width + 5
    end_x = width - 50 - can.stringWidth(str(page_number), "Helvetica", 12) - 10
    line_y = text_y + 3
    can.line(start_x, line_y, end_x, line_y)
    can.setDash()

    can.setFillColor(HexColor("#000000"))
    can.drawRightString(width - 50, text_y, str(page_number))

def main():
    input_dir = input("Masukkan path folder PDF: ").strip()
    pdf_files = sorted(
        [f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')],
        key=natural_key
    )
    pdf_list = [(os.path.join(input_dir, f), os.path.splitext(f)[0]) for f in pdf_files]

    if not pdf_list:
        print("❌ Tidak ada file PDF ditemukan di folder!")
        return

    cover_path = input("Masukkan path file cover image (opsional): ").strip()
    add_cover = bool(cover_path and os.path.isfile(cover_path))

    print(f"🔃 Menggabungkan semua PDF ..")

    width, height = A4
    line_height = 24
    margin_atas = 60  # margin atas di halaman TOC selain pertama
    header_y = height - 70  # posisi header di halaman pertama

    # Hitung berapa banyak entri TOC per halaman
    entries_first_page = 30
    entries_next_pages = 32

    # Hitung jumlah halaman tiap file PDF
    num_pages_list = []
    for file, title in pdf_list:
        try:
            reader = PdfReader(file)
            n = len(reader.pages)
            if n == 0:
                print(f"⚠️ {file} tidak punya halaman, dilewati di TOC.")
            num_pages_list.append(n)
        except Exception as e:
            print(f"⚠️ Gagal membaca {file}: {e}")
            num_pages_list.append(0)

    cover_offset = 1 if add_cover else 0

    # === Step 3: Dummy TOC untuk hitung jumlah halaman ===
    dummy_packet = io.BytesIO()
    can = canvas.Canvas(dummy_packet, pagesize=A4)

    y = header_y
    y = draw_toc_header(can, width, y)
    y -= 30

    for idx in range(len(pdf_list)):
        if idx == entries_first_page:
            can.showPage()
            y = height - margin_atas
        elif idx > entries_first_page and (idx - entries_first_page) % entries_next_pages == 0:
            can.showPage()
            y = height - margin_atas
        y -= line_height

    can.showPage()
    can.save()
    dummy_packet.seek(0)
    num_toc_pages = len(PdfReader(dummy_packet).pages)
    dummy_packet.close()

    # Hitung target_pages
    target_pages = []
    current_page = num_toc_pages + cover_offset
    for num in num_pages_list:
        if num == 0:
            target_pages.append(current_page + 1)
            continue
        target_pages.append(current_page + 1)
        current_page += num

    # === Step 4: Buat TOC real ===
    packet = io.BytesIO()
    can = canvas.Canvas(packet, pagesize=A4)

    y = header_y
    y = draw_toc_header(can, width, y)
    y -= 30
    link_rects = []

    for idx, (_, title) in enumerate(pdf_list):
        if idx == entries_first_page:
            can.showPage()
            y = height - margin_atas
        elif idx > entries_first_page and (idx - entries_first_page) % entries_next_pages == 0:
            can.showPage()
            y = height - margin_atas

        draw_toc_entry(can, title, target_pages[idx], width, y)
        link_rects.append((idx, (50, y - 2, width - 50, y + 12)))
        y -= line_height

    can.showPage()
    can.save()
    packet.seek(0)
    toc_pdf = PdfReader(packet)
    real_num_toc_pages = len(toc_pdf.pages)

    # === Step 5: Buat cover jika ada ===
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

    # === Step 6: Gabungkan semua PDF ===
    writer = PdfWriter()
    if add_cover:
        writer.add_page(cover_pdf.pages[0])

    for toc_page in toc_pdf.pages:
        writer.add_page(toc_page)

    current_page = real_num_toc_pages + cover_offset
    for idx, (filepath, title) in enumerate(pdf_list):
        reader = PdfReader(filepath)
        n = len(reader.pages)
        if n == 0:
            print(f"⚠️ Lewati bookmark untuk file kosong: {title}")
            continue
        for page in reader.pages:
            writer.add_page(page)
        writer.add_outline_item(title, current_page)
        current_page += n

    with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as tmp:
        temp_pdf_path = tmp.name
        writer.write(tmp)

    print(f"🔃 Menambahkan annotation ..")

    # === Step 7: Tambahkan link annotation ===
    parent_dir = os.path.dirname(input_dir)
    folder_name = os.path.basename(os.path.normpath(input_dir))
    output_file = os.path.join(parent_dir, f"{folder_name}_merged.pdf")

    with pikepdf.open(temp_pdf_path) as pdf:
        for idx, target_page in enumerate(target_pages):
            if idx < entries_first_page:
                toc_page_index = 0
            else:
                toc_page_index = 1 + ((idx - entries_first_page) // entries_next_pages)

            toc_page = pdf.pages[cover_offset + toc_page_index]
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

if __name__ == "__main__":
    main()
