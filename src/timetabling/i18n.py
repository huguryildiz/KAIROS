"""Tiny i18n layer for the UI. Pure + import-light so it stays unit-testable.

Pages read the current language from st.session_state["lang"] (default "tr") and
call t(key, lang, **kwargs). Strings carry {placeholders} formatted via str.format.
"""
from __future__ import annotations

LANGS = ("tr", "en")
DEFAULT_LANG = "en"

# Localized day labels for the timetable grid, keyed by the internal day code.
DAY_LABELS = {
    "tr": {"Mo": "Pzt", "Tu": "Sal", "We": "Çar", "Th": "Per", "Fr": "Cum", "Sa": "Cmt"},
    "en": {"Mo": "Mon", "Tu": "Tue", "We": "Wed", "Th": "Thu", "Fr": "Fri", "Sa": "Sat"},
}

STRINGS = {
    "tr": {
        "lang_label": "Dil / Language",
        "nav_home": "Ana sayfa",
        # app shell (single-flow UI)
        "app_title": "Kairos",
        "app_subtitle": "Ders programlama · CP-SAT",
        "theme_toggle": "Tema",
        "step_review": "Veriyi incele",
        "hero_stat_sections": "Şube / dönem",
        "hero_stat_conflicts": "Sert çakışma",
        "hero_stat_placed": "Yerleştirme",
        "hero_stat_engine": "Çözüm motoru",
        "hero_stat_speed": "Çözüm süresi",
        "hero_stat_speed_v": "Dakikalar",
        "hero_dur_min": "dk",
        # review step
        "review_header": "Yüklenen veri",
        "review_caption": "Çözmeden önce kapsamı doğrula. Uyarılar engelleyici değildir.",
        # sample data
        "upload_dropzone_title": "CSV dosyasını buraya bırakın",
        "upload_dropzone_sub": "veya bilgisayarınızdan seçin · maks. 200 MB · yalnızca .csv",
        "upload_sample_btn": "+ Örnek veri seti ile dene",
        "upload_sample_caption": "Gerçek CSV gerekmez — **Örnek veri seti** ile tüm akışı şimdi deneyebilirsiniz.",
        # kpi labels
        "kpi_sections": "Şube",
        "kpi_courses": "Ders",
        "kpi_depts": "Bölüm",
        "kpi_instructors": "Eğitmen",
        "kpi_rooms": "Derslik",
        "kpi_labs": "Laboratuvar",
        "kpi_maxcap": "Maks. kapasite",
        "kpi_online": "Online oda",
        # hero (landing)
        "hero_title_html": "Her ders, <em>çakışmasız</em> bir haftalık programda.",
        "hero_body": "Ders listeni yükle, dersliklerini tanımla. Gerisini motor halleder: "
                     "her şube otomatik olarak gün, saat ve dersliğe yerleşir — oda, eğitmen "
                     "ve laboratuvar çakışması olmadan.",
        "step_upload": "Ders yükle",
        "step_classrooms": "Derslikler",
        "step_solve": "Çöz",
        "step_results": "Sonuçlar",
        "start_hint": "Kenar çubuğundan başla → **Ders yükle**.",
        # upload
        "upload_header": "Ders yükle",
        "upload_caption": "Her satır bir şube. Sütunlar: `Course Code, Course Name, Section No, "
                          "T, P, L, Lecturer Name, Lecturer Email, ~Students`.",
        "upload_example_expander": "Örnek format (3 satır)",
        "upload_uploader": "Ders listesi (CSV)",
        "upload_loaded": "{n} satır yüklendi.",
        "upload_current": "Şu an {n} satır yüklü — değiştirmek için yeniden yükle.",
        "upload_none": "Henüz dosya yok. Örnek: examples/courses_demo.csv.",
        "upload_format_label": "Her satır bir şube — beklenen sütunlar:",
        "upload_format_tpl": "T = haftalık teori saati · P = pratik / tartışma saati · L = laboratuvar saati",
        # validation warnings
        "upload_error_title": "Dosya okunamadı.",
        "upload_error_hint": "Geçerli bir UTF-8 CSV dosyası yükle ya da örnek veri setini dene.",
        "warn_no_rows": "Yüklenen dosyada satır yok.",
        "warn_missing_cols": "Eksik zorunlu sütun(lar): {cols}",
        "warn_zero_hours": "{n} satırda T+P+L=0 (3 saatlik teori bloğuna varsayıldı).",
        "warn_blank_email": "{n} satırda eğitmen e-postası boş (eğitmen çakışma kontrolü dışı).",
        "warn_bad_code": "{n} satırda çözümlenemeyen ders kodu (kohort = UNK).",
        "info_part_time": "{n} eğitmen '(S)' ile yarı zamanlı algılandı.",
        # CSV import preview (VERA-style)
        "import_detected": "Algılanan sütunlar",
        "import_positional": "konuma göre",
        "import_valid": "geçerli",
        "import_duplicate": "yinelenen",
        "import_error": "hata",
        "import_total": "toplam",
        "import_preview_heading": "İçe aktarma önizlemesi",
        "import_col_row": "Satır",
        "import_col_status": "Durum",
        "import_skipped_note": "{skipped} satır atlandı · {valid} geçerli satır içe aktarıldı.",
        "import_status_ok": "Geçerli",
        "import_status_dup": "Yinelenen",
        "import_status_dup_file": "Dosyada yinelenen",
        "import_status_err_code": "Ders kodu eksik",
        "import_status_err_hours": "Geçersiz T/P/L",
        # classrooms
        "cr_header": "Derslikler",
        "cr_caption": "Derslik ekle, sil veya düzenle. Lab, oda adından (-L / -PC) algılanır "
                      "ama elle değiştirilebilir. Online sanal oda çözüm anında otomatik eklenir.",
        "cr_upload_expander": "⬆ CSV ile derslik listesi yükle",
        "cr_upload_hint": "Sütunlar: Room, Cap (ve isteğe bağlı Lab). Ham veri formatı "
                          "ROOM, ROOM_CAP da kabul edilir; Lab verilmezse oda adından "
                          "(-L / -PC) türetilir.",
        "cr_upload_uploader": "Derslik CSV'si seç",
        "cr_upload_loaded": "{n} derslik yüklendi.",
        "cr_upload_error": "Geçersiz CSV: 'Room' (veya 'ROOM') sütunu bulunamadı.",
        "cr_reset": "↺ Varsayılanlara dön",
        "cr_col_room": "Oda",
        "cr_col_cap": "Kapasite",
        "cr_col_lab": "Lab",
        "cr_count": "{n} derslik tanımlı.",
        "cr_edit_header": "Derslik ekle / düzenle",
        "cr_edit_pick": "Düzenlenecek derslik",
        "cr_new_room": "+ Yeni derslik",
        "cr_save": "Kaydet",
        "cr_remove": "Sil",
        "cr_saved": "“{room}” kaydedildi.",
        "cr_removed": "“{room}” silindi.",
        "cr_need_name": "Oda adı boş olamaz.",
        # solve
        "solve_header": "Çöz",
        "solve_need_upload": "Önce bir ders listesi yükle (Ders yükle sayfası).",
        "solve_ready": "{c} ders satırı · {r} derslik hazır.",
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
        "res_view_course": "Ders",
        "res_no_assign": "Gösterilecek atama yok.",
        "res_grid_caption": "dolu = teori · renk = bölüm",
        "res_dl_json": "📋  schedule.json  ·  indir",
        "res_dl_csv": "📊  assignments.csv  ·  indir",
        "res_unsched_title": "Yerleşemeyen şubeler ({n})",
        # grid (ui_style)
        "grid_empty": "Gösterilecek oturum yok.",
        # footer
        "footer_dev": "Geliştiren",
    },
    "en": {
        "lang_label": "Dil / Language",
        "nav_home": "Home",
        "app_title": "Kairos",
        "app_subtitle": "Course timetabling · CP-SAT",
        "theme_toggle": "Theme",
        "step_review": "Review data",
        "hero_stat_sections": "Sections / term",
        "hero_stat_conflicts": "Hard conflicts",
        "hero_stat_placed": "Placement",
        "hero_stat_engine": "Solver engine",
        "hero_stat_speed": "Solve time",
        "hero_stat_speed_v": "Minutes",
        "hero_dur_min": "min",
        "review_header": "Uploaded data",
        "review_caption": "Review the scope before solving. Warnings are informational, not blocking.",
        "upload_dropzone_title": "Drop your CSV file here",
        "upload_dropzone_sub": "or browse from your computer · max 200 MB · CSV only",
        "upload_sample_btn": "+ Try with sample dataset",
        "upload_sample_caption": "No real CSV needed — try the **full flow** right now with sample data.",
        "kpi_sections": "Sections",
        "kpi_courses": "Courses",
        "kpi_depts": "Departments",
        "kpi_instructors": "Instructors",
        "kpi_rooms": "Rooms",
        "kpi_labs": "Labs",
        "kpi_maxcap": "Max capacity",
        "kpi_online": "Online room",
        "hero_title_html": "Every section, placed on a <em>conflict-free</em> weekly grid.",
        "hero_body": "Upload your course list and define your rooms. The engine handles the rest — "
                     "every section lands on a day, time, and room, with no room, instructor, "
                     "or lab clashes.",
        "step_upload": "Upload courses",
        "step_classrooms": "Classrooms",
        "step_solve": "Solve",
        "step_results": "Results",
        "start_hint": "Start from the sidebar → **Upload courses**.",
        "upload_header": "Upload courses",
        "upload_caption": "One row per section. Columns: `Course Code, Course Name, Section No, "
                          "T, P, L, Lecturer Name, Lecturer Email, ~Students`.",
        "upload_example_expander": "Example format (3 rows)",
        "upload_uploader": "Course list (CSV)",
        "upload_loaded": "Loaded {n} rows.",
        "upload_current": "{n} rows currently loaded — re-upload to replace.",
        "upload_none": "No file yet. Try the sample at examples/courses_demo.csv.",
        "upload_format_label": "One row per section — expected columns:",
        "upload_format_tpl": "T = weekly theory hours · P = practice / discussion hours · L = lab hours",
        "upload_error_title": "Could not read the file.",
        "upload_error_hint": "Make sure the file is a valid UTF-8 CSV, or try the sample dataset.",
        "warn_no_rows": "No rows found in the uploaded file.",
        "warn_missing_cols": "Missing required column(s): {cols}",
        "warn_zero_hours": "{n} row(s) have T+P+L=0 (defaulted to a 3h theory block).",
        "warn_blank_email": "{n} row(s) have a blank lecturer email "
                            "(excluded from instructor no-overlap).",
        "warn_bad_code": "{n} row(s) have an unparseable course code (cohort = UNK).",
        "info_part_time": "{n} lecturer(s) detected as part-time via '(S)'.",
        # CSV import preview (VERA-style)
        "import_detected": "Detected columns",
        "import_positional": "positional",
        "import_valid": "valid",
        "import_duplicate": "duplicate",
        "import_error": "error",
        "import_total": "total",
        "import_preview_heading": "Import preview",
        "import_col_row": "Row",
        "import_col_status": "Status",
        "import_skipped_note": "{skipped} row(s) skipped · {valid} valid row(s) imported.",
        "import_status_ok": "Valid",
        "import_status_dup": "Duplicate",
        "import_status_dup_file": "Duplicate in file",
        "import_status_err_code": "Missing course code",
        "import_status_err_hours": "Invalid T/P/L",
        "cr_header": "Classrooms",
        "cr_caption": "Add, remove, or edit rooms. Lab is detected from room name (-L / -PC) "
                      "but can be overridden. The Online virtual room is added automatically "
                      "at solve time.",
        "cr_upload_expander": "⬆ Upload a room list via CSV",
        "cr_upload_hint": "Columns: Room, Cap (and optional Lab). The raw data format "
                          "ROOM, ROOM_CAP is also accepted; when Lab is omitted it is "
                          "derived from the room name (-L / -PC).",
        "cr_upload_uploader": "Choose a rooms CSV",
        "cr_upload_loaded": "{n} room(s) loaded.",
        "cr_upload_error": "Invalid CSV: no 'Room' (or 'ROOM') column found.",
        "cr_reset": "↺ Reset to defaults",
        "cr_col_room": "Room",
        "cr_col_cap": "Capacity",
        "cr_col_lab": "Lab",
        "cr_count": "{n} room(s) defined.",
        "cr_edit_header": "Add / edit a room",
        "cr_edit_pick": "Room to edit",
        "cr_new_room": "+ New room",
        "cr_save": "Save",
        "cr_remove": "Remove",
        "cr_saved": "“{room}” saved.",
        "cr_removed": "“{room}” removed.",
        "cr_need_name": "Room name can't be empty.",
        "solve_header": "Solve",
        "solve_need_upload": "Upload a course list first (Upload page).",
        "solve_ready": "{c} course rows · {r} rooms ready.",
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
        "res_view_course": "Course",
        "res_no_assign": "No assignments to display.",
        "res_grid_caption": "solid = theory · color = department",
        "res_dl_json": "📋  Download schedule.json",
        "res_dl_csv": "📊  Download assignments.csv",
        "res_unsched_title": "Unschedulable sections ({n})",
        "grid_empty": "No sessions to show.",
        # footer
        "footer_dev": "Developed by",
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
