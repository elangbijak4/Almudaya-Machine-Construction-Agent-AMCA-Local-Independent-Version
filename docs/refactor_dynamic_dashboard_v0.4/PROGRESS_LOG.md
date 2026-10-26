# Formal Continuation Ledger — Refaktor Dashboard Dinamis (`v0.4`)

Dokumen ini mencatat progres formal untuk setiap langkah penyelesaian masalah dashboard dinamis. Apabila pengerjaan terhenti sewaktu-waktu karena batas token (*token limit*), model AI penerus wajib melanjutkan dari fase pertama yang berstatus `IN_PROGRESS` atau `PENDING`.

## Status Ringkas Fase Refaktor

| ID Fase | Nama Fase | Status | Target Berkas & Hasil Pengujian |
| :--- | :--- | :--- | :--- |
| **RF-00** | Penyusunan Rencana Teknis & Cetak Biru Dashboard Dinamis | `COMPLETED` | Folder `docs/refactor_dynamic_dashboard_v0.4/` (4 berkas dokumen) |
| **RF-01** | Helper Runtime Status Probe (`src/amca_agent/provider.py`) | `COMPLETED` | `inspect_provider_runtime_status()` aktif & teruji (9Router, Ollama, LM Studio, OpenCode) |
| **RF-02** | Refaktor Antarmuka Sidebar Dinamis (`app.py`) | `COMPLETED` | Kartu adaptif per kategori, auto-detect 9Router key, eliminasi kolom membingungkan |
| **RF-03** | Eksekusi Test Suite & Verifikasi Streamlit AppTest | `COMPLETED` | 116/116 unit & integration tests PASS (`OK`), zero widget regression |
| **RF-04** | Sinkronisasi 3 Buku Panduan Pengguna (`help/`) | `COMPLETED` | Seluruh 6 file panduan di `help/` diselaraskan ke v0.4.0 & lulus lint PowerShell |

---

## Log Riwayat Langkah Demi Langkah

### [2026-10-26T14:41:00+07:00] `RF-00` — COMPLETED
- Membuat direktori kerja baru `docs/refactor_dynamic_dashboard_v0.4/`.
- Menyusun 4 berkas cetak biru teknis lengkap:
  1. [`00-README-DYNAMIC-DASHBOARD-INDEX.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_dynamic_dashboard_v0.4/00-README-DYNAMIC-DASHBOARD-INDEX.md)
  2. [`01-SPEC-DYNAMIC-PROVIDER-CARDS.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_dynamic_dashboard_v0.4/01-SPEC-DYNAMIC-PROVIDER-CARDS.md)
  3. [`02-TUTORIAL-PROVIDER-UI-FLOWS.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_dynamic_dashboard_v0.4/02-TUTORIAL-PROVIDER-UI-FLOWS.md)
  4. [`03-IMPLEMENTATION-AND-TESTING-PLAN.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_dynamic_dashboard_v0.4/03-IMPLEMENTATION-AND-TESTING-PLAN.md)
- Dokumen siap dieksekusi ke kode produksi.

### [2026-10-26T14:43:00+07:00] `RF-01` & `RF-02` — COMPLETED
- **`src/amca_agent/provider.py`**:
  - Menambahkan fungsi `inspect_provider_runtime_status(provider, base_url)` untuk mem-probe status gateway/runtime lokal secara real-time dan memeriksa jumlah akun aktif serta combo di SQLite 9Router.
  - Memperbaiki penanganan `_post()` agar menampilkan rincian error dari server (`detail`) alih-alih hanya kode HTTP numerik.
- **`app.py`**:
  - Merefaktor sidebar pengaturan provider menjadi **Dashboard Dinamis Adaptif**:
    - **9Router**: Menampilkan badge status real-time, panduan edukatif jika belum ada akun terhubung, dropdown model/combo terdeteksi, dan menyembunyikan kolom API key ke expander opsional (Default Key otomatis digunakan).
    - **Cloud API (Gemini/dsb)**: Menampilkan rekomendasi model riset + kolom API key aman dengan badge penyimpanan RAM memori sesi saja.
    - **Ollama / LM Studio / OpenCode**: Menampilkan badge status probe port real-time + dropdown model lokal yang terpasang di laptop periset (tanpa kolom API key).
    - **Local Model (GGUF)**: Menampilkan panel inspeksi spesifikasi laptop (`hardware.py`) dan keputusan kelayakan gerbang perangkat keras.
    - **AMCA Combo**: Pembangun rantai fallback interaktif tahan batas token.
    - **Offline Deterministic**: Banner mode Air-Gapped 100% lokal, tanpa konfigurasi jaringan.

### [2026-10-26T14:44:00+07:00] `RF-03` — COMPLETED
- Menambahkan test baru `test_inspect_provider_runtime_status_returns_structured_diagnostics` pada `tests/unit/test_agent_provider.py`.
- Memverifikasi `tests/integration/test_streamlit_app.py` lulus 100% tanpa pergeseran indeks widget bodi utama.
- Menjalankan verifikasi penuh: **116 dari 116 tests PASS (`OK`)** dalam 8.37 detik.
- Validasi alur kerja: `python tools/validate_workflow.py` -> **PASS**.

### [2026-10-26T14:46:00+07:00] `RF-04` — COMPLETED
- Seluruh 6 file dokumentasi di `help/` (`USER_MANUAL.md`, `USER-MANUAL.md`, `USER_GUIDE.md`, `USER-GUIDE.md`, `USER_TUTORIAL.md`, `USER-TUTORIAL.md`) telah disinkronkan ke versi `0.4.0`.
- Memperbarui panduan operasional agar periset memahami alur otomatisasi 9Router, peniadaan kolom key untuk runtime lokal (Ollama/LM Studio), dan opsi Cloud API langsung.
- Lulus uji kepatuhan PowerShell path `tests/unit/test_windows_user_commands.py`.
- **Status Refaktor v0.4 Selesai 100%**: Menunggu persetujuan pengguna sebelum melakukan push ke GitHub.
