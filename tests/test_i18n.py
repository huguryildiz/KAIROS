from timetabling.i18n import t, STRINGS, LANGS, DEFAULT_LANG


def test_default_lang_is_english():
    # the bare key resolves to the configured default (English)
    assert DEFAULT_LANG == "en"
    assert t("app_subtitle") == STRINGS["en"]["app_subtitle"]


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
    keys = ["app_title", "theme_toggle", "step_review",
            "review_header", "upload_sample_btn", "kpi_sections", "kpi_rooms",
            "hero_stat_sections", "footer_dev"]
    for k in keys:
        for lang in LANGS:
            assert t(k, lang) and t(k, lang) != k        # present, actually translated
