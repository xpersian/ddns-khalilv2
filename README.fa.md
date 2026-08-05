<div align="center">

```
 ██████╗ ██████╗ ███╗   ██╗███████╗    ██████╗ ███╗   ██╗███████╗
██╔════╝██╔═══██╗████╗  ██║██╔════╝    ██╔══██╗████╗  ██║██╔════╝
██║     ██║   ██║██╔██╗ ██║█████╗      ██║  ██║██╔██╗ ██║███████╗
██║     ██║   ██║██║╚██╗██║██╔══╝      ██║  ██║██║╚██╗██║╚════██║
╚██████╗╚██████╔╝██║ ╚████║██║         ██████╔╝██║ ╚████║███████║
 ╚═════╝ ╚═════╝ ╚═╝  ╚═══╝╚═╝         ╚═════╝ ╚═╝  ╚═══╝╚══════╝
```

# پلتفرم مدیریت DNS رایگان

**سرویس ساب‌دامین روی دامنه‌ی خودت — یک بار نصب کن، برای همه سرویس بده (با Cloudflare API)**

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=for-the-badge&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)](https://reactjs.org/)
[![MongoDB](https://img.shields.io/badge/MongoDB-47A248?style=for-the-badge&logo=mongodb&logoColor=white)](https://www.mongodb.com/)
[![Cloudflare](https://img.shields.io/badge/Cloudflare-F38020?style=for-the-badge&logo=cloudflare&logoColor=white)](https://www.cloudflare.com/)
[![Telegram](https://img.shields.io/badge/Telegram_Bot-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://core.telegram.org/bots)
[![License](https://img.shields.io/badge/License-MIT-black?style=for-the-badge)](LICENSE)

[نصب](#-نصب-سریع) •
[قابلیت‌ها](#-قابلیتها-به-تفکیک) •
[پیکربندی](#%EF%B8%8F-پیکربندی) •
[API](#-مستندات-api) •
[پشتیبانی](#-پشتیبانی-و-ارتباط-با-توسعهدهنده) •
[English](README.md)

</div>

---

## 🌐 درباره‌ی پروژه

یک پلتفرم **کاملاً اوپن‌سورس مدیریت DNS** که روی سرور و دامنه‌ی خودت نصب می‌شه. کاربرها ثبت‌نام می‌کنن و می‌تونن رکوردهای واقعی **A / AAAA / CNAME / NS** زیر دامنه‌ی تو بسازن — رایگان یا با پلن‌هایی که خودت تعریف می‌کنی.

رکوردها شبیه‌سازی نیستن: هر ساخت/ویرایش/حذف مستقیماً از طریق **Cloudflare API** روی DNS واقعی اعمال می‌شه و انتشار روی شبکه‌ی جهانی Cloudflare انجام می‌گیره.

> **مثال:** اگر دامنه‌ت `example.com` باشه، کاربر می‌تونه `mysite.example.com` بسازه و به هر IP وصلش کنه.

سه رابط کاربری به‌صورت پیش‌فرض وجود داره:

| رابط | مخاطب | کارکرد |
|------|-------|--------|
| **وب‌اپ** (React) | کاربران | ثبت‌نام، مدیریت رکورد، رفرال، CSV، لاگ فعالیت |
| **پنل ادمین** (`/admin`) | مدیر سایت | کاربران، رکوردها، پلن‌ها، زون‌ها، تنظیمات، بکاپ، لاگ |
| **ربات تلگرام** | همه | مدیریت کامل DNS + پنل ادمین داخل تلگرام (فارسی/انگلیسی) |

---

## ✨ قابلیت‌ها به تفکیک

### 👤 حساب کاربری و احراز هویت

- ثبت‌نام با ایمیل و رمز عبور، هش شدن رمز با **bcrypt** و نشست **JWT** (۷۲ ساعته).
- **ورود با گوگل** (OAuth) — کاملاً از پنل ادمین تنظیم می‌شه، بدون نیاز به دیپلوی مجدد.
- **حالت فقط گوگل**: ادمین می‌تونه فرم ثبت‌نام ایمیلی رو کلاً غیرفعال کنه؛ صفحه‌ی ثبت‌نام خودکار فقط دکمه‌ی گوگل رو نشون می‌ده.
- **تأیید ایمیل** با کد ۶ رقمی (اختیاری، نیازمند SMTP، قابل خاموش/روشن شدن توسط ادمین).
- **فراموشی رمز عبور**: ارسال کد ۶ رقمی به ایمیل و سپس تغییر رمز (اگر SMTP تنظیم نشده باشه، این گزینه خودکار مخفی می‌شه).
- **تعیین رمز در اولین ورود** برای کاربران گوگل (`SecurePasswordInit`) تا بتونن با ربات و ایمیل هم وارد بشن.
- تغییر رمز از داشبورد یا از داخل ربات تلگرام.
- نرمال‌سازی ایمیل (آگاه به نقطه و alias جیمیل) برای جلوگیری از حساب تکراری.

### 🖥 داشبورد کاربر

- **کارت‌های آماری**: تعداد رکورد نسبت به سقف، پلن فعال، دامنه‌ی اصلی، رکوردهای جایزه‌ی رفرال.
- **جدول رکوردها** با جستجو، بروزرسانی، کپی یک‌کلیکی آدرس کامل، ویرایش و حذف.
- **دیالوگ ساخت رکورد** — فقط نوع‌هایی که ادمین فعال کرده نمایش داده می‌شه، انتخاب زون در صورت فعال بودن چند زون Cloudflare، و گزینه‌ی پراکسی Cloudflare.
- **هشدار رسیدن به سقف** با دکمه‌ی ارتقا، و هشدار «ساخت رکورد غیرفعال است» وقتی ادمین همه‌ی نوع‌ها رو خاموش کرده.
- **خروجی CSV** از رکوردهای خودت و **ورود گروهی CSV** (با فایل نمونه، اعتبارسنجی هر ردیف، رعایت سقف و زون‌های مجاز و گزارش نتیجه‌ی هر ردیف).
- **کارت رفرال** — لینک دعوت، دکمه‌ی کپی، تعداد دعوت موفق و رکورد جایزه.
- **لاگ فعالیت** با صفحه‌بندی (ساخت/ویرایش/حذف رکورد، ورود، ثبت‌نام، اتصال تلگرام و…).

### 🛡 پنل مدیریت

پنل `/admin` شامل پنج تب است:

**۱. کاربران**
- فهرست همه‌ی کاربران با پلن، تعداد رکورد، وضعیت تأیید و منبع ثبت‌نام.
- تغییر پلن کاربر، تغییر رمز کاربر، حذف کاربر (رکوردهای DNS او از Cloudflare هم پاک می‌شه).
- **عملیات گروهی**: تغییر پلن دسته‌ای و حذف دسته‌ای.
- مشاهده‌ی رکوردهای هر کاربر.

**۲. رکوردها**
- مشاهده‌ی همه‌ی رکوردهای ساخته‌شده به‌همراه مالک.
- ساخت رکورد به نام یک کاربر و حذف هر رکوردی.
- **خروجی CSV کامل** و **ورود گروهی CSV به نام کاربران** (با رعایت سقف هر کاربر و زون‌های فعال).

**۳. پلن‌ها**
- ساخت / ویرایش / حذف پلن: `plan_id`، نام (انگلیسی و فارسی)، قیمت (انگلیسی و فارسی)، سقف رکورد (`0` = نامحدود)، فهرست امکانات (انگلیسی و فارسی)، نشان «محبوب»، ترتیب نمایش.
- همین اطلاعات بخش قیمت‌گذاری صفحه‌ی اصلی رو می‌سازه؛ وقتی زبان سایت فارسیه، **نام، قیمت و فهرست امکانات فارسی** نمایش داده می‌شه.
- سقف پلن **Free** تنها منبع تعیین تعداد رکورد رایگان کاربر جدید است.

**۴. لاگ‌ها**
- لاگ فعالیت کل پلتفرم با صفحه‌بندی و فیلتر بر اساس کاربر و نوع عملیات.

**۵. تنظیمات**
- **ارتباط / تلگرام**: نام کاربری یا لینک تلگرام که در دکمه‌های پلن و فوتر استفاده می‌شه، به‌همراه متن تماس اختصاصی (فارسی/انگلیسی).
- **جایزه‌ی رفرال به‌ازای هر دعوت** (عدد قابل تنظیم).
- **کلید نوع رکوردها**: فعال/غیرفعال کردن جداگانه‌ی `A`، `AAAA`، `CNAME`، `NS`. نوع غیرفعال از فرم وب و ربات حذف می‌شه؛ اگر همه خاموش باشن، ساخت رکورد در همه‌جا بسته می‌شه.
- **پشتیبانی چند زون Cloudflare**: افزودن/حذف زون و فعال یا غیرفعال کردن هر زون؛ کاربر هنگام ساخت رکورد زون رو انتخاب می‌کنه.
- **مدیریت توکن Cloudflare** با امکان تست زنده‌ی توکن.
- **Google OAuth** (Client ID/Secret) و کلید فعال/غیرفعال بودن ثبت‌نام ایمیلی.
- **SMTP** و کلید تأیید ایمیل و بررسی وضعیت.
- **مدیریت ربات تلگرام**: توکن، آیدی عددی ادمین، شروع/توقف و وضعیت زنده.
- **بکاپ خودکار MongoDB**: زمان‌بندی دوره‌ای، ارسال فایل بکاپ به تلگرام ادمین، بکاپ فوری، تست ربات و **بازگردانی** از فایل بکاپ (دیتابیس و/یا کانفیگ).

### 🤖 ربات تلگرام

- دوزبانه (فارسی/انگلیسی) با حفظ زبان انتخابی هر چت.
- **ثبت‌نام** و **ورود** داخل چت (شامل تأیید ایمیل در صورت فعال بودن).
- **رکوردهای من**، **ساخت رکورد** (نوع ← زون ← نام ساب‌دامین ← مقدار ← روشن/خاموش کردن پروکسی کلادفلر، کاملاً مرحله‌به‌مرحله)، **حذف رکورد** با تأییدیه.
- **ویرایش رکورد**: تغییر مقدار (IP یا مقصد) و روشن/خاموش کردن پروکسی کلادفلر بعد از ساخت رکورد.
- **وضعیت اکانت**: پلن، مصرف، کد دعوت، تعداد دعوت.
- **لینک دعوت**، **تغییر رمز عبور**، **خروج**.
- رعایت خودکار کلیدهای نوع رکورد و زون‌های غیرفعال.
- **پنل ادمین داخل ربات**: آمار، کاربران (صفحه‌بندی‌شده)، رکوردها، **مدیریت کامل پلن‌ها (ساخت / ویرایش همه‌ی فیلدها / تغییر نشان محبوب / حذف)**، ویرایش تنظیمات، لاگ‌ها و تغییر رمز هر کاربر.
- اطلاع‌رسانی به ادمین برای هر ثبت‌نام جدید (وب یا ربات).
- مدیریت از پنل وب یا `ddns-menu` (توکن/آیدی ادمین/شروع/توقف) به‌همراه پاک‌سازی lock تا فقط یک نمونه از ربات اجرا بشه.

### 🎨 طراحی و فرانت‌اند

- ظاهر **ترمینالی**: فونت مونواسپیس، کورسورهای چشمک‌زن، خطوط اسکن و رنگ اصلی زمردی.
- پشتیبانی کامل **RTL** فارسی و LTR انگلیسی، قابل تغییر از نوار بالا؛ همه‌ی متن‌ها در `src/lib/i18n.js`.
- تم **تاریک/روشن** با ذخیره‌ی انتخاب کاربر.
- طراحی ریسپانسیو با Tailwind CSS و shadcn/ui و آیکون‌های lucide/phosphor.
- ویژگی `data-testid` روی عناصر تعاملی برای تست خودکار مطمئن.
- **نام دامنه کاملاً داینامیک**؛ هیچ‌جا هاردکد نشده و از متغیر محیطی خونده می‌شه.

### ⚙️ زیرساخت و نگهداری

- **نصب یک‌مرحله‌ای** (`install.sh`) برای Ubuntu/Debian: پیش‌نیازها، MongoDB، محیط مجازی پایتون، بیلد پروداکشن فرانت، سرویس systemd، وی‌هاست Nginx، SSL رایگان Let's Encrypt و فایروال UFW.
- دستور سراسری `ddns-menu` برای مدیریت روزمره.
- **Export / Import** برای انتقال بی‌دردسر به سرور جدید.
- **تغییر دامنه** با بازنویسی هر دو فایل `.env`، وی‌هاست Nginx و صدور مجدد SSL.
- ساخت خودکار swap در سرورهای کم‌رم هنگام بیلد فرانت‌اند.
- لاگ بک‌اند با `journalctl` و نمایش وضعیت سرویس‌ها، مصرف رم و تاریخ انقضای SSL در صفحه‌ی Status.

---

## 🏗 معماری

```
        مرورگر / تلگرام
                │
                ▼
         Nginx  (443, SSL)
         │            │
         │ /          │ /api
         ▼            ▼
   بیلد React    FastAPI (uvicorn, 8001)
                      │        │
                      ▼        ▼
                 MongoDB   Cloudflare API
                      │
                      ▼
              ربات تلگرام (همان پروسه)
```

| لایه | فناوری |
|------|--------|
| فرانت‌اند | React 19، CRA/Craco، Tailwind CSS، shadcn/ui، react-router |
| بک‌اند | FastAPI، Uvicorn، Motor (MongoDB async)، PyJWT، bcrypt، httpx |
| ربات | python-telegram-bot (داخل چرخه‌ی عمر FastAPI) |
| دیتابیس | MongoDB |
| DNS | Cloudflare API v4 (چند زون) |
| وب‌سرور | Nginx + Let's Encrypt (certbot) |
| مدیریت پروسه | systemd (`ddns-backend.service`) |

---

## 🚀 نصب سریع

### پیش‌نیازها

| نیازمندی | توضیح |
|----------|-------|
| Ubuntu 20.04+ / Debian 11+ | سرور تازه توصیه می‌شه |
| دسترسی root | برای systemd، Nginx و SSL |
| یک دامنه | رکورد A آن باید به IP سرور اشاره کنه |
| حساب Cloudflare | API Token (Edit DNS) + Zone ID |

### نصب یک‌خطی

```bash
bash <(curl -fsSL https://raw.githubusercontent.com/admin6501/ddns-khalilv2/main/install.sh)
```

یا به‌صورت دستی:

```bash
git clone https://github.com/admin6501/ddns-khalilv2.git
cd ddns-khalilv2
sudo bash install.sh
```

نصب‌کننده این موارد رو می‌پرسه:

| سؤال | نمونه | توضیح |
|------|-------|-------|
| نام دامنه | `yourdomain.com` | دامنه‌ی اصلی ساب‌دامین‌ها |
| ایمیل SSL | `you@email.com` | برای Let's Encrypt |
| توکن API کلادفلر | — | [ساخت توکن](https://dash.cloudflare.com/profile/api-tokens) با دسترسی *Edit zone DNS* |
| Zone ID کلادفلر | — | از بخش Overview دامنه |
| ایمیل ادمین | `admin@yourdomain.com` | ورود به پنل مدیریت |
| رمز ادمین | — | حداقل ۶ کاراکتر |
| آدرس MongoDB | `mongodb://localhost:27017` | پیش‌فرض: لوکال |
| نام دیتابیس | `dns_management` | به انتخاب خودت |
| توکن ربات / آیدی ادمین تلگرام | — | اختیاری، بعداً هم قابل تنظیم |
| ایمیل و رمز SMTP | — | اختیاری، بعداً هم قابل تنظیم |

### منوی مدیریت

```bash
sudo ddns-menu
```

```
  1 )  Install          نصب کامل از ابتدا
  2 )  Start            اجرای همه‌ی سرویس‌ها
  3 )  Stop             توقف سرویس‌ها
  4 )  Restart          ری‌استارت سرویس‌ها
  5 )  Uninstall        حذف کامل (سرویس + دیتابیس + SSL + فایل‌ها)
  6 )  Status           وضعیت سرویس‌ها + مصرف رم + انقضای SSL + وضعیت ربات
  7 )  Logs             لاگ بک‌اند
  8 )  Update           دریافت آخرین کد و بیلد مجدد
  9 )  SSL Renew        تمدید یا صدور مجدد گواهی SSL
  e )  Export           تهیه‌ی بکاپ برای انتقال سرور
  i )  Import           بازگردانی از فایل بکاپ
  t )  Telegram Bot     تنظیم ربات تلگرام
  d )  Change Domain    تغییر دامنه‌ی سایت
  0 )  Exit             خروج
```

معادل‌های خط فرمان:

```bash
sudo bash install.sh start | stop | restart | update | status | export | import
```

---

## 🔄 انتقال سرور (Migration)

**۱. سرور قدیم — ساخت بکاپ**

```bash
sudo bash install.sh export      # ~/ddns-backup-*.tar.gz
```

**۲. انتقال فایل**

```bash
scp ~/ddns-backup-*.tar.gz root@NEW_SERVER_IP:~/
```

**۳. سرور جدید — نصب و سپس بازگردانی**

```bash
sudo bash install.sh          # گزینه‌ی ۱ (Install)
sudo bash install.sh import   # مسیر فایل بکاپ رو بده
```

حالت‌های بازگردانی: **دیتابیس + کانفیگ** (توصیه‌شده)، **فقط دیتابیس**، **فقط کانفیگ**.

> بعد از انتقال، رکورد A دامنه رو به IP جدید تغییر بده و SSL رو تمدید کن (`ddns-menu` → گزینه‌ی ۹).

---

## ⚙️ پیکربندی

### دامنه‌ی داینامیک

هیچ‌چیز هاردکد نیست؛ نام برند از متغیرهای محیطی خونده می‌شه که نصب‌کننده می‌سازه.

| متغیر | فایل | کاربرد |
|-------|------|--------|
| `DOMAIN_NAME` | `backend/.env` | دامنه‌ی مورد استفاده‌ی API و ربات |
| `REACT_APP_DOMAIN_NAME` | `frontend/.env` | دامنه‌ی نمایش‌داده‌شده در رابط کاربری |

### فایل `backend/.env`

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

### فایل `frontend/.env`

```env
REACT_APP_BACKEND_URL=https://yourdomain.com
REACT_APP_DOMAIN_NAME=yourdomain.com
```

> کاربر ادمین در هر بار بالا آمدن سرویس، از `ADMIN_EMAIL` و `ADMIN_PASSWORD` ساخته/به‌روزرسانی می‌شه.

---

## 🔐 راه‌اندازی Google OAuth (اختیاری)

۱. به [console.cloud.google.com](https://console.cloud.google.com/) برو و یک **پروژه‌ی جدید** بساز.
۲. **APIs & Services → OAuth consent screen** → نوع *External* → نام اپ، ایمیل پشتیبانی و ایمیل توسعه‌دهنده رو پر کن و ذخیره کن.
۳. **Credentials → Create credentials → OAuth client ID → Web application**:
   - Authorized JavaScript origins: `https://yourdomain.com`
   - Authorized redirect URIs: `https://yourdomain.com`
۴. **Client ID** و **Client Secret** رو در **پنل ادمین → تنظیمات → Google OAuth** وارد و فعال کن.

بعد از این، دکمه‌ی ورود با گوگل در صفحات ورود و ثبت‌نام ظاهر می‌شه. با غیرفعال کردن ثبت‌نام ایمیلی می‌تونی سایت رو کاملاً **فقط گوگل** کنی.

---

## 📧 راه‌اندازی SMTP (اختیاری)

برای تأیید ایمیل و بازیابی رمز عبور لازمه.

۱. در حساب گوگل، تأیید دو مرحله‌ای رو فعال و یک **App Password** بساز ([myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)).
۲. ایمیل و رمز ۱۶ کاراکتری رو در **پنل ادمین → تنظیمات → SMTP** وارد کن.
۳. اگر می‌خوای کاربران جدید ایمیلشون رو تأیید کنن، کلید **تأیید ایمیل** رو روشن کن.

اگر SMTP تنظیم نشده باشه، گزینه‌ی «فراموشی رمز» خودکار مخفی می‌شه.

---

## 📡 مستندات API

آدرس پایه: `https://yourdomain.com/api`
احراز هویت: `Authorization: Bearer <JWT>`

### احراز هویت

| متد | مسیر | توضیح |
|-----|------|-------|
| POST | `/auth/register` | ثبت‌نام (پشتیبانی از کد رفرال `?ref=`) |
| POST | `/auth/login` | ورود و دریافت توکن JWT |
| GET | `/auth/me` | پروفایل و سقف رکورد کاربر جاری |
| POST | `/auth/verify-email` | بررسی کد ۶ رقمی |
| POST | `/auth/resend-code` | ارسال مجدد کد |
| GET | `/auth/verification-status` | فعال بودن تأیید ایمیل |
| GET | `/auth/signup-status` | فعال بودن ثبت‌نام ایمیلی |
| GET | `/auth/password-reset-status` | فعال بودن بازیابی رمز (SMTP) |
| POST | `/auth/forgot-password` | ارسال کد بازیابی |
| POST | `/auth/reset-password` | تغییر رمز با کد |
| PUT | `/auth/password` | تغییر رمز خود کاربر |
| POST | `/auth/set-initial-password` | تعیین رمز اولیه (کاربران گوگل) |
| GET | `/auth/google/config` | تنظیمات عمومی Google OAuth |
| POST | `/auth/google` | ورود/ثبت‌نام با گوگل |

### رکوردهای DNS

| متد | مسیر | توضیح |
|-----|------|-------|
| GET | `/dns/records` | رکوردهای من |
| POST | `/dns/records` | ساخت رکورد |
| PUT | `/dns/records/{id}` | ویرایش رکورد |
| DELETE | `/dns/records/{id}` | حذف رکورد |
| GET | `/dns/zones` | زون‌های در دسترس کاربر |
| GET | `/dns/records/export` | خروجی CSV رکوردهای من |
| GET | `/dns/records/import/template` | فایل نمونه‌ی CSV |
| POST | `/dns/records/import` | ورود گروهی از CSV |

### عمومی و متفرقه

| متد | مسیر | توضیح |
|-----|------|-------|
| GET | `/plans` | فهرست عمومی پلن‌ها (فیلدهای فارسی و انگلیسی) |
| GET | `/config` | تنظیمات سایت (دامنه، ارتباط، کلیدها) |
| GET | `/settings/contact` | اطلاعات تماس |
| GET | `/referral/stats` | آمار رفرال من |
| GET | `/activity/logs` | لاگ فعالیت من (صفحه‌بندی‌شده) |
| GET | `/telegram/status` | وضعیت ربات |
| GET | `/telegram/debug` | اطلاعات عیب‌یابی ربات |

### پنل مدیریت (نیازمند نقش `admin`)

| متد | مسیر | توضیح |
|-----|------|-------|
| GET | `/admin/users` | همه‌ی کاربران |
| DELETE | `/admin/users/{id}` | حذف کاربر و رکوردهایش |
| PUT | `/admin/users/{id}/plan` | تغییر پلن |
| PUT | `/admin/users/{id}/password` | تغییر رمز کاربر |
| GET | `/admin/users/{id}/records` | رکوردهای یک کاربر |
| POST | `/admin/users/bulk/plan` | تغییر پلن گروهی |
| POST | `/admin/users/bulk/delete` | حذف گروهی |
| GET | `/admin/records` | همه‌ی رکوردها |
| POST | `/admin/dns/records` | ساخت رکورد برای یک کاربر |
| DELETE | `/admin/dns/records/{id}` | حذف هر رکورد |
| GET | `/admin/records/export` | خروجی CSV همه‌ی رکوردها |
| GET | `/admin/records/import/template` | فایل نمونه‌ی CSV ادمین |
| POST | `/admin/records/import` | ورود گروهی به نام کاربران |
| GET / POST | `/admin/plans` | فهرست / ساخت پلن |
| PUT / DELETE | `/admin/plans/{plan_id}` | ویرایش / حذف پلن |
| GET / PUT | `/admin/settings` | تنظیمات سایت |
| GET / PUT | `/admin/record-types` | کلید نوع رکوردها |
| GET / POST | `/admin/zones` | فهرست / افزودن زون کلادفلر |
| PATCH / DELETE | `/admin/zones/{zone_id}` | فعال‌سازی-غیرفعال‌سازی / حذف زون |
| GET / PUT | `/admin/cf-token` | توکن کلادفلر |
| POST | `/admin/cf-token/test` | تست زنده‌ی توکن |
| GET / PUT | `/admin/google-oauth` | تنظیمات Google OAuth |
| GET / PUT | `/admin/smtp/status`، `/admin/smtp/config` | تنظیمات SMTP |
| PUT | `/admin/smtp/toggle-verification` | کلید تأیید ایمیل |
| GET / PUT | `/admin/auth/signup-status`، `/admin/auth/toggle-email-signup` | کلید ثبت‌نام ایمیلی |
| GET / PUT | `/admin/bot/status`، `/admin/bot/token`، `/admin/bot/admin-id` | تنظیمات ربات |
| POST | `/admin/bot/start`، `/admin/bot/stop` | شروع / توقف ربات |
| GET / PUT | `/admin/backup/settings` | زمان‌بندی بکاپ |
| POST | `/admin/backup/now`، `/admin/backup/restore`، `/admin/backup/test-bot` | عملیات بکاپ |
| GET | `/admin/activity/logs` | لاگ فعالیت کل پلتفرم |

مستندات تعاملی FastAPI: `https://yourdomain.com/api/docs` (در صورت فعال بودن).

---

## 📁 ساختار پروژه

```
├── install.sh                     # اسکریپت نصب و مدیریت (ddns-menu)
├── README.md                      # مستندات انگلیسی
├── README.fa.md                   # مستندات فارسی
│
├── backend/
│   ├── server.py                  # اپ FastAPI: APIها، کلادفلر، بکاپ، ربات تلگرام
│   ├── requirements.txt
│   ├── tests/                     # تست‌های رگرسیون احراز هویت
│   └── .env
│
└── frontend/
    ├── package.json / tailwind.config.js / craco.config.js
    ├── public/index.html
    └── src/
        ├── App.js                 # روتینگ
        ├── index.css              # متغیرهای تم، انیمیشن‌ها، قواعد RTL
        ├── config/site.js         # دامنه از متغیر محیطی
        ├── lib/api.js             # کلاینت Axios
        ├── lib/i18n.js            # متن‌های فارسی و انگلیسی
        ├── contexts/              # Auth، Config، Theme، Language
        ├── components/
        │   ├── Navbar.js
        │   ├── GoogleLoginButton.js
        │   ├── SecurePasswordInit.js
        │   ├── EmailVerifyPanel.js
        │   ├── RouteLoader.js
        │   └── ui/                # کامپوننت‌های shadcn/ui
        └── pages/
            ├── Landing.js         # هیرو، قابلیت‌ها، پلن‌ها، سوالات، فوتر
            ├── Login.js / Register.js / ForgotPassword.js
            ├── Dashboard.js       # رکوردها، رفرال، CSV، لاگ فعالیت
            └── Admin.js           # پنل ادمین پنج‌تبی
```

---

## 🎯 سیستم پلن‌ها

پلن‌ها کاملاً از پنل ادمین مدیریت می‌شن. پیش‌فرض‌هایی که در اولین اجرا ساخته می‌شن:

| پلن | تعداد رکورد | قیمت | توضیح |
|-----|-------------|------|-------|
| Free | ۲ | ۰ | پلن پیش‌فرض هر کاربر جدید |
| Pro | ۵۰ | ۵ دلار ماهانه | دکمه‌ی آن به تلگرام ادمین وصل می‌شه |
| Enterprise | ۵۰۰ | ۲۰ دلار ماهانه | دکمه‌ی آن به تلگرام ادمین وصل می‌شه |

- مقدار `record_limit = 0` یعنی **نامحدود**.
- سقف واقعی کاربر = سقف پلن **+** رکوردهای جایزه‌ی رفرال.
- نام، قیمت و فهرست امکانات فارسی، وقتی زبان سایت فارسی باشه به‌صورت خودکار استفاده می‌شن.

---

## 🤝 سیستم رفرال (دعوت دوستان)

```
              لینک دعوت
   کاربر A ───────────────────►  کاربر B ثبت‌نام می‌کند
      │                                 │
      │◄────── +N رکورد جایزه ───────────┘
                (N را ادمین تعیین می‌کند)
```

- هر کاربر یک کد دعوت اختصاصی داره.
- لینک دعوت: `https://yourdomain.com/register?ref=CODE`
- برای هر ثبت‌نام موفق، دعوت‌کننده **N** رکورد اضافه می‌گیره (`referral_bonus_per_invite`، پیش‌فرض `1`).

---

## 🛠 توسعه‌ی محلی

**بک‌اند**

```bash
cd backend
python3 -m venv venv && source venv/bin/activate
pip install -r requirements.txt
# فایل .env را بساز (بخش پیکربندی)
uvicorn server:app --host 0.0.0.0 --port 8001 --reload
```

**فرانت‌اند**

```bash
cd frontend
yarn install
# فایل .env با REACT_APP_BACKEND_URL و REACT_APP_DOMAIN_NAME
yarn start
```

**تست‌ها**

```bash
cd backend && pytest tests -q
```

---

## 🔧 عیب‌یابی

```bash
# وضعیت سرویس‌ها، رم، انقضای SSL و وضعیت ربات
sudo ddns-menu        # گزینه‌ی ۶

# لاگ بک‌اند
sudo journalctl -u ddns-backend -n 200 -f

# وضعیت MongoDB
sudo systemctl status mongod

# بررسی فایل محیطی
cat /opt/ddns/backend/.env
```

| نشانه | چه چیزی را بررسی کنیم |
|-------|------------------------|
| سایت باز نمی‌شه | Nginx فعاله؟ SSL معتبره؟ `ddns-menu` → گزینه‌ی ۴ (Restart) |
| رکورد ساخته نمی‌شه | صحت توکن و Zone ID (تنظیمات → تست توکن)، فعال بودن زون، فعال بودن نوع رکورد، سقف پلن |
| ربات جواب نمی‌ده | توکن و آیدی ادمین ثبت شده؟ ربات استارت شده؟ فقط یک نمونه اجراست؟ (`ddns-menu` → t) |
| ایمیل تأیید/بازیابی نمی‌رسه | اعتبار App Password، فعال بودن تأیید ایمیل |
| دکمه‌ی گوگل نیست | ذخیره بودن Client ID/Secret و تطابق دقیق origin و redirect URI با دامنه |

---

## 🔒 امنیت

- رمزها با **bcrypt** هش می‌شن و توکن‌های JWT بعد از ۷۲ ساعت منقضی می‌شن.
- همه‌ی مسیرهای ادمین در هر درخواست با نقش `admin` محافظت می‌شن.
- CORS محدود به دامنه‌ی سایت (`CORS_ORIGINS`).
- هدرهای امنیتی Nginx و TLS با Let's Encrypt.
- کلیدها فقط در فایل‌های `.env` نگهداری می‌شن؛ نه کامیت می‌شن و نه به فرانت‌اند می‌رن.
- تأیید ایمیل اختیاری و حالت اختیاری «فقط ورود با گوگل».

---

## 💬 پشتیبانی و ارتباط با توسعه‌دهنده

گزارش باگ، نظر، پیشنهاد، انتقاد و ایده‌ی جدید — همه‌شون خوش‌آمدن. مستقیم در تلگرام با توسعه‌دهنده در ارتباط باش:

<div align="center">

### [![Telegram](https://img.shields.io/badge/@asangozar__support-26A5E4?style=for-the-badge&logo=telegram&logoColor=white)](https://t.me/asangozar_support)

**توسعه‌دهنده:** [@asangozar_support](https://t.me/asangozar_support)

</div>

هنگام گزارش باگ لطفاً این‌ها رو بفرست:

۱. چه کاری انجام دادی و چه انتظاری داشتی.
۲. سیستم‌عامل/نوع سرور و روش نصب.
۳. خروجی مرتبط `sudo journalctl -u ddns-backend -n 100`.
۴. اگر مشکل ظاهریه، یک اسکرین‌شات.

ایشوهای گیت‌هاب: [github.com/admin6501/ddns-khalilv2/issues](https://github.com/admin6501/ddns-khalilv2/issues)

---

## 📄 مجوز

این پروژه تحت مجوز [MIT](LICENSE) منتشر شده است.

<div align="center">

اگر این پروژه به کارت اومد، یک ستاره ⭐ بده

</div>
