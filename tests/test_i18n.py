from timetabling.i18n import t, STRINGS, LANGS


def test_default_is_turkish():
    # the bare key resolves to Turkish by default
    assert t("hero_eyebrow") == STRINGS["tr"]["hero_eyebrow"]


def test_english_when_asked():
    assert t("solve_button", "en") == STRINGS["en"]["solve_button"]
    assert t("solve_button", "tr") != t("solve_button", "en")


def test_format_kwargs():
    assert "5" in t("upload_loaded", "tr", n=5)
    assert "5" in t("upload_loaded", "en", n=5)


def test_missing_key_falls_back_to_key():
    assert t("___nope___", "tr") == "___nope___"


def test_langs_and_parity():
    assert set(LANGS) == {"tr", "en"}
    # every TR key has an EN counterpart and vice versa
    assert set(STRINGS["tr"]) == set(STRINGS["en"])


def test_new_ui_keys_bilingual():
    keys = ["app_title", "appbar_waiting", "theme_toggle", "step_review",
            "review_header", "upload_sample_btn", "kpi_sections", "kpi_rooms",
            "hero_stat_sections"]
    for k in keys:
        for lang in LANGS:
            assert t(k, lang) and t(k, lang) != k        # present, actually translated
    assert "793" in t("appbar_loaded", "tr", n=793)
    assert "793" in t("appbar_loaded", "en", n=793)
