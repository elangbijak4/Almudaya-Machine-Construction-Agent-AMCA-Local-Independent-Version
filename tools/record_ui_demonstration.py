"""Automated script to record demonstration video and capture step-by-step screenshots.

Drives the live Streamlit UI at http://localhost:8502 using Playwright and Google Chrome.
Generates:
1. docs/demonstration/video/*.webm (Authentic video recording of the entire session)
2. docs/demonstration/screenshots/*.png (High-resolution step-by-step screenshots)
3. Animated walkthrough GIF if PIL is available.
"""
from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from PIL import Image
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1]
DEMO_DIR = ROOT / "docs" / "demonstration"
SCREENSHOTS_DIR = DEMO_DIR / "screenshots"
VIDEO_DIR = DEMO_DIR / "video"

SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
VIDEO_DIR.mkdir(parents=True, exist_ok=True)


def record_demo() -> None:
    print("[1/5] Launching Playwright with Chrome...")
    with sync_playwright() as p:
        browser = p.chromium.launch(
            executable_path="C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            headless=True,
            args=["--disable-gpu", "--no-sandbox"],
        )

        context = browser.new_context(
            viewport={"width": 1280, "height": 800},
            record_video_dir=str(VIDEO_DIR),
            record_video_size={"width": 1280, "height": 800},
        )
        page = context.new_page()

        print("[2/5] Navigating to http://localhost:8502...")
        page.goto("http://localhost:8502", wait_until="networkidle", timeout=60000)
        time.sleep(3)

        # Scene 1: Initial 9Router Dashboard
        print("  Capturing Scene 1: Initial Dashboard (9Router)...")
        page.screenshot(path=str(SCREENSHOTS_DIR / "01_dashboard_9router.png"), full_page=False)

        # Scene 2: Switch Provider to Gemini
        print("  Capturing Scene 2: Dynamic Provider Switching (Gemini)...")
        sidebar_selectboxes = page.locator('[data-testid="stSidebar"] [data-testid="stSelectbox"]')
        if sidebar_selectboxes.count() > 0:
            provider_sb = sidebar_selectboxes.nth(0)
            provider_sb.click()
            time.sleep(0.5)
            # Click 'Gemini' option in popup
            gemini_opt = page.locator('li[role="option"]:has-text("Gemini")').first
            if gemini_opt.count() > 0:
                gemini_opt.click()
                time.sleep(2)
                page.screenshot(path=str(SCREENSHOTS_DIR / "02_provider_gemini.png"), full_page=False)

        # Scene 3: Switch Provider to Offline Deterministic
        print("  Capturing Scene 3: Air-Gapped Mode (Offline Deterministic)...")
        if sidebar_selectboxes.count() > 0:
            provider_sb = sidebar_selectboxes.nth(0)
            provider_sb.click()
            time.sleep(0.5)
            offline_opt = page.locator('li[role="option"]:has-text("Offline Deterministic")').first
            if offline_opt.count() > 0:
                offline_opt.click()
                time.sleep(2)
                page.screenshot(path=str(SCREENSHOTS_DIR / "03_provider_offline_airgapped.png"), full_page=False)

        # Scene 4: Load Example YAML & Validate
        print("  Capturing Scene 4: Loading Example YAML & Structural Validation...")
        # Main area example selectbox
        main_selectboxes = page.locator('[data-testid="stMain"] [data-testid="stSelectbox"]')
        if main_selectboxes.count() > 0:
            main_sb = main_selectboxes.nth(0)
            main_sb.click()
            time.sleep(0.5)
            opt_valid = page.locator('li[role="option"]:has-text("valid_parallel_analysis")').first
            if opt_valid.count() > 0:
                opt_valid.click()
                time.sleep(1)

        # Click 'Muat contoh ke editor'
        btn_load = page.locator('button:has-text("Muat contoh ke editor")').first
        if btn_load.count() > 0:
            btn_load.click()
            time.sleep(2)
            page.screenshot(path=str(SCREENSHOTS_DIR / "04_example_yaml_loaded.png"), full_page=False)

        # Click 'Validasi YAML saat ini'
        print("  Capturing Scene 5: Formal Proof (PROVED) & DAG Graph...")
        btn_val = page.locator('button:has-text("Validasi YAML saat ini")').first
        if btn_val.count() > 0:
            btn_val.click()
            time.sleep(3)
            # Scroll down to graphviz DAG
            page.evaluate("window.scrollBy(0, 500)")
            time.sleep(1)
            page.screenshot(path=str(SCREENSHOTS_DIR / "05_formal_verification_and_dag.png"), full_page=False)

        # Scene 6: Approve Execution & Run Machine
        print("  Capturing Scene 6: Runtime Execution...")
        cb_approve = page.locator('label:has-text("Saya menyetujui eksekusi mesin ini")').first
        if cb_approve.count() > 0:
            cb_approve.click()
            time.sleep(1)
            btn_run = page.locator('button:has-text("Jalankan mesin")').first
            if btn_run.count() > 0:
                btn_run.click()
                time.sleep(3)
                page.evaluate("window.scrollBy(0, 400)")
                time.sleep(1)
                page.screenshot(path=str(SCREENSHOTS_DIR / "06_runtime_execution_succeeded.png"), full_page=False)

        # Scene 7: Two-Stage Approval & Construction
        print("  Capturing Scene 7: Two-Stage Approval & Handover ZIP Construction...")
        # Open Section 6 expander if closed
        expander = page.locator('div[data-testid="stExpander"] details').first
        if expander.count() > 0:
            # Check if not open
            is_open = expander.get_attribute("open") is not None
            if not is_open:
                expander.locator("summary").click()
                time.sleep(1)

        btn_app_spec = page.locator('button:has-text("1. Kunci Persetujuan Spesifikasi")').first
        if btn_app_spec.count() > 0:
            btn_app_spec.click()
            time.sleep(2)

        btn_app_construct = page.locator('button:has-text("2. Setujui Konstruksi & Bangun Paket Handover ZIP")').first
        if btn_app_construct.count() > 0:
            btn_app_construct.click()
            time.sleep(5)
            page.evaluate("window.scrollBy(0, 500)")
            time.sleep(1)
            page.screenshot(path=str(SCREENSHOTS_DIR / "07_handover_zip_package_ready.png"), full_page=False)

        # Scene 8: Error Fly-Window Modal Demonstration (@st.dialog)
        print("  Capturing Scene 8: Error Diagnostics Fly-Window Modal (@st.dialog)...")
        # Scroll back up to YAML text area
        page.evaluate("window.scrollTo(0, 400)")
        time.sleep(1)

        # Put broken YAML into textarea
        yaml_ta = page.locator('textarea').nth(1)
        if yaml_ta.count() > 0:
            yaml_ta.fill("schema_version: '1.0'\nmalformed_yaml: [missing end bracket\n")
            time.sleep(1)

        if btn_val.count() > 0:
            btn_val.click()
            time.sleep(2)

        # Click 'Diagnosa Masalah Validasi' button
        btn_diag = page.locator('button:has-text("Diagnosa Masalah Validasi")').first
        if btn_diag.count() > 0:
            btn_diag.click()
            time.sleep(2)
            # Fly-window dialog should now be open!
            page.screenshot(path=str(SCREENSHOTS_DIR / "08_fly_window_error_modal.png"), full_page=False)

            # Close dialog via Tutup Jendela
            btn_close_modal = page.locator('button:has-text("Tutup Jendela")').first
            if btn_close_modal.count() > 0:
                btn_close_modal.click()
                time.sleep(2)
                page.screenshot(path=str(SCREENSHOTS_DIR / "09_sidebar_reopen_button.png"), full_page=False)

        print("[3/5] Finalizing video recording...")
        page.close()
        context.close()
        browser.close()

    # Find the generated video file
    video_files = list(VIDEO_DIR.glob("*.webm"))
    if video_files:
        main_video = VIDEO_DIR / "amca_ui_demonstration.webm"
        if main_video.exists():
            main_video.unlink()
        video_files[0].rename(main_video)
        print(f"[4/5] Video saved: {main_video} ({main_video.stat().st_size} bytes)")

    # Generate Animated GIF from screenshots
    print("[5/5] Generating animated walkthrough GIF...")
    screenshots = sorted(SCREENSHOTS_DIR.glob("*.png"))
    if screenshots:
        images = [Image.open(s).resize((960, 600)) for s in screenshots]
        gif_path = DEMO_DIR / "amca_ui_walkthrough.gif"
        images[0].save(
            gif_path,
            save_all=True,
            append_images=images[1:],
            duration=2500,  # 2.5 seconds per slide
            loop=0,
        )
        print(f"Animated GIF created: {gif_path} ({gif_path.stat().st_size} bytes)")

    print("Demonstration recording successfully completed!")


if __name__ == "__main__":
    record_demo()
