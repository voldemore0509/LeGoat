# -*- coding: utf-8 -*-
"""Generation du PDF de profil."""
from __future__ import annotations

import io
import re

try:
    from PIL import Image
except Exception:
    Image = None

try:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen import canvas as pdf_canvas
except Exception:
    A4 = None
    ImageReader = None
    pdf_canvas = None

def _sanitize_pdf_filename(value: str) -> str:
    cleaned = re.sub(r'[^a-zA-Z0-9_-]+', '-', value.strip().lower())
    cleaned = re.sub(r'-+', '-', cleaned).strip('-')
    return cleaned or 'profil-goat'

def _wrap_pdf_text(pdf, text: str, max_width: float) -> list[str]:
    words = str(text or '').split()
    if not words:
        return []
    lines: list[str] = []
    current = words[0]
    for word in words[1:]:
        candidate = current + ' ' + word
        if pdf.stringWidth(candidate, 'Helvetica', 11) <= max_width:
            current = candidate
        else:
            lines.append(current)
            current = word
    lines.append(current)
    return lines

def _draw_pdf_image(pdf, data_url: str, x: float, y: float, w: float, h: float) -> None:
    if not data_url or Image is None or ImageReader is None:
        return
    image = _image_from_data_url(data_url)
    if image.mode not in ('RGB', 'RGBA'):
        image = image.convert('RGBA')
    buf = io.BytesIO()
    image.save(buf, format='PNG')
    buf.seek(0)
    pdf.drawImage(ImageReader(buf), x, y, width=w, height=h, mask='auto', preserveAspectRatio=False)

def _build_profile_pdf(profile: dict, chat_count: int, goat_score: int, include_score: bool) -> bytes:
    if pdf_canvas is None or A4 is None:
        raise RuntimeError("reportlab est requis pour l'export PDF.")
    width, height = A4
    buffer = io.BytesIO()
    pdf = pdf_canvas.Canvas(buffer, pagesize=A4)
    margin = 36
    card_x, card_y = margin, 72
    card_w, card_h = width - (margin * 2), height - 120
    banner_h = 130
    pdf.setFillColorRGB(0.97, 0.98, 1)
    pdf.roundRect(card_x, card_y, card_w, card_h, 18, fill=1, stroke=0)
    if profile.get('banner'):
        _draw_pdf_image(pdf, str(profile.get('banner') or ''), card_x, card_y + card_h - banner_h, card_w, banner_h)
    else:
        pdf.setFillColorRGB(0.12, 0.19, 0.34)
        pdf.roundRect(card_x, card_y + card_h - banner_h, card_w, banner_h, 18, fill=1, stroke=0)
    avatar_size = 76
    avatar_x = card_x + 24
    avatar_y = card_y + card_h - banner_h - (avatar_size / 2)
    pdf.setFillColorRGB(1, 1, 1)
    pdf.roundRect(avatar_x - 4, avatar_y - 4, avatar_size + 8, avatar_size + 8, 20, fill=1, stroke=0)
    if profile.get('avatar'):
        _draw_pdf_image(pdf, str(profile.get('avatar') or ''), avatar_x, avatar_y, avatar_size, avatar_size)
    full_name = ' '.join([str(profile.get('firstname') or '').strip(), str(profile.get('lastname') or '').strip()]).strip() or 'Profil Goat'
    pdf.setFillColorRGB(0.08, 0.11, 0.17)
    pdf.setFont('Helvetica-Bold', 20)
    pdf.drawString(card_x + 120, avatar_y + 42, full_name)
    pdf.setFont('Helvetica', 10)
    pdf.setFillColorRGB(0.34, 0.38, 0.44)
    pdf.drawString(card_x + 120, avatar_y + 24, 'Profil exporté depuis Le Goat')
    current_y = avatar_y - 26
    pdf.setFillColorRGB(0.08, 0.11, 0.17)
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(card_x + 24, current_y, 'Description')
    current_y -= 18
    pdf.setFont('Helvetica', 11)
    pdf.setFillColorRGB(0.18, 0.22, 0.28)
    bio_lines = _wrap_pdf_text(pdf, str(profile.get('bio') or 'Aucune description renseignée.'), card_w - 48)
    for line in bio_lines[:6]:
        pdf.drawString(card_x + 24, current_y, line)
        current_y -= 15
    current_y -= 8
    pdf.setFillColorRGB(0.08, 0.11, 0.17)
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(card_x + 24, current_y, f"Chats envoyés à l'IA : {chat_count}")
    current_y -= 18
    if include_score:
        pdf.drawString(card_x + 24, current_y, f'Goat Score : {goat_score}')
        current_y -= 22
    else:
        current_y -= 4
    socials = [
        ('Instagram', profile.get('instagram')),
        ('TikTok', profile.get('tiktok')),
        ('YouTube', profile.get('youtube')),
        ('GitHub', profile.get('github')),
        ('Bluesky', profile.get('bluesky')),
    ]
    pdf.setFont('Helvetica-Bold', 11)
    pdf.drawString(card_x + 24, current_y, 'Réseaux')
    current_y -= 18
    pdf.setFont('Helvetica', 10.5)
    pdf.setFillColorRGB(0.18, 0.22, 0.28)
    for label, value in socials:
        value = str(value or '').strip()
        if not value:
            continue
        for idx, line in enumerate(_wrap_pdf_text(pdf, f'{label} : {value}', card_w - 48)[:2]):
            pdf.drawString(card_x + 24, current_y, line)
            current_y -= 14
        current_y -= 2 
    pdf.showPage()
    pdf.save()
    return buffer.getvalue()

