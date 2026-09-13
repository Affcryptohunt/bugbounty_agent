"""
Ingestion parsers. Each function returns (title, text). Feed the result into
kb.add_document(). External libraries are imported lazily so the CLI still
works for formats you don't need without forcing every dependency.
"""
from pathlib import Path


def ingest_txt(path):
    p = Path(path)
    return p.stem, p.read_text(errors="ignore")


def ingest_pdf(path):
    try:
        from pypdf import PdfReader
    except ImportError:
        raise SystemExit("Missing dependency. Run: pip install pypdf")
    p = Path(path)
    reader = PdfReader(str(p))
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    title = reader.metadata.title if reader.metadata and reader.metadata.title else p.stem
    return title, text


def ingest_docx(path):
    try:
        import docx
    except ImportError:
        raise SystemExit("Missing dependency. Run: pip install python-docx")
    p = Path(path)
    d = docx.Document(str(p))
    text = "\n".join(para.text for para in d.paragraphs)
    return p.stem, text


def ingest_epub(path):
    try:
        from ebooklib import epub
        import ebooklib
        from bs4 import BeautifulSoup
    except ImportError:
        raise SystemExit("Missing dependency. Run: pip install ebooklib beautifulsoup4")
    p = Path(path)
    book = epub.read_epub(str(p))
    parts = []
    for item in book.get_items():
        if item.get_type() == ebooklib.ITEM_DOCUMENT:
            soup = BeautifulSoup(item.get_content(), "html.parser")
            parts.append(soup.get_text(separator=" "))
    title = book.get_metadata("DC", "title")
    title = title[0][0] if title else p.stem
    return title, "\n".join(parts)


def ingest_youtube(video_id_or_url):
    """
    Pulls the transcript/captions of a YouTube video (if available) via
    youtube-transcript-api. This uses whatever captions the uploader
    published (auto-generated or manual) — same as clicking "Show
    transcript" on YouTube.
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi
    except ImportError:
        raise SystemExit("Missing dependency. Run: pip install youtube-transcript-api")

    video_id = video_id_or_url
    if "v=" in video_id_or_url:
        video_id = video_id_or_url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in video_id_or_url:
        video_id = video_id_or_url.split("youtu.be/")[1].split("?")[0]

    transcript = YouTubeTranscriptApi.get_transcript(video_id)
    text = " ".join(seg["text"] for seg in transcript)
    return f"YouTube:{video_id}", text


def ingest_url(url):
    """
    Fetches a web page and strips it down to readable text (article body,
    docs page, writeup, etc.).
    """
    try:
        import requests
        from bs4 import BeautifulSoup
    except ImportError:
        raise SystemExit("Missing dependency. Run: pip install requests beautifulsoup4")

    resp = requests.get(url, timeout=20, headers={"User-Agent": "Mozilla/5.0"})
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")
    for tag in soup(["script", "style", "nav", "footer", "header"]):
        tag.decompose()
    title = soup.title.string.strip() if soup.title and soup.title.string else url
    text = soup.get_text(separator=" ")
    return title, text


def auto_ingest_file(path):
    ext = Path(path).suffix.lower()
    if ext == ".pdf":
        return ingest_pdf(path), "pdf"
    if ext == ".docx":
        return ingest_docx(path), "docx"
    if ext == ".epub":
        return ingest_epub(path), "epub"
    if ext in (".txt", ".md"):
        return ingest_txt(path), "txt"
    raise SystemExit(f"Unsupported file type: {ext}. Supported: .pdf .docx .epub .txt .md")
