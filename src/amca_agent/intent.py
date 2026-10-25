"""Opening greeting and intent/scope classification for the AMCA Agent Constructor."""
from __future__ import annotations

from dataclasses import dataclass

OPENING_GREETING = "Mesin/agent apakah yang Anda ingin buat?"

OUT_OF_SCOPE_KEYWORDS: tuple[str, ...] = (
    "resep masakan",
    "cara memasak",
    "nasi goreng",
    "puisi cinta",
    "ramalan cuaca",
    "skor sepak bola",
    "jadwal bioskop",
    "lagu",
    "novel",
    "recipe",
    "cook",
    "weather forecast",
    "horoscope",
)

IN_SCOPE_KEYWORDS: tuple[str, ...] = (
    "mesin",
    "agent",
    "agen",
    "pipeline",
    "dag",
    "yaml",
    "teks",
    "text",
    "validasi",
    "validate",
    "analisis",
    "analysis",
    "karakter",
    "kata",
    "ringkasan",
    "summary",
    "laporan",
    "report",
    "komponen",
    "component",
    "sistem",
    "system",
    "workflow",
    "input",
    "output",
    "count",
    "hitung",
    "buat",
    "build",
    "make",
    "draw",
    "revisi",
)


@dataclass(frozen=True)
class IntentClassification:
    status: str  # "in_scope" | "needs_clarification" | "out_of_scope"
    reason: str
    boundary_message: str | None = None

    @property
    def allowed(self) -> bool:
        return self.status == "in_scope"

    @property
    def accepted(self) -> bool:
        return self.allowed

    def as_dict(self) -> dict[str, str | None]:
        return {
            "status": self.status,
            "reason": self.reason,
            "boundary_message": self.boundary_message,
        }


def classify_intent(prompt: str) -> IntentClassification:
    """Classify a user request into in_scope, needs_clarification, or out_of_scope."""
    cleaned = (prompt or "").strip()
    if not cleaned:
        return IntentClassification(
            status="needs_clarification",
            reason="Permintaan masih kosong.",
            boundary_message=f"{OPENING_GREETING} Jelaskan input, langkah pemrosesan/validasi, dan bentuk laporan keluarannya.",
        )
    if len(cleaned) > 8_000:
        return IntentClassification(
            status="out_of_scope",
            reason="Permintaan melebihi batas maksimum 8.000 karakter per giliran.",
            boundary_message="Panjang prompt melebihi batas 8.000 karakter. Ringkas spesifikasi mesin/agent Anda.",
        )

    lower = cleaned.lower()
    for kw in OUT_OF_SCOPE_KEYWORDS:
        if kw in lower and not any(ik in lower for ik in ("mesin", "agent", "pipeline", "dag", "yaml", "analisis teks")):
            return IntentClassification(
                status="out_of_scope",
                reason=f"Permintaan terdeteksi di luar cakupan rekayasa mesin/agent ({kw!r}).",
                boundary_message=(
                    "Permintaan tersebut berada di luar cakupan AMCA. AMCA khusus dirancang untuk merancang, "
                    "memverifikasi secara formal, dan membangun sistem mesin/agent pemrosesan terstruktur (DAG)."
                ),
            )

    if any(ik in lower for ik in IN_SCOPE_KEYWORDS) or len(cleaned) >= 3:
        return IntentClassification(
            status="in_scope",
            reason="Permintaan sesuai dengan cakupan konstruksi atau revisi mesin/agent AMCA.",
            boundary_message=None,
        )

    return IntentClassification(
        status="needs_clarification",
        reason="Deskripsi mesin terlalu singkat atau ambigu.",
        boundary_message=f"{OPENING_GREETING} Sebutkan tujuan mesin, input teks, dan analisis yang dibutuhkan.",
    )
