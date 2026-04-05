🚀 Xfinity Upload Watchdog

Automatically monitor your upload speed, track history, and reboot your Xfinity modem when performance drops.

---

## ⚠️ Why This Exists

If you use Xfinity, you’ve probably seen this:

* Download speeds are fine ✅
* Upload suddenly drops far below normal ❌
* Restarting the modem instantly fixes it 🔄

This is a common issue with many Xfinity gateways and DOCSIS networks:

* Upload channels can degrade or get stuck
* Signal conditions fluctuate throughout the day
* The modem doesn’t always recover on its own
* A simple reboot often restores full upload speed

👉 This tool automates that process.

---

## 📡 Important: Know Your Plan Speeds

Xfinity upload speeds vary depending on your plan.

Typical DOCSIS upload tiers:

| Plan Type         | Typical Upload |
| ----------------- | -------------- |
| Lower tiers       | 10–20 Mbps     |
| Mid tiers         | 20–50 Mbps     |
| Higher tiers      | 100–200 Mbps   |
| 2 Gig+ / Next Gen | 200–400+ Mbps  |

⚠️ Important:

* High upload speeds (200–400 Mbps) are usually only available on newer plans
* Set your threshold based on your **normal performance**, not max advertised

---

## 🎯 What This Tool Fixes

This is **NOT for slow plans**.

This is for when:

* You normally get **200–400 Mbps upload**
* But suddenly drop to **20–80 Mbps**
* And a reboot fixes it

👉 This detects and fixes that automatically.

---

## 🧠 What It Does

Every scheduled interval (default: **:15 and :45 each hour**):

* Runs a Speedtest
* Checks your upload speed
* If below threshold:

  * Retries multiple times
* If still below threshold:

  * Logs into your modem
  * Sends the real backend reboot command
  * Tracks reboot history and streaks

---

## ⚙️ Features

### 📊 Monitoring & Automation

* 📡 Accurate Speedtest (Ookla CLI)
* 🔁 Retry logic with configurable attempts
* 🔌 Automatic modem reboot when needed
* ⏱️ Scheduled checks (:15 / :45 default)

### 📈 Dashboard (NEW)

* 🖥️ Web UI dashboard (Flask)
* 📊 Upload speed chart (last checks)
* 🔄 Reboot history list
* 📋 Check log (good / reboot / failed)
* ⚡ Auto-refresh (every 60s)
* 🎯 Threshold visualization

### 💾 Persistence (NEW)

* Saves history to `/logs/state.json`
* Survives container restarts
* Tracks:

  * recent speeds
  * reboot history
  * check results
  * reboot streaks

### 🚨 Alerts

* 🔔 Optional Discord notifications
* 🚨 Escalation warning after repeated failures

### ⚡ Smart Tracking

* Reboot streak detection
* Recovery detection ("back to normal")
* Prevents silent failures

### 🐳 Deployment

* Docker-based
* Raspberry Pi friendly
* Lightweight

---

## 🖥️ Requirements

* Xfinity modem/router with local UI (`http://10.0.0.1`)
* Docker + Docker Compose
* Modem admin credentials

---

## 📦 Installation

```bash
git clone https://github.com/YOUR_USERNAME/xfinity-upload-watchdog.git
cd xfinity-upload-watchdog
```

Edit config:

```bash
nano docker-compose.yml
```

Set your modem password:

```yaml
MODEM_PASSWORD: "your_password_here"
```

Start it:

```bash
docker compose up -d
```

---

## 📁 Volumes (IMPORTANT)

Make sure logs are persisted:

```yaml
volumes:
  - /home/YOUR_USER/xfinity-watchdog:/app
  - /home/YOUR_USER/xfinity-watchdog/logs:/logs
```

👉 Without this, history will reset on restart.

---

## 🌐 Dashboard

Once running:

```
http://YOUR_DEVICE_IP:8080
```

Shows:

* Live upload status
* Speed history chart
* Reboot history
* Check logs
* Threshold tracking

---

## 🔍 Configuration

```yaml
UPLOAD_THRESHOLD_MBPS: "100"
MAX_ATTEMPTS: "3"
RETRY_WAIT_SECONDS: "30"
DISCORD_WEBHOOK_URL: ""
ENABLE_REBOOT: "true"
```

---

## ⚙️ Choosing the Right Threshold

Set based on your **normal upload speed**:

| Plan         | Suggested Threshold |
| ------------ | ------------------- |
| 20 Mbps      | 15                  |
| 50 Mbps      | 40                  |
| 200–400 Mbps | 100–150             |

---

## 🧪 Manual Commands

Run a check immediately:

```bash
docker exec -it xfinity-watchdog python /app/watchdog.py --run-now
```

Reboot modem manually:

```bash
docker exec -it xfinity-watchdog python /app/watchdog.py --reboot-now
```

---

## 🍓 Raspberry Pi Support

Runs отлично on:

* Pi 4 / Pi 5 recommended
* Very low resource usage
* Great for 24/7 monitoring

Install Docker:

```bash
curl -sSL https://get.docker.com | sh
```

---

## 🧩 How It Works (Technical)

Instead of clicking UI buttons, this script:

* Logs into the modem using Playwright
* Extracts session + CSRF tokens
* Sends real backend requests:

```
/actionHandler/ajaxSet_Reset_Restore.jst
/actionHandler/ajaxSet_mta_Line_Diagnostics.jst
```

👉 More reliable than UI automation.

---

## 📊 Example Output

```
Starting check...
Test 1: 42 Mbps
Test 2: 38 Mbps
Test 3: 41 Mbps
Upload LOW after 3 tests...
Rebooting modem...
```

---

## 🔔 Optional Discord Alerts

```yaml
DISCORD_WEBHOOK_URL: "https://discord.com/api/webhooks/..."
```

---

## ⚠️ Limitations

* Designed for Xfinity gateways only
* Firmware changes may break endpoints
* Requires modem UI access enabled

---

## 💡 Why This Is Better

Most scripts:

❌ Click buttons (fragile)

This:

✔ Uses real backend API
✔ Handles auth + tokens
✔ Tracks history + trends
✔ Has a full dashboard

---

## 🛠️ Future Improvements

* Manual trigger button in dashboard
* Real-time updates (WebSocket)
* Smarter trend detection
* Multi-ISP support

---

## ⭐ Support

If this helped you:

👉 Star the repo
👉 Share it

---

## ⚠️ Disclaimer

Use at your own risk.

This interacts with your modem’s internal API and is not officially supported by Xfinity.
