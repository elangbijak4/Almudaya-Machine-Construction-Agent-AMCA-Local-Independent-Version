# AMCA User Manual (Rincian Teknis & Acuan Verifikasi Sistem — Versi Lokal Mandiri)

**Versi Dokumen:** `0.2.0` (Mencakup Baseline `v0.1.0` dan Versi Lokal Mandiri `v0.2.0`)  
**Bahasa:** Indonesia  
**Status:** Kontrak Referensi Teknis & Orakel Verifikasi Implementasi (*Verification Oracle*)

> [!IMPORTANT]
> **Peran Dokumen Ini sebagai Acuan Verifikasi (*Verification Oracle*):**  
> Buku `USER_MANUAL.md` ini, bersama `USER_GUIDE.md` dan `USER_TUTORIAL.md`, merupakan **tolok ukur verifikasi wajib** saat pembangunan aplikasi AMCA selesai. Tim/agen penguji wajib memverifikasi bahwa perilaku aktual aplikasi (GUI, CLI, Harness, Hardware Gate, 9Router/Combo Fallback, Subworker HITL, 3-Stage Formal Verifier, Builder, dan Handover ZIP) **100% konsisten minimal** dengan rincian di ketiga buku ini. Apabila selama implementasi terdapat penambahan fitur baru yang melampaui batas minimal namun tetap konsisten dengan arsitektur ini, maka ketiga buku ini **wajib diperbarui** sebelum gerbang akhir (*Task 7 Gate*) disetujui.

---

## 1. Ikhtisar Sistem & Arsitektur AMCA Versi Lokal Mandiri

**AMCA (*Almudaya Machine Construction Agent* — Local Independent Version)** adalah:
1. **Specialized Agent Harness**: Kerangka kerja (*harness*) orkestrasi agen yang tidak terikat pada satu model AI tunggal (*model-agnostic*). Otak Agent Utama AMCA maupun setiap *Subworker* yang dibuatnya dapat diganti-ganti (*hot-swappable*) menggunakan sembarang Cloud API Key, **9Router** (termasuk **Combo 9Router**), runtime AI lokal (**Ollama**, **LM Studio**, **OpenCode**), model lokal yang diunduh langsung ke laptop (dijaga oleh inspeksi spesifikasi perangkat keras otomatis), atau **Rantai Fallback Combo Native AMCA (`amca_combo`)**.
2. **Compositional 3-Stage Formal Verifier**: Mesin pembuktian matematis dan struktural 3-tahap yang membuktikan kebenaran topologi, konfluensi (*Church-Rosser*), implikasi prasyarat-pascakondisi logika Hoare ($\{P_c\}\;c\;\{Q_c\}$), ketiadaan kebocoran rahasia (*taint non-interference*), pelestarian invarian antar-revisi, hingga **isomorfisme AST kode Python terhadap spesifikasi YAML** ($G_{\text{code}} \cong G_{\text{yaml}}$).
3. **Deterministic Agent/Machine Constructor**: Pembangun proyek perangkat lunak Python mandiri (*standalone runnable Python package*) yang menghasilkan kode sumber, *runtime contract guards*, suite pengujian `unittest`/`pytest` asli, laporan verifikasi, sertifikat bukti formal (`formal-proof-certificate.json`), dan arsip serah-terima **Handover ZIP**.

### 1.1 Karakteristik Arsitektur Lokal Mandiri (`d:\AMCA_Waterfall_Scaffold_v0.2`)

| Aspek Teknis | Spesifikasi Versi Lokal Mandiri |
| :--- | :--- |
| **Paket Python** | `src/amca/` (inti deterministik) + `src/amca_agent/` (Harness, Formal Verifier, Builder, Packager, CLI) + `app.py` (GUI Streamlit) |
| **Tempat Eksekusi UI & CLI** | 100% lokal di laptop (`streamlit run app.py` & `python -m amca_agent.cli`) |
| **Inspeksi Spek Laptop (`hardware.py`)** | Berjalan lokal di `src/amca_agent/hardware.py` (RAM, Disk, CPU, GPU/VRAM) |
| **Koneksi Ollama / LM Studio / OpenCode / 9Router Lokal** | Langsung dari `src/amca_agent/provider.py` ke `127.0.0.1` |
| **Penyimpanan API Key (Primary & Subworker)** | Hanya di memori sesi lokal (`SessionCredentialVault`), tidak pernah ditulis ke disk |
| **Eksekusi 3-Stage Formal Verifier & Builder** | Lokal di `artifacts/constructed_projects/<machine_id>-rev<NNN>/` beserta `<machine_id>-rev<NNN>-handover.zip` |

---

## 2. Batas Keamanan, Anti-Mocking, dan Kebersihan Rahasia (*Triple Secret Hygiene*)

1. **Larangan Mutlak *Mocking* pada Kode Produksi (*Strict Anti-Mocking Mandate*)**:
   - Seluruh modul produksi (`hardware.py`, `harness.py`, `provider.py`, `formal_verifier.py`, `builder.py`, `packager.py`) wajib mengeksekusi algoritma nyata: pembacaan memori/disk OS asli, soket HTTP asli, penelusuran graf BFS/DFS asli, deduksi himpunan predikat Hoare asli, `ast.parse()` asli, eksekusi `compileall` dan `unittest` asli, serta pembuatan arsip `.zip` asli.
2. **Input dan Spesifikasi Dianggap Tidak Tepercaya (*Untrusted Input*)**:
   - Semua prompt pengguna, respons LLM/Subworker, YAML, dan JSON input diperlakukan sebagai data tidak tepercaya.
   - Loader YAML (`_StrictSafeLoader`) menolak YAML *aliases/anchors*, *duplicate keys*, dokumen non-mapping, dan spesifikasi berukuran `> 65.536` byte (64 KiB).
   - Tidak ada penggunaan `eval`, `exec`, `__import__`, atau eksekusi perintah shell arbitrer dari spesifikasi YAML.
3. **Tiga Batas Rahasia (*Triple Secret Boundary*)**:
   - **Rahasia 1 — API Key Agent Utama AMCA (`amca_primary`)**: Hanya disimpan di memori sesi (`SessionCredentialVault`).
   - **Rahasia 2 — API Key Khusus Subworker (`subworker:<id>`)**: Dimasukkan secara *on-the-fly* saat *Human-in-the-Loop (HITL)*, disimpan terpisah dari API key Agent Utama di memori sesi, dan tidak pernah bocor ke log atau disk.
   - **Rahasia 3 — Kredensial Mesin Target (`secretRef`)**: Di dalam dokumen YAML `amca/v1alpha1`, layanan eksternal hanya boleh mendeklarasikan nama variabel lingkungan berhuruf kapital (`secretRef: AMCA_LLM_API_KEY`, pola `^[A-Z][A-Z0-9_]{1,63}$`). Nilai rahasia aktual tidak boleh ada di dalam YAML atau Handover ZIP.

---

## 3. Spesifikasi *Specialized Agent Harness* & 12 Konektor Provider/Runtime

Baik **Agent Utama AMCA (`amca_primary`)** maupun setiap **Subworker (`subworker:<id>`)** menggunakan kontrak pengikatan model `ModelBinding`.

### 3.1 Daftar 12 Tipe Provider (`provider_type`)

| No | `provider_type` | Endpoint / Protokol Default | Mekanisme Koneksi, *Auto-Discovery*, & Keamanan |
| :--- | :--- | :--- | :--- |
| 1 | `gemini` | `https://generativelanguage.googleapis.com` | Google Gemini REST API (`generateContent`), API key di memori sesi. |
| 2 | `xai` | `https://api.x.ai/v1/chat/completions` | xAI Grok REST API, Bearer API key di memori sesi. |
| 3 | `openai` | `https://api.openai.com/v1/chat/completions` | OpenAI Chat Completions API, Bearer API key di memori sesi. |
| 4 | `anthropic` | `https://api.anthropic.com/v1/messages` | Anthropic Messages API (`x-api-key` header di memori sesi). |
| 5 | `openai_compatible` | Custom `base_url` | Endpoint OpenAI-compatible kustom (DeepSeek, Groq, OpenRouter, vLLM, dsb.). |
| 6 | `nine_router` | `http://127.0.0.1:20128/v1` | **Bridge 9Router**: Memanggil `GET /v1/models` untuk mendeteksi model tunggal maupun **alias Combo 9Router** (mis. `premium-coding`, `free-combo`), serta mengirim inferensi ke `/v1/chat/completions` menggunakan API key 9Router. |
| 7 | `ollama` | `http://127.0.0.1:11434` | **Bridge Ollama**: Memanggil `GET /api/tags` untuk mendeteksi model yang terinstal di Ollama; wajib melewati gerbang `hardware.py` sebelum mengizinkan `POST /api/pull` model baru atau memuat model besar; inferensi via `/api/chat` atau `/v1/chat/completions`. |
| 8 | `lm_studio` | `http://127.0.0.1:1234/v1` | **Bridge LM Studio**: Memanggil `GET /v1/models` pada server lokal LM Studio untuk mendeteksi model GGUF aktif/tersedia; memeriksa kecukupan RAM/VRAM via `hardware.py`; inferensi via `/v1/chat/completions`. |
| 9 | `opencode` | `http://127.0.0.1:4096` atau CLI `opencode` | **Bridge OpenCode**: Mendeteksi daftar model yang telah dikonfigurasi di dalam instalasi OpenCode pengguna (`GET /config` / `opencode models`) dan meneruskan prompt melalui server lokal OpenCode atau `opencode run --format json`. |
| 10 | `local_model` | Direktori `artifacts/local_models/` | Unduhan berkas model GGUF lokal langsung ke laptop. **Wajib lulus inspeksi `hardware.py` (`status == "ELIGIBLE"`)** dan persetujuan pengguna sebelum diunduh. |
| 11 | `amca_combo` | Internal `FallbackComboRouter` | **Rantai Fallback Combo Native AMCA** (`Tier 1 -> Tier 2 -> ... -> Tier N`) yang menggabungkan beberapa provider di atas dengan *failover* otomatis saat terjadi limit token atau kuota habis. |
| 12 | `offline_deterministic` | Internal (`src/amca_agent/`) | Synthesizer deterministik berbasis aturan/registri bawaan yang berjalan 100% tanpa koneksi jaringan dan tanpa LLM/API key. |

---

## 4. Inspeksi Spesifikasi Perangkat Keras Laptop (`hardware.py`)

Sebelum model lokal (`local_model`) diunduh ke laptop atau model baru ditarik melalui `ollama` / `lm_studio`, modul `hardware.py` menjalankan inspeksi sistem operasi secara nyata (*real-time*):

1. **Metrik yang Diperiksa**:
   - `ram_total_mb` & `ram_available_mb`: Melalui `ctypes.windll.kernel32.GlobalMemoryStatusEx` pada Windows, `/proc/meminfo` pada Linux, atau `vm_stat`/`sysctl` pada macOS.
   - `disk_free_mb`: Melalui `shutil.disk_usage` pada partisi target penyimpanan model.
   - `cpu_logical_cores` & `cpu_arch`: Melalui `os.cpu_count()` dan `platform.machine()`.
   - `gpu_detected` & `gpu_vram_mb`: Deteksi akselerator GPU/VRAM jika tersedia.
2. **Keputusan Gerbang (*Fail-Closed Gate*)**:
   - **`ELIGIBLE`**: Jika `ram_available_mb >= min_ram_available_mb`, `disk_free_mb >= min_disk_free_mb` ($\ge 1.5\times$ ukuran unduhan), dan syarat GPU terpenuhi. Tombol/perintah unduh diaktifkan setelah konfirmasi pengguna.
   - **`REFUSED_INSUFFICIENT_HARDWARE`**: Jika salah satu syarat tidak terpenuhi. **Unduhan ditolak secara otomatis dan keras (*blocked*)**, disertai laporan defisit perangkat keras secara rinci (mis. *"Available RAM (5800 MB) is below the model minimum requirement (6144 MB)"*).

---

## 5. Protokol Rantai Fallback Combo & Penanganan Limit Token (`FallbackComboRouter`)

AMCA menyediakan ketahanan berlapis terhadap masalah habisnya kuota atau batas token melalui dua jalur yang dapat dikombinasikan:
1. **Delegasi ke Combo 9Router (`provider_type: "nine_router"`)**: Memilih nama Combo yang sudah dikonfigurasi di dashboard 9Router (`http://localhost:20128`).
2. **Konfigurasi Combo Native AMCA (`provider_type: "amca_combo"`)**: Menyusun urutan prioritas **Tier 1 $\to$ Tier 2 $\to \dots \to$ Tier $N$** langsung di antarmuka AMCA (GUI maupun CLI).

### 5.1 Kondisi Pemicu *Failover* Otomatis (`trigger_reason`)
`FallbackComboRouter` di dalam `harness.py` memindahkan eksekusi dari **Tier $k$** ke **Tier $k+1$** secara otomatis apabila Tier $k$ mengalami:
- **`token_limit_exceeded`**: Jumlah token prompt + output melampaui *context window* model (`context_length_exceeded`, `max_tokens` overflow) atau mencapai batas *Tokens Per Minute (TPM)* / *Tokens Per Day (TPD)*.
- **`output_truncated_length`**: Output model terpotong karena `finish_reason == "length"`, menyebabkan blok YAML atau kode tidak selesai.
- **`rate_limit_429`**: Provider mengembalikan status `HTTP 429 Too Many Requests` atau `RESOURCE_EXHAUSTED`.
- **`quota_or_credit_exhausted`**: Provider menolak permintaan karena saldo/kuota API key habis (`insufficient_quota`).
- **`upstream_unavailable`**: Gangguan server `HTTP 500/502/503/504` atau koneksi *timeout*.

### 5.2 Prosedur Kompaksi Konteks & Audit Transisi
Saat pemicunya adalah `token_limit_exceeded` atau `output_truncated_length`:
1. AMCA menjalankan **Smart Token-Limit Context Compaction**: menyusun payload ringkas yang mempertahankan (a) YAML `amca/v1alpha1` revisi terakhir, (b) daftar alasan penolakan verifier / *counterexample* formal terakhir, dan (c) instruksi pengguna saat ini, sambil memangkas riwayat percakapan lama yang boros token.
2. AMCA mencatat objek **`FallbackTransitionEvent`** (berisi `combo_id`, `from_tier`, `to_tier`, `trigger_reason`, `context_compacted`, dan `timestamp`—tanpa membocorkan API key).
3. AMCA langsung mengirim permintaan yang telah dikompaksi ke **Tier $k+1$**.

---

## 6. Protokol *On-The-Fly Subworker Human-in-the-Loop (HITL)*

Secara default, perencana kerja AMCA (`planner.py`) mengutamakan efisiensi biaya satu agen (`policy: minimize-cost`, `useSubagents: false`). Namun ketika kompleksitas sistem mesin memerlukan pekerja spesialis tambahan (**Subworker**, misalnya `subworker:spec_auditor` atau `subworker:test_reviewer`):

1. **Penjedaan Eksekusi (*HITL Pause*)**:
   - Eksekusi berhenti sejenak dan menampilkan **Antarmuka *On-The-Fly Subworker HITL*** di GUI atau CLI (pada Edisi Cloud, sesi berubah ke status `AWAITING_SUBWORKER_HITL`).
2. **Informasi yang Ditampilkan kepada Pengguna**:
   - ID & Peran Subworker (`role`), deskripsi tugas (`task_description`), serta alasan biaya/manfaat (`rationale`).
3. **Input Persetujuan & API Key Independen dari Pengguna**:
   - **Setuju (`APPROVED`)**: Pengguna memilih provider/model untuk Subworker tersebut (bisa berupa Cloud API berbeda, **Combo 9Router**, model di **Ollama / LM Studio / OpenCode**, **Combo Native AMCA**, atau model lokal yang lulus `hardware.py`) dan **memasukkan API Key khusus untuk Subworker tersebut** (yang disimpan terpisah dari API Key Agent Utama).
   - **Tolak (`DECLINED`)**: AMCA membatalkan pembuatan Subworker dan menyelesaikan seluruh tugas menggunakan **Agent Utama AMCA** saja.

---

## 7. Model Spesifikasi (`v1.0` & `amca/v1alpha1`) dan Kontrak Formal Hoare

AMCA mendukung dua format spesifikasi yang saling kompatibel:
1. **Format Inti (`schema_version: "1.0"`)**: Digunakan oleh `src/amca/` dengan `machine_id`, `nodes`, dan `edges`.
2. **Format Konstruktor Sistem (`apiVersion: amca/v1alpha1`, `kind: MachineSystem`)**: Digunakan oleh konstruktor agen lengkap dengan `metadata`, `intent`, `machines`, `connections`, `environment`, `securityPolicy`, `construction`, `assumptions`, `limitations`, dan `unresolvedQuestions`.

### 7.1 Registri Komponen, Alias, dan Kontrak Hoare ($\{P_c\}\;c\;\{Q_c\}$)

| ID Kanonis `v1.0` | Alias `v1alpha1` | Port Input & Prasyarat Formal ($P_c$) | Port Output & Pascakondisi Formal ($Q_c$) | Murni (*Pure*) |
| :--- | :--- | :--- | :--- | :--- |
| `input_source` | `text.input` | **Config**: `input_key`<br/>**Pre**: $\text{env\_has\_nonempty\_str}(\text{input\_key})$ | `text: string`<br/>**Post**: $\{\text{is\_str}, \text{non\_empty\_raw}\}$ | Ya |
| `validate_text` | `text.validate` | `text: string`<br/>**Pre**: $\{\text{is\_str}\}$ | `text: string`<br/>**Post**: $\{\text{is\_str}, \text{non\_empty\_trimmed}, \text{len\_ge\_1}\}$ | Ya |
| `analysis_a` | `text.char_count` | `text: string`<br/>**Pre**: $\{\text{is\_str}, \text{non\_empty\_trimmed}\}$ | `finding: object`<br/>**Post**: $\{\text{is\_obj}, \text{has\_nonneg\_int:character\_count}\}$ | Ya |
| `analysis_b` | `text.word_count` | `text: string`<br/>**Pre**: $\{\text{is\_str}, \text{non\_empty\_trimmed}\}$ | `finding: object`<br/>**Post**: $\{\text{is\_obj}, \text{has\_nonneg\_int:word\_count}\}$ | Ya |
| `aggregate_results` | `text.summarize` | `finding_a: object` ($\{\text{is\_obj}, \text{has\_nonneg\_int:character\_count}\}$)<br/>`finding_b: object` ($\{\text{is\_obj}, \text{has\_nonneg\_int:word\_count}\}$) | `summary: string`<br/>**Post**: $\{\text{is\_str}, \text{formatted\_metrics\_summary}\}$ | Ya |
| `generate_report` | `report.assemble` | `summary: string`<br/>**Pre**: $\{\text{is\_str}, \text{formatted\_metrics\_summary}\}$ | `report: object`<br/>**Post**: $\{\text{is\_obj}, \text{report\_contains\_summary}\}$ | Ya |

> **Catatan Referensi Perilaku Deterministik:** Untuk berkas contoh `examples/valid_parallel_analysis.yaml` dengan masukan `examples/reference-input.json` (`{"text": "AMCA builds a graph."}`), hasil eksekusi wajib menghasilkan ringkasan `characters=20; words=4`.

---

## 8. Mesin Verifikasi Formal 3-Tahap (`formal_verifier.py`)

Selain 10 pemeriksaan struktural pada `verify_candidate` (`src/amca/verifier.py`), AMCA menjalankan **Verifikasi Formal 3-Tahap** dan menerbitkan **`formal-proof-certificate.json`**:

### 8.1 Stage 1 — Pembuktian Tingkat Spesifikasi (`verify_formal_spec`)
Dijalankan pada setiap revisi draf YAML:
1. **`FO-TOP-01` (*Source-to-Sink Reachability & Deadlock Freedom*)**: Menggunakan BFS/DFS maju dan mundur untuk membuktikan setiap node berada pada jalur valid dari node sumber (`input_source`) ke node muara (`generate_report`) dan tidak ada node buntu.
2. **`FO-CON-01` (*Schedule Confluence / Church-Rosser*)**: Membuktikan bahwa untuk semua urutan pengurutan topologis $S_1, S_2$ yang valid pada DAG bercabang, hasil eksekusi identik secara deterministik karena setiap port input tujuan memiliki tepat satu sumber (`in-degree == 1`) dan setiap komponen bersifat murni (*pure*) dengan himpunan tulis yang saling lepas.
3. **`FO-HOA-01` (*Compositional Hoare Pre/Postcondition Entailment*)**: Untuk setiap sisi berarah $e = (u.\text{out} \to v.\text{in})$, membuktikan secara simbolik bahwa pascakondisi $Q_u(\text{out})$ mengimplikasikan prasyarat $P_v(\text{in})$ ($Q_u(\text{out}) \supseteq P_v(\text{in})$).
   - *Contoh Penolakan Formal*: Jika pengguna menghubungkan `input_source.text` langsung ke `analysis_a.text` tanpa melewati `validate_text`, pemeriksaan tipe port biasa lulus (`string -> string`), tetapi **`FO-HOA-01` menggagalkannya (`REFUTED`)** karena $\{\text{is\_str}, \text{non\_empty\_raw}\} \not\supseteq \{\text{is\_str}, \text{non\_empty\_trimmed}\}$ dan menghasilkan *counterexample* konkret (`"   "` — string berisi spasi saja).
4. **`FO-GOAL-01` (*Acceptance Criteria Goal Entailment*)**: Membuktikan bahwa gabungan pascakondisi di sepanjang jalur DAG memenuhi seluruh `formalGoal` pada `intent.acceptanceCriteria`.
5. **`FO-SEC-01` (*Security & Secret Taint Non-Interference*)**: Membuktikan bahwa kebijakan keamanan bernilai `deny-by-default`, `operatingSystemCommands: deny`, `secretPolicy: references-only`, dan tidak ada `secretRef` yang mengalir ke port output laporan publik.

### 8.2 Stage 2 — Pembuktian Tingkat Evolusi Revisi (`verify_revision_invariants`)
Dijalankan saat membandingkan revisi `rev-N` dengan `rev-(N+1)` untuk membuktikan bahwa invarian keamanan dan kontrak input/output yang telah disetujui tidak mengalami regresi.

### 8.3 Stage 3 — Pembuktian Tingkat Penyempurnaan Kode / AST (`verify_code_refinement`)
Dijalankan setelah `builder.py` menghasilkan proyek Python di disk:
1. **`FO-REF-01` (*Code-to-YAML Graph Isomorphism* — $G_{\text{code}} \cong G_{\text{yaml}}$)**: Mem-parsing kode Python hasil konstruksi menggunakan `ast.parse()`, mengekstrak graf ketergantungan pemanggilan komponen $G_{\text{code}}$, dan membuktikan kesamaan tepat terhadap $G_{\text{yaml}}$ (`nodes(G_code) == nodes(G_yaml)` dan `edges(G_code) == edges(G_yaml)`).
2. **`FO-REF-02` (*Runtime Contract Guard Presence*)**: Memeriksa AST dari setiap modul komponen yang dihasilkan untuk memastikan adanya pemeriksaan `assert`/guard prasyarat dan pascakondisi saat runtime.

---

## 9. Siklus Persetujuan Ganda (*Two-Stage Approval*) & Artefak Handover

Tidak ada proyek yang dapat dibangun atau dijalankan tanpa melewati gerbang persetujuan manusia secara berurutan:
1. **Approval A (`spec_approval`)**: Hanya dapat diberikan jika status struktural `verified` **DAN** status Stage 1 Formal Verification `PROVED`. Mengunci nomor revisi, `specification_sha256`, dan `certificate_sha256`.
2. **Approval HITL Subworker (`subworker_hitl_approval`)** *(jika Subworker diusulkan)*: Mengunci keputusan pengguna (`APPROVED` beserta metadata model/Combo terisolasi, atau `DECLINED`).
3. **Approval B (`construction_approval`)**: Mengikat ke `spec_approval` dan mengizinkan pembuatan berkas proyek di dalam `artifacts/constructed_projects/<machine_id>-rev<NNN>/`.
4. **Arsip Serah-Terima (`<machine_id>-rev<NNN>-handover.zip`)**: Berisi kode sumber Python mandiri, `machine.yaml`, `formal-proof-certificate.json`, `machine-dag.dot`, catatan persetujuan, laporan hasil uji `unittest`, `README.md`, dan `construction-log.jsonl` (yang telah disanitasi dari semua rahasia).

---

## 10. Referensi Antarmuka GUI & Perintah CLI Lengkap

### 10.1 Pemasangan Lingkungan (Windows PowerShell, CPython 3.12+)

```powershell
py -3.12 -m venv .venv
$PY = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $PY)) { throw "Virtual environment not found. Run: py -3.12 -m venv .venv" }
& $PY -m pip install -r requirements-app.txt
$env:PYTHONPATH = "src"
```
*(Untuk CLI inti tanpa Streamlit, gunakan `requirements-dev.txt`).*

### 10.2 Perintah CLI Inti (`amca.cli` — Baseline `v0.1.0`)
- `& $PY -m amca.cli validate <spec.yaml>`
- `& $PY -m amca.cli verify <spec.yaml>`
- `& $PY -m amca.cli run <spec.yaml> --inputs <input.json> [--output <record.json>]`
- `& $PY -m amca.cli report <record.json>`

### 10.3 Perintah CLI Agent & Konstruktor Lokal (`amca_agent.cli` — Edisi 1)
- **Pengaturan Harness, Hardware Check, & Combo**:
  - `& $PY -m amca_agent.cli hardware-check [--model <model_id>]` — Menjalankan inspeksi RAM, Disk, CPU, dan GPU laptop serta mengevaluasi kelayakan model lokal (`ELIGIBLE` / `REFUSED_INSUFFICIENT_HARDWARE`).
  - `& $PY -m amca_agent.cli discover-models --provider <nine_router|ollama|lm_studio|opencode> [--base-url <url>]` — Memindai model atau Combo yang tersedia di 9Router, Ollama, LM Studio, atau OpenCode.
  - `& $PY -m amca_agent.cli combo-config` — Menyusun rantai fallback Combo Native AMCA (`Tier 1 -> Tier 2 -> ... -> Tier N`).
- **Katalog Komponen Terdaftar, Batasan Prompt, & Pendaftaran Komponen Baru**:
  - `& $PY -m amca_agent.cli components [--json] [--output <path>]` — Menampilkan **Katalog Komponen Terdaftar & Panduan Batasan Prompt** (mencakup 6 komponen inti bawaan + seluruh komponen kustom yang telah didaftarkan beserta port masuk/keluar, kunci konfigurasi, prasyarat/pascakondisi Hoare, dan aturan batasan prompt untuk Mesin Tunggal, Pipeline Linier, maupun Graf Nonlinier).
  - `& $PY -m amca_agent.cli register-component --id <component_id> [--alias <alias>] [--name <nama>] [--role <deskripsi>] [--template text_transform|text_metric_object|text_metric_string|dual_finding_combiner|report_packager] [--mode <mode>]` — Membuat dan mendaftarkan komponen deterministik baru ke Registry AMCA (`artifacts/custom_components/custom_registry.json`), lengkap dengan kontrak Hoare dan generator kode AST Stage 3.
  - `& $PY -m amca_agent.cli unregister-component --id <component_id>` — Menghapus komponen kustom dari registry (6 komponen inti bawaan tidak dapat dihapus atau ditimpa).
- **Contoh, Validasi, Verifikasi Formal, & Graf**:
  - `& $PY -m amca_agent.cli examples`
  - `& $PY -m amca_agent.cli example valid_parallel_analysis --output machine.yaml`
  - `& $PY -m amca_agent.cli validate machine.yaml` *(exit code `0` = verified, `1` = ditolak, `2` = error input/operasional)*
  - `& $PY -m amca_agent.cli formal-verify machine.yaml --output formal-proof-certificate.json`
  - `& $PY -m amca_agent.cli graph machine.yaml --output machine-dag.dot`
- **Sesi Interaktif Pembuatan & Konstruksi Mesin (`chat`)**:
  - `& $PY -m amca_agent.cli chat [--provider <provider>] [--model <model_or_combo>] [--example <name>] [--session <id>]`
  - Perintah di dalam prompt interaktif `amca>`:
    - `components` — Menampilkan tabel **Katalog Komponen Terdaftar & Panduan Batasan Prompt** secara langsung di dalam sesi chat.
    - `register-component <id> <deskripsi>` — Mendraft dan mendaftarkan komponen baru secara langsung dari sesi interaktif.
    - `setup` — Membuka pengaturan *Preliminary Harness* / mengganti provider, API key, 9Router Combo, atau AMCA Combo secara *on-the-fly*.
    - `hardware` — Menampilkan status spesifikasi perangkat keras laptop saat ini.
    - `show` — Menampilkan YAML revisi aktif.
    - `validate` — Menjalankan verifikasi struktural + Stage 1 & 2 Formal Verification.
    - `proof` — Menampilkan rincian `formal-proof-certificate.json` beserta *counterexample* (jika ada).
    - `revisi <instruksi>` — Meminta revisi YAML (secara otomatis menyertakan diagnostik struktural & *counterexample* formal).
    - `versions` / `restore <n>` / `load <path.yaml>` — Mengelola riwayat versi YAML yang *immutable*.
    - `approve-spec` — Mencatat **Approval A (`spec_approval`)** (meminta ketikan konfirmasi `APPROVE_SPEC`).
    - `plan` — Menampilkan rencana konstruksi SDLC Waterfall dan usulan Subworker (jika ada, memicu prompt **On-The-Fly Subworker HITL**).
    - `approve-construction` — Mencatat **Approval B (`construction_approval`)** (meminta ketikan konfirmasi `APPROVE_CONSTRUCTION`).
    - `construct` — Membangun proyek Python mandiri di `artifacts/constructed_projects/`, menjalankan Stage 3 AST Isomorphism (`FO-REF-01`, `FO-REF-02`), `compileall`, `unittest`, dan membuat `<machine_id>-rev<NNN>-handover.zip`.
    - `run <input.json>` — Menjalankan mesin pada input JSON setelah mengetik konfirmasi persis `RUN`.
    - `quit` — Menyimpan sesi dan keluar.
- **Manajemen Sesi, Artefak, & Konstruksi Non-Interaktif**:
  - `& $PY -m amca_agent.cli construct <spec.yaml> --approve-spec --approve-construction [--profile minimize_cost|balanced|maximize_capability]`
  - `& $PY -m amca_agent.cli sessions`
  - `& $PY -m amca_agent.cli artifacts [--show <run_or_build_id>]`
  - `& $PY -m amca_agent.cli show <path>`

---

## 11. Batas Kuantitatif & Parameter Keamanan Sistem

| Parameter | Nilai Batas / Ambang | Titik Penegakan |
| :--- | :--- | :--- |
| **Ukuran maksimum spesifikasi YAML** | `65.536` byte (64 KiB) | `specification.py` & `system_spec.py` |
| **Jumlah maksimum mesin / node per sistem** | `1` s/d `64` mesin | `schema.py` & `system_spec.py` |
| **Jumlah maksimum koneksi / edge per sistem** | `0` s/d `128` koneksi | `schema.py` & `system_spec.py` |
| **Ukuran maksimum `config` per mesin** | `16.384` byte JSON kanonis (16 KiB) | `schema.py` & `system_spec.py` |
| **Panjang maksimum prompt pengguna per giliran** | `8.000` karakter; maks `8` giliran terakhir di konteks | `provider.py` & `intent.py` |
| **Batas waktu HTTP LLM & ukuran respons** | `45` detik timeout; maks `1.000.000` byte (1 MB) | `provider.py` & `harness.py` |
| **Ambang aman perangkat keras model lokal** | RAM Tersedia $\ge$ `min_ram_available_mb`; Disk Bebas $\ge$ `min_disk_free_mb` ($\ge 1.5\times$ ukuran model) | `hardware.py` |
| **Direktori tujuan konstruksi yang diizinkan** | Hanya di dalam `artifacts/constructed_projects/<machine_id>-rev<NNN>/` | `builder.py` (`Path.resolve()`) |
| **Maksimum berkas per proyek hasil konstruksi** | `64` berkas; maks `1.048.576` byte (1 MiB) per berkas | `builder.py` & `packager.py` |
| **Ukuran maksimum arsip Handover ZIP** | `10.485.760` byte (10 MiB) | `packager.py` |

---

## 12. Matriks Konsistensi Verifikasi Akhir (*Verification Oracle Checklist*)

Saat aplikasi selesai dibangun, verifikator wajib mencentang seluruh butir berikut terhadap implementasi nyata:
- [x] **VO-01**: Antarmuka Pendahuluan (*Preliminary Harness Setup*) tersedia di GUI dan CLI serta mendukung pergantian *on-the-fly* antar Cloud API, **9Router** (`nine_router`), **Ollama** (`ollama`), **LM Studio** (`lm_studio`), **OpenCode** (`opencode`), **Model Lokal** (`local_model`), **Combo Native AMCA** (`amca_combo`), dan **Offline Deterministic**.
- [x] **VO-02**: `hardware.py` membaca RAM, Disk, CPU, dan GPU asli dari OS laptop dan menolak unduhan (`REFUSED_INSUFFICIENT_HARDWARE`) bila spesifikasi di bawah ambang model.
- [x] **VO-03**: `FallbackComboRouter` terbukti melakukan *failover* otomatis dari Tier $k$ ke Tier $k+1$ saat terjadi `token_limit_exceeded`, `finish_reason == "length"`, atau `HTTP 429`, serta mencatat `FallbackTransitionEvent` tanpa membocorkan API key.
- [x] **VO-04**: Saat Subworker diusulkan, muncul prompt *On-The-Fly Subworker HITL* yang mengizinkan pemasukan API key/model/Combo berbeda untuk Subworker atau jatuh kembali (*fallback*) ke Agent Utama bila ditolak.
- [x] **VO-05**: `formal_verifier.py` menjalankan pembuktian nyata Stage 1 (`FO-TOP-01`, `FO-CON-01`, `FO-HOA-01`, `FO-GOAL-01`, `FO-SEC-01`), Stage 2 (invarian revisi), dan Stage 3 (`ast.parse()` isomorfisme $G_{\text{code}} \cong G_{\text{yaml}}$ `FO-REF-01` & guard `FO-REF-02`) serta menerbitkan `formal-proof-certificate.json`.
- [x] **VO-06**: Seluruh perintah CLI dan alur GUI yang tertulis di `USER_MANUAL.md`, `USER_GUIDE.md`, dan `USER_TUTORIAL.md` berjalan sesuai dokumentasi, dan setiap penambahan fitur baru telah disinkronkan kembali ke ketiga buku ini.
