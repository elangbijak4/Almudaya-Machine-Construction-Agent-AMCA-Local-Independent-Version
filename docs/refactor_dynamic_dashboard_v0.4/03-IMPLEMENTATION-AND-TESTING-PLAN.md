# Rencana Implementasi & Pengujian Antarmuka Dinamis (*Execution & Verification Plan*)

## 1. Rincian Modifikasi Kode

### A. Modul Pembantu: Pemeriksaan Status Port & Akun Provider (`src/amca_agent/provider.py`)
Tambahkan fungsi `inspect_provider_runtime_status(provider: str, base_url: str | None = None) -> dict`:
1. **Untuk 9Router**:
   - Memeriksa HTTP `GET http://127.0.0.1:20128/v1/models` (timeout 1 detik).
   - Membaca database SQLite `data.sqlite` secara *read-only*:
     - Menghitung jumlah akun pada `providerConnections WHERE isActive = 1`.
     - Mengambil daftar nama `combos`.
     - Mengambil `Default Key` lokal.
   - Mengembalikan kamus status:
     ```python
     {
         "reachable": True/False,
         "active_connections_count": int,
         "combos": list[str],
         "default_key_detected": bool,
         "guidance_message": str
     }
     ```
2. **Untuk Ollama / LM Studio / OpenCode**:
   - Memeriksa keterjangkauan port (11434 / 1234 / 4096) dalam timeout 500ms secara lokal.
   - Mengembalikan status ketersediaan runtime dan daftar model yang terpasang.

---

### B. Antarmuka Sidebar Reaktif (`app.py`)
Refaktor blok `with st.sidebar:` pada `app.py`:
1. **Pilihan Provider**: Tetap menggunakan `st.selectbox("Provider model", PROVIDER_OPTIONS)`.
2. **Kondisional Dinamis per Provider**:
   - **`provider == "9Router"`**:
     - Render kartu status `inspect_provider_runtime_status("9router")`.
     - Jika terhubung tetapi 0 koneksi: tampilkan `st.info` ramah yang memandu membuka `http://localhost:20128` untuk menghubungkan akun AI.
     - Sembunyikan kolom API key dari tampilan utama; masukkan ke dalam `with st.expander("Pengaturan Lanjutan (Override 9Router Key)", expanded=False):`.
     - Dropdown model menampilkan model/combo yang terdeteksi.
   - **`provider == "Google Gemini"`**:
     - Model selector dengan pilihan rekomendasi (`gemini-2.5-flash`, `gemini-2.5-pro`).
     - Kolom API key dengan badge memori sesi RAM (`SessionCredentialVault`).
   - **`provider in {"Ollama", "LM Studio", "OpenCode"}`**:
     - Badge probe status port real-time.
     - Dropdown model lokal terpasang.
     - Hilangkan kolom API key di layar utama.
   - **`provider == "Local Model"`**:
     - Panel inspeksi spek laptop nyata (`hardware.py`).
     - Keputusan Hardware Gate (`ELIGIBLE` / `REFUSED`).
     - Tombol daftarkan model.
     - Tanpa kolom API key.
   - **`provider == "AMCA Combo"`**:
     - Panel pembangun rantai fallback multi-tier.
   - **`provider == "Offline Deterministic"`**:
     - Badge mode *Air-Gapped* 100% lokal.
     - Sembunyikan seluruh pengaturan jaringan.

---

## 2. Verifikasi & Pengujian Tanpa Mocking (*Strict Verification Plan*)

1. **Pengujian Non-Regresi Unit & Integrasi**:
   - Menjalankan suite pengujian lengkap:
     ```powershell
     $env:PYTHONPATH = "src"
     .\.venv-retest\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
     ```
   - Memastikan seluruh **115 tests tetap lulus 100% (0 fail, 0 error)**.
2. **Pengujian Spesifik Streamlit AppTest**:
   - Memastikan `tests/integration/test_streamlit_app.py` tetap lulus sempurna tanpa pergeseran indeks widget bodi utama.
3. **Pengujian Alur Kerja SDLC Waterfall**:
   - Menjalankan `tools/validate_workflow.py` untuk memastikan kepatuhan tata kelola proyek.
4. **Sinkronisasi Buku Panduan Pengguna**:
   - Memperbarui `help/USER_MANUAL.md`, `help/USER_GUIDE.md`, dan `help/USER_TUTORIAL.md` untuk mendokumentasikan fitur Dashboard Dinamis per provider ini.

---

## 3. Komitmen & Batasan Eksekusi

- **Dilarang melakukan push ke GitHub** sampai ada izin formal dari pengguna.
- Perubahan kode harus bersih, terdokumentasi, dan memelihara kebersihan rahasia (*triple secret hygiene*).
