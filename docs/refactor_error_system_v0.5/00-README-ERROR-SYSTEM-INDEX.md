# Rencana Teknis & Handover Master: Sistem Penanganan & Diagnostik Error Terintegrasi (`v0.5`)

## 1. Latar Belakang & Urgensi bagi Peneliti (*Researcher Empathy & Intent Preservation*)

Dalam rekayasa sistem agen dan mesin formal, periset sering kali menghadapi berbagai jenis kendala:
1. Kesalahan pada spesifikasi rancangan mesin (misalnya port tidak cocok atau prasyarat Hoare dilanggar).
2. Gangguan layanan hulu eksternal (misalnya 9Router belum dikonfigurasi, kuota token API habis, atau rate-limit HTTP 429).
3. Hambatan operasional sistem laptop (misalnya memori RAM habis atau berkas tidak dapat ditulis).

Ketika sebuah error terjadi, **tampilan error generik berupa teks merah mentah (*raw exception string*) sangat membingungkan periset**. Periset tidak dapat membedakan:
- *"Apakah model AI yang salah memahami rancangan saya?"*
- *"Apakah spesifikasi YAML saya yang keliru?"*
- *"Ataukah server eksternal seperti 9Router yang sedang bermasalah?"*

Kesalahpahaman ini dapat merusak alur berpikir dan menyebabkan periset mengubah prompt atau rancangan mesin yang sebenarnya sudah benar.

Oleh karena itu, AMCA versi `0.5` menghadirkan **Sistem Penanganan Error Terpadu (*Integrated Diagnostic & Error Handler*)** yang dilengkapi:
1. **Mesin Klasifikasi Diagnostik Tiga Kategori (*Tri-Origin Error Classifier*)** di lapisan inti (`src/amca_agent/diagnostics.py`).
2. **Jendela Mengambang Diagnostik Interaktif (*Interactive Fly-Window Modal Dialog*)** di antarmuka GUI Streamlit (`@st.dialog`).
3. **Format Pelaporan Terminal Berstruktur** di antarmuka CLI.

---

## 2. Taksonomi 3 Kategori Asal Error (*Tri-Origin Error Taxonomy*)

| Kategori Asal Error | Simbol & Label UI | Definisi & Contoh Kasus | Tanggung Jawab Tindakan |
| :--- | :--- | :--- | :--- |
| **1. Layanan Eksternal / Gateway** (`EXTERNAL_SERVICE`) | 🌐 **Layanan Eksternal** | • 9Router: belum ada akun provider aktif (HTTP 404/401).<br/>• Cloud API: kuota habis, rate limit (HTTP 429), token limit exceeded.<br/>• Runtime lokal: Ollama/LM Studio belum dijalankan di port lokal.<br/>• Jaringan: upstream timeout / connection refused. | Periksa konfigurasi gateway/koneksi (bukan merevisi prompt atau arsitektur mesin). |
| **2. Alur Masukan / Spesifikasi Riset** (`USER_INPUT_FLOW`) | 📝 **Alur Masukan / Spesifikasi** | • Intent out-of-scope (permintaan di luar perancangan mesin).<br/>• Sintaksis YAML malformed atau melanggar skema.<br/>• Tipe port output-ke-input tidak kompatibel.<br/>• Pelanggaran kontrak Hoare ($\text{Post}(u) \not\supseteq \text{Pre}(v)$).<br/>• Upaya transisi tanpa persetujuan (Approval A / B belum disetujui).<br/>• Pelanggaran keamanan AST pada kode komponen eksternal. | Perbaiki prompt, perbaiki koneksi port YAML, atau berikan persetujuan formal. |
| **3. Sistem Inti AMCA** (`CORE_SYSTEM`) | ⚙️ **Sistem Inti AMCA** | • Invarian sistem internal terlanggar (*internal bug*).<br/>• Kegagalan izin I/O disk lokal.<br/>• Inkonsistensi kompilasi kode proyek atau builder.<br/>• Kegagalan tak terduga (*unexpected unhandled exception*). | Laporkan bug sistem internal atau periksa integritas instalasi lokal AMCA. |

---

## 3. Struktur Berkas Refaktor (`docs/refactor_error_system_v0.5/`)

| File | Fokus Teknis |
| :--- | :--- |
| [`00-README-ERROR-SYSTEM-INDEX.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_error_system_v0.5/00-README-ERROR-SYSTEM-INDEX.md) | Indeks master, filosofi mitigasi kesalahpahaman intent, dan taksonomi 3 asal error. |
| [`01-SPEC-ERROR-TAXONOMY-AND-DIAGNOSTICS.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_error_system_v0.5/01-SPEC-ERROR-TAXONOMY-AND-DIAGNOSTICS.md) | Spesifikasi mesin klasifikasi diagnostik (`src/amca_agent/diagnostics.py`), model data `DiagnosticReport`, dan aturan inferensi asal error. |
| [`02-SPEC-UI-FLY-WINDOW-MODAL-DIALOG.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_error_system_v0.5/02-SPEC-UI-FLY-WINDOW-MODAL-DIALOG.md) | Desain jendela *fly-window* (`@st.dialog`) di Streamlit, layout kartu diagnostik, dan aksi solusi satu-klik. |
| [`03-IMPLEMENTATION-AND-TESTING-PLAN.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_error_system_v0.5/03-IMPLEMENTATION-AND-TESTING-PLAN.md) | Rencana implementasi teknis, pengujian unit klasifikasi, dan verifikasi non-regresi AppTest. |
| [`PROGRESS_LOG.md`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/docs/refactor_error_system_v0.5/PROGRESS_LOG.md) | Log formal langkah-demi-langkah pengerjaan refaktor. |

---

## 4. Invarian Sistem yang Wajib Dijaga (*Strict Constraints*)

1. **Aturan Push Git**: **DILARANG MELAKUKAN PUSH KE GITHUB** tanpa izin eksplisit pengguna.
2. **Invarian Widget Streamlit AppTest**:
   - Fungsi dialog (`@st.dialog`) hanya dipanggil ketika terjadi error aktif (`st.session_state.active_error_report`).
   - Pada alur pengujian normal tanpa error (`test_streamlit_app.py`), dialog tidak dirender sehingga indeks `app.selectbox[0]`, `app.button[0..2]`, dan `app.checkbox[0]` tetap 100% konsisten.
3. **Zero-Mocking Mandate**: Pengujian diagnostik wajib menggunakan objek eksepsi asli (`ProviderError`, `AMCAError`, `ContractViolationError`, dsb.).
4. **Non-Regression Suite**: Seluruh 116 unit test dan `validate_workflow.py` wajib tetap berstatus **`OK` / `PASS`**.
