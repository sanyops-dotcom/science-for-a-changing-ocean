"""
MD-to-Word_converter.py
-----------------------
Streamlit Markdown (.md) -> Microsoft Word (.docx) converter.

Run from VS Code terminal:
    pip install streamlit pypandoc python-docx
    streamlit run MD-to-Word_converter.py

The app can use Pandoc for high-quality Markdown conversion. If Pandoc is
not installed, the app offers an automatic download through pypandoc.

Features:
- Markdown upload in browser
- Automatic output filename based on Markdown filename
- Scientific-document layout
- Title page
- Heading styles
- Tables
- Page margins
- Times New Roman body font
- Heading formatting
- Page numbers
- Table of contents field
- Header/footer
- Optional date on title page
- Optional author/institution
- DOCX download
"""

import os
import re
import shutil
import tempfile
from datetime import date
from pathlib import Path

import streamlit as st
import pypandoc
from docx import Document
from docx.enum.section import WD_SECTION
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt


# ---------------------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------------------

st.set_page_config(
    page_title="MD to Word Converter",
    page_icon="📄",
    layout="wide",
)


# ---------------------------------------------------------------------
# HELPERS
# ---------------------------------------------------------------------

def set_cell_font(cell, font_name="Times New Roman", font_size=11):
    """Apply font formatting to every paragraph/run in a table cell."""
    for paragraph in cell.paragraphs:
        for run in paragraph.runs:
            run.font.name = font_name
            run.font.size = Pt(font_size)

            # East Asian font mapping
            rpr = run._element.get_or_add_rPr()
            rfonts = rpr.rFonts
            if rfonts is None:
                rfonts = OxmlElement("w:rFonts")
                rpr.append(rfonts)
            rfonts.set(qn("w:ascii"), font_name)
            rfonts.set(qn("w:hAnsi"), font_name)
            rfonts.set(qn("w:eastAsia"), font_name)


def set_run_font(run, font_name="Times New Roman", font_size=12):
    """Set font name and size for a run."""
    run.font.name = font_name
    run.font.size = Pt(font_size)

    rpr = run._element.get_or_add_rPr()
    rfonts = rpr.rFonts
    if rfonts is None:
        rfonts = OxmlElement("w:rFonts")
        rpr.append(rfonts)
    rfonts.set(qn("w:ascii"), font_name)
    rfonts.set(qn("w:hAnsi"), font_name)
    rfonts.set(qn("w:eastAsia"), font_name)


def add_page_number(paragraph):
    """Insert a Word PAGE field into a paragraph."""
    run = paragraph.add_run()

    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")

    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = " PAGE "

    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "end")

    run._r.append(fld_char1)
    run._r.append(instr_text)
    run._r.append(fld_char2)

    set_run_font(run, "Times New Roman", 10)


def add_toc(paragraph):
    """Insert a Word TOC field.

    Word normally updates the field when the document is opened.
    """
    run = paragraph.add_run()

    fld_char1 = OxmlElement("w:fldChar")
    fld_char1.set(qn("w:fldCharType"), "begin")
    fld_char1.set(qn("w:dirty"), "true")

    instr_text = OxmlElement("w:instrText")
    instr_text.set(qn("xml:space"), "preserve")
    instr_text.text = ' TOC \\o "1-3" \\h \\z \\u '

    fld_char2 = OxmlElement("w:fldChar")
    fld_char2.set(qn("w:fldCharType"), "separate")

    placeholder = OxmlElement("w:t")
    placeholder.text = "Update this table of contents in Word."

    fld_char3 = OxmlElement("w:fldChar")
    fld_char3.set(qn("w:fldCharType"), "end")

    run._r.append(fld_char1)
    run._r.append(instr_text)
    run._r.append(fld_char2)
    run._r.append(placeholder)
    run._r.append(fld_char3)

    set_run_font(run, "Times New Roman", 11)


def configure_styles(
    document,
    body_font="Times New Roman",
    body_size=12,
    line_spacing=1.5,
):
    """Configure Normal and heading styles."""
    styles = document.styles

    normal = styles["Normal"]
    normal.font.name = body_font
    normal.font.size = Pt(body_size)

    # Paragraph settings
    normal.paragraph_format.line_spacing = line_spacing
    normal.paragraph_format.space_after = Pt(6)

    heading_sizes = {
        "Heading 1": 16,
        "Heading 2": 14,
        "Heading 3": 12,
    }

    for style_name, size in heading_sizes.items():
        style = styles[style_name]
        style.font.name = body_font
        style.font.size = Pt(size)
        style.font.bold = True

        # Ensure font mapping
        rpr = style._element.get_or_add_rPr()
        rfonts = rpr.rFonts
        if rfonts is None:
            rfonts = OxmlElement("w:rFonts")
            rpr.append(rfonts)
        rfonts.set(qn("w:ascii"), body_font)
        rfonts.set(qn("w:hAnsi"), body_font)
        rfonts.set(qn("w:eastAsia"), body_font)


def configure_page(section, margin_top, margin_bottom, margin_left, margin_right):
    """Set page dimensions and margins."""
    section.top_margin = Inches(margin_top)
    section.bottom_margin = Inches(margin_bottom)
    section.left_margin = Inches(margin_left)
    section.right_margin = Inches(margin_right)


def add_header_footer(
    document,
    header_text="",
    footer_text="",
    show_page_number=True,
):
    """Add header and footer to all document sections."""
    for section in document.sections:
        header = section.header
        header_para = header.paragraphs[0]
        header_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        if header_text:
            run = header_para.add_run(header_text)
            set_run_font(run, "Times New Roman", 9)

        footer = section.footer
        footer_para = footer.paragraphs[0]
        footer_para.alignment = WD_ALIGN_PARAGRAPH.CENTER

        if footer_text:
            run = footer_para.add_run(footer_text)
            set_run_font(run, "Times New Roman", 9)

        if show_page_number:
            if footer_text:
                footer_para.add_run("    |    ")

            run = footer_para.add_run("Page ")
            set_run_font(run, "Times New Roman", 9)
            add_page_number(footer_para)


def add_title_page(
    document,
    title,
    subtitle="",
    author="",
    institution="",
    include_date=True,
):
    """Create a scientific-style title page."""
    section = document.sections[0]

    # Vertical spacing
    for _ in range(5):
        p = document.add_paragraph()
        p.paragraph_format.space_after = Pt(0)

    p = document.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(24)

    run = p.add_run(title)
    set_run_font(run, "Times New Roman", 22)
    run.bold = True

    if subtitle:
        p = document.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(30)

        run = p.add_run(subtitle)
        set_run_font(run, "Times New Roman", 14)
        run.italic = True

    if author:
        p = document.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(8)

        run = p.add_run(author)
        set_run_font(run, "Times New Roman", 13)
        run.bold = True

    if institution:
        p = document.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(8)

        run = p.add_run(institution)
        set_run_font(run, "Times New Roman", 12)

    if include_date:
        p = document.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(20)

        run = p.add_run(date.today().strftime("%d %B %Y"))
        set_run_font(run, "Times New Roman", 11)

    # New page after title
    document.add_page_break()


def extract_first_heading(markdown_text):
    """Use the first Markdown heading as a default document title."""
    match = re.search(r"^\s*#\s+(.+?)\s*$", markdown_text, re.MULTILINE)
    if match:
        title = match.group(1).strip()
        title = re.sub(r"[*_`]", "", title)
        return title
    return ""


def ensure_pandoc():
    """Return the installed Pandoc version, downloading it if necessary."""
    try:
        return pypandoc.get_pandoc_version()
    except OSError:
        pypandoc.download_pandoc()
        return pypandoc.get_pandoc_version()


def convert_markdown_to_docx(
    markdown_file,
    output_file,
    title,
    subtitle,
    author,
    institution,
    include_title_page,
    include_toc,
    include_date,
    body_font,
    body_size,
    line_spacing,
    margin_top,
    margin_bottom,
    margin_left,
    margin_right,
    header_text,
    footer_text,
    show_page_numbers,
):
    """Convert Markdown to DOCX using Pandoc, then apply scientific formatting."""

    # Ensure Pandoc is available
    ensure_pandoc()

    # Temporary DOCX created by Pandoc
    with tempfile.TemporaryDirectory() as temp_dir:
        intermediate_docx = os.path.join(temp_dir, "converted.docx")

        # Pandoc conversion
        pypandoc.convert_file(
            markdown_file,
            "docx",
            outputfile=intermediate_docx,
            extra_args=[
                "--standalone",
            ],
        )

        # Open converted document
        document = Document(intermediate_docx)

        # Configure styles
        configure_styles(
            document,
            body_font=body_font,
            body_size=body_size,
            line_spacing=line_spacing,
        )

        # Configure page margins
        for section in document.sections:
            configure_page(
                section,
                margin_top,
                margin_bottom,
                margin_left,
                margin_right,
            )

        # Title page
        if include_title_page:
            # A title page should appear before the converted content.
            # We create a new document and copy the converted body elements.
            final_doc = Document()

            configure_styles(
                final_doc,
                body_font=body_font,
                body_size=body_size,
                line_spacing=line_spacing,
            )

            configure_page(
                final_doc.sections[0],
                margin_top,
                margin_bottom,
                margin_left,
                margin_right,
            )

            add_title_page(
                final_doc,
                title=title,
                subtitle=subtitle,
                author=author,
                institution=institution,
                include_date=include_date,
            )

            # Optional TOC
            if include_toc:
                toc_heading = final_doc.add_paragraph()
                toc_heading.style = final_doc.styles["Heading 1"]
                toc_heading.add_run("Table of Contents")

                toc = final_doc.add_paragraph()
                add_toc(toc)

                final_doc.add_page_break()

            # Copy body XML from Pandoc document
            for element in document.element.body:
                # Skip sectPr because final_doc controls sections
                if element.tag == qn("w:sectPr"):
                    continue
                final_doc.element.body.append(element)

            document = final_doc

        else:
            # No title page, but still optionally add TOC at beginning.
            if include_toc:
                # Insert TOC at beginning by creating a new document.
                final_doc = Document()

                configure_styles(
                    final_doc,
                    body_font=body_font,
                    body_size=body_size,
                    line_spacing=line_spacing,
                )

                configure_page(
                    final_doc.sections[0],
                    margin_top,
                    margin_bottom,
                    margin_left,
                    margin_right,
                )

                toc_heading = final_doc.add_paragraph()
                toc_heading.style = final_doc.styles["Heading 1"]
                toc_heading.add_run("Table of Contents")

                toc = final_doc.add_paragraph()
                add_toc(toc)

                final_doc.add_page_break()

                for element in document.element.body:
                    if element.tag == qn("w:sectPr"):
                        continue
                    final_doc.element.body.append(element)

                document = final_doc

        # Reapply margins to all resulting sections
        for section in document.sections:
            configure_page(
                section,
                margin_top,
                margin_bottom,
                margin_left,
                margin_right,
            )

        # Add header/footer
        add_header_footer(
            document,
            header_text=header_text,
            footer_text=footer_text,
            show_page_number=show_page_numbers,
        )

        # Format table contents
        for table in document.tables:
            for row in table.rows:
                for cell in row.cells:
                    set_cell_font(
                        cell,
                        font_name=body_font,
                        font_size=body_size,
                    )

        # Save final document
        document.save(output_file)


# ---------------------------------------------------------------------
# STREAMLIT INTERFACE
# ---------------------------------------------------------------------

st.title("Markdown → Scientific Word Converter")
st.caption(
    "Convert a .md file into a professionally formatted .docx document "
    "directly from your browser."
)

with st.sidebar:
    st.header("Document Settings")

    st.subheader("Title page")

    include_title_page = st.checkbox(
        "Add scientific title page",
        value=True,
    )

    title = st.text_input(
        "Document title",
        value="",
        help="Leave blank to use the first # Markdown heading.",
    )

    subtitle = st.text_input(
        "Subtitle",
        value="",
    )

    author = st.text_input(
        "Author",
        value="",
    )

    institution = st.text_input(
        "Institution / Organization",
        value="",
    )

    include_date = st.checkbox(
        "Add current date",
        value=True,
    )

    st.subheader("Navigation")

    include_toc = st.checkbox(
        "Add Table of Contents",
        value=True,
        help="The TOC is inserted as a Word field. Open the DOCX in Word "
             "and update the field if necessary.",
    )

    st.subheader("Typography")

    body_font = st.selectbox(
        "Main font",
        [
            "Times New Roman",
            "Arial",
            "Calibri",
            "Cambria",
            "Georgia",
        ],
        index=0,
    )

    body_size = st.number_input(
        "Body font size",
        min_value=9,
        max_value=16,
        value=12,
        step=1,
    )

    line_spacing = st.selectbox(
        "Line spacing",
        [1.0, 1.15, 1.5, 2.0],
        index=2,
    )

    st.subheader("Page margins")

    margin_top = st.number_input(
        "Top (inches)",
        min_value=0.25,
        max_value=2.5,
        value=1.0,
        step=0.05,
    )

    margin_bottom = st.number_input(
        "Bottom (inches)",
        min_value=0.25,
        max_value=2.5,
        value=1.0,
        step=0.05,
    )

    margin_left = st.number_input(
        "Left (inches)",
        min_value=0.25,
        max_value=2.5,
        value=1.0,
        step=0.05,
    )

    margin_right = st.number_input(
        "Right (inches)",
        min_value=0.25,
        max_value=2.5,
        value=1.0,
        step=0.05,
    )

    st.subheader("Header / Footer")

    header_text = st.text_input(
        "Header text",
        value="",
    )

    footer_text = st.text_input(
        "Footer text",
        value="",
    )

    show_page_numbers = st.checkbox(
        "Add page numbers",
        value=True,
    )


uploaded_file = st.file_uploader(
    "Upload your Markdown file",
    type=["md", "markdown"],
    help="Select the .md file you want to convert.",
)

if uploaded_file is None:
    st.info(
        "Upload a Markdown (.md) file to begin. "
        "The Word file will automatically use the same filename."
    )

    st.markdown(
        """
### Supported Markdown features

- Headings (`#`, `##`, `###`, etc.)
- Bold and italic text
- Numbered and bulleted lists
- Tables
- Links
- Block quotes
- Code blocks
- Horizontal rules
- Mathematical content supported by Pandoc
- Scientific-document title page
- Table of Contents
- Page numbers
- Custom margins and fonts
"""
    )

else:
    original_name = Path(uploaded_file.name).stem
    output_name = f"{original_name}.docx"

    markdown_bytes = uploaded_file.getvalue()
    markdown_text = markdown_bytes.decode("utf-8", errors="replace")

    # Auto-detect title from first # heading
    detected_title = extract_first_heading(markdown_text)

    if not title.strip():
        effective_title = detected_title or original_name.replace("_", " ")
    else:
        effective_title = title.strip()

    st.success(f"Loaded: {uploaded_file.name}")

    with st.expander("Preview Markdown", expanded=False):
        st.markdown(markdown_text)

    st.markdown("### Conversion")

    st.write(f"**Output file:** `{output_name}`")
    st.write(f"**Detected title:** {effective_title}")

    if st.button(
        "Convert to Word",
        type="primary",
        use_container_width=True,
    ):
        with st.spinner(
            "Converting Markdown and applying scientific formatting..."
        ):
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    md_path = os.path.join(
                        temp_dir,
                        uploaded_file.name,
                    )

                    output_path = os.path.join(
                        temp_dir,
                        output_name,
                    )

                    with open(md_path, "wb") as f:
                        f.write(markdown_bytes)

                    convert_markdown_to_docx(
                        markdown_file=md_path,
                        output_file=output_path,
                        title=effective_title,
                        subtitle=subtitle,
                        author=author,
                        institution=institution,
                        include_title_page=include_title_page,
                        include_toc=include_toc,
                        include_date=include_date,
                        body_font=body_font,
                        body_size=body_size,
                        line_spacing=line_spacing,
                        margin_top=margin_top,
                        margin_bottom=margin_bottom,
                        margin_left=margin_left,
                        margin_right=margin_right,
                        header_text=header_text,
                        footer_text=footer_text,
                        show_page_numbers=show_page_numbers,
                    )

                    with open(output_path, "rb") as f:
                        docx_bytes = f.read()

                st.success("Conversion completed successfully.")

                st.download_button(
                    label=f"Download {output_name}",
                    data=docx_bytes,
                    file_name=output_name,
                    mime=(
                        "application/vnd.openxmlformats-officedocument."
                        "wordprocessingml.document"
                    ),
                    type="primary",
                    use_container_width=True,
                )

            except Exception as error:
                st.error("Conversion failed.")
                st.exception(error)

st.divider()

st.caption(
    "MD-to-Word Converter • Streamlit + Pandoc + python-docx"
)
