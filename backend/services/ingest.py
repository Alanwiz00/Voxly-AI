import io
import asyncio
import pdfplumber
import docx
from firecrawl import FirecrawlApp
from core.config import settings

_firecrawl: FirecrawlApp | None = None


def get_firecrawl() -> FirecrawlApp:
    global _firecrawl
    if _firecrawl is None:
        _firecrawl = FirecrawlApp(api_key=settings.FIRECRAWL_API_KEY)
    return _firecrawl


def extract_from_pdf(file_bytes: bytes) -> str:
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        return "\n".join(page.extract_text() or "" for page in pdf.pages)


def extract_from_docx(file_bytes: bytes) -> str:
    doc = docx.Document(io.BytesIO(file_bytes))
    return "\n".join(p.text for p in doc.paragraphs if p.text.strip())


async def extract_from_url(url: str) -> str:
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: get_firecrawl().scrape_url(url, params={"formats": ["markdown"]}),
    )
    return result.get("markdown", "")[:12000]


def extract_from_text(text: str) -> str:
    return text.strip()


async def ingest(
    text: str | None = None,
    file_bytes: bytes | None = None,
    file_type: str | None = None,  # "pdf" | "docx"
    url: str | None = None,
) -> str:
    if text:
        return extract_from_text(text)
    if file_bytes and file_type == "pdf":
        return extract_from_pdf(file_bytes)
    if file_bytes and file_type == "docx":
        return extract_from_docx(file_bytes)
    if url:
        return await extract_from_url(url)
    return ""
