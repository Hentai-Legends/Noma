import os
import html
from typing import List, Dict, Optional
from ebooklib import epub

from src.parsers.base import DocumentChunk, ElementType
from .base import BaseBuilder, align_chunk_translations


CSS_CONTENT = """\
body {
    margin: 5%;
    text-align: justify;
}
h1, h2, h3, h4, h5, h6 {
    text-align: center;
    font-weight: bold;
    margin-top: 1.5em;
    margin-bottom: 0.8em;
}
p {
    text-indent: 1.5em;
    text-align: justify;
    line-height: 1.5;
}
p.original {
    font-style: italic;
    color: gray;
}
.image-container {
    text-align: center;
    margin: 1.5em 0;
}
.image-container img {
    max-width: 100%;
}
"""


class EpubBuilder(BaseBuilder):
    def build(
        self,
        chunks: List[DocumentChunk],
        translations: Dict[int, Dict[int, str]],
        output_file_path: str,
        bilingual: bool = False
    ):
        book = epub.EpubBook()

        # Ambil judul buku dari nama file output
        base_name = os.path.splitext(os.path.basename(output_file_path))[0]
        base_name = base_name.replace("_translated", "").replace("_partial", "").replace("_", " ").title()
        book_title = base_name if base_name else "Novel Terjemahan"
        book.set_title(book_title)
        book.set_language("id")

        # Buat file CSS terpisah
        css_item = epub.EpubItem(
            uid="style",
            file_name="style/default.css",
            media_type="text/css",
            content=CSS_CONTENT.encode('utf-8')
        )
        book.add_item(css_item)

        spine: list = ["nav"]
        img_counter = 0
        heading_counter = 0
        file_counter = 0

        # Setiap chapter: (title, content_html_list, toc_title, toc_anchor)
        chapter_list: list = []
        current_content: List[str] = []
        current_title: str = book_title
        current_toc_title: Optional[str] = None
        current_toc_anchor: Optional[str] = None

        def commit_current():
            """Simpan konten yang sudah terkumpul sebagai satu chapter."""
            nonlocal current_content, current_title, current_toc_title, current_toc_anchor
            if not current_content:
                return
            chapter_list.append((
                current_title,
                list(current_content),
                current_toc_title,
                current_toc_anchor,
            ))
            current_content = []
            current_toc_title = None
            current_toc_anchor = None

        for chunk in chunks:
            chunk_trans = align_chunk_translations(chunk, translations.get(chunk.chunk_id, {}))

            for i, el in enumerate(chunk.elements):
                if el.is_image() and el.image_bytes:
                    img_counter += 1
                    img_name = f"image_{img_counter}.{el.image_ext}"
                    img_item = epub.EpubItem(
                        uid=f"img_{img_counter}",
                        file_name=f"images/{img_name}",
                        media_type=f"image/{el.image_ext}",
                        content=el.image_bytes
                    )
                    book.add_item(img_item)
                    current_content.append(
                        f'<div class="image-container">'
                        f'<img src="images/{img_name}" alt="image"/>'
                        f'</div>'
                    )

                elif el.element_type == ElementType.PAGE_BREAK:
                    # Page break diabaikan — pemisahan chapter dilakukan per heading
                    continue

                elif el.is_text():
                    translated_text = chunk_trans.get(i, el.text)

                    if el.element_type == ElementType.HEADING:
                        # Commit konten sebelumnya sebagai chapter terpisah
                        commit_current()

                        lvl = min(max(el.heading_level or 1, 1), 6)
                        escaped_title = html.escape(translated_text)
                        heading_counter += 1
                        anchor_id = f"heading_{heading_counter}"

                        # Set info chapter baru
                        current_title = translated_text.strip()
                        current_toc_title = translated_text.strip()
                        current_toc_anchor = anchor_id

                        # Heading menjadi konten pertama chapter baru
                        current_content.append(
                            f'<h{lvl} id="{anchor_id}">{escaped_title}</h{lvl}>'
                        )

                    else:
                        escaped_trans = html.escape(translated_text)
                        if bilingual and el.text.strip() and el.text.strip() != translated_text.strip():
                            escaped_orig = html.escape(el.text)
                            current_content.append(
                                f'<p class="original">{escaped_orig}</p>'
                            )
                        current_content.append(f'<p>{escaped_trans}</p>')

        # Commit chapter terakhir
        commit_current()

        # Bangun file XHTML per chapter dan susun TOC
        toc_links = []
        for title, content_parts, toc_title, toc_anchor in chapter_list:
            file_counter += 1
            file_name = f"chap_{file_counter}.xhtml"

            chap = epub.EpubHtml(
                title=title,
                file_name=file_name,
                lang="id"
            )
            chap.content = (
                f'<?xml version="1.0" encoding="utf-8"?>\n'
                f'<!DOCTYPE html>\n'
                f'<html xmlns="http://www.w3.org/1999/xhtml" xmlns:epub="http://www.idpf.org/2007/ops">\n'
                f'<head>\n'
                f'<title>{html.escape(title)}</title>\n'
                f'<link rel="stylesheet" type="text/css" href="style/default.css"/>\n'
                f'</head>\n'
                f'<body>\n'
                f'{"".join(content_parts)}\n'
                f'</body>\n'
                f'</html>'
            ).encode('utf-8')
            book.add_item(chap)
            spine.append(chap)

            # Tambahkan ke TOC jika chapter dimulai dari heading
            if toc_title and toc_anchor:
                toc_links.append(epub.Link(
                    f"{file_name}#{toc_anchor}",
                    toc_title,
                    f"nav_{file_counter}"
                ))

        # Set TOC
        if toc_links:
            book.toc = tuple(toc_links)
        elif len(spine) > 1:
            book.toc = tuple(spine[1:])

        book.add_item(epub.EpubNcx())
        book.add_item(epub.EpubNav())
        book.spine = spine

        out_dir = os.path.dirname(os.path.abspath(output_file_path))
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)

        epub.write_epub(output_file_path, book)
