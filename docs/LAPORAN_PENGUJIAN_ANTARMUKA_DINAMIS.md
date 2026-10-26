# Laporan Pengujian Komprehensif Antarmuka Dinamis AMCA (`app.py`)

**Tanggal & Waktu Pengujian:** 26 Oktober 2026, 15:46 WIB  
**Versi Aplikasi:** `v0.5.0` (Mencakup Baseline `v0.1.0`, Versi Lokal Mandiri `v0.2.0`, Pustaka Komponen Kumulatif `v0.3.0`, Dashboard Dinamis Adaptif `v0.4.0`, dan Sistem Penanganan Error Terpadu & Diagnostik `v0.5.0`)  
**Metodologi Pengujian:** Otomasi Pengujian Antarmuka Penuh (*Headless Browser Engine Simulation via Streamlit AppTest*), Evaluasi Ergonomi & Tampilan Natural, Deteksi Redundansi Komponen, dan Audit Konsistensi State Antar-Provider.  
**Prinsip Pengujian:** *Strict Zero-Mocking* (Menjalankan engine pembuktian formal, parser AST, compiler kode, dan runtime AMCA asli).

---

## 1. Ringkasan Eksekutif & Hasil Pengujian Antarmuka

Pengujian penuh antarmuka dinamis AMCA dilakukan untuk memastikan bahwa seluruh fitur antarmuka mengalir secara natural, bebas dari kebingungan bagi periset, tidak memiliki redundansi komponen yang tidak perlu, dan mempertahankan konsistensi data saat beralih antar-provider maupun saat terjadi kesalahan.

### Metrik Hasil Pengujian

| Parameter Pengujian | Target | Hasil Aktual | Status |
| :--- | :--- | :--- | :--- |
| **Skenario Integrasi UI Komprehensif Baru** | 8 skenario | **8 skenario PASS** (11.62s) | ✅ **100% LULUS** |
| **Skenario Integrasi UI Asli Streamlit** | 2 skenario | **2 skenario PASS** (2.03s) | ✅ **100% LULUS** |
| **Total Seluruh Test Suite Repositori** | 136 tests | **136 tests PASS** (20.43s) | ✅ **100% LULUS** |
| **Validasi Scaffold & Workflow AMCA** | PASS | **PASS** (`tools/validate_workflow.py`) | ✅ **100% LULUS** |
| **Pengecekan Integritas Path Panduan Pengguna** | 6 berkas | **6 berkas PASS** (`test_windows_user_commands.py`) | ✅ **100% LULUS** |
| **Duplikasi Widget ID (*DuplicateWidgetID*)** | 0 | **0 (Zero Collision)** | ✅ **SEMPURNA** |
| **Redundansi Komponen Antarmuka** | Teridentifikasi & Teratasi | **1 Inkonsistensi Ditemukan & Diperbaiki** | ✅ **TERSELESAIKAN** |

---

## 2. Pengujian Dashboard Dinamis Berdasarkan Pilihan Provider (12 Opsi)

Sidebar pengaturan Agent Harness diuji secara otomatis pada ke-12 pilihan provider untuk memastikan antarmuka berubah secara adaptif, natural, dan proporsional sesuai kebutuhan teknis masing-masing provider:

```
                            ┌──────────────────────────────────────────────┐
                            │   PILIHAN PROVIDER MODEL (SIDEBAR DINAMIS)   │
                            └──────────────────────┬───────────────────────┘
                                                   │
        ┌───────────────────┬──────────────────────┼──────────────────────┬───────────────────┐
        ▼                   ▼                      ▼                      ▼                   ▼
┌───────────────┐   ┌───────────────┐      ┌───────────────┐      ┌───────────────┐   ┌───────────────┐
│    9Router    │   │  Cloud Direct │      │ Local Runtime │      │  Local Model  │   │  Combo & Off  │
├───────────────┤   ├───────────────┤      ├───────────────┤      ├───────────────┤   ├───────────────┤
│ • Status Port │   │ • Gemini / OAI│      │ • Ollama / LM │      │ • Spek Laptop │   │ • AMCA Combo  │
│ • No API Key  │   │ • API Key RAM │      │ • Scan Model  │      │ • HardwareGate│   │ • 3-Tier Fall │
│ • Combo Scan  │   │ • Model Input │      │ • No Key local│      │ • Unduh GGUF  │   │ • Offline Det │
└───────────────┘   └───────────────┘      └───────────────┘      └───────────────┘   └───────────────┘
```

### Rincian Verifikasi 12 Provider:

1. **`9Router` (Local Proxy Gateway)**:
   - **Tampilan Dinamis**: Menampilkan input endpoint (`http://127.0.0.1:20128/v1`), pemeriksaan port runtime aktif/tidak aktif (`🟢 9Router Aktif`), tombol *Pindai Model & Combo 9Router*, dropdown model/combo, keterangan ramah bahwa API key sudah dikelola 9Router (tanpa beban input API key bagi periset), serta expander lanjutan bila ingin *override* API key remote.
   - **Hasil Uji**: ✅ Berfungsi sempurna, transisi mulus, zero key input by default.
2. **`Gemini` (Google Gemini Direct Cloud)**:
   - **Tampilan Dinamis**: Menampilkan keterangan koneksi langsung cloud, dropdown kurasi model resmi (`gemini-2.5-flash`, `gemini-2.5-pro`, `gemini-2.0-flash`, `gemini-1.5-pro`), input password API key, dan garansi keamanan RAM vault (`SessionCredentialVault`).
   - **Hasil Uji**: ✅ Berfungsi sempurna setelah perbaikan inkonsistensi string label.
3. **`xAI (Grok)`**:
   - **Tampilan Dinamis**: Input Model ID (`grok-2-latest`), input password API key, garansi memori sesi RAM.
   - **Hasil Uji**: ✅ Berfungsi normal.
4. **`OpenAI`**:
   - **Tampilan Dinamis**: Input Model ID (`gpt-4o-mini`), input password API key, garansi memori sesi RAM.
   - **Hasil Uji**: ✅ Berfungsi normal.
5. **`Anthropic`**:
   - **Tampilan Dinamis**: Input Model ID (`claude-3-5-sonnet-latest`), input password API key, garansi memori sesi RAM.
   - **Hasil Uji**: ✅ Berfungsi normal.
6. **`Custom OpenAI-Compatible`**:
   - **Tampilan Dinamis**: Input Base URL kustom (`http://127.0.0.1:8000/v1`), input Model ID, input password API key.
   - **Hasil Uji**: ✅ Berfungsi normal.
7. **`Ollama`**:
   - **Tampilan Dinamis**: Input endpoint (`http://127.0.0.1:11434`), status runtime probe, tombol *Pindai Model Ollama*, dropdown model lokal terpasang, keterangan bebas API key, dan expander bearer token opsional.
   - **Hasil Uji**: ✅ Berfungsi normal.
8. **`LM Studio`**:
   - **Tampilan Dinamis**: Input endpoint (`http://127.0.0.1:1234/v1`), status probe, tombol pindai, dropdown model terpasang, keterangan bebas API key.
   - **Hasil Uji**: ✅ Berfungsi normal.
9. **`OpenCode`**:
   - **Tampilan Dinamis**: Input endpoint (`http://127.0.0.1:4096`), status probe, tombol pindai, keterangan bebas API key.
   - **Hasil Uji**: ✅ Berfungsi normal.
10. **`Local Model` (Model GGUF Mandiri Dijaga Hardware Gate)**:
    - **Tampilan Dinamis**: Dropdown katalog model terkurasi (`qwen2.5-coder-7b-instruct-q4_k_m`, `deepseek-r1-distill-qwen-7b-q4_k_m`), tampilan spek laptop seketika (RAM Tersedia, Disk Bebas, CPU Logical Cores), status keputusan Hardware Gate (`ELIGIBLE` atau `REFUSED`), dan tombol pendaftaran manifest.
    - **Hasil Uji**: ✅ Berfungsi normal, inspeksi hardware OS asli.
11. **`AMCA Combo` (Rantai Fallback Native)**:
    - **Tampilan Dinamis**: Input Nama Rantai Combo (`resilient-local-combo`), spesifikasi Tier 1, Tier 2, Tier 3 Fallback Akhir, dan API key Tier 1 opsional. Mendaftarkan rantai fallback ke `AgentHarnessSession`.
    - **Hasil Uji**: ✅ Berfungsi normal.
12. **`Offline Deterministic` (Mode Air-Gapped 100% Offline)**:
    - **Tampilan Dinamis**: Banner hijau `🛡️ Mode Air-Gapped (100% Offline)`, penjelasan pembuat spesifikasi berbasis aturan matematika deterministik murni, tanpa koneksi jaringan, tanpa API key, tanpa biaya token.
    - **Hasil Uji**: ✅ Berfungsi normal, zero input API key, menghasilkan spesifikasi valid secara deterministik.

---

## 3. Pengujian Alur 8 Bagian Antarmuka Kerja (*The 8 Workflow Sections*)

Pengujian menyeluruh dilakukan dari langkah perancangan awal hingga eksekusi dan ekspor paket kode ZIP:

### Bagian 1 · Problem Statement & Batasan Prompt
- **Katalog Komponen Terdaftar**: Menampilkan badge jumlah komponen aktif (`22 komponen`) beserta daftar ID komponen yang dapat digunakan.
- **Expander Panduan Kontrak Hoare**: Menampilkan tabel Markdown yang merinci seluruh input port, output port, prasyarat $\{P_c\}$, dan pascakondisi $\{Q_c\}$.
- **Pemilih Contoh (*Example Selector*)**: Memilih contoh dari berkas `examples/*.yaml` dan memuatnya ke editor seketika, serta opsi `(tanpa contoh)` untuk mengosongkan editor.
- **Klasifikasi Intent**: Prompt yang di luar cakupan (*out-of-scope*) seperti meminta resep masakan langsung ditolak secara aman dan memicu Jendela Mengambang Diagnostik.

### Bagian 2 · Revisi lewat Chat
- **Riwayat Obrolan (*Chat Messages*)**: Memelihara pesan percakapan berurutan (*user* dan *assistant*).
- **Status Validasi Real-time**: Menampilkan widget status saat revisi diproses dan memvalidasi ulang kandidat secara otomatis.
- **Injeksi Diagnostik**: Apabila terdapat kegagalan validasi atau *counterexample* formal pada revisi sebelumnya, sistem secara otomatis meneruskannya ke agent sebagai konteks perbaikan.

### Bagian 3 · Tinjau, Validasi Struktural, & Verifikasi Formal 3-Tahap
- **Editor YAML**: Menampilkan draf YAML lengkap dengan penomoran baris.
- **Deteksi Komponen Tak Terdaftar**: Memindai draf YAML untuk menemukan komponen baru. Jika ditemukan, menampilkan peringatan kuning dan tombol **⚡ Sintesis & Daftarkan Komponen On-The-Fly (Code Agent)**.
- **Validasi AMCA**: Menampilkan badge hijau `VERIFIED` atau merah `REJECTED`.
- **Formal Verification (Stage 1 & 2)**: Menampilkan badge `PROVED` beserta SHA-256 sertifikat bukti, atau badge `REFUTED` beserta jumlah *counterexample* konkret.
- **Expander Sertifikat Bukti Formal**: Menampilkan struktur JSON lengkap dari `formal-proof-certificate.json`.
- **Riwayat Versi YAML (*Immutable Versioning*)**: Dropdown pemilih versi draf terdahulu dan tombol **Pulihkan versi terpilih**.

### Bagian 4 · Graf DAG Mesin
- **Visualisasi Graphviz**: Menampilkan visualisasi graf aliran data terarah (DAG) secara interaktif ketika spesifikasi berstatus `verified`.
- **Unduh Graf DAG**: Tombol unduh berkas `machine-dag.dot`.
- **Candidate Graph JSON**: Expander yang menampilkan representasi internal kandidat graf.

### Bagian 5 · Eksekusi yang Disetujui User (*Safe Runtime*)
- **Input Runtime JSON**: Area teks untuk konfigurasi data masukan JSON.
- **Checkbox Persetujuan**: Checkbox wajib *"Saya menyetujui eksekusi mesin ini"*. Tombol eksekusi dinonaktifkan (*disabled*) jika checkbox belum dicentang.
- **Eksekusi Deterministik**: Menjalankan mesin melalui runtime AMCA murni dan menampilkan `execution-record.json` lengkap.

### Bagian 6 · Konstruksi Proyek Python Mandiri & Paket Handover (.zip)
- **Persyaratan Gerbang**: Bagian ini terkunci rapat hingga spesifikasi berstatus `verified` dan pembuktian formal Stage 1 berstatus `PROVED`.
- **Persetujuan Dua Tahap (*Two-Stage Approval*)**:
  - Tombol 1: **Kunci Persetujuan Spesifikasi (`APPROVE_SPEC`)** $\to$ menghasilkan *Construction Plan*.
  - Tombol 2: **Setujui Konstruksi & Bangun Paket Handover ZIP (`APPROVE_CONSTRUCTION`)** $\to$ menyusun struktur folder proyek, menjalankan verifikasi Stage 3 AST isomorfisme ($G_{\text{code}} \cong G_{\text{yaml}}$), menjalankan `compileall` dan `unittest`, serta membundel pustaka kumulatif `src/amca_components/`.
- **Unduh Handover ZIP**: Tombol unduh langsung untuk berkas `<machine_id>-rev<NNN>-handover.zip`.

### Bagian 7 · Artefak Tersimpan & Penjelajah Riwayat
- **Folder Artefak Terakhir**: Menampilkan daftar seluruh berkas yang dihasilkan pada siklus aktif beserta tombol unduh per berkas (`.json`, `.yaml`, `.dot`).
- **Jelajahi Artefak Siklus Sebelumnya**: Dropdown untuk meninjau kembali berkas dari eksekusi historis di folder `artifacts/runs/`.

### Bagian 8 · Pembuat & Pendaftar Komponen Baru (Custom Component Studio)
- **Tab 1 — Template Operasi Deterministik**: Form perancangan komponen kustom dengan pilihan mode pemrosesan teks, pendaftaran langsung ke registry AMCA, dan tombol draf otomatis dari deskripsi peran.
- **Tab 2 — Ikat File Python (.py) dari Luar**: Editor kode Python dengan **Gerbang Keamanan AST Statis**. Kode yang memuat impor berbahaya (`import os`, `subprocess`, `sys`) langsung ditolak secara *fail-closed* dan memunculkan Jendela Mengambang Diagnostik.

---

## 4. Pengujian Jendela Mengambang Diagnostik (*Fly-Window Modal* `@st.dialog`)

Jendela mengambang modal diuji untuk memastikan error tidak lagi tampil sebagai pesan merah mentah yang membingungkan:

1. **Kasus 1: Error 9Router Tanpa Akun Provider Terhubung (`EXTERNAL_SERVICE`)**:
   - **Tampilan**: Modal dialog muncul di tengah layar dengan badge oranye `🌐 Layanan Eksternal / Gateway AI`.
   - **Judul**: `9Router Belum Memiliki Akun Penyedia AI yang Terhubung`.
   - **Instruksi Solusi**: Menyediakan tautan langsung yang dapat diklik ke `http://localhost:20128` menu Providers.
   - **Interaktivitas**: Tombol "Tutup Jendela" menutup modal tanpa menghapus draf kerja pengguna. Tombol di sidebar **"🔍 Buka Jendela Diagnostik"** dapat diklik kapan saja untuk membuka kembali laporan.
2. **Kasus 2: Error Sintaksis YAML & Ketidakcocokan Port (`USER_INPUT_FLOW`)**:
   - **Tampilan**: Modal dialog dengan badge biru laut `📝 Alur Masukan / Spesifikasi Riset`.
   - **Judul**: `Spesifikasi YAML Melanggar Skema atau Topologi Graf`.
   - **Instruksi Solusi**: Panduan memeriksa sintaksis atau meninjau letak sisi (edges) yang keliru pada graf.
3. **Kasus 3: Penolakan Gerbang Keamanan AST Statis (`USER_INPUT_FLOW`)**:
   - **Tampilan**: Modal dialog dengan badge biru laut `📝 Alur Masukan / Spesifikasi Riset`.
   - **Judul**: `Kode Komponen Ditolak oleh Gerbang Keamanan AST Statis`.
   - **Instruksi Solusi**: Panduan menghapus impor modul sistem berbahaya dan hanya menggunakan modul deterministik murni (`re`, `json`, `math`).
4. **Kasus 4: Pengecualian Sistem Internal (`CORE_SYSTEM`)**:
   - **Tampilan**: Modal dialog dengan badge merah tua `⚙️ Sistem Inti AMCA`.
   - **Expander Rincian Teknis**: Menampilkan konteks operasi, pesan asli sistem, dan *stack trace* untuk kebutuhan pelaporan bug.

---

## 5. Analisis Konsistensi, Redundansi Komponen, & Ergonomi Tampilan

### A. Temuan & Resolusi Inkonsistensi Komponen
Selama proses audit antarmuka dinamis, ditemukan 1 (satu) inkonsistensi string pada pemetaan provider:
- **Temuan**: Pada `app.py` baris 68, opsi provider bernama `"Gemini"`. Namun pada baris 229 dan 234 terdapat pengecekan `provider == "Google Gemini"`. Akibatnya, ketika periset memilih `"Gemini"`, antarmuka melewati blok konfigurasi Gemini dan tidak menampilkan kolom API Key maupun dropdown rekomendasi model Gemini.
- **Resolusi**: Diperbaiki menjadi `elif provider in {"Gemini", "Google Gemini", ...}:` dan `if provider in {"Gemini", "Google Gemini"}:`.
- **Hasil Verifikasi**: Dropdown *"Pilih Model Gemini"* (`gemini-2.5-flash`, dll.) dan kolom API key kini muncul sempurna secara dinamis saat Gemini dipilih.

### B. Audit Redundansi Komponen
- **Pengecekan Kunci Widget (*Widget Keys*)**: Seluruh widget di `app.py` memiliki *unique key* yang konsisten (misal `key="model_gemini_select"`, `key="key_9router_override"`, `key="btn_synthesize_otf"`), sehingga tidak terjadi benturan state (*zero widget collision*).
- **Pengecekan Duplikasi Tombol**: Tidak ada tombol duplikat dengan fungsi ganda. Tombol tindakan penting (seperti validasi, sintesis, persetujuan, dan eksekusi) dikelompokkan secara kontekstual di bagiannya masing-masing.

### C. Evaluasi Tampilan Natural & Ergonomi Riset
1. **Pemisahan Perhatian (*Separation of Concerns*)**:
   - Sidebar kiri dikhususkan murni untuk **Infrastruktur & Sumber Kecerdasan** (pilihan provider, API key, inspeksi spek laptop, muat sesi).
   - Kolom kiri kanvas dikhususkan untuk **Perumusan Masalah & Kolaborasi AI** (katalog kontrak Hoare, perumusan problem, draf awal, dan revisi chat).
   - Kolom kanan kanvas dikhususkan untuk **Verifikasi Formal & Penjaminan Kualitas** (editor YAML, status verifikasi struktural, sertifikat bukti formal, dan diagram DAG).
2. **Keterbukaan Bertahap (*Progressive Disclosure*)**:
   - Fitur eksekusi mesin (Bagian 5) terkunci sampai spesifikasi berstatus `verified`.
   - Fitur konstruksi proyek Python dan pengemasan ZIP (Bagian 6) terkunci sampai spesifikasi lolos Stage 1 Formal Verification (`PROVED`).
   - Pendekatan ini secara natural memandu peneliti agar tidak melompat ke tahap eksekusi sebelum spesifikasi terbukti benar secara matematis.

---

## 6. Kesimpulan & Rekomendasi

Aplikasi AMCA Versi Lokal Mandiri (`v0.5.0`) telah lulus pengujian komprehensif antarmuka dinamis dengan predikat **Sangat Baik**:
- Seluruh 12 alur provider adaptif berfungsi normal.
- Penanganan error terpadu dengan Jendela Mengambang (*Fly-Window Modal*) berhasil mengeliminasi kebingungan periset melalui klasifikasi 3 asal masalah.
- Pustaka komponen kumulatif dan pengikatan komponen eksternal terintegrasi mulus dengan verifikasi formal 3-tahap.
- 136 pengujian otomatis lulus 100% tanpa regresi.

Laporan ini siap dijadikan acuan operasional dan bukti verifikasi fungsional sistem.
