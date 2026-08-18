# 🚀 JobRecruitment — AI SMS Campaign Studio & Physical Radio Automation

A 100% Free, production-grade Android SIM Radio automation platform designed for recruitment teams, candidate bulk messaging, and dynamic AI copy generation.

---

## 🌟 Key Features

- **⚡ Zero-Cost Physical Radio Gateway:** Uses your existing Android phone SIM (Jio True5G / Airtel) to dispatch SMS without expensive third-party aggregators.
- **🔌 Multi-Gateway Connectivity:** USB Cable + 3-Way Wi-Fi Wireless Debugging (Direct IP:Port, 6-Digit PIN, Native QR).
- **🤖 Multi-Provider AI Copywriter:** Llama 3.3 70B (Groq), Gemini 2.5 Flash (Google), DeepSeek R1 (NVIDIA), GPT-4o (OpenAI).
- **🛡️ Regulatory Safety:** TRAI 180 SMS/day compliance engine with atomic midnight reset.
- **🍪 Dual Persistence:** Browser Cookies & LocalStorage + Supabase PostgreSQL Cloud Ledger & Past Campaigns with 1-click Re-use.
- **💓 24/7 Render Keep-Alive:** Built-in self-pinging heartbeat engine keeps Render instances active 24/7.

---

## 🚢 Deploy to Render.com (1-Click)

1. Fork or push this repository to GitHub.
2. Connect your GitHub account to [Render.com](https://render.com).
3. Create a **New Web Service** and select this repo (Environment: **Docker**).
4. Set Environment Variables:
   - `WORKER_API_URL`
   - `WORKER_API_KEY`
   - `SUPABASE_DB_URL`
   - `GROQ_API_KEY`
5. Click **Create Web Service**!

---

## 🌐 Custom Subdomain (e.g. `sms.jobrecruitment.in`)

1. In Render Dashboard: **Settings** -> **Custom Domains** -> Add `sms.jobrecruitment.in`.
2. In Cloudflare / Hostinger DNS:
   - Type: `CNAME`
   - Name: `sms`
   - Target: `<your-render-subdomain>.onrender.com`

---

## 💻 Local Development

```bash
git clone https://github.com/jobrecruitmentdev-lang/SMS_automation.git
cd SMS_automation
pip install -r requirements.txt
python sms_studio.py
```
Open `http://localhost:8050` in your browser.
