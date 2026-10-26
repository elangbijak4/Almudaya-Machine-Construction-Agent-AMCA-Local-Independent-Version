# Spesifikasi Teknis: Mesin Diagnostik Error & Taksonomi Penyebab (`diagnostics.py`)

## 1. Arsitektur Modul Diagnostik (`src/amca_agent/diagnostics.py`)

Modul `diagnostics.py` bertindak sebagai orakel inferensi independen yang memetakan sembarang eksepsi Python atau pesan kegagalan sistem ke dalam struktur diagnostik yang kaya konteks:

```
                  ┌────────────────────────────────────────┐
                  │          Eksepsi Python / Error        │
                  │  (ProviderError, AMCAError, OSError)   │
                  └───────────────────┬────────────────────┘
                                      │
                                      ▼
                  ┌────────────────────────────────────────┐
                  │    diagnose_exception(exc, context)    │
                  │        (Evaluasi Pola & Aturan)        │
                  └───────────────────┬────────────────────┘
                                      │
          ┌───────────────────────────┼───────────────────────────┐
          ▼                           ▼                           ▼
┌──────────────────┐        ┌──────────────────┐        ┌──────────────────┐
│ EXTERNAL_SERVICE │        │ USER_INPUT_FLOW  │        │   CORE_SYSTEM    │
│ (Gateway, Kuota, │        │ (YAML, Port,     │        │ (Bug, I/O Disk,  │
│  Port Down, 429) │        │  Hoare, AST)     │        │  Invarian Pecah) │
└─────────┬────────┘        └─────────┬────────┘        └─────────┬────────┘
          │                           │                           │
          └───────────────────────────┼───────────────────────────┘
                                      │
                                      ▼
                        ┌───────────────────────────┐
                        │      DiagnosticReport     │
                        │  • Kategori & Simbol      │
                        │  • Judul Ringkas          │
                        │  • Penjelasan Peneliti    │
                        │  • Langkah Solusi Aksi    │
                        │  • Detail Teknis Rinci    │
                        └───────────────────────────┘
```

---

## 2. Struktur Data `DiagnosticReport`

```python
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

class ErrorOrigin(str, Enum):
    EXTERNAL_SERVICE = "external_service"   # Gangguan layanan upstream / gateway / kuota / jaringan
    USER_INPUT_FLOW = "user_input_flow"     # Kekeliruan alur riset, spesifikasi YAML, kontrak, atau port
    CORE_SYSTEM = "core_system"             # Masalah internal sistem, berkas lokal, atau bug software

@dataclass(frozen=True)
class DiagnosticReport:
    origin: ErrorOrigin
    origin_label: str
    origin_icon: str
    headline: str
    explanation: str
    remediation_steps: list[str]
    context: str = ""
    technical_details: dict[str, Any] = field(default_factory=dict)
    raw_message: str = ""
```

---

## 3. Matriks Inferensi & Aturan Klasifikasi Eksepsi

| Kelas Eksepsi / Sinyal Error | Pola Deteksi / Ciri Khas | Asal Error (`origin`) | Judul Ringkas (`headline`) & Rekomendasi Solusi |
| :--- | :--- | :--- | :--- |
| **`ProviderError` (9Router No Credentials)** | Memuat substring `"No active credentials for provider"` atau HTTP 404 pada 9Router. | `EXTERNAL_SERVICE` | **Judul**: 9Router Belum Memiliki Akun Penyedia AI Aktif.<br/>**Solusi**: Buka dashboard [http://localhost:20128](http://localhost:20128) $\to$ menu **Providers** $\to$ tambahkan API key penyedia AI (Gemini, Claude, OpenAI, dsb.). |
| **`ProviderError` (Quota / 429)** | `status_code == 429`, `"RESOURCE_EXHAUSTED"`, `"insufficient_quota"`, `"rate_limit_exceeded"`. | `EXTERNAL_SERVICE` | **Judul**: Batas Kuota / Rate Limit Penyedia AI Tercapai.<br/>**Solusi**: Beralih ke model cadangan, gunakan `AMCA Combo` untuk failover otomatis, atau periksa saldo/kuota API key Anda. |
| **`ProviderError` (Auth 401)** | `status_code == 401`, `"unauthorized"`, `"invalid_api_key"`. | `EXTERNAL_SERVICE` | **Judul**: Kunci Otorisasi Ditolak oleh Provider.<br/>**Solusi**: Periksa kembali ketikan API key pada antarmuka konfigurasi sidebar. |
| **`ProviderError` (Token Limit / Length)** | `trigger_reason == "token_limit_exceeded"` atau `"finish_reason=length"`. | `EXTERNAL_SERVICE` | **Judul**: Respons Model Terpotong karena Batas Token Konteks.<br/>**Solusi**: Aktifkan fitur kompaksi konteks AMCA, sederhanakan prompt rancangan, atau gunakan model berkapasitas konteks lebih besar. |
| **`ProviderError` (Port Unreachable / Timeout)** | `"upstream_unavailable"`, `"Connection refused"`, `"Timed out"`. | `EXTERNAL_SERVICE` | **Judul**: Layanan Model Lokal / Gateway Tidak Dapat Dihubungi.<br/>**Solusi**: Pastikan runtime lokal (9Router/Ollama/LM Studio) sedang berjalan pada port lokal yang sesuai. |
| **`IntentRejection` (Out of Scope)** | `classify_intent().allowed is False`. | `USER_INPUT_FLOW` | **Judul**: Permintaan Berada di Luar Cakupan Rekayasa Mesin.<br/>**Solusi**: Sesuaikan prompt Anda agar fokus pada perancangan pipeline data, agen, atau transformasi logika. |
| **`SpecificationError` / `SchemaError`** | Malformed YAML, duplicate keys, tipe port tidak cocok, siklus DAG. | `USER_INPUT_FLOW` | **Judul**: Draf Spesifikasi YAML Melanggar Aturan Skema.<br/>**Solusi**: Periksa daftar pemeriksaan struktural (`checks`), sesuaikan nama port output-ke-input, atau klik tombol revisi dengan agen. |
| **`ContractViolationError` (Hoare Violation)** | Precondition failed, empty input string, type assertion failure. | `USER_INPUT_FLOW` | **Judul**: Pelanggaran Kontrak Logika Formal Hoare ($P_c \to Q_c$).<br/>**Solusi**: Hubungkan komponen pembersih (misal `validate_text`) sebelum data dialirkan ke komponen analisis yang membutuhkan teks tervalidasi. |
| **`ASTSecurityError` (AST Gate Block)** | Percobaan impor `os`, `subprocess`, `socket`, pemanggilan `eval`/`exec`. | `USER_INPUT_FLOW` | **Judul**: Kode Komponen Ditolak oleh Gerbang Keamanan AST Statis.<br/>**Solusi**: Hilangkan impor pustaka berbahaya dan pastikan komponen beroperasi secara deterministik murni (*pure function*). |
| **`ApprovalMissingError` / `PermissionError`** | Mencoba memanggil construct tanpa token `APPROVE_SPEC` atau `APPROVE_CONSTRUCTION`. | `USER_INPUT_FLOW` | **Judul**: Persetujuan Formal Diperlukan Sebelum Konstruksi.<br/>**Solusi**: Berikan Approval A (kunci spesifikasi) dan Approval B (kunci rencana konstruksi) terlebih dahulu. |
| **`OSError` / `IOError` / Unhandled Exception** | Eksepsi sistem berkas atau runtime tak tertangani. | `CORE_SYSTEM` | **Judul**: Kendala Akses Sistem Operasi / Berkas Lokal.<br/>**Solusi**: Periksa izin tulis pada folder `artifacts/` atau ruang penyimpanan disk laptop Anda. |

---

## 4. Fungsi Format Terpadu (GUI & CLI)

1. `diagnose_exception(exc: Exception | str, *, context: str = "") -> DiagnosticReport`:  
   Menghasilkan objek laporan diagnosa lengkap.
2. `format_diagnostic_report_for_cli(report: DiagnosticReport) -> str`:  
   Menghasilkan representasi teks ANSI berwarna yang rapi untuk terminal CLI.
3. `format_diagnostic_report_for_markdown(report: DiagnosticReport) -> str`:  
   Menghasilkan representasi Markdown berstruktur untuk kartu atau jendela dialog GUI.
