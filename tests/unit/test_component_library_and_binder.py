"""Unit tests for Component Library (amca_components) and AST Security Binder (RF-01, RF-02).

Zero-mocking: Tests execute real AST parsing, genuine sandbox compilation, real Hoare contract
guards, and runtime library dispatch.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from amca.registry import BUILTIN_COMPONENT_IDS, component_ids
from amca_agent.component_binder import (
    ComponentBindingError,
    ComponentSecurityError,
    audit_component_source_ast,
    bind_component_from_python_source,
    bind_external_component_file,
)
from amca_agent.custom_components import (
    clear_all_custom_components,
    list_custom_component_specs,
)
from amca_components import (
    COMPONENT_DISPATCH,
    ContractViolationError,
    execute_library_component,
)


class ComponentLibraryAndBinderTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_all_custom_components(persist=False)

    def tearDown(self) -> None:
        clear_all_custom_components(persist=False)

    def test_ast_security_gate_allows_pure_deterministic_modules(self) -> None:
        valid_source = """
import re
import math
import json
from typing import Any

def clean_text(text: str) -> str:
    \"\"\"Strip non-alphanumeric chars and normalize whitespace.\"\"\"
    cleaned = re.sub(r'[^\\w\\s]', '', text or '').strip()
    return ' '.join(cleaned.split())
"""
        report = audit_component_source_ast(valid_source)
        self.assertTrue(report.passed)
        self.assertIn("re", report.imported_modules)
        self.assertIn("clean_text", report.defined_functions)
        self.assertTrue(len(report.source_sha256) == 64)

    def test_ast_security_gate_fails_closed_on_forbidden_imports(self) -> None:
        bad_imports = [
            "import os\ndef f(x): return x",
            "import sys\ndef f(x): return x",
            "import subprocess\ndef f(x): return x",
            "import socket\ndef f(x): return x",
            "import urllib.request\ndef f(x): return x",
            "import pathlib\ndef f(x): return x",
            "import shutil\ndef f(x): return x",
            "import pickle\ndef f(x): return x",
            "import ctypes\ndef f(x): return x",
            "from os import path\ndef f(x): return x",
            "from subprocess import Popen\ndef f(x): return x",
            "from math import *\ndef f(x): return x",  # Wildcard import forbidden
        ]
        for src in bad_imports:
            with self.subTest(src=src):
                with self.assertRaises(ComponentSecurityError):
                    audit_component_source_ast(src)

    def test_ast_security_gate_fails_closed_on_forbidden_calls_and_dunders(self) -> None:
        bad_calls = [
            "def f(x):\n    eval('1+1')\n    return x",
            "def f(x):\n    exec('x = 1')\n    return x",
            "def f(x):\n    open('secret.txt', 'r')\n    return x",
            "def f(x):\n    __import__('os')\n    return x",
            "def f(x):\n    return getattr(x, 'name')",
            "def f(x):\n    return x.__class__.__subclasses__()",
            "def f(x):\n    return globals()",
            "def f(x):\n    return locals()",
        ]
        for src in bad_calls:
            with self.subTest(src=src):
                with self.assertRaises(ComponentSecurityError):
                    audit_component_source_ast(src)

    def test_bind_plain_python_function_format_b_with_auto_inference(self) -> None:
        plain_py = """
import re

def strip_accents_and_clean(text: str) -> str:
    \"\"\"Menghapus karakter non-ASCII dan spasi berlebih.\"\"\"
    cleaned = re.sub(r'[^\\w\\s]', '', text or '').strip()
    return ' '.join(cleaned.split())
"""
        record = bind_component_from_python_source(
            plain_py,
            component_id="strip_accents_and_clean",
            alias="custom.strip_accents_and_clean",
            persist=False,
        )
        self.assertEqual(record.spec.component_id, "strip_accents_and_clean")
        self.assertIn("strip_accents_and_clean", component_ids())
        self.assertIn("strip_accents_and_clean", COMPONENT_DISPATCH)
        self.assertTrue(record.precondition_rejection_verified)

        # Test runtime execution via amca_components library dispatch
        sample_in = {"text": "Hello,   world!!!  "}
        out = execute_library_component("strip_accents_and_clean", sample_in, {}, sample_in)
        self.assertEqual(out["text"], "Hello world")

        # Test runtime Hoare precondition guard: empty input must raise ContractViolationError
        with self.assertRaises(ContractViolationError):
            execute_library_component("strip_accents_and_clean", {"text": ""}, {}, {})

    def test_bind_explicit_meta_component_format_a(self) -> None:
        explicit_py = """
import re
from typing import Any

AMCA_COMPONENT_META = {
    "component_id": "count_vowels",
    "alias": "custom.count_vowels",
    "name": "Vowel Counter",
    "role": "Count vowels in text and return metric object.",
    "input_ports": {"text": "string"},
    "output_ports": {"finding": "object"},
    "config_keys": ["include_y"],
    "default_config": {"include_y": False},
}

def run_count_vowels(inputs: dict[str, Any], config: dict[str, Any], raw_inputs: dict[str, Any]) -> dict[str, Any]:
    text = str(inputs.get("text", ""))
    vowels = "aiueo" + ("y" if config.get("include_y") else "")
    hits = sum(1 for c in text.lower() if c in vowels)
    return {
        "finding": {
            "vowel_hits": hits,
            "character_count": len(text),
            "word_count": len(text.split()),
            "custom_metric": hits,
            "summary": f"vowels={hits}",
        }
    }
"""
        record = bind_component_from_python_source(explicit_py, persist=False)
        self.assertEqual(record.spec.component_id, "count_vowels")
        self.assertIn("count_vowels", component_ids())

        out = execute_library_component(
            "count_vowels",
            {"text": "The quick brown fox jumps over the lazy dog"},
            {"include_y": True},
            {"text": "The quick brown fox jumps over the lazy dog"},
        )
        self.assertIsInstance(out["finding"], dict)
        self.assertIn("vowel_hits", out["finding"])
        self.assertGreater(out["finding"]["vowel_hits"], 0)

    def test_bind_external_file_on_disk(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            py_file = Path(td) / "custom_sentiment.py"
            py_file.write_text(
                """
import re

def custom_sentiment(text: str) -> dict:
    \"\"\"Analyze simple sentiment tone.\"\"\"
    words = set(re.findall(r'\\w+', (text or '').lower()))
    pos = len(words & {'good', 'great', 'valid', 'clean', 'proved'})
    neg = len(words & {'bad', 'error', 'failed', 'invalid'})
    score = pos - neg
    return {
        "score": score,
        "tone": "positive" if score > 0 else ("negative" if score < 0 else "neutral"),
    }
""",
                encoding="utf-8",
            )
            record = bind_external_component_file(
                py_file,
                component_id="custom_sentiment",
                persist=False,
            )
            self.assertEqual(record.spec.component_id, "custom_sentiment")
            self.assertIn("custom_sentiment", component_ids())

            out = execute_library_component("custom_sentiment", {"text": "This is a great clean proved machine"}, {}, {})
            self.assertIsInstance(out["finding"], dict)
            self.assertEqual(out["finding"]["score"], 3)
            self.assertEqual(out["finding"]["tone"], "positive")


if __name__ == "__main__":
    unittest.main()
