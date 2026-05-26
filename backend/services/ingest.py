import base64
import io
import asyncio
import pdfplumber
import docx
from firecrawl import FirecrawlApp
from core.config import settings
from services.sentiment import get_openai

_firecrawl: FirecrawlApp | None = None

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}
IMAGE_MIME_TYPES = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
    ".gif": "image/gif",
    ".bmp": "image/bmp",
}


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


async def extract_from_image(file_bytes: bytes, mime_type: str) -> str:
    """
    Use GPT-4o vision to extract and interpret image content.
    Handles screenshots, infographics, photos of text, charts, and handwriting.
    """
    b64 = base64.b64encode(file_bytes).decode("utf-8")
    response = await get_openai().chat.completions.create(
        model=settings.OPENAI_GENERATION_MODEL,
        messages=[
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:{mime_type};base64,{b64}",
                            "detail": "high",
                        },
                    },
                    {
                        "type": "text",
                        "text": (
                            "Analyze this image and extract all useful content for writing social media posts about it.\n\n"
                            "- If it contains text (screenshot, article, quote, slide): transcribe it in full.\n"
                            "- If it contains charts or data: describe the key numbers, trends, and insights.\n"
                            "- If it shows a product, event, or scene: describe what's shown and why it matters.\n"
                            "- If it's an infographic: capture each section's key points.\n\n"
                            "Be thorough and specific. Return the extracted content as structured plain text."
                        ),
                    },
                ],
            }
        ],
        max_tokens=2000,
    )
    return response.choices[0].message.content or ""


async def extract_from_url(url: str) -> str:
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        None,
        lambda: get_firecrawl().scrape_url(url, formats=["markdown"]),
    )
    # firecrawl-py 1.x returns a ScrapeResponse object; older versions returned a dict
    if isinstance(result, dict):
        markdown = result.get("markdown", "")
    else:
        markdown = getattr(result, "markdown", None) or ""
    return markdown[:12000]


def extract_from_text(text: str) -> str:
    return text.strip()


async def ingest(
    text: str | None = None,
    file_bytes: bytes | None = None,
    file_type: str | None = None,  # "pdf" | "docx" | "image"
    mime_type: str | None = None,
    url: str | None = None,
) -> str:
    if text:
        return extract_from_text(text)
    if file_bytes and file_type == "pdf":
        return extract_from_pdf(file_bytes)
    if file_bytes and file_type == "docx":
        return extract_from_docx(file_bytes)
    if file_bytes and file_type == "image" and mime_type:
        return await extract_from_image(file_bytes, mime_type)
    if url:
        return await extract_from_url(url)
    return ""
