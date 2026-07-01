"""Injects the GA4 gtag.js snippet into Streamlit's installed static/index.html.

Run at Docker build time only (see Dockerfile) — this patches the container
image's copy of Streamlit, never the local dev venv, so `streamlit run`
locally never fires GA.
"""
import os
import sys

MEASUREMENT_ID = "G-3WR6GHJPN0"


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


def patch_html(html: str, measurement_id: str) -> str:
    if measurement_id in html:
        return html
    return html.replace("</head>", build_snippet(measurement_id) + "</head>", 1)


def default_index_path() -> str:
    import streamlit
    return os.path.join(os.path.dirname(streamlit.__file__), "static", "index.html")


def main(path=None, measurement_id=MEASUREMENT_ID) -> None:
    path = path or default_index_path()
    with open(path, "r", encoding="utf-8") as f:
        html = f.read()
    patched = patch_html(html, measurement_id)
    if patched != html:
        with open(path, "w", encoding="utf-8") as f:
            f.write(patched)


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
