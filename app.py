import streamlit as st
import requests
import os
import io
from PIL import Image
from google import genai
from reportlab.lib.pagesizes import letter
from reportlab.lib.colors import HexColor
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Image as RLImage, PageBreak
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfgen import canvas

# --- Page Configuration ---
st.set_page_config(
    page_title="AI E-Book Generator",
    page_icon="📚",
    layout="wide"
)

# --- Numbered Canvas for Page Numbers & Footers ---
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
            self.draw_page_number(num_pages)
            super().showPage()
        super().save()

    def draw_page_number(self, page_count):
        if self._pageNumber == 1:
            return  # Skip cover page
        self.saveState()
        self.setFont("Helvetica", 9)
        self.setFillColor(HexColor("#666666"))
        page_text = f"Page {self._pageNumber} of {page_count}"
        self.drawRightString(612 - 54, 36, page_text)
        self.restoreState()

# --- Helper Functions ---
def fetch_unsplash_image(query, api_key):
    if not api_key:
        return None
    url = f"https://api.unsplash.com/photos/random?query={query}&orientation=landscape&client_id={api_key}"
    try:
        res = requests.get(url, timeout=10)
        if res.status_code == 200:
            data = res.json()
            img_url = data['urls']['regular']
            img_res = requests.get(img_url, timeout=10)
            if img_res.status_code == 200:
                return io.BytesIO(img_res.content)
    except Exception as e:
        st.warning(f"Failed to fetch image for '{query}': {e}")
    return None

def generate_ebook_content(gemini_key, topic, page_count):
    client = genai.Client(api_key=gemini_key)
    target_chapters = max(3, min(page_count, 15))
    
    prompt = f"""
    You are a professional author and subject matter expert.
    Write a comprehensive, highly engaging, and structured e-book on the topic: "{topic}".
    The target length of the e-book is approximately {page_count} pages.
    Structure the book into exactly {target_chapters} well-developed chapters.

    Format the output strictly as follows for each chapter:
    [CHAPTER_TITLE] Chapter Title Here
    [CHAPTER_IMAGE_KEYWORD] single_word_keyword_for_image
    [CHAPTER_CONTENT]
    Detailed paragraphs and actionable insights for this chapter...
    [END_CHAPTER]
    """
    
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
            keyword = "abstract"
            for line in lines:
                if line.startswith("[CHAPTER_IMAGE_KEYWORD]"):
                    keyword = line.replace("[CHAPTER_IMAGE_KEYWORD]", "").strip()
            
            chapters.append({
                "title": title,
                "keyword": keyword,
                "content": content
            })
        except Exception:
            continue
    return chapters

def create_pdf(topic, author, chapters, unsplash_key, primary_color, secondary_color, text_color):
    pdf_buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        pdf_buffer,
        pagesize=letter,
        leftMargin=54, rightMargin=54,
        topMargin=54, bottomMargin=54
    )
    
    styles = getSampleStyleSheet()
    
    cover_title_style = ParagraphStyle(
        'CoverTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=32,
        leading=38,
        textColor=HexColor(primary_color),
        alignment=1,
        spaceAfter=20
    )
    
    cover_author_style = ParagraphStyle(
        'CoverAuthor',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=16,
        leading=20,
        textColor=HexColor(secondary_color),
        alignment=1,
        spaceAfter=40
    )
    
    h1_style = ParagraphStyle(
        'Heading1_Custom',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=HexColor(primary_color),
        spaceBefore=15,
        spaceAfter=15
    )
    
    body_style = ParagraphStyle(
        'Body_Custom',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=11,
        leading=16,
        textColor=HexColor(text_color),
        spaceAfter=12
    )

    story = []

    # --- Cover Page ---
    story.append(Spacer(1, 100))
    story.append(Paragraph(topic, cover_title_style))
    story.append(Paragraph(f"By {author}", cover_author_style))
    
    cover_img_data = fetch_unsplash_image(topic, unsplash_key)
    if cover_img_data:
        story.append(RLImage(cover_img_data, width=400, height=250))
    
    story.append(PageBreak())

    # --- Chapters ---
    for idx, chap in enumerate(chapters, 1):
        story.append(Paragraph(f"Chapter {idx}: {chap['title']}", h1_style))
        
        chap_img_data = fetch_unsplash_image(chap['keyword'], unsplash_key)
        if chap_img_data:
            story.append(RLImage(chap_img_data, width=450, height=225))
            story.append(Spacer(1, 15))
        
        paragraphs = chap['content'].split("\n\n")
        for p in paragraphs:
            if p.strip():
                story.append(Paragraph(p.strip(), body_style))
        
        story.append(PageBreak())

    doc.build(story, canvasmaker=NumberedCanvas)
    pdf_buffer.seek(0)
    return pdf_buffer

# --- UI Interface ---
st.title("📚 AI-Driven Automated E-Book Generator")
st.markdown("Create fully stylized, image-rich e-books in seconds using Gemini AI & Unsplash.")

with st.sidebar:
    st.header("🔑 API Credentials")
    gemini_key = st.text_input("Gemini API Key", type="password")
    unsplash_key = st.text_input("Unsplash Access Key", type="password")
    
    st.header("🎨 Styling & Design")
    primary_color = st.color_picker("Primary / Title Color", "#1A365D")
    secondary_color = st.color_picker("Secondary / Subtitle Color", "#2B6CB0")
    text_color = st.color_picker("Body Text Color", "#2D3748")

col1, col2 = st.columns([1, 1])

with col1:
    st.header("📖 E-Book Details")
    topic = st.text_input("E-Book Topic / Title", "Mastering Artificial Intelligence in 2026")
    author = st.text_input("Author Name", "Priyanshu")
    page_count = st.slider("Target Page Count", min_value=3, max_value=100, value=10)
    
    generate_btn = st.button("🚀 Generate E-Book", type="primary")

if generate_btn:
    if not gemini_key:
        st.error("Please enter your Gemini API Key in the sidebar.")
    else:
        with st.spinner("Generating e-book content with AI..."):
            try:
                raw_text = generate_ebook_content(gemini_key, topic, page_count)
                chapters = parse_generated_text(raw_text)
                
                if not chapters:
                    st.error("Failed to parse content. Please try again.")
                else:
                    st.success(f"Generated {len(chapters)} chapters successfully!")
                    
                    with st.spinner("Building PDF with auto-inserted images..."):
                        pdf_data = create_pdf(
                            topic, author, chapters, unsplash_key,
                            primary_color, secondary_color, text_color
                        )
                    
                    st.session_state['pdf_data'] = pdf_data
                    st.session_state['chapters'] = chapters
            except Exception as e:
                st.error(f"An error occurred: {e}")

if 'pdf_data' in st.session_state:
    with col2:
        st.header("📥 Preview & Download")
        st.download_button(
            label="📄 Download E-Book (PDF)",
            data=st.session_state['pdf_data'],
            file_name=f"{topic.replace(' ', '_')}_ebook.pdf",
            mime="application/pdf"
        )
        
        st.subheader("Chapter Breakdown Preview")
        for ch in st.session_state['chapters']:
            with st.expander(ch['title']):
                st.write(ch['content'][:300] + "...")
  
