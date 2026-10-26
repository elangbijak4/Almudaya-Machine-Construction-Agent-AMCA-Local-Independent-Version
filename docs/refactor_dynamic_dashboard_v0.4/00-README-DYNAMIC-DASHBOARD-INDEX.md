# Rencana Teknis & Handover Master: Refaktor Dashboard Dinamis & Antarmuka Berbasis Provider (`v0.4`)

## 1. Latar Belakang & Filosofi Desain bagi Periset (*Researcher-Centric UX*)

AMCA (*Almudaya Machine Construction Agent*) dirancang sebagai platform rekayasa mesin formal untuk **para periset dan perekayasa perangkat lunak**. Periset membutuhkan lingkungan kerja yang:
1. **Bebas Distraksi & Kebingungan (*Zero-Cognitive Friction*)**: Setiap kolom masukan harus memiliki alasan keberadaan yang jelas. Jika suatu provider tidak memerlukan API key (misalnya 9Router yang membaca kredensial internal atau runtime lokal Ollama/LM Studio), kolom API key tidak boleh membebani perhatian periset atau memicu rasa ragu apakah kolom itu wajib diisi.
2. **Konteks Dinamis yang Mengalir Natural (*Adaptive Dynamic Dashboard*)**: Antarmuka konfigurasi di sidebar dan dashboard utama harus beradaptasi seketika (*reactive & dynamic*) mengikuti pilihan provider model yang menjadi otak agen AMCA.
3. **Umpan Balik Diagnostik Cerdas (*Proactive Live Diagnostics*)**:
   - Jika periset memilih **9Router**, sistem langsung memeriksa ketersediaan port `20128`, mendeteksi kunci lokal otomatis, dan memberi tahu secara ramah apakah sudah ada *provider connection* aktif di dashboard 9Router.
   - Jika periset memilih **Ollama** atau **LM Studio**, sistem langsung mengecek konektivitas port `11434` / `1234` dan menampilkan daftar model lokal yang terpasang tanpa meminta API key.
   - Jika periset memilih **Local Model (GGUF)**, gerbang spesifikasi perangkat keras (`hardware.py`) langsung menampilkan metrik RAM, VRAM, dan CPU terkini laptop periset.
   - Jika periset memilih **Offline Deterministic**, antarmuka langsung menyembunyikan semua parameter jaringan dan menegaskan status *Air-Gapped*.

---

## 2. Taksonomi 4 Kategori Provider AMCA

Untuk menyederhanakan mental model periset di tengah tersedianya 12 jenis provider/runtime, sistem mengelompokkan provider ke dalam **4 Kategori Arsitektural**:

| Kategori | Opsi Provider | Ciri Khas Antarmuka Dinamis | Kebutuhan Kredensial / Jaringan |
| :--- | :--- | :--- | :--- |
| **Kategori A: Cloud API Langsung** | `Google Gemini`, `xAI (Grok)`, `OpenAI`, `Anthropic`, `Custom OpenAI-Compatible` | Dropdown model rekomendasi periset + Kolom API Key berkeamanan tinggi dengan badge: *"Disimpan hanya di memori sesi RAM laptop"*. | Wajib API Key Cloud; URL endpoint otomatis disesuaikan (kecuali kustom). |
| **Kategori B: Local Proxy & Gateway** | `9Router` | Status probe port 20128 aktif + Pilihan model/Combo lokal + Indikator otomatisasi `Default Key` (kolom API key disembunyikan di expander lanjutan). Jika belum ada koneksi di 9Router, muncul kartu edukatif ramah. | 100% lokal ke `127.0.0.1:20128`. Kunci penyedia AI dikelola di 9Router. |
| **Kategori C: Runtime Model Lokal Laptop** | `Ollama`, `LM Studio`, `OpenCode` | Status probe koneksi port aktif + Dropdown model lokal yang terpasang + Tanpa kolom API Key. | 100% lokal di laptop tanpa internet; tanpa API Key. |
| **Kategori D: Mandiri, Combo, & Air-Gapped** | `Local Model (GGUF)`, `AMCA Combo (Native Fallback Chain)`, `Offline Deterministic` | • **Local Model**: Panel inspeksi spek OS laptop (`hardware.py`).<br/>• **AMCA Combo**: Visualisasi interaktif rantai fallback multi-tier.<br/>• **Offline**: Banner mode *Air-Gapped*, zero konfigurasi. | Berjalan lokal di laptop; mandiri dan tahan kendala batas token. |

---

## 3. Struktur Dokumen Refaktor (`docs/refactor_dynamic_dashboard_v0.4/`)

| File | Judul & Fokus Teknis |
| :--- | :--- |
| [`00-README-DYNAMIC-DASHBOARD-INDEX.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_dynamic_dashboard_v0.4/00-README-DYNAMIC-DASHBOARD-INDEX.md) | Indeks utama, filosofi UX periset, dan taksonomi 4 kategori provider. |
| [`01-SPEC-DYNAMIC-PROVIDER-CARDS.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_dynamic_dashboard_v0.4/01-SPEC-DYNAMIC-PROVIDER-CARDS.md) | Spesifikasi teknis perilaku dinamis komponen antarmuka sidebar dan kartu status per provider. |
| [`02-TUTORIAL-PROVIDER-UI-FLOWS.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_dynamic_dashboard_v0.4/02-TUTORIAL-PROVIDER-UI-FLOWS.md) | Tutorial alur operasional per provider dari pemilihan model hingga konstruksi mesin nyata. |
| [`03-IMPLEMENTATION-AND-TESTING-PLAN.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_dynamic_dashboard_v0.4/03-IMPLEMENTATION-AND-TESTING-PLAN.md) | Rencana perubahan kode konkret di `app.py`, pengujian unit/integrasi AppTest tanpa mocking, dan sinkronisasi buku panduan. |
| [`PROGRESS_LOG.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_dynamic_dashboard_v0.4/PROGRESS_LOG.md) | Log penanda checkpoint formal kelanjutan tugas. |

---

## 4. Invarian Sistem yang Tidak Boleh Dilanggar (*Strict Constraints*)

1. **Aturan Push Git**: **DILARANG MELAKUKAN GIT PUSH KE GITHUB** tanpa izin eksplisit pengguna.
2. **Invarian Widget Streamlit AppTest**:
   - Pengujian `tests/integration/test_streamlit_app.py` memeriksa indeks widget tetap di bodi utama:
     - `app.selectbox[0]` adalah pemilih contoh YAML di Bagian 1.
     - `app.button[0]` adalah tombol "Muat contoh ke editor".
     - `app.button[2]` adalah tombol "Validasi YAML saat ini".
     - `app.checkbox[0]` adalah checkbox "Saya menyetujui eksekusi mesin ini".
     - Tombol berlabel "Jalankan mesin".
   - Semua elemen dinamis provider berada di dalam `with st.sidebar:` atau dirender secara kondisional tanpa menggeser urutan elemen bodi utama di Bagian 1, 3, dan 5.
3. **Zero-Mocking Mandate**: Probe port, inspeksi SQLite 9Router, inspeksi spek laptop, dan inferensi model wajib mengeksekusi kode Python nyata.
4. **Non-Regression Suite**: Seluruh 115 test suite dan `validate_workflow.py` wajib tetap berstatus **`OK` / `PASS`**.
