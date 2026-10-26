# Tutorial Praktis: Panduan Alur Antarmuka Berdasarkan Pilihan Provider (*Researcher's Guide*)

Panduan ini disusun khusus untuk membantu periset menavigasi antarmuka AMCA secara lancar dan bebas dari keraguan saat memilih berbagai jenis sumber kecerdasan buatan (*Agent Brain*).

---

## 1. Alur 1: Menggunakan 9Router (Local Proxy Gateway & Combos)

Gunakan opsi ini jika Anda menggunakan **9Router** untuk mengelola beragam akun AI atau memanfaatkan alias Combo (seperti `free-combo` atau `premium-coding`).

```
[Buka 9Router Dashboard] ──► [Hubungkan Akun Provider] ──► [Pilih 9Router di AMCA] ──► [Selesai! Tanpa Ketik Key]
(http://localhost:20128)      (Google/Claude/OpenAI)        (Kunci Otomatis Terbaca)
```

### Langkah-demi-Langkah:
1. **Langkah Persiapan (Satu Kali Saja di 9Router)**:
   - Pastikan 9Router berjalan di komputer Anda (`http://localhost:20128`).
   - Buka menu **Providers** (`http://localhost:20128/dashboard/providers`).
   - Hubungkan minimal satu akun penyedia AI (misalnya memasukkan Google Gemini API key atau login akun yang Anda miliki).
2. **Di Antarmuka AMCA (`http://localhost:8501`)**:
   - Pada sidebar kiri, pilih **Provider model**: `9Router`.
   - **Perhatikan Antarmuka yang Beradaptasi**:
     - Muncul indikator hijau: `🟢 9Router Aktif (Port 20128)`.
     - Jika provider di 9Router sudah aktif, muncul info jumlah provider yang terhubung.
     - Kolom API key disembunyikan karena AMCA secara otomatis mendeteksi `Default Key` lokal dari database 9Router.
3. **Pilih Model atau Combo**:
   - Pada dropdown model, pilih alias combo yang Anda inginkan (misalnya `free-combo`) atau model tertentu (seperti `alicode-intl/qwen3.5-plus`).
4. **Mulai Merancang Mesin**:
   - Masukkan prompt perancangan mesin di Bagian 1, lalu klik **Buat YAML dengan agent**.

---

## 2. Alur 2: Menggunakan Google Gemini (Cloud API Langsung)

Gunakan opsi ini jika Anda ingin menghubungkan AMCA langsung ke Google Gemini API tanpa perantara lokal.

### Langkah-demi-Langkah:
1. Pada sidebar kiri AMCA, pilih **Provider model**: `Google Gemini`.
2. **Perhatikan Antarmuka yang Beradaptasi**:
   - Pilihan model otomatis menampilkan rekomendasi riset:
     - `gemini-2.5-flash`: Sangat cepat, hemat kuota, ideal untuk iterasi cepat.
     - `gemini-2.5-pro`: Penalaran mendalam, ideal untuk spesifikasi graf nonlinier kompleks.
3. **Masukkan API Key Google Gemini**:
   - Tempel API key Anda pada kolom bertanda gembok `🔒 API key (hanya di memori sesi)`.
   - *Catatan Keamanan*: Kunci ini hanya berada di RAM laptop Anda selama sesi aktif.
4. **Mulai Merancang Mesin**:
   - Masukkan prompt di Bagian 1 dan klik **Buat YAML dengan agent**.

---

## 3. Alur 3: Menggunakan Ollama / LM Studio (Inferensi Lokal di Laptop)

Gunakan opsi ini jika Anda ingin menjalankan model open-weights (seperti `Qwen2.5-Coder`, `Llama-3`, `DeepSeek-Coder`) secara mandiri di laptop Anda tanpa koneksi internet.

### Langkah-demi-Langkah:
1. **Pastikan Aplikasi Runtime Aktif**:
   - Untuk **Ollama**: jalankan `ollama serve` di terminal (port `11434`).
   - Untuk **LM Studio**: buka aplikasi LM Studio dan aktifkan fitur *Local Server* (port `1234`).
2. **Di Antarmuka AMCA**:
   - Pada sidebar kiri, pilih **Provider model**: `Ollama` atau `LM Studio`.
   - **Perhatikan Antarmuka yang Beradaptasi**:
     - Sistem mem-probe port secara otomatis:
       - Jika aktif: muncul badge hijau `🟢 Terhubung ke runtime lokal`.
       - Jika belum aktif: muncul petunjuk kuning untuk menyalakan runtime.
     - **Kolom API Key ditiadakan**: Anda tidak perlu memikirkan atau mengetik API key.
     - Dropdown model otomatis menyajikan daftar model yang sudah Anda unduh ke laptop.
3. **Pilih Model Lokal**:
   - Pilih model coding lokal yang Anda sukai dari dropdown.
4. **Mulai Merancang Mesin**:
   - Masukkan prompt di Bagian 1 dan klik **Buat YAML dengan agent**.

---

## 4. Alur 4: Menggunakan Local Model GGUF Mandiri (Dijaga Hardware Gate)

Gunakan opsi ini jika Anda ingin mengunduh dan menjalankan berkas model GGUF terkurasi langsung di dalam direktori AMCA (`artifacts/local_models/`).

### Langkah-demi-Langkah:
1. Pada sidebar kiri AMCA, pilih **Provider model**: `Local Model`.
2. **Perhatikan Antarmuka yang Beradaptasi**:
   - Panel **Inspeksi Perangkat Keras Nyata (`hardware.py`)** muncul di sidebar, memperlihatkan kapasitas RAM bebas, ruang disk, dan core CPU laptop Anda.
   - Pilih model dari katalog terkurasi (mis. `qwen2.5-coder-7b-q4_k_m`).
3. **Tinjau Keputusan Gerbang Keamanan (*Hardware Gate Decision*)**:
   - **`ELIGIBLE` (Hijau)**: Laptop Anda memiliki kapasitas memori dan disk yang aman untuk menjalankan model ini. Tombol registrasi akan aktif.
   - **`REFUSED_INSUFFICIENT_HARDWARE` (Merah)**: Sistem menolak secara otomatis demi mencegah laptop Anda mengalami *freeze/hang* jika RAM tidak mencukupi.
4. **Daftarkan Model**:
   - Jika berstatus `ELIGIBLE`, klik tombol **Daftarkan & Siapkan Model Lokal**.

---

## 5. Alur 5: Menggunakan AMCA Combo (Rantai Fallback Multi-Tier Tahan Batas Token)

Gunakan opsi ini untuk penelitian skala besar di mana Anda ingin memastikan sesi tidak pernah terhenti akibat kehabisan token atau batasan kuota (*rate limit 429*).

### Langkah-demi-Langkah:
1. Pada sidebar kiri AMCA, pilih **Provider model**: `AMCA Combo`.
2. **Perhatikan Antarmuka yang Beradaptasi**:
   - Muncul panel pembangun rantai fallback bertingkat:
     - **Tier 1 (Utama)**: Model berkapasitas tinggi (mis. `Google Gemini:gemini-2.5-pro` atau `9Router:premium-coding`).
     - **Tier 2 (Cadangan)**: Model lokal atau model cepat (mis. `Ollama:qwen2.5-coder:7b`).
     - **Tier 3 (Darurat)**: Model deterministik lokal (`Offline Deterministic:builtin-v1`).
3. **Masukkan Kunci untuk Tier yang Membutuhkan**:
   - Hanya masukkan API key untuk Tier yang memerlukan koneksi cloud.
4. **Mekanisme Otomatis Saat Terjadi Kendala Token**:
   - Jika Tier 1 mencapai batas token (*token limit exceeded*) atau error `HTTP 429`, AMCA secara transparan melakukan **kompaksi konteks pintar** dan mengalihkan giliran pengerjaan ke Tier 2 secara otomatis tanpa kehilangan draf spesifikasi Anda!

---

## 6. Alur 6: Menggunakan Mode Offline Deterministic (Air-Gapped Research)

Gunakan opsi ini untuk lingkungan penelitian terisolasi tanpa jaringan internet (*air-gapped environment*), pengujian laboratorium berulang, atau saat Anda ingin membangun pipeline standar secara instan.

### Langkah-demi-Langkah:
1. Pada sidebar kiri AMCA, pilih **Provider model**: `Offline Deterministic`.
2. **Perhatikan Antarmuka yang Beradaptasi**:
   - Muncul badge `🛡️ Mode Air-Gapped (100% Offline)`.
   - Seluruh kolom konfigurasi jaringan, URL, dan API key otomatis lenyap.
3. **Mulai Merancang Mesin**:
   - Masukkan prompt di Bagian 1. AMCA menggunakan penalaran berbasis aturan kanonis untuk langsung menghasilkan spesifikasi graf YAML yang terbukti valid dan siap diverifikasi secara formal!
