# Rencana Teknis & Handover Master: Refaktor Ekosistem Library Komponen & Sintesis Kode *On-The-Fly* (`v0.3`)

## 1. Tujuan Dokumen Ini (Protokol Kontinuitas Lintas-Model / Lintas-Sesi)

Dokumen terstruktur di dalam folder `docs/refactor_component_library_v0.3/` ini dirancang sebagai **cetak biru teknis lengkap (*executable technical blueprint*)** bagi model Gemini atau agen kode mana pun yang melanjutkan pekerjaan apabila sesi mencapai batas token (*token limit*).

Seluruh rancangan di dalam folder ini mematuhi tiga prinsip mutlak proyek **AMCA Local Independent Version**:
1. **Zero-Mocking Mandate**: Dilarang keras menggunakan *mock*, *stub*, *placeholder*, atau `pass` pada kode produksi. Seluruh sintesis kode komponen, audit AST, eksekusi kontrak Hoare, pemanggilan library, dan pembungkusan `.zip` wajib bekerja secara nyata.
2. **Kompatibilitas Mundur 100% (*Non-Regression Invariants*)**: Seluruh **107 pengujian otomatis** yang sudah lulus saat ini wajib tetap lulus pada setiap langkah refaktor.
3. **Keamanan *Fail-Closed* & Sanitasi Rahasia**: Tidak boleh ada API key di dalam repositori atau artefak, dan setiap kode komponen (baik hasil *generate* AI maupun impor eksternal dari Antigravity/OpenCode/Codex) wajib melewati **Static AST Security Gate** sebelum diikat ke Library Komponen.

---

## 2. Daftar Isi Folder Refaktor (`docs/refactor_component_library_v0.3/`)

| Urutan | Nama File | Cakupan Teknis |
| :--- | :--- | :--- |
| **00** | [`00-README-MASTER-HANDOVER-INDEX.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_component_library_v0.3/00-README-MASTER-HANDOVER-INDEX.md) | Indeks utama, invarian sistem yang wajib dijaga, urutan eksekusi refaktor, dan cara memeriksa progres. |
| **01** | [`01-PHASE-RF01-PERSISTENT-COMPONENT-LIBRARY.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_component_library_v0.3/01-PHASE-RF01-PERSISTENT-COMPONENT-LIBRARY.md) | **Poin 3**: Refaktor penyimpanan komponen menjadi paket library Python nyata (`src/amca_components/`) yang terus diperbarui secara kumulatif dan dipanggil langsung sebagai library (`import amca_components`) oleh naskah kode mesin (`pipeline.py`). |
| **02** | [`02-PHASE-RF02-AST-SECURITY-GATE-AND-EXTERNAL-BINDING.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_component_library_v0.3/02-PHASE-RF02-AST-SECURITY-GATE-AND-EXTERNAL-BINDING.md) | **Poin 2**: Mekanisme pendaftaran dan pengikatan (*binding*) komponen kode Python (`.py`) yang dibuat dari luar (Antigravity, OpenCode, Codex) lengkap dengan **Static AST Security Gate** dan uji kontrak Hoare. |
| **03** | [`03-PHASE-RF03-ON-THE-FLY-CODE-AGENT-COMPONENT-SYNTHESIS.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_component_library_v0.3/03-PHASE-RF03-ON-THE-FLY-CODE-AGENT-COMPONENT-SYNTHESIS.md) | **Poin 1**: Alur tengah (*mid-flow*) di mana Agent AMCA merencanakan komponen belum terdaftar di dalam YAML, meminta persetujuan user (HITL), lalu bertindak sebagai **Code Agent** untuk mengenerate kode Python komponen tersebut secara *on-the-fly*, mendaftarkannya ke library, dan membangun mesin nyata. |
| **04** | [`04-PHASE-RF04-UI-CLI-TESTS-AND-DOCUMENTATION-SYNC.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_component_library_v0.3/04-PHASE-RF04-UI-CLI-TESTS-AND-DOCUMENTATION-SYNC.md) | Integrasi antarmuka GUI (`app.py`) dan CLI (`src/amca_agent/cli.py`), spesifikasi pengujian unit/integrasi tanpa mocking, dan pembaruan ketiga buku (`USER_MANUAL.md`, `USER_GUIDE.md`, `USER_TUTORIAL.md`). |

---

## 3. Lingkungan Eksekusi & Invarian yang Tidak Boleh Dilanggar

Sebelum memulai atau melanjutkan fase mana pun, model penerus wajib memperhatikan fakta lingkungan berikut:

1. **Workspace & Perintah Pengujian**:
   - Direktori kerja: `d:\AMCA_Waterfall_Scaffold_v0.2`
   - Interpreter Python pengujian: `.\.venv-retest\Scripts\python.exe` (atau `.\.venv\Scripts\python.exe` pada dokumentasi user)
   - Perintah verifikasi penuh:
     ```powershell
     $env:PYTHONPATH = "src"
     .\.venv-retest\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
     .\.venv-retest\Scripts\python.exe tools\validate_workflow.py
     ```
2. **Invarian Pengujian Kritis yang Wajib Dijaga**:
   - **`tests/unit/test_registry.py`**:
     Menguji bahwa saat `amca.registry` diimpor dalam keadaan bersih (tanpa pemuatan komponen kustom), `component_ids()` mengembalikan tepat 6 komponen inti:
     `("aggregate_results", "analysis_a", "analysis_b", "generate_report", "input_source", "validate_text")`.
     *Aturan*: Komponen tambahan di library kustom dimuat secara eksplisit melalui fungsi sinkronisasi library (`load_component_library()`) pada lapisan `amca_agent` dan dapat di-reset dengan `clear_all_custom_components(persist=False)` pada `setUp`/`tearDown` unit test.
   - **`tests/integration/test_streamlit_app.py`**:
     Menggunakan `streamlit.testing.v1.AppTest` dengan indeks widget tetap pada *main body* `app.py`:
     - `app.selectbox[0]` harus tetap memilih contoh YAML (`Contoh YAML sebagai titik awal`).
     - `app.button[0]` harus tetap tombol `Muat contoh ke editor`.
     - `app.button[1]` harus tetap tombol `Buat YAML dengan agent`.
     - `app.button[2]` harus tetap tombol `Validasi YAML saat ini`.
     - `app.checkbox[0]` harus tetap checkbox `Saya menyetujui eksekusi mesin ini` di Bagian 5.
     *Aturan*: Jika menampilkan modal/tombol persetujuan *On-The-Fly Component Synthesis* pada Bagian 1–3, tombol tersebut hanya boleh dirender secara kondisional (`if st.session_state.pending_missing_components:`) sehingga saat contoh standar dimuat pada `test_streamlit_app.py`, indeks `selectbox[0]`, `button[0..2]`, dan `checkbox[0]` tidak bergeser sama sekali.
   - **`tests/unit/test_windows_user_commands.py`**:
     Setiap contoh perintah PowerShell di `README.md` dan `help/*.md` yang merujuk ke `.venv` wajib diawali titik-garis-miring (`.\.venv\Scripts\python.exe`), tidak boleh menulis `\.venv\Scripts\python.exe`.

---

## 4. Urutan Eksekusi Bertahap (Checklist Progres untuk Model Penerus)

Jika Anda adalah model yang melanjutkan pekerjaan ini, periksa keberadaan file di bawah ini untuk mengetahui fase mana yang sedang berjalan:

- [ ] **Fase RF-01 (Library Komponen Kumulatif `src/amca_components/`)** — Detail di `01-PHASE-RF01-PERSISTENT-COMPONENT-LIBRARY.md`
  - Target file baru: `src/amca_components/__init__.py`, `src/amca_components/contracts.py`, `src/amca_components/builtin.py`, `src/amca_components/loader.py`, `src/amca_components/custom/__init__.py`
  - Target modifikasi: `src/amca_agent/builder.py`, `src/amca_agent/formal_verifier.py`, `src/amca_agent/packager.py`
- [ ] **Fase RF-02 (Audit AST & Pengikatan Komponen Eksternal dari Antigravity/OpenCode/Codex)** — Detail di `02-PHASE-RF02-AST-SECURITY-GATE-AND-EXTERNAL-BINDING.md`
  - Target file baru: `src/amca_agent/component_binder.py`
  - Target modifikasi: `src/amca_agent/custom_components.py`
- [ ] **Fase RF-03 (Sintesis Kode Komponen *On-The-Fly* di Tengah Alur YAML)** — Detail di `03-PHASE-RF03-ON-THE-FLY-CODE-AGENT-COMPONENT-SYNTHESIS.md`
  - Target file baru: `src/amca_agent/component_synthesizer.py`
  - Target modifikasi: `src/amca_agent/provider.py`, `src/amca_agent/harness.py`
- [ ] **Fase RF-04 (Integrasi GUI/CLI, Pengujian Tanpa Mocking, & Buku Panduan)** — Detail di `04-PHASE-RF04-UI-CLI-TESTS-AND-DOCUMENTATION-SYNC.md`
  - Target modifikasi: `app.py`, `src/amca_agent/cli.py`, `help/USER_MANUAL.md`, `help/USER_GUIDE.md`, `help/USER_TUTORIAL.md`
  - Target file pengujian baru: `tests/unit/test_component_library_and_binder.py`, `tests/integration/test_on_the_fly_component_flow.py`
