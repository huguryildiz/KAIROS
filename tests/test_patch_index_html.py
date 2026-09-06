from patch_index_html import (MEASUREMENT_ID, PAGE_DESCRIPTION, PAGE_TITLE,
                              main, patch_html, patch_seo)


def test_patch_html_inserts_snippet_before_head_close():
    html = "<html><head><title>x</title></head><body></body></html>"

    patched = patch_html(html, MEASUREMENT_ID)

    assert MEASUREMENT_ID in patched
    assert patched.index(MEASUREMENT_ID) < patched.index("</head>")


def test_patch_html_is_idempotent():
    html = "<html><head><title>x</title></head><body></body></html>"
    once = patch_html(html, MEASUREMENT_ID)

    twice = patch_html(once, MEASUREMENT_ID)

    assert once == twice
    assert twice.count(MEASUREMENT_ID) == 2  # once in the src=, once in gtag('config', ...)


def test_patch_html_uses_given_measurement_id():
    html = "<html><head></head><body></body></html>"

    patched = patch_html(html, "G-TESTID123")

    assert "G-TESTID123" in patched
    assert MEASUREMENT_ID not in patched


def test_patch_seo_replaces_title_and_adds_description():
    html = "<html><head><title>Streamlit</title></head><body></body></html>"

    patched = patch_seo(html)

    assert "<title>Streamlit</title>" not in patched
    assert f"<title>{PAGE_TITLE}</title>" in patched
    assert PAGE_DESCRIPTION in patched
    assert 'rel="canonical"' in patched
    assert 'property="og:title"' in patched
    assert patched.index('name="description"') < patched.index("</head>")


def test_patch_seo_replaces_noscript_placeholder():
    html = ("<html><head><title>Streamlit</title></head><body>"
            "<noscript>You need to enable JavaScript to run this app.</noscript>"
            "</body></html>")

    patched = patch_seo(html)

    assert "<noscript>You need to enable JavaScript" not in patched
    assert f"<noscript><h1>{PAGE_TITLE}</h1>" in patched


def test_patch_seo_is_idempotent():
    html = "<html><head><title>Streamlit</title></head><body></body></html>"
    once = patch_seo(html)

    assert patch_seo(once) == once


def test_main_patches_index_and_writes_static_files(tmp_path):
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text(
        "<html><head><title>Streamlit</title></head><body></body></html>",
        encoding="utf-8",
    )

    main(str(static_dir))

    html = (static_dir / "index.html").read_text(encoding="utf-8")
    assert MEASUREMENT_ID in html
    assert PAGE_DESCRIPTION in html
    assert "Sitemap:" in (static_dir / "robots.txt").read_text(encoding="utf-8")
    assert "<urlset" in (static_dir / "sitemap.xml").read_text(encoding="utf-8")
    assert (static_dir / "favicon.png").exists()  # copied from repo assets/
