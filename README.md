<div align="center">

```
 ██████╗ ██████╗ ███╗   ██╗███████╗    ██████╗ ███╗   ██╗███████╗
██╔════╝██╔═══██╗████╗  ██║██╔════╝    ██╔══██╗████╗  ██║██╔════╝
██║     ██║   ██║██╔██╗ ██║█████╗      ██║  ██║██╔██╗ ██║███████╗
██║     ██║   ██║██║╚██╗██║██╔══╝      ██║  ██║██║╚██╗██║╚════██║
╚██████╗╚██████╔╝██║ ╚████║██║         ██████╔╝██║ ╚████║███████║
 ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝         ╚═════╝ ╚═╝  ╚═══╝╚══════╝
```

# Free DNS Management Platform

**Self-hosted subdomain / DNS service on your own domain — powered by the Cloudflare API**

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![Cloudflare](https://img.shields.io/badge/Cloudflare-F38020?style=for-the-badge&logo=cloudflare&logoColor=white)](https://www.cloudflare.com/)
[![Telegram](https://img.shields.io/badge/Telegram_Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://core.telegram.org/bots)
[![License](https://img.shields.io/badge/License-MIT-black?style=for-the-badge)](LICENSE)

[Install](#-quick-install) •
[Features](#-features-in-detail) •
[Configuration](#%EF%B8%8F-configuration) •
[API](#-api-reference) •
[Support](#-support--feedback) •
[فارسی](README.fa.md)

</div>

---

## 🌐 About

An open-source, **self-hosted DNS management platform**. You install it once on your own server with your own domain, and your users can register and create real **A / AAAA / CNAME / NS** records under your domain — for free or via paid plans that you define.

Records are **not simulated**: every create / edit / delete call is applied to real DNS through the **Cloudflare API**, so propagation happens on Cloudflare's global anycast network.

> **Example:** if your domain is `example.com`, a user can create `mysite.example.com` and point it at any IP.

Three interfaces are included out of the box:

| Interface | Who it's for | What it does |
|-----------|--------------|--------------|
| **Web app** (React) | End users | Register, manage records, referrals, CSV import/export, activity log |
| **Admin panel** (`/admin`) | You | Users, records, plans, zones, settings, backups, logs |
| **Telegram bot** | Everyone | Full DNS management + admin panel inside Telegram (FA/EN) |

---

## ✨ Features in Detail

### 👤 User Account & Authentication

- Email + password registration with **bcrypt** hashing and **JWT** sessions (72h).
- **Sign in with Google** (OAuth) — configured entirely from the admin panel, no redeploy needed.
- **Google-only mode**: admin can disable the email signup form globally; the register page automatically falls back to the Google button.
- **Email verification** with a 6-digit code (optional, requires SMTP, toggleable by admin).
- **Forgot password** flow — 6-digit code sent by email, then password reset (auto-hidden when SMTP is not configured).
- **First-login password setup** for Google users (`SecurePasswordInit`) so they can also use the bot / email login.
- Change own password from the dashboard or from the Telegram bot.
- Email normalization (Gmail dot/alias aware) to prevent duplicate accounts.

### 🖥 User Dashboard

- **Stats grid**: record count vs. limit, active plan, primary zone, referral bonus.
- **Record table** with search, refresh, one-click copy of the full hostname, inline edit and delete.
- **Create record dialog** — only the record types enabled by the admin are shown; multi-zone selector when several Cloudflare zones are active; optional Cloudflare proxy flag.
- **Limit warning banner** with an upgrade CTA when the plan limit is reached, and a clear "record creation disabled" banner when the admin turns all record types off.
- **CSV export** of your own records and **CSV import** (with downloadable template, per-row validation, limit + zone enforcement, and a per-row result report).
- **Referral card** — invite link, copy button, successful-invite count and bonus records earned.
- **Activity log** with pagination (record created / updated / deleted, login, register, telegram linked …).

### 🛡 Admin Panel

Five tabs (`/admin`):

**1. Users**
- List all users with plan, record count, verification state and source.
- Change a user's plan, reset a user's password, delete a user (their DNS records are removed from Cloudflare too).
- **Bulk actions**: batch plan change, batch delete.
- Drill into any user's records.

**2. Records**
- View every DNS record created on the platform with its owner.
- Create a record on behalf of a user, delete any record.
- **Bulk CSV export** of all records, **bulk CSV import** on behalf of users (respects each user's limit and the enabled zones).

**3. Plans**
- Create / edit / delete plans: `plan_id`, name (EN + FA), price (EN + FA), record limit (`0` = unlimited), feature list (EN + FA), "popular" badge, sort order.
- Plan data drives the public pricing section — Persian names, prices **and feature lists** are shown when the site language is Persian.
- The **Free plan limit is the single source of truth** for how many records a new user gets.

**4. Logs**
- Activity log for the whole platform with pagination and filters by user and action type.

**5. Settings**
- **Contact / Telegram**: Telegram username or full URL used by pricing CTAs and the footer, plus custom contact messages (EN/FA).
- **Referral bonus per invite** (integer, admin-defined).
- **Record-type toggles**: enable/disable `A`, `AAAA`, `CNAME`, `NS` individually. Disabled types disappear from the web form *and* the bot; if all are off, record creation is blocked everywhere.
- **Multi-zone Cloudflare support**: add / remove zones and enable/disable each one; users pick a zone when creating a record.
- **Cloudflare API token** management with a live "test token" call.
- **Google OAuth** client ID / secret, and the email-signup toggle.
- **SMTP** configuration + email-verification toggle + status check.
- **Telegram bot** management: token, admin chat ID, start / stop, live status.
- **Automated MongoDB backups**: schedule (interval), send the archive to the admin's Telegram, run a backup right now, test the bot, and **restore** from an uploaded archive (database and/or config).

### 🤖 Telegram Bot

- Bilingual (Persian / English) with per-chat language memory.
- **Register** and **login** inside the chat (including email verification when enabled).
- **My records**, **add record** (type → zone → subdomain → value, fully guided), **delete record** with confirmation.
- **Account status**: plan, usage, referral code, invites.
- **Referral link**, **change my password**, **logout**.
- Respects admin record-type toggles and disabled zones automatically.
- **Admin panel inside the bot**: stats, users (paginated), records, plans, settings editing, logs, and changing any user's password.
- Admin notifications for every new registration (web or bot).
- Managed from the web admin panel or `ddns-menu` (token / admin ID / start / stop), with lock-file cleanup so only one bot instance runs.

### 🎨 Design & Frontend

- **Terminal aesthetic** UI: monospace accents, blinking cursors, scanlines, emerald primary color.
- Full **RTL** Persian support and English LTR, switchable from the navbar; every string lives in `src/lib/i18n.js`.
- **Dark / light** themes with persisted preference.
- Responsive layout built on Tailwind CSS + shadcn/ui + lucide/phosphor icons.
- `data-testid` attributes across interactive elements for reliable automated testing.
- **Fully dynamic domain**: the brand shown everywhere comes from env vars, never hardcoded.

### ⚙️ Ops & Infrastructure

- **One-command installer** (`install.sh`) for Ubuntu/Debian: dependencies, MongoDB, Python venv, frontend production build, systemd service, Nginx vhost, Let's Encrypt SSL, UFW firewall.
- `ddns-menu` global command for day-to-day management.
- **Export / Import** archives for painless server migration.
- **Change domain** flow that rewrites both `.env` files, the Nginx vhost and re-issues SSL.
- Automatic swap creation on low-RAM servers during the frontend build.
- Backend logs via `journalctl`, service status with RAM usage and SSL expiry in the status screen.

---

## 🏗 Architecture

```
        Browser / Telegram
                │
                ▼
        Nginx  (443, SSL)
         │            │
         │ /          │ /api
         ▼            ▼
  React build   FastAPI (uvicorn, 8001)
                      │        │
                      ▼        ▼
                 MongoDB   Cloudflare API
                      │
                      ▼
             Telegram Bot (same process)
```

| Layer | Technology |
|-------|-----------|
| Frontend | React 19, CRA/Craco, Tailwind CSS, shadcn/ui, react-router |
| Backend | FastAPI, Uvicorn, Motor (async MongoDB), PyJWT, bcrypt, httpx |
| Bot | python-telegram-bot (started inside the FastAPI lifecycle) |
| Database | MongoDB |
| DNS | Cloudflare API v4 (multi-zone) |
| Web server | Nginx + Let's Encrypt (certbot) |
| Process manager | systemd (`ddns-backend.service`) |

---

## 🚀 Quick Install

### Prerequisites

| Requirement | Notes |
|-------------|-------|
| Ubuntu 20.04+ / Debian 11+ | Fresh VPS recommended |
| Root access | Needed for systemd, Nginx, SSL |
| A domain | Its A record must point to the server IP |
| Cloudflare account | API Token (Edit DNS) + Zone ID |

### One-line install

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/admin6501/ddns-khalilv2/main/install.sh)
```

Or manually:

```bash
git clone https://github.com/admin6501/ddns-khalilv2.git
cd ddns-khalilv2
sudo bash install.sh
```

The installer asks for:

| Question | Example | Notes |
|----------|---------|-------|
| Domain name | `yourdomain.com` | Root domain for subdomains |
| SSL email | `you@email.com` | Let's Encrypt notifications |
| Cloudflare API Token | — | [Create one](https://dash.cloudflare.com/profile/api-tokens) with *Edit zone DNS* |
| Cloudflare Zone ID | — | Domain → Overview → API section |
| Admin email | `admin@yourdomain.com` | Admin panel login |
| Admin password | — | Minimum 6 characters |
| MongoDB URL | `mongodb://localhost:27017` | Local by default |
| Database name | `dns_management` | Free choice |
| Telegram bot token / admin ID | — | Optional, can be set later |
| SMTP email / password | — | Optional, can be set later |

### Management menu

```bash
sudo ddns-menu
```

```
  1 )  Install          Full installation from scratch
  2 )  Start            Start all services
  3 )  Stop             Stop all services
  4 )  Restart          Restart all services
  5 )  Uninstall        Remove everything (service + DB + SSL + files)
  6 )  Status           Services + RAM usage + SSL expiry + bot status
  7 )  Logs             Backend logs
  8 )  Update           Pull latest code & rebuild
  9 )  SSL Renew        Renew / re-issue certificate
  e )  Export           Backup data for migration
  i )  Import           Restore data from backup
  t )  Telegram Bot     Configure the Telegram bot
  d )  Change Domain    Change the site domain
  0 )  Exit
```

Non-interactive equivalents:

```bash
sudo bash install.sh start | stop | restart | update | status | export | import
```

---

## 🔄 Server Migration

**1. Old server — create the archive**

```bash
sudo bash install.sh export      # ~/ddns-backup-*.tar.gz
```

**2. Copy it over**

```bash
scp ~/ddns-backup-*.tar.gz root@NEW_SERVER_IP:~/
```

**3. New server — install, then import**

```bash
sudo bash install.sh          # option 1 (Install)
sudo bash install.sh import   # give the archive path
```

Import modes: **Database + Config** (recommended), **Database only**, **Config only**.

> After migrating, repoint the domain's A record to the new IP and renew SSL (`ddns-menu` → 9).

---

## ⚙️ Configuration

### Dynamic domain

Nothing is hardcoded — the brand name comes from environment variables written by the installer.

| Variable | File | Purpose |
|----------|------|---------|
| `DOMAIN_NAME` | `backend/.env` | Domain used by the API and the bot |
| `REACT_APP_DOMAIN_NAME` | `frontend/.env` | Domain shown in the UI |

### `backend/.env`

```env
MONGO_URL=mongodb://localhost:27017
DB_NAME=dns_management
CORS_ORIGINS=https://yourdomain.com
CLOUDFLARE_API_TOKEN=your_cloudflare_token
CLOUDFLARE_ZONE_ID=your_zone_id
JWT_SECRET=auto_generated_on_install
DOMAIN_NAME=yourdomain.com
ADMIN_EMAIL=admin@yourdomain.com
ADMIN_PASSWORD=your_admin_password
TELEGRAM_BOT_TOKEN=optional
TELEGRAM_ADMIN_ID=optional
SMTP_EMAIL=optional
SMTP_PASSWORD=optional
```

### `frontend/.env`

```env
REACT_APP_BACKEND_URL=https://yourdomain.com
REACT_APP_DOMAIN_NAME=yourdomain.com
```

> The admin user is created/updated on startup from `ADMIN_EMAIL` / `ADMIN_PASSWORD`.

---

## 🔐 Google OAuth (optional)

1. Open [console.cloud.google.com](https://console.cloud.google.com/) → **New Project**.
2. **APIs & Services → OAuth consent screen** → *External* → fill app name, support email, developer email → save.
3. **Credentials → Create credentials → OAuth client ID → Web application**:
   - Authorized JavaScript origins: `https://yourdomain.com`
   - Authorized redirect URIs: `https://yourdomain.com`
4. Copy the **Client ID** and **Client Secret** into **Admin panel → Settings → Google OAuth** and enable it.

Google login then appears on the login and register pages. You can also switch the site to **Google-only** mode by disabling email signup.

---

## 📧 SMTP (optional)

Needed for email verification and password reset.

1. Enable 2-step verification on your Google account and create an **App Password** ([myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)).
2. Put the address and the 16-character app password into **Admin panel → Settings → SMTP**.
3. Toggle **email verification** on if you want new users to confirm their address.

When SMTP is off, the "forgot password" entry point is hidden automatically.

---

## 📡 API Reference

Base URL: `https://yourdomain.com/api`
Auth: `Authorization: Bearer <JWT>`

### Auth

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/register` | Register (supports `?ref=` referral code) |
| POST | `/auth/login` | Login, returns JWT |
| GET | `/auth/me` | Current user profile + limits |
| POST | `/auth/verify-email` | Verify the 6-digit code |
| POST | `/auth/resend-code` | Resend verification code |
| GET | `/auth/verification-status` | Is email verification enabled |
| GET | `/auth/signup-status` | Is email signup enabled |
| GET | `/auth/password-reset-status` | Is password reset available (SMTP) |
| POST | `/auth/forgot-password` | Send reset code |
| POST | `/auth/reset-password` | Reset password with code |
| PUT | `/auth/password` | Change own password |
| POST | `/auth/set-initial-password` | Set first password (Google users) |
| GET | `/auth/google/config` | Public Google OAuth config |
| POST | `/auth/google` | Login / register with Google |

### DNS records

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/dns/records` | My records |
| POST | `/dns/records` | Create a record |
| PUT | `/dns/records/{id}` | Update a record |
| DELETE | `/dns/records/{id}` | Delete a record |
| GET | `/dns/zones` | Zones available to the user |
| GET | `/dns/records/export` | Export my records as CSV |
| GET | `/dns/records/import/template` | CSV import template |
| POST | `/dns/records/import` | Bulk import from CSV |

### Public / misc

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/plans` | Public plan list (EN + FA fields) |
| GET | `/config` | Site config (domain, contact, toggles) |
| GET | `/settings/contact` | Contact info |
| GET | `/referral/stats` | My referral stats |
| GET | `/activity/logs` | My activity log (paginated) |
| GET | `/telegram/status` | Bot status |
| GET | `/telegram/debug` | Bot diagnostics |

### Admin (role `admin` required)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/admin/users` | All users |
| DELETE | `/admin/users/{id}` | Delete user + their records |
| PUT | `/admin/users/{id}/plan` | Change plan |
| PUT | `/admin/users/{id}/password` | Reset password |
| GET | `/admin/users/{id}/records` | User's records |
| POST | `/admin/users/bulk/plan` | Bulk plan change |
| POST | `/admin/users/bulk/delete` | Bulk delete |
| GET | `/admin/records` | All records |
| POST | `/admin/dns/records` | Create record for a user |
| DELETE | `/admin/dns/records/{id}` | Delete any record |
| GET | `/admin/records/export` | Export all records (CSV) |
| GET | `/admin/records/import/template` | Admin CSV template |
| POST | `/admin/records/import` | Bulk import for users |
| GET / POST | `/admin/plans` | List / create plans |
| PUT / DELETE | `/admin/plans/{plan_id}` | Edit / delete a plan |
| GET / PUT | `/admin/settings` | Site settings |
| GET / PUT | `/admin/record-types` | Record-type toggles |
| GET / POST | `/admin/zones` | List / add Cloudflare zones |
| PATCH / DELETE | `/admin/zones/{zone_id}` | Enable-disable / remove a zone |
| GET / PUT | `/admin/cf-token` | Cloudflare token |
| POST | `/admin/cf-token/test` | Live token test |
| GET / PUT | `/admin/google-oauth` | Google OAuth settings |
| GET / PUT | `/admin/smtp/status`, `/admin/smtp/config` | SMTP settings |
| PUT | `/admin/smtp/toggle-verification` | Toggle email verification |
| GET / PUT | `/admin/auth/signup-status`, `/admin/auth/toggle-email-signup` | Email signup toggle |
| GET / PUT | `/admin/bot/status`, `/admin/bot/token`, `/admin/bot/admin-id` | Bot config |
| POST | `/admin/bot/start`, `/admin/bot/stop` | Start / stop the bot |
| GET / PUT | `/admin/backup/settings` | Backup scheduler |
| POST | `/admin/backup/now`, `/admin/backup/restore`, `/admin/backup/test-bot` | Backup actions |
| GET | `/admin/activity/logs` | Platform activity log |

Interactive docs (FastAPI): `https://yourdomain.com/api/docs` when enabled.

---

## 📁 Project Structure

```
├── install.sh                     # Installer & management script (ddns-menu)
├── README.md                      # English documentation
├── README.fa.md                   # Persian documentation
│
├── backend/
│   ├── server.py                  # FastAPI app: APIs, Cloudflare, backups, Telegram bot
│   ├── requirements.txt
│   ├── tests/                     # Auth regression tests
│   └── .env
│
└── frontend/
    ├── package.json / tailwind.config.js / craco.config.js
    ├── public/index.html
    └── src/
        ├── App.js                 # Routing
        ├── index.css              # Theme tokens, animations, RTL rules
        ├── config/site.js         # Domain from env
        ├── lib/api.js             # Axios client
        ├── lib/i18n.js            # FA / EN strings
        ├── contexts/              # Auth, Config, Theme, Language
        ├── components/
        │   ├── Navbar.js
        │   ├── GoogleLoginButton.js
        │   ├── SecurePasswordInit.js
        │   ├── EmailVerifyPanel.js
        │   ├── RouteLoader.js
        │   └── ui/                # shadcn/ui components
        └── pages/
            ├── Landing.js         # Hero, features, pricing, FAQ, footer
            ├── Login.js / Register.js / ForgotPassword.js
            ├── Dashboard.js       # Records, referrals, CSV, activity
            └── Admin.js           # 5-tab admin panel
```

---

## 🎯 Plan System

Plans are fully managed from the admin panel. Defaults created on first run:

| Plan | Records | Price | Notes |
|------|---------|-------|-------|
| Free | 2 | $0 | Default plan for every new user |
| Pro | 50 | $5/mo | CTA opens the admin's Telegram |
| Enterprise | 500 | $20/mo | CTA opens the admin's Telegram |

- `record_limit = 0` means **unlimited**.
- Effective limit = plan limit **+** referral bonus records.
- Persian name / price / feature list are used automatically when the site is in Persian.

---

## 🤝 Referral System

```
              invite link
   User A ───────────────────►  User B registers
      │                                 │
      │◄──────  +N bonus records  ───────┘
                (N set by admin)
```

- Every user gets a unique referral code.
- Invite link: `https://yourdomain.com/register?ref=CODE`
- The inviter gains **N** extra records per successful signup (`referral_bonus_per_invite`, default `1`).

---

## 🛠 Local Development

**Backend**

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# create .env (see Configuration)
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

**Frontend**

```bash
cd frontend
yarn install
# create .env with REACT_APP_BACKEND_URL / REACT_APP_DOMAIN_NAME
yarn start
```

**Tests**

```bash
cd backend && pytest tests -q
```

---

## 🔧 Troubleshooting

```bash
# Service status, RAM, SSL expiry, bot status
sudo ddns-menu        # option 6

# Backend logs
sudo journalctl -u ddns-backend -n 200 -f

# MongoDB
sudo systemctl status mongod

# Check env files
cat /opt/ddns/backend/.env
```

| Symptom | Check |
|---------|-------|
| Site not loading | Nginx running? SSL valid? `ddns-menu` → 4 (Restart) |
| Records not created | Cloudflare token & Zone ID (Settings → test token), zone enabled, record type enabled, plan limit |
| Bot not responding | Token + admin ID set, bot started, only one instance (`ddns-menu` → t) |
| Verification / reset emails missing | SMTP app password valid, verification enabled |
| Google login missing | Client ID/secret saved, origins and redirect URI match the domain exactly |

---

## 🔒 Security

- Passwords hashed with **bcrypt**; JWT tokens expire after 72 hours.
- Admin routes gated by the `admin` role on every request.
- CORS restricted to the site domain (`CORS_ORIGINS`).
- Nginx security headers + Let's Encrypt TLS.
- Secrets kept in `.env` files only (never committed, never exposed to the frontend).
- Optional email verification, and an optional Google-only signup mode.

---

## 💬 Support & Feedback

Bugs, ideas, feature requests, criticism — all welcome. Contact the developer directly on Telegram:

<div align="center">

### [![Telegram](https://img.shields.io/badge/@asangozar__support-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/asangozar_support)

**Developer:** [@asangozar_support](https://t.me/asangozar_support)

</div>

When reporting a bug, please include:

1. What you did and what you expected.
2. Your OS / server type and how you installed it.
3. Relevant output of `sudo journalctl -u ddns-backend -n 100`.
4. A screenshot, if it is a UI issue.

GitHub issues: [github.com/admin6501/ddns-khalilv2/issues](https://github.com/admin6501/ddns-khalilv2/issues)

---

## 📄 License

Released under the [MIT](LICENSE) license.

<div align="center">

If this project helped you, leave a star ⭐

</div>
