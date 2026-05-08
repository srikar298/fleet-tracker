# 🚛 FleetTracker Pro: Enterprise B2B Transport Aggregator

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![Telegram Bot](https://img.shields.io/badge/Bot-Telegram-0088cc?logo=telegram&logoColor=white)](https://core.telegram.org/bots)
[![Google Sheets](https://img.shields.io/badge/Database-Google%20Sheets-34A853?logo=google-sheets&logoColor=white)](https://www.google.com/sheets/about/)
[![Cloudflare R2](https://img.shields.io/badge/Storage-Cloudflare%20R2-F38020?logo=cloudflare&logoColor=white)](https://www.cloudflare.com/products/r2/)

FleetTracker Pro is a sophisticated, production-grade transport management engine designed for B2B fleet operators. It transforms a Telegram Bot into a full-scale operational dashboard, automating driver payouts, client billing, and real-time operational visibility.

---

## 🌟 Key Features

### 🏁 Operation Modes
- **Real-Time Tracking**: For drivers who prefer instant reporting after every trip.
- **Bulk Daily Session**: A professional morning-to-evening workflow. Record a morning check-in and submit all trips in a single batch at night.

### 💰 B2B Financial Engine
- **Dual-Pricing Margin Engine**: Automatically calculates the spread between Client Billing and Driver Payout for every trip.
- **Automated Payroll**: Monthly payroll generation with base salary, attendance bonuses, and performance-based rewards.
- **Expense Management**: Capture fuel receipts, tolls, and maintenance costs with OCR-ready image storage.

### 🛡️ Operational Hardening
- **Fraud Detection**: Automatic flagging of large odometer jumps and suspicious trip durations.
- **Evidence-Based Reporting**: Compulsory photo uploads for odo readings and fuel receipts, stored securely on Cloudflare R2.
- **Self-Healing Attendance**: Automatically marks attendance on the first trip of the day, ensuring drivers never miss a payout.

### 📊 Admin Command Center
- **Live Fleet Watch**: Real-time status of all vehicles and drivers.
- **One-Click Exports**: Download daily, weekly, or range-based reports directly in Excel/CSV format.
- **Leaderboards & Gamification**: Driver ranking based on safety scores, distance, and efficiency.

---

## 🛠️ Tech Stack

- **Logic**: Python 3.10+ (AsyncIO)
- **Interface**: Telegram Bot API (`python-telegram-bot`)
- **Database/Ledger**: Google Sheets API (v4)
- **Object Storage**: Cloudflare R2 (S3-Compatible)
- **Deployment**: Optimized for Railway, Docker, or Linux VPS.

---

## 🚀 Quick Start

### 1. Environment Configuration
Create a `.env` file in the root directory:
```env
TELEGRAM_BOT_TOKEN=your_token
ADMIN_IDS=123456,789012
GOOGLE_SHEETS_ID=your_spreadsheet_id
GOOGLE_CREDENTIALS_JSON='{...}'

# Cloudflare R2
CLOUDFLARE_R2_ACCOUNT_ID=...
CLOUDFLARE_R2_ACCESS_KEY=...
CLOUDFLARE_R2_SECRET_KEY=...
CLOUDFLARE_R2_BUCKET=...
CLOUDFLARE_R2_PUBLIC_URL=...
```

### 2. Installation
```bash
pip install -r requirements.txt
python src/main.py
```

---

## 📱 Bot Command Reference

| Command | Role | Description |
| :--- | :--- | :--- |
| `/start` | Driver | Register and access the Main Menu |
| `/startbulkday` | Driver | Morning Check-in (Odo + Photo) |
| `/endbulkday` | Driver | Evening Batch Trip Submission |
| `/admin` | Admin | Access the Admin Management Suite |
| `/viewdaily` | Admin | Instant performance snapshot |
| `/live` | Admin | Real-time vehicle status watch |
| `/payroll` | Admin | Generate and export payroll sheets |

---

## 📁 Project Structure

```text
fleet-tracker/
├── src/
│   ├── handlers/       # Logic for Trips, Admin, Bulk, Registration
│   ├── services/       # Core APIs (Sheets, Cloudflare, Attendance)
│   ├── core/           # Constants and State Management
│   └── utils/          # UI components and Helpers
├── scripts/            # Database seeding and maintenance
└── requirements.txt    # Production dependencies
```

---

## 📊 Business Logic: The Master Ledger
The system pushes data into a highly structured Google Sheet with the following key components:
- **`Master_Ledger`**: The source of truth for every KM driven.
- **`Master_Drivers`**: Profiles, KYC links, and salary configurations.
- **`Master_Vehicles`**: Real-time odometer and health tracking.
- **`Monthly_Payroll`**: Live-calculated earnings including bonuses and deductions.

---

## ⚖️ License
Internal B2B Enterprise Software. All rights reserved.
