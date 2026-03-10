from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.services.about_page_content import build_about_page_document
from app.services.about_page_content import extract_primary_image_src


def test_extract_primary_image_src_returns_first_image():
    html = '<section><img src="/media/uploads/mickael.jpg" alt="portrait" /><img src="/other.jpg" /></section>'
    assert extract_primary_image_src(html) == "/media/uploads/mickael.jpg"


def test_build_about_page_document_preserves_existing_photo():
    document = build_about_page_document(
        "fr",
        existing_html='<div><img src="https://cdn.example.com/mickael-benmoussa.webp" alt="Mickael" /></div>',
    )
    html = document["content"]["main"]["html"]
    seo = document["content"]["seo"]

    assert "https://cdn.example.com/mickael-benmoussa.webp" in html
    assert "<h1>Qui est Israel Growth Venture</h1>" in html
    assert "IGV n’est pas un fonds d’investissement" in html
    assert seo["canonical"] == "/about/"
    assert seo["robots"] == "index,follow"


def test_build_about_page_document_sets_hebrew_rtl_markup():
    document = build_about_page_document("he")
    html = document["content"]["main"]["html"]
    seo = document["content"]["seo"]

    assert 'dir="rtl"' in html
    assert "מי היא Israel Growth Venture" in html
    assert "מה IGV לא עושה" in html
    assert seo["canonical"] == "/he/about/"
