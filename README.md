# Course Timetabling — Üniversite Ders Çizelgeleme (UCTP)

Gerçek üniversite verisinden **çakışmasız haftalık ders programı** üreten bir
OR-Tools **CP-SAT** modeli. Her section'a **gün + saat + oda** atar; section/hoca/
büyüklük/T-P-L sabit girdidir (karar değişkenleri yalnızca **zaman ve oda**).

> **Bu faz (Faz 1):** uçtan uca çalışan pipeline + departman/fakülte dilimlerinde
> kanıtlanmış feasibility. Tam dönem (~800 section) çözümü ve web arayüzü
> sonraki fazlarda — bkz. [TODO.md](TODO.md).

İlgili dokümanlar:
- Tasarım spec'i: [docs/superpowers/specs/2026-06-19-course-timetabling-cpsat-design.md](docs/superpowers/specs/2026-06-19-course-timetabling-cpsat-design.md)
- Uygulama planı: [docs/superpowers/plans/2026-06-19-uctp-cpsat-pipeline.md](docs/superpowers/plans/2026-06-19-uctp-cpsat-pipeline.md)
- Problem spesifikasyonu: [prompts/university_course_timetabling_prompt.md](prompts/university_course_timetabling_prompt.md)

---

## Kurulum

```bash
python3 -m pip install -r requirements.txt   # pandas, ortools, pytest
```

## Çalıştırma

```bash
PYTHONPATH=src python3 -m timetabling --period 001 \
    --scope faculty="Department of Psychology" --mode A,B --time-limit 60
```

**Parametreler:**

| Bayrak | Değerler | Açıklama |
|---|---|---|
| `--period` | `001` (Güz) \| `002` (Bahar) | Çizelgelenecek dönem (bağımsız) |
| `--scope` | `all` \| `faculty=<metin>` \| `dept=<KOD>` | Çözülecek dilim. `faculty` Grades `Dept.` kolonunu, `dept` cohort dept kodunu eşler |
| `--mode` | `A,B` (varsayılan) \| `A` \| `B` | A = sıfırdan çöz, B = mevcut programla benchmark |
| `--time-limit` | saniye (varsayılan 60) | CP-SAT çözüm süre sınırı |
| `--out` | dizin (varsayılan `out/`) | Çıktı klasörü |

Tüm diğer parametreler (blackout saatleri, zaman pencereleri, objective ağırlıkları,
`max_rooms_per_block`, toggle'lar) [src/timetabling/config.py](src/timetabling/config.py)
içindeki `Config` dataclass'ında.

## Çıktılar (`out/`)

- **`schedule_<period>.json`** — arayüzün tüketeceği şema. Her atama:
  `section_id, course_code, course_name, block_kind, instructor_id, instructor_name,
  cohort, dept, students, day, start, end, room, room_cap, is_lab_room, flags`;
  ayrıca `period`, `meta`, `unmet_soft`, `conflicts`.
- **`schedule_<period>.csv`** — aynı atamaların düz tablo hâli.
- **`data_quality_<period>.json`** — parse/oda/cohort/join sağlaması, lab-oda tablosu,
  çizelgelenemeyen (oversize / blok > gün penceresi) section listesi.
- **`mode_b_<period>.json`** — üretilen program ↔ mevcut program (çakışma sayıları,
  oda kullanımı, akşam oranı).

## Test

```bash
python3 -m pytest -q        # 39 test
```

---

## Mimari

```
src/timetabling/
  config.py         Config dataclass + tüm parametreler, DAYS
  model.py          Room, Instructor, Block, Section, Candidate, Assignment, Violation
  textnorm.py       Staff ID / isim / int normalizasyonu
  schedule_parse.py SCHEDULE grameri (birim / zincir / X/Y / kirli→flag)
  io_csv.py         quote-aware CSV yükleyiciler (period eklemeli)
  clean.py          oda sınıflama (lab/online/fiziksel), hoca master nesneleri
  join.py           Grades ⨝ enrollment ⨝ Plan birleşik tablosu
  derive.py         Section+Block türetme (level, cohort, T+P/L blokları, hariç tutma)
  model_cpsat.py    aday üretimi + pruning + CP-SAT model + çözüm
  validate.py       çözücüden bağımsız hard-constraint doğrulayıcı
  report.py         veri kalitesi + Mode-B benchmark
  export.py         schedule.json + CSV
  __main__.py       CLI / pipeline orkestrasyonu
```

Hard kısıtların çoğu **aday üretiminde** uygulanır (yalnızca legal `(oda, gün, saat)`
yerleşimleri üretilir): kapasite, lab-odası, lisans <18:00 penceresi, Cuma 13–14 ve
Perşembe 14–16 (tam zamanlı) blackout'lar. Modelde yalnızca **H1 yerleşim** ve
**H2–H4 oda/hoca/cohort çakışmazlığı** açık kısıt olarak yer alır. `validate.py`
çözümü modelden **bağımsız** yeniden denetler — çözücü hatası sessizce geçemez.

---

## Doğrulanmış sonuçlar (dönem 001)

Her dilim mevcut programı çakışma / oda sayısı / akşam oranında geçer:

| Dilim | Section | Durum | Hard ihlal | Mode A vs mevcut |
|---|---|---|---|---|
| ADA bölümü | 5 | OPTIMAL | 0 | 1 oda vs 4 |
| Econ fakültesi | 16 | OPTIMAL | 0 | 5 oda vs 13, 0 vs 9 çakışma |
| Psychology | 35 | FEASIBLE | 0 | 6 oda vs 19, 0 vs 36 çakışma |
| Architecture | 12 (+5 studio hariç) | OPTIMAL | 0 | 3 oda vs 10 |

---

## Bilinen sınırlamalar (bu fazda kabul edilen — detay: [TODO.md](TODO.md))

1. **Cohort proxy `(Dept_Code, Year_Level)`** servis/seçmeli derslerde ve *aynı dersin
   birden çok section'ında* fazla kısıtlayıcı → bu fakültelerde infeasible
   (örn. ENG-1: 47 section / 188 saat, haftada ~45 saatlik pencereye sığmaz).
2. **Uzun bloklar** (studio; T+P ≥ 10 saat tek blok) gün penceresine sığmaz →
   çok-güne bölme gerekir; şu an hariç tutulup raporlanır.
3. **Oversize section'lar** (öğr. sayısı > en büyük oda 100) → hariç tutulup raporlanır.
4. **Çok-hocalı section'lar** (Grades `Staff ID`'de virgülle iki kimlik) tek sentetik
   hoca olarak ele alınır; isim eşleşmesi boş kalır.
5. **Tam dönem (~800 section)** çözümü #1–#2 nedeniyle olduğu gibi çözülmez —
   sonraki faz işidir.
