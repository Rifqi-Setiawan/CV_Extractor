# 📄 CV Section Extractor

Mengekstrak **nama, kontak, dan section** (ringkasan, pengalaman, pendidikan, keahlian, dst.) dari CV PDF berbahasa **Indonesia maupun Inggris**, dengan berbagai template (1 kolom, 2 kolom, Canva, ATS, hasil scan).

- **Gratis & lokal**: berjalan di CPU, tanpa API berbayar. Data CV tidak pernah keluar dari mesin.
- **Tanpa LLM secara default**: semua aturan ditulis dengan Python. LLM lokal (Ollama) hanya **fallback opsional**.
- **Teks disalin apa adanya**: isi section selalu disalin langsung dari dokumen, jadi tidak ada isi yang dikarang.
- **Web UI (Streamlit)**: unggah CV, lihat hasil per section, preview halaman dengan highlight warna, unduh JSON.

---

## Daftar isi
1. [Cara kerja](#cara-kerja)
2. [Struktur project (clean architecture)](#struktur-project-clean-architecture)
3. [Instalasi](#instalasi)
4. [Menjalankan](#menjalankan)
5. [Format output](#format-output)
6. [LLM lokal (opsional)](#llm-lokal-opsional)
7. [Hasil uji pada CV contoh](#hasil-uji-pada-cv-contoh)
8. [Keterbatasan](#keterbatasan)
9. [Mengembangkan lebih lanjut](#mengembangkan-lebih-lanjut)

---

## Cara kerja

```
PDF
 │
 ├─ 1. Baca per halaman ── ada lapisan teks? ──ya──► PyMuPDF (teks + ukuran font + bold)
 │                                         └─tidak─► render 300 DPI → Tesseract OCR (eng+ind)
 │                                                    + estimasi bold dari ketebalan goresan
 │
 ├─ 2. Layout  : hapus nomor halaman/header berulang → deteksi 1/2 kolom
 │               → gabungkan potongan di baris yang sama → urutan baca
 │
 ├─ 3. Heading : kandidat (baris pendek) → anchor (cocok kamus EN/ID)
 │               → pelajari "gaya heading" CV ini → semua baris dengan gaya sama = heading
 │
 ├─ 4. Label   : kamus + fuzzy match → (opsional) LLM lokal → kalau gagal: "other"
 │
 ├─ 5. Section : teks di antara dua heading = isi section (disalin apa adanya)
 │               header (sebelum heading pertama) → nama, headline, kontak, ringkasan
 │
 └─ 6. Skor kepercayaan + peringatan → (opsional) fallback LLM bila skor rendah
```

### Inti fleksibilitasnya: heading dipelajari dari gaya, bukan hanya dari kamus

Template CV berbeda-beda, dan nama heading-nya tidak terbatas ("ACTIVITIES", "DESKRIPSI", "INFORMASI TAMBAHAN", ...). Kamus heading tidak akan pernah lengkap. Tapi **di dalam satu CV, semua heading section ditulis dengan gaya yang sama**:

| CV | Gaya heading |
|---|---|
| Tiara | ukuran 14, bold, kapital semua |
| Elsa | ukuran 13, bold, kapital semua |

Cara kerjanya:
1. Beberapa heading yang dikenali kamus menjadi **anchor**.
2. Dari anchor itu, sistem mempelajari **gaya heading** CV tersebut.
3. Semua baris dengan gaya yang sama ikut diangkat jadi heading, walaupun tidak ada di kamus.

Ada beberapa aturan pengaman:
- Baris di atas heading pertama di halaman 1 tidak pernah diangkat. Contohnya "SAP PP-QM CONSULTANT" di bawah nama dianggap headline, bukan section.
- Heading berlabel sama yang muncul berurutan dianggap sub-heading. Contohnya "KEMAMPUAN" → "TEKNIK SKILL" → "SOFT SKILL" tetap jadi satu section skills.
- Kandidat heading harus punya jarak kosong di atasnya yang cukup.

Pada PDF hasil OCR, info bold tidak tersedia, jadi bold **diperkirakan dari ketebalan goresan huruf** di gambar.

---

## Struktur project (clean architecture)

```
cv-section-extractor/
├── app.py                         # entry point Streamlit
├── src/cv_extractor/
│   ├── domain/                    # ENTITAS — tanpa I/O, tanpa library pihak ketiga
│   │   ├── models.py              #   TextLine, Section, ParsedCV, ContactInfo, ...
│   │   └── section_labels.py      #   label kanonik + alias heading EN/ID
│   ├── services/                  # LOGIKA INTI — fungsi murni, mudah di-unit-test
│   │   ├── layout.py              #   kolom, urutan baca, merge baris, buang noise
│   │   ├── heading_detector.py    #   deteksi heading berbasis gaya (style signature)
│   │   ├── sectioner.py           #   potong section + parsing header (nama, ringkasan)
│   │   ├── contact_extractor.py   #   regex email, HP, LinkedIn, URL, lokasi
│   │   ├── confidence.py          #   skor kepercayaan + peringatan
│   │   └── text_cleaning.py       #   bersihkan bullet, normalisasi heading
│   ├── application/               # USE CASE + PORT (interface)
│   │   ├── ports.py               #   DocumentReader, OcrEngine, HeadingLabeler, HeadingAdvisor
│   │   ├── pipeline.py            #   CVExtractionService.extract()
│   │   └── config.py              #   PipelineConfig, OcrConfig, LlmConfig
│   ├── infrastructure/            # ADAPTER ke library/layanan luar
│   │   ├── pdf_reader.py          #   PyMuPDF (lapisan teks / render untuk OCR)
│   │   ├── ocr/tesseract_engine.py#   Tesseract
│   │   ├── ocr/stroke.py          #   estimasi bold dari gambar
│   │   └── labelers/              #   DictionaryLabeler (rapidfuzz), Ollama (LLM lokal)
│   ├── presentation/              # UI
│   │   ├── streamlit_app.py
│   │   └── preview.py             #   highlight section di gambar halaman
│   ├── bootstrap.py               # composition root: merangkai adapter konkret
│   └── cli.py                     # mode command-line (batch / evaluasi)
└── tests/                         # 31 unit test (data sintetis, tanpa PDF)
```

**Aturan dependensi**: `presentation → application → services → domain`. Library pihak ketiga hanya disentuh di `infrastructure/`. Pipeline cuma mengenal *port* (interface), sehingga OCR engine, labeler, atau LLM bisa diganti tanpa mengubah logika inti. Di unit test, semuanya diganti dengan fake/mock.

---

## Instalasi

### 1. Prasyarat
- **Python 3.10+**
- **Tesseract OCR** beserta data bahasa **Indonesia** (`ind`). Hanya dibutuhkan untuk PDF tanpa lapisan teks (hasil scan, Canva yang diekspor sebagai gambar, "Microsoft Print to PDF" yang mengubah huruf jadi vektor). PDF yang punya teks tetap bisa diproses tanpa Tesseract.

| OS | Perintah |
|---|---|
| Ubuntu/Debian | `sudo apt install tesseract-ocr tesseract-ocr-ind` |
| macOS | `brew install tesseract tesseract-lang` |
| Windows | Unduh installer dari [UB Mannheim](https://github.com/UB-Mannheim/tesseract/wiki). Saat instalasi, centang **Indonesian** di *Additional language data*. |

Cek instalasi:
```bash
tesseract --list-langs     # harus muncul: eng, ind
```

> **Windows**: kalau `tesseract` tidak dikenali, set lokasi exe-nya:
> `set TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe` (CMD) atau
> `$env:TESSERACT_CMD="C:\Program Files\Tesseract-OCR\tesseract.exe"` (PowerShell)

### 2. Install dependensi Python
```bash
cd cv-section-extractor
python -m venv .venv
# Linux/macOS:
source .venv/bin/activate
# Windows:
.venv\Scripts\activate

pip install -r requirements.txt
```

---

## Menjalankan

### Web UI (Streamlit)
```bash
streamlit run app.py
```
Buka `http://localhost:8501`, lalu unggah satu atau beberapa CV PDF.

| Bagian | Isi |
|---|---|
| **Ringkasan** (jika > 1 file) | tabel nama, email, jumlah section, confidence, tanda "perlu dicek", unduh semua JSON |
| **Identitas** | headline, email, telepon, LinkedIn, lokasi, URL lain, peringatan |
| **📑 Section** | setiap section dengan label, heading asli, dan isinya |
| **🖼️ Preview** | halaman CV dengan heading diberi kotak dan isi section diarsir per warna. Berguna untuk debugging. |
| **🧾 JSON** | output lengkap + tombol unduh |

Sidebar berisi pengaturan: bahasa OCR, DPI, dan toggle LLM lokal.

### Command line (batch)
```bash
PYTHONPATH=src python -m cv_extractor.cli cv1.pdf cv2.pdf -o hasil.json
# dengan fallback LLM lokal:
PYTHONPATH=src python -m cv_extractor.cli cv1.pdf --llm --llm-model qwen2.5:3b
```
Di Windows PowerShell: `$env:PYTHONPATH="src"; python -m cv_extractor.cli cv1.pdf -o hasil.json`

### Unit test
```bash
pip install -r requirements-dev.txt
pytest
```

---

## Format output

```json
{
  "name": "Tiara Rahmania Hadiningrum",
  "headline": null,
  "contact": {
    "emails": ["tiararahmania05@gmail.com"],
    "phones": ["081332496225"],
    "linkedin": "https://www.linkedin.com/in/tiararh",
    "urls": ["https://bit.ly/PortofolioTiaraRahmaniaH"],
    "location": "Sidoarjo, Jawa Timur"
  },
  "sections": [
    {"label": "summary", "raw_heading": null, "inferred": true,
     "label_source": "inferred", "pages": [1], "text": "I am a freelance web developer ..."},
    {"label": "training", "raw_heading": "ACTIVITIES", "inferred": false,
     "label_source": "dictionary", "pages": [2], "text": "FEBRUARI 2024 – MARET 2024\n..."}
  ],
  "meta": {
    "file_name": "tiara.pdf", "seconds": 0.05, "confidence": 1.0, "needs_review": false,
    "heading_strategy": "style_signature", "llm_used": false, "warnings": [],
    "pages": [{"page": 1, "source": "text_layer", "columns": 1, "lines": 46}]
  }
}
```

| Field | Arti |
|---|---|
| `label` | label kanonik: `summary`, `experience`, `education`, `skills`, `projects`, `training`, `certifications`, `organizations`, `awards`, `languages`, `contact`, `personal_info`, `publications`, `interests`, `references`, `additional_info`, `header`, `other` |
| `raw_heading` | teks heading persis seperti di CV. Tetap disimpan walaupun labelnya `other`, jadi tidak ada informasi yang hilang. |
| `inferred` | `true` jika section tidak punya heading. Contohnya paragraf ringkasan di bawah nama, atau `header` (sisa baris di bagian atas CV). |
| `label_source` | `dictionary` / `llm` / `inferred` / `unknown` |
| `confidence` | skor 0–1. Di bawah 0,6 → `needs_review: true` |
| `heading_strategy` | `style_signature` (gaya heading berhasil dipelajari), `dictionary_only`, `llm`, atau `none` |

---

## LLM lokal (opsional)

Secara default **tidak ada LLM yang dipakai**. Kalau diaktifkan, LLM hanya dipanggil untuk:
1. **Memberi nama heading yang tidak dikenali kamus**. Inputnya cuma teks heading-nya, beberapa token saja.
2. **CV dengan confidence rendah**. Yang dikirim hanya *kandidat heading* (baris pendek + info gaya), bukan seluruh CV, karena di CPU proses membaca prompt panjang juga lambat. Output dipaksa berupa JSON lewat JSON schema (parameter `format` di Ollama).

Setup:
```bash
# 1. install Ollama: https://ollama.com/download
# 2. unduh model (pilih salah satu; cek versi terbaru di library Ollama)
ollama pull qwen2.5:3b      # ringan, cukup untuk melabeli heading
ollama pull qwen2.5:7b      # lebih akurat, lebih lambat di CPU
# 3. Ollama berjalan di http://localhost:11434 (otomatis setelah instalasi)
```
Lalu di UI aktifkan **"Aktifkan fallback Ollama"** di sidebar, atau pakai `--llm` di CLI. Kalau Ollama tidak bisa dihubungi, sistem tetap jalan dengan aturan Python.

Kebutuhan RAM (model terkuantisasi 4-bit): model 3–4B butuh ~3–4 GB, model 7–8B ~5–6 GB.

---

## Hasil uji pada CV contoh

Diuji pada 6 CV dengan template berbeda:

| CV | Jenis PDF | Layout | Hasil | Waktu* |
|---|---|---|---|---|
| Tran Dai Duong | teks (Canva) | 2 kolom | 5 section ✅, nama + headline ✅ | 0,04 s |
| Huynh Trung Khai | gambar → OCR | 2 kolom | 5 section ✅, nama + headline ✅ | ~24 s |
| M. Rifqi Setiawan | vektor (Print to PDF) → OCR | 1 kolom | 6 section + ringkasan tanpa heading ✅ | ~34 s |
| Tiara R. H. | teks (Print to PDF) | 1 kolom | 6 section + ringkasan ✅, termasuk "ACTIVITIES" | 0,05 s |
| Elsa N. P. | teks (Canva), bahasa Indonesia | 1 kolom, tanggal rata kanan | 4 section ✅, termasuk "DESKRIPSI" dan "INFORMASI TAMBAHAN" | 0,03 s |
| ATS Indonesia | vektor → OCR | 1 kolom, heading di kiri | 7 section ✅, sub-heading tetap di dalam "KEMAMPUAN" | ~61 s |

\*Diukur di mesin dengan 2 core CPU. Waktu OCR akan lebih cepat di mesin dengan core lebih banyak.

**Uji ketahanan**: beberapa alias sengaja dihapus dari kamus (ACTIVITIES, PROJECTS, ORGANIZATION, PENDIDIKAN, ...). Batas section tetap terdeteksi dengan benar lewat gaya heading. Labelnya jadi `other`, tapi teks heading aslinya tetap tersimpan.

---

## Keterbatasan

- **Salah baca OCR satu karakter**. Contohnya `rifqis232@gmail.com` terbaca `rifgis232@gmail.com`. Untuk CV hasil OCR, email, HP, dan nama perlu dicek ulang (UI menampilkan peringatan). Sistem **sengaja tidak mengoreksi otomatis**, karena bisa saja CV aslinya memang salah ketik.
- **OCR kadang melewatkan potongan teks kecil**, misalnya label "GPA:" atau sebagian baris di template yang padat.
- **OCR lambat di CPU** (±20–60 detik per CV). PDF yang punya lapisan teks selesai dalam < 0,1 detik.
- **RapidOCR sudah diuji sebagai alternatif**. Kecepatannya ~3× Tesseract, tapi model bawaannya menghapus spasi ("BachelorDegreeofMathematics"), jadi tidak dipakai sebagai default.
- **CV yang heading-nya tidak berbeda gaya dari isinya dan tidak ada di kamus** tidak bisa dipotong dengan aturan. Kasus ini ditandai `needs_review`, dan bisa ditangani dengan fallback LLM.
- **Output hanya sampai level section**. Isi section belum dipecah jadi jabatan, perusahaan, atau tanggal per pengalaman.
- **Input saat ini hanya PDF**.

---

## Mengembangkan lebih lanjut

| Ingin... | Caranya |
|---|---|
| Menambah sinonim heading | tambahkan alias di `domain/section_labels.py` |
| Mengganti mesin OCR | buat class baru yang mengikuti `OcrEngine` di `application/ports.py`, lalu pasang di `bootstrap.py` |
| Menambah cara memberi label (mis. embedding multibahasa) | buat class yang mengikuti `HeadingLabeler`, lalu pasang sebagai `fallback_labeler` di `bootstrap.py` |
| Mendukung DOCX/gambar | buat `DocumentReader` baru yang menghasilkan `TextLine` |
| Ekstraksi level field (jabatan/perusahaan/tanggal) | tambahkan use case baru yang memproses `Section.text` milik section `experience`/`education` (cocok untuk LLM 7–8B, karena input hanya satu section) |
| Mengukur akurasi | buat *gold set* CV berlabel manual, jalankan CLI, bandingkan per section (akurasi baris, F1 heading) |

> ⚠️ **Privasi**: CV berisi data pribadi. Jangan commit file PDF atau hasil JSON ke repository (`.gitignore` sudah mengecualikannya).
