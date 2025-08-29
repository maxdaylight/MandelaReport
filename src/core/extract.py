# pyright: reportMissingImports=false
try:
    from selectolax.parser import HTMLParser  # type: ignore
except Exception:  # pragma: no cover - runtime fallback
    HTMLParser = None  # type: ignore


def extract_title_text(html: str):
    """Extract a short title and a textual body from HTML.

    Use selectolax if available for speed; otherwise fall back to
    BeautifulSoup + html5lib so the project can run without compiling
    native wheels (useful on Windows/CI without build tools).
    """
    if HTMLParser is not None:
        doc = HTMLParser(html)
        title = (doc.css_first("title").text() if doc.css_first("title") else "")[:300]
        for sel in ["script", "style", "noscript", "svg", "canvas"]:
            for n in doc.css(sel):
                n.decompose()
        main = (
            doc.css_first("article") or doc.css_first("main") or doc.css_first("body")
        )
        text = (
            main.text(separator=" ", strip=True)
            if main
            else doc.text(separator=" ", strip=True)
        )
        return title, text[:80000]

    # Fallback using BeautifulSoup
    from bs4 import BeautifulSoup  # type: ignore[import]

    soup = BeautifulSoup(html, "html5lib")
    title_tag = soup.find("title")
    title = (title_tag.get_text() if title_tag else "")[:300]
    for tag in soup.find_all(["script", "style", "noscript", "svg", "canvas"]):
        tag.decompose()
    main = soup.find("article") or soup.find("main") or soup.find("body")
    text = main.get_text(" ", strip=True) if main else soup.get_text(" ", strip=True)
    return title, text[:80000]
