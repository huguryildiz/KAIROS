# TODO — İleri Fazlar

Faz 1 (uçtan uca pipeline + dilim bazlı feasibility kanıtı) tamamlandı.
Bkz. [README.md](README.md). Aşağıdakiler sonraki fazların iş listesidir.

---

## Faz 2 — Model doğruluğu ve tam-ölçek çözüm

### 2.1 Cohort kısıtı düzeltmesi (yüksek öncelik, spec'e sadık)
- **Sorun:** Şu an aynı cohort'un *herhangi* iki section'ı aynı anda olamıyor. Ama
  spec hard-kısıt #3 "aynı anda iki **derste**" diyor → aynı **dersin** farklı
  section'ları (farklı öğrenci grupları için paralel açılan) çakışmamalı sayılıyor.
- **Yapılacak:** Cohort çakışmazlığını **ders kodu düzeyinde** kur: bir (cohort, slot)
  içinde en fazla bir *distinct ders kodu* aktif olsun; aynı dersin section'ları paralel
  olabilsin. CP kodlaması: `course_busy[cohort, course, day, hour]` gösterge değişkeni +
  `(cohort, slot)` başına `sum(course_busy) <= 1`.
- **Beklenen etki:** CMPE 113 _01–_04 gibi durumlar ve servis dersleri feasible olur.
- **Test:** aynı dersin iki section'ı paralel olabilmeli; iki *farklı* dersin section'ı
  olamamalı.

### 2.2 Uzun blokları çok-güne bölme
- **Sorun:** T+P ≥ ~10 saat tek blok 09–18 penceresine sığmaz (studio dersleri).
- **Yapılacak:** `blocks_from_tpl`'i, uzun teorik yükü birden çok güne yayılan daha küçük
  bloklara bölecek şekilde genişlet (Madde 1 zaten IGNORE; serbest bölme). Aynı section'ın
  blokları cohort/hoca üzerinden zaten çakışmaz; ek olarak "ardışık günlere yayma" (soft #2)
  ödüllendirilebilir. Bölme stratejisi parametrik olsun (ör. maks blok uzunluğu).
- **Test:** 10 saatlik bir section ≥2 bloğa bölünüp yerleşmeli.

### 2.3 Çok-hocalı (team-taught) section'lar
- **Sorun:** Grades `Staff ID` bazı section'larda virgülle iki kimlik içeriyor
  (`"00003893,00002022"`) → tek sentetik hoca gibi ele alınıyor, isim boş kalıyor.
- **Yapılacak:** Kimlikleri ayır; section'ı *tüm* listelenen hocalara ait say
  (her biri için hoca-çakışmazlığına dahil et); arayüz için isimleri birleşik göster.

### 2.4 Oversize section'lar
- **Sorun:** 16 section (en büyük TEDU 101 = 497 öğr.) en büyük odayı (100) aşıyor.
- **Seçenekler:** (a) büyük amfileri oda master'ına ekle; (b) section'ı paralel
  alt-gruplara böl; (c) kapasite kısıtını "taşma cezası" olan soft'a çevir (opsiyonel).
  Şu an: hariç tutulup raporlanıyor — karar verilince uygula.

### 2.5 Tam dönem çözümü ve decomposition
- 2.1–2.2 sonrası `--scope all` ile **tüm 001 (~793 section)** çözümünü dene; süre/kalite
  ölç. Gerekirse:
  - Oda havuzunu paylaşan **fakülte-bazlı decomposition** + ortak oda rezervasyon şeması.
  - Sıcak başlatma (mevcut programdan hint) — Mode C.
- **002 (Bahar) dönemini** de çalıştır ve raporla (pipeline period-parametrik).

### 2.6 Soft objective kalibrasyonu
- Ağırlıkları benchmark'lara göre ayarla: oda doluluğu ~0.53, akşam oranı ~%7.
- Soft #2/#4/#5/#7/#8/#14'ü (ardışık gün, gün dengesi, günlük yük, hoca boş günü,
  yarı-zamanlı kümeleme, uygulama dersi tamponu) kademeli ekle ve etkisini ölç.

---

## Faz 3 — Web arayüzü (salt-okunur)

- React + shadcn/ui; çözücüyü çalıştırmaz, yalnızca `schedule_<period>.json` okur.
- Haftalık ızgara (Pzt–Cuma × 09:00–21:00); oda / hoca / cohort / bölüm filtreleri.
- Çakışma ve sağlanamayan soft-constraint vurgusu; Mode-B karşılaştırma özeti.
- JSON sözleşmesi `export.py`'de sabit — arayüz ona göre tüketir.

---

## Opsiyonel / kapsam dışı (talep gelirse)

- **Lisansüstü (5XX/6XX)** dahil etme toggle'ı (`include_grad`) + akşam 18–21 tercihi.
- **Cumartesi** toggle'ı (`saturday_enabled`) — Dekan onaylı istisnalar.
- **Plan-only ~225 section** dahil etme (`include_plan_only`) ve saat tahmini.
- Sınav dönemi çizelgeleme (haftalık timetable dışı — Madde 13).

## Veri kalitesi takibi

- Lab-oda eşlemesini gözden geçir (13 oda bulundu; spec ~14 diyordu).
- Grades `Schedule` kolonundaki kirli satırları da raporla (şu an Plan üzerinden bakılıyor;
  Plan 001'de 0 kirli bulundu).
- `enrollment_summary` ile bölüm×sınıf toplamlarının çapraz doğrulamasını rapora ekle.
