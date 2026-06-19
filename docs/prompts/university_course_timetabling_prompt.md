# University Course Timetabling Prompt

`data/` klasöründeki gerçek CSV dosyalarını analiz ederek üniversite ders çizelgeleme problemi için **çakışmasız** bir atama modeli geliştirmeni istiyorum. Bu sadece basit bir greedy atama problemi değildir; büyük ölçekli bir **University Course Timetabling Problem (UCTP)** olarak ele alınmalı, Operations Research bakışıyla (conflict graph, integer/constraint programming, feasibility repair) çözülmelidir.

> **Not:** Bu prompt'un önceki sürümü tek bir Excel "Ek-3. Section Data" sekmesi varsayıyordu. Gerçek veri **8 ayrı CSV** dosyasıdır ve önemli farklar içerir (aşağıdaki "Veri Gerçekleri" bölümüne bak). Modeli gerçek veriye göre kur.
>
> **Kapsam (sabit girdiler):** Hangi section'ın açılacağı, **hangi hocanın hangi dersi/section'ı verdiği**, section büyüklüğü ve ders saatleri (T/P/L) **sabit girdilerdir** — yeniden atanmaz. **Amaç yalnızca timetable üretmek:** her section'a **gün + saat + oda** atamak. Yani `LECTURER`, `cohort`, `Students`, `T/P/L` birer **parametredir**; **karar değişkenleri sadece zaman ve odadır.**

---

## Görev Modu

Veride **zaten atanmış bir ders programı var** (`SCHEDULE` kolonu). Bu nedenle görevi üç moddan biri/birkaçı olarak ele al. **Varsayılan: Mod A + Mod B birlikte.**

- **Mod A — Sıfırdan kurma (öğrenme/optimizasyon, varsayılan):** Mevcut `SCHEDULE` atamasını **yok say**, sadece yapısal veriyi (ders, hoca, saat sayısı, cohort, kontenjan, oda havuzu) girdi al ve sıfırdan çakışmasız bir program üret.
- **Mod B — Benchmark / doğrulama (varsayılan):** Mevcut programı *ground truth* olarak parse et, tüm çakışmaları raporla ve Mod A çıktısını mevcut programla karşılaştır (oda kullanımı, çakışma sayısı, akşam dersi oranı vb.).
- **Mod C — Onarım / warm-start (opsiyonel):** Mevcut programı başlangıç çözümü (hint) olarak ver, sadece çakışan atamaları onararak çözücüyü hızlandır.

---

## Gerçek Veri Kaynakları (`data/`)

Tüm dosyalar **virgülle ayrılmış, tırnaklı alanlar içerebilen** CSV'dir. **Naive `split(",")` KULLANMA** — bazı `COURSE_NAME` alanları tırnak içinde virgül içerir ve kolonları kaydırır. `pandas.read_csv` veya `csv` modülü (quote-aware) kullan.

| Dosya | Satır | Rol | Anahtar Kolonlar |
|---|---|---|---|
| `2025-01-Grades.csv`, `2025-02-Grades.csv` | ~841 / ~826 | **YETKİLİ ROSTER: hangi ders + hangi hoca + hangi dönem açıldı** + ders saatleri (T/P/L/Cr) + gerçek öğrenci sayısı | `Period`, `Code`, `Section`, `T`, `P`, `L`, `Cr`, `ECTS`, `Category`, `Lecturer`, `Staff ID`, `Room`, `Schedule`, `# of Students` |
| `2025-01-Plan.csv`, `2025-02-Plan.csv` | ~1059 / ~1056 | Mevcut oda+saat programı + kontenjanlar (Grades'e göre daha geniş superset) | `COURSE_CODE`, `COURSE_NAME`, `DEPT`, `SECTION`, `LECTURER`, `ROOM`, `SCHEDULE`, `SECT_CAP`, `ROOM_CAP` |
| `enrollment_by_section.csv` | 1667 | **Cohort anahtarı + section kontenjanı** | `Period`, `Dept_Code`, `Dept_Name`, `Year_Level`, `Course_Code`, `Section`, `Students` |
| `enrollment_summary.csv` | 132 | Bölüm×sınıf düzeyi özetleri (sağlama için) | `Dept_Code`, `Year_Level`, `Total_Sections`, `Total_Students`, `Avg/Max_Students` |
| `classrooms.csv` | 101 | **Oda havuzu (master room list)** | `ROOM`, `ROOM_CAP` |
| `lecturers.csv` | 340 | **Öğretim elemanı master listesi** | `Staff_ID`, `Name`, `Is_Staff`, `Dept` |

### Birleştirme (Join) Haritası

Ana birleştirme anahtarı: **`Section` + `Period`** (örn. `ADA 403_01` + `001`).

```text
Grades (YETKİLİ ROSTER: section + course + lecturer + period + T/P/L/Cr + Staff ID + #students)
  ⨝ enrollment_by_section  ON Section+Period   → cohort = (Dept_Code, Year_Level), Students
  ⨝ lecturers              ON Staff_ID          → Is_Staff (tam/yarı zaman), hocanın ev bölümü
  ⨝ Plan (LEFT JOIN)       ON Section+Period   → mevcut SCHEDULE + ROOM (benchmark/warm-start), SECT_CAP
  + classrooms (room master)                   → ROOM_CAP, lab-uygunluğu (isimden türet)
```

- **`Period` (dönem):** **`001` = Güz / Fall**, **`002` = Bahar / Spring**. **Her dönemi bağımsız çizelgele** (iki ayrı timetable). Bir section'ın hangi dönem açıldığı Grades'in `Period` kolonunda kesindir.
- **Çizelgelenecek roster (yetkili):** Hangi dersin **hangi hoca** tarafından **hangi dönem** açıldığı **Grades dosyalarında** kesindir (`Code`/`Section` + `Lecturer`/`Staff ID` + `Period`). Bu, çizelgelenecek section kümesinin ve hoca↔ders eşleşmesinin **ground truth**'udur. Plan yalnızca mevcut oda+saat programını ve kontenjanları ekler; Grades'te olmayan ~225 Plan section'ı muhtemelen açılmadı/kayıt almadı → **varsayılan olarak roster'dan hariç tut** (opsiyonel toggle ile dahil edilebilir).
- **Hoca join anahtarı:** Tercihen `Staff_ID` (Grades `Staff ID` ⨝ lecturers `Staff_ID`); isim eşleşmesi kirlidir (~266/345 ad eşleşir, `(S)`/boşluk normalizasyonu gerekir).
- **Section ID formatı:** `"<COURSE_CODE>_<NN>"` (örn. `MATH 101_02`). `-O` gibi ekler şube varyantı olabilir (`ARCH 301-O_1`).

---

## Doğrulanmış Veri Gerçekleri (001 dönemi referans)

Modeli bu doğrulanmış sayılara göre ölçekle:

- **~1059 section / dönem**, **2 dönem**.
- **345 öğretim elemanı** Plan'da (`LECTURER` distinct); **`lecturers.csv` master listesinde 340** kayıt. *(Not: `(S)` eki = isim üzerindeki işaret, temizle.)*
- Hoca kadro durumu (`lecturers.Is_Staff`): **114 tam zamanlı (True)** / **226 yarı zamanlı/dış (False)**. Hocaların ev bölümü 30 distinct (offering department'tan ayrıdır).
- **101 oda**, bunlardan **1'i `Online` (kapasite 9999, placeholder)** → ~100 fiziksel oda.
- **52 bölüm**, **sınıf düzeyleri 1–4**.
- **~14 lab/PC odası** isim ekinden tanımlanabilir: `-PC-L`, `-L`, `-PSY-L`, `-PSCG-L`, `-PECE-L`, `-EF-L`. Kapasiteleri 20–99.
- Oda kapasiteleri: 20–100 arası (medyan ~40), + 1 outlier (9999 = Online).
- Ders saati profili (Grades T/P/L/Cr): en sık `3/0/0/3` (380 ders, düz 3 saat teorik), `2/2/0/3` (129), lab içeren `2/0/2/3` (46), `3/0/2/4` (19) vb.
- **386 / 1062 section çok-oturumlu** (`SCHEDULE` birden fazla gün/blok içeriyor).

---

## Türetilmiş Kavramlar (veride doğrudan yok — sen türeteceksin)

1. **Öğrenci grubu / cohort:** Veride öğrenci ID'si veya açık grup listesi **yoktur**. Cohort'u **`(Dept_Code, Year_Level)`** olarak tanımla (örn. `ARCH-1`). Bu, problemi **curriculum-based timetabling (CB-CTT)** yapar: aynı cohort'a ait section'lar aynı anda olamaz (öğrenciler ortak kabul edilir). Bu bir *yaklaşımdır* — sınırlarını açıkça belirt.
2. **Ders saati (slot sayısı):** Roster Grades olduğu için her section'ın `T` (teorik) + `L` (lab) saati zaten mevcuttur → toplam haftalık blok = `T + L` (uygunsa `P` pratik). Yalnızca opsiyonel olarak dahil edilen Plan-only section'lar için saat bilgisi eksiktir → ders kodundan/Cr'den tahmin et veya varsayılan (3 saat) ata ve raporla.
3. **Lab gereksinimi:** Bir section lab gerektirir ⟺ Grades `L > 0`. Lab dersi yalnızca lab odasına (isim eki `-L`/`PC` içeren) atanmalı. **`classrooms.csv`'de oda tipi kolonu yoktur** → lab-uygunluğunu oda adından çıkar ve bu eşlemeyi açıkça bir tabloya yaz.
4. **Kontenjan:** Section büyüklüğü için `enrollment_by_section.Students` (yoksa Plan `SECT_CAP`) kullan. Oda kapasitesi ≥ section büyüklüğü olmalı.
5. **Çizelgelenmeyecek kayıtlar:** Grades `Category` ∈ {`Internship` (48), bazı `Mandatory (YOK)`} → staj/uzaktan kayıtlar oda+slot tüketmeyebilir; ayıkla ve raporla.
6. **Ders düzeyi (course level):** Ders kodundaki üç haneli sayının ilk hanesinden türet. **1–4 = lisans (undergraduate)**, **5 = yüksek lisans, 6 = doktora → 5XX+6XX = lisansüstü (graduate)**. Bu düzey, "level-based time window" zaman kısıtını (lisans 18:00'den önce biter — hard; grad akşam tercihli — soft) belirler. Bkz. *Zaman Modeli*.

---

## Zaman Modeli ve `SCHEDULE` Parse Etme

- **Zaman ufku:** Pazartesi–Cuma (`Mo, Tu, We, Th, Fr`). Veride Cmt/Pazar gözlenmedi.
- **Slot granülaritesi:** 1 saatlik bloklar, **09:00–21:00** (akşam dersleri 18:00–20:00 gözlendi). → 12 slot/gün × 5 gün = 60 slot.
- **Ders düzeyine göre zaman penceresi (level-based time window):** Ders kodundaki sayıdan düzey türetilir.
  - **Lisans (undergraduate) = kod sayısı 1XX–4XX (5XX/6XX olmayan):** ders **18:00'den önce bitmeli** → izinli başlangıç blokları 09–17 (son blok bitişi ≤ 18:00). Bu **hard** kısıttır.
  - **Lisansüstü (graduate) = 5XX (yüksek lisans) + 6XX (doktora):** dersler **18:00–21:00 akşam** penceresinde olmalı/tercih edilmeli. Bu **soft** tercihtir (gündüze de izin verilir; ör. veride `ARCH 510 Tu 09 - 12`, `ARCH 540 Mo 13 - 16` gibi gündüz işlenen grad section'lar mevcuttur).
  - **Cuma namazı blackout:** **Cuma 13:00–14:00** tüm section'lara kapalı (hard, parametre). 002 verisinde bu saatte doluluk komşu saatlerin ~%15'ine düşer → desen doğrulanır. 001'de daha zayıf olduğundan saat dönem/mevsime göre ayarlanabilir tutulur.
  - **Veri gerçeği — kapsam:** Yetkili roster **Grades** dosyalarıdır ve **yalnızca lisans (düzey 1–4) içerir**; 5XX/6XX section'lar **yalnızca Plan dosyalarında** görülür. Varsayılan kapsamda **yalnızca lisans çizelgelenir** → grad evening kuralı pratikte "lisans dersleri 18:00'den önce bitmeli" hard kısıtı olarak uygulanır. Plan-only grad section'lar opsiyonel toggle ile dahil edilirse yukarıdaki grad soft tercihi devreye girer.
- **`SCHEDULE` formatı** (parse edilmeli, mevcut programdan):
  - Temel birim: `"<Gün> <başlangıç> - <bitiş>"`, saatler tam sayı (24h). Örn. `Fr 13 - 16` = Cuma 13:00–16:00 (3 blok).
  - **Çok-oturum:** Birimler boşlukla zincirlenir. Örn. `Th 09 - 12 Th 13 - 16` = Perşembe iki ayrı blok.
  - **Çok-gün notasyonu `X/Y`:** `Tu/Fr 09 - 12` = **hem Salı hem Cuma** 09:00–12:00. Genişlet: iki ayrı oturum.
- **Kirli `SCHEDULE` değerleri** (~11 satır): CSV kayması yüzünden bu alanda hoca adı/oda kodu (`Işıl Sevilay Yılmaz`, `D232`) görülebilir. Geçerli gün token'ı ile başlamayanları **parse hatası** olarak işaretle, otomatik onarmaya çalışma, raporla.

Mevcut programdan çıkarılan gün/saat, **Mod B** doğrulamasında ve **Mod C** warm-start'ında kullanılır. **Mod A**'da bu alanı yok say.

---

## Veri Kalitesi ve Temizleme (model öncesi zorunlu adım)

Çıktının ilk bölümü bir **veri kalitesi raporu** olmalı:

1. **CSV parse:** Tırnaklı/virgüllü alanları doğru oku (~11 satırda kolon kayması var).
2. **Boş ROOM:** Plan'da **251/1062 satırda `ROOM` boş** → bunlar Mod A'da serbestçe atanır; Mod B'de "oda atanmamış" olarak raporla.
3. **Boş/kirli SCHEDULE:** 8 boş + ~11 kirli satır.
4. **Lecturer normalizasyonu:** `(S)` eki, fazla boşluk, büyük/küçük harf.
5. **Oda outlier:** `Online,9999` placeholder'ı fiziksel oda havuzundan ayır.
6. **Join kapsama:** 225 Plan section'ının Grades/enrollment karşılığı yok → eksik saat/cohort olarak işaretle ve fallback uygula.
7. **Sağlama:** `enrollment_summary` ile bölüm×sınıf düzeyi toplamlarını çapraz doğrula.

---

## Resmi Çizelgeleme Kuralları (`data/rules.pdf`) — Yetkili Kaynak

`data/rules.pdf` ("Çizelgelemede Uyulacak Kurallar", 14 madde) çizelgelemenin **yetkili kural kaynağıdır** ve aşağıdaki hard/soft constraint listelerine bağlanır. **Önemli:** Mevcut programın (`SCHEDULE`) büyük kısmı bu kurallara uymaz (ör. **403/840 lisans section'ı tek günde 3+ saat blok** içeriyor → Madde 1 ihlali). Bu nedenle **Mod A bu kuralları zorlar**; **Mod B** mevcut programın kural ihlallerini de raporlar.

| # | Kural | Tür | Modelde karşılığı |
|---|---|---|---|
| 1 | ~~Bir öğretim elemanına üst üste en fazla 3 saat ders; aynı ders tek günde en fazla 2 saat → 2+1; saat ücretli + Dekan onayı istisnası.~~ | **IGNORE (kapsam dışı)** | **Bu madde modelde uygulanmaz** (kullanıcı kararı). Ders blokları T+L'ye göre serbest ayrıştırılır; 3+ saat tek blok ve >3 saat ardışık hoca yükü kısıtı **yok**. Mod B'de de Madde 1 ihlali **raporlanmaz**. |
| 2 | Bir lisans dersi mümkünse **ardışık günlere** çizelgelenmez. | **Soft** | Aynı section'ın oturumları arası gün mesafesini ödüllendir. |
| 3 | Lisans dersleri hafta içi **09:00–18:00**. Zorunlu hallerde Dekan onayı ile **Cumartesi**. | **Hard** (+ Cmt opsiyonel) | Lisans için izinli pencere; Cumartesi varsayılan kapalı, toggle ile açılır. |
| 4 | Yüksek lisans dersleri hafta içi **18:00–21:00**. Zorunlu hallerde Dekan/Enstitü onayı ile gündüz/hafta sonu. | **Soft** (grad dahilse) | Grad akşam tercihi; gündüz izinli (onay/istisna). |
| 5 | **ENG 101 ve ENG 102** (ELS) = fakülte dersleri kategorisinde → **09:00–18:00** (lisans gibi). Zorunlu hallerde ELS Müdürü onayı ile Cumartesi. | **Hard** | Bu kodları açıkça lisans zaman penceresine bağla. |
| 6 | **Tam zamanlı** personel (`Is_Staff=True`) **Öğretme-Öğrenme Merkezi seminer saatlerinde** ders veremez (2019 Bahar ref: **Perşembe 14:00–16:00**). | **Hard** | Full-time hocalar için blackout slot. Seminer saati **parametre** (dönem bazında güncellenebilir; 2025 değeri teyit edilmeli). |
| 7 | Tam zamanlı hocalar için olanaklar dahilinde **en fazla 2 boş gün**; daha fazlası talep edilemez. | **Soft** | Full-time hoca başına ≤2 ders günü-boş; daha fazlasını ödüllendirme. |
| 8 | EBYS girişi sonrası ders açma/kapama ve gün/saat değişikliği Dekan onayıyla. | Kapsam dışı | Yönetişim/süreç — modelde değil. |
| 9 | **Yüksek lisans dersleri 3 saat** verilmelidir. | **Hard** (grad dahilse) | Grad section toplam blok = 3 (ve 18–21 tek blok, Madde 1'in grad istisnası). |
| 10 | Derslikler kapasiteyle orantılı planlanır; kişisel talepler (ofise uzaklık, gereksiz büyük sınıf) dikkate alınmaz. | Kısmen (kapasite) | Oda kapasitesi ≥ section (zaten Hard #5); kişisel tercih yok. |
| 11 | Dersliklerin fiziksel sorunları Genel Sekreterliğe; komisyon kapasiteye uygun odaları kullanır. | Kapsam dışı | Süreç — modelde değil. |
| 12 | Kayıt haftasından sonra zorunlu haller dışında değişiklik yok. | Kapsam dışı | Yönetişim — modelde değil. |
| 13 | Saat ücretli ve tam zamanlı hocalar ara/final sınavlarında sınıfta olmalı. | Kapsam dışı | Sınav dönemi — haftalık timetable dışı. |
| 14 | Eğitim Fakültesi'nde Öğretmenlik Uygulaması / Okul Deneyimi / Okullarda Gözlem derslerinden sonra **öğrenci geri dönüş süresi** dikkate alınır. | **Soft** | Bu derslerden sonra aynı cohort'a tampon (boşluk) bırak. |

## Veriden Türetilen Ampirik Kalibrasyon (`data/`)

> **Yetki notu:** `data/rules.pdf` **yetkili kural kaynağıdır**. Bu bölüm kural koymaz; mevcut programın (`SCHEDULE`) istatistiksel analizinden çıkan **kalibrasyon parametreleri** ve **ihlal teşhisi**dir. (001 dönemi referans; 002 ile tutarlı.)

### A. Veriyle doğrulanan kurallar (modeli kalibre etmek için güvenli)

- **Zaman ufku:** Tüm dersler **09:00** başlangıçlı, **Pzt–Cuma** (Cmt/Pazar gözlenmedi). Lisans bloklarının ~%93'ü 18:00'den önce bitiyor; **akşam (≥18:00) blokları yalnızca ~%7** → Madde 3 ile uyumlu.
- **Seminer blackout (Madde 6):** **Perşembe 14:00–16:00'da hiçbir tam zamanlı hoca ders vermiyor (0 ihlal)** → bu blackout veride fiilen aktif; parametre gerçek. (2025 dönemi için saat teyit edilmeli ama desen mevcut.)
- **Hoca kompaktlığı (Madde 7):** Hoca başına **medyan 2 öğretim günü** → mevcut program zaten çok kompakt; soft "az güne kümele" hedefi veriyle destekleniyor.
- **Blok birimi:** Hâkim blok **2 saat** (en sık), sonra 1 ve 3 saat. *(Not: Madde 1 ignore edildiğinden 3+ saat tek blok serbesttir; blok ayrıştırma yalnızca T+L'ye göre yapılır.)*
- **Gün dengesi:** 5 güne dengeli yayılım (Salı hafif yoğun).

### B. Kalibrasyon parametreleri (objective ağırlıkları / başlangıç için)

- **Oda doluluğu hedefi:** Mevcut medyan **~0.53** (öğrenci/kapasite) → odalar tipik yarı dolu. Soft #7 (kompakt oda) için iyileştirme payı var; benchmark = 0.53.
- **Lab havuzu:** `L>0` olan **~83 section**; ~25'i lab-görünmeyen odada → lab-oda eşleme tablosu temizlenmeli (Türetilmiş Kavramlar #3).
- **Akşam oranı benchmark:** ~%7 → Mod A bunu aşmamalı (soft #6).

### C. Mevcut programdaki kural İHLALLERİ (kural DEĞİL — Mod A düzeltmeli, Mod B raporlamalı)

- **Madde 3 (lisans <18:00):** Az sayıda lisans bloğu (özellikle 4XX) 18:00 sonrasına, uçta 22–23'e taşıyor → aykırı kayıt olarak işaretle.

> **Madde 1 ignore edildi (kullanıcı kararı):** "tek günde maks 2 saat" ve "ardışık ≤3 saat" kısıtları uygulanmadığından, veride gözlenen 3+ saat tek bloklar (~404/840) ve >3 saat ardışık hoca yükleri (~90/303) **ihlal sayılmaz**, raporlanmaz.

> **Kritik:** B/C ayrımını koru. (A) ve (B) modeli besler; (C) **benimsenmez** — bunlar mevcut programın hatalarıdır, ampirik "kural" gibi öğrenilirse model kuralları sistematik biçimde ihlal eder.

## Hard Constraints

1. Her section gerekli blok sayısı kadar (T+L, gerekirse P) atanmalı.
2. Aynı hoca aynı anda iki section veremez.
3. Aynı cohort `(Dept_Code, Year_Level)` aynı anda iki derste olamaz.
4. Aynı oda aynı anda iki section'a atanamaz.
5. Oda kapasitesi ≥ section büyüklüğü (`Students`).
6. `L > 0` olan section yalnızca lab odasına (isim eki `-L`/`PC`).
7. Toplam atanan slot = `T + L` (+ uygunsa `P`) ile tutarlı.
8. Bir section'ın teorik ve lab bileşenleri kendi içinde çakışmamalı.
9. Çok-oturumlu (`X/Y` veya zincir) section'ların tüm oturumları yerleşmeli ve birbiriyle çakışmamalı.
10. (Mod C) Açık zaman kısıtı verilmiş / sabitlenmiş section'lar yalnızca izinli slotlarda.
11. **Lisans dersleri (1XX–4XX) 18:00'den önce bitmeli** → tüm bloklar 09:00–18:00 aralığında (izinli başlangıç blokları 09–17). Roster yalnızca lisans içerdiğinden bu, fiili zaman penceresi kısıtıdır.
12. **Cuma namazı bloğu:** **Cuma günü namaz saatine ders konulamaz** — varsayılan blackout **Cuma 13:00–14:00** (tüm bölüm/cohort/oda/hoca için). Bu slot tüm section'lara kapalıdır. Namaz saati **parametredir** (dönem/mevsime göre kaydırılabilir; 002 verisi bu saati doğrular: doluluk komşu saatlerin ~%15'ine düşüyor).

## Soft Constraints / Objective

1. Hocaların derslerinin gün içinde dağınık (boşluklu) olmaması.
2. Cohort'ların gün içinde aşırı boşluk yaşamaması.
3. Derslerin makul saatlere (sabah/öğleden sonra) yerleşmesi.
4. Aynı bölüm derslerinin günlere dengeli yayılması.
5. Cohort başına günlük ders yükünün aşırı yoğun olmaması.
6. **Akşam slotlarının (18:00–20:00) sadece gerektiğinde kullanılması.**
7. **Oda kullanımının kompakt olması** (az sayıda odayı verimli doldurmak; benchmark: mevcut programın oda sayısı).
8. **Yarı zamanlı hoca müsaitliği** (`Is_Staff = False`): bu hocaların derslerini az sayıda güne kümele / dağıtma — tam zamanlı kadro (`True`) daha esnek varsayılabilir.
9. Mevcut programa yakınlık (Mod C): gereksiz yere mevcut atamayı bozmamak.
10. **Lisansüstü dersleri (5XX+6XX) akşam penceresine (18:00–21:00) yerleştirme tercihi** — opsiyonel olarak grad section'lar dahil edilirse: mümkünse akşam, ama gündüz de yapılabilir (gözlenen gündüz grad istisnaları korunur).

---

## Beklenen Çıktı

1. **Veri kalitesi raporu** (yukarıdaki maddeler) + normalize edilmiş tablo şeması:
   `Sections`, `Instructors`, `Rooms` (lab flag dahil), `TimeSlots`, `Cohorts`, `Constraints`, `Assignments`.
2. Hangi kolonların **karar değişkeni / kısıt / parametre** olduğunu açıkla.
3. **Matematiksel formülasyon:** kümeler, parametreler, karar değişkenleri, hard/soft constraints, amaç fonksiyonu.
4. Bunu **CP-SAT / MILP** olarak nasıl kuracağını öner (değişken tanımı `x[section, room, day, start_slot]` veya pattern-based).
5. **Ölçek stratejisi** (~1060 section, ~100 oda, 60 slot): ön işleme, conflict graph, büyük/kısıtlı section'ları önce yerleştirme, dönem-bazlı/bölüm-bazlı decomposition, feasibility repair.
6. **Çözücü tartışması:** Google OR-Tools **CP-SAT** (önerilen), Gurobi MILP, hybrid heuristic + exact repair.
7. **Çıktı formatları:**
   - Section / hoca / oda / cohort bazlı haftalık program (tablo).
   - **Çakışma raporu** (tür bazında — aşağıya bak).
   - Sağlanamayan soft constraint raporu.
   - **Mod B karşılaştırması:** üretilen program vs. mevcut program (çakışma sayısı, oda kullanımı, akşam oranı).
   - **JSON export** (gün/saat/oda/section şeması) — *sonraki adımda shadcn arayüzü bunu tüketecek.*
8. **Python çözüm mimarisi:** CSV okuma (quote-aware) → temizleme → join → SCHEDULE parse → cohort/lab türetme → model kurma (OR-Tools) → çözme → doğrulama (validation checks) → Excel/CSV/JSON yazma.

---

## Arayüz (Sonuç Görselleştirme)

Modelin ürettiği timetable, ayrı ve basit bir **web arayüzünde** sunulacak (React + shadcn/ui). Arayüz çözücüyü çalıştırmaz; yalnızca modelin **JSON çıktısını** okuyup gösterir. (Detaylı tasarım sonraki adımda; burada amaç ve kapsam.)

- **Girdi:** `schedule.json` — her section için dönem, gün, saat, oda, hoca, cohort.
- **Ana görünüm:** Haftalık ızgara (Pzt–Cuma × 09:00–21:00).
- **Filtreler / görünümler:** Oda, hoca, cohort (Dept+Year), bölüm bazında.
- **Vurgular:** Çakışmalar ve sağlanamayan soft-constraint'ler renkli işaretlenir.
- **Karşılaştırma (Mod B):** Üretilen program ↔ mevcut program (özet metrikler: çakışma sayısı, oda kullanımı, akşam oranı).
- İlk sürüm **salt-okunur**; ileride manuel atama/düzenleme eklenebilir.

---

## Çakışma Türleri (ayrı ayrı raporla)

- Instructor conflict
- Student-group/cohort conflict `(Dept_Code, Year_Level)`
- Room conflict
- Capacity conflict
- Lab-room mismatch
- Multi-session internal conflict (aynı section'ın oturumları)
- Missing/dirty data (boş oda, parse edilemeyen schedule, eksik join)

---

## Önemli Notlar

- **Öncelik 1: feasible** (çakışmasız) program. **Öncelik 2:** kalite (soft constraints).
- Cohort yaklaşımı `(Dept_Code, Year_Level)` bir **proxy'dir** — gerçek öğrenci kayıt çakışmasını tam yansıtmaz; bu varsayımın etkisini tartış.
- Mevcut program (`SCHEDULE`) hem **benchmark** hem **warm-start** olarak değerlidir; sıfırdan modeli (Mod A) bununla kıyasla.
- Sonuçta hem **kavramsal model** hem **uygulanabilir teknik yol haritası** (çalışan Python iskeleti) ver.
