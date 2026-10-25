# AMCA User Guide (Panduan Operasional Pengguna — Versi Lokal Mandiri)

**Versi Dokumen:** `0.2.0` · **Bahasa:** Indonesia  
**Peran Dokumen:** Panduan praktis bagi peneliti dan perekayasa perangkat lunak untuk mengoperasikan AMCA Versi Lokal Mandiri sehari-hari, sekaligus acuan verifikasi fungsional (*Functional Verification Reference*).

---

## 1. Memilih Antarmuka Kerja AMCA (GUI vs. CLI)

AMCA Versi Lokal Mandiri menyediakan dua antarmuka lokal (GUI & CLI) dengan kesetaraan fitur penuh (*feature parity*):

| Kebutuhan Pengguna | Antarmuka GUI (`app.py`) | Antarmuka CLI (`amca_agent.cli`) |
| :--- | :--- | :--- |
| **Mengatur API Key, 9Router, Ollama, LM Studio, OpenCode, atau Model Lokal** | Panel **Preliminary Harness & Combo Setup** di Sidebar / Tab Konfigurasi Awal | `amca_agent.cli chat` (perintah `setup`), `discover-models`, `hardware-check` |
| **Meracik Rantai Fallback Combo (Antisipasi Limit Token / Kuota)** | Tab **Combo & Fallback Chain Builder** (mirip 9Router Combos) | `amca_agent.cli combo-config` atau memilih `--provider nine_router --model <combo>` |
| **Membuat Spesifikasi Mesin dari Bahasa Alami** | Kotak dialog *"Mesin/agent apakah yang Anda ingin buat?"* | `amca_agent.cli chat` |
| **Meninjau Bukti Formal 3-Tahap & Memperbaiki *Counterexample*** | Panel **Formal Proof Certificate** & tombol **Revisi Otomatis** | Perintah `validate`, `proof`, dan `revisi <instruksi>` |
| **Menyetujui Spesifikasi (Approval A)** | Checkbox & Tombol **Setujui Spesifikasi (Approval A)** | Perintah `approve-spec` (ketik `APPROVE_SPEC`) |
| **Merespons Usulan Subworker (*On-The-Fly HITL*)** | Modal / Kartu Interaktif **Subworker HITL Approval & Key Input** | Prompt interaktif saat `plan` / `construct` meminta persetujuan & API key Subworker |
| **Membangun Proyek Python Mandiri & Mengunduh Handover ZIP** | Tombol **Setujui Konstruksi (Approval B)** $\to$ **Bangun Proyek & Unduh ZIP** | Perintah `approve-construction` $\to$ `construct` |
| **Menjalankan Mesin dengan Input JSON** | Panel **Runtime Input JSON** + Checkbox Persetujuan $\to$ **Jalankan Mesin** | Perintah `run <input.json>` (ketik `RUN`) |

---

## 2. Langkah 0: Mengonfigurasi *Specialized Agent Harness* (Sebelum Memulai)

Sebelum meminta AMCA merancang atau membangun mesin/agen, atur terlebih dahulu sumber kecerdasan (**Otak Agent Utama AMCA**) pada antarmuka pendahuluan:

### Opsi A — Menggunakan Cloud API Key (Gemini, xAI Grok, OpenAI, Anthropic, atau Custom Endpoint)
1. Pilih provider (`gemini`, `xai`, `openai`, `anthropic`, atau `openai_compatible`).
2. Masukkan nama model (misalnya `gemini-2.5-flash`, `grok-3-mini`, `gpt-4.1-mini`, atau `claude-3-7-sonnet`).
3. Masukkan API Key pada kolom password (atau saat diminta secara tersembunyi di CLI).
   - *Jaminan Keamanan*: API Key Anda hanya disimpan di memori sesi sementara dan tidak pernah ditulis ke berkas YAML, log, maupun arsip ZIP. Anda dapat mengganti API Key dan model kapan saja di tengah sesi (*hot-swap*).

### Opsi B — Menghubungkan ke **9Router** (Model Tunggal atau Combo 9Router)
Jika Anda menjalankan **9Router** di komputer Anda (`http://localhost:20128`):
1. Pilih provider **`9Router (nine_router)`** dengan Base URL `http://127.0.0.1:20128/v1` dan isi API Key 9Router Anda.
2. Klik **Pindai Model & Combo 9Router** (atau jalankan `discover-models --provider nine_router`).
3. Pilih salah satu model atau pilih langsung **nama Combo 9Router** Anda (misalnya `premium-coding` atau `free-combo`) agar rantai *fallback* 9Router otomatis menangani perpindahan model jika terjadi *rate limit*.

### Opsi C — Menghubungkan ke **Ollama**, **LM Studio**, atau **OpenCode**
1. Pilih konektor runtime lokal yang sedang aktif di laptop Anda:
   - **`Ollama`** (`http://127.0.0.1:11434`)
   - **`LM Studio`** (`http://127.0.0.1:1234/v1`)
   - **`OpenCode`** (`http://127.0.0.1:4096` atau CLI `opencode`)
2. Klik **Deteksi Model Tersedia** (`discover-models`). AMCA akan menampilkan daftar seluruh model yang sudah terpasang di Ollama, LM Studio, atau OpenCode Anda.
3. Pilih model yang diinginkan untuk menjadi otak Agent Utama AMCA.

### Opsi D — Mengunduh Model Lokal ke Laptop (Dijaga oleh Inspeksi Perangkat Keras)
Jika Anda memilih untuk mengunduh model baru ke laptop (`local_model` atau *pull* model baru via Ollama):
1. AMCA **secara otomatis memeriksa spesifikasi perangkat keras laptop Anda terlebih dahulu** (`hardware.py`): kapasitas RAM total & RAM bebas saat ini, ruang disk bebas, jumlah core CPU, serta keberadaan GPU/VRAM.
2. **Jika Spek Laptop Memenuhi Syarat (`ELIGIBLE`)**: AMCA menampilkan rincian spek laptop Anda dan mengaktifkan tombol konfirmasi **Unduh & Gunakan Model Lokal**.
3. **Jika Spek Laptop Tidak Cukup (`REFUSED_INSUFFICIENT_HARDWARE`)**: AMCA **menolak dan memblokir unduhan secara otomatis** agar laptop Anda tidak mengalami *hang/crash*, serta menampilkan alasan kekurangan spek (misalnya RAM bebas kurang dari batas minimum model). Anda dapat beralih memilih model yang lebih ringan, memakai Cloud API Key, atau memakai 9Router.

### Opsi E — Meracik Rantai Fallback Combo Native AMCA (`amca_combo`)
Untuk mencegah pekerjaan terhenti ketika sebuah model kehabisan kuota atau mencapai **batas token (*token limit*)**:
1. Buka pengaturan **Combo & Fallback Chain Builder** (mirip konfigurasi *Combos* di 9Router).
2. Susun urutan model dari **Tier 1** hingga **Tier $N$**, misalnya:
   - **Tier 1**: `gemini / gemini-2.5-pro` (API Key Utama)
   - **Tier 2**: `nine_router / premium-coding` (Combo 9Router)
   - **Tier 3**: `ollama / qwen2.5-coder:7b` (Model Lokal di Laptop)
   - **Tier 4**: `offline_deterministic / builtin-v1` (Cadangan Deterministik Lokal)
3. Saat bekerja, apabila Tier 1 mengalami **limit token (`token_limit_exceeded` / konteks penuh / respons terpotong `finish_reason == "length"`)** atau **batas kuota (`HTTP 429`)**, AMCA otomatis merangkum/mengompaksi konteks percakapan, mencatat log transisi (`FallbackTransitionEvent`), dan melanjutkan tugas menggunakan Tier 2 tanpa kehilangan progres!

---

## 3. Langkah 1 & 2: Merancang Mesin & Menjalankan Verifikasi Formal (Stage 1 & 2)

1. **Sambutan & Klasifikasi Cakupan**:
   - Aplikasi menyapa Anda dengan: ***“Mesin/agent apakah yang Anda ingin buat?”***
   - Jelaskan mesin/agen yang ingin Anda bangun dalam bahasa alami. Contoh:
     > *"Saya ingin membuat sistem mesin analisis teks yang menerima teks masukan, memvalidasi agar teks tidak kosong, menghitung jumlah karakter dan kata secara terpisah, menggabungkan ringkasannya, lalu menghasilkan laporan."*
   - Jika permintaan berada di luar cakupan rekayasa mesin/agen (misalnya meminta resep masakan), AMCA akan menolak secara sopan tanpa membuat YAML.
2. **Peninjauan Draf YAML `amca/v1alpha1` & Asumsi Eksplisit**:
   - AMCA menghasilkan draf YAML bernomor revisi (`rev-1`, `rev-2`, dst.) yang secara eksplisit memuat bagian `assumptions` (asumsi), `limitations` (batasan), dan `unresolvedQuestions` (pertanyaan terbuka).
3. **Pemeriksaan Verifikasi Struktural + Verifikasi Formal Stage 1 & 2**:
   - Setiap draf secara otomatis diperiksa oleh:
     - **Verifier Struktural**: Memeriksa kevalidan skema, komponen allowlist, kecocokan tipe port, dan ketiadaan siklus (DAG).
     - **Stage 1 Formal Verifier**: Membuktikan keterjangkauan sumber-ke-muara (`FO-TOP-01`), konfluensi penjadwalan *Church-Rosser* (`FO-CON-01`), implikasi prasyarat-pascakondisi Hoare $Q_u \supseteq P_v$ (`FO-HOA-01`), pencapaian tujuan (`FO-GOAL-01`), dan keamanan *secret taint* (`FO-SEC-01`).
     - **Stage 2 Formal Verifier**: Memastikan revisi baru tidak melanggar invarian keamanan dari revisi sebelumnya.
4. **Iterasi Revisi Berbasis *Counterexample***:
   - Jika terdapat bukti formal yang gagal (`REFUTED`), AMCA menampilkan **Counterexample Konkret** (misalnya input `"   "` yang lolos dari `input_source` namun melanggar prasyarat `analysis_a` jika `validate_text` dilewati).
   - Klik **Revisi dengan Agent** atau ketik `revisi <instruksi>`. Diagnostik dan *counterexample* otomatis dikirim ke model agar diperbaiki pada revisi berikutnya.

---

## 4. Langkah 3, 4, & 5: Approval A, *On-The-Fly Subworker HITL*, & Approval B

1. **Langkah 3 — Mengunci Spesifikasi (Approval A / `spec_approval`)**:
   - Setelah status menunjukkan **`VERIFIED`** dan Sertifikat Bukti Formal menunjukkan **`PROVED`**, tinjau diagram DAG dan klik **Setujui Spesifikasi (Approval A)** (atau jalankan `approve-spec` di CLI). Revisi tersebut kini terkunci secara kriptografis (SHA-256).
2. **Langkah 4 — Merespons Usulan *Subworker* secara *On-The-Fly* (*Human-in-the-Loop*)**:
   - Saat menyusun rencana konstruksi SDLC Waterfall, jika AMCA mengusulkan pembuatan **Subworker** (misalnya *Independent Formal Test Auditor*), jendela **On-The-Fly Subworker HITL** akan muncul:
     - Anda dapat memilih **Setujui Subworker (`APPROVED`)** lalu memilih model/Combo untuk Subworker tersebut (bisa dari API Key berbeda, **Combo 9Router**, **Ollama**, **LM Studio**, **OpenCode**, atau model lokal yang lulus cek spek laptop).
     - Atau pilih **Tolak Subworker (`DECLINED`)**, sehingga seluruh konstruksi tetap dikerjakan oleh Agent Utama AMCA.
3. **Langkah 5 — Menyetujui Rencana Konstruksi (Approval B / `construction_approval`)**:
   - Tinjau rencana tahapan Waterfall dan direktori tujuan (`artifacts/constructed_projects/<machine_id>-rev<NNN>/`), lalu berikan **Approval B (`construction_approval`)**.

---

## 5. Langkah 6: Konstruksi Proyek, Verifikasi Stage 3 ($G_{\text{code}} \cong G_{\text{yaml}}$), & Handover ZIP

Setelah Approval A dan Approval B aktif, jalankan **Bangun Proyek (`construct`)**:
1. **Pembuatan Paket Python Mandiri**: AMCA menulis kode sumber Python lengkap beserta *runtime pre/postcondition guards* dan unit test ke `artifacts/constructed_projects/<machine_id>-rev<NNN>/`.
2. **Verifikasi Formal Stage 3 (`verify_code_refinement`)**: AMCA mem-parsing AST kode Python yang baru dibuat menggunakan `ast.parse()` untuk membuktikan secara matematis bahwa graf aliran data di dalam kode Python **isomorfik (identik secara struktural)** dengan spesifikasi YAML ($G_{\text{code}} \cong G_{\text{yaml}}$).
3. **Eksekusi Pengujian Nyata**: AMCA menjalankan `compileall` dan suite `unittest` asli milik proyek yang dihasilkan.
4. **Pengemasan Handover ZIP**: Seluruh kode, test, `machine.yaml`, `formal-proof-certificate.json`, `machine-dag.dot`, `README.md`, dan log audit yang telah disanitasi dikemas ke dalam **`<machine_id>-rev<NNN>-handover.zip`** yang siap diunduh dan dijalankan secara mandiri di komputer mana pun.

