# Fase RF-04: Integrasi GUI (`app.py`) & CLI (`cli.py`), Suite Pengujian Tanpa Mocking, dan Sinkronisasi Tiga Buku Panduan

## 1. Integrasi pada Antarmuka CLI (`src/amca_agent/cli.py`)

### 1.1 Di Tengah Alur Sesi Interaktif `_chat(args)`
Pada [`src/amca_agent/cli.py`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/src/amca_agent/cli.py), di dalam fungsi `_record()` atau tepat setelah YAML kandidat dibuat/direvisi/dimuat:
1. Apabila `_check(text)` melempar `SpecificationError` karena `Unknown component '...'` (atau `detect_unregistered_components_in_yaml(text)` menemukan komponen yang belum terdaftar di library):
   - Tampilkan rincian **`[Rencana Komponen Baru Belum Terdaftar]`** kepada user:
     - Daftar `component_id`, port masuk (`inferred_input_ports`), port keluar (`inferred_output_ports`), dan prasyarat/pascakondisi Hoare yang disimpulkan dari graf YAML.
   - Tanyakan persetujuan *Human-in-the-Loop*:
     ```text
     [On-The-Fly Code Agent HITL] YAML ini merencanakan N komponen baru yang belum terdaftar di Library: <daftar_id>.
     Ketik APPROVE_COMPONENTS untuk mengizinkan Agent AMCA mengenerate kode Python komponen tersebut secara on-the-fly, mengaudit AST-nya, dan mendaftarkannya ke Library Komponen (atau tekan Enter untuk menolak):
     ```
   - Jika user mengetik `APPROVE_COMPONENTS` (atau `APPROVE`):
     - Jalankan `synthesize_and_bind_missing_components(plans, harness=harness, problem_statement=args.problem)`.
     - Cetak bukti pendaftaran modul di `src/amca_components/custom/<id>.py` beserta digest SHA-256-nya.
     - Jalankan ulang `_record(...)` secara otomatis sehingga YAML kandidat langsung tervalidasi menjadi **`verified`** dan **`Formal: PROVED`**!
2. Tambahkan juga perintah eksplisit di dalam prompt `amca>`:
   - `synthesize-components` — Memindai YAML aktif untuk komponen yang belum terdaftar dan memicu alur *On-The-Fly Code Agent* jika sebelumnya sempat ditunda.
   - `bind-component <path_ke_file.py> [id]` — Mengikat file komponen Python eksternal (buatan Antigravity/OpenCode/Codex) langsung dari dalam sesi chat.

### 1.2 Subperintah CLI Non-Interaktif Baru
Tambahkan subperintah berikut pada `_parser()` dan `main()` di `src/amca_agent/cli.py`:
1. `bind-component`:
   ```powershell
   $env:PYTHONPATH = "src"
   .\.venv\Scripts\python.exe -m amca_agent.cli bind-component <file.py> [--id <component_id>] [--alias <alias>] [--name <nama>] [--role <deskripsi>] [--output <out.json>]
   ```
   Mengaudit AST file `.py` eksternal, menginferensi/memvalidasi kontrak Hoare, menguji perilaku di sandbox, lalu menyimpannya ke `src/amca_components/custom/<component_id>.py` dan `catalog.json`.
2. `synthesize-missing`:
   ```powershell
   $env:PYTHONPATH = "src"
   .\.venv\Scripts\python.exe -m amca_agent.cli synthesize-missing <spec.yaml> --approve-components [--provider <provider>] [--model <model>] [--output <out.json>]
   ```
   Mendeteksi seluruh komponen belum terdaftar di `<spec.yaml>`, mengenerate kode Python nyatanya melalui *Code Agent*, mengikatnya ke Library Komponen `src/amca_components/`, lalu memverifikasi ulang `<spec.yaml>` hingga berstatus `verified` & `PROVED`.

---

## 2. Integrasi pada Antarmuka Web GUI (`app.py`)

### 2.1 Aturan Penting Penempatan Widget (Menjaga `test_streamlit_app.py`)
Ingat invarian pengujian `tests/integration/test_streamlit_app.py`:
- Saat contoh standar `valid_parallel_analysis.yaml` dimuat dan tidak ada komponen tak terdaftar, urutan widget utama tidak boleh berubah:
  - `app.selectbox[0]` = pilih contoh YAML
  - `app.button[0]` = `Muat contoh ke editor`
  - `app.button[1]` = `Buat YAML dengan agent`
  - `app.button[2]` = `Validasi YAML saat ini`
  - `app.checkbox[0]` = `Saya menyetujui eksekusi mesin ini`

### 2.2 Panel *On-The-Fly Component Synthesis HITL* di Bagian 3 (`app.py`)
Di dalam `_record_version(source)` pada `app.py`:
1. Simpan hasil `detect_unregistered_components_in_yaml(text, st.session_state.problem)` ke `st.session_state.unregistered_plans`.
2. Di **Bagian 3 (`3 · Tinjau, validasi struktural, & verifikasi formal`)**, tepat setelah tombol `Validasi YAML saat ini` (`app.button[2]`):
   - Render blok **hanya jika `st.session_state.unregistered_plans` tidak kosong** (`if st.session_state.get("unregistered_plans"):`):
     - Tampilkan peringatan informatif:
       *"⚡ Terdeteksi N komponen baru di dalam YAML yang belum terdaftar di Library Komponen AMCA."*
     - Tampilkan tabel rencana komponen (`component_id`, `inferred_input_ports`, `inferred_output_ports`, `inferred_preconditions`, `inferred_postconditions`, `role_description`).
     - Tampilkan tombol **`⚡ Setujui & Generate Kode Komponen On-The-Fly (Code Agent) + Daftarkan ke Library`**.
     - Saat diklik, panggil `synthesize_and_bind_missing_components(...)`, panggil `_record_version("on_the_fly_component_synthesis")`, tampilkan kode Python yang berhasil di-generate dan disimpan di `src/amca_components/custom/`, lalu `st.rerun()`!
   - *(Karena blok ini hanya muncul ketika `unregistered_plans` tidak kosong, maka pada saat `valid_parallel_analysis.yaml` dijalankan oleh `test_streamlit_app.py`, tidak ada satu pun widget ekstra yang dirender!)*

### 2.3 Panel Pengikatan Komponen dari Luar (Antigravity / OpenCode / Codex) di Bagian 8 (`app.py`)
Di **Bagian 8 (`8 · Pembuat & Pendaftar Komponen Baru & Library Komponen`)**:
- Tambahkan bagian input kode Python eksternal / path file `.py` untuk mengikat komponen buatan **Antigravity**, **OpenCode**, atau **Codex** melalui `bind_component_from_python_source()`, lengkap dengan tampilan status **Static AST Security Gate** dan lokasi modul di `src/amca_components/custom/`.

---

## 3. Spesifikasi Pengujian Baru Tanpa Mocking (`tests/`)

Buat dua file pengujian otomatis baru yang menguji seluruh fitur secara nyata (tanpa *mock*):

1. **`tests/unit/test_component_library_and_binder.py`**:
   - **Test 1 (`test_external_python_component_binding_and_ast_gate_pass`)**:
     Membuat file `.py` eksternal nyata (simulasi hasil Antigravity/OpenCode/Codex) berisi fungsi pembersih tanda baca / penghitung metrik, mengikatnya dengan `bind_external_component_file()`, memastikan file tersimpan di `src/amca_components/custom/`, terdaftar di `catalog.json`, dan dapat dipanggil melalui `from amca_components import execute_library_component`.
   - **Test 2 (`test_ast_security_gate_rejects_dangerous_imports_and_calls`)**:
     Menguji bahwa kode komponen yang mengimpor `os`, `subprocess`, `socket`, `urllib` atau memanggil `eval()`, `exec()`, `open()` langsung ditolak secara *fail-closed* oleh `audit_component_source_ast()` sebelum pernah dieksekusi.
   - **Test 3 (`test_constructed_project_calls_amca_components_as_library`)**:
     Membangun proyek mesin dengan `build_constructed_project()` dan `verify_and_package_project()`, lalu memverifikasi bahwa `src/constructed_machine/pipeline.py` meng-`import` dari library `amca_components`, arsip `.zip` memuat `src/amca_components/`, Stage 3 AST Proof (`FO-REF-01` & `FO-REF-02`) berstatus `PROVED`, dan `unittest` proyek lulus 100%.

2. **`tests/integration/test_on_the_fly_component_flow.py`**:
   - **Test 1 (`test_mid_flow_unregistered_component_detection_synthesis_and_machine_construction`)**:
     1. User memasukkan problem statement / YAML yang memuat 2 komponen baru yang belum terdaftar di daftar awal (mis. `html_cleaner` dan `sentence_density_analyzer`).
     2. `detect_unregistered_components_in_yaml()` mendeteksi kedua komponen tersebut dan menyimpulkan port serta kontrak Hoare yang klop dengan graf `edges`.
     3. Setelah disetujui (`APPROVE_COMPONENTS`), `synthesize_and_bind_missing_components()` bertindak sebagai *Code Agent* untuk mengenerate kode Python nyata bagi kedua komponen tersebut, mengaudit AST-nya, dan mendaftarkannya ke `src/amca_components/custom/`.
     4. Spesifikasi YAML yang sama diverifikasi ulang dan terbukti langsung mencapai status **`verified`** (struktural) dan **`PROVED`** (Stage 1 Formal Verification: `FO-TOP-01`, `FO-CON-01`, `FO-HOA-01`, `FO-GOAL-01`, `FO-SEC-01`).
     5. Proyek dikonstruksi menjadi paket Python mandiri + Handover `.zip`, lulus **Stage 3 AST Proof (`PROVED`)**, dan ketika dijalankan terhadap input nyata menghasilkan output deterministik dari kedua komponen baru tersebut!
   - **Test 2 (`test_cli_bind_component_and_synthesize_missing_subcommands`)**:
     Menguji subperintah CLI `bind-component` dan `synthesize-missing --approve-components` secara *end-to-end*.

---

## 4. Sinkronisasi Ketiga Buku Panduan (`help/`) & Push ke GitHub

Setelah seluruh kode dan pengujian di atas lulus:
1. Perbarui [`help/USER-MANUAL.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/help/USER-MANUAL.md), [`help/USER-GUIDE.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/help/USER-GUIDE.md), dan [`help/USER-TUTORIAL.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/help/USER-TUTORIAL.md) untuk mendokumentasikan:
   - Arsitektur Library Komponen Kumulatif (`src/amca_components/`),
   - Alur *On-The-Fly Code Agent Component Synthesis* di tengah pembuatan YAML,
   - Cara mengikat komponen buatan luar (Antigravity / OpenCode / Codex) dengan `bind-component`.
2. Salin ketiga file tersebut ke pasangan garis bawahnya:
   ```powershell
   Copy-Item help\USER-MANUAL.md help\USER_MANUAL.md -Force
   Copy-Item help\USER-GUIDE.md help\USER_GUIDE.md -Force
   Copy-Item help\USER-TUTORIAL.md help\USER_TUTORIAL.md -Force
   ```
3. Jalankan verifikasi akhir penuh:
   ```powershell
   $env:PYTHONPATH = "src"
   .\.venv-retest\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
   .\.venv-retest\Scripts\python.exe tools\validate_workflow.py
   ```
4. Pastikan `git status` bersih dari file sementara atau kredensial, lalu *commit* dan *push* ke `origin main` (`https://github.com/elangbijak4/Almudaya-Machine-Construction-Agent-AMCA-Local-Independent-Version.git`).
