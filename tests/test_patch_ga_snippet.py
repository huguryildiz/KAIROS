from patch_ga_snippet import patch_html, MEASUREMENT_ID


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
