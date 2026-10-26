# Spesifikasi Teknis: Desain Kartu & Alur Dinamis Provider (*Dynamic Dashboard Cards*)

## 1. Prinsip Antarmuka Reaktif Berbasis Kategori

Antarmuka sidebar di [`app.py`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/app.py) harus bertindak sebagai **konsol adaptif**. Elemen visual yang ditampilkan harus 100% relevan dengan provider yang sedang dipilih oleh periset:

```
[Pilihan Provider]
       │
       ├─► 9Router                ──► Status Port 20128 + Deteksi Provider Aktif + Combo Selector + Key Auto-Detected
       ├─► Cloud API (Gemini/dsb) ──► Model Rekomendasi + Kolom API Key Aman (Badge Memory Vault)
       ├─► Ollama / LM Studio     ──► Probe Port Lokal + Daftar Model Terpasang di Laptop (Tanpa Key)
       ├─► Local Model (GGUF)     ──► Inspeksi Spek Laptop (RAM/VRAM/Disk) + Tombol Pasang (Tanpa Key)
       ├─► AMCA Native Combo      ──► Pembangun Rantai Fallback Tier 1-N + Visualisasi Failover
       └─► Offline Deterministic  ──► Status Air-Gapped + Zero Konfigurasi Jaringan (Tanpa Key)
```

---

## 2. Rincian Perilaku Dinamis per Provider

### 2.1 Provider `9Router` (Local Proxy & Gateway)
- **Tujuan UX**: Memberikan kepastian status server lokal 9Router dan menghilangkan keraguan periset mengenai perlunya API key.
- **Komponen Dinamis yang Ditampilkan**:
  1. **Indikator Konektivitas Real-Time**:
     - Sistem mem-probe `http://127.0.0.1:20128/v1/models` dan database SQLite lokal (`C:\Users\HP\AppData\Roaming\9router\db\data.sqlite`).
     - Jika aktif: Menampilkan status `🟢 9Router Aktif di Port 20128`.
     - Jika nonaktif: Menampilkan status `🔴 9Router Tidak Terdeteksi di Port 20128` beserta petunjuk menjalankan `9router start`.
  2. **Inspeksi Provider Connection 9Router**:
     - Memeriksa jumlah baris aktif pada tabel `providerConnections` di `data.sqlite`:
       - **Jika > 0**: Menampilkan info ramah `✅ Terhubung ke X akun provider di 9Router`.
       - **Jika == 0**: Menampilkan kartu edukatif berwarna biru muda/kuning:
         > *"ℹ️ 9Router terdeteksi aktif, tetapi belum ada akun provider yang disambungkan di dashboard 9Router. Buka [http://localhost:20128](http://localhost:20128) lalu menu **Providers** untuk menambahkan kunci AI (Gemini, Claude, OpenAI, dsb.)."*
  3. **Pilihan Model & Combo**:
     - Dropdown model yang memuat daftar Combo (seperti `free-combo`, `premium-coding`) di urutan teratas, diikuti model spesifik.
  4. **Penyederhanaan Kolom API Key**:
     - Kolom API key **tidak ditampilkan di layar utama** karena AMCA otomatis menggunakan `Default Key` lokal.
     - Disediakan tombol/expander tertutup: `⚙️ Pengaturan Lanjutan (Override 9Router Access Key)` jika periset menghubungkan ke 9Router di komputer lain.

---

### 2.2 Provider Cloud API Langsung (`Google Gemini`, `xAI (Grok)`, `OpenAI`, `Anthropic`, `Custom OpenAI-Compatible`)
- **Tujuan UX**: Memastikan kunci rahasia periset terlindungi dan memberikan pilihan model riset terbaik.
- **Komponen Dinamis yang Ditampilkan**:
  1. **Badge Kategori**: `☁️ Cloud API Langsung`.
  2. **Model Rekomendasi Riset**:
     - Untuk `Google Gemini`: pilihan cepat `gemini-2.5-flash` (cepat, hemat) atau `gemini-2.5-pro` (penalaran kompleks).
     - Untuk `xAI (Grok)`: `grok-3-mini` atau `grok-2`.
     - Untuk `OpenAI`: `gpt-4.1-mini`, `gpt-4o`.
     - Untuk `Anthropic`: `claude-3-7-sonnet`.
  3. **Kolom Input API Key Khusus**:
     - Tipe input `password` dengan ikon gembok.
     - Badge edukatif:
       > *"🔒 **Jaminan Keamanan**: API key hanya disimpan sementara di memori RAM laptop untuk sesi saat ini (`SessionCredentialVault`). Kunci tidak pernah ditulis ke berkas proyek, tidak dicatat di log, dan tidak disertakan ke arsip ZIP."*
  4. **Endpoint URL**:
     - Terkunci otomatis ke endpoint resmi provider (hanya dapat diubah jika memilih `Custom OpenAI-Compatible`).

---

### 2.3 Provider Runtime Model Lokal (`Ollama`, `LM Studio`, `OpenCode`)
- **Tujuan UX**: Menjalankan inferensi model open-weights secara mandiri di laptop periset tanpa internet dan tanpa API key.
- **Komponen Dinamis yang Ditampilkan**:
  1. **Indikator Port Runtime Real-Time**:
     - Untuk `Ollama`: mem-probe port `11434`.
     - Untuk `LM Studio`: mem-probe port `1234`.
     - Untuk `OpenCode`: mem-probe port `4096`.
     - Menampilkan badge hijau jika runtime aktif, atau badge peringatan kuning jika aplikasi runtime belum dijalankan periset.
  2. **Dropdown Model Terpasang**:
     - Mengambil daftar model yang telah di-download di laptop periset via `discover_provider_models()`.
     - Periset tinggal memilih model dari dropdown tanpa perlu mengetik manual.
  3. **Peniadaan Kolom API Key**:
     - Kolom API key disembunyikan sepenuhnya (atau diletakkan di expander opsional jika server lokal menggunakan bearer token khusus).

---

### 2.4 Provider `Local Model (GGUF)` (Model Mandiri Dijaga Inspeksi Spek)
- **Tujuan UX**: Memberikan transparansi kapasitas komputasi laptop periset sebelum memuat model besar.
- **Komponen Dinamis yang Ditampilkan**:
  1. **Katalog Model GGUF Terkurasi**: Dropdown pilihan model (mis. `qwen2.5-coder-7b-q4_k_m`, `deepseek-coder-1.3b-q4_k_m`).
  2. **Panel Inspeksi Perangkat Keras Nyata (`hardware.py`)**:
     - RAM Tersedia vs. RAM Total.
     - Ruang Disk Bebas vs. Kebutuhan Model.
     - Jumlah Core CPU dan Deteksi Akselerator GPU/VRAM.
  3. **Keputusan Gerbang (*Hardware Decision Gate*)**:
     - Status `ELIGIBLE` (hijau) atau `REFUSED_INSUFFICIENT_HARDWARE` (merah).
  4. **Tombol Konfirmasi Pemuatan**: Hanya aktif jika berstatus `ELIGIBLE`.
  5. **Tanpa Kolom API Key**: 100% komputasi lokal.

---

### 2.5 Provider `AMCA Combo` (Rantai Fallback Native Tahan Batas Token)
- **Tujuan UX**: Mencegah sesi perancangan mesin periset gagal saat menghadapi limit kuota atau token penuh.
- **Komponen Dinamis yang Ditampilkan**:
  1. **Nama Rantai**: Kolom nama identifikasi combo (mis. `riset-tahan-limit`).
  2. **Penyusun Rantai Bertingkat (*Multi-Tier Builder*)**:
     - Tier 1: Model Utama (mis. Cloud API Gemini atau 9Router).
     - Tier 2: Model Cadangan (mis. Ollama lokal).
     - Tier 3: Model Darurat (mis. Offline Deterministic).
  3. **Kartu Penjelasan Otomasi**:
     - Penjelasan bahwa sistem otomatis melakukan kompaksi konteks percakapan dan berpindah ke tier berikutnya jika terjadi error `HTTP 429` atau `token_limit_exceeded`.

---

### 2.6 Provider `Offline Deterministic` (Mode Air-Gapped)
- **Tujuan UX**: Menjamin ketersediaan 100% untuk pengujian atau lingkungan penelitian tertutup (*air-gapped*).
- **Komponen Dinamis yang Ditampilkan**:
  1. **Banner Mode Mandiri**:
     > *"🛡️ **Mode Air-Gapped (100% Offline)**: Menggunakan sintesis berbasis aturan formal deterministik. Tanpa koneksi jaringan, tanpa API key, tanpa biaya token."*
  2. **Tampilan Bersih**: Seluruh kolom URL, kunci, dan pengaturan jaringan dihilangkan sehingga periset dapat langsung fokus merancang mesin di Bagian 1.

---

## 3. Matriks Komponen Antarmuka Dinamis

| Provider Terpilih | Status Probe Port | Model Selector | Kolom API Key | Endpoint URL | Panel Hardware |
| :--- | :---: | :---: | :---: | :---: | :---: |
| **9Router** | Port 20128 & SQLite | Dropdown Model/Combo | Tersembunyi (Auto Default Key) | Terkunci 20128 | Tidak |
| **Google Gemini** | Tidak (Cloud) | Pilihan Cepat Rekomendasi | Wajib (Badge RAM Vault) | Terkunci Google | Tidak |
| **OpenAI / Claude / Grok** | Tidak (Cloud) | Model Input | Wajib (Badge RAM Vault) | Terkunci Resmi | Tidak |
| **Ollama / LM Studio** | Port 11434 / 1234 | Dropdown Model Lokal | Tidak Ditampilkan | Dapat disesuaikan | Tidak |
| **Local Model (GGUF)** | Spek OS Laptop | Katalog Terkurasi | Tidak Ditampilkan | N/A (Lokal) | **Aktif (`hardware.py`)** |
| **AMCA Combo** | Gabungan Tier | Rantai Tier 1..N | Opsional per Tier | N/A | Tergantung Tier |
| **Offline Deterministic** | Tidak (Lokal) | Terkunci Kanonik | Tidak Ditampilkan | N/A | Tidak |
