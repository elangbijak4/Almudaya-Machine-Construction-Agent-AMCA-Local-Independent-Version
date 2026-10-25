"""Real OS hardware capability inspector and fail-closed gate for local model downloads."""
from __future__ import annotations

import ctypes
import json
import os
import platform
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
LOCAL_MODELS_DIR = ROOT / "artifacts" / "local_models"


@dataclass(frozen=True)
class LocalModelProfile:
    model_id: str
    display_name: str
    download_size_mb: int
    min_ram_available_mb: int
    min_disk_free_mb: int
    requires_gpu: bool = False
    min_gpu_vram_mb: int = 0

    def as_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "display_name": self.display_name,
            "download_size_mb": self.download_size_mb,
            "min_ram_available_mb": self.min_ram_available_mb,
            "min_disk_free_mb": self.min_disk_free_mb,
            "requires_gpu": self.requires_gpu,
            "min_gpu_vram_mb": self.min_gpu_vram_mb,
        }


LOCAL_MODEL_CATALOG: dict[str, LocalModelProfile] = {
    "qwen2.5-coder-1.5b-instruct-q4_k_m.gguf": LocalModelProfile(
        model_id="qwen2.5-coder-1.5b-instruct-q4_k_m.gguf",
        display_name="Qwen 2.5 Coder 1.5B Instruct (Q4_K_M, Light Laptop)",
        download_size_mb=1120,
        min_ram_available_mb=1536,
        min_disk_free_mb=2048,
        requires_gpu=False,
    ),
    "qwen2.5-coder-7b-instruct-q4_k_m.gguf": LocalModelProfile(
        model_id="qwen2.5-coder-7b-instruct-q4_k_m.gguf",
        display_name="Qwen 2.5 Coder 7B Instruct (Q4_K_M, Standard Laptop)",
        download_size_mb=4680,
        min_ram_available_mb=6144,
        min_disk_free_mb=7020,
        requires_gpu=False,
    ),
    "deepseek-r1-distill-qwen-14b-q4_k_m.gguf": LocalModelProfile(
        model_id="deepseek-r1-distill-qwen-14b-q4_k_m.gguf",
        display_name="DeepSeek R1 Distill Qwen 14B (Q4_K_M, High-Spec Laptop)",
        download_size_mb=9000,
        min_ram_available_mb=12288,
        min_disk_free_mb=14000,
        requires_gpu=False,
    ),
    "llama-3.3-70b-instruct-q4_k_m.gguf": LocalModelProfile(
        model_id="llama-3.3-70b-instruct-q4_k_m.gguf",
        display_name="Llama 3.3 70B Instruct (Q4_K_M, Workstation GPU Required)",
        download_size_mb=42500,
        min_ram_available_mb=49152,
        min_disk_free_mb=65000,
        requires_gpu=True,
        min_gpu_vram_mb=24576,
    ),
}

CURATED_LOCAL_MODELS = LOCAL_MODEL_CATALOG


@dataclass(frozen=True)
class HostHardwareSnapshot:
    inspection_timestamp: str
    host_os: str
    cpu_arch: str
    cpu_logical_cores: int
    ram_total_mb: int
    ram_available_mb: int
    disk_free_mb: int
    gpu_detected: bool
    gpu_vram_mb: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "inspection_timestamp": self.inspection_timestamp,
            "host_os": self.host_os,
            "cpu_arch": self.cpu_arch,
            "cpu_logical_cores": self.cpu_logical_cores,
            "ram_total_mb": self.ram_total_mb,
            "ram_available_mb": self.ram_available_mb,
            "disk_free_mb": self.disk_free_mb,
            "gpu_detected": self.gpu_detected,
            "gpu_vram_mb": self.gpu_vram_mb,
        }


@dataclass(frozen=True)
class HardwareEligibilityReport:
    snapshot: HostHardwareSnapshot
    requested_local_model: LocalModelProfile
    status: str  # "ELIGIBLE" | "REFUSED_INSUFFICIENT_HARDWARE"
    reasons: tuple[str, ...]

    @property
    def eligible(self) -> bool:
        return self.status == "ELIGIBLE"

    @property
    def decision(self) -> str:
        return self.status

    def as_dict(self) -> dict[str, Any]:
        return {
            **self.snapshot.as_dict(),
            "requested_local_model": self.requested_local_model.as_dict(),
            "status": self.status,
            "reasons": list(self.reasons),
        }


class _MEMORYSTATUSEX(ctypes.Structure):
    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("sullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def _query_ram_mb() -> tuple[int, int]:
    """Query actual total and available physical RAM in MiB from the host OS."""
    if os.name == "nt":
        stat = _MEMORYSTATUSEX()
        stat.dwLength = ctypes.sizeof(_MEMORYSTATUSEX)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
            total_mb = int(stat.ullTotalPhys // (1024 * 1024))
            avail_mb = int(stat.ullAvailPhys // (1024 * 1024))
            return max(total_mb, 1), max(avail_mb, 1)

    meminfo = Path("/proc/meminfo")
    if meminfo.is_file():
        lines = meminfo.read_text(encoding="utf-8", errors="ignore").splitlines()
        values: dict[str, int] = {}
        for line in lines:
            if ":" in line:
                k, v = line.split(":", 1)
                parts = v.strip().split()
                if parts and parts[0].isdigit():
                    values[k.strip()] = int(parts[0]) // 1024
        if "MemTotal" in values:
            total = values["MemTotal"]
            avail = values.get("MemAvailable", values.get("MemFree", total // 2))
            return max(total, 1), max(avail, 1)

    # POSIX fallback via os.sysconf
    if hasattr(os, "sysconf"):
        try:
            page_size = os.sysconf("SC_PAGE_SIZE")
            phys_pages = os.sysconf("SC_PHYS_PAGES")
            avail_pages = os.sysconf("SC_AVPHYS_PAGES") if "SC_AVPHYS_PAGES" in os.sysconf_names else phys_pages // 2
            total_mb = int((page_size * phys_pages) // (1024 * 1024))
            avail_mb = int((page_size * avail_pages) // (1024 * 1024))
            return max(total_mb, 1), max(avail_mb, 1)
        except (ValueError, OSError):
            pass

    return 4096, 2048


def _query_gpu_vram_mb() -> tuple[bool, int]:
    """Check if an NVIDIA GPU is present via nvidia-smi without failing if absent."""
    nvsmi = shutil.which("nvidia-smi")
    if not nvsmi:
        return False, 0
    try:
        proc = subprocess.run(
            [nvsmi, "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
            timeout=2,
            check=False,
        )
        if proc.returncode == 0 and proc.stdout.strip():
            first_line = proc.stdout.strip().splitlines()[0].strip()
            if first_line.isdigit():
                vram = int(first_line)
                return vram > 0, vram
    except (OSError, subprocess.SubprocessError, ValueError):
        pass
    return False, 0


def inspect_host_hardware(target_dir: Path | None = None) -> HostHardwareSnapshot:
    """Inspect real host OS RAM, free disk space, CPU cores, and GPU/VRAM."""
    check_path = target_dir or ROOT
    if not check_path.exists():
        check_path = ROOT
    usage = shutil.disk_usage(check_path)
    disk_free_mb = int(usage.free // (1024 * 1024))
    ram_total_mb, ram_available_mb = _query_ram_mb()
    gpu_detected, gpu_vram_mb = _query_gpu_vram_mb()

    return HostHardwareSnapshot(
        inspection_timestamp=datetime.now(timezone.utc).isoformat(),
        host_os=platform.platform(),
        cpu_arch=platform.machine() or "unknown",
        cpu_logical_cores=max(os.cpu_count() or 1, 1),
        ram_total_mb=ram_total_mb,
        ram_available_mb=ram_available_mb,
        disk_free_mb=disk_free_mb,
        gpu_detected=gpu_detected,
        gpu_vram_mb=gpu_vram_mb,
    )


def resolve_local_model_profile(model_id_or_profile: str | LocalModelProfile) -> LocalModelProfile:
    if isinstance(model_id_or_profile, LocalModelProfile):
        return model_id_or_profile
    if model_id_or_profile in LOCAL_MODEL_CATALOG:
        return LOCAL_MODEL_CATALOG[model_id_or_profile]
    # Infer profile from parameter size in model name (e.g., 70b, 32b, 14b, 7b, 1.5b)
    lower = model_id_or_profile.lower()
    if "70b" in lower:
        return LOCAL_MODEL_CATALOG["llama-3.3-70b-instruct-q4_k_m.gguf"]
    if "14b" in lower or "32b" in lower:
        return LOCAL_MODEL_CATALOG["deepseek-r1-distill-qwen-14b-q4_k_m.gguf"]
    if "1.5b" in lower or "1b" in lower or "3b" in lower:
        return LOCAL_MODEL_CATALOG["qwen2.5-coder-1.5b-instruct-q4_k_m.gguf"]
    return LocalModelProfile(
        model_id=model_id_or_profile,
        display_name=f"Local Model ({model_id_or_profile})",
        download_size_mb=4680,
        min_ram_available_mb=6144,
        min_disk_free_mb=7020,
        requires_gpu=False,
    )


def evaluate_local_model_eligibility(
    model_id_or_profile: str | LocalModelProfile,
    *,
    hardware: HostHardwareSnapshot | None = None,
) -> HardwareEligibilityReport:
    """Evaluate whether the laptop meets the model's RAM, disk, and GPU requirements (fail-closed)."""
    snapshot = hardware or inspect_host_hardware()
    profile = resolve_local_model_profile(model_id_or_profile)
    reasons: list[str] = []

    if snapshot.ram_available_mb < profile.min_ram_available_mb:
        reasons.append(
            f"Available RAM ({snapshot.ram_available_mb} MB) is below the model minimum requirement ({profile.min_ram_available_mb} MB)."
        )
    if snapshot.disk_free_mb < profile.min_disk_free_mb:
        reasons.append(
            f"Free disk space ({snapshot.disk_free_mb} MB) is below the model minimum requirement ({profile.min_disk_free_mb} MB)."
        )
    if profile.requires_gpu and not snapshot.gpu_detected:
        reasons.append(
            f"Model {profile.model_id!r} requires a dedicated GPU, but no compatible GPU was detected."
        )
    elif profile.requires_gpu and snapshot.gpu_vram_mb < profile.min_gpu_vram_mb:
        reasons.append(
            f"Detected GPU VRAM ({snapshot.gpu_vram_mb} MB) is below the model minimum requirement ({profile.min_gpu_vram_mb} MB)."
        )

    status = "ELIGIBLE" if not reasons else "REFUSED_INSUFFICIENT_HARDWARE"
    return HardwareEligibilityReport(
        snapshot=snapshot,
        requested_local_model=profile,
        status=status,
        reasons=tuple(reasons),
    )


def register_approved_local_model(
    model_id_or_profile: str | LocalModelProfile,
    *,
    user_approved: bool,
    hardware: HostHardwareSnapshot | None = None,
    target_dir: Path | None = None,
) -> tuple[HardwareEligibilityReport, Path]:
    """Enforce the fail-closed hardware gate before registering/provisioning a local model."""
    report = evaluate_local_model_eligibility(model_id_or_profile, hardware=hardware)
    if not report.eligible:
        raise PermissionError(
            f"Unduhan model lokal ditolak otomatis ({report.status}): {'; '.join(report.reasons)}"
        )
    if not user_approved:
        raise PermissionError("Unduhan model lokal memerlukan persetujuan eksplisit dari pengguna.")

    dest_root = (target_dir or LOCAL_MODELS_DIR).resolve()
    dest_root.mkdir(parents=True, exist_ok=True)
    manifest_path = dest_root / f"{report.requested_local_model.model_id}.manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "model_id": report.requested_local_model.model_id,
                "eligibility_report": report.as_dict(),
                "user_approved": True,
                "registered_at": datetime.now(timezone.utc).isoformat(),
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return report, manifest_path
