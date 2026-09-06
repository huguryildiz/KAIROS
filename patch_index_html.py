"""Patches Streamlit's installed static/index.html for analytics + SEO.

Streamlit ships a single-page shell whose crawlable HTML says only
`<title>Streamlit</title>` and "You need to enable JavaScript to run this app"
— so search engines index that instead of KAIROS. `st.set_page_config` only
fixes the title at runtime (JS), which crawlers may never execute.

This script rewrites the shell at Docker build time:
  * GA4 gtag.js snippet,
  * title / description / canonical / Open Graph / Twitter / JSON-LD,
  * KAIROS favicon over Streamlit's, plus robots.txt and sitemap.xml.

Build time only (see Dockerfile) — it patches the container image's copy of
Streamlit, never the local dev venv, so `streamlit run` locally never fires GA
and never shows the patched metadata.
"""
import os
import shutil
import sys

MEASUREMENT_ID = "G-3WR6GHJPN0"

SITE_URL = "https://kairos.huguryildiz.com/"
SITE_NAME = "KAIROS"
PAGE_TITLE = "KAIROS — University Course Timetabling Solver"
PAGE_DESCRIPTION = (
    "KAIROS builds conflict-free university course timetables in your browser. "
    "Upload course and classroom CSVs, set instructor and room preferences, and "
    "get a day/time/room assignment for every section — solved with CP-SAT."
)
OG_IMAGE = SITE_URL + "favicon.png"

_SEO_MARKER = '<meta name="description"'

_JSON_LD = f"""<script type="application/ld+json">
{{
  "@context": "https://schema.org",
  "@type": "WebApplication",
  "name": "{SITE_NAME}",
  "url": "{SITE_URL}",
  "description": "{PAGE_DESCRIPTION}",
  "applicationCategory": "EducationalApplication",
  "operatingSystem": "Web browser",
  "inLanguage": ["en", "tr"],
  "offers": {{"@type": "Offer", "price": "0", "priceCurrency": "USD"}}
}}
</script>"""

ROBOTS_TXT = f"""User-agent: *
Allow: /

Sitemap: {SITE_URL}sitemap.xml
"""

SITEMAP_XML = f"""<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
  <url>
    <loc>{SITE_URL}</loc>
    <changefreq>monthly</changefreq>
    <priority>1.0</priority>
  </url>
</urlset>
"""


def build_snippet(measurement_id: str) -> str:
    return (
        f'<script async src="https://www.googletagmanager.com/gtag/js?id={measurement_id}"></script>\n'
        "<script>\n"
        "  window.dataLayer = window.dataLayer || [];\n"
        "  function gtag(){dataLayer.push(arguments);}\n"
        "  gtag('js', new Date());\n"
        f"  gtag('config', '{measurement_id}');\n"
        "</script>"
    )


def build_seo_head() -> str:
    return "\n".join([
        f'<meta name="description" content="{PAGE_DESCRIPTION}" />',
        '<meta name="robots" content="index, follow" />',
        f'<link rel="canonical" href="{SITE_URL}" />',
        '<meta property="og:type" content="website" />',
        f'<meta property="og:site_name" content="{SITE_NAME}" />',
        f'<meta property="og:title" content="{PAGE_TITLE}" />',
        f'<meta property="og:description" content="{PAGE_DESCRIPTION}" />',
        f'<meta property="og:url" content="{SITE_URL}" />',
        f'<meta property="og:image" content="{OG_IMAGE}" />',
        '<meta name="twitter:card" content="summary" />',
        f'<meta name="twitter:title" content="{PAGE_TITLE}" />',
        f'<meta name="twitter:description" content="{PAGE_DESCRIPTION}" />',
        f'<meta name="twitter:image" content="{OG_IMAGE}" />',
        _JSON_LD,
    ]) + "\n"


def patch_html(html: str, measurement_id: str) -> str:
    """Inject the GA4 snippet just before </head> (idempotent)."""
    if measurement_id in html:
        return html
    return html.replace("</head>", build_snippet(measurement_id) + "</head>", 1)


def build_noscript() -> str:
    return (
        "<noscript>"
        f"<h1>{PAGE_TITLE}</h1>"
        f"<p>{PAGE_DESCRIPTION}</p>"
        "<p>JavaScript is required to run this app.</p>"
        "</noscript>"
    )


def patch_seo(html: str) -> str:
    """Replace the placeholder title/noscript and add crawlable metadata (idempotent)."""
    if _SEO_MARKER in html:
        return html
    html = html.replace("<title>Streamlit</title>", f"<title>{PAGE_TITLE}</title>", 1)
    html = html.replace(
        "<noscript>You need to enable JavaScript to run this app.</noscript>",
        build_noscript(), 1)
    return html.replace("</head>", build_seo_head() + "</head>", 1)


def default_static_dir() -> str:
    import streamlit
    return os.path.join(os.path.dirname(streamlit.__file__), "static")


def install_static_files(static_dir: str, assets_dir: str) -> None:
    """Overwrite Streamlit's favicon and drop robots.txt / sitemap.xml at root."""
    favicon = os.path.join(assets_dir, "favicon.png")
    if os.path.exists(favicon):
        shutil.copyfile(favicon, os.path.join(static_dir, "favicon.png"))
    for name, body in (("robots.txt", ROBOTS_TXT), ("sitemap.xml", SITEMAP_XML)):
        with open(os.path.join(static_dir, name), "w", encoding="utf-8") as f:
            f.write(body)


def main(static_dir=None, measurement_id=MEASUREMENT_ID) -> None:
    static_dir = static_dir or default_static_dir()
    path = os.path.join(static_dir, "index.html")
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    patched = patch_seo(patch_html(html, measurement_id))
    if patched != html:
        with open(path, "w", encoding="utf-8") as f:
            f.write(patched)
    install_static_files(static_dir, os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets"))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
