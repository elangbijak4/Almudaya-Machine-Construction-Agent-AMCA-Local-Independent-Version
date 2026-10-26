# AMCA User Guide (Panduan Operasional Pengguna — Versi Lokal Mandiri)

**Versi Dokumen:** `0.5.0` (Mencakup Baseline `v0.1.0`, Versi Lokal Mandiri `v0.2.0`, Pustaka Komponen Kumulatif `v0.3.0`, Dashboard Dinamis Adaptif `v0.4.0`, dan Sistem Penanganan Error Terpadu & Diagnostik `v0.5.0`) · **Bahasa:** Indonesia  
**Peran Dokumen:** Panduan praktis bagi peneliti dan perekayasa perangkat lunak untuk mengoperasikan AMCA Versi Lokal Mandiri sehari-hari, sekaligus acuan verifikasi fungsional (*Functional Verification Reference*).

---

## 1. Memilih Antarmuka Kerja AMCA (GUI vs. CLI)

AMCA Versi Lokal Mandiri menyediakan dua antarmuka lokal (GUI & CLI) dengan kesetaraan fitur penuh (*feature parity*):

| Kebutuhan Pengguna | Antarmuka GUI (`app.py`) | Antarmuka CLI (`amca_agent.cli`) |
| :--- | :--- | :--- |
| **Mengatur API Key, 9Router, Ollama, LM Studio, OpenCode, atau Model Lokal** | Panel **Preliminary Harness & Combo Setup** di Sidebar / Tab Konfigurasi Awal | `amca_agent.cli chat` (perintah `setup`), `discover-models`, `hardware-check` |
| **Meracik Rantai Fallback Combo (Antisipasi Limit Token / Kuota)** | Tab **Combo & Fallback Chain Builder** (mirip 9Router Combos) | `amca_agent.cli combo-config` atau memilih `--provider nine_router --model <combo>` |
| **Membuat Spesifikasi Mesin dari Bahasa Alami** | Kotak dialog *"Mesin/agent apakah yang Anda ingin buat?"* | `amca_agent.cli chat` |
| **Sintesis Komponen On-The-Fly oleh Code Agent** | Kartu **Sintesis Komponen Baru On-The-Fly** di Bagian 3 (muncul otomatis jika ada komponen tak terdaftar) | `amca_agent.cli chat` (perintah `synthesize` / `approve-components`) atau `synthesize-missing <spec.yaml>` |
| **Mengikat Komponen Eksternal (.py) dari Antigravity / OpenCode / Codex** | Tab **Ikat Berkas Komponen Eksternal (.py)** di Bagian 8 | `amca_agent.cli bind-component --source <file.py>` |
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
1. Pilih provider **`9Router (nine_router)`**.
2. **Ketiadaan Beban API Key**: Seluruh API key model AI (Gemini, Claude, OpenAI, dll.) dikelola di dalam dashboard 9Router. AMCA secara otomatis membaca `Default Key` lokal dari database 9Router di latar belakang, sehingga **Anda tidak perlu mengetikkan API key di AMCA**.
3. **Pemeriksaan Status Real-Time**: AMCA langsung mem-probe port `20128`:
   - Jika aktif, muncul badge hijau `🟢 9Router Aktif`.
   - Jika belum ada akun provider di 9Router, AMCA menyajikan panduan ramah untuk menghubungkan akun di dashboard [http://localhost:20128](http://localhost:20128) menu **Providers**.
4. Klik **Pindai Model & Combo 9Router** dan pilih alias Combo Anda (misal `free-combo`, `premium-coding`) atau model spesifik.

### Opsi C — Menghubungkan ke **Ollama**, **LM Studio**, atau **OpenCode** (Tanpa API Key)
1. Pilih konektor runtime lokal yang sedang aktif di laptop Anda:
   - **`Ollama`** (`http://127.0.0.1:11434`)
   - **`LM Studio`** (`http://127.0.0.1:1234/v1`)
   - **`OpenCode`** (`http://127.0.0.1:4096` atau CLI `opencode`)
2. **Antarmuka Otomatis Tanpa API Key**: AMCA langsung mem-probe ketersediaan port secara real-time dan menampilkan dropdown model yang telah terpasang di laptop Anda. Kolom API key disembunyikan sepenuhnya.
3. Pilih model lokal yang diinginkan untuk menjadi otak Agent Utama AMCA.

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

## 3. Langkah 1 & 2: Katalog Komponen Terdaftar, Batasan Prompt, Pembuatan Komponen Baru, Pengikatan Eksternal, Sintesis On-The-Fly, & Verifikasi Formal

1. **Sajian Katalog Komponen Terdaftar & Panduan Batasan Prompt (Bagian 1 GUI / Perintah `components` CLI)**:
   - Sebelum memasukkan prompt, AMCA menyajikan **Katalog Komponen Terdaftar** yang mencantumkan seluruh komponen yang diizinkan (6 komponen inti bawaan + seluruh komponen kustom yang Anda daftarkan), lengkap dengan port masuk (`in`), port keluar (`out`), kunci konfigurasi (`config_keys`), dan **Kontrak Hoare ($P_c \rightarrow Q_c$)**.
   - **Batasan Prompt (*Prompt Boundaries*)**:
     - YAML hanya dapat merangkai komponen yang terdaftar pada katalog tersebut.
     - Keluaran `input_source` (`text`) wajib divalidasi oleh `validate_text` (atau komponen transformasi kustom yang menjamin `non_empty_trimmed`) sebelum masuk ke komponen analisis (`FO-HOA-01`).
     - Prompt dapat meminta **Mesin Tunggal (`single_machine`)**, **Pipeline Linier (`linear_pipeline`)**, maupun **Graf Nonlinier / DAG Paralel (`nonlinear_dag`)**.
2. **Pembuatan Komponen Deterministik Berbasis Template (*Custom Component Studio* — Bagian 8 GUI / `register-component` CLI)**:
   - Jika Anda membutuhkan kemampuan pemrosesan baru dari template bawaan (misalnya penghitung kalimat `sentence_counter`, pencari kata kunci `keyword_counter`, atau normalisasi huruf `uppercase_normalizer`), buka **Bagian 8 · Pembuat & Pendaftar Komponen Baru** di GUI (atau jalankan `& $PY -m amca_agent.cli register-component --id sentence_counter --role "Menghitung jumlah kalimat dari teks tervalidasi"`).
3. **Pengikatan Berkas Komponen Eksternal dari Antigravity / OpenCode / Codex (`bind-component` CLI / Tab Bagian 8 GUI)**:
   - Jika Anda telah menulis kode komponen Python di luar sistem (misalnya dikembangkan melalui Antigravity, OpenCode, Codex, atau editor teks biasa), Anda dapat langsung mengikatnya ke pustaka AMCA:
     - Melalui CLI: `& $PY -m amca_agent.cli bind-component --source path/to/my_component.py`
     - Melalui GUI: Buka tab **Ikat Berkas Komponen Eksternal (.py)** di Bagian 8, pilih file atau tempel kodenya, lalu klik **Audit Keamanan & Ikat Komponen**.
   - **Gerbang Keamanan AST Otomatis**: Kode eksternal diaudit ketat secara statis sebelum dijalankan. Seluruh modul berbahaya (`os`, `subprocess`, `socket`, `eval`, `exec`) langsung ditolak (*fail-closed*). Kode yang aman dibungkus dengan *runtime Hoare guards*, diuji di sandbox, dan didaftarkan ke `catalog.json` serta `src/amca_components/custom/`.
4. **Sintesis Komponen *On-The-Fly* oleh Code Agent (Di Tengah Alur Chat/YAML)**:
   - Apabila Anda memasukkan prompt yang membutuhkan komponen baru yang belum terdaftar di katalog, Code Agent AMCA:
     1. Merancang kandidat YAML yang memuat nama komponen baru tersebut beserta alur port-nya.
     2. Menjalankan **Propagasi Batasan Hoare Dua Arah** untuk menyimpulkan prasyarat $P_v$ dari node input dan pascakondisi $Q_v$ untuk node penerus.
     3. Menampilkan kartu persetujuan *Human-in-the-Loop* di GUI (Bagian 3) atau prompt konfirmasi di CLI (`amca> synthesize` / `approve-components`).
     4. Menghasilkan kode Python nyata (*on-the-fly*), mengauditnya via Gerbang AST, membungkus kontrak, menguji di sandbox, dan mengikatnya ke pustaka kumulatif.
     5. Memverifikasi ulang kandidat YAML hingga status `verified` dan Sertifikat Bukti Formal menjadi **`PROVED`**.
5. **Sambutan & Klasifikasi Cakupan**:
   - Aplikasi menyapa Anda dengan: ***“Mesin/agent apakah yang Anda ingin buat?”***
   - Jelaskan mesin/agen yang ingin Anda bangun dalam bahasa alami. Contoh:
     > *"Saya ingin membuat sistem mesin analisis teks yang menerima teks masukan, memvalidasi agar teks tidak kosong, menghitung jumlah karakter dan kata secara terpisah, menggabungkan ringkasannya, lalu menghasilkan laporan."*
   - Jika permintaan berada di luar cakupan rekayasa mesin/agen (misalnya meminta resep masakan), AMCA akan menolak secara sopan tanpa membuat YAML.
6. **Peninjauan Draf YAML `amca/v1alpha1` & Asumsi Eksplisit**:
   - AMCA menghasilkan draf YAML bernomor revisi (`rev-1`, `rev-2`, dst.) yang secara eksplisit memuat bagian `assumptions` (asumsi), `limitations` (batasan), dan `unresolvedQuestions` (pertanyaan terbuka).
7. **Pemeriksaan Verifikasi Struktural + Verifikasi Formal Stage 1 & 2**:
   - Setiap draf secara otomatis diperiksa oleh:
     - **Verifier Struktural**: Memeriksa kevalidan skema, komponen allowlist, kecocokan tipe port, dan ketiadaan siklus (DAG).
     - **Stage 1 Formal Verifier**: Membuktikan keterjangkauan sumber-ke-muara (`FO-TOP-01`), konfluensi penjadwalan *Church-Rosser* (`FO-CON-01`), implikasi prasyarat-pascakondisi Hoare $Q_u \supseteq P_v$ (`FO-HOA-01`), pencapaian tujuan (`FO-GOAL-01`), dan keamanan *secret taint* (`FO-SEC-01`).
     - **Stage 2 Formal Verifier**: Memastikan revisi baru tidak melanggar invarian keamanan dari revisi sebelumnya.
8. **Iterasi Revisi Berbasis *Counterexample***:
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
1. **Pembuatan Paket Python Mandiri & Panggilan Pustaka Kumulatif**: AMCA menulis kode sumber Python lengkap (`pipeline.py`). Kode mesin nyata langsung memanggil fungsi-fungsi komponen dari pustaka kumulatif `src/amca_components/` (`from amca_components import run_input_source, ...`), memisahkan logika perakitan dari implementasi komponen.
2. **Verifikasi Formal Stage 3 (`verify_code_refinement`)**: AMCA mem-parsing AST kode Python yang baru dibuat menggunakan `ast.parse()` untuk membuktikan secara matematis bahwa graf aliran data di dalam kode Python **isomorfik (identik secara struktural)** dengan spesifikasi YAML ($G_{\text{code}} \cong G_{\text{yaml}}$).
3. **Eksekusi Pengujian Nyata**: AMCA menjalankan `compileall` dan suite `unittest` asli milik proyek yang dihasilkan.
4. **Pengemasan Handover ZIP Mandiri**: Seluruh kode mesin, tes unit, pustaka kumulatif `src/amca_components/` (beserta `catalog.json`, `contracts.py`, `builtin.py`, dan modul `custom/`), `machine.yaml`, `formal-proof-certificate.json`, `machine-dag.dot`, `README.md`, dan log audit dikemas ke dalam **`<machine_id>-rev<NNN>-handover.zip`** yang siap diekstrak dan dijalankan secara mandiri di mana pun.

---

## 6. Langkah 7: Memahami & Menyelesaikan Kesalahan dengan Jendela Mengambang Diagnostik (*Fly-Window Modal*)

Ketika terjadi kendala operasional, sintaksis, atau koneksi AI, AMCA tidak menampilkan pesan merah mentah yang membingungkan. AMCA menampilkan **Jendela Mengambang Diagnostik (*Fly-Window Modal Overlay*)** yang secara otomatis mengklasifikasikan sumber masalah ke dalam salah satu dari tiga asal:

### 6.1 Mengenali 3 Asal Kesalahan

1. **🌐 Layanan Eksternal / Gateway AI (`EXTERNAL_SERVICE`)**:
   - **Tanda**: Badge berwarna oranye.
   - **Penyebab**: Kegagalan koneksi ke penyedia AI, gateway 9Router lokal belum memiliki kredensial provider aktif (HTTP 404), kuota akun habis / rate-limit (HTTP 429), API Key salah/kedaluwarsa (HTTP 401), atau token overflow.
   - **Solusi**: Ikuti tautan langsung yang tertera di jendela dialog (misalnya membuka dashboard [http://localhost:20128](http://localhost:20128) untuk menghubungkan akun AI), atau beralih ke provider lokal/offline.
2. **📝 Alur Masukan / Spesifikasi Riset (`USER_INPUT_FLOW`)**:
   - **Tanda**: Badge berwarna biru laut.
   - **Penyebab**: Format dokumen YAML tidak valid, port masukan tidak cocok dengan port luaran, pelanggaran kontrak Hoare (misalnya masukan kosong dikirim ke node yang mensyaratkan teks bersih), impor kode Python berbahaya yang ditolak oleh Gerbang Keamanan AST, atau prompt yang di luar cakupan (*out-of-scope*).
   - **Solusi**: Ikuti saran perbaikan spesifikasi yang tertera, sisipkan komponen pembersih teks (`validate_text`), atau hapus pustaka berbahaya dari kode komponen.
3. **⚙️ Sistem Inti AMCA (`CORE_SYSTEM`)**:
   - **Tanda**: Badge berwarna merah tua.
   - **Penyebab**: Masalah sistem lokal di laptop Anda, seperti izin penulisan berkas pada folder `artifacts/` atau ruang penyimpanan disk yang penuh.
   - **Solusi**: Periksa izin direktori atau bersihkan ruang penyimpanan laptop Anda.

### 6.2 Menutup dan Membuka Kembali Jendela Diagnostik

- **Menutup Dialog**: Klik tombol **Tutup Jendela** pada bagian bawah jendela mengambang untuk kembali ke editor atau draf kerja Anda.
- **Membuka Kembali (*Re-open*)**: Jika Anda telah menutup dialog namun ingin membaca kembali instruksi solusi atau rincian teknis, klik tombol **🔍 Buka Jendela Diagnostik** yang selalu tersedia di bagian bawah Sidebar Pengaturan.


