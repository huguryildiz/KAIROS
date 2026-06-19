# Timetabling Efficiency Analysis: 2025-01 and 2025-02 Plan Files

**Source files:** `data/2025-01-Plan.csv` · `data/2025-02-Plan.csv`  
**Date of analysis:** 2026-06-19  
**Institution:** TOBB ETÜ

---

## File Overview

| | 2025-01 (Fall) | 2025-02 (Spring) |
|---|---|---|
| Total data rows | 1,062 | 1,056 |
| ZSURVEY=0001 — lecture sections | 866 | 861 |
| ZSURVEY=0002 — admin/thesis/practice | 175 | 175 |
| Unique departments (Period 1) | 33 | 35 |

> **Note:** ZSURVEY=0002 rows (thesis, summer practice, PhD exams) have no physical room assignments by design and use administrative placeholder times. All substantive analysis below covers Period 1 (lecture sections) unless stated otherwise.

---

## 1. Room Utilization (SECT_CAP / ROOM_CAP)

Rows with both capacity fields populated and numeric. Online sections (ROOM_CAP=9999) are included in the raw count but excluded from the underutilization analysis.

| Metric | 2025-01 | 2025-02 |
|---|---|---|
| Rows with capacity data | 795 | 772 |
| Average SECT_CAP / ROOM_CAP ratio | **64.3%** | **66.3%** |
| Overcapacity (SECT_CAP > ROOM_CAP) | **23** | **15** |
| Underutilized (SECT_CAP < 50% of ROOM_CAP) | **187** | **201** |

Nearly 1 in 4 lecture sections has a section cap below half the room capacity. Top departments with underutilized assignments: Basic Sciences, English Language Education, Educational Sciences, English Literature, and Computer Engineering — mostly small graduate seminars assigned to large classrooms.

---

## 2. Day Distribution

Counts represent "section-day slots" — a Tu/Fr section contributes one slot to each day.

| Day | 2025-01 | 2025-02 |
|---|---|---|
| Monday | 253 | 225 |
| Tuesday | 278 | 263 |
| Wednesday | 275 | 276 |
| Thursday | 239 | 251 |
| Friday | 200 | 214 |

**Friday is consistently the lightest day** — roughly 20–25% fewer slots than Tuesday/Wednesday in both semesters. The Tuesday–Wednesday pairing carries the heaviest load across both terms.

---

## 3. Time Slot Distribution

Each schedule block (including multi-block entries) is counted separately.

| Slot | 2025-01 | Share | 2025-02 | Share |
|---|---|---|---|---|
| Early morning 09–<12 | 489 | 38.3% | 477 | 37.8% |
| Midday 12–<15 | 405 | 31.7% | 415 | 32.9% |
| Afternoon 15–<18 | 284 | 22.3% | 268 | 21.3% |
| Evening 18+ | 98 | 7.7% | 101 | 8.0% |

**Extreme 09:00 concentration:** 313 blocks (2025-01) and 322 blocks (2025-02) start at 09:00, while only 16–21 blocks start at 10:00. Three-hour morning blocks lock rooms from 09:00 to noon, compressing the rest of the schedule into a narrower afternoon window. The 10:00 and 17:00 hours are nearly empty in both terms.

---

## 4. Evening Courses (any block starting at 18:00 or later)

| Department | 2025-01 | 2025-02 |
|---|---|---|
| Department of Psychology | — | 20 |
| Graduate School | 23 | 18 |
| Department of Business Administration | 4 | 15 |
| Dep. of English Language and Literature | 11 | 12 |
| Department of Economics | 6 | 8 |
| Basic Sciences | 17 | 6 |
| Dep. of Political Science & Intern. Rel. | 7 | 3 |
| Applied Data Science | 4 | 3 |
| Department of Mathematics | 6 | — |
| Management in Educational Institutions | 5 | 3 |

Total evening sections: **~98–101 per semester**. Graduate School is consistently heavy. The large 2025-02 jump for Psychology (0 → 20) and Business Administration (4 → 15) reflects term-specific course offerings; several of the BA evening entries are Graduation Paper supervision rows with no physical room booking.

---

## 5. Lecturer Load

Threshold: 5 or more sections in a single period (Period 1 only). Multi-lecturer studio strings are counted as a single entry, so design studio lecturers are slightly under-counted individually.

**2025-01 — 40 lecturers at ≥5 sections:**

| Sections | Lecturer |
|---|---|
| 12 | Fahri Dikkaya |
| 12 | Fatma Akın Çelebi |
| 8 | Aylin Tekiner Tolu |
| 7 | Tolga Kurtuluş Çapın, Erdem Aksoy, Javad Momeni Kolour, Melike İrem Alhas, Erdem Kayserilioğlu (S) |
| 6 | Kıymet Duygu Erdaş, Eren Ulu, Anıl Özdemir, Fırat Akba, Günnur Ege Bilgin, Taner Can, Michael Douglas Sheridan, Ece Çakır (S), Çağan Aksak (S), Mehmet Onur Fen, Bengisen Pekmen, Merve Gürbüz Çaldağ |
| 5 | Orhan Gencel, İrem Asena Güney Aslan (S), Işıl Sevilay Yılmaz, Niyazi Anıl Gezer, Mehmet Evren Coşkun, Seyit Mümin Cılasun, Meltem Dayıoğlu Tayfur, Yeşer Torun, Mehmet Sak, Oliver David Bevington, Başak Ağın, Sinem Sözen Özdoğan, İlknur Aka (S), Aslı Bayar (S), Ruşen Kaya, Şeyda Yıldız, Engin Özkan, Selin Onaylı, Ayşegül Aracı İyiaydın, Yağmur Ar |

**2025-02 — 35 lecturers at ≥5 sections:**

| Sections | Lecturer |
|---|---|
| 8 | Melike İrem Alhas |
| 7 | Fahri Dikkaya, Bengisen Pekmen |
| 6 | Can Armutlu, Anıl Özdemir, Jülide Yıldırım Öcal, Meltem Dayıoğlu Tayfur, Erdem Aksoy, Oliver David Bevington, Javad Momeni Kolour, Cemre Mimoza Bartu Esen (S), Ece Çakır (S), Erdem Kayserilioğlu (S), Emrah Keser, Buse Merve Ürgen, Burcu Altın, Fatma Akın Çelebi |
| 5 | Aslı Yüksel, Ali Berkol (S), Selin Akyüz Tursun, Arzu Kanat Mutluoğlu, Michael Douglas Sheridan, Aylin Tekiner Tolu, Aslı Bayar (S), Senem Yıldırım Özdem, Engin Özkan, Niyazi Anıl Gezer, Mehmet Onur Fen, Fuat Erdem, Adile Aylin Özman Erkman, Tuba Şahin İlikoğlu, Çağlayan Özdemir, Bağdat Deniz Kaynak, Deniz Okay, Yağmur Ar |

---

## 6. Missing Room Assignments

| | 2025-01 | 2025-02 |
|---|---|---|
| Period 1 — lecture sections without a room | **71** | **89** |
| Period 2 — admin sections without a room | 173 | 171 |

Period 2 gaps are expected by design. The Period 1 gaps represent actual teaching sections without a physical room. Notable cases: Architecture 4th-year design studio (ARCH 401 / ARCH 402), several CE/Civil Engineering summer practice entries mistakenly placed in Period 1, and some BA Graduation Paper sections.

---

## 7. Overcapacity Cases (SECT_CAP > ROOM_CAP)

### 2025-01 — 23 cases

| Section | SECT_CAP | ROOM_CAP | Room | Schedule |
|---|---|---|---|---|
| ADS 525_01 | 30 | 24 | A435 | We 18–21 |
| CMPE 327_04 | 50 | 30 | D228 / A437 | We 09–10 / Mo 09–11 |
| EE 309-O_01 | 30 | 24 | A435 / A317-MF-L | Tu/Fr 14–16 |
| EE 309_01 | 30 | 24 | A317-MF-L / A435 | Fr/Tu 14–16 |
| IE 232_01 | 30 | 24 | A422 | Th 11–12 / Tu 16–18 |
| IE 311_01 | 30 | 24 | A422 / A435 / A316-L | Tu 13–14 / We 11–13 |
| IE 331_01 | 31 | 24 | A422 | Tu 11–12 / Th 12–14 |
| MATH 105_01 | 30 | 24 | A437 / A435 | We 09–11 / Fr 12–13 |
| MATH 113-O_1 | 25 | 24 | A435 / A211-PC-L / A437 | Th 11–13 / Fr 14–15 / Tu 14–16 |
| MATH 113_01 | 25 | 24 | A435 / A211-PC-L / A437 | Th 11–13 / Fr 14–15 / Tu 14–16 |
| MATH 114-O_1 | 25 | 24 | A422 / A435 / A211-PC-L | Tu 09–11 / Mo 09–11 / Fr 15–16 |
| MATH 114_01 | 25 | 24 | A422 / A435 / A211-PC-L | Tu 09–11 / Mo 09–11 / Fr 15–16 |
| MATH 211-O_1 | 30 | 24 | A422 / A437 | We 14–16 / Mo 14–16 |
| MATH 211_01 | 30 | 24 | A422 / A437 | We 14–16 / Mo 14–16 |
| MATH 212-O_1 | 30 | 24 | A422 | We 12–14 / Mo 12–14 |
| MATH 212_01 | 30 | 24 | A422 | We 12–14 / Mo 12–14 |
| MATH 313_01 | 25 | 24 | A437 / A422 | We 16–18 / Mo 16–18 |
| MATH 321_01 | 25 | 24 | A435 / A437 | Tu 09–11 / Th 12–14 |
| MATH 331_01 | 25 | 24 | A437 / A211-PC-L / A422 | Th 10–12 / Tu 14–15 |
| MATH 333_01 | 25 | 24 | A211-PC-L / A435 | Mo 13–16 / We 15–16 |
| MATH 435_01 | 25 | 24 | A422 / B171 | We 09–12 |
| PHYS 105_01 | 34 | 24 | A435 | Tu 11–13 / Fr 11–12 |
| SOC 223_01 | 25 | 24 | A422 | Fr 09–12 |

**18 of 23 cases are Mathematics courses** — all in A-block rooms (A422, A435, A437, A211-PC-L) with a fixed capacity of 24, systematically assigned to sections capped at 25–30. This is a department-level room-type mismatch, not individual planning errors.

### 2025-02 — 15 cases

| Section | SECT_CAP | ROOM_CAP | Room | Schedule |
|---|---|---|---|---|
| ADA 423_01 | 40 | 27 | F306 | Th 11–14 |
| EE 342_01 | 25 | 24 | A435 / A422 | Tu 09–11 / Mo 11–12 |
| IE 222_02 | 35 | 30 | A437 | Tu 11–12 / We 16–18 |
| MATH 113_01 | 30 | 24 | A211-PC-L / A435 | Fr/We/Mo 11–13 |
| MATH 211_01 | 30 | 24 | A422 | Mo/We 16–18 |
| MATH 221_01 | 30 | 24 | A435 / A422 | Mo 13–15 / We 12–14 |
| MATH 222_01 | 30 | 24 | A435 | We 09–11 / Th 16–18 |
| MATH 314_01 | 30 | 24 | A422 | Mo/We 14–16 |
| MATH 322_01 | 30 | 24 | A435 / A422 | Fr/Th 09–11 |
| MATH 352_01 | 30 | 24 | A422 / A435 | Various |
| MATH 401_01 | 30 | 24 | A422 | Tu 09–12 |
| ME 336_01 | 21 | 20 | G201 | We 15–18 |
| ME 362_01 | 21 | 20 | G009 / G101 | We 11–13 / Mo 13–14 |
| PHYS 105_01 | 25 | 24 | A422 | Tu/Fr |
| SOC 104_01 | 25 | 24 | A435 / A331 | Tu/Th |

The Mathematics room mismatch persists (10 of 15 cases). ME 336 and ME 362 have a 1-student margin (SECT_CAP 21 vs. ROOM_CAP 20) — likely data entry errors.

---

## 8. Multi-day / Split Sections

| File | Period 1 |
|---|---|
| 2025-01 | 16 |
| 2025-02 | 19 |

All multi-day sections (SCHEDULE contains "/") are Architecture, City Planning, Interior Design, and Visual Communication Design studios following the "Tu/Fr 09–13 Tu/Fr 14–15" full-day pattern. These are structurally intentional and expected.

---

## Summary

| Criterion | Assessment |
|---|---|
| Day balance | Acceptable — Friday consistently ~20% lighter than Tue/Wed |
| Room utilization | Weak — 65% mean occupancy; 187–201 sections under 50% fill |
| Overcapacity violations | Critical — Math department systematic room mismatch |
| Start-time distribution | 09:00 severely overloaded; 10:00 and 17:00 nearly empty |
| Unassigned rooms (Period 1) | 71–89 lecture sections have no room |
| Lecturer workload | 40 / 35 lecturers carry ≥5 sections; top two at 12 each |
| Evening sections | ~100/semester; Graduate School + Psychology + English Lit heaviest |

### Implications for the CP-SAT Solver

The Math department overcapacity issue originates in the Plan input data. Until A-block room capacities are corrected (or Math SECT_CAPs adjusted down to ≤24), the solver will reproduce the same constraint violations. One fix option: in `clean.py`, set a minimum room capacity filter for Math sections, or raise `ROOM_CAP` for A422/A435/A437 if the physical rooms have been reconfigured since the data was recorded.
