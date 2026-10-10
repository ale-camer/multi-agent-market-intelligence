"""HTML parser extracting clean headlines, body content, and metadata from articles."""

import re
from typing import Any

from bs4 import BeautifulSoup, Tag


class NewsHTMLParser:
    """HTML article content extractor with boilerplate removal."""

    STRIP_TAGS: list[str] = [
        "script",
        "style",
        "nav",
        "header",
        "footer",
        "aside",
        "form",
        "noscript",
        "svg",
        "iframe",
    ]

    @classmethod
    def parse(cls, html: str, fallback_source: str = "web") -> dict[str, Any]:
        """Parse raw HTML string and extract article headline, content, and metadata.

        Args:
            html: Raw HTML content.
            fallback_source: Default source identifier if not found in metadata.

        Returns:
            Dictionary containing headline, content, source, and metadata.
        """
        if not html or not html.strip():
            return {
                "headline": "Untitled Article",
                "content": "",
                "source": fallback_source,
                "metadata": {},
            }

        soup = BeautifulSoup(html, "html.parser")

        # Extract metadata before stripping tags
        metadata: dict[str, Any] = cls._extract_metadata(soup)
        source = str(metadata.get("site_name") or fallback_source)

        # Extract headline before decomposition
        headline = cls._extract_headline(soup)

        # Decompose non-content boilerplate elements
        for tag_name in cls.STRIP_TAGS:
            for element in soup.find_all(tag_name):
                element.decompose()

        # Extract main text body
        content = cls._extract_content(soup)

        return {
            "headline": headline,
            "content": content,
            "source": source,
            "metadata": metadata,
        }

    @classmethod
    def _extract_headline(cls, soup: BeautifulSoup) -> str:
        """Resolve article headline from OpenGraph, meta tags, h1, or title."""
        # 1. OpenGraph title
        og_title = soup.find("meta", property="og:title")
        if isinstance(og_title, Tag) and og_title.get("content"):
            title_text = str(og_title["content"]).strip()
            if title_text:
                return title_text

        # 2. Twitter title
        tw_title = soup.find("meta", attrs={"name": "twitter:title"})
        if isinstance(tw_title, Tag) and tw_title.get("content"):
            title_text = str(tw_title["content"]).strip()
            if title_text:
                return title_text

        # 3. Meta title
        meta_title = soup.find("meta", attrs={"name": "title"})
        if isinstance(meta_title, Tag) and meta_title.get("content"):
            title_text = str(meta_title["content"]).strip()
            if title_text:
                return title_text

        # 4. First <h1> tag
        h1 = soup.find("h1")
        if isinstance(h1, Tag):
            h1_text = h1.get_text(strip=True)
            if h1_text:
                return h1_text

        # 5. <title> tag
        title_tag = soup.find("title")
        if isinstance(title_tag, Tag):
            title_tag_text = title_tag.get_text(strip=True)
            if title_tag_text:
                return title_tag_text

        return "Untitled Article"

    @classmethod
    def _extract_content(cls, soup: BeautifulSoup) -> str:
        """Extract clean body text from <article> or paragraph elements."""
        container = soup.find("article") or soup.find("main") or soup.find("body") or soup

        paragraphs = container.find_all("p")
        cleaned_paragraphs: list[str] = []
        for p in paragraphs:
            text = p.get_text(separator=" ", strip=True)
            # Remove excessive inner whitespace
            text = re.sub(r"\s+", " ", text)
            if text and len(text) > 10:  # Skip tiny fragments
                cleaned_paragraphs.append(text)

        if cleaned_paragraphs:
            return "\n\n".join(cleaned_paragraphs)

        # Fallback to general text extraction if no <p> tags found
        raw_text = container.get_text(separator="\n", strip=True)
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        return "\n\n".join(lines)

    @classmethod
    def _extract_metadata(cls, soup: BeautifulSoup) -> dict[str, Any]:
        """Extract OpenGraph and meta article attributes."""
        metadata: dict[str, Any] = {}

        og_site = soup.find("meta", property="og:site_name")
        if isinstance(og_site, Tag) and og_site.get("content"):
            metadata["site_name"] = str(og_site["content"]).strip()

        og_desc = soup.find("meta", property="og:description")
        if isinstance(og_desc, Tag) and og_desc.get("content"):
            metadata["description"] = str(og_desc["content"]).strip()

        author = soup.find("meta", attrs={"name": "author"})
        if isinstance(author, Tag) and author.get("content"):
            metadata["author"] = str(author["content"]).strip()

        pub_time = soup.find("meta", property="article:published_time")
        if isinstance(pub_time, Tag) and pub_time.get("content"):
            metadata["published_time"] = str(pub_time["content"]).strip()

        return metadata
