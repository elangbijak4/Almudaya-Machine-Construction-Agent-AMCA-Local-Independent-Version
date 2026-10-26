# Spesifikasi Desain Antarmuka: Jendela Mengambang Diagnostik (*Fly-Window Modal Dialog*)

## 1. Filosofi Desain *Fly-Window* (@st.dialog)

Ketika error terjadi di antarmuka GUI, sistem tidak boleh hanya menampilkan teks merah mentah yang terbenam di antara widget lain. Sistem harus menampilkan **Jendela Mengambang Diagnostik (*Diagnostic Fly-Window Modal*)** yang elegan, ramah, dan memandu periset secara langsung:

```
┌────────────────────────────────────────────────────────────────────────┐
│ 🔍 Pemberitahuan Diagnostik Kesalahan                                  │
├────────────────────────────────────────────────────────────────────────┤
│                                                                        │
│  [🌐 Layanan Eksternal / Gateway AI]                                  │
│                                                                        │
│  ### 9Router Belum Memiliki Akun Penyedia AI yang Terhubung           │
│                                                                        │
│  AMCA berhasil menghubungi gateway 9Router lokal di port 20128,        │
│  namun 9Router menolak permintaan inferensi karena belum ada akun      │
│  penyedia AI (Google Gemini, Claude, OpenAI, dll.) yang berstatus      │
│  aktif di dalam dashboard 9Router Anda.                                │
│                                                                        │
│  ┌─ Langkah Penyelesaian yang Disarankan: ──────────────────────────┐  │
│  │ 1. Buka dashboard 9Router Anda di: [http://localhost:20128]      │  │
│  │ 2. Masuk ke menu 'Providers' (atau 'OAuth').                      │  │
│  │ 3. Hubungkan minimal satu akun penyedia AI (masukkan API Key).    │  │
│  │ 4. Setelah berstatus hijau, kembali ke AMCA dan klik tombol coba. │  │
│  └───────────────────────────────────────────────────────────────────┘  │
│                                                                        │
│  ▶ Rincian Diagnostik Teknis (Klik untuk memperluas)                   │
│    • Kode HTTP: 404 Not Found                                          │
│    • Penyedia Diminta: alicode-intl                                    │
│    • Pesan Server: No active credentials for provider: alicode-intl    │
│                                                                        │
│                                                   [ Tutup Jendela ]    │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Struktur Visual Komponen Dialog

1. **Badge Kategori Asal Error**:
   - Menegaskan secara instan sumber masalah agar periset tidak salah menyalahkan model AI atau spesifikasi YAML mereka:
     - 🌐 **Layanan Eksternal**: Kategori oranye/biru (9Router, jaringan, kuota).
     - 📝 **Alur Masukan / Spesifikasi**: Kategori kuning (YAML, port, Hoare contract).
     - ⚙️ **Sistem Inti AMCA**: Kategori merah (internal I/O, bug).
2. **Penjelasan Bahasa Manusia (*Human-First Copywriting*)**:
   - Menjelaskan masalah secara logis tanpa akronim atau istilah internal yang membingungkan.
3. **Langkah Solusi Konkret & Tautan Langsung**:
   - Jika masalahnya adalah 9Router: menyertakan link langsung yang dapat diklik ke `http://localhost:20128`.
   - Jika masalahnya adalah port Hoare: menjelaskan port sumber dan port tujuan yang tidak cocok beserta saran menambahkan komponen pembersih.
4. **Detail Diagnostik Teknis Tersembunyi (*Collapsible Technical Expander*)**:
   - Di dalam expander, ditampilkan kode error HTTP, exception type, context fungsi, dan stack trace untuk memudahkan pelaporan bug teknis bila diperlukan.
5. **Tombol Penutup (*Dismiss*)**:
   - Tombol "Tutup & Lanjutkan" yang membersihkan state dialog tanpa merusak data sesi percakapan atau draf YAML yang sedang dikerjakan.

---

## 3. Penempatan Integrasi pada Titik Eksekusi GUI (`app.py`)

Dialog diagnostik dipasang pada seluruh titik interaksi kritis:
1. **Titik 1 — Perancangan YAML Awal (`st.button("Buat YAML dengan agent")`)**:
   - Menangkap `ProviderError`, `IntentRejection`, atau kegagalan koneksi.
2. **Titik 2 — Revisi Spesifikasi Lewat Chat (`st.chat_input`)**:
   - Menangkap error saat iterasi perbaikan draf.
3. **Titik 3 — Validasi Struktural & Formal (`st.button("Validasi YAML saat ini")`)**:
   - Menangkap error sintaksis YAML, port mismatch, atau pembuktian Hoare yang gagal secara fatal.
4. **Titik 4 — Persetujuan & Konstruksi Mesin (`construct`)**:
   - Menangkap kegagalan Stage 3 AST isomorfisme, unit test internal, atau izin penulisan disk.
5. **Titik 5 — Pengikatan Komponen Eksternal (Bagian 8)**:
   - Menangkap penolakan Gerbang Keamanan AST atau kegagalan sandbox perilaku.
