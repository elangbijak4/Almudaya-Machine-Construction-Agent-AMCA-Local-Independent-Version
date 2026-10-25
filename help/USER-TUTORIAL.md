# AMCA User Tutorial (Tutorial Praktik Langkah-demi-Langkah & Skenario Verifikasi — Versi Lokal Mandiri)

**Versi Dokumen:** `0.2.0` · **Bahasa:** Indonesia  
**Peran Dokumen:** Panduan *hands-on* langkah demi langkah dari tingkat dasar hingga tingkat lanjut (9Router/Combo Fallback, Hardware Gate, Subworker HITL, 3-Stage Formal Verification, dan Handover ZIP), sekaligus skenario uji terima (*Acceptance Test Scenarios*) saat verifikasi aplikasi Versi Lokal Mandiri.

---

## Persiapan Awal Lingkungan (Windows PowerShell)

Buka Windows PowerShell di direktori akar repositori (`d:\AMCA_Waterfall_Scaffold_v0.2`):

```powershell
py -3.12 -m venv .venv
$PY = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $PY)) { throw "Virtual environment not found. Run: py -3.12 -m venv .venv" }
& $PY -m pip install -r requirements-app.txt
$env:PYTHONPATH = "src"
```

---

## Tutorial 1: Alur Dasar Lokal (`schema_version: "1.0"`) Tanpa API Key

Tutorial pertama ini memastikan kompatibilitas mundur (`P0`–`P6`) tetap berjalan sempurna tanpa memerlukan koneksi internet atau API Key.

### A. Melalui CLI
```powershell
& $PY -m amca_agent.cli examples
& $PY -m amca_agent.cli example valid_parallel_analysis --output machine.yaml
& $PY -m amca_agent.cli validate machine.yaml
& $PY -m amca_agent.cli graph machine.yaml --output machine-dag.dot
& $PY -m amca.cli run machine.yaml --inputs examples/reference-input.json --output execution-record.json
& $PY -m amca.cli report execution-record.json
```
- **Hasil yang Wajib Terverifikasi**:
  - `validate` menghasilkan status `VERIFIED` (exit code `0`).
  - `report` menampilkan status `SUCCEEDED` dengan ringkasan `characters=20; words=4` untuk input `{"text": "AMCA builds a graph."}`.

### B. Melalui GUI (`app.py`)
1. Jalankan `& $PY -m streamlit run app.py` dan buka `http://localhost:8501`.
2. Pilih contoh `valid_parallel_analysis` $\to$ klik **Muat contoh ke editor** $\to$ klik **Validasi YAML saat ini**.
3. Pastikan status `VERIFIED` dan graf DAG tampil di layar.
4. Centang **Saya menyetujui eksekusi mesin ini** $\to$ klik **Jalankan mesin** $\to$ pastikan output memuat `characters=20; words=4`.

---

## Tutorial 2: Inspeksi Spesifikasi Laptop (`hardware.py`) & Koneksi ke Ollama / LM Studio / OpenCode

Tutorial ini memverifikasi bahwa AMCA memeriksa spesifikasi perangkat keras laptop secara nyata sebelum mengizinkan unduhan model lokal, serta dapat mendeteksi model di **Ollama**, **LM Studio**, dan **OpenCode**.

### Langkah 1 — Menguji Inspeksi Perangkat Keras Laptop
Jalankan perintah inspeksi perangkat keras:
```powershell
& $PY -m amca_agent.cli hardware-check
```
- **Hasil yang Wajib Terverifikasi**:
  - Menampilkan data nyata dari OS laptop Anda: `ram_total_mb`, `ram_available_mb`, `disk_free_mb`, `cpu_logical_cores`, `cpu_arch`, dan `gpu_detected`.
  - Menampilkan daftar kelayakan katalog model lokal:
    - Model yang kebutuhannya di bawah RAM/Disk bebas laptop Anda berstatus **`ELIGIBLE`**.
    - Model raksasa yang melebihi kapasitas RAM/Disk laptop Anda berstatus **`REFUSED_INSUFFICIENT_HARDWARE`** dan tombol/perintah unduhannya **diblokir secara otomatis**.

### Langkah 2 — Memindai Model Lokal dari Ollama, LM Studio, atau OpenCode
Jika Anda menjalankan Ollama (`:11434`), LM Studio (`:1234`), atau OpenCode (`:4096` / CLI):
```powershell
& $PY -m amca_agent.cli discover-models --provider ollama
& $PY -m amca_agent.cli discover-models --provider lm_studio
& $PY -m amca_agent.cli discover-models --provider opencode
```
- **Hasil yang Wajib Terverifikasi**:
  - AMCA menampilkan daftar model yang terpasang pada masing-masing runtime lokal tersebut dan mengizinkan Anda memilihnya sebagai otak Agent Utama maupun Subworker.

---

## Tutorial 3: Menghubungkan **9Router** & Meracik **Rantai Fallback Combo (`amca_combo`)** untuk Mengatasi Limit Token

Tutorial ini mempraktikkan cara menghubungkan AMCA ke **9Router** (termasuk **Combo 9Router**) serta menyusun **Rantai Fallback Combo Native AMCA** agar sesi konstruksi tidak gagal saat sebuah model mencapai batas token (*token limit*) atau kuota habis (`HTTP 429`).

### Skenario A — Menggunakan Model atau Combo dari 9Router
1. Pastikan 9Router berjalan di `http://127.0.0.1:20128`.
2. Pindai daftar model dan Combo yang ada di 9Router:
   ```powershell
   & $PY -m amca_agent.cli discover-models --provider nine_router --base-url http://127.0.0.1:20128/v1
   ```
3. Mulai sesi konstruksi menggunakan alias Combo 9Router (misalnya `premium-coding` atau `free-combo`):
   ```powershell
   & $PY -m amca_agent.cli chat --provider nine_router --model premium-coding
   ```

### Skenario B — Menyusun Rantai Fallback Combo Native di AMCA (`Tier 1 -> Tier 2 -> Tier 3`)
1. Pada GUI (`app.py`), buka panel **Preliminary Harness & Combo Setup** $\to$ pilih tab **Combo & Fallback Chain Builder** (atau jalankan `& $PY -m amca_agent.cli combo-config`).
2. Buat Combo bernama `riset-tahan-limit` dengan urutan:
   - **Tier 1**: `gemini` (`gemini-2.5-pro`)
   - **Tier 2**: `nine_router` (`free-combo`)
   - **Tier 3**: `ollama` (`qwen2.5-coder:7b`)
   - **Tier 4**: `offline_deterministic` (`builtin-v1`)
3. Simpan dan aktifkan `riset-tahan-limit` sebagai otak Agent Utama AMCA.
4. **Hasil yang Wajib Terverifikasi saat Terjadi Limit Token**:
   - Ketika Tier 1 mencapai batas token (`token_limit_exceeded` / `context_length_exceeded` / respons terpotong `finish_reason == "length"`) atau kuota habis (`HTTP 429`), AMCA:
     1. Mengompaksi konteks percakapan (tetap menyimpan YAML revisi terakhir dan *counterexample* formal),
     2. Mencatat `FallbackTransitionEvent` (`from_tier: 1 -> to_tier: 2`, `trigger_reason: "token_limit_exceeded"`),
     3. Melanjutkan pembuatan YAML secara otomatis melalui Tier 2 tanpa kehilangan sesi.

---

## Tutorial 4: Merancang Sistem Mesin (`amca/v1alpha1`) & Memperbaiki *Counterexample* Verifikasi Formal Stage 1–2

Tutorial ini mendemonstrasikan mengapa verifikasi struktural biasa tidak cukup bagi peneliti, dan bagaimana **Stage 1 Formal Verifier (`formal_verifier.py`)** menangkap cacat logika komposisi.

1. Mulai sesi interaktif:
   ```powershell
   & $PY -m amca_agent.cli chat
   ```
2. Ketika muncul pertanyaan ***“Mesin/agent apakah yang Anda ingin buat?”***, masukkan permintaan:
   > *"Buat sistem analisis teks yang menerima teks masukan, memvalidasi agar tidak kosong, menghitung karakter dan kata, merangkum hasil, dan membuat laporan."*
3. Di dalam prompt `amca>`, jalankan:
   ```text
   amca> validate
   amca> proof
   ```
4. **Simulasi Cacat Logika Komposisi (Uji Negatif Formal)**:
   - Misalkan pada draf YAML, koneksi dari `input` (`text.input`) langsung dihubungkan ke `analysis_a` (`text.char_count`) dengan melewati `validate` (`text.validate`).
   - Pemeriksaan tipe port biasa melihat `string -> string` (cocok), **TETAPI** perintah `proof` akan melaporkan:
     - **Status Stage 1**: `REFUTED` pada kewajiban **`FO-HOA-01` (*Hoare Pre/Postcondition Entailment*)**.
     - **Counterexample**: Pascakondisi `text.input` hanya menjamin `non_empty_raw`, sedangkan prasyarat `text.char_count` mewajibkan `non_empty_trimmed` (contoh penyangkal: input `"   "`).
5. Minta agen memperbaiki berdasarkan *counterexample* tersebut:
   ```text
   amca> revisi Hubungkan output text dari input ke validate terlebih dahulu sebelum masuk ke analysis_a dan analysis_b
   amca> validate
   amca> proof
   ```
6. Pastikan kini seluruh pemeriksaan Stage 1 (`FO-TOP-01`, `FO-CON-01`, `FO-HOA-01`, `FO-GOAL-01`, `FO-SEC-01`) dan Stage 2 berstatus **`PROVED`**.
7. Kunci spesifikasi dengan **Approval A**:
   ```text
   amca> approve-spec
   ```
   Ketik `APPROVE_SPEC` saat diminta konfirmasi.

---

## Tutorial 5: *On-The-Fly Subworker HITL*, Approval B, Konstruksi Proyek, Bukti Stage 3 ($G_{\text{code}} \cong G_{\text{yaml}}$), & Handover ZIP

Melanjutkan dari Tutorial 4 setelah `approve-spec` berhasil:

1. Tampilkan rencana konstruksi dan picu evaluasi Subworker:
   ```text
   amca> plan
   ```
2. **Merespons Prompt *On-The-Fly Subworker HITL***:
   - Ketika AMCA mengusulkan pembuatan Subworker (mis. `subworker-formal-auditor-01` untuk mengaudit pengujian tepi), antarmuka **On-The-Fly HITL** akan muncul meminta persetujuan Anda.
   - Pilih **`APPROVED`**, lalu masukkan konfigurasi model/API key yang **berbeda** dari Agent Utama (misalnya mengarahkan Subworker ke model lokal di **Ollama/LM Studio**, ke **Combo 9Router**, atau memasukkan API Key provider lain). *(Jika Anda memilih `DECLINED`, AMCA akan tetap lanjut menggunakan Agent Utama saja).*
3. Kunci rencana konstruksi dengan **Approval B**:
   ```text
   amca> approve-construction
   ```
   Ketik `APPROVE_CONSTRUCTION` saat diminta konfirmasi.
4. Bangun proyek Python mandiri dan jalankan verifikasi lengkap:
   ```text
   amca> construct
   ```
5. **Hasil yang Wajib Terverifikasi**:
   - Proyek Python lengkap terbuat di `artifacts/constructed_projects/<machine_id>-rev<NNN>/`.
   - **Stage 3 Formal Verification (`FO-REF-01` & `FO-REF-02`)** mem-parsing AST file Python yang dihasilkan dan membuktikan **`PROVED`** bahwa $G_{\text{code}} \cong G_{\text{yaml}}$ serta setiap komponen memiliki *runtime contract guard*.
   - Suite `unittest` milik proyek yang dihasilkan dieksekusi secara nyata dan lulus 100%.
   - Arsip **`<machine_id>-rev<NNN>-handover.zip`** berhasil dibuat, berisi kode sumber, test, `machine.yaml`, `formal-proof-certificate.json`, `machine-dag.dot`, `README.md`, dan `construction-log.jsonl` (tanpa satu pun API key di dalamnya).

---

## Tutorial 6: Membuat & Mendaftarkan Komponen Baru, Memeriksa Katalog Batasan Prompt, & Mengonstruksi Mesin Kustom

Tutorial ini memandu Anda menambahkan komponen deterministik baru di luar 6 komponen bawaan, memeriksa **Katalog Komponen Terdaftar & Batasan Prompt**, lalu mengonstruksi paket proyek Python mandiri (`.zip`) yang menggunakan komponen kustom tersebut:

1. **Tampilkan Katalog Komponen Terdaftar & Batasan Prompt saat ini**:
   ```powershell
   & $PY -m amca_agent.cli components
   ```
   Perhatikan tabel komponen bawaan (`input_source`, `validate_text`, `analysis_a`, `analysis_b`, `aggregate_results`, `generate_report`) beserta panduan **Batasan Prompt**.
2. **Buat dan daftarkan komponen baru (`sentence_counter`)**:
   ```powershell
   & $PY -m amca_agent.cli register-component --id sentence_counter --alias custom.sentence_counter --name "Sentence Counter" --role "Menghitung jumlah kalimat dari teks yang telah divalidasi" --template text_metric_object --mode sentence_count
   ```
   *(Di GUI `app.py`, Anda juga dapat membuka **Bagian 8 · Pembuat & Pendaftar Komponen Baru (Custom Component Studio)** dan menekan **Daftarkan Komponen ke Registry AMCA** atau **Draft Otomatis dari Deskripsi Peran**).*
3. **Verifikasi bahwa `sentence_counter` kini tampil di Katalog Komponen Terdaftar**:
   ```powershell
   & $PY -m amca_agent.cli components
   ```
   Kini tabel menampilkan **7 Komponen (6 Inti, 1 Kustom)** beserta kontrak Hoare untuk `sentence_counter`.
4. **Bangun YAML dan Konstruksi Paket Proyek Mandiri (`.zip`) dengan Komponen Baru**:
   Di dalam sesi `chat` (`& $PY -m amca_agent.cli chat --provider "Offline Deterministic"`), masukkan prompt:
   > *"Buat pipeline `machine_id: custom_sentence_machine` menggunakan `sentence_counter` setelah `validate_text`."*
   Lalu jalankan `approve-spec`, `plan`, `approve-construction`, dan `construct`. Proyek mandiri yang dihasilkan di `artifacts/constructed_projects/custom_sentence_machine-rev001/` dan arsip `.zip`-nya akan memuat fungsi `run_custom_sentence_counter` beserta *runtime Hoare guard*-nya dan lulus **Stage 3 AST Proof (`PROVED`)**!


