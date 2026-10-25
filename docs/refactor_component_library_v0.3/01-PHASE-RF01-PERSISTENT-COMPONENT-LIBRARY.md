# Fase RF-01: Arsitektur Library Komponen Kumulatif (`src/amca_components/`) & Pemanggilan sebagai Library pada Naskah Kode Mesin

## 1. Tujuan Teknis (Poin 3)

Mengubah cara AMCA menyimpan dan menggunakan komponen terdaftar sehingga:
1. AMCA memelihara sebuah **paket library Python nyata (`src/amca_components/`)** yang menyimpan seluruh komponen terdaftar (6 komponen bawaan + seluruh komponen tambahan dari sintesis *on-the-fly* maupun pengikatan eksternal) dan **memperbaruinya secara terus-menerus (kumulatif)** setiap kali ada komponen baru.
2. Ketika AMCA mengonstruksi kode mesin nyata di `artifacts/constructed_projects/<machine_id>-rev<NNN>/`, naskah kode mesin (`pipeline.py` / `components.py`) **cukup meng-`import` dan memanggil library `amca_components`** alih-alih menyalin ulang kode implementasi panjang di dalam naskah mesin.
3. Saat proyek dikemas ke dalam arsip Handover `<machine_id>-rev<NNN>-handover.zip`, paket library `src/amca_components/` ikut dibundel ke dalam direktori `src/amca_components/` proyek hasil konstruksi sehingga arsip `.zip` tetap 100% mandiri (*self-contained*) saat diunduh dan dijalankan di komputer lain.

---

## 2. Struktur Paket Library Komponen (`src/amca_components/`)

Buat paket Python baru di `src/amca_components/` dengan tata letak berikut:

```text
src/amca_components/
├── __init__.py          # Entrypoint publik library: COMPONENT_DISPATCH, get_library_component(), execute_library_component(), register_library_module()
├── contracts.py         # ContractViolationError, enforce_component_preconditions(), enforce_component_postconditions()
├── builtin.py           # Implementasi 6 komponen inti bawaan (run_input_source, run_validate_text, run_analysis_a, run_analysis_b, run_aggregate_results, run_generate_report)
├── catalog.json         # Manifest JSON kumulatif berisi metadata, kontrak Hoare, dan digest SHA-256 setiap modul komponen di library
└── custom/              # Direktori modul Python (.py) untuk setiap komponen kustom terdaftar
    ├── __init__.py      # Loader dinamis yang mengimpor seluruh modul .py terverifikasi di dalam custom/
    └── <component_id>.py # Satu file .py per komponen tambahan (hasil on-the-fly Code Agent atau impor eksternal)
```

---

## 3. Spesifikasi Rinci Tiap File di `src/amca_components/`

### 3.1 `src/amca_components/contracts.py`
Menyediakan *runtime Hoare precondition & postcondition guards* terpusat yang dipanggil oleh seluruh komponen di dalam library:
- `class ContractViolationError(ValueError)`: Eksepsi standar pelanggaran kontrak Hoare saat runtime.
- `PRECONDITION_PREDICATE_CHECKS: dict[str, Callable[[Any], bool]]`:
  - `"is_str"`: `isinstance(val, str)`
  - `"non_empty_raw"`: `isinstance(val, str) and len(val) > 0`
  - `"non_empty_trimmed"`: `isinstance(val, str) and len(val.strip()) > 0`
  - `"len_ge_1"`: `isinstance(val, str) and len(val.strip()) >= 1`
  - `"is_obj"`: `isinstance(val, (dict, str))` (mendukung representasi dict pada runtime AMCA maupun string metrik terformat pada proyek terkonstruksi)
  - `"formatted_metrics_summary"`: `isinstance(val, str) and ("=" in val or ";" in val) and bool(val.strip())`
  - `"report_contains_summary"`: `isinstance(val, dict) and "summary" in val`
- `enforce_preconditions(component_id: str, inputs: dict[str, Any], required_preconditions: dict[str, tuple[str, ...]] | None = None) -> None`
- `enforce_postconditions(component_id: str, outputs: dict[str, Any], guaranteed_postconditions: dict[str, tuple[str, ...]] | None = None) -> None`

### 3.2 `src/amca_components/builtin.py`
Berisi implementasi 6 komponen inti (`run_input_source`, `run_validate_text`, `run_analysis_a`, `run_analysis_b`, `run_aggregate_results`, `run_generate_report`) yang masing-masing memanggil `_enforce_preconditions("<component_id>", inputs)` dan `_enforce_postconditions("<component_id>", outputs)`.

### 3.3 Standar Modul Komponen di `src/amca_components/custom/<component_id>.py`
Setiap kali komponen baru ditambahkan (baik melalui Poin 1 *On-The-Fly Code Agent* maupun Poin 2 *External Component Binding*), AMCA menulis sebuah file modul Python nyata `src/amca_components/custom/<component_id>.py` (serta menyimpannya di `artifacts/custom_components/modules/<component_id>.py` untuk persistensi sesi) dengan kontrak standar:

```python
"""AMCA Registered Library Component: <component_id>."""
from __future__ import annotations

from typing import Any
from amca_components.contracts import (
    ContractViolationError,
    _enforce_postconditions,
    _enforce_preconditions,
)

AMCA_COMPONENT_META: dict[str, Any] = {
    "component_id": "<component_id>",
    "alias": "<alias>",
    "name": "<name>",
    "role": "<role>",
    "input_ports": {...},
    "output_ports": {...},
    "config_keys": [...],
    "default_config": {...},
    "preconditions": {...},
    "postconditions": {...},
    "prompt_hint": "<prompt_hint>",
    "origin": "on_the_fly_code_agent | external_bound | studio_template",
}


def run_<component_id>(
    inputs: dict[str, Any],
    config: dict[str, Any],
    raw_inputs: dict[str, Any],
) -> dict[str, Any]:
    _enforce_preconditions("<component_id>", inputs)
    # ... logika deterministik nyata komponen ...
    outputs = {...}
    _enforce_postconditions("<component_id>", outputs)
    return outputs
```

### 3.4 `src/amca_components/__init__.py`
Mengekspos:
- `COMPONENT_DISPATCH: dict[str, Callable[[dict[str, Any], dict[str, Any], dict[str, Any]], dict[str, Any]]]`
- `LIBRARY_CATALOG: dict[str, dict[str, Any]]`
- `reload_custom_library_modules(custom_dir: Path | None = None) -> dict[str, Any]`
- `execute_library_component(component_id: str, inputs: dict[str, Any], config: dict[str, Any], raw_inputs: dict[str, Any]) -> dict[str, Any]`

---

## 4. Refaktor pada `src/amca_agent/builder.py` & `src/amca_agent/formal_verifier.py`

### 4.1 Perubahan pada `src/amca_agent/builder.py`
1. **Naskah `src/constructed_machine/pipeline.py` Memanggil Library**:
   Di dalam `pipeline.py` yang dihasilkan oleh `_render_pipeline_py(candidate)`:
   ```python
   from amca_components import COMPONENT_DISPATCH, ContractViolationError
   ```
   Dan `src/constructed_machine/components.py` menjadi jembatan tipis (*thin library facade*) yang mengimpor dari `amca_components` sekaligus menyertakan deklarasi eksplisit `_enforce_preconditions` / `_enforce_postconditions` atau re-export dari `amca_components` agar kompatibel dengan seluruh test yang mengimpor `from constructed_machine.components import ContractViolationError, COMPONENT_DISPATCH`.
2. **Pembundelan Snapshot Library `src/amca_components/` ke Proyek Terkonstruksi**:
   Pada `build_constructed_project()`, selain menulis `src/constructed_machine/*.py`, builder menyalin modul-modul aktif dari `amca_components` (`__init__.py`, `contracts.py`, `builtin.py`, `catalog.json`, dan modul `custom/<component_id>.py` yang digunakan oleh mesin atau terdaftar di library) ke dalam `project_dir / "src" / "amca_components"`.
   **Hasilnya**:
   - Naskah mesin di `src/constructed_machine/pipeline.py` bersih dan hanya memanggil `amca_components` sebagai library.
   - Karena `src/amca_components/` berada di dalam `project_dir / "src"`, ketika proyek dikemas ke dalam `<machine_id>-rev<NNN>-handover.zip` oleh `packager.py`, arsip `.zip` tersebut langsung memuat library `amca_components` dan dapat dieksekusi di komputer mana pun dengan `$env:PYTHONPATH = "src"`.

### 4.2 Kompatibilitas dengan Verifikasi Formal Stage 3 (`src/amca_agent/formal_verifier.py`)
Perhatikan bahwa `verify_code_refinement()` di [`src/amca_agent/formal_verifier.py`](file:///d:/AMCA_Waterfall_Scaffold_v0.2/src/amca_agent/formal_verifier.py#L670-L725) sudah memindai **seluruh file `.py` di bawah `project_dir / "src"`** menggunakan `src_root.rglob("*.py")`!
Karena `project_dir / "src" / "amca_components"` berada di bawah `src_root`:
- **`FO-REF-01` ($G_{\text{code}} \cong G_{\text{yaml}}$)**: Mem-parsing `src/constructed_machine/pipeline.py` dan menemukan panggilan `execute_component_node` serta `wire_edge` yang persis sama dengan YAML.
- **`FO-REF-02` (*Runtime Hoare Guard Verification*)**: Mem-parsing `src/amca_components/builtin.py` dan `src/amca_components/custom/<component_id>.py`, menemukan panggilan `_enforce_preconditions("<cid>", inputs)` dan `_enforce_postconditions("<cid>", outputs)` untuk setiap komponen di `candidate.nodes`, serta membuktikan status **`PROVED`**!

---

## 5. Kriteria Lulus Fase RF-01 (*Verification Gate RF-01*)

Sebelum lanjut ke Fase RF-02, jalankan perintah berikut dan pastikan semuanya lulus:
```powershell
$env:PYTHONPATH = "src"
.\.venv-retest\Scripts\python.exe -m unittest discover -s tests -p "test_*.py" -v
```
- Seluruh test di `tests/integration/test_construction_and_zip.py` dan `tests/unit/test_custom_components.py` wajib lulus (`OK`).
- Di dalam arsip `.zip` hasil konstruksi, terdapat paket `src/amca_components/` dan `src/constructed_machine/pipeline.py` yang mengimpor library tersebut.
