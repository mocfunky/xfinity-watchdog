import json
import os
import subprocess
import sys
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path

import requests
from flask import Flask, jsonify, send_from_directory
from playwright.sync_api import sync_playwright

# ── Config ────────────────────────────────────────────────────────────────────
RUN_MINUTES             = [15, 45]
UPLOAD_THRESHOLD_MBPS   = float(os.getenv("UPLOAD_THRESHOLD_MBPS", "100"))
MAX_ATTEMPTS            = int(os.getenv("MAX_ATTEMPTS", "3"))
RETRY_WAIT_SECONDS      = int(os.getenv("RETRY_WAIT_SECONDS", "30"))
DISCORD_WEBHOOK_URL     = os.getenv("DISCORD_WEBHOOK_URL", "").strip()
ENABLE_REBOOT           = os.getenv("ENABLE_REBOOT", "false").lower() == "true"
MODEM_URL               = os.getenv("MODEM_URL", "http://10.0.0.1").rstrip("/")
MODEM_USERNAME          = os.getenv("MODEM_USERNAME", "admin")
MODEM_PASSWORD          = os.getenv("MODEM_PASSWORD", "")
REBOOT_ESCALATION_COUNT = int(os.getenv("REBOOT_ESCALATION_COUNT", "3"))
DASHBOARD_PORT          = int(os.getenv("DASHBOARD_PORT", "8080"))
LOG_PATH                = "/logs/watchdog.log"
STATE_PATH              = "/logs/state.json"
DASHBOARD_DIR           = Path(__file__).parent / "dashboard"

# ── Default state shape ───────────────────────────────────────────────────────
DEFAULT_STATE = {
    "reboot_streak":    0,
    "last_reboot_time": None,
    "total_reboots":    0,
    "last_speed":       None,
    "last_check_time":  None,
    "next_check_time":  None,
    "recent_speeds":    [],
    "recent_reboots":   [],
    "recent_checks":    [],
}

state_lock = threading.Lock()


# ── Persist state to /logs/state.json ────────────────────────────────────────
def load_state() -> dict:
    try:
        with open(STATE_PATH, "r", encoding="utf-8") as f:
            saved = json.load(f)
        # Merge with defaults so new keys added later don't break old files
        merged = dict(DEFAULT_STATE)
        merged.update(saved)
        return merged
    except Exception:
        return dict(DEFAULT_STATE)


def save_state(s: dict) -> None:
    try:
        with open(STATE_PATH, "w", encoding="utf-8") as f:
            json.dump(s, f, indent=2)
    except Exception as e:
        log(f"Failed to save state: {e}")


# Load state at startup so history survives container restarts
state = load_state()


# ── Logging ───────────────────────────────────────────────────────────────────
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


# ── Scheduler ─────────────────────────────────────────────────────────────────
def seconds_until_next_run(target_minutes: list) -> tuple:
    now = datetime.now()
    soonest_seconds = None
    soonest_minute  = None
    for minute in target_minutes:
        target = now.replace(minute=minute, second=0, microsecond=0)
        if now >= target:
            target += timedelta(hours=1)
        diff = int((target - now).total_seconds())
        if soonest_seconds is None or diff < soonest_seconds:
            soonest_seconds = diff
            soonest_minute  = minute
    return max(1, soonest_seconds), soonest_minute


# ── Speed test ────────────────────────────────────────────────────────────────
def run_speedtest():
    try:
        result = subprocess.run(
            ["speedtest", "--accept-license", "--accept-gdpr", "-f", "json"],
            capture_output=True, text=True, timeout=180, check=False,
        )
        if result.returncode != 0:
            log(f"Speed test failed: {(result.stderr or result.stdout).strip()}")
            return None
        data        = json.loads(result.stdout)
        upload_mbps = (data["upload"]["bandwidth"] * 8) / 1_000_000
        return round(upload_mbps, 2)
    except Exception as e:
        log(f"Speed test exception: {e}")
        return None


# ── Modem reboot ──────────────────────────────────────────────────────────────
def _fill_first(page, selectors, value):
    for sel in selectors:
        try:
            loc = page.locator(sel)
            for i in range(loc.count()):
                item = loc.nth(i)
                if item.is_visible():
                    item.fill(value)
                    return True
        except Exception:
            pass
    return False


def _click_first_visible(page, selectors):
    for sel in selectors:
        try:
            loc = page.locator(sel)
            for i in range(loc.count()):
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
            page    = browser.new_page(viewport={"width": 1440, "height": 1000})

            log("Opening modem login page.")
            page.goto(MODEM_URL, wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            _fill_first(page, [
                'input[name="username"]', 'input[name="user"]',
                'input[id*="user" i]', 'input[placeholder*="user" i]',
                'input[type="text"]',
            ], MODEM_USERNAME)

            if not _fill_first(page, [
                'input[type="password"]', 'input[name="password"]',
                'input[id*="pass" i]', 'input[placeholder*="password" i]',
            ], MODEM_PASSWORD):
                log("Could not find password field.")
                return False

            if not _click_first_visible(page, [
                'button[type="submit"]', 'input[type="submit"]',
                'button:has-text("Log In")', 'button:has-text("Login")',
                'text=Log In', 'text=Login',
            ]):
                page.keyboard.press("Enter")
            page.wait_for_timeout(3000)

            log("Opening restore/reboot page.")
            page.goto(f"{MODEM_URL}/restore_reboot.jst", wait_until="domcontentloaded", timeout=30000)
            page.wait_for_timeout(2000)

            cookie_map  = {c["name"]: c["value"] for c in page.context.cookies()}
            duksid      = cookie_map.get("DUKSID")
            csrfp_token = cookie_map.get("csrfp_token")

            if not duksid or not csrfp_token:
                log(f"Missing cookies. DUKSID={bool(duksid)} csrfp_token={bool(csrfp_token)}")
                return False

            log("Got session cookies.")
            s = requests.Session()
            s.headers.update({
                "User-Agent":       "Mozilla/5.0",
                "X-Requested-With": "XMLHttpRequest",
                "Referer":          f"{MODEM_URL}/restore_reboot.jst",
                "Origin":           MODEM_URL,
            })
            s.cookies.set("DUKSID",      duksid)
            s.cookies.set("csrfp_token", csrfp_token)

            r1 = s.post(
                f"{MODEM_URL}/actionHandler/ajaxSet_Reset_Restore.jst",
                data={"resetInfo": '["btn1","Device","admin"]', "csrfp_token": csrfp_token},
                timeout=15,
            )
            log(f"Reset POST {r1.status_code}: {r1.text.strip()[:300]}")
            if r1.status_code != 200:
                return False

            r2 = s.get(
                f"{MODEM_URL}/actionHandler/ajaxSet_mta_Line_Diagnostics.jst",
                params={"get_statusx": "true", "restore_reboot": "true"},
                timeout=15,
            )
            log(f"Reboot GET {r2.status_code}: {r2.text.strip()[:300]}")
            return r2.status_code == 200

    except Exception as e:
        log(f"Reboot automation failed: {e}")
        return False
    finally:
        if browser:
            try:
                browser.close()
            except Exception:
                pass


# ── Main check logic ──────────────────────────────────────────────────────────
def run_check() -> bool:
    results = []
    log(f"Starting check. threshold={UPLOAD_THRESHOLD_MBPS} Mbps, attempts={MAX_ATTEMPTS}")

    for attempt in range(1, MAX_ATTEMPTS + 1):
        upload = run_speedtest()
        ts     = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        if upload is None:
            results.append("fail")
            log(f"Test {attempt}: FAILED")
        else:
            results.append(upload)
            log(f"Test {attempt}: {upload} Mbps")
            with state_lock:
                state["last_speed"] = upload
                state["recent_speeds"].append({"time": ts, "speed": upload})
                state["recent_speeds"] = state["recent_speeds"][-50:]

        if upload is not None and upload >= UPLOAD_THRESHOLD_MBPS:
            log("Upload is good. No action needed.")
            with state_lock:
                if state["reboot_streak"] > 0:
                    notify(f"✅ Upload recovered after {state['reboot_streak']} reboot(s). Back to {upload} Mbps.")
                    state["reboot_streak"] = 0
                state["last_check_time"] = ts
                state["recent_checks"].append({"time": ts, "result": "good", "speed": upload})
                state["recent_checks"] = state["recent_checks"][-50:]
                save_state(state)
            return True

        if attempt < MAX_ATTEMPTS:
            log(f"Waiting {RETRY_WAIT_SECONDS}s before retry.")
            time.sleep(RETRY_WAIT_SECONDS)

    # All tests failed — reboot
    speeds_str = ", ".join(str(r) for r in results)
    notify(
        f"⚠️ Upload LOW after {MAX_ATTEMPTS} tests: [{speeds_str}]. "
        f"Threshold={UPLOAD_THRESHOLD_MBPS} Mbps. Rebooting modem."
    )

    ok = reboot_modem()
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    with state_lock:
        state["last_check_time"] = ts
        if ok:
            state["reboot_streak"]   += 1
            state["total_reboots"]   += 1
            state["last_reboot_time"] = ts
            state["recent_reboots"].append({"time": ts, "speeds_before": speeds_str})
            state["recent_reboots"] = state["recent_reboots"][-20:]
            state["recent_checks"].append({
                "time": ts, "result": "rebooted",
                "speed": results[-1] if isinstance(results[-1], float) else None,
            })
            notify(f"🔄 Modem reboot sent. (#{state['reboot_streak']} in a row)")
            if state["reboot_streak"] >= REBOOT_ESCALATION_COUNT:
                notify(
                    f"🚨 Hey, something's wrong — the modem has been rebooted "
                    f"**{state['reboot_streak']} times in a row** and upload is still not recovering. "
                    f"It's not fixing itself. You may need to manually check the modem or call Xfinity."
                )
        else:
            state["recent_checks"].append({"time": ts, "result": "reboot_failed", "speed": None})
            notify("❌ Upload was low but modem reboot failed.")
        state["recent_checks"] = state["recent_checks"][-50:]
        save_state(state)

    return False


# ── Flask dashboard ───────────────────────────────────────────────────────────
app = Flask(__name__)

@app.route("/")
def index():
    return send_from_directory(str(DASHBOARD_DIR), "index.html")

@app.route("/api/status")
def api_status():
    wait_s, _ = seconds_until_next_run(RUN_MINUTES)
    next_run  = (datetime.now() + timedelta(seconds=wait_s)).strftime("%H:%M")
    with state_lock:
        return jsonify({
            "threshold_mbps":  UPLOAD_THRESHOLD_MBPS,
            "last_speed":      state["last_speed"],
            "last_check_time": state["last_check_time"],
            "next_check_time": f"~{next_run}",
            "reboot_streak":   state["reboot_streak"],
            "total_reboots":   state["total_reboots"],
            "recent_speeds":   state["recent_speeds"][-12:],
            "recent_reboots":  state["recent_reboots"][-5:],
            "recent_checks":   state["recent_checks"][-8:],
        })

def start_dashboard():
    log(f"Dashboard starting on http://0.0.0.0:{DASHBOARD_PORT}")
    app.run(host="0.0.0.0", port=DASHBOARD_PORT, debug=False, use_reloader=False)


# ── Entry point ───────────────────────────────────────────────────────────────
def main_loop() -> None:
    log("Xfinity watchdog started.")
    log(f"Scheduled checks at :{RUN_MINUTES[0]} and :{RUN_MINUTES[1]} every hour.")
    log(f"State loaded from {STATE_PATH}: {state['total_reboots']} total reboots on record.")

    threading.Thread(target=start_dashboard, daemon=True).start()

    while True:
        wait_s, next_min = seconds_until_next_run(RUN_MINUTES)
        next_run = datetime.now() + timedelta(seconds=wait_s)
        with state_lock:
            state["next_check_time"] = next_run.strftime("%Y-%m-%d %H:%M:%S")
        log(f"Sleeping {wait_s}s until :{next_min:02d} ({next_run.strftime('%H:%M:%S')})")
        time.sleep(wait_s)
        run_check()


if __name__ == "__main__":
    if "--run-now" in sys.argv:
        log("Manual run requested.")
        run_check()
        sys.exit(0)
    if "--reboot-now" in sys.argv:
        log("Manual reboot requested.")
        sys.exit(0 if reboot_modem() else 1)
    main_loop()
