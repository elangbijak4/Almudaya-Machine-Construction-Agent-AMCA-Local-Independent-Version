# Rencana Implementasi & Pengujian: Sistem Diagnostik Error Terintegrasi (`v0.5`)

## 1. Tahapan Pengerjaan

### Fase ED-01: Modul Diagnostik Inti (`src/amca_agent/diagnostics.py`)
- Mendefinisikan enum `ErrorOrigin`:
  - `EXTERNAL_SERVICE` (Layanan Eksternal / Gateway / Kuota / Jaringan)
  - `USER_INPUT_FLOW` (Alur Masukan / Spesifikasi Riset / Port / Kontrak Hoare)
  - `CORE_SYSTEM` (Sistem Inti AMCA / I/O Berkas / Bug Internal)
- Mendefinisikan dataclass `DiagnosticReport`.
- Mengimplementasikan fungsi inferensi `diagnose_exception(exc, context="")`.
- Mengimplementasikan fungsi pemformat `format_diagnostic_report_for_markdown()` dan `format_diagnostic_report_for_cli()`.

---

### Fase ED-02: Integrasi Jendela Mengambang (*Fly-Window Modal*) di GUI (`app.py`)
- Mendefinisikan fungsi dialog `@st.dialog("Pemberitahuan Diagnostik Kesalahan", width="large")`:
  - Menampilkan badge kategori, judul masalah, penjelasan logis, daftar tindakan solusi, dan expander detail teknis.
- Menggantikan penanganan error polos `st.error(str(exc))` di seluruh titik kritis `app.py`:
  1. Tombol "Buat YAML dengan agent"
  2. Input chat revisi spesifikasi
  3. Tombol "Validasi YAML saat ini"
  4. Tombol "Bangun Proyek (Construct)"
  5. Pengikatan komponen eksternal (Bagian 8)
- Menyimpan laporan terakhir di `st.session_state.last_error_report` dengan opsi menampilkan kembali (*re-open*) jika ditutup.

---

### Fase ED-03: Integrasi Pelaporan Berstruktur di CLI (`src/amca_agent/cli.py`)
- Menghubungkan pelaporan eksepsi di `cli.py` ke `diagnose_exception()` dan `format_diagnostic_report_for_cli()`.

---

### Fase ED-04: Suite Pengujian Otomatis Tanpa Mocking & Non-Regresi
- Membuat berkas tes baru `tests/unit/test_diagnostics.py`:
  - Menguji diagnosis error 9Router tanpa akun provider (`EXTERNAL_SERVICE`).
  - Menguji diagnosis error kuota / HTTP 429 (`EXTERNAL_SERVICE`).
  - Menguji diagnosis error sintaksis/skema YAML (`USER_INPUT_FLOW`).
  - Menguji diagnosis pelanggaran kontrak Hoare (`USER_INPUT_FLOW`).
  - Menguji diagnosis penolakan gerbang keamanan AST (`USER_INPUT_FLOW`).
  - Menguji diagnosis error sistem internal (`CORE_SYSTEM`).
- Memverifikasi pengujian integrasi GUI `tests/integration/test_streamlit_app.py` tetap lulus 100% tanpa regresi indeks widget.
- Menjalankan seluruh pengujian unit/integrasi (`discover`).
- Menjalankan `tools/validate_workflow.py`.

---

### Fase ED-05: Sinkronisasi 3 Buku Panduan Pengguna (`help/`)
- Memperbarui `help/USER_MANUAL.md`, `help/USER_GUIDE.md`, dan `help/USER_TUTORIAL.md` (beserta salinan tanda hubung) ke versi `0.5.0` untuk mendokumentasikan taksonomi 3 kategori error dan jendela diagnostik *fly-window*.
