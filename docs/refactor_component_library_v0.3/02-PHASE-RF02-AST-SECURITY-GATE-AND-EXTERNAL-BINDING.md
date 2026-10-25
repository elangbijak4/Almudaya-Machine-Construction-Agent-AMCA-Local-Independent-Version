# Fase RF-02: Pengikatan Komponen dari Luar (Antigravity, OpenCode, Codex) & Gerbang Keamanan AST Statis (`src/amca_agent/component_binder.py`)

## 1. Tujuan Teknis (Poin 2)

Memungkinkan pengguna membuat komponen di luar aplikasi AMCA (misalnya dengan bantuan **Antigravity**, **OpenCode**, **Codex**, atau ditulis langsung sebagai file `.py`), lalu **mendaftarkan dan mengikatnya (*binding*)** ke dalam aplikasi Agent AMCA serta Library Komponen (`src/amca_components/`) untuk digunakan membangun mesin nyata, dengan jaminan keamanan dan determinisme penuh.

---

## 2. Desain Modul `src/amca_agent/component_binder.py`

Buat modul baru `src/amca_agent/component_binder.py` yang bertanggung jawab atas 4 tahap pengikatan komponen eksternal maupun komponen hasil *Code Agent*:

### Tahap 1: *Static AST Security & Determinism Gate* (`audit_component_source_ast`)
Setiap kode sumber Python komponen (baik dari file eksternal `.py` maupun dari *On-The-Fly Code Agent* di Fase RF-03) **wajib** diperiksa menggunakan `ast.parse()` sebelum pernah dieksekusi:

1. **Allowlist Modul Standar yang Diizinkan (`ALLOWED_STDLIB_IMPORTS`)**:
   ```python
   ALLOWED_STDLIB_IMPORTS = frozenset({
       "__future__",
       "re",
       "json",
       "math",
       "statistics",
       "collections",
       "itertools",
       "functools",
       "string",
       "unicodedata",
       "hashlib",
       "typing",
       "dataclasses",
       "decimal",
       "fractions",
       "amca_components",
       "amca_components.contracts",
   })
   ```
   Setiap node `ast.Import` atau `ast.ImportFrom` yang mengimpor modul di luar daftar ini (seperti `os`, `sys`, `subprocess`, `socket`, `urllib`, `http`, `pathlib`, `shutil`, `ctypes`, `pickle`, `importlib`) **langsung ditolak secara *fail-closed*** dengan `ComponentSecurityError`.

2. **Blocklist Fungsi Bawaan & Atribut Berbahaya (`FORBIDDEN_CALLS` & `FORBIDDEN_ATTRS`)**:
   - Menolak pemanggilan nama fungsi: `eval`, `exec`, `compile`, `open`, `__import__`, `input`, `breakpoint`, `globals`, `locals`, `vars`, `delattr`, `setattr`.
   - Menolak akses atribut dunder berbahaya: `__subclasses__`, `__globals__`, `__code__`, `__builtins__`, `__dict__`, `__class__`.

3. **Verifikasi Keberadaan Fungsi Entrypoint Komponen**:
   - Memastikan file memiliki fungsi `run_<component_id>(inputs, config, raw_inputs)` atau fungsi utama yang dapat dibungkus (*wrapped*) secara otomatis ke dalam tanda tangan standar `(inputs: dict[str, Any], config: dict[str, Any], raw_inputs: dict[str, Any]) -> dict[str, Any]`.

---

### Tahap 2: Ekstraksi & Inferensi Kontrak Komponen (`extract_or_infer_component_meta`)

Pengguna yang membuat komponen di Antigravity / OpenCode / Codex dapat memilih salah satu dari **dua format file `.py`**:

#### Format A — File `.py` dengan `AMCA_COMPONENT_META` Eksplisit
Jika file `.py` sudah menyertakan dictionary `AMCA_COMPONENT_META` (seperti spesifikasi di Fase RF-01), binder langsung membaca dan memvalidasi metadata tersebut.

#### Format B — File `.py` Berisi Fungsi Python Murni Tanpa `AMCA_COMPONENT_META` (Auto-Wrapping & Contract Inference)
Jika pengguna membuat fungsi Python biasa dengan Antigravity / OpenCode / Codex, misalnya:
```python
import re

def clean_punctuation(text: str) -> str:
    """Remove punctuation characters and normalize whitespace."""
    cleaned = re.sub(r"[^\w\s]", "", text).strip()
    return " ".join(cleaned.split())
```
Maka `extract_or_infer_component_meta()` pada `component_binder.py` akan:
1. Membaca AST fungsi pertama yang bukan private (`clean_punctuation`), membaca *docstring*, parameter argumen (`text: str`), dan tipe kembalian (`-> str` atau `-> dict`).
2. Menyusun metadata `CustomComponentSpec` secara otomatis:
   - `component_id`: `"clean_punctuation"` (atau sesuai `--id` yang diberikan user)
   - `alias`: `"custom.clean_punctuation"`
   - `input_ports`: `{"text": "string"}` (atau sesuai nama parameter fungsi)
   - `output_ports`: `{"text": "string"}` jika mengembalikan `str`, atau `{"finding": "object"}` jika mengembalikan `dict`.
   - `preconditions` & `postconditions`: Disimpulkan secara otomatis dari tipe port (atau dapat disesuaikan user di GUI/CLI).
3. Membungkus (*wrap*) fungsi tersebut ke dalam modul standar `src/amca_components/custom/<component_id>.py` yang menyertakan panggilan eksplisit:
   ```python
   _enforce_preconditions("<component_id>", inputs)
   ...
   _enforce_postconditions("<component_id>", outputs)
   ```
   sehingga komponen dari luar tersebut **otomatis lulus Verifikasi Formal Stage 1 (`FO-HOA-01`) dan Stage 3 (`FO-REF-02`)**!

---

### Tahap 3: *Self-Test Execution Sandbox* Sebelum Pendaftaran (`verify_component_behavior`)
Sebelum komponen ditulis ke `src/amca_components/custom/<component_id>.py`:
1. Binder mengeksekusi modul komponen di dalam namespace terisolasi (` restricted_builtins`) dengan sampel uji otomatis (misalnya `{"text": "AMCA builds a graph."}`).
2. Memastikan keluaran komponen adalah `dict` yang memiliki kunci sesuai `output_ports` dan nilai dengan tipe yang benar (`str` untuk `"string"`, `dict` atau `str` berformat metrik untuk `"object"`).
3. Memastikan bahwa ketika diberi input kosong/tidak valid (`{}` atau `{"text": "   "}`), komponen menolak dengan `ContractViolationError` atau `ComponentFailure`.

---

### Tahap 4: Pengikatan ke Library & Registry Aktif (`bind_external_component_file`)
Fungsi utama yang akan dipanggil oleh CLI, GUI, maupun *On-The-Fly Code Agent*:
```python
def bind_component_from_python_source(
    source_code: str,
    *,
    component_id: str = "",
    alias: str = "",
    name: str = "",
    role: str = "",
    input_ports: dict[str, str] | None = None,
    output_ports: dict[str, str] | None = None,
    config_keys: list[str] | None = None,
    preconditions: dict[str, list[str]] | None = None,
    postconditions: dict[str, list[str]] | None = None,
    origin: str = "external_bound",
    persist: bool = True,
) -> BoundComponentRecord:
```
Fungsi ini:
1. Menjalankan `audit_component_source_ast(source_code)`.
2. Mengekstrak/menyusun metadata dan membungkus kode menjadi modul standar `src/amca_components/custom/<component_id>.py` yang memiliki `_enforce_preconditions` & `_enforce_postconditions`.
3. Menjalankan `verify_component_behavior()`.
4. Menulis modul ke `src/amca_components/custom/<component_id>.py` dan memperbarui `src/amca_components/catalog.json` (beserta SHA-256).
5. Mendaftarkan `ComponentDefinition` (dengan adaptor yang memanggil fungsi Python nyata dari modul tersebut!) ke `amca.registry`, `amca_agent.system_spec`, dan `amca_agent.formal_verifier.HOARE_CONTRACTS`.

---

## 3. Antarmuka CLI & GUI untuk Poin 2

- **Perintah CLI Baru**:
  ```powershell
  $env:PYTHONPATH = "src"
  .\.venv\Scripts\python.exe -m amca_agent.cli bind-component <path_ke_file.py> [--id <component_id>] [--alias <alias>] [--role <deskripsi>]
  ```
- **Panel GUI di `app.py` (Bagian 8)**:
  Tambahkan tab/bagian **"🔗 Ikat Komponen Eksternal dari File Python (`.py`) — Antigravity / OpenCode / Codex"** di mana user dapat mengunggah file `.py` atau menempelkan kode Python hasil Antigravity/OpenCode/Codex, menjalankan **Audit AST & Uji Kontrak Hoare**, lalu mengikatnya ke Library Komponen AMCA.
