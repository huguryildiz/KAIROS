# START — Çizelgeleme Modeli Başlangıç Prompt'u

`course-timetabling` projesinde üniversite ders çizelgeleme (UCTP) modelini kur. Detaylı spesifikasyon **`prompts/university_course_timetabling_prompt.md`** dosyasında; veriler **`data/`** altında (`2025-01/02-Grades.csv`, `*-Plan.csv`, `enrollment_by_section.csv`, `classrooms.csv`, `lecturers.csv`, kurallar: `rules.pdf`). Bu prompt'u **önce baştan sona oku**, sonra başla.

**Amaç:** Her section'a **gün + saat + oda** ata (karar değişkenleri yalnızca zaman ve oda; section/hoca/büyüklük/T-P-L sabit girdi). Öncelik 1: çakışmasız (feasible); öncelik 2: soft constraint kalitesi. İki dönemi (001 Güz, 002 Bahar) ayrı çizelgele.

**Yerleşmiş kararlar (detaylı prompt'la tutarlı):**
- Roster = **Grades** (yalnızca lisans, düzey 1–4). Grad (5XX+6XX) sadece Plan'da; varsayılan kapsam dışı.
- **Lisans dersleri 18:00'den önce bitmeli** (hard). Grad akşam 18:00–21:00 tercihi (soft, grad dahil edilirse).
- **Cuma namazı blackout: Cuma 13:00–14:00** tüm section'lara kapalı (hard, parametre).
- **Seminer blackout: Perşembe 14:00–16:00** tam zamanlı hocalara kapalı (hard, parametre).
- **`rules.pdf` Madde 1 (2+1 / ardışık ≤3 saat) IGNORE** — uygulanmaz, raporlanmaz.
- Diğer hard kısıtlar: hoca / cohort `(Dept, Year)` / oda çakışması, oda kapasitesi ≥ section, lab dersi (`L>0`) → lab odası.

**Çıktı:**
1. Veri kalitesi raporu + normalize tablo şeması.
2. Matematiksel formülasyon (kümeler, parametreler, karar değişkenleri, hard/soft, amaç).
3. Çalışan **Python iskeleti:** quote-aware CSV → temizlik → join → `SCHEDULE` parse → cohort/lab türetme → **OR-Tools CP-SAT** model → çöz → validasyon → CSV/JSON export. JSON şeması sonraki adımdaki shadcn arayüzü tarafından tüketilecek.

**Mod:** Mod A (sıfırdan, varsayılan) + Mod B (mevcut programla benchmark) birlikte.
