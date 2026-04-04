import json
import os
import subprocess
import sys
import time
from datetime import datetime, timedelta

import requests
from playwright.sync_api import sync_playwright


RUN_MINUTE = int(os.getenv("RUN_MINUTE", "30"))
UPLOAD_THRESHOLD_MBPS = float(os.getenv("UPLOAD_THRESHOLD_MBPS", "100"))
MAX_ATTEMPTS = int(os.getenv("MAX_ATTEMPTS", "3"))
RETRY_WAIT_SECONDS = int(os.getenv("RETRY_WAIT_SECONDS", "30"))

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL", "").strip()

ENABLE_REBOOT = os.getenv("ENABLE_REBOOT", "false").lower() == "true"
MODEM_URL = os.getenv("MODEM_URL", "http://10.0.0.1").rstrip("/")
MODEM_USERNAME = os.getenv("MODEM_USERNAME", "admin")
MODEM_PASSWORD = os.getenv("MODEM_PASSWORD", "")

LOG_PATH = "/logs/watchdog.log"


def log(msg: str) -> None:
    line = f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}"
    print(line, flush=True)
    try:
        with open(LOG_PATH, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def notify(msg: str) -> None:
    log(f"NOTIFY: {msg}")
    if not DISCORD_WEBHOOK_URL:
        return
    try:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": msg}, timeout=10)
    except Exception as e:
        log(f"Discord notification failed: {e}")


def seconds_until_next_run(target_minute: int) -> int:
    now = datetime.now()
    target = now.replace(minute=target_minute, second=0, microsecond=0)
    if now >= target:
        target += timedelta(hours=1)
    return max(1, int((target - now).total_seconds()))


def run_speedtest() -> float | None:
    try:
        result = subprocess.run(
            ["speedtest", "--accept-license", "--accept-gdpr", "-f", "json"],
            capture_output=True,
            text=True,
            timeout=180,
            check=False,
        )

        if result.returncode != 0:
            err = (result.stderr or result.stdout).strip()
            log(f"Speed test failed: {err}")
            return None

        data = json.loads(result.stdout)
        upload_bandwidth = data["upload"]["bandwidth"]
        upload_mbps = (upload_bandwidth * 8) / 1_000_000
        return round(upload_mbps, 2)

    except Exception as e:
        log(f"Speed test exception: {e}")
        return None


def _fill_first(page, selectors, value: str) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel)
            count = loc.count()
            for i in range(count):
                item = loc.nth(i)
                if item.is_visible():
                    item.fill(value)
                    return True
        except Exception:
            pass
    return False


def _click_first_visible(page, selectors) -> bool:
    for sel in selectors:
        try:
            loc = page.locator(sel)
            count = loc.count()
            for i in range(count):
                item = loc.nth(i)
                if item.is_visible():
                    item.click(timeout=5000)
                    return True
        except Exception:
            pass
    return False


def reboot_modem() -> bool:
    if not ENABLE_REBOOT:
        log("Reboot skipped: ENABLE_REBOOT is false.")
        return False

    if not MODEM_PASSWORD:
        log("Reboot skipped: MODEM_PASSWORD is empty.")
        return False

    browser = None
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page(viewport={"width": 1440, "height": 1000})

            log("Opening modem login page.")
            page.goto(MODEM_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            username_ok = _fill_first(page, [
                'input[name="username"]',
                'input[name="user"]',
                'input[id*="user" i]',
                'input[placeholder*="user" i]',
                'input[type="text"]',
            ], MODEM_USERNAME)

            password_ok = _fill_first(page, [
                'input[type="password"]',
                'input[name="password"]',
                'input[id*="pass" i]',
                'input[placeholder*="password" i]',
            ], MODEM_PASSWORD)

            if not password_ok:
                log("Could not find password field.")
                return False

            log("Filled username and password." if username_ok else "Filled password only.")

            submitted = _click_first_visible(page, [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:has-text("Log In")',
                'button:has-text("Login")',
                'text=Log In',
                'text=Login',
            ])

            if not submitted:
                page.keyboard.press("Enter")

            page.wait_for_timeout(3000)

            log("Opening restore/reboot page.")
            page.goto(f"{MODEM_URL}/restore_reboot.jst", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            cookies = page.context.cookies()
            cookie_map = {c["name"]: c["value"] for c in cookies}

            duksid = cookie_map.get("DUKSID")
            csrfp_token = cookie_map.get("csrfp_token")

            if not duksid or not csrfp_token:
                log(f"Missing required cookies. DUKSID={bool(duksid)} csrfp_token={bool(csrfp_token)}")
                return False

            log("Got authenticated session cookies.")

            s = requests.Session()
            s.headers.update({
                "User-Agent": "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest",
                "Referer": f"{MODEM_URL}/restore_reboot.jst",
                "Origin": MODEM_URL,
            })

            s.cookies.set("DUKSID", duksid)
            s.cookies.set("csrfp_token", csrfp_token)

            post_url = f"{MODEM_URL}/actionHandler/ajaxSet_Reset_Restore.jst"
            post_data = {
                "resetInfo": '["btn1","Device","admin"]',
                "csrfp_token": csrfp_token,
            }

            log("Sending reset POST request.")
            r1 = s.post(post_url, data=post_data, timeout=15)
            log(f"Reset POST status: {r1.status_code}")
            log(f"Reset POST response: {r1.text.strip()[:500]}")

            if r1.status_code != 200:
                return False

            get_url = f"{MODEM_URL}/actionHandler/ajaxSet_mta_Line_Diagnostics.jst"
            params = {
                "get_statusx": "true",
                "restore_reboot": "true",
            }

            log("Sending reboot/status GET request.")
            r2 = s.get(get_url, params=params, timeout=15)
            log(f"Reboot GET status: {r2.status_code}")
            log(f"Reboot GET response: {r2.text.strip()[:500]}")

            if r2.status_code != 200:
                return False

            log("Reboot backend request sequence sent.")
            return True

    except Exception as e:
        log(f"Reboot automation failed: {e}")
        return False

    finally:
        if browser is not None:
            try:
                browser.close()
            except Exception:
                pass


def run_check() -> bool:
    results = []

    log(f"Starting check. threshold={UPLOAD_THRESHOLD_MBPS} Mbps, attempts={MAX_ATTEMPTS}")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        upload = run_speedtest()

        if upload is None:
            results.append("fail")
            log(f"Test {attempt}: FAILED")
        else:
            results.append(upload)
            log(f"Test {attempt}: {upload} Mbps")
            if upload >= UPLOAD_THRESHOLD_MBPS:
                log("Upload is good. No action needed.")
                return True

        if attempt < MAX_ATTEMPTS:
            log(f"Waiting {RETRY_WAIT_SECONDS} seconds before retry.")
            time.sleep(RETRY_WAIT_SECONDS)

    notify(
        f"Upload LOW after {MAX_ATTEMPTS} tests: {results}. "
        f"Threshold={UPLOAD_THRESHOLD_MBPS} Mbps. Rebooting modem."
    )

    ok = reboot_modem()

    if ok:
        notify("Modem reboot command sent.")
    else:
        notify("Upload was low, but modem reboot failed.")

    return False


def main_loop() -> None:
    log("Xfinity watchdog started.")
    while True:
        wait_seconds = seconds_until_next_run(RUN_MINUTE)
        next_run = datetime.now() + timedelta(seconds=wait_seconds)
        log(f"Sleeping {wait_seconds} seconds until next scheduled run at {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
        time.sleep(wait_seconds)
        run_check()


if __name__ == "__main__":
    if "--run-now" in sys.argv:
        log("Manual run requested.")
        run_check()
        sys.exit(0)

    if "--reboot-now" in sys.argv:
        log("Manual reboot requested.")
        ok = reboot_modem()
        sys.exit(0 if ok else 1)

    main_loop()