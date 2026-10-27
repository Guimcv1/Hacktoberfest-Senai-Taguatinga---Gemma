import fitz


def build_pdf(pages: list[str]) -> bytes:
    """Cria um PDF em memória, uma página por item da lista."""
    document = fitz.open()
    try:
        for text in pages:
            page = document.new_page()
            if text:
                page.insert_text((72, 72), text)
        return document.tobytes()
    finally:
        document.close()
