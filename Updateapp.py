import streamlit as st
import requests
import io
from google import genai
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

st.set_page_config(
    page_title="AI Ultra E-Book Studio",
    page_icon="📖",
    layout="wide"
)

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            if self._pageNumber > 1:
                self.saveState()
                self.setFont("Helvetica", 9)
                self.setFillColor(HexColor("#718096"))
                self.drawRightString(612 - 54, 36, f"Page {self._pageNumber} of {num_pages}")
                self.restoreState()
            super().showPage()
        super().save()

def fetch_unsplash_image(query, api_key):
    if not api_key:
        return None
    url = f"https://api.unsplash.com/photos/random?query={query}&orientation=landscape&client_id={api_key}"
    try:
        res = requests.get(url, timeout=8)
        if res.status_code == 200:
            img_url = res.json()['urls']['regular']
            img_res = requests.get(img_url, timeout=8)
            if img_res.status_code == 200:
                return io.BytesIO(img_res.content)
    except Exception:
        pass
    return None

def generate_ebook_content(gemini_key, topic, page_count):
    client = genai.Client(api_key=gemini_key)
    target_chapters = max(3, min(page_count, 15))
    
    prompt = f"""
    You are an expert author writing a high-quality book titled: "{topic}".
    Target length: approx {page_count} pages.
    Create exactly {target_chapters} detailed chapters with practical insights, subheadings, and deep content.

    Format strictly as:
    [CHAPTER_TITLE] Chapter Name Here
    [CHAPTER_IMAGE_KEYWORD] single_word_keyword
    [CHAPTER_CONTENT]
    Full text content here...
    [END_CHAPTER]
    """
    
    # Updated to gemini-2.5-flash for fixed model resolution
    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt
    )
    return response.text

def parse_generated_text(raw_text):
    chapters = []
    blocks = raw_text.split("[CHAPTER_TITLE]")
    for block in blocks:
        if not block.strip():
            continue
        try:
            parts = block.split("[CHAPTER_CONTENT]")
            header_part = parts[0].strip()
            content = parts[1].replace("[END_CHAPTER]", "").strip() if len(parts) > 1 else ""
            
            lines = [line.strip() for line in header_part.split("\n") if line.strip()]
            title = lines[0] if lines else "Chapter"
            keyword = "book"
            for line in lines:
                if line.startswith("[CHAPTER_IMAGE_KEYWORD]"):
                    keyword = line.replace("[CHAPTER_IMAGE_KEYWORD]", "").strip()
            
            chapters.append({"title": title, "keyword": keyword, "content": content})
        except Exception:
            continue
    return chapters

def create_pdf(topic, author, chapters, unsplash_key, primary_color, secondary_color, text_color):
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(pdf_buffer, pagesize=letter, leftMargin=54, rightMargin=54, topMargin=54, bottomMargin=54)
    styles = getSampleStyleSheet()
    
    title_style = ParagraphStyle('CoverTitle', parent=styles['Title'], fontName='Helvetica-Bold', fontSize=30, leading=36, textColor=HexColor(primary_color), alignment=1, spaceAfter=20)
    author_style = ParagraphStyle('CoverAuthor', parent=styles['Normal'], fontName='Helvetica', fontSize=15, leading=18, textColor=HexColor(secondary_color), alignment=1, spaceAfter=30)
    h1_style = ParagraphStyle('H1', parent=styles['Heading1'], fontName='Helvetica-Bold', fontSize=20, leading=24, textColor=HexColor(primary_color), spaceBefore=15, spaceAfter=15)
    body_style = ParagraphStyle('Body', parent=styles['BodyText'], fontName='Helvetica', fontSize=11, leading=16, textColor=HexColor(text_color), spaceAfter=12)

    story = [Spacer(1, 80), Paragraph(topic, title_style), Paragraph(f"By {author}", author_style)]
    
    cover_img = fetch_unsplash_image(topic, unsplash_key)
    if cover_img:
        story.append(RLImage(cover_img, width=420, height=240))
    story.append(PageBreak())

    for idx, chap in enumerate(chapters, 1):
        story.append(Paragraph(f"Chapter {idx}: {chap['title']}", h1_style))
        chap_img = fetch_unsplash_image(chap['keyword'], unsplash_key)
        if chap_img:
            story.append(RLImage(chap_img, width=420, height=210))
            story.append(Spacer(1, 12))
        
        for p in chap['content'].split("\n\n"):
            if p.strip():
                story.append(Paragraph(p.strip(), body_style))
        story.append(PageBreak())

    doc.build(story, canvasmaker=NumberedCanvas)
    pdf_buffer.seek(0)
    return pdf_buffer

# --- UI Setup ---
st.title("🚀 AI Ultra E-Book Studio")

with st.sidebar:
    st.subheader("🔑 API Keys")
    gemini_key = st.text_input("Gemini API Key", type="password")
    unsplash_key = st.text_input("Unsplash Access Key", type="password")
    
    st.subheader("🎨 Custom Styling")
    primary_color = st.color_picker("Primary / Heading Color", "#1E3A8A")
    secondary_color = st.color_picker("Subtitle Color", "#3B82F6")
    text_color = st.color_picker("Body Text Color", "#1F2937")

c1, c2 = st.columns([1, 1])

with c1:
    st.subheader("⚙️ Book Configuration")
    topic = st.text_input("Book Title", "How To Make Money By Selling AI Digital Products")
    author = st.text_input("Author Name", "Apex")
    page_count = st.slider("Target Page Count", 3, 50, 15)
    
    btn = st.button("🔥 Generate Full E-Book", type="primary", use_container_width=True)

if btn:
    if not gemini_key:
        st.error("Please provide Gemini API Key in sidebar!")
    else:
        with st.spinner("AI is generating book text & auto-searching Unsplash images..."):
            try:
                raw_text = generate_ebook_content(gemini_key, topic, page_count)
                chapters = parse_generated_text(raw_text)
                pdf_data = create_pdf(topic, author, chapters, unsplash_key, primary_color, secondary_color, text_color)
                st.session_state['pdf'] = pdf_data
                st.session_state['ch'] = chapters
                st.success("E-Book successfully created!")
            except Exception as e:
                st.error(f"Error: {e}")

if 'pdf' in st.session_state:
    with c2:
        st.subheader("📥 Download & Live Chapter Preview")
        st.download_button("⬇️ Download E-Book (PDF)", data=st.session_state['pdf'], file_name=f"{topic}.pdf", mime="application/pdf", use_container_width=True)
        for ch in st.session_state['ch']:
            with st.expander(ch['title']):
                st.write(ch['content'][:400] + "...")
                                                  
