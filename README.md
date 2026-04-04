🚀 Xfinity Upload Watchdog

Automatically monitor your upload speed and reboot your Xfinity modem when performance drops.

⚠️ Why This Exists

If you use Xfinity, you’ve probably seen this:

Download speeds are fine ✅
Upload suddenly drops far below normal ❌
Restarting the modem instantly fixes it 🔄

This is a common issue with many Xfinity gateways and DOCSIS networks:

Upload channels can degrade or get stuck
Signal conditions fluctuate throughout the day
The modem doesn’t always recover on its own
A simple reboot often restores full upload speed

👉 This tool automates that process.

📡 Important: Know Your Plan Speeds

Xfinity upload speeds vary depending on your plan.

Typical DOCSIS upload tiers:

Plan Type	Typical Upload
Lower tiers	10–20 Mbps
Mid tiers	20–50 Mbps
Higher tiers	100–200 Mbps
2 Gig+ / Next Gen	200–400+ Mbps

⚠️ Important:

High upload speeds (200–400 Mbps) are usually only available on newer 2 Gig+ / Next Gen plans
If your plan is lower, adjust the threshold accordingly
🎯 What This Tool Fixes

This is NOT for slow plans.

This is for when:

You normally get 300 Mbps upload
But suddenly drop to 20–50 Mbps
And a reboot fixes it

👉 This detects and fixes that automatically.

🧠 What It Does

Every hour (default :30):

Runs a Speedtest
Checks your upload speed
If upload is below threshold:
retries 2 more times
If all 3 tests are below threshold:
logs into your modem
sends the real backend reboot command
restarts the gateway automatically
⚙️ Features
📡 Accurate Speedtest (Ookla CLI)
🔁 Retry logic
🔐 Logs into modem automatically
🔌 Uses internal Xfinity API (not UI clicking)
🔔 Optional Discord alerts
🐳 Docker-based
🍓 Works great on Raspberry Pi
🖥️ Requirements
Xfinity modem/router with local UI (http://10.0.0.1)
Docker + Docker Compose
Modem admin credentials
📦 Installation
git clone https://github.com/YOUR_USERNAME/xfinity-upload-watchdog.git
cd xfinity-upload-watchdog

Edit config:

nano docker-compose.yml

Change:

MODEM_PASSWORD: "your_password_here"

Then start:

docker compose up -d
🔍 Configuration
RUN_MINUTE: "30"
UPLOAD_THRESHOLD_MBPS: "100"
MAX_ATTEMPTS: "3"
RETRY_WAIT_SECONDS: "30"
DISCORD_WEBHOOK_URL: ""
⚙️ Choosing the Right Threshold

Set this based on your plan:

UPLOAD_THRESHOLD_MBPS: "100"

Examples:

Plan	Recommended Threshold
20 Mbps	15
50 Mbps	40
200–400 Mbps	100
🧪 Manual Commands

Run a test immediately:

docker exec -it xfinity-watchdog python /app/xfinity.py --run-now

Reboot modem manually:

docker exec -it xfinity-watchdog python /app/xfinity.py --reboot-now
🍓 Raspberry Pi Support

This runs perfectly on a Raspberry Pi:

Pi 4 / Pi 5 recommended
Very low resource usage
Great for 24/7 monitoring

Install Docker:

curl -sSL https://get.docker.com | sh

Then follow normal setup.

🧩 How It Works (Technical)

Instead of clicking UI buttons, this script:

Logs into the modem via Playwright
Extracts session + CSRF tokens
Sends real backend requests:
/actionHandler/ajaxSet_Reset_Restore.jst
/actionHandler/ajaxSet_mta_Line_Diagnostics.jst

👉 This makes it far more reliable than UI automation.

📊 Example Output
Starting check...
Test 1: 42 Mbps
Test 2: 38 Mbps
Test 3: 41 Mbps
Upload LOW after 3 tests...
Rebooting modem...
🔔 Optional Discord Alerts
DISCORD_WEBHOOK_URL: "https://discord.com/api/webhooks/..."
⚠️ Limitations
Designed for Xfinity gateways only
Other routers will require modification
Firmware changes may break endpoints
💡 Why This Is Better

Most scripts:
❌ Click buttons (break easily)

This:
✔ Uses actual backend API
✔ Handles auth + tokens properly
✔ Is stable and repeatable

🛠️ Future Improvements
Reboot cooldown
Speed history tracking
Smarter decision logic
⭐ Support

If this helped you:
👉 Star the repo
👉 Share it

⚠️ Disclaimer

Use at your own risk.
This interacts with your modem’s internal API and is not officially supported by Xfinity.