"""Diagnostic engine and tri-origin error classification for AMCA.

Categorizes errors into:
1. EXTERNAL_SERVICE: 9Router, Cloud API, local runtimes, network, quotas, auth.
2. USER_INPUT_FLOW: YAML schema, port mismatches, Hoare contract violations, intent rejection, AST security.
3. CORE_SYSTEM: Internal invariants, disk I/O, unexpected software exceptions.
"""
from __future__ import annotations

import json
import traceback
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class ErrorOrigin(str, Enum):
    EXTERNAL_SERVICE = "external_service"
    USER_INPUT_FLOW = "user_input_flow"
    CORE_SYSTEM = "core_system"


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


def diagnose_exception(exc: Exception | str, *, context: str = "") -> DiagnosticReport:
    """Diagnose any exception or failure message and map it to a structured DiagnosticReport."""
    if isinstance(exc, Exception):
        exc_type_name = exc.__class__.__name__
        raw_msg = str(exc)
        tb_str = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)) if exc.__traceback__ else ""
        status_code = getattr(exc, "status_code", None)
        trigger_reason = getattr(exc, "trigger_reason", None)
    else:
        exc_type_name = "ErrorMessage"
        raw_msg = str(exc)
        tb_str = ""
        status_code = None
        trigger_reason = None

    lower_msg = raw_msg.lower()

    # =========================================================================
    # Kategori 1: Layanan Eksternal / Gateway / Kuota / Jaringan
    # =========================================================================
    # 1.1 9Router: Belum ada akun provider aktif
    if "no active credentials for provider" in lower_msg or ("9router" in lower_msg and "404" in lower_msg):
        return DiagnosticReport(
            origin=ErrorOrigin.EXTERNAL_SERVICE,
            origin_label="Layanan Eksternal / Gateway AI",
            origin_icon="🌐",
            headline="9Router Belum Memiliki Akun Penyedia AI yang Terhubung",
            explanation=(
                "AMCA berhasil menghubungi gateway 9Router lokal di port 20128, namun 9Router menolak "
                "permintaan inferensi karena belum ada akun penyedia AI (Google Gemini, OpenAI, Claude, Groq, dll.) "
                "yang terhubung dan berstatus aktif di dalam dashboard 9Router Anda."
            ),
            remediation_steps=[
                "Buka dashboard 9Router Anda di browser: http://localhost:20128",
                "Masuk ke menu 'Providers' (atau 'OAuth')",
                "Tambahkan minimal satu akun penyedia AI aktif (masukkan API Key yang Anda miliki)",
                "Setelah provider berstatus aktif (hijau) di 9Router, kembali ke AMCA dan klik tombol coba lagi.",
            ],
            context=context,
            technical_details={"status_code": 404, "exception_type": exc_type_name, "traceback": tb_str},
            raw_message=raw_msg,
        )

    # 1.2 Auth: Kunci Ditolak (HTTP 401)
    if "401" in lower_msg or "unauthorized" in lower_msg or "invalid_api_key" in lower_msg or "kunci otorisasi" in lower_msg:
        return DiagnosticReport(
            origin=ErrorOrigin.EXTERNAL_SERVICE,
            origin_label="Layanan Eksternal / Gateway AI",
            origin_icon="🌐",
            headline="Kunci Otorisasi Ditolak oleh Provider (HTTP 401)",
            explanation="Penyedia model menolak kredensial API key yang diberikan karena tidak valid, salah ketik, atau telah kedaluwarsa.",
            remediation_steps=[
                "Periksa kembali ketikan API key pada sidebar pengaturan AMCA",
                "Pastikan API key masih aktif di konsol penyedia model (misal Google AI Studio atau OpenAI Platform)",
                "Jika menggunakan 9Router, periksa kembali Access Key pada menu API Keys di dashboard 9Router.",
            ],
            context=context,
            technical_details={"status_code": status_code or 401, "exception_type": exc_type_name, "traceback": tb_str},
            raw_message=raw_msg,
        )

    # 1.3 Kuota Habis / Rate Limit (HTTP 429)
    if "429" in lower_msg or "resource_exhausted" in lower_msg or "insufficient_quota" in lower_msg or "rate_limit" in lower_msg:
        return DiagnosticReport(
            origin=ErrorOrigin.EXTERNAL_SERVICE,
            origin_label="Layanan Eksternal / Gateway AI",
            origin_icon="🌐",
            headline="Batas Kuota / Rate Limit Tercapai (HTTP 429)",
            explanation="Batas panggilan per menit (RPM/TPM) atau kuota saldo pada akun penyedia AI Anda telah habis sementara waktu.",
            remediation_steps=[
                "Tunggu beberapa saat hingga jendela rate-limit tereset otomatis",
                "Gunakan provider 'AMCA Combo' untuk berpindah otomatis ke model cadangan",
                "Beralih ke model lokal (Ollama / LM Studio) atau mode Offline Deterministic yang tanpa batas kuota.",
            ],
            context=context,
            technical_details={"status_code": status_code or 429, "exception_type": exc_type_name, "traceback": tb_str},
            raw_message=raw_msg,
        )

    # 1.4 Token Limit Exceeded / Finish Reason Length
    if "token_limit_exceeded" in lower_msg or "finish_reason=length" in lower_msg or "melebihi batas 1 mb" in lower_msg or "terpotong karena batas token" in lower_msg:
        return DiagnosticReport(
            origin=ErrorOrigin.EXTERNAL_SERVICE,
            origin_label="Layanan Eksternal / Gateway AI",
            origin_icon="🌐",
            headline="Respons Model Terpotong karena Batas Token (Context Overflow)",
            explanation="Jumlah token prompt atau respons melampaui kapasitas jendela konteks model yang sedang aktif.",
            remediation_steps=[
                "Pilih model dengan jendela konteks yang lebih besar (misal gemini-2.5-pro)",
                "Gunakan 'AMCA Combo' yang mendukung fitur kompaksi konteks cerdas",
                "Sederhanakan instruksi perancangan mesin pada prompt Anda.",
            ],
            context=context,
            technical_details={"trigger_reason": trigger_reason or "token_limit_exceeded", "exception_type": exc_type_name, "traceback": tb_str},
            raw_message=raw_msg,
        )

    # 1.5 Port Unreachable / Connection Refused / Upstream Timeout
    if "upstream_unavailable" in lower_msg or "connection refused" in lower_msg or "timed out" in lower_msg or "urllib.error.urlerror" in lower_msg or "tidak dapat menghubungi api" in lower_msg:
        return DiagnosticReport(
            origin=ErrorOrigin.EXTERNAL_SERVICE,
            origin_label="Layanan Eksternal / Gateway AI",
            origin_icon="🌐",
            headline="Layanan Gateway atau Runtime Lokal Tidak Terjangkau",
            explanation="AMCA tidak dapat tersambung ke port jaringan gateway atau runtime lokal yang dipilih di laptop Anda.",
            remediation_steps=[
                "Pastikan aplikasi runtime terkait (9Router di port 20128, Ollama di port 11434, atau LM Studio di port 1234) sedang berjalan",
                "Periksa kembali Endpoint Base URL di sidebar pengaturan",
                "Uji coba konektivitas dengan menekan tombol 'Pindai Model'.",
            ],
            context=context,
            technical_details={"exception_type": exc_type_name, "traceback": tb_str},
            raw_message=raw_msg,
        )

    # =========================================================================
    # Kategori 2: Alur Masukan / Spesifikasi Riset / Port / Kontrak Hoare
    # =========================================================================
    # 2.1 Hoare Contract Violation
    if "contractviolationerror" in lower_msg or "precondition" in lower_msg or "postcondition" in lower_msg or "hoare" in lower_msg:
        return DiagnosticReport(
            origin=ErrorOrigin.USER_INPUT_FLOW,
            origin_label="Alur Masukan / Spesifikasi Riset",
            origin_icon="📝",
            headline="Pelanggaran Kontrak Logika Formal Hoare",
            explanation=(
                "Sebuah komponen menolak eksekusi data karena prasyarat formal (precondition) tidak terpenuhi, "
                "misalnya menerima string kosong, teks tanpa pembersihan spasi, atau tipe struktur data yang tidak sesuai."
            ),
            remediation_steps=[
                "Pastikan masukan teks melewati komponen pembersih (seperti 'validate_text') sebelum diteruskan ke komponen analisis",
                "Periksa kecocokan prasyarat dan pascakondisi pada Katalog Komponen Terdaftar (Bagian 1)",
                "Gunakan tombol 'Revisi dengan agent' untuk memperbaiki topologi alur secara otomatis.",
            ],
            context=context,
            technical_details={"exception_type": exc_type_name, "traceback": tb_str},
            raw_message=raw_msg,
        )

    # 2.2 AST Security Gate Block
    if "blocked dangerous import" in lower_msg or "ast security" in lower_msg or "forbidden" in lower_msg:
        return DiagnosticReport(
            origin=ErrorOrigin.USER_INPUT_FLOW,
            origin_label="Alur Masukan / Spesifikasi Riset",
            origin_icon="📝",
            headline="Kode Komponen Ditolak oleh Gerbang Keamanan AST Statis",
            explanation="Berkas komponen eksternal memuat impor modul berbahaya (misal 'os', 'subprocess', 'socket') atau pemanggilan 'eval'/'exec' yang dilarang demi keamanan sistem.",
            remediation_steps=[
                "Hapus impor pustaka berbahaya dari berkas kode komponen Anda",
                "Pastikan fungsi komponen bersifat deterministik murni (hanya menggunakan pustaka Python bawaan yang aman seperti 're', 'json', 'math')",
                "Gunakan template kanonis yang tersedia di Bagian 8.",
            ],
            context=context,
            technical_details={"exception_type": exc_type_name, "traceback": tb_str},
            raw_message=raw_msg,
        )

    # 2.3 YAML Specification / Schema / Port Mismatch / DAG Cycle / Syntax Error
    if any(k in lower_msg for k in (
        "yaml", "schema_version", "unknown component", "cycle", "port", "incompatible",
        "validation failed", "verifier", "syntax", "parsing", "scanner", "inputerror",
        "flow sequence", "flow mapping", "unregistered",
    )):
        return DiagnosticReport(
            origin=ErrorOrigin.USER_INPUT_FLOW,
            origin_label="Alur Masukan / Spesifikasi Riset",
            origin_icon="📝",
            headline="Spesifikasi YAML Melanggar Skema atau Topologi Graf",
            explanation="Dokumen YAML draf rancangan mengandung kesalahan skema, port yang tidak saling cocok, atau hubungan siklik yang melanggar sifat graf terarah (DAG).",
            remediation_steps=[
                "Tinjau tab diagram graf untuk melihat letak sambungan sisi (edges) yang keliru",
                "Pastikan seluruh komponen yang digunakan telah terdaftar di Katalog Komponen",
                "Klik tombol 'Validasi YAML saat ini' untuk melihat daftar diagnostik periksa yang gagal.",
            ],
            context=context,
            technical_details={"exception_type": exc_type_name, "traceback": tb_str},
            raw_message=raw_msg,
        )

    # 2.4 Intent Rejection (Out of Scope)
    if "out-of-scope" in lower_msg or "cakupan" in lower_msg or "bukan rekayasa mesin" in lower_msg:
        return DiagnosticReport(
            origin=ErrorOrigin.USER_INPUT_FLOW,
            origin_label="Alur Masukan / Spesifikasi Riset",
            origin_icon="📝",
            headline="Permintaan di Luar Cakupan Rekayasa Mesin AMCA",
            explanation="AMCA mendeteksi bahwa prompt pengguna meminta topik percakapan umum yang berada di luar lingkup rekayasa mesin atau pipeline data.",
            remediation_steps=[
                "Fokuskan kembali deskripsi permintaan pada alur pemrosesan data, transformasi teks, atau arsitektur agen",
                "Gunakan salah satu contoh bawaan di Bagian 1 sebagai titik awal.",
            ],
            context=context,
            technical_details={"exception_type": exc_type_name, "traceback": tb_str},
            raw_message=raw_msg,
        )

    # 2.5 Approval Missing / Permission
    if "approval" in lower_msg or "permissionerror" in lower_msg or "belum disetujui" in lower_msg:
        return DiagnosticReport(
            origin=ErrorOrigin.USER_INPUT_FLOW,
            origin_label="Alur Masukan / Spesifikasi Riset",
            origin_icon="📝",
            headline="Tahap Persetujuan Formal Belum Diberikan",
            explanation="Operasi konstruksi atau eksekusi mesin memerlukan persetujuan ganda formal (Approval A dan Approval B) sebelum berkas dapat dibuat atau dijalankan.",
            remediation_steps=[
                "Centang dan klik 'Setujui Spesifikasi (Approval A)' di Bagian 4",
                "Tinjau rencana tahapan Waterfall di Bagian 5 lalu klik 'Setujui Rencana Konstruksi (Approval B)'.",
            ],
            context=context,
            technical_details={"exception_type": exc_type_name, "traceback": tb_str},
            raw_message=raw_msg,
        )

    # =========================================================================
    # Kategori 3: Sistem Inti AMCA (Internal Invariant / Disk I/O / Bug)
    # =========================================================================
    return DiagnosticReport(
        origin=ErrorOrigin.CORE_SYSTEM,
        origin_label="Sistem Inti AMCA",
        origin_icon="⚙️",
        headline="Kendala Operasional Sistem atau Berkas Lokal",
        explanation="Terjadi kegagalan I/O pada penyimpanan lokal laptop atau kondisi pengecualian internal yang tidak tertangani.",
        remediation_steps=[
            "Periksa izin penulisan (write permission) pada direktori 'artifacts/' di laptop Anda",
            "Pastikan ruang penyimpanan disk mencukupi untuk konstruksi berkas proyek",
            "Buka rincian teknis di bawah ini untuk melihat jejak tumpukan kode (stack trace).",
        ],
        context=context,
        technical_details={"exception_type": exc_type_name, "traceback": tb_str},
        raw_message=raw_msg,
    )


def format_diagnostic_report_for_cli(report: DiagnosticReport) -> str:
    """Format a DiagnosticReport into an ANSI-friendly structured terminal string."""
    banner = f"\n[{report.origin_icon} DIAGNOSTIK KESALAHAN AMCA — ASAL: {report.origin_label.upper()}]"
    lines = [
        "=" * 72,
        banner,
        "=" * 72,
        f"Masalah: {report.headline}",
        "",
        f"Penjelasan: {report.explanation}",
        "",
        "Langkah Solusi yang Disarankan:",
    ]
    for idx, step in enumerate(report.remediation_steps, 1):
        lines.append(f"  {idx}. {step}")
    if report.context:
        lines.append(f"\nKonteks: {report.context}")
    if report.raw_message:
        lines.append(f"\nPesan Asli: {report.raw_message}")
    lines.append("=" * 72)
    return "\n".join(lines)


def format_diagnostic_report_for_markdown(report: DiagnosticReport) -> str:
    """Format a DiagnosticReport into clean structured Markdown for GUI rendering."""
    lines = [
        f"### {report.origin_icon} {report.headline}",
        f"**Kategori Asal Masalah**: `{report.origin_label}`",
        "",
        report.explanation,
        "",
        "#### Langkah Penyelesaian yang Disarankan:",
    ]
    for idx, step in enumerate(report.remediation_steps, 1):
        lines.append(f"{idx}. {step}")
    return "\n".join(lines)
