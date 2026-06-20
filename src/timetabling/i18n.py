"""Tiny i18n layer for the UI. Pure + import-light so it stays unit-testable.

Pages read the current language from st.session_state["lang"] (default "tr") and
call t(key, lang, **kwargs). Strings carry {placeholders} formatted via str.format.
"""
from __future__ import annotations

LANGS = ("tr", "en")
DEFAULT_LANG = "tr"

# Localized day labels for the timetable grid, keyed by the internal day code.
DAY_LABELS = {
    "tr": {"Mo": "Pzt", "Tu": "Sal", "We": "Çar", "Th": "Per", "Fr": "Cum", "Sa": "Cmt"},
    "en": {"Mo": "Mon", "Tu": "Tue", "We": "Wed", "Th": "Thu", "Fr": "Fri", "Sa": "Sat"},
}

STRINGS = {
    "tr": {
        "lang_label": "Dil / Language",
        # hero (landing)
        "hero_eyebrow": "Üniversite ders programlama",
        "hero_title_html": "Her ders, <em>çakışmasız</em> bir haftalık programda.",
        "hero_body": "Ders listeni yükle, derslikleri ayarla; CP-SAT çözücü her şubeye "
                     "gün, saat ve derslik atasın — oda, eğitmen veya lab çakışması olmadan.",
        "step_upload": "Ders yükle",
        "step_classrooms": "Derslikler",
        "step_solve": "Çöz",
        "step_results": "Sonuçlar",
        "start_hint": "Kenar çubuğundan başla → **Ders yükle**.",
        # upload
        "upload_header": "Ders yükle",
        "upload_caption": "Her satır bir şube. Sütunlar: Course Code, Course Name, Section No, "
                          "T, P, L, Lecturer Name, Lecturer Email, ~Students.",
        "upload_uploader": "Ders listesi (CSV)",
        "upload_loaded": "{n} satır yüklendi.",
        "upload_current": "Şu an {n} satır yüklü — değiştirmek için yeniden yükle.",
        "upload_none": "Henüz dosya yok. Örnek: examples/courses_demo.csv.",
        # validation warnings
        "warn_no_rows": "Yüklenen dosyada satır yok.",
        "warn_missing_cols": "Eksik zorunlu sütun(lar): {cols}",
        "warn_zero_hours": "{n} satırda T+P+L=0 (3 saatlik teori bloğuna varsayıldı).",
        "warn_blank_email": "{n} satırda eğitmen e-postası boş (eğitmen çakışma kontrolü dışı).",
        "warn_bad_code": "{n} satırda çözümlenemeyen ders kodu (kohort = UNK).",
        "info_part_time": "{n} eğitmen '(S)' ile yarı zamanlı algılandı.",
        # classrooms
        "cr_header": "Derslikler",
        "cr_caption": "Derslik ekle, sil veya düzenle. Lab, oda adından (-L / -PC) algılanır "
                      "ama elle değiştirilebilir. Online sanal oda çözüm anında otomatik eklenir.",
        "cr_reset": "↺ Varsayılanlara dön",
        "cr_col_room": "Oda",
        "cr_col_cap": "Kapasite",
        "cr_col_lab": "Lab",
        "cr_count": "{n} derslik tanımlı.",
        # solve
        "solve_header": "Çöz",
        "solve_need_upload": "Önce bir ders listesi yükle (Ders yükle sayfası).",
        "solve_ready": "{c} ders satırı · {r} derslik hazır.",
        "solve_period": "Dönem",
        "solve_period_help": "001 = Güz, 002 = Bahar",
        "solve_timelimit": "Süre limiti (saniye)",
        "solve_button": "Programı çöz",
        "solve_spinner": "{n} şube çözülüyor…",
        "solve_done": "{a} blok yerleşti · {v} sert çakışma · {u} yerleşemeyen.",
        "solve_see_results": "Sonuçlara git →",
        # results
        "res_header": "Sonuçlar",
        "res_no_solution": "Henüz çözüm yok — önce Çöz sayfasından çalıştır.",
        "res_m_placed": "Yerleşen",
        "res_m_conflicts": "Sert çakışma",
        "res_m_rooms": "Kullanılan oda",
        "res_m_unsched": "Yerleşemeyen",
        "res_view_by": "Şuna göre görüntüle",
        "res_view_cohort": "Kohort",
        "res_view_room": "Oda",
        "res_view_instructor": "Eğitmen",
        "res_view_dept": "Bölüm",
        "res_no_assign": "Gösterilecek atama yok.",
        "res_grid_caption": "{n} blok · dolu çubuk = teori · kesik çubuk = lab · "
                            "renk = bölüm · ayrıntı için bloğun üzerine gel.",
        "res_dl_json": "schedule.json indir",
        "res_dl_csv": "assignments.csv indir",
        "res_unsched_title": "Yerleşemeyen şubeler ({n})",
        # grid (ui_style)
        "grid_empty": "Gösterilecek oturum yok.",
    },
    "en": {
        "lang_label": "Dil / Language",
        "hero_eyebrow": "University course timetabling",
        "hero_title_html": "Every section, placed on a <em>conflict-free</em> weekly grid.",
        "hero_body": "Upload your course list, set your rooms, and let the CP-SAT solver assign "
                     "a day, time, and room to each section — no double-booked rooms, "
                     "instructors, or labs.",
        "step_upload": "Upload courses",
        "step_classrooms": "Classrooms",
        "step_solve": "Solve",
        "step_results": "Results",
        "start_hint": "Start from the sidebar → **Upload courses**.",
        "upload_header": "Upload courses",
        "upload_caption": "One row per section. Columns: Course Code, Course Name, Section No, "
                          "T, P, L, Lecturer Name, Lecturer Email, ~Students.",
        "upload_uploader": "Course list (CSV)",
        "upload_loaded": "Loaded {n} rows.",
        "upload_current": "{n} rows currently loaded — re-upload to replace.",
        "upload_none": "No file yet. Try the sample at examples/courses_demo.csv.",
        "warn_no_rows": "No rows found in the uploaded file.",
        "warn_missing_cols": "Missing required column(s): {cols}",
        "warn_zero_hours": "{n} row(s) have T+P+L=0 (defaulted to a 3h theory block).",
        "warn_blank_email": "{n} row(s) have a blank lecturer email "
                            "(excluded from instructor no-overlap).",
        "warn_bad_code": "{n} row(s) have an unparseable course code (cohort = UNK).",
        "info_part_time": "{n} lecturer(s) detected as part-time via '(S)'.",
        "cr_header": "Classrooms",
        "cr_caption": "Add, remove, or edit rooms. Lab is detected from room name (-L / -PC) "
                      "but can be overridden. The Online virtual room is added automatically "
                      "at solve time.",
        "cr_reset": "↺ Reset to defaults",
        "cr_col_room": "Room",
        "cr_col_cap": "Capacity",
        "cr_col_lab": "Lab",
        "cr_count": "{n} room(s) defined.",
        "solve_header": "Solve",
        "solve_need_upload": "Upload a course list first (Upload page).",
        "solve_ready": "{c} course rows · {r} rooms ready.",
        "solve_period": "Period",
        "solve_period_help": "001 = Fall, 002 = Spring",
        "solve_timelimit": "Time limit (seconds)",
        "solve_button": "Solve timetable",
        "solve_spinner": "Solving {n} sections…",
        "solve_done": "Placed {a} blocks · {v} hard conflicts · {u} unschedulable.",
        "solve_see_results": "See results →",
        "res_header": "Results",
        "res_no_solution": "No solution yet — run a solve first (Solve page).",
        "res_m_placed": "Placed",
        "res_m_conflicts": "Hard conflicts",
        "res_m_rooms": "Rooms used",
        "res_m_unsched": "Unschedulable",
        "res_view_by": "View by",
        "res_view_cohort": "Cohort",
        "res_view_room": "Room",
        "res_view_instructor": "Instructor",
        "res_view_dept": "Department",
        "res_no_assign": "No assignments to display.",
        "res_grid_caption": "{n} blocks · solid bar = theory · dashed bar = lab · "
                            "color = department · hover a block for details.",
        "res_dl_json": "Download schedule.json",
        "res_dl_csv": "Download assignments.csv",
        "res_unsched_title": "Unschedulable sections ({n})",
        "grid_empty": "No sessions to show.",
    },
}


def t(key: str, lang: str = DEFAULT_LANG, **kwargs) -> str:
    lang = lang if lang in STRINGS else DEFAULT_LANG
    s = STRINGS[lang].get(key) or STRINGS[DEFAULT_LANG].get(key) or key
    if kwargs:
        try:
            return s.format(**kwargs)
        except (KeyError, IndexError):
            return s
    return s
