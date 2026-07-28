from fastapi import FastAPI, APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, EmailStr
from typing import List, Optional
import uuid
import string
import random
from datetime import datetime, timezone, timedelta
import bcrypt
import jwt
import httpx
import asyncio
import subprocess
import tempfile
import shutil
import csv
import io
from fastapi.responses import Response

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env', interpolate=False)

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Cloudflare config
CF_API_TOKEN = os.environ.get('CLOUDFLARE_API_TOKEN', '').strip().strip('"').strip("'")
CF_ZONE_ID = os.environ.get('CLOUDFLARE_ZONE_ID', '').strip().strip('"').strip("'")
CF_API_BASE = "https://api.cloudflare.com/client/v4"
DOMAIN_NAME = os.environ.get('DOMAIN_NAME', 'example.com').strip().strip('"').strip("'")

# DNS zone domain (auto-detected from Cloudflare, fallback to DOMAIN_NAME)
CF_ZONE_DOMAIN = DOMAIN_NAME

# JWT config
JWT_SECRET = os.environ.get('JWT_SECRET', 'fallback_secret')
JWT_ALGORITHM = "HS256"
JWT_EXPIRATION_HOURS = 72

# Plan limits
PLAN_LIMITS = {"free": 2, "pro": 50, "enterprise": 500}

# Create the main app
app = FastAPI()
api_router = APIRouter(prefix="/api")
security = HTTPBearer()

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# ============== MODELS ==============

class UserRegister(BaseModel):
    email: EmailStr
    password: str = Field(min_length=6)
    name: str = Field(min_length=2)
    referral_code: Optional[str] = None

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class UserResponse(BaseModel):
    id: str
    email: str
    name: str
    plan: str
    role: str
    record_count: int
    record_limit: int
    created_at: str

class DNSRecordCreate(BaseModel):
    name: str = Field(min_length=1, description="Subdomain name")
    record_type: str = Field(description="A, AAAA, CNAME, or NS")
    content: str = Field(min_length=1, description="IP or target domain")
    ttl: int = Field(default=1, ge=1, le=86400)
    proxied: bool = Field(default=False)
    zone_id: Optional[str] = Field(default=None, description="Cloudflare zone ID (optional, defaults to primary)")

class AdminDNSRecordCreate(BaseModel):
    user_id: str
    name: str = Field(min_length=1)
    record_type: str
    content: str = Field(min_length=1)
    ttl: int = Field(default=1, ge=1, le=86400)
    proxied: bool = Field(default=False)
    zone_id: Optional[str] = Field(default=None, description="Cloudflare zone ID (optional, defaults to primary)")

class DNSRecordUpdate(BaseModel):
    content: Optional[str] = None
    ttl: Optional[int] = Field(default=None, ge=1, le=86400)
    proxied: Optional[bool] = None

class PlanUpdate(BaseModel):
    plan: str = Field(description="plan id")

class PasswordUpdate(BaseModel):
    new_password: str = Field(min_length=6)

class BulkPlanUpdate(BaseModel):
    user_ids: List[str] = Field(min_length=1)
    plan: str

class BulkDeleteUsers(BaseModel):
    user_ids: List[str] = Field(min_length=1)

class PlanCreate(BaseModel):
    plan_id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    name_fa: str = Field(min_length=1)
    price: str
    price_fa: str
    record_limit: int = Field(ge=0)
    features: List[str] = []
    features_fa: List[str] = []
    popular: bool = False
    sort_order: int = Field(default=0)

class PlanEdit(BaseModel):
    name: Optional[str] = None
    name_fa: Optional[str] = None
    price: Optional[str] = None
    price_fa: Optional[str] = None
    record_limit: Optional[int] = Field(default=None, ge=0)
    features: Optional[List[str]] = None
    features_fa: Optional[List[str]] = None
    popular: Optional[bool] = None
    sort_order: Optional[int] = None

class SettingsUpdate(BaseModel):
    telegram_id: Optional[str] = None
    telegram_url: Optional[str] = None
    contact_message_en: Optional[str] = None
    contact_message_fa: Optional[str] = None
    referral_bonus_per_invite: Optional[int] = None

class ChangeMyPassword(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=6)

# ============== HELPERS ==============

def generate_referral_code(length=8):
    chars = string.ascii_lowercase + string.digits
    return ''.join(random.choices(chars, k=length))

def normalize_email(email: str) -> str:
    """Canonical form for storing and looking up an email address.
    Addresses are case-insensitive in practice, so we keep exactly one
    spelling in the database and normalize every lookup through here."""
    return (email or "").strip().lower()

def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')

def verify_password(password: str, hashed: str) -> bool:
    """Check a password against a bcrypt hash.

    Returns False instead of raising when the stored hash is empty or
    malformed — OAuth-only accounts carry an empty password_hash, and
    bcrypt raises ValueError('Invalid salt') on those."""
    if not password or not hashed:
        return False
    try:
        return bcrypt.checkpw(password.encode('utf-8'), hashed.encode('utf-8'))
    except (ValueError, TypeError):
        return False

def create_token(user_id: str, email: str) -> str:
    payload = {
        "user_id": user_id,
        "email": email,
        "exp": datetime.now(timezone.utc) + timedelta(hours=JWT_EXPIRATION_HOURS)
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

# ============== EMAIL VERIFICATION HELPER ==============

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def _send_smtp_html(email: str, subject: str, html_body: str, log_label: str = "email") -> bool:
    """Send an HTML email via Gmail SMTP. Returns True on success, False on any failure."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        logger.warning(f"SMTP not configured, skipping {log_label} to {email}")
        return False
    try:
        msg = MIMEMultipart()
        msg['From'] = SMTP_EMAIL
        msg['To'] = email
        msg['Subject'] = subject
        msg.attach(MIMEText(html_body, 'html'))
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(SMTP_EMAIL, SMTP_PASSWORD)
        server.sendmail(SMTP_EMAIL, email, msg.as_string())
        server.quit()
        logger.info(f"{log_label} sent to {email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send {log_label} to {email}: {e}")
        return False


async def send_verification_email(email: str, code: str):
    """Send verification code via Gmail SMTP."""
    body = f"""
        <html><body style="font-family:Arial,sans-serif;direction:rtl;text-align:center;padding:20px;">
        <h2>کد تأیید ایمیل / Email Verification Code</h2>
        <div style="background:#f0f0f0;padding:20px;border-radius:10px;display:inline-block;margin:20px 0;">
            <h1 style="letter-spacing:8px;color:#333;font-size:36px;">{code}</h1>
        </div>
        <p>این کد تا ۱۰ دقیقه معتبر است.</p>
        <p>This code is valid for 10 minutes.</p>
        </body></html>
        """
    return _send_smtp_html(email, f'Email Verification Code: {code}', body, "Verification email")

def generate_verification_code():
    return str(random.randint(100000, 999999))

async def is_email_verification_enabled():
    """Check if email verification is enabled (SMTP configured + admin toggle)."""
    if not SMTP_EMAIL or not SMTP_PASSWORD:
        return False
    settings = await db.settings.find_one({"key": "site_settings"}, {"_id": 0})
    if settings and settings.get("email_verification_enabled") is False:
        return False
    # Default: enabled if SMTP is configured
    return True

# ============== ACTIVITY LOG HELPER ==============

async def log_activity(user_id: str, user_email: str, action: str, details: str = "", ip: str = ""):
    """Log user/admin activity to activity_logs collection."""
    log_doc = {
        "id": str(uuid.uuid4()),
        "user_id": user_id,
        "user_email": user_email,
        "action": action,
        "details": details,
        "ip": ip,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    try:
        await db.activity_logs.insert_one(log_doc)
    except Exception as e:
        logger.warning(f"Failed to log activity: {e}")

async def _resolve_plan_record_limit(plan_id: str) -> int:
    """Look up record limit for a plan_id. Falls back to PLAN_LIMITS cache.
    Raises HTTPException(400) if the plan is unknown."""
    plan_doc = await db.plans.find_one({"plan_id": plan_id}, {"_id": 0})
    if plan_doc:
        return plan_doc["record_limit"]
    if plan_id not in PLAN_LIMITS:
        raise HTTPException(status_code=400, detail=f"Invalid plan: {plan_id}")
    return PLAN_LIMITS[plan_id]


async def _delete_user_with_records(uid: str) -> int:
    """Delete a user, their CF records (best-effort) and their dns_records docs.
    Returns the number of CF records that existed for that user."""
    user_records = await db.dns_records.find({"user_id": uid}, {"_id": 0}).to_list(500)
    for rec in user_records:
        try:
            await cf_delete_record(rec["cf_record_id"], zone_id=rec.get("zone_id"))
        except Exception as e:
            logger.warning(f"Failed to delete CF record {rec['cf_record_id']}: {e}")
    await db.dns_records.delete_many({"user_id": uid})
    await db.users.delete_one({"id": uid})
    return len(user_records)


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        payload = jwt.decode(credentials.credentials, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user = await db.users.find_one({"id": payload["user_id"]}, {"_id": 0})
        if not user:
            raise HTTPException(status_code=401, detail="User not found")
        return user
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expired")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Invalid token")

async def get_admin_user(current_user: dict = Depends(get_current_user)):
    if current_user.get("role") != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user

# ============== CLOUDFLARE API ==============

async def cf_fetch_zone_domain():
    """Fetch actual domain name from Cloudflare zone. Called on startup."""
    global CF_ZONE_DOMAIN
    if not CF_ZONE_ID or not CF_API_TOKEN:
        logger.warning("Cloudflare zone ID or API token not set, using DOMAIN_NAME as fallback")
        return
    try:
        async with httpx.AsyncClient(timeout=30.0) as client_http:
            response = await client_http.get(
                f"{CF_API_BASE}/zones/{CF_ZONE_ID}",
                headers={"Authorization": f"Bearer {CF_API_TOKEN}"}
            )
            data = response.json()
            if data.get("success") and data.get("result"):
                CF_ZONE_DOMAIN = data["result"]["name"]
                logger.info(f"Cloudflare zone domain detected: {CF_ZONE_DOMAIN}")
            else:
                logger.warning(f"Could not fetch zone domain, using DOMAIN_NAME: {DOMAIN_NAME}")
    except Exception as e:
        logger.warning(f"Failed to fetch zone domain from Cloudflare: {e}")

async def get_zone_status(zone_id: str) -> str:
    """Return 'active' or 'disabled' for a given zone_id.
    Primary zone defaults to active unless an override doc exists in cf_zones."""
    if not zone_id:
        return "active"
    doc = await db.cf_zones.find_one({"zone_id": zone_id}, {"status": 1, "_id": 0})
    if not doc:
        return "active"
    return doc.get("status", "active")

async def ensure_zone_enabled(zone_id: str):
    """Raise 400 if the zone is disabled."""
    zstatus = await get_zone_status(zone_id or CF_ZONE_ID)
    if zstatus != "active":
        raise HTTPException(status_code=400, detail="This zone is disabled. Please enable it from admin settings or choose another zone.")

async def get_zone_config(zone_id: str = None):
    """Get zone config (zone_id, api_token, domain) for a given zone_id.
    Falls back to primary zone if zone_id is None or matches primary."""
    if not zone_id or zone_id == CF_ZONE_ID:
        return {"zone_id": CF_ZONE_ID, "api_token": CF_API_TOKEN, "domain": CF_ZONE_DOMAIN}
    zone_doc = await db.cf_zones.find_one({"zone_id": zone_id}, {"_id": 0})
    if not zone_doc:
        raise HTTPException(status_code=400, detail="Zone not found")
    return {
        "zone_id": zone_doc["zone_id"],
        "api_token": zone_doc.get("api_token", CF_API_TOKEN),
        "domain": zone_doc.get("domain", ""),
    }

async def cf_create_record(name: str, record_type: str, content: str, ttl: int = 1, proxied: bool = False, zone_id: str = None):
    zone_cfg = await get_zone_config(zone_id)
    full_name = f"{name}.{zone_cfg['domain']}" if name != "@" else zone_cfg['domain']
    async with httpx.AsyncClient(timeout=30.0) as client_http:
        response = await client_http.post(
            f"{CF_API_BASE}/zones/{zone_cfg['zone_id']}/dns_records",
            headers={"Authorization": f"Bearer {zone_cfg['api_token']}", "Content-Type": "application/json"},
            json={"type": record_type, "name": full_name, "content": content, "ttl": ttl, "proxied": proxied}
        )
        data = response.json()
        if not data.get("success"):
            errors = data.get("errors", [])
            error_msg = errors[0].get("message", "Unknown error") if errors else "Failed to create record"
            raise HTTPException(status_code=400, detail=error_msg)
        return data["result"], zone_cfg

async def cf_update_record(cf_record_id: str, record_type: str, name: str, content: str, ttl: int = 1, proxied: bool = False, zone_id: str = None):
    zone_cfg = await get_zone_config(zone_id)
    async with httpx.AsyncClient(timeout=30.0) as client_http:
        response = await client_http.put(
            f"{CF_API_BASE}/zones/{zone_cfg['zone_id']}/dns_records/{cf_record_id}",
            headers={"Authorization": f"Bearer {zone_cfg['api_token']}", "Content-Type": "application/json"},
            json={"type": record_type, "name": name, "content": content, "ttl": ttl, "proxied": proxied}
        )
        data = response.json()
        if not data.get("success"):
            errors = data.get("errors", [])
            error_msg = errors[0].get("message", "Unknown error") if errors else "Failed to update record"
            raise HTTPException(status_code=400, detail=error_msg)
        return data["result"]

async def cf_delete_record(cf_record_id: str, zone_id: str = None):
    zone_cfg = await get_zone_config(zone_id)
    async with httpx.AsyncClient(timeout=30.0) as client_http:
        response = await client_http.delete(
            f"{CF_API_BASE}/zones/{zone_cfg['zone_id']}/dns_records/{cf_record_id}",
            headers={"Authorization": f"Bearer {zone_cfg['api_token']}"}
        )
        if response.status_code == 404:
            logger.info(f"CF record {cf_record_id} already deleted (404), treating as success")
            return True
        data = response.json()
        if not data.get("success"):
            errors = data.get("errors", [])
            if errors and any(
                "not found" in str(err.get("message", "")).lower() or
                "does not exist" in str(err.get("message", "")).lower()
                for err in errors
            ):
                logger.info(f"CF record {cf_record_id} not found in CF, treating as success")
                return True
            error_msg = errors[0].get("message", "Unknown error") if errors else "Failed to delete record"
            raise HTTPException(status_code=400, detail=error_msg)
        return True

# ============== AUTH ROUTES ==============

@api_router.post("/auth/register")
async def register(user_data: UserRegister):
    # Check if email registration form is disabled by admin
    settings = await db.settings.find_one({"key": "site_settings"}, {"_id": 0})
    email_signup_enabled = (settings or {}).get("email_signup_enabled", True)
    if not email_signup_enabled:
        raise HTTPException(
            status_code=403,
            detail="Email registration is currently disabled. Please sign up with Google.",
        )
    # Normalize before any lookup or storage so that Foo@Gmail.com and
    # foo@gmail.com are the same account everywhere.
    email = normalize_email(user_data.email)

    # Only allow Gmail addresses
    if not email.endswith("@gmail.com"):
        raise HTTPException(status_code=400, detail="Only Gmail addresses (@gmail.com) are allowed for registration.")

    existing = await db.users.find_one({"email": email}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    # Get free plan record limit (single source of truth: plans collection / PLAN_LIMITS cache)
    default_free = PLAN_LIMITS.get("free", 2)
    
    # Generate unique referral code
    ref_code = generate_referral_code()
    while await db.users.find_one({"referral_code": ref_code}):
        ref_code = generate_referral_code()
    
    user_id = str(uuid.uuid4())
    user_doc = {
        "id": user_id,
        "email": email,
        "name": user_data.name,
        "password_hash": hash_password(user_data.password),
        "plan": "free",
        "role": "user",
        "record_count": 0,
        "record_limit": default_free,
        "referral_code": ref_code,
        "referred_by": None,
        "referral_count": 0,
        "referral_bonus": 0,
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    
    # Process referral
    if user_data.referral_code:
        referrer = await db.users.find_one({"referral_code": user_data.referral_code}, {"_id": 0})
        if referrer:
            user_doc["referred_by"] = referrer["id"]
            
            # Get bonus amount from settings
            settings = await db.settings.find_one({"key": "site_settings"}, {"_id": 0})
            bonus = (settings or {}).get("referral_bonus_per_invite", 1)
            
            # Give referrer bonus records
            await db.users.update_one(
                {"id": referrer["id"]},
                {
                    "$inc": {
                        "record_limit": bonus,
                        "referral_count": 1,
                        "referral_bonus": bonus
                    }
                }
            )
            logger.info(f"Referral: {referrer['email']} gets +{bonus} records from {email}")
    
    await db.users.insert_one(user_doc)
    
    # Check if email verification is needed
    verify_enabled = await is_email_verification_enabled()
    if verify_enabled:
        user_doc["email_verified"] = False
        await db.users.update_one({"id": user_id}, {"$set": {"email_verified": False}})
        code = generate_verification_code()
        await db.verification_codes.delete_many({"email": email})
        await db.verification_codes.insert_one({
            "email": email,
            "code": code,
            "user_id": user_id,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
        })
        await send_verification_email(email, code)
    else:
        user_doc["email_verified"] = True
        await db.users.update_one({"id": user_id}, {"$set": {"email_verified": True}})

    token = create_token(user_id, email)
    await log_activity(user_id, email, "register", "New account created")
    
    # Notify admin via Telegram bot
    try:
        if telegram_bot_app and telegram_bot_app.running and TELEGRAM_ADMIN_ID:
            import asyncio
            asyncio.create_task(_notify_admin_web_register(user_data.name, email))
    except Exception:
        pass
    
    return {
        "token": token,
        "email_verification_required": verify_enabled,
        "user": {
            "id": user_id,
            "email": email,
            "name": user_data.name,
            "plan": "free",
            "role": "user",
            "record_count": 0,
            "record_limit": default_free,
            "referral_code": ref_code,
            "referral_count": 0,
            "referral_bonus": 0,
            "email_verified": not verify_enabled,
            "created_at": user_doc["created_at"]
        }
    }

@api_router.post("/auth/verify-email")
async def verify_email(body: dict):
    """Verify email with 6-digit code."""
    email = normalize_email(body.get("email", ""))
    code = body.get("code", "").strip()
    if not email or not code:
        raise HTTPException(status_code=400, detail="Email and code are required")
    
    record = await db.verification_codes.find_one({"email": email, "code": code})
    if not record:
        raise HTTPException(status_code=400, detail="Invalid verification code")
    
    # Check expiry
    if record.get("expires_at"):
        expires = datetime.fromisoformat(record["expires_at"])
        if datetime.now(timezone.utc) > expires:
            await db.verification_codes.delete_many({"email": email})
            raise HTTPException(status_code=400, detail="Code expired. Please request a new one.")
    
    # Mark user as verified
    await db.users.update_one({"email": email}, {"$set": {"email_verified": True}})
    await db.verification_codes.delete_many({"email": email})
    
    user = await db.users.find_one({"email": email}, {"_id": 0, "password_hash": 0})
    return {"success": True, "user": user}

@api_router.post("/auth/resend-code")
async def resend_verification_code(body: dict):
    """Resend verification code to email."""
    email = normalize_email(body.get("email", ""))
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.get("email_verified"):
        raise HTTPException(status_code=400, detail="Email already verified")
    
    code = generate_verification_code()
    await db.verification_codes.delete_many({"email": email})
    await db.verification_codes.insert_one({
        "email": email,
        "code": code,
        "user_id": user["id"],
        "created_at": datetime.now(timezone.utc).isoformat(),
        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
    })
    sent = await send_verification_email(email, code)
    if not sent:
        raise HTTPException(status_code=500, detail="Failed to send email")
    return {"success": True}

@api_router.get("/auth/verification-status")
async def verification_status():
    """Check if email verification is enabled."""
    enabled = await is_email_verification_enabled()
    return {"email_verification_enabled": enabled}


# ============== AUTH PUBLIC FLAGS ==============

@api_router.get("/auth/signup-status")
async def signup_status():
    """Public flag — whether the email/password signup form is shown."""
    settings = await db.settings.find_one({"key": "site_settings"}, {"_id": 0})
    enabled = bool((settings or {}).get("email_signup_enabled", True))
    return {"email_signup_enabled": enabled}


@api_router.get("/auth/password-reset-status")
async def password_reset_status():
    """Public flag — whether forgot-password is available (requires SMTP)."""
    has_smtp = bool(SMTP_EMAIL and SMTP_PASSWORD)
    return {"enabled": has_smtp}


# ============== FORGOT / RESET PASSWORD ==============

async def send_password_reset_email(email: str, code: str):
    """Send a 6-digit password reset code via Gmail SMTP."""
    body = f"""
        <html><body style="font-family:Arial,sans-serif;direction:rtl;text-align:center;padding:20px;">
        <h2>کد بازنشانی رمز عبور / Password Reset Code</h2>
        <p>برای بازنشانی رمز عبور خود از کد زیر استفاده کنید:</p>
        <p>Use the code below to reset your password:</p>
        <div style="background:#f0f0f0;padding:20px;border-radius:10px;display:inline-block;margin:20px 0;">
            <h1 style="letter-spacing:8px;color:#333;font-size:36px;">{code}</h1>
        </div>
        <p>این کد تا ۱۵ دقیقه معتبر است.</p>
        <p>This code is valid for 15 minutes.</p>
        <p style="color:#888;font-size:12px;margin-top:24px;">If you did not request this, simply ignore this email.</p>
        </body></html>
        """
    return _send_smtp_html(email, f'Password Reset Code: {code}', body, "Password reset email")


@api_router.post("/auth/forgot-password")
async def forgot_password(body: dict):
    """Send a password reset code if SMTP is configured. Always returns 200 to avoid leaking accounts."""
    has_smtp = bool(SMTP_EMAIL and SMTP_PASSWORD)
    if not has_smtp:
        raise HTTPException(
            status_code=503,
            detail="Password reset is currently unavailable — SMTP is not configured.",
        )
    email = normalize_email(body.get("email"))
    if not email:
        raise HTTPException(status_code=400, detail="Email is required")
    user = await db.users.find_one({"email": email}, {"_id": 0})
    # Don't reveal whether email exists. Only send if the user exists.
    if user:
        code = generate_verification_code()
        await db.password_reset_codes.delete_many({"email": email})
        await db.password_reset_codes.insert_one({
            "email": email,
            "code": code,
            "user_id": user["id"],
            "created_at": datetime.now(timezone.utc).isoformat(),
            "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
        })
        await send_password_reset_email(email, code)
    return {"success": True}


@api_router.post("/auth/reset-password")
async def reset_password(body: dict):
    """Verify the 6-digit code and set a new password."""
    has_smtp = bool(SMTP_EMAIL and SMTP_PASSWORD)
    if not has_smtp:
        raise HTTPException(status_code=503, detail="Password reset is currently unavailable.")
    email = normalize_email(body.get("email"))
    code = (body.get("code") or "").strip()
    new_password = body.get("new_password") or ""
    if not email or not code or not new_password:
        raise HTTPException(status_code=400, detail="Email, code and new password are required")
    if len(new_password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    record = await db.password_reset_codes.find_one({"email": email, "code": code})
    if not record:
        raise HTTPException(status_code=400, detail="Invalid reset code")
    expires = datetime.fromisoformat(record["expires_at"])
    if datetime.now(timezone.utc) > expires:
        await db.password_reset_codes.delete_many({"email": email})
        raise HTTPException(status_code=400, detail="Reset code expired. Please request a new one.")
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    await db.users.update_one(
        {"id": user["id"]},
        {"$set": {"password_hash": hash_password(new_password), "requires_password_setup": False}},
    )
    await db.password_reset_codes.delete_many({"email": email})
    await log_activity(user["id"], email, "password_reset", "Password reset via email code")
    return {"success": True}

@api_router.post("/auth/login")
async def login(user_data: UserLogin):
    user = await db.users.find_one({"email": normalize_email(user_data.email)}, {"_id": 0})
    if not user or not verify_password(user_data.password, user.get("password_hash", "")):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    
    token = create_token(user["id"], user["email"])
    await log_activity(user["id"], user["email"], "login", "User logged in")
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "plan": user["plan"],
            "role": user.get("role", "user"),
            "record_count": user["record_count"],
            "record_limit": user["record_limit"],
            "referral_code": user.get("referral_code", ""),
            "referral_count": user.get("referral_count", 0),
            "referral_bonus": user.get("referral_bonus", 0),
            "email_verified": user.get("email_verified", True),
            "requires_password_setup": not bool(user.get("password_hash")),
            "created_at": user["created_at"]
        }
    }

@api_router.get("/auth/me")
async def get_me(current_user: dict = Depends(get_current_user)):
    record_count = await db.dns_records.count_documents({"user_id": current_user["id"]})
    return {
        "id": current_user["id"],
        "email": current_user["email"],
        "name": current_user["name"],
        "plan": current_user["plan"],
        "role": current_user.get("role", "user"),
        "record_count": record_count,
        "record_limit": current_user["record_limit"],
        "referral_code": current_user.get("referral_code", ""),
        "referral_count": current_user.get("referral_count", 0),
        "referral_bonus": current_user.get("referral_bonus", 0),
        "email_verified": current_user.get("email_verified", True),
        "requires_password_setup": not bool(current_user.get("password_hash")),
        "created_at": current_user["created_at"]
    }

# ============== RECORD TYPES (admin toggles) ==============

SUPPORTED_RECORD_TYPES = ["A", "AAAA", "CNAME", "NS"]
TYPE_EMOJI = {"A": "🅰️", "AAAA": "🔤", "CNAME": "🔀", "NS": "🌐"}

async def _get_enabled_record_types():
    """Return record types currently enabled for user record creation.
    Stored as a 'disabled' list so newly-supported types default to enabled."""
    doc = await db.settings.find_one({"key": "record_types"}, {"_id": 0}) or {}
    disabled = set(doc.get("disabled", []))
    return [t for t in SUPPORTED_RECORD_TYPES if t not in disabled]


# ============== GOOGLE OAUTH ==============

async def _get_google_oauth_settings():
    doc = await db.settings.find_one({"key": "google_oauth"}, {"_id": 0}) or {}
    return {
        "enabled": bool(doc.get("enabled", False)),
        "client_id": doc.get("client_id", ""),
        "client_secret": doc.get("client_secret", ""),
    }

@api_router.get("/auth/google/config")
async def public_google_config():
    """Public endpoint — returns whether Google login is enabled and the client_id
    so the frontend can render the GoogleLogin button. Secret is NEVER returned."""
    s = await _get_google_oauth_settings()
    return {"enabled": s["enabled"] and bool(s["client_id"]), "client_id": s["client_id"]}

class GoogleLoginPayload(BaseModel):
    credential: str  # ID token from Google

@api_router.post("/auth/google")
async def google_login(payload: GoogleLoginPayload):
    """Verify Google ID token, create or merge user by email, return our JWT."""
    s = await _get_google_oauth_settings()
    if not s["enabled"] or not s["client_id"]:
        raise HTTPException(status_code=400, detail="Google login is disabled.")
    try:
        from google.oauth2 import id_token as g_id_token
        from google.auth.transport import requests as g_requests
        # Allow up to 30s clock skew (some servers have small drift)
        idinfo = g_id_token.verify_oauth2_token(
            payload.credential, g_requests.Request(), s["client_id"], clock_skew_in_seconds=30
        )
    except ValueError as e:
        # Surface the underlying reason so admin can fix (wrong client_id, expired, audience mismatch, etc.)
        logger.error(f"Google ID token verification failed: {e}")
        raise HTTPException(status_code=401, detail=f"Google token verification failed: {str(e)[:300]}")
    except Exception as e:
        # Include exception type + message so we can diagnose unusual failures
        logger.error(f"Google ID token verification unexpected error: {type(e).__name__}: {e}", exc_info=True)
        raise HTTPException(status_code=401, detail=f"Google token error: {type(e).__name__}: {str(e)[:300]}")

    email = normalize_email(idinfo.get("email"))
    if not email:
        raise HTTPException(status_code=400, detail="Email not present in Google account")
    if not idinfo.get("email_verified", False):
        raise HTTPException(status_code=400, detail="Google email not verified")
    name = idinfo.get("name") or idinfo.get("given_name") or email.split("@")[0]
    google_sub = idinfo.get("sub", "")

    # Find existing user by email and merge, or create
    user = await db.users.find_one({"email": email}, {"_id": 0})
    if user:
        if not user.get("google_id"):
            await db.users.update_one(
                {"id": user["id"]},
                {"$set": {"google_id": google_sub, "email_verified": True}}
            )
    else:
        # Create new user
        user_id = str(uuid.uuid4())
        referral_code = uuid.uuid4().hex[:8]
        user_doc = {
            "id": user_id,
            "email": email,
            "name": name,
            "password_hash": "",  # Google-only account, no password
            "google_id": google_sub,
            "plan": "free",
            "role": "user",
            "record_count": 0,
            "record_limit": PLAN_LIMITS.get("free", 2),
            "referral_code": referral_code,
            "referred_by": None,
            "referral_count": 0,
            "referral_bonus": 0,
            "email_verified": True,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        await db.users.insert_one(user_doc)
        user = user_doc
        # Notify admin (telegram if configured)
        try:
            if telegram_bot_app and telegram_bot_app.running and TELEGRAM_ADMIN_ID:
                import asyncio as _asy
                _asy.create_task(_notify_admin_web_register(name, email))
        except Exception:
            pass

    token = create_token(user["id"], user["email"])
    await log_activity(user["id"], user["email"], "google_login", "Logged in via Google")
    return {
        "token": token,
        "user": {
            "id": user["id"],
            "email": user["email"],
            "name": user["name"],
            "plan": user.get("plan", "free"),
            "role": user.get("role", "user"),
            "record_count": user.get("record_count", 0),
            "record_limit": user.get("record_limit", PLAN_LIMITS.get("free", 2)),
            "referral_code": user.get("referral_code", ""),
            "referral_count": user.get("referral_count", 0),
            "referral_bonus": user.get("referral_bonus", 0),
            "email_verified": True,
            "requires_password_setup": not bool(user.get("password_hash")),
            "created_at": user.get("created_at", datetime.now(timezone.utc).isoformat()),
        }
    }

# ============== ADMIN: GOOGLE OAUTH SETTINGS ==============

class GoogleOAuthUpdate(BaseModel):
    client_id: Optional[str] = None
    client_secret: Optional[str] = None
    enabled: Optional[bool] = None

@api_router.get("/admin/google-oauth")
async def admin_get_google_oauth(admin: dict = Depends(get_admin_user)):
    s = await _get_google_oauth_settings()
    secret = s["client_secret"]
    masked = ""
    if secret:
        masked = secret[:6] + "***" + secret[-4:] if len(secret) > 12 else "***"
    return {
        "enabled": s["enabled"],
        "client_id": s["client_id"],
        "client_secret_masked": masked,
        "has_secret": bool(secret),
    }

@api_router.put("/admin/google-oauth")
async def admin_update_google_oauth(body: GoogleOAuthUpdate, admin: dict = Depends(get_admin_user)):
    update = {}
    if body.client_id is not None:
        update["client_id"] = body.client_id.strip()
    if body.client_secret is not None and body.client_secret.strip():
        # Only update secret if provided and non-empty (so user can leave blank to keep existing)
        update["client_secret"] = body.client_secret.strip()
    if body.enabled is not None:
        update["enabled"] = bool(body.enabled)
    if not update:
        raise HTTPException(status_code=400, detail="No fields to update")
    await db.settings.update_one(
        {"key": "google_oauth"},
        {"$set": {**update, "key": "google_oauth"}},
        upsert=True,
    )
    await log_activity(admin["id"], admin["email"], "google_oauth_updated", f"Fields: {list(update.keys())}")
    return {"success": True}

# ============== REFERRAL ROUTES ==============

@api_router.get("/referral/stats")
async def get_referral_stats(current_user: dict = Depends(get_current_user)):
    # Get list of users referred by current user
    referred_users = await db.users.find(
        {"referred_by": current_user["id"]},
        {"_id": 0, "id": 1, "name": 1, "email": 1, "created_at": 1}
    ).to_list(100)
    
    # Get bonus per invite from settings
    settings = await db.settings.find_one({"key": "site_settings"}, {"_id": 0})
    bonus_per_invite = (settings or {}).get("referral_bonus_per_invite", 1)
    
    return {
        "referral_code": current_user.get("referral_code", ""),
        "referral_count": current_user.get("referral_count", 0),
        "referral_bonus": current_user.get("referral_bonus", 0),
        "bonus_per_invite": bonus_per_invite,
        "referred_users": [
            {"name": u["name"], "date": u["created_at"]}
            for u in referred_users
        ]
    }


@api_router.put("/auth/password")
async def change_my_password(pw_data: ChangeMyPassword, current_user: dict = Depends(get_current_user)):
    """Allow any user to change their own password."""
    if not current_user.get("password_hash"):
        raise HTTPException(
            status_code=400,
            detail="This account has no password yet. Use the set-initial-password flow instead.",
        )
    if not verify_password(pw_data.current_password, current_user["password_hash"]):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"password_hash": hash_password(pw_data.new_password)}}
    )
    await log_activity(current_user["id"], current_user["email"], "password_changed", "Self password change")
    return {"message": "Password changed successfully"}


class SetInitialPassword(BaseModel):
    new_password: str = Field(..., min_length=6)

@api_router.post("/auth/set-initial-password")
async def set_initial_password(body: SetInitialPassword, current_user: dict = Depends(get_current_user)):
    """Allow OAuth users (with no password yet) to set their initial password.
    This endpoint refuses if the user already has a password — they must use /auth/password instead."""
    if current_user.get("password_hash"):
        raise HTTPException(status_code=400, detail="Password already set. Use the change-password flow instead.")
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$set": {"password_hash": hash_password(body.new_password)}}
    )
    await log_activity(current_user["id"], current_user["email"], "password_initialized", "Set initial password (OAuth user)")
    return {"message": "Password set successfully"}


# ============== DNS ROUTES ==============

@api_router.get("/dns/records")
async def list_records(current_user: dict = Depends(get_current_user)):
    records = await db.dns_records.find(
        {"user_id": current_user["id"]},
        {"_id": 0}
    ).to_list(100)
    return {"records": records, "count": len(records)}

# ============== BULK IMPORT / EXPORT ==============

CSV_HEADERS = ["name", "record_type", "content", "ttl", "proxied", "zone_domain"]

def _records_to_csv(records: list, zone_domain_map: dict) -> str:
    """Convert a list of record dicts to a CSV string."""
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(CSV_HEADERS)
    for r in records:
        zd = zone_domain_map.get(r.get("zone_id") or CF_ZONE_ID, CF_ZONE_DOMAIN)
        writer.writerow([
            r.get("name", ""),
            r.get("record_type", ""),
            r.get("content", ""),
            r.get("ttl", 1),
            "true" if r.get("proxied") else "false",
            zd,
        ])
    return buf.getvalue()

async def _build_zone_maps():
    """Return (domain_to_zone_id, zone_id_to_domain, enabled_ids)."""
    domain_to_id = {}
    id_to_domain = {}
    enabled = set()
    if CF_ZONE_ID:
        domain_to_id[CF_ZONE_DOMAIN.lower()] = CF_ZONE_ID
        id_to_domain[CF_ZONE_ID] = CF_ZONE_DOMAIN
    db_zones = await db.cf_zones.find({}, {"_id": 0}).to_list(100)
    status_map = {z.get("zone_id"): z.get("status", "active") for z in db_zones}
    for z in db_zones:
        zid = z.get("zone_id")
        dom = z.get("domain", "")
        if dom:
            domain_to_id[dom.lower()] = zid
            id_to_domain[zid] = dom
    # Enabled ids (primary counted as active unless override disabled)
    if CF_ZONE_ID and status_map.get(CF_ZONE_ID, "active") == "active":
        enabled.add(CF_ZONE_ID)
    for z in db_zones:
        if z.get("zone_id") != CF_ZONE_ID and z.get("status", "active") == "active":
            enabled.add(z.get("zone_id"))
    return domain_to_id, id_to_domain, enabled

def _parse_csv_records(csv_text: str) -> list:
    """Parse CSV text into list of dicts. Raises ValueError on malformed header."""
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        raise ValueError("Empty CSV")
    normalized = [h.strip().lower() for h in reader.fieldnames]
    required = {"name", "record_type", "content"}
    if not required.issubset(set(normalized)):
        raise ValueError(f"Missing required columns. Required: {', '.join(required)}")
    rows = []
    for i, row in enumerate(reader, start=2):
        rows.append({
            "line": i,
            "name": (row.get("name") or "").strip(),
            "record_type": (row.get("record_type") or "").strip().upper(),
            "content": (row.get("content") or "").strip(),
            "ttl": row.get("ttl") or "1",
            "proxied": (row.get("proxied") or "false").strip().lower() in ("true", "1", "yes", "y"),
            "zone_domain": (row.get("zone_domain") or "").strip().lower(),
        })
    return rows

@api_router.get("/dns/records/export")
async def export_records_csv(current_user: dict = Depends(get_current_user)):
    """Export all of the current user's DNS records as a CSV download."""
    records = await db.dns_records.find({"user_id": current_user["id"]}, {"_id": 0}).to_list(1000)
    _, id_to_domain, _ = await _build_zone_maps()
    csv_text = _records_to_csv(records, id_to_domain)
    filename = f"dns-records-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    return Response(
        content=csv_text,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@api_router.get("/dns/records/import/template")
async def import_template():
    """Download an example CSV template."""
    sample = (
        ",".join(CSV_HEADERS) + "\n"
        "www,A,1.2.3.4,1,false,example.com\n"
        "api,A,5.6.7.8,3600,true,example.com\n"
        "blog,CNAME,target.example.net,1,false,example.com\n"
    )
    return Response(
        content=sample,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="dns-records-template.csv"'},
    )

@api_router.post("/dns/records/import")
async def import_records_csv(body: dict, current_user: dict = Depends(get_current_user)):
    """Import DNS records from CSV text. Body: {"csv": "<csv text>"}.
    Respects record_limit, zone enabled state, duplicates. Returns per-row results."""
    csv_text = (body or {}).get("csv", "").strip()
    if not csv_text:
        raise HTTPException(status_code=400, detail="CSV content is empty")
    try:
        rows = _parse_csv_records(csv_text)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if not rows:
        raise HTTPException(status_code=400, detail="No data rows in CSV")

    domain_to_id, id_to_domain, enabled_ids = await _build_zone_maps()
    # Current user record count for limit enforcement
    current_count = await db.dns_records.count_documents({"user_id": current_user["id"]})
    limit = current_user.get("record_limit", 0) or 0

    results = {"success": [], "failed": [], "total": len(rows)}
    for row in rows:
        line = row["line"]
        try:
            # CSV import allows any supported type, even if currently toggled off for the create form
            if row["record_type"] not in SUPPORTED_RECORD_TYPES:
                raise ValueError(f"Unsupported record type: {row['record_type']}")
            if not row["name"] or not row["content"]:
                raise ValueError("name and content are required")
            # Resolve zone
            zone_id = None
            if row["zone_domain"]:
                zone_id = domain_to_id.get(row["zone_domain"])
                if not zone_id:
                    raise ValueError(f"Unknown zone_domain: {row['zone_domain']}")
            else:
                zone_id = CF_ZONE_ID  # default to primary
            if zone_id not in enabled_ids:
                raise ValueError("Zone is disabled or not configured")
            # Limit check
            if limit > 0 and current_count >= limit:
                raise ValueError(f"Record limit reached ({limit})")
            # TTL parse
            try:
                ttl = int(row["ttl"])
            except Exception:
                ttl = 1
            ttl = max(1, min(86400, ttl))
            # Duplicate check
            zone_domain = id_to_domain.get(zone_id, CF_ZONE_DOMAIN)
            full_name = f"{row['name']}.{zone_domain}" if row["name"] != "@" else zone_domain
            existing = await db.dns_records.find_one(
                {"full_name": full_name, "record_type": row["record_type"]}, {"_id": 0}
            )
            if existing:
                raise ValueError(f"Record {full_name} ({row['record_type']}) already exists")
            # Create on Cloudflare
            cf_result, used_zone = await cf_create_record(
                name=row["name"], record_type=row["record_type"], content=row["content"],
                ttl=ttl, proxied=row["proxied"], zone_id=zone_id,
            )
            record_id = str(uuid.uuid4())
            record_doc = {
                "id": record_id,
                "cf_record_id": cf_result["id"],
                "user_id": current_user["id"],
                "name": row["name"],
                "full_name": full_name,
                "record_type": row["record_type"],
                "content": row["content"],
                "ttl": ttl,
                "proxied": row["proxied"],
                "zone_id": used_zone["zone_id"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.dns_records.insert_one(record_doc)
            current_count += 1
            results["success"].append({"line": line, "full_name": full_name, "type": row["record_type"]})
        except HTTPException as he:
            results["failed"].append({"line": line, "name": row["name"], "error": he.detail})
        except Exception as e:
            results["failed"].append({"line": line, "name": row["name"], "error": str(e)})

    # Sync user record_count
    if results["success"]:
        await db.users.update_one(
            {"id": current_user["id"]},
            {"$inc": {"record_count": len(results["success"])}},
        )
        await log_activity(
            current_user["id"], current_user["email"], "records_imported",
            f"Imported {len(results['success'])}/{len(rows)} records from CSV",
        )
    return results

@api_router.get("/dns/zones")
async def list_available_zones(current_user: dict = Depends(get_current_user)):
    """List all available (enabled) zones for record creation (primary + additional)."""
    zones = []
    db_zones = await db.cf_zones.find({}, {"_id": 0}).to_list(50)
    status_map = {z.get("zone_id"): z.get("status", "active") for z in db_zones}
    if CF_ZONE_ID and status_map.get(CF_ZONE_ID, "active") == "active":
        zones.append({"id": CF_ZONE_ID, "domain": CF_ZONE_DOMAIN, "is_primary": True})
    for z in db_zones:
        if z.get("zone_id") != CF_ZONE_ID and z.get("status", "active") == "active":
            zones.append({"id": z["zone_id"], "domain": z.get("domain", ""), "is_primary": False})
    return {"zones": zones}

@api_router.post("/dns/records", status_code=201)
async def create_record(record_data: DNSRecordCreate, current_user: dict = Depends(get_current_user)):
    # Validate record type against admin-enabled types
    enabled_types = await _get_enabled_record_types()
    if not enabled_types:
        raise HTTPException(status_code=403, detail="Record creation is currently disabled.")
    if record_data.record_type not in enabled_types:
        raise HTTPException(status_code=400, detail=f"Record type '{record_data.record_type}' is not available.")
    
    # Check plan limits (0 means unlimited)
    record_count = await db.dns_records.count_documents({"user_id": current_user["id"]})
    if current_user["record_limit"] > 0 and record_count >= current_user["record_limit"]:
        raise HTTPException(
            status_code=403,
            detail=f"Record limit reached ({current_user['record_limit']}). Upgrade your plan for more records."
        )
    
    # Resolve zone config
    zone_cfg = await get_zone_config(record_data.zone_id)
    # Block creation on disabled zones
    await ensure_zone_enabled(zone_cfg["zone_id"])
    zone_domain = zone_cfg["domain"]
    
    # Check for duplicate subdomain
    full_name = f"{record_data.name}.{zone_domain}" if record_data.name != "@" else zone_domain
    existing = await db.dns_records.find_one(
        {"full_name": full_name, "record_type": record_data.record_type},
        {"_id": 0}
    )
    if existing:
        raise HTTPException(status_code=400, detail=f"Record {full_name} ({record_data.record_type}) already exists")
    
    # Create on Cloudflare
    cf_result, used_zone = await cf_create_record(
        name=record_data.name,
        record_type=record_data.record_type,
        content=record_data.content,
        ttl=record_data.ttl,
        proxied=record_data.proxied,
        zone_id=record_data.zone_id
    )
    
    # Store in MongoDB
    record_id = str(uuid.uuid4())
    record_doc = {
        "id": record_id,
        "cf_record_id": cf_result["id"],
        "user_id": current_user["id"],
        "name": record_data.name,
        "full_name": full_name,
        "record_type": record_data.record_type,
        "content": record_data.content,
        "ttl": record_data.ttl,
        "proxied": record_data.proxied,
        "zone_id": used_zone["zone_id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.dns_records.insert_one(record_doc)
    
    # Update user record count
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$inc": {"record_count": 1}}
    )
    
    await log_activity(current_user["id"], current_user["email"], "record_created",
                       f"{record_data.record_type} {full_name} → {record_data.content}")
    
    return {
        "id": record_id,
        "cf_record_id": cf_result["id"],
        "user_id": current_user["id"],
        "name": record_data.name,
        "full_name": full_name,
        "record_type": record_data.record_type,
        "content": record_data.content,
        "ttl": record_data.ttl,
        "proxied": record_data.proxied,
        "zone_id": used_zone["zone_id"],
        "created_at": record_doc["created_at"]
    }

@api_router.put("/dns/records/{record_id}")
async def update_record(record_id: str, update_data: DNSRecordUpdate, current_user: dict = Depends(get_current_user)):
    record = await db.dns_records.find_one(
        {"id": record_id, "user_id": current_user["id"]},
        {"_id": 0}
    )
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    # Build update fields
    content = update_data.content if update_data.content is not None else record["content"]
    ttl = update_data.ttl if update_data.ttl is not None else record["ttl"]
    proxied = update_data.proxied if update_data.proxied is not None else record["proxied"]
    
    # Update on Cloudflare (use stored zone_id)
    await cf_update_record(
        cf_record_id=record["cf_record_id"],
        record_type=record["record_type"],
        name=record["full_name"],
        content=content,
        ttl=ttl,
        proxied=proxied,
        zone_id=record.get("zone_id")
    )
    
    # Update in MongoDB
    update_fields = {"content": content, "ttl": ttl, "proxied": proxied}
    await db.dns_records.update_one(
        {"id": record_id},
        {"$set": update_fields}
    )
    
    await log_activity(current_user["id"], current_user["email"], "record_updated",
                       f"{record['record_type']} {record['full_name']} → {content}")
    
    record.update(update_fields)
    return record

@api_router.delete("/dns/records/{record_id}")
async def delete_record(record_id: str, current_user: dict = Depends(get_current_user)):
    record = await db.dns_records.find_one(
        {"id": record_id, "user_id": current_user["id"]},
        {"_id": 0}
    )
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    # Delete from Cloudflare
    await cf_delete_record(record["cf_record_id"], zone_id=record.get("zone_id"))
    
    # Delete from MongoDB
    await db.dns_records.delete_one({"id": record_id})
    
    # Update user record count
    await db.users.update_one(
        {"id": current_user["id"]},
        {"$inc": {"record_count": -1}}
    )
    
    await log_activity(current_user["id"], current_user["email"], "record_deleted",
                       f"{record['record_type']} {record['full_name']}")
    
    return {"message": "Record deleted successfully"}

# ============== ADMIN ROUTES ==============

@api_router.get("/admin/users")
async def admin_list_users(admin: dict = Depends(get_admin_user)):
    users = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(1000)
    for u in users:
        u["record_count"] = await db.dns_records.count_documents({"user_id": u["id"]})
    return {"users": users, "count": len(users)}

@api_router.delete("/admin/users/{user_id}")
async def admin_delete_user(user_id: str, admin: dict = Depends(get_admin_user)):
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.get("role") == "admin":
        raise HTTPException(status_code=400, detail="Cannot delete admin user")

    deleted_records = await _delete_user_with_records(user_id)
    return {"message": f"User {user['email']} and {deleted_records} records deleted"}

@api_router.put("/admin/users/{user_id}/plan")
async def admin_update_plan(user_id: str, plan_data: PlanUpdate, admin: dict = Depends(get_admin_user)):
    new_limit = await _resolve_plan_record_limit(plan_data.plan)
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    await db.users.update_one(
        {"id": user_id},
        {"$set": {"plan": plan_data.plan, "record_limit": new_limit}}
    )
    return {"message": f"User plan updated to {plan_data.plan}", "record_limit": new_limit}

@api_router.put("/admin/users/{user_id}/password")
async def admin_change_password(user_id: str, pw_data: PasswordUpdate, admin: dict = Depends(get_admin_user)):
    user = await db.users.find_one({"id": user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    new_hash = hash_password(pw_data.new_password)
    await db.users.update_one({"id": user_id}, {"$set": {"password_hash": new_hash}})
    return {"message": f"Password updated for {user['email']}"}

@api_router.post("/admin/users/bulk/plan")
async def admin_bulk_update_plan(data: BulkPlanUpdate, admin: dict = Depends(get_admin_user)):
    new_limit = await _resolve_plan_record_limit(data.plan)
    
    # Filter out admin users
    non_admin_ids = []
    for uid in data.user_ids:
        u = await db.users.find_one({"id": uid, "role": {"$ne": "admin"}}, {"_id": 0, "id": 1})
        if u:
            non_admin_ids.append(uid)
    
    if not non_admin_ids:
        raise HTTPException(status_code=400, detail="No eligible users to update")
    
    result = await db.users.update_many(
        {"id": {"$in": non_admin_ids}},
        {"$set": {"plan": data.plan, "record_limit": new_limit}}
    )
    return {"message": f"{result.modified_count} users updated to {data.plan}", "updated_count": result.modified_count}

@api_router.post("/admin/users/bulk/delete")
async def admin_bulk_delete_users(data: BulkDeleteUsers, admin: dict = Depends(get_admin_user)):
    deleted_count = 0
    deleted_records = 0
    
    for uid in data.user_ids:
        user = await db.users.find_one({"id": uid}, {"_id": 0})
        if not user or user.get("role") == "admin":
            continue
        rec_count = await _delete_user_with_records(uid)
        deleted_count += 1
        deleted_records += rec_count
    
    return {"message": f"{deleted_count} users and {deleted_records} records deleted", "deleted_count": deleted_count}

@api_router.get("/admin/users/{user_id}/records")
async def admin_get_user_records(user_id: str, admin: dict = Depends(get_admin_user)):
    user = await db.users.find_one({"id": user_id}, {"_id": 0, "password_hash": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    records = await db.dns_records.find({"user_id": user_id}, {"_id": 0}).to_list(500)
    return {"user": user, "records": records, "count": len(records)}

@api_router.get("/admin/records")
async def admin_list_all_records(admin: dict = Depends(get_admin_user)):
    records = await db.dns_records.find({}, {"_id": 0}).to_list(1000)
    # Attach user email to each record
    user_cache = {}
    for rec in records:
        uid = rec["user_id"]
        if uid not in user_cache:
            u = await db.users.find_one({"id": uid}, {"_id": 0, "email": 1, "name": 1})
            user_cache[uid] = u or {"email": "unknown", "name": "unknown"}
        rec["user_email"] = user_cache[uid].get("email", "unknown")
        rec["user_name"] = user_cache[uid].get("name", "unknown")
    return {"records": records, "count": len(records)}

@api_router.get("/admin/records/export")
async def admin_export_records_csv(admin: dict = Depends(get_admin_user)):
    """Export ALL records (all users) to CSV. Includes user_email column."""
    records = await db.dns_records.find({}, {"_id": 0}).to_list(5000)
    _, id_to_domain, _ = await _build_zone_maps()
    # Build user email map
    user_ids = list({r.get("user_id") for r in records if r.get("user_id")})
    user_map = {}
    if user_ids:
        async for u in db.users.find({"id": {"$in": user_ids}}, {"_id": 0, "id": 1, "email": 1}):
            user_map[u["id"]] = u.get("email", "unknown")
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(["user_email"] + CSV_HEADERS)
    for r in records:
        zd = id_to_domain.get(r.get("zone_id") or CF_ZONE_ID, CF_ZONE_DOMAIN)
        writer.writerow([
            user_map.get(r.get("user_id"), "unknown"),
            r.get("name", ""),
            r.get("record_type", ""),
            r.get("content", ""),
            r.get("ttl", 1),
            "true" if r.get("proxied") else "false",
            zd,
        ])
    filename = f"all-dns-records-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    return Response(
        content=buf.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )

@api_router.get("/admin/records/import/template")
async def admin_import_template(admin: dict = Depends(get_admin_user)):
    """Download an example CSV template for admin (with user_email column)."""
    sample = (
        "user_email," + ",".join(CSV_HEADERS) + "\n"
        "user1@example.com,www,A,1.2.3.4,1,false,example.com\n"
        "user2@example.com,api,A,5.6.7.8,3600,true,example.com\n"
        "user1@example.com,blog,CNAME,target.example.net,1,false,example.com\n"
    )
    return Response(
        content=sample,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="all-records-template.csv"'},
    )

@api_router.post("/admin/records/import")
async def admin_import_records_csv(body: dict, admin: dict = Depends(get_admin_user)):
    """Import DNS records from CSV (with user_email column). Each row creates a record
    on behalf of the matching user. Per-user record_limit and zone-enabled rules apply."""
    csv_text = (body or {}).get("csv", "").strip()
    if not csv_text:
        raise HTTPException(status_code=400, detail="CSV content is empty")
    reader = csv.DictReader(io.StringIO(csv_text))
    if not reader.fieldnames:
        raise HTTPException(status_code=400, detail="Empty CSV")
    normalized = [h.strip().lower() for h in reader.fieldnames]
    required = {"user_email", "name", "record_type", "content"}
    if not required.issubset(set(normalized)):
        raise HTTPException(status_code=400, detail=f"Missing required columns. Required: {', '.join(sorted(required))}")
    rows = []
    for i, row in enumerate(reader, start=2):
        rows.append({
            "line": i,
            "user_email": normalize_email(row.get("user_email")),
            "name": (row.get("name") or "").strip(),
            "record_type": (row.get("record_type") or "").strip().upper(),
            "content": (row.get("content") or "").strip(),
            "ttl": row.get("ttl") or "1",
            "proxied": (row.get("proxied") or "false").strip().lower() in ("true", "1", "yes", "y"),
            "zone_domain": (row.get("zone_domain") or "").strip().lower(),
        })
    if not rows:
        raise HTTPException(status_code=400, detail="No data rows in CSV")

    domain_to_id, id_to_domain, enabled_ids = await _build_zone_maps()
    user_cache = {}  # email -> user doc
    count_cache = {}  # user_id -> current count

    results = {"success": [], "failed": [], "total": len(rows)}
    for row in rows:
        line = row["line"]
        try:
            email = row["user_email"]
            if not email:
                raise ValueError("user_email is required")
            if email not in user_cache:
                user_cache[email] = await db.users.find_one({"email": email}, {"_id": 0})
            user = user_cache[email]
            if not user:
                raise ValueError(f"User not found: {email}")
            if row["record_type"] not in ["A", "AAAA", "CNAME", "NS"]:
                raise ValueError(f"Unsupported record type: {row['record_type']}")
            if not row["name"] or not row["content"]:
                raise ValueError("name and content are required")
            zone_id = None
            if row["zone_domain"]:
                zone_id = domain_to_id.get(row["zone_domain"])
                if not zone_id:
                    raise ValueError(f"Unknown zone_domain: {row['zone_domain']}")
            else:
                zone_id = CF_ZONE_ID
            if zone_id not in enabled_ids:
                raise ValueError("Zone is disabled or not configured")
            # Per-user limit check
            uid = user["id"]
            if uid not in count_cache:
                count_cache[uid] = await db.dns_records.count_documents({"user_id": uid})
            limit = user.get("record_limit", 0) or 0
            if limit > 0 and count_cache[uid] >= limit:
                raise ValueError(f"Record limit reached for {email} ({limit})")
            try:
                ttl = int(row["ttl"])
            except Exception:
                ttl = 1
            ttl = max(1, min(86400, ttl))
            zone_domain = id_to_domain.get(zone_id, CF_ZONE_DOMAIN)
            full_name = f"{row['name']}.{zone_domain}" if row["name"] != "@" else zone_domain
            existing = await db.dns_records.find_one(
                {"full_name": full_name, "record_type": row["record_type"]}, {"_id": 0}
            )
            if existing:
                raise ValueError(f"Record {full_name} ({row['record_type']}) already exists")
            cf_result, used_zone = await cf_create_record(
                name=row["name"], record_type=row["record_type"], content=row["content"],
                ttl=ttl, proxied=row["proxied"], zone_id=zone_id,
            )
            record_id = str(uuid.uuid4())
            record_doc = {
                "id": record_id,
                "cf_record_id": cf_result["id"],
                "user_id": uid,
                "name": row["name"],
                "full_name": full_name,
                "record_type": row["record_type"],
                "content": row["content"],
                "ttl": ttl,
                "proxied": row["proxied"],
                "zone_id": used_zone["zone_id"],
                "created_at": datetime.now(timezone.utc).isoformat(),
            }
            await db.dns_records.insert_one(record_doc)
            await db.users.update_one({"id": uid}, {"$inc": {"record_count": 1}})
            count_cache[uid] += 1
            results["success"].append({"line": line, "user_email": email, "full_name": full_name, "type": row["record_type"]})
        except HTTPException as he:
            results["failed"].append({"line": line, "user_email": row.get("user_email"), "name": row["name"], "error": he.detail})
        except Exception as e:
            results["failed"].append({"line": line, "user_email": row.get("user_email"), "name": row["name"], "error": str(e)})

    if results["success"]:
        await log_activity(
            admin["id"], admin["email"], "admin_records_imported",
            f"Imported {len(results['success'])}/{len(rows)} records via admin CSV",
        )
    return results

@api_router.post("/admin/dns/records", status_code=201)
async def admin_create_record(record_data: AdminDNSRecordCreate, admin: dict = Depends(get_admin_user)):
    if record_data.record_type not in ["A", "AAAA", "CNAME", "NS"]:
        raise HTTPException(status_code=400, detail="Only A, AAAA, CNAME, and NS records are supported")
    
    user = await db.users.find_one({"id": record_data.user_id}, {"_id": 0})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    
    # Resolve zone config
    zone_cfg = await get_zone_config(record_data.zone_id)
    await ensure_zone_enabled(zone_cfg["zone_id"])
    zone_domain = zone_cfg["domain"]
    full_name = f"{record_data.name}.{zone_domain}" if record_data.name != "@" else zone_domain
    
    cf_result, used_zone = await cf_create_record(
        name=record_data.name, record_type=record_data.record_type,
        content=record_data.content, ttl=record_data.ttl, proxied=record_data.proxied,
        zone_id=record_data.zone_id
    )
    
    record_id = str(uuid.uuid4())
    record_doc = {
        "id": record_id, "cf_record_id": cf_result["id"], "user_id": record_data.user_id,
        "name": record_data.name, "full_name": full_name, "record_type": record_data.record_type,
        "content": record_data.content, "ttl": record_data.ttl, "proxied": record_data.proxied,
        "zone_id": used_zone["zone_id"],
        "created_at": datetime.now(timezone.utc).isoformat()
    }
    await db.dns_records.insert_one(record_doc)
    await db.users.update_one({"id": record_data.user_id}, {"$inc": {"record_count": 1}})
    
    return {k: v for k, v in record_doc.items() if k != "_id"}

@api_router.delete("/admin/dns/records/{record_id}")
async def admin_delete_record(record_id: str, admin: dict = Depends(get_admin_user)):
    record = await db.dns_records.find_one({"id": record_id}, {"_id": 0})
    if not record:
        raise HTTPException(status_code=404, detail="Record not found")
    
    await cf_delete_record(record["cf_record_id"], zone_id=record.get("zone_id"))
    await db.dns_records.delete_one({"id": record_id})
    await db.users.update_one({"id": record["user_id"]}, {"$inc": {"record_count": -1}})
    return {"message": "Record deleted successfully"}

# ============== SETTINGS ROUTES ==============

@api_router.get("/admin/settings")
async def admin_get_settings(admin: dict = Depends(get_admin_user)):
    settings = await db.settings.find_one({"key": "site_settings"}, {"_id": 0})
    if not settings:
        settings = {
            "key": "site_settings",
            "telegram_id": "",
            "telegram_url": "",
            "contact_message_en": "Contact us on Telegram for pricing",
            "contact_message_fa": "برای استعلام قیمت در تلگرام تماس بگیرید",
            "referral_bonus_per_invite": 1,
        }
    return settings

@api_router.put("/admin/settings")
async def admin_update_settings(settings_data: SettingsUpdate, admin: dict = Depends(get_admin_user)):
    update_fields = {k: v for k, v in settings_data.model_dump().items() if v is not None}
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    await db.settings.update_one(
        {"key": "site_settings"},
        {"$set": update_fields},
        upsert=True
    )
    settings = await db.settings.find_one({"key": "site_settings"}, {"_id": 0})
    return settings

# ============== ADMIN: RECORD TYPES ==============

class RecordTypesUpdate(BaseModel):
    enabled: List[str]

@api_router.get("/admin/record-types")
async def admin_get_record_types(admin: dict = Depends(get_admin_user)):
    enabled = await _get_enabled_record_types()
    return {"types": [{"type": t, "enabled": t in enabled} for t in SUPPORTED_RECORD_TYPES]}

@api_router.put("/admin/record-types")
async def admin_update_record_types(payload: RecordTypesUpdate, admin: dict = Depends(get_admin_user)):
    enabled = [t for t in SUPPORTED_RECORD_TYPES if t in payload.enabled]
    disabled = [t for t in SUPPORTED_RECORD_TYPES if t not in enabled]
    await db.settings.update_one(
        {"key": "record_types"},
        {"$set": {"key": "record_types", "disabled": disabled}},
        upsert=True,
    )
    await log_activity(admin["id"], admin["email"], "record_types_updated", f"Enabled record types: {', '.join(enabled) or 'none'}")
    return {"types": [{"type": t, "enabled": t in enabled} for t in SUPPORTED_RECORD_TYPES]}

# Public endpoint for site config (domain, contact info)
@api_router.get("/config")
async def get_site_config():
    settings = await db.settings.find_one({"key": "site_settings"}, {"_id": 0})
    telegram_id = (settings or {}).get("telegram_id", "")
    telegram_url = (settings or {}).get("telegram_url", "")
    # Auto-generate telegram_url from telegram_id if URL is empty or just base
    if telegram_id and (not telegram_url or telegram_url.rstrip("/") == "https://t.me"):
        telegram_url = f"https://t.me/{telegram_id.lstrip('@')}"
    enabled_types = await _get_enabled_record_types()
    return {
        "domain": DOMAIN_NAME,
        "dns_domain": CF_ZONE_DOMAIN,
        "telegram_id": telegram_id,
        "telegram_url": telegram_url,
        "contact_message_en": (settings or {}).get("contact_message_en", ""),
        "contact_message_fa": (settings or {}).get("contact_message_fa", ""),
        "referral_bonus_per_invite": (settings or {}).get("referral_bonus_per_invite", 1),
        "supported_record_types": SUPPORTED_RECORD_TYPES,
        "enabled_record_types": enabled_types,
    }

# ============== ADMIN: BACKUP SYSTEM ==============

backup_task_handle = None

async def do_backup(mongo_url: str, db_name: str, bot_token: str, admin_id: str):
    """Create MongoDB dump and send to Telegram."""
    tmp_dir = tempfile.mkdtemp(prefix="backup_")
    try:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        dump_dir = os.path.join(tmp_dir, "dump")
        archive_path = os.path.join(tmp_dir, f"backup_{db_name}_{timestamp}.gz")

        # mongodump
        cmd = ["mongodump", "--uri", mongo_url, "--db", db_name, "--out", dump_dir, "--quiet"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            logger.error(f"mongodump failed: {result.stderr}")
            return False, f"mongodump failed: {result.stderr[:200]}"

        # ── Include configuration (.env) so the backup is a full restore ──
        # The dump_dir already holds <db_name>/*.bson; we add a config/ folder
        # next to it so the archive contains both the database and the .env files.
        # install.sh's Import locates these automatically (config/backend.env).
        config_dir = os.path.join(dump_dir, "config")
        os.makedirs(config_dir, exist_ok=True)
        included_config = []
        env_sources = [
            (ROOT_DIR / ".env", "backend.env"),
        ]
        for src, dest_name in env_sources:
            try:
                if src.exists():
                    shutil.copy2(src, os.path.join(config_dir, dest_name))
                    included_config.append(dest_name)
            except Exception as e:
                logger.warning(f"Could not include {dest_name} in backup: {e}")

        # Save a small metadata file for context on restore
        try:
            with open(os.path.join(dump_dir, "metadata.txt"), "w") as mf:
                mf.write(f"export_date={datetime.now(timezone.utc).isoformat()}\n")
                mf.write(f"db_name={db_name}\n")
                mf.write(f"domain={DOMAIN_NAME}\n")
                mf.write(f"source=telegram_backup_bot\n")
        except Exception as e:
            logger.warning(f"Could not write backup metadata: {e}")

        # Compress to tar.gz
        shutil.make_archive(archive_path.replace(".gz", ""), "gztar", dump_dir)
        archive_file = archive_path.replace(".gz", ".tar.gz")

        # Send to Telegram
        file_size = os.path.getsize(archive_file)
        if file_size > 49 * 1024 * 1024:
            return False, "Backup file too large (>49MB) for Telegram"

        caption = f"🗄 Backup: {db_name}\n📅 {timestamp}\n📦 {file_size / 1024:.1f} KB"
        if included_config:
            caption += f"\n⚙️ Config: {', '.join(included_config)}"
        else:
            caption += "\n⚙️ Config: none (database only)"
        async with httpx.AsyncClient(timeout=120.0) as client_http:
            with open(archive_file, "rb") as f:
                resp = await client_http.post(
                    f"https://api.telegram.org/bot{bot_token}/sendDocument",
                    data={"chat_id": admin_id, "caption": caption},
                    files={"document": (os.path.basename(archive_file), f, "application/gzip")}
                )
                data = resp.json()
                if not data.get("ok"):
                    desc = data.get("description", "Telegram send failed")
                    if "chat not found" in desc.lower():
                        return False, "Chat not found. Send /start to the backup bot first."
                    return False, desc

        # Log
        file_id = data.get("result", {}).get("document", {}).get("file_id", "")
        await db.backup_logs.insert_one({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "size_bytes": file_size,
            "status": "success",
            "file_id": file_id,
        })
        return True, "Backup sent successfully"
    except subprocess.TimeoutExpired:
        return False, "mongodump timed out"
    except Exception as e:
        logger.error(f"Backup error: {e}")
        return False, str(e)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


async def backup_scheduler():
    """Background task that runs backups on schedule."""
    while True:
        try:
            settings = await db.settings.find_one({"key": "backup_settings"}, {"_id": 0})
            if not settings or not settings.get("enabled"):
                await asyncio.sleep(60)
                continue
            interval_minutes = settings.get("interval_minutes", 60)
            bot_token = settings.get("bot_token", "")
            admin_id = settings.get("admin_id", "")
            if not bot_token or not admin_id:
                await asyncio.sleep(60)
                continue

            # Check last backup time
            last = await db.backup_logs.find_one({"status": "success"}, {"_id": 0}, sort=[("timestamp", -1)])
            if last:
                last_time = datetime.fromisoformat(last["timestamp"])
                elapsed = (datetime.now(timezone.utc) - last_time).total_seconds() / 60
                if elapsed < interval_minutes:
                    await asyncio.sleep(60)
                    continue

            mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
            db_name_env = os.environ.get("DB_NAME", "khalilv2_dns")
            success, msg = await do_backup(mongo_url, db_name_env, bot_token, admin_id)
            if success:
                logger.info(f"Scheduled backup completed: {msg}")
            else:
                logger.error(f"Scheduled backup failed: {msg}")
                await db.backup_logs.insert_one({
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "status": "failed",
                    "error": msg,
                })
        except Exception as e:
            logger.error(f"Backup scheduler error: {e}")
        await asyncio.sleep(60)


def start_backup_scheduler():
    global backup_task_handle
    if backup_task_handle is None or backup_task_handle.done():
        backup_task_handle = asyncio.create_task(backup_scheduler())
        logger.info("Backup scheduler started")


@api_router.get("/admin/backup/settings")
async def get_backup_settings(admin: dict = Depends(get_admin_user)):
    settings = await db.settings.find_one({"key": "backup_settings"}, {"_id": 0})
    if not settings:
        return {"enabled": False, "bot_token_set": False, "masked_token": "", "admin_id": "", "interval_minutes": 60, "last_backup": None, "last_backup_size": None}
    masked_token = ""
    if settings.get("bot_token"):
        t = settings["bot_token"]
        masked_token = t[:10] + "..." + t[-4:] if len(t) > 14 else "***"
    # Last backup info
    last = await db.backup_logs.find_one({"status": "success"}, {"_id": 0}, sort=[("timestamp", -1)])
    return {
        "enabled": settings.get("enabled", False),
        "bot_token_set": bool(settings.get("bot_token")),
        "masked_token": masked_token,
        "admin_id": settings.get("admin_id", ""),
        "interval_minutes": settings.get("interval_minutes", 60),
        "last_backup": last.get("timestamp") if last else None,
        "last_backup_size": last.get("size_bytes") if last else None,
    }


@api_router.put("/admin/backup/settings")
async def update_backup_settings(body: dict, admin: dict = Depends(get_admin_user)):
    update_fields = {}
    if "enabled" in body:
        update_fields["enabled"] = bool(body["enabled"])
    if "bot_token" in body and body["bot_token"].strip():
        update_fields["bot_token"] = body["bot_token"].strip()
    if "admin_id" in body:
        update_fields["admin_id"] = str(body["admin_id"]).strip()
    if "interval_minutes" in body:
        val = int(body["interval_minutes"])
        update_fields["interval_minutes"] = max(1, min(val, 10080))  # 1 min to 7 days

    await db.settings.update_one(
        {"key": "backup_settings"},
        {"$set": {**update_fields, "key": "backup_settings"}},
        upsert=True
    )
    return {"message": "Backup settings updated"}


@api_router.post("/admin/backup/now")
async def trigger_backup_now(admin: dict = Depends(get_admin_user)):
    settings = await db.settings.find_one({"key": "backup_settings"}, {"_id": 0})
    if not settings or not settings.get("bot_token") or not settings.get("admin_id"):
        raise HTTPException(status_code=400, detail="Backup bot token and admin ID must be configured first")
    mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
    db_name_env = os.environ.get("DB_NAME", "khalilv2_dns")
    success, msg = await do_backup(mongo_url, db_name_env, settings["bot_token"], settings["admin_id"])
    if success:
        return {"success": True, "message": msg}
    raise HTTPException(status_code=500, detail=msg)


@api_router.post("/admin/backup/restore")
async def restore_backup(admin: dict = Depends(get_admin_user)):
    """Restore from the latest backup file."""
    settings = await db.settings.find_one({"key": "backup_settings"}, {"_id": 0})
    if not settings or not settings.get("bot_token"):
        raise HTTPException(status_code=400, detail="Backup bot token must be configured first")

    bot_token = settings["bot_token"]

    # Find last successful backup with file_id
    last = await db.backup_logs.find_one(
        {"status": "success", "file_id": {"$exists": True, "$ne": ""}},
        {"_id": 0},
        sort=[("timestamp", -1)]
    )
    if not last or not last.get("file_id"):
        raise HTTPException(status_code=404, detail="No backup found. Please create a backup first.")

    file_id = last["file_id"]
    tmp_dir = tempfile.mkdtemp(prefix="restore_")
    try:
        async with httpx.AsyncClient(timeout=120.0) as client_http:
            # Get file path from Telegram
            file_resp = await client_http.get(
                f"https://api.telegram.org/bot{bot_token}/getFile",
                params={"file_id": file_id}
            )
            file_data = file_resp.json()
            if not file_data.get("ok"):
                raise HTTPException(status_code=500, detail="Failed to get file from Telegram: " + file_data.get("description", ""))

            file_path = file_data["result"]["file_path"]
            dl_resp = await client_http.get(f"https://api.telegram.org/file/bot{bot_token}/{file_path}")

            archive_path = os.path.join(tmp_dir, "backup.tar.gz")
            with open(archive_path, "wb") as f:
                f.write(dl_resp.content)

        # Extract
        shutil.unpack_archive(archive_path, tmp_dir)

        # Find the dump directory
        db_name_env = os.environ.get("DB_NAME", "khalilv2_dns")
        dump_path = os.path.join(tmp_dir, db_name_env)
        if not os.path.isdir(dump_path):
            for root, dirs, _files in os.walk(tmp_dir):
                if db_name_env in dirs:
                    dump_path = os.path.join(root, db_name_env)
                    break

        if not os.path.isdir(dump_path):
            raise HTTPException(status_code=400, detail=f"Backup does not contain database '{db_name_env}'")

        # Save backup logs and settings before restore (they'll be dropped)
        saved_logs = await db.backup_logs.find({}, {"_id": 0}).to_list(100)
        saved_backup_settings = await db.settings.find_one({"key": "backup_settings"}, {"_id": 0})

        # mongorestore
        mongo_url = os.environ.get("MONGO_URL", "mongodb://localhost:27017")
        cmd = ["mongorestore", "--uri", mongo_url, "--db", db_name_env, "--drop", dump_path, "--quiet"]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
        if result.returncode != 0:
            raise HTTPException(status_code=500, detail=f"mongorestore failed: {result.stderr[:200]}")

        # Re-insert backup logs and settings
        if saved_logs:
            await db.backup_logs.insert_many(saved_logs)
        if saved_backup_settings:
            await db.settings.update_one({"key": "backup_settings"}, {"$set": saved_backup_settings}, upsert=True)

        await db.backup_logs.insert_one({
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": "restored",
        })
        return {"success": True, "message": "Database restored successfully"}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Restore error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


@api_router.post("/admin/backup/test-bot")
async def test_backup_bot(body: dict, admin: dict = Depends(get_admin_user)):
    """Test backup bot token and admin ID by sending a test message."""
    bot_token = body.get("bot_token", "").strip()
    admin_id = body.get("admin_id", "").strip()
    # If no token provided, use stored
    if not bot_token:
        settings = await db.settings.find_one({"key": "backup_settings"}, {"_id": 0})
        bot_token = (settings or {}).get("bot_token", "")
    if not admin_id:
        settings = await db.settings.find_one({"key": "backup_settings"}, {"_id": 0})
        admin_id = (settings or {}).get("admin_id", "")
    if not bot_token or not admin_id:
        return {"success": False, "message": "Bot token and admin ID are required"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client_http:
            resp = await client_http.post(
                f"https://api.telegram.org/bot{bot_token}/sendMessage",
                json={"chat_id": admin_id, "text": "✅ Backup bot connection test successful!"}
            )
            data = resp.json()
            if data.get("ok"):
                return {"success": True, "message": "Test message sent successfully"}
            desc = data.get("description", "Failed")
            # User-friendly error messages
            if "chat not found" in desc.lower():
                return {"success": False, "message": "Chat not found. Please send /start to the backup bot in Telegram first, then try again."}
            if "bot was blocked" in desc.lower():
                return {"success": False, "message": "Bot is blocked by user. Please unblock the bot in Telegram."}
            if "unauthorized" in desc.lower() or "token" in desc.lower():
                return {"success": False, "message": "Invalid bot token. Please check and re-enter."}
            return {"success": False, "message": desc}
    except Exception as e:
        return {"success": False, "message": str(e)}


# ============== ADMIN: BOT MANAGEMENT ==============

@api_router.get("/admin/cf-token")
async def admin_get_cf_token(admin: dict = Depends(get_admin_user)):
    """Get masked Cloudflare API token status."""
    token = CF_API_TOKEN
    has_token = bool(token)
    masked = ""
    if token:
        masked = token[:8] + "..." + token[-4:] if len(token) > 12 else "***"
    return {"has_token": has_token, "masked_token": masked}

@api_router.put("/admin/cf-token")
async def admin_update_cf_token(body: dict, admin: dict = Depends(get_admin_user)):
    """Update the primary Cloudflare API token."""
    global CF_API_TOKEN
    new_token = body.get("api_token", "").strip()
    if not new_token:
        raise HTTPException(status_code=400, detail="API token cannot be empty")
    CF_API_TOKEN = new_token
    # Persist to .env file
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r") as f:
            lines = f.readlines()
        found = False
        new_lines = []
        for line in lines:
            if line.strip().startswith("CLOUDFLARE_API_TOKEN="):
                new_lines.append(f"CLOUDFLARE_API_TOKEN={new_token}\n")
                found = True
            else:
                new_lines.append(line)
        if not found:
            new_lines.append(f"CLOUDFLARE_API_TOKEN={new_token}\n")
        with open(env_path, "w") as f:
            f.writelines(new_lines)
    return {"message": "API token updated", "masked_token": new_token[:8] + "..." + new_token[-4:] if len(new_token) > 12 else "***"}

@api_router.post("/admin/cf-token/test")
async def admin_test_cf_token(admin: dict = Depends(get_admin_user)):
    """Test the current Cloudflare API token by verifying it works."""
    if not CF_API_TOKEN:
        return {"success": False, "message": "API token is not set"}
    try:
        async with httpx.AsyncClient(timeout=15.0) as client_http:
            # First try: token verify endpoint (works with API Tokens)
            response = await client_http.get(
                "https://api.cloudflare.com/client/v4/user/tokens/verify",
                headers={
                    "Authorization": f"Bearer {CF_API_TOKEN}",
                    "Content-Type": "application/json"
                }
            )
            data = response.json()
            if data.get("success") and data.get("result", {}).get("status") == "active":
                return {"success": True, "message": "Token is valid and active"}

            # Second try: if verify fails, test with zones list (works with both API Token and API Key)
            if CF_ZONE_ID:
                response2 = await client_http.get(
                    f"https://api.cloudflare.com/client/v4/zones/{CF_ZONE_ID}",
                    headers={
                        "Authorization": f"Bearer {CF_API_TOKEN}",
                        "Content-Type": "application/json"
                    }
                )
                data2 = response2.json()
                if data2.get("success"):
                    return {"success": True, "message": "Token is valid (zone access confirmed)"}

            # Both failed - return error
            errors = data.get("errors", [])
            error_msg = errors[0].get("message", "") if errors else ""
            if error_msg:
                return {"success": False, "message": error_msg}
            return {"success": False, "message": "Token verification failed"}
    except httpx.ConnectError:
        return {"success": False, "message": "Cannot connect to Cloudflare API. Check your internet connection."}
    except httpx.TimeoutException:
        return {"success": False, "message": "Connection to Cloudflare timed out."}
    except Exception as e:
        return {"success": False, "message": f"Connection error: {str(e)}"}

@api_router.get("/admin/bot/status")
async def admin_bot_status(admin: dict = Depends(get_admin_user)):
    """Get Telegram bot status, masked token, and admin ID."""
    token = TELEGRAM_BOT_TOKEN
    masked_token = ""
    if token:
        masked_token = token[:10] + "..." + token[-4:] if len(token) > 14 else "***"
    bot_running = False
    bot_username = ""
    if telegram_bot_app:
        try:
            bot_running = telegram_bot_app.running
            if bot_running:
                info = await telegram_bot_app.bot.get_me()
                bot_username = f"@{info.username}"
        except Exception:
            pass
    return {
        "has_token": bool(token),
        "masked_token": masked_token,
        "admin_id": TELEGRAM_ADMIN_ID,
        "bot_running": bot_running,
        "bot_username": bot_username,
    }

@api_router.put("/admin/bot/token")
async def admin_update_bot_token(body: dict, admin: dict = Depends(get_admin_user)):
    """Update bot token, save to .env, and restart bot."""
    global TELEGRAM_BOT_TOKEN
    new_token = body.get("token", "").strip()
    # Validate token format (roughly)
    if new_token and ":" not in new_token:
        raise HTTPException(status_code=400, detail="Invalid token format. Should be like 123456:ABC-DEF...")
    # Stop current bot
    await stop_telegram_bot()
    # Update in-memory
    TELEGRAM_BOT_TOKEN = new_token
    os.environ["TELEGRAM_BOT_TOKEN"] = new_token
    # Update .env file
    _update_env_file("TELEGRAM_BOT_TOKEN", new_token)
    # Start new bot if token provided
    if new_token:
        import asyncio
        asyncio.create_task(_safe_start_bot())
    return {"success": True, "has_token": bool(new_token)}

@api_router.put("/admin/bot/admin-id")
async def admin_update_bot_admin_id(body: dict, admin: dict = Depends(get_admin_user)):
    """Update Telegram admin ID."""
    global TELEGRAM_ADMIN_ID
    new_id = str(body.get("admin_id", "")).strip()
    TELEGRAM_ADMIN_ID = new_id
    os.environ["TELEGRAM_ADMIN_ID"] = new_id
    _update_env_file("TELEGRAM_ADMIN_ID", new_id)
    return {"success": True, "admin_id": new_id}

@api_router.get("/admin/smtp/status")
async def admin_smtp_status(admin: dict = Depends(get_admin_user)):
    """Get SMTP configuration status."""
    has_smtp = bool(SMTP_EMAIL and SMTP_PASSWORD)
    masked_email = SMTP_EMAIL if has_smtp else ""
    verify_enabled = await is_email_verification_enabled()
    return {
        "has_smtp": has_smtp,
        "smtp_email": masked_email,
        "email_verification_enabled": verify_enabled,
    }

@api_router.put("/admin/smtp/config")
async def admin_update_smtp(body: dict, admin: dict = Depends(get_admin_user)):
    """Update SMTP credentials."""
    global SMTP_EMAIL, SMTP_PASSWORD
    new_email = body.get("smtp_email", "").strip()
    new_password = body.get("smtp_password", "").strip()
    if new_email:
        SMTP_EMAIL = new_email
        os.environ["SMTP_EMAIL"] = new_email
        _update_env_file("SMTP_EMAIL", new_email)
    if new_password:
        SMTP_PASSWORD = new_password
        os.environ["SMTP_PASSWORD"] = new_password
        _update_env_file("SMTP_PASSWORD", new_password)
    return {"success": True, "has_smtp": bool(SMTP_EMAIL and SMTP_PASSWORD)}

@api_router.put("/admin/smtp/toggle-verification")
async def admin_toggle_verification(body: dict, admin: dict = Depends(get_admin_user)):
    """Toggle email verification on/off."""
    enabled = body.get("enabled", False)
    await db.settings.update_one(
        {"key": "site_settings"},
        {"$set": {"email_verification_enabled": enabled}},
        upsert=True
    )
    return {"success": True, "email_verification_enabled": enabled}


@api_router.get("/admin/auth/signup-status")
async def admin_get_signup_status(admin: dict = Depends(get_admin_user)):
    """Admin: get the current state of the email signup form."""
    settings = await db.settings.find_one({"key": "site_settings"}, {"_id": 0})
    enabled = bool((settings or {}).get("email_signup_enabled", True))
    return {"email_signup_enabled": enabled}


@api_router.put("/admin/auth/toggle-email-signup")
async def admin_toggle_email_signup(body: dict, admin: dict = Depends(get_admin_user)):
    """Admin: enable / disable the email-and-password signup form site-wide.
    When disabled, only Google OAuth registration remains available."""
    enabled = bool(body.get("enabled", True))
    await db.settings.update_one(
        {"key": "site_settings"},
        {"$set": {"email_signup_enabled": enabled}},
        upsert=True,
    )
    await log_activity(
        admin["id"], admin["email"],
        "email_signup_toggled",
        f"Email signup -> {'enabled' if enabled else 'disabled'}",
    )
    return {"success": True, "email_signup_enabled": enabled}


@api_router.post("/admin/bot/stop")
async def admin_stop_bot(admin: dict = Depends(get_admin_user)):
    """Stop the Telegram bot."""
    if not telegram_bot_app:
        raise HTTPException(status_code=400, detail="Bot is not running")
    await stop_telegram_bot()
    return {"success": True, "bot_running": False}

@api_router.post("/admin/bot/start")
async def admin_start_bot(admin: dict = Depends(get_admin_user)):
    """Start/restart the Telegram bot."""
    if not TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=400, detail="No bot token configured")
    import asyncio
    await stop_telegram_bot()
    asyncio.create_task(_safe_start_bot())
    return {"success": True, "message": "Bot starting..."}

def _update_env_file(key: str, value: str):
    """Update a key in the backend .env file."""
    env_path = os.path.join(os.path.dirname(__file__), ".env")
    if not os.path.exists(env_path):
        return
    lines = []
    found = False
    with open(env_path, "r") as f:
        for line in f:
            if line.startswith(f"{key}="):
                lines.append(f"{key}={value}\n")
                found = True
            else:
                lines.append(line)
    if not found:
        lines.append(f"{key}={value}\n")
    with open(env_path, "w") as f:
        f.writelines(lines)

async def _safe_start_bot():
    """Safely start the bot (used from API endpoints)."""
    import asyncio
    await asyncio.sleep(2)
    try:
        await start_telegram_bot()
    except Exception as e:
        logger.error(f"Failed to start bot from API: {e}", exc_info=True)

async def _notify_admin_web_register(name, email):
    """Notify admin about web registration (called as background task)."""
    try:
        if not TELEGRAM_ADMIN_ID or not telegram_bot_app or not telegram_bot_app.running:
            return
        admin_lang = "fa"
        pref = await db.telegram_prefs.find_one({"chat_id": str(TELEGRAM_ADMIN_ID)}, {"_id": 0})
        if pref:
            admin_lang = pref.get("lang", "fa")
        # Build message manually (t() is inside start_telegram_bot scope)
        import re as _re
        source_text = "🌐 وب‌سایت" if admin_lang == "fa" else "🌐 Website"
        if admin_lang == "fa":
            msg = f"🆕 <b>کاربر جدید ثبت‌نام کرد</b>\n\n👤 {name}\n📧 <code>{email}</code>\n📱 منبع: {source_text}"
        else:
            msg = f"🆕 <b>New user registered</b>\n\n👤 {name}\n📧 <code>{email}</code>\n📱 Source: {source_text}"
        await telegram_bot_app.bot.send_message(
            chat_id=int(TELEGRAM_ADMIN_ID),
            text=msg,
            parse_mode="HTML"
        )
        logger.info(f"Admin notified about web registration: {email}")
    except Exception as e:
        logger.warning(f"Failed to notify admin about web registration: {e}")

# ============== ADMIN: ZONES MANAGEMENT ==============

@api_router.get("/admin/zones")
async def admin_list_zones(admin: dict = Depends(get_admin_user)):
    """List all Cloudflare zones (primary from env + additional from DB)."""
    zones = []
    db_zones = await db.cf_zones.find({}, {"_id": 0}).to_list(50)
    status_map = {z.get("zone_id"): z.get("status", "active") for z in db_zones}
    # Primary zone from env (status read from DB override if exists)
    if CF_ZONE_ID:
        zones.append({
            "id": CF_ZONE_ID,
            "domain": CF_ZONE_DOMAIN,
            "is_primary": True,
            "status": status_map.get(CF_ZONE_ID, "active"),
        })
    # Additional zones from DB
    for z in db_zones:
        if z.get("zone_id") != CF_ZONE_ID:
            zones.append({
                "id": z["zone_id"],
                "domain": z.get("domain", ""),
                "is_primary": False,
                "status": z.get("status", "active"),
            })
    return {"zones": zones}

@api_router.post("/admin/zones")
async def admin_add_zone(body: dict, admin: dict = Depends(get_admin_user)):
    """Add a new Cloudflare zone. Validates with CF API."""
    zone_id = body.get("zone_id", "").strip()
    api_token = body.get("api_token", "").strip() or CF_API_TOKEN
    if not zone_id:
        raise HTTPException(status_code=400, detail="Zone ID is required")
    if not api_token:
        raise HTTPException(status_code=400, detail="API token is required")
    # Check if already exists
    existing = await db.cf_zones.find_one({"zone_id": zone_id})
    if existing or zone_id == CF_ZONE_ID:
        raise HTTPException(status_code=400, detail="Zone already exists")
    # Verify zone with Cloudflare
    try:
        async with httpx.AsyncClient(timeout=30.0) as hc:
            resp = await hc.get(
                f"{CF_API_BASE}/zones/{zone_id}",
                headers={"Authorization": f"Bearer {api_token}"},
                timeout=10
            )
            data = resp.json()
            if not data.get("success"):
                errors = data.get("errors", [])
                err_msg = errors[0].get("message", "Invalid zone") if errors else "Invalid zone ID or token"
                raise HTTPException(status_code=400, detail=err_msg)
            domain = data["result"]["name"]
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to verify zone: {str(e)}")
    # Save to DB
    zone_doc = {
        "zone_id": zone_id,
        "domain": domain,
        "api_token": api_token,
        "status": "active",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    await db.cf_zones.insert_one(zone_doc)
    await log_activity(admin["id"], admin["email"], "zone_added", f"Zone added: {domain} ({zone_id})")
    return {"success": True, "zone": {"id": zone_id, "domain": domain, "is_primary": False, "status": "active"}}

@api_router.delete("/admin/zones/{zone_id}")
async def admin_remove_zone(zone_id: str, admin: dict = Depends(get_admin_user)):
    """Remove a Cloudflare zone (cannot remove primary)."""
    if zone_id == CF_ZONE_ID:
        raise HTTPException(status_code=400, detail="Cannot remove primary zone. Change it from server configuration.")
    result = await db.cf_zones.delete_one({"zone_id": zone_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Zone not found")
    await log_activity(admin["id"], admin["email"], "zone_removed", f"Zone removed: {zone_id}")
    return {"success": True}

@api_router.patch("/admin/zones/{zone_id}")
async def admin_toggle_zone(zone_id: str, body: dict, admin: dict = Depends(get_admin_user)):
    """Enable or disable a zone. Disabled zones are hidden from record-creation pickers
    and block new record creation. Works for primary (env) and additional zones."""
    enabled = bool(body.get("enabled", True))
    new_status = "active" if enabled else "disabled"
    if zone_id == CF_ZONE_ID:
        # Upsert an override doc for the primary zone so we can persist its toggle state.
        await db.cf_zones.update_one(
            {"zone_id": zone_id},
            {"$set": {
                "zone_id": zone_id,
                "domain": CF_ZONE_DOMAIN,
                "api_token": CF_API_TOKEN,
                "status": new_status,
                "is_primary_override": True,
            },
             "$setOnInsert": {"created_at": datetime.now(timezone.utc).isoformat()}},
            upsert=True,
        )
        domain_for_log = CF_ZONE_DOMAIN
    else:
        existing = await db.cf_zones.find_one({"zone_id": zone_id}, {"_id": 0})
        if not existing:
            raise HTTPException(status_code=404, detail="Zone not found")
        await db.cf_zones.update_one({"zone_id": zone_id}, {"$set": {"status": new_status}})
        domain_for_log = existing.get("domain", zone_id)
    action = "zone_enabled" if enabled else "zone_disabled"
    await log_activity(admin["id"], admin["email"], action, f"{domain_for_log} ({zone_id}) -> {new_status}")
    return {"success": True, "zone_id": zone_id, "status": new_status}

# Public endpoint for contact info (legacy)
@api_router.get("/settings/contact")
async def get_contact_info():
    settings = await db.settings.find_one({"key": "site_settings"}, {"_id": 0})
    telegram_id = (settings or {}).get("telegram_id", "")
    telegram_url = (settings or {}).get("telegram_url", "")
    if telegram_id and (not telegram_url or telegram_url.rstrip("/") == "https://t.me"):
        telegram_url = f"https://t.me/{telegram_id.lstrip('@')}"
    return {
        "telegram_id": telegram_id,
        "telegram_url": telegram_url,
        "contact_message_en": (settings or {}).get("contact_message_en", ""),
        "contact_message_fa": (settings or {}).get("contact_message_fa", ""),
        "domain": DOMAIN_NAME,
        "dns_domain": CF_ZONE_DOMAIN
    }

# ============== PLANS ROUTES ==============

@api_router.get("/plans")
async def get_plans():
    plans = await db.plans.find({}, {"_id": 0}).sort("sort_order", 1).to_list(50)
    if not plans:
        # Fallback to defaults if DB empty
        plans = DEFAULT_PLANS
    return {"plans": plans}

# Admin plan CRUD
@api_router.get("/admin/plans")
async def admin_list_plans(admin: dict = Depends(get_admin_user)):
    plans = await db.plans.find({}, {"_id": 0}).sort("sort_order", 1).to_list(50)
    return {"plans": plans, "count": len(plans)}

@api_router.post("/admin/plans", status_code=201)
async def admin_create_plan(plan_data: PlanCreate, admin: dict = Depends(get_admin_user)):
    existing = await db.plans.find_one({"plan_id": plan_data.plan_id}, {"_id": 0})
    if existing:
        raise HTTPException(status_code=400, detail=f"Plan '{plan_data.plan_id}' already exists")
    
    plan_doc = plan_data.model_dump()
    await db.plans.insert_one(plan_doc)
    # Update PLAN_LIMITS cache
    PLAN_LIMITS[plan_data.plan_id] = plan_data.record_limit
    return {k: v for k, v in plan_doc.items() if k != "_id"}

@api_router.put("/admin/plans/{plan_id}")
async def admin_update_plan_details(plan_id: str, plan_data: PlanEdit, admin: dict = Depends(get_admin_user)):
    existing = await db.plans.find_one({"plan_id": plan_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    update_fields = {k: v for k, v in plan_data.model_dump().items() if v is not None}
    if not update_fields:
        raise HTTPException(status_code=400, detail="No fields to update")
    
    await db.plans.update_one({"plan_id": plan_id}, {"$set": update_fields})
    
    # Update PLAN_LIMITS cache if record_limit changed
    if "record_limit" in update_fields:
        PLAN_LIMITS[plan_id] = update_fields["record_limit"]
    
    updated = await db.plans.find_one({"plan_id": plan_id}, {"_id": 0})
    return updated

@api_router.delete("/admin/plans/{plan_id}")
async def admin_delete_plan(plan_id: str, admin: dict = Depends(get_admin_user)):
    existing = await db.plans.find_one({"plan_id": plan_id}, {"_id": 0})
    if not existing:
        raise HTTPException(status_code=404, detail="Plan not found")
    
    # Check if any users are on this plan
    users_on_plan = await db.users.count_documents({"plan": plan_id})
    if users_on_plan > 0:
        raise HTTPException(status_code=400, detail=f"Cannot delete plan: {users_on_plan} users are on this plan")
    
    await db.plans.delete_one({"plan_id": plan_id})
    PLAN_LIMITS.pop(plan_id, None)
    return {"message": f"Plan '{plan_id}' deleted"}

# Default plans for seeding
DEFAULT_PLANS = [
    {
        "plan_id": "free", "name": "Free", "name_fa": "رایگان",
        "price": "Free", "price_fa": "رایگان", "record_limit": 2,
        "features": ["2 DNS Records", "A, AAAA, CNAME, NS Support", "Basic Dashboard", "Community Support"],
        "features_fa": ["۲ رکورد DNS", "پشتیبانی A، AAAA، CNAME، NS", "داشبورد پایه", "پشتیبانی انجمن"],
        "popular": False, "sort_order": 0
    },
    {
        "plan_id": "pro", "name": "Pro", "name_fa": "حرفه‌ای",
        "price": "50,000 T/mo", "price_fa": "۵۰ هزار تومان/ماه", "record_limit": 50,
        "features": ["50 DNS Records", "A, AAAA, CNAME, NS Support", "Advanced Dashboard", "Priority Support", "API Access"],
        "features_fa": ["۵۰ رکورد DNS", "پشتیبانی A، AAAA، CNAME، NS", "داشبورد پیشرفته", "پشتیبانی اولویت‌دار", "دسترسی API"],
        "popular": True, "sort_order": 1
    },
    {
        "plan_id": "enterprise", "name": "Enterprise", "name_fa": "سازمانی",
        "price": "200,000 T/mo", "price_fa": "۲۰۰ هزار تومان/ماه", "record_limit": 500,
        "features": ["500 DNS Records", "All Record Types", "Premium Dashboard", "24/7 Support", "API Access", "Custom Domain"],
        "features_fa": ["۵۰۰ رکورد DNS", "تمام انواع رکورد", "داشبورد ویژه", "پشتیبانی ۲۴/۷", "دسترسی API", "دامنه اختصاصی"],
        "popular": False, "sort_order": 2
    }
]

# ============== ACTIVITY LOG ROUTES ==============

MAX_LOG_PAGE_SIZE = 200

def _clamp_pagination(page: int, limit: int) -> tuple:
    """Keep page/limit in a range Mongo accepts — a page below 1 produces a
    negative skip, which pymongo rejects with ValueError."""
    return max(1, page), max(1, min(limit, MAX_LOG_PAGE_SIZE))


@api_router.get("/activity/logs")
async def get_user_activity_logs(page: int = 1, limit: int = 20, current_user: dict = Depends(get_current_user)):
    page, limit = _clamp_pagination(page, limit)
    skip = (page - 1) * limit
    total = await db.activity_logs.count_documents({"user_id": current_user["id"]})
    logs = await db.activity_logs.find(
        {"user_id": current_user["id"]}, {"_id": 0}
    ).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"logs": logs, "total": total, "page": page, "pages": (total + limit - 1) // limit if total > 0 else 1}

@api_router.get("/admin/activity/logs")
async def admin_get_activity_logs(page: int = 1, limit: int = 50, user_id: Optional[str] = None, action: Optional[str] = None, admin: dict = Depends(get_admin_user)):
    page, limit = _clamp_pagination(page, limit)
    query = {}
    if user_id:
        query["user_id"] = user_id
    if action:
        query["action"] = action
    skip = (page - 1) * limit
    total = await db.activity_logs.count_documents(query)
    logs = await db.activity_logs.find(query, {"_id": 0}).sort("created_at", -1).skip(skip).limit(limit).to_list(limit)
    return {"logs": logs, "total": total, "page": page, "pages": (total + limit - 1) // limit if total > 0 else 1}

# ============== TELEGRAM BOT ==============

TELEGRAM_BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
TELEGRAM_ADMIN_ID = os.environ.get('TELEGRAM_ADMIN_ID', '')
SMTP_EMAIL = os.environ.get('SMTP_EMAIL', '')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')
telegram_bot_app = None

async def start_telegram_bot():
    """Start the Telegram bot in polling mode if token is configured."""
    global telegram_bot_app
    if not TELEGRAM_BOT_TOKEN:
        logger.info("Telegram bot: No token configured, skipping.")
        return

    try:
        from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
        from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters
    except ImportError:
        logger.warning("Telegram bot: python-telegram-bot not installed, skipping.")
        return

    # ── Translations ──────────────────────────────────────────
    import re as _re


    def _get_error_msg(e):
        """Extract meaningful error message from exception (handles HTTPException detail)."""
        detail = getattr(e, 'detail', None)
        if detail:
            return str(detail)
        msg = str(e)
        return msg if msg else type(e).__name__

    def _fmt_limit(limit, lang="fa"):
        """Format record limit: 0 means unlimited."""
        if limit == 0:
            return "نامحدود" if lang == "fa" else "Unlimited"
        return str(limit)


    def _md_to_html(text):
        """Convert Markdown bold/code to HTML for Telegram."""
        # Convert **bold** to <b>bold</b>
        text = _re.sub(r'\*\*(.+?)\*\*', r'<b>\1</b>', text)
        # Convert `code` to <code>code</code>
        text = _re.sub(r'`(.+?)`', r'<code>\1</code>', text)
        return text

    def _html_escape(val):
        """Escape HTML special chars in dynamic values."""
        if not isinstance(val, str):
            return val
        return val.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def t(lang, key, **kwargs):
        """Get translated string with HTML formatting."""
        template = T.get(lang, T["fa"]).get(key, T["fa"].get(key, key))
        try:
            # Escape HTML in kwargs values
            safe_kwargs = {k: _html_escape(v) for k, v in kwargs.items()}
            result = template.format(**safe_kwargs) if safe_kwargs else template
        except (KeyError, IndexError):
            result = template
        return _md_to_html(result)

    T = {
        "fa": {
            "welcome_logged_in": "👋 سلام {name}!\n🌐 مدیریت DNS {domain}\n\nاز دکمه‌های زیر استفاده کنید:",
            "welcome_new": "👋 به ربات مدیریت DNS {domain} خوش آمدید!\n\nبرای شروع، اکانت خود را متصل کنید:",
            "not_logged_in": "❌ ابتدا باید وارد اکانت خود شوید.",
            "btn_login": "🔑 ورود به اکانت",
            "btn_records": "📝 رکوردهای من",
            "btn_add": "➕ ساخت رکورد",
            "btn_status": "📊 وضعیت اکانت",
            "btn_delete": "🗑 حذف رکورد",
            "btn_referral": "🔗 لینک دعوت",
            "btn_logout": "🚪 خروج",
            "btn_lang": "🌐 English",
            "btn_back": "🔙 منوی اصلی",
            "btn_cancel": "❌ انصراف",
            "btn_refresh": "🔄 بروزرسانی",
            "btn_view_records": "📝 مشاهده رکوردها",
            "btn_add_another": "➕ ساخت دیگر",
            "btn_yes_delete": "✅ بله، حذف شود",
            "btn_yes_logout": "✅ بله، خروج",
            "btn_relogin": "🔑 ورود مجدد",
            "help_login_title": "🔑 **ورود به اکانت**",
            "help_login_body": "📧 لطفاً ایمیل خود را وارد کنید:",
            "login_enter_password": "🔒 حالا رمز عبور خود را وارد کنید:",
            "login_usage": "📧 لطفاً ایمیل خود را وارد کنید:",
            "login_fail": "❌ ایمیل یا رمز عبور اشتباه است.",
            "login_success": "✅ اکانت {name} ({email}) با موفقیت متصل شد!",
            "no_records": "📭 هیچ رکوردی ندارید.",
            "records_title": "📝 رکوردهای شما ({count}/{limit}):\n\n",
            "status_title": "📊 **وضعیت اکانت**\n\n",
            "status_body": "👤 {name}\n📧 `{email}`\n📋 پلن: **{plan}**\n📝 رکوردها: **{count}** از {limit}\n🔗 کد دعوت: `{ref_code}`\n👥 دعوت موفق: {ref_count}",
            "referral_title": "🔗 **لینک دعوت شما:**\n\n",
            "referral_body": "`{link}`\n\n👥 دعوت موفق: {count}\n🎁 رکورد جایزه: {bonus}\n\nلینک بالا را کپی و برای دوستان ارسال کنید!",
            "add_choose_type": "➕ **نوع رکورد را انتخاب کنید:**",
            "add_types_disabled": "⚠️ در حال حاضر ساخت رکورد غیرفعال است. لطفاً بعداً دوباره تلاش کنید.",
            "add_limit_reached": "❌ به سقف رکورد ({limit}) رسیدید.\nپلن خود را ارتقا دهید.",
            "add_enter_name": "📝 نوع: **{type}**\n\nنام ساب‌دامین را بنویسید:\n{example}\n\nفقط نام را بدون دامنه تایپ کنید:",
            "add_name_invalid": "❌ نام نامعتبر. دوباره تلاش کنید:",
            "add_enter_value_A": "آدرس IPv4 را وارد کنید:\nمثال: `1.2.3.4`",
            "add_enter_value_AAAA": "آدرس IPv6 را وارد کنید:\nمثال: `2001:db8::1`",
            "add_enter_value_CNAME": "دامنه مقصد را وارد کنید:\nمثال: `example.com`",
            "add_name_confirm": "✅ نام: `{name}.{domain}`\n\n{hint}",
            "add_exists": "❌ رکورد `{name}` ({type}) قبلاً وجود دارد.",
            "add_success": "✅ رکورد ساخته شد!\n\n`{type}` │ {name} → `{value}`",
            "add_example_A": "مثال: `mysite`  →  mysite.{domain}",
            "add_example_AAAA": "مثال: `mysite`  →  mysite.{domain}",
            "add_example_CNAME": "مثال: `blog`  →  blog.{domain}",
            "add_example_NS": "مثال: `sub`  →  sub.{domain}",
            "add_value_NS": "آدرس نیم‌سرور را وارد کنید:\nمثال: ns1.example.com",
            "delete_title": "🗑 **کدام رکورد حذف شود؟**",
            "delete_no_records": "📭 رکوردی برای حذف وجود ندارد.",
            "delete_confirm": "⚠️ **آیا مطمئنید؟**\n\nنوع: `{type}`\nnام: `{name}`\nمقدار: `{value}`",
            "delete_success": "✅ رکورد حذف شد!\n\n`{type}` {name}",
            "delete_not_found": "❌ رکورد پیدا نشد.",
            "logout_confirm": "⚠️ آیا مطمئنید می‌خواهید خارج شوید؟",
            "logout_success": "✅ اکانت شما از ربات قطع شد.",
            "lang_changed": "🌐 زبان به فارسی تغییر کرد.",
            "error": "❌ خطا: {err}",
            # ── Registration ──
            "btn_register": "📝 ثبت‌نام",
            "register_name": "📝 **ثبت‌نام**\n\nنام خود را وارد کنید:",
            "register_email": "📧 ایمیل جیمیل خود را وارد کنید:\n(فقط @gmail.com)",
            "register_password": "🔑 رمز عبور را وارد کنید:\n(حداقل ۶ کاراکتر)",
            "register_success": "✅ ثبت‌نام موفق!\n\n👤 {name}\n📧 `{email}`\n\nاکانت شما فعال شد.",
            "register_email_exists": "❌ این ایمیل قبلاً ثبت شده.\nلطفاً از دکمه ورود استفاده کنید.",
            "register_email_invalid": "❌ فقط ایمیل جیمیل (@gmail.com) مجاز است.",
            "register_password_short": "❌ رمز عبور باید حداقل ۶ کاراکتر باشد.",
            # ── Admin notification ──
            "admin_notify_register": "🆕 **کاربر جدید ثبت‌نام کرد**\n\n👤 {name}\n📧 `{email}`\n📱 منبع: {source}",
            # ── Email verification (bot) ──
            "verify_code_sent": "📧 یک کد ۶ رقمی به `{email}` ارسال شد.\nکد را وارد کنید:",
            "verify_success": "✅ ایمیل تأیید شد!",
            "verify_invalid": "❌ کد نادرست. دوباره تلاش کنید:",
            "verify_expired": "❌ کد منقضی شده. کد جدید ارسال شد.",
            "verify_resend": "📧 کد جدید ارسال شد.",
            # ── Admin Panel ──
            "btn_admin": "🛡 پنل ادمین",
            "admin_title": "🛡 **پنل مدیریت**\n\nاز دکمه‌های زیر استفاده کنید:",
            "admin_stats": "📊 آمار کلی",
            "admin_users": "👥 کاربران",
            "admin_records": "📝 همه رکوردها",
            "admin_plans": "📋 پلن‌ها",
            "admin_settings": "⚙️ تنظیمات",
            "admin_logs": "📜 لاگ فعالیت",
            "admin_back": "🔙 منوی اصلی",
            "admin_stats_text": "📊 **آمار کلی**\n\n👥 کاربران: **{users}**\n📝 رکوردها: **{records}**\n📋 پلن‌ها: **{plans}**\n\n📈 پلن رایگان: {free}\n📈 پلن حرفه‌ای: {pro}\n📈 پلن سازمانی: {enterprise}\n📈 سایر: {other}",
            "admin_users_title": "👥 **کاربران** (صفحه {page}/{pages})\n\n",
            "admin_user_line": "👤 {name} | `{email}` | {plan} | {count} رکورد\n",
            "admin_user_detail": "👤 **جزئیات کاربر**\n\n🆔 `{id}`\n📧 `{email}`\n👤 {name}\n📋 پلن: **{plan}**\n📝 رکوردها: **{count}** از {limit}\n🔗 کد دعوت: `{ref_code}`\n👥 دعوت: {ref_count}\n📅 ثبت‌نام: {date}",
            "admin_user_records": "📝 **رکوردهای {name}** ({count}):\n\n",
            "admin_no_users": "📭 کاربری یافت نشد.",
            "admin_no_records": "📭 رکوردی یافت نشد.",
            "btn_change_plan": "📋 تغییر پلن",
            "btn_del_user": "🗑 حذف کاربر",
            "btn_user_records": "📝 رکوردها",
            "btn_prev": "◀️ قبلی",
            "btn_next": "▶️ بعدی",
            "admin_select_plan": "📋 **پلن جدید را انتخاب کنید:**",
            "admin_plan_changed": "✅ پلن کاربر {email} به **{plan}** تغییر کرد.",
            "admin_del_confirm": "⚠️ **آیا از حذف مطمئنید؟**\n\n👤 {name}\n📧 `{email}`\n📝 {count} رکورد حذف خواهد شد.",
            "admin_del_success": "✅ کاربر {email} و {count} رکورد حذف شد.",
            "admin_record_del_confirm": "⚠️ **حذف رکورد؟**\n\n`{type}` │ {name}\n→ `{value}`\n👤 {user}",
            "admin_record_del_success": "✅ رکورد حذف شد.\n`{type}` │ {name}",
            "admin_plans_title": "📋 **پلن‌ها:**\n\n",
            "admin_plan_line": "📋 **{name}** (`{id}`)\n   💰 {price} | 📝 {limit} رکورد\n\n",
            "admin_settings_title": "⚙️ **تنظیمات سایت**\n\n",
            "admin_settings_body": "📱 تلگرام ID: `{tg_id}`\n🔗 لینک تلگرام: {tg_url}\n🎁 جایزه دعوت: {bonus} رکورد\n📝 رکورد رایگان: {free_records}\n💬 پیام EN: {msg_en}\n💬 پیام FA: {msg_fa}",
            "admin_logs_title": "📜 **آخرین فعالیت‌ها:**\n\n",
            "admin_log_line": "🕐 {date}\n   {email} → {action}\n   {details}\n\n",
            "admin_not_authorized": "❌ شما دسترسی ادمین ندارید.",
            "btn_edit_setting": "✏️ ویرایش",
            "admin_setting_choose": "⚙️ **کدام تنظیم را ویرایش کنید؟**",
            "admin_setting_enter": "✏️ مقدار جدید برای **{field}** را وارد کنید:",
            "admin_setting_updated": "✅ تنظیم **{field}** بروزرسانی شد.",
            # ── Password change (bot) ──
            "btn_change_my_pass": "🔑 تغییر رمز عبور",
            "admin_chpass_select": "👤 **شماره/ایمیل کاربری که رمزش عوض بشه رو انتخاب کنید:**",
            "admin_chpass_enter": "🔑 رمز عبور جدید برای **{email}** را وارد کنید:\n(حداقل ۶ کاراکتر)",
            "admin_chpass_success": "✅ رمز عبور **{email}** با موفقیت تغییر کرد.",
            "admin_chpass_short": "❌ رمز عبور باید حداقل ۶ کاراکتر باشد.",
            "chpass_enter_current": "🔐 رمز عبور فعلی خود را وارد کنید:",
            "chpass_enter_new": "🔑 رمز عبور جدید را وارد کنید:\n(حداقل ۶ کاراکتر)",
            "chpass_wrong_current": "❌ رمز عبور فعلی اشتباه است.",
            "chpass_success": "✅ رمز عبور شما با موفقیت تغییر کرد.",
            "chpass_short": "❌ رمز عبور باید حداقل ۶ کاراکتر باشد.",
        },
        "en": {
            "welcome_logged_in": "👋 Hello {name}!\n🌐 DNS Management for {domain}\n\nUse the buttons below:",
            "welcome_new": "👋 Welcome to {domain} DNS Bot!\n\nConnect your account to get started:",
            "not_logged_in": "❌ Please log in first.",
            "btn_login": "🔑 Login",
            "btn_records": "📝 My Records",
            "btn_add": "➕ Add Record",
            "btn_status": "📊 Account Status",
            "btn_delete": "🗑 Delete Record",
            "btn_referral": "🔗 Referral Link",
            "btn_logout": "🚪 Logout",
            "btn_lang": "🌐 فارسی",
            "btn_back": "🔙 Main Menu",
            "btn_cancel": "❌ Cancel",
            "btn_refresh": "🔄 Refresh",
            "btn_view_records": "📝 View Records",
            "btn_add_another": "➕ Add Another",
            "btn_yes_delete": "✅ Yes, Delete",
            "btn_yes_logout": "✅ Yes, Logout",
            "btn_relogin": "🔑 Login Again",
            "help_login_title": "🔑 **Login**",
            "help_login_body": "📧 Please enter your email:",
            "login_enter_password": "🔒 Now enter your password:",
            "login_usage": "📧 Please enter your email:",
            "login_fail": "❌ Invalid email or password.",
            "login_success": "✅ Account {name} ({email}) connected!",
            "no_records": "📭 You have no records.",
            "records_title": "📝 Your Records ({count}/{limit}):\n\n",
            "status_title": "📊 **Account Status**\n\n",
            "status_body": "👤 {name}\n📧 `{email}`\n📋 Plan: **{plan}**\n📝 Records: **{count}** of {limit}\n🔗 Referral: `{ref_code}`\n👥 Invites: {ref_count}",
            "referral_title": "🔗 **Your Referral Link:**\n\n",
            "referral_body": "`{link}`\n\n👥 Successful invites: {count}\n🎁 Bonus records: {bonus}\n\nShare this link with friends!",
            "add_choose_type": "➕ **Choose record type:**",
            "add_types_disabled": "⚠️ Record creation is currently disabled. Please try again later.",
            "add_limit_reached": "❌ Record limit reached ({limit}).\nUpgrade your plan.",
            "add_enter_name": "📝 Type: **{type}**\n\nEnter subdomain name:\n{example}\n\nType only the name without the domain:",
            "add_name_invalid": "❌ Invalid name. Try again:",
            "add_enter_value_A": "Enter IPv4 address:\nExample: `1.2.3.4`",
            "add_enter_value_AAAA": "Enter IPv6 address:\nExample: `2001:db8::1`",
            "add_enter_value_CNAME": "Enter target domain:\nExample: `example.com`",
            "add_name_confirm": "✅ Name: `{name}.{domain}`\n\n{hint}",
            "add_exists": "❌ Record `{name}` ({type}) already exists.",
            "add_success": "✅ Record created!\n\n`{type}` │ {name} → `{value}`",
            "add_example_A": "Example: `mysite`  →  mysite.{domain}",
            "add_example_AAAA": "Example: `mysite`  →  mysite.{domain}",
            "add_example_CNAME": "Example: `blog`  →  blog.{domain}",
            "add_example_NS": "Example: `sub`  →  sub.{domain}",
            "add_value_NS": "Enter the nameserver address:\nExample: ns1.example.com",
            "delete_title": "🗑 **Which record to delete?**",
            "delete_no_records": "📭 No records to delete.",
            "delete_confirm": "⚠️ **Are you sure?**\n\nType: `{type}`\nName: `{name}`\nValue: `{value}`",
            "delete_success": "✅ Record deleted!\n\n`{type}` {name}",
            "delete_not_found": "❌ Record not found.",
            "logout_confirm": "⚠️ Are you sure you want to logout?",
            "logout_success": "✅ Your account has been disconnected.",
            "lang_changed": "🌐 Language changed to English.",
            "error": "❌ Error: {err}",
            # ── Registration ──
            "btn_register": "📝 Register",
            "register_name": "📝 **Registration**\n\nEnter your name:",
            "register_email": "📧 Enter your Gmail address:\n(only @gmail.com)",
            "register_password": "🔑 Enter a password:\n(minimum 6 characters)",
            "register_success": "✅ Registration successful!\n\n👤 {name}\n📧 `{email}`\n\nYour account is now active.",
            "register_email_exists": "❌ This email is already registered.\nPlease use the login button.",
            "register_email_invalid": "❌ Only Gmail (@gmail.com) addresses are allowed.",
            "register_password_short": "❌ Password must be at least 6 characters.",
            # ── Admin notification ──
            "admin_notify_register": "🆕 **New user registered**\n\n👤 {name}\n📧 `{email}`\n📱 Source: {source}",
            # ── Email verification (bot) ──
            "verify_code_sent": "📧 A 6-digit code was sent to `{email}`.\nEnter the code:",
            "verify_success": "✅ Email verified!",
            "verify_invalid": "❌ Invalid code. Try again:",
            "verify_expired": "❌ Code expired. A new code has been sent.",
            "verify_resend": "📧 New code sent.",
            # ── Admin Panel ──
            "btn_admin": "🛡 Admin Panel",
            "admin_title": "🛡 **Admin Panel**\n\nUse the buttons below:",
            "admin_stats": "📊 Stats",
            "admin_users": "👥 Users",
            "admin_records": "📝 All Records",
            "admin_plans": "📋 Plans",
            "admin_settings": "⚙️ Settings",
            "admin_logs": "📜 Activity Logs",
            "admin_back": "🔙 Main Menu",
            "admin_stats_text": "📊 **Dashboard**\n\n👥 Users: **{users}**\n📝 Records: **{records}**\n📋 Plans: **{plans}**\n\n📈 Free: {free}\n📈 Pro: {pro}\n📈 Enterprise: {enterprise}\n📈 Other: {other}",
            "admin_users_title": "👥 **Users** (Page {page}/{pages})\n\n",
            "admin_user_line": "👤 {name} | `{email}` | {plan} | {count} records\n",
            "admin_user_detail": "👤 **User Details**\n\n🆔 `{id}`\n📧 `{email}`\n👤 {name}\n📋 Plan: **{plan}**\n📝 Records: **{count}** of {limit}\n🔗 Referral: `{ref_code}`\n👥 Invites: {ref_count}\n📅 Joined: {date}",
            "admin_user_records": "📝 **Records of {name}** ({count}):\n\n",
            "admin_no_users": "📭 No users found.",
            "admin_no_records": "📭 No records found.",
            "btn_change_plan": "📋 Change Plan",
            "btn_del_user": "🗑 Delete User",
            "btn_user_records": "📝 Records",
            "btn_prev": "◀️ Prev",
            "btn_next": "▶️ Next",
            "admin_select_plan": "📋 **Select new plan:**",
            "admin_plan_changed": "✅ User {email} plan changed to **{plan}**.",
            "admin_del_confirm": "⚠️ **Confirm delete?**\n\n👤 {name}\n📧 `{email}`\n📝 {count} records will be deleted.",
            "admin_del_success": "✅ User {email} and {count} records deleted.",
            "admin_record_del_confirm": "⚠️ **Delete record?**\n\n`{type}` │ {name}\n→ `{value}`\n👤 {user}",
            "admin_record_del_success": "✅ Record deleted.\n`{type}` │ {name}",
            "admin_plans_title": "📋 **Plans:**\n\n",
            "admin_plan_line": "📋 **{name}** (`{id}`)\n   💰 {price} | 📝 {limit} records\n\n",
            "admin_settings_title": "⚙️ **Site Settings**\n\n",
            "admin_settings_body": "📱 Telegram ID: `{tg_id}`\n🔗 Telegram URL: {tg_url}\n🎁 Referral bonus: {bonus} records\n📝 Free records: {free_records}\n💬 Message EN: {msg_en}\n💬 Message FA: {msg_fa}",
            "admin_logs_title": "📜 **Recent Activity:**\n\n",
            "admin_log_line": "🕐 {date}\n   {email} → {action}\n   {details}\n\n",
            "admin_not_authorized": "❌ You don't have admin access.",
            "btn_edit_setting": "✏️ Edit",
            "admin_setting_choose": "⚙️ **Which setting to edit?**",
            "admin_setting_enter": "✏️ Enter new value for **{field}**:",
            "admin_setting_updated": "✅ Setting **{field}** updated.",
            # ── Password change (bot) ──
            "btn_change_my_pass": "🔑 Change Password",
            "admin_chpass_select": "👤 **Select user to change password:**",
            "admin_chpass_enter": "🔑 Enter new password for **{email}**:\n(minimum 6 characters)",
            "admin_chpass_success": "✅ Password for **{email}** changed successfully.",
            "admin_chpass_short": "❌ Password must be at least 6 characters.",
            "chpass_enter_current": "🔐 Enter your current password:",
            "chpass_enter_new": "🔑 Enter new password:\n(minimum 6 characters)",
            "chpass_wrong_current": "❌ Current password is incorrect.",
            "chpass_success": "✅ Your password changed successfully.",
            "chpass_short": "❌ Password must be at least 6 characters.",
        }
    }

    def get_lang(user):
        """Get user's bot language, default Persian."""
        if user:
            return user.get("telegram_lang", "fa")
        return "fa"

    # ── Helper: get user from chat id ────────────────────────
    async def get_user_by_chat(chat_id):
        return await db.users.find_one({"telegram_chat_id": str(chat_id)}, {"_id": 0})

    # ── Helper: persist language for chat_id (even before login) ──
    async def get_chat_lang(chat_id, user=None):
        """Get language: from logged-in user > from prefs collection > default fa."""
        if user:
            return user.get("telegram_lang", "fa")
        pref = await db.telegram_prefs.find_one({"chat_id": str(chat_id)}, {"_id": 0})
        if pref:
            return pref.get("lang", "fa")
        return None  # No language chosen yet

    async def set_chat_lang(chat_id, lang, user=None):
        """Save language preference persistently."""
        await db.telegram_prefs.update_one(
            {"chat_id": str(chat_id)},
            {"$set": {"chat_id": str(chat_id), "lang": lang}},
            upsert=True
        )
        if user:
            await db.users.update_one({"id": user["id"]}, {"$set": {"telegram_lang": lang}})

    async def send_not_logged_in(update_or_query, lang="fa", chat_id=None):
        rows = [[InlineKeyboardButton(t(lang, "btn_login"), callback_data="help_login")]]
        if chat_id and is_admin_chat(chat_id):
            rows.append([InlineKeyboardButton(t(lang, "btn_admin"), callback_data="adm_panel")])
        msg = t(lang, "not_logged_in")
        if hasattr(update_or_query, 'message') and update_or_query.message:
            await update_or_query.message.reply_text(msg, reply_markup=InlineKeyboardMarkup(rows))
        else:
            await update_or_query.edit_message_text(msg, reply_markup=InlineKeyboardMarkup(rows))

    async def notify_admin_new_user(name, email, source="web"):
        """Send notification to admin about new user registration."""
        if not TELEGRAM_ADMIN_ID or not telegram_bot_app or not telegram_bot_app.running:
            return
        try:
            # Get admin's language preference
            admin_lang = "fa"
            pref = await db.telegram_prefs.find_one({"chat_id": str(TELEGRAM_ADMIN_ID)}, {"_id": 0})
            if pref:
                admin_lang = pref.get("lang", "fa")
            source_text = {"web": "🌐 وب‌سایت" if admin_lang == "fa" else "🌐 Website",
                           "telegram": "🤖 ربات تلگرام" if admin_lang == "fa" else "🤖 Telegram Bot"}
            msg = t(admin_lang, "admin_notify_register", name=name, email=email, source=source_text.get(source, source))
            await telegram_bot_app.bot.send_message(
                chat_id=int(TELEGRAM_ADMIN_ID),
                text=msg,
                parse_mode="HTML"
            )
            logger.info(f"Admin notified about new user: {email} (source: {source})")
        except Exception as e:
            logger.warning(f"Failed to notify admin about new user: {e}")

    # ── Main Menu Keyboard ───────────────────────────────────
    def is_admin_chat(chat_id):
        """Check if chat_id is the configured admin."""
        return TELEGRAM_ADMIN_ID and str(chat_id) == str(TELEGRAM_ADMIN_ID)

    def is_admin_user(user, chat_id):
        """Check if user is admin (by role or by chat_id)."""
        if user and user.get("role") == "admin":
            return True
        return is_admin_chat(chat_id)

    def main_menu_kb(lang="fa", chat_id=None, user=None):
        rows = [
            [InlineKeyboardButton(t(lang, "btn_records"), callback_data="records"),
             InlineKeyboardButton(t(lang, "btn_add"), callback_data="add_start")],
            [InlineKeyboardButton(t(lang, "btn_status"), callback_data="status"),
             InlineKeyboardButton(t(lang, "btn_delete"), callback_data="delete_list")],
            [InlineKeyboardButton(t(lang, "btn_referral"), callback_data="referral"),
             InlineKeyboardButton(t(lang, "btn_change_my_pass"), callback_data="chpass_start")],
            [InlineKeyboardButton(t(lang, "btn_logout"), callback_data="logout")],
            [InlineKeyboardButton(t(lang, "btn_lang"), callback_data="toggle_lang")],
        ]
        if is_admin_user(user, chat_id):
            rows.insert(-1, [InlineKeyboardButton(t(lang, "btn_admin"), callback_data="adm_panel")])
        return InlineKeyboardMarkup(rows)

    def admin_menu_kb(lang="fa"):
        return InlineKeyboardMarkup([
            [InlineKeyboardButton(t(lang, "admin_stats"), callback_data="adm_stats"),
             InlineKeyboardButton(t(lang, "admin_users"), callback_data="adm_users_0")],
            [InlineKeyboardButton(t(lang, "admin_records"), callback_data="adm_records_0"),
             InlineKeyboardButton(t(lang, "admin_plans"), callback_data="adm_plans")],
            [InlineKeyboardButton(t(lang, "admin_settings"), callback_data="adm_settings"),
             InlineKeyboardButton(t(lang, "admin_logs"), callback_data="adm_logs_0")],
            [InlineKeyboardButton("🔑 " + (lang == "fa" and "تغییر رمز کاربران" or "Change Passwords"), callback_data="adm_chpass")],
            [InlineKeyboardButton(t(lang, "admin_back"), callback_data="main_menu")],
        ])

    def admin_back_kb(lang="fa"):
        return InlineKeyboardMarkup([[InlineKeyboardButton("🔙 " + t(lang, "btn_admin").replace("🛡 ", ""), callback_data="adm_panel")]])

    def prelogin_kb(lang, chat_id):
        """Keyboard for non-logged-in users (login + register + lang + admin if applicable)."""
        rows = [
            [InlineKeyboardButton(t(lang, "btn_login"), callback_data="help_login"),
             InlineKeyboardButton(t(lang, "btn_register"), callback_data="help_register")],
            [InlineKeyboardButton(t(lang, "btn_lang"), callback_data="toggle_lang_prelogin")]
        ]
        if is_admin_chat(chat_id):
            rows.insert(1, [InlineKeyboardButton(t(lang, "btn_admin"), callback_data="adm_panel")])
        return InlineKeyboardMarkup(rows)

    def back_menu_kb(lang="fa"):
        return InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_back"), callback_data="main_menu")]])

    # ── Helper: clear all in-progress flow state (preserves language) ─
    _FLOW_KEYS = (
        "login_step", "login_email",
        "reg_step", "reg_name", "reg_email",
        "add_step", "add_type", "add_name", "add_zone_id", "add_zone_domain",
        "adm_edit_step", "adm_edit_field",
        "chpass_step", "adm_chpass_step", "adm_chpass_uid",
        "verify_email", "verify_user_id",
    )

    def _clear_flow_state(context):
        for k in _FLOW_KEYS:
            context.user_data.pop(k, None)

    # ── /start ───────────────────────────────────────────────
    async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            # Only clear flow-specific data, preserve language
            _clear_flow_state(context)

            chat_id = update.effective_chat.id
            logger.info(f"Telegram /start from chat_id={chat_id}")
            user = await get_user_by_chat(chat_id)
            lang = await get_chat_lang(chat_id, user)

            if user:
                # Logged-in user → main menu (lang is always set)
                if not lang:
                    lang = "fa"
                context.user_data["lang"] = lang
                await update.message.reply_text(
                    t(lang, "welcome_logged_in", name=user['name'], domain=CF_ZONE_DOMAIN),
                    reply_markup=main_menu_kb(lang, chat_id, user)
                )
            elif lang is None:
                # New user, no language chosen yet → show ONLY language selection
                await update.message.reply_text(
                    "🌐 لطفاً زبان خود را انتخاب کنید\n🌐 Please select your language:",
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🇮🇷 فارسی", callback_data="set_lang_fa"),
                         InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")]
                    ])
                )
            else:
                # Language already chosen, not logged in → show welcome + login
                context.user_data["lang"] = lang
                await update.message.reply_text(
                    t(lang, "welcome_new", domain=CF_ZONE_DOMAIN),
                    reply_markup=prelogin_kb(lang, chat_id)
                )
        except Exception as e:
            logger.error(f"Error in cmd_start: {e}", exc_info=True)
            try:
                await update.message.reply_text(
                    t("fa", "error", err=_get_error_msg(e)),
                    reply_markup=InlineKeyboardMarkup([
                        [InlineKeyboardButton("🇮🇷 فارسی", callback_data="set_lang_fa"),
                         InlineKeyboardButton("🇬🇧 English", callback_data="set_lang_en")]
                    ])
                )
            except Exception:
                pass

    # ── /login (redirect to button flow) ───────────────────
    async def cmd_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
        try:
            saved_lang = context.user_data.get("lang", "fa")
            _clear_flow_state(context)
            context.user_data["lang"] = saved_lang
            context.user_data["login_step"] = "email"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(saved_lang, "btn_cancel"), callback_data="main_menu")]])
            await update.message.reply_text(t(saved_lang, "help_login_body"), reply_markup=kb)
        except Exception as e:
            logger.error(f"Error in cmd_login: {e}", exc_info=True)

    # ── Callback Handler ─────────────────────────────────────
    async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        try:
            await query.answer()
        except Exception:
            pass
        data = query.data
        chat_id = update.effective_chat.id
        logger.info(f"Telegram callback: {data} from chat_id={chat_id}")
        user = await get_user_by_chat(chat_id)
        lang = await get_chat_lang(chat_id, user)
        if lang is None:
            lang = context.user_data.get("lang", "fa")
        context.user_data["lang"] = lang

        # ── Set language (first time — before login) ──
        if data in ("set_lang_fa", "set_lang_en"):
            new_lang = "fa" if data == "set_lang_fa" else "en"
            context.user_data["lang"] = new_lang
            await set_chat_lang(chat_id, new_lang, user)
            if user:
                # Logged in → show main menu
                await query.edit_message_text(
                    t(new_lang, "welcome_logged_in", name=user['name'], domain=CF_ZONE_DOMAIN),
                    reply_markup=main_menu_kb(new_lang, chat_id, user)
                )
            else:
                # Not logged in → show welcome + login button
                await query.edit_message_text(
                    t(new_lang, "welcome_new", domain=CF_ZONE_DOMAIN),
                    reply_markup=prelogin_kb(new_lang, chat_id)
                )
            return

        # ── Toggle language (pre-login) ──
        if data == "toggle_lang_prelogin":
            new_lang = "en" if lang == "fa" else "fa"
            context.user_data["lang"] = new_lang
            await set_chat_lang(chat_id, new_lang, user)
            await query.edit_message_text(
                t(new_lang, "welcome_new", domain=CF_ZONE_DOMAIN),
                reply_markup=prelogin_kb(new_lang, chat_id)
            )
            return

        # ── Toggle language (logged in — main menu) ──
        if data == "toggle_lang":
            new_lang = "en" if lang == "fa" else "fa"
            context.user_data["lang"] = new_lang
            await set_chat_lang(chat_id, new_lang, user)
            if user:
                await query.edit_message_text(
                    t(new_lang, "welcome_logged_in", name=user['name'], domain=CF_ZONE_DOMAIN),
                    reply_markup=main_menu_kb(new_lang, chat_id, user)
                )
            else:
                await query.edit_message_text(
                    t(new_lang, "welcome_new", domain=CF_ZONE_DOMAIN),
                    reply_markup=prelogin_kb(new_lang, chat_id)
                )
            return

        # ── Main Menu ──
        if data == "main_menu":
            if not user:
                # Not logged in → show login button
                await query.edit_message_text(
                    t(lang, "welcome_new", domain=CF_ZONE_DOMAIN),
                    reply_markup=prelogin_kb(lang, chat_id)
                )
                return
            await query.edit_message_text(
                t(lang, "welcome_logged_in", name=user['name'], domain=CF_ZONE_DOMAIN),
                reply_markup=main_menu_kb(lang, chat_id, user)
            )

        # ── Help Login (start login flow) ──
        elif data == "help_login":
            saved_lang = context.user_data.get("lang", lang)
            _clear_flow_state(context)
            context.user_data["lang"] = saved_lang
            context.user_data["login_step"] = "email"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(saved_lang, "btn_cancel"), callback_data="main_menu")]])
            await query.edit_message_text(
                t(saved_lang, "help_login_title") + "\n\n" + t(saved_lang, "help_login_body"),
                parse_mode="HTML",
                reply_markup=kb
            )

        # ── Help Register (start registration flow) ──
        elif data == "help_register":
            saved_lang = context.user_data.get("lang", lang)
            _clear_flow_state(context)
            context.user_data["lang"] = saved_lang
            context.user_data["reg_step"] = "name"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(saved_lang, "btn_cancel"), callback_data="main_menu")]])
            await query.edit_message_text(
                t(saved_lang, "register_name"),
                parse_mode="HTML",
                reply_markup=kb
            )

        # ── Records List ──
        elif data == "records":
            if not user:
                await send_not_logged_in(query, lang, chat_id)
                return
            records = await db.dns_records.find({"user_id": user["id"]}, {"_id": 0}).to_list(100)
            if not records:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton(t(lang, "btn_add"), callback_data="add_start")],
                    [InlineKeyboardButton(t(lang, "btn_back"), callback_data="main_menu")]
                ])
                await query.edit_message_text(t(lang, "no_records"), reply_markup=kb)
                return
            text = t(lang, "records_title", count=len(records), limit=_fmt_limit(user['record_limit'], lang))
            for r in records:
                proxy = "🟠" if r.get("proxied") else "⚪️"
                text += f"{proxy} <code>{r['record_type']}</code> │ {r['full_name']} → <code>{r['content']}</code>\n"
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(t(lang, "btn_add"), callback_data="add_start"),
                 InlineKeyboardButton(t(lang, "btn_delete"), callback_data="delete_list")],
                [InlineKeyboardButton(t(lang, "btn_refresh"), callback_data="records"),
                 InlineKeyboardButton(t(lang, "btn_back"), callback_data="main_menu")]
            ])
            await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")

        # ── Status ──
        elif data == "status":
            if not user:
                await send_not_logged_in(query, lang, chat_id)
                return
            record_count = await db.dns_records.count_documents({"user_id": user["id"]})
            text = t(lang, "status_title") + t(lang, "status_body",
                name=user['name'], email=user['email'], plan=user['plan'],
                count=record_count, limit=_fmt_limit(user['record_limit'], lang),
                ref_code=user.get('referral_code', '-'), ref_count=user.get('referral_count', 0))
            await query.edit_message_text(text, reply_markup=back_menu_kb(lang), parse_mode="HTML")

        # ── Referral ──
        elif data == "referral":
            if not user:
                await send_not_logged_in(query, lang, chat_id)
                return
            ref_link = f"https://{DOMAIN_NAME}/register?ref={user.get('referral_code', '')}"
            text = t(lang, "referral_title") + t(lang, "referral_body",
                link=ref_link, count=user.get('referral_count', 0), bonus=user.get('referral_bonus', 0))
            await query.edit_message_text(text, reply_markup=back_menu_kb(lang), parse_mode="HTML")

        # ── Add Record: Choose Type ──
        elif data == "add_start":
            if not user:
                await send_not_logged_in(query, lang, chat_id)
                return
            enabled_types = await _get_enabled_record_types()
            if not enabled_types:
                await query.edit_message_text(t(lang, "add_types_disabled"), reply_markup=back_menu_kb(lang))
                return
            record_count = await db.dns_records.count_documents({"user_id": user["id"]})
            if user["record_limit"] > 0 and record_count >= user["record_limit"]:
                await query.edit_message_text(
                    t(lang, "add_limit_reached", limit=user['record_limit']),
                    reply_markup=back_menu_kb(lang))
                return
            # Check if multiple zones are available (only enabled ones)
            all_zones = []
            db_zones = await db.cf_zones.find({}, {"_id": 0}).to_list(50)
            status_map = {z.get("zone_id"): z.get("status", "active") for z in db_zones}
            if CF_ZONE_ID and status_map.get(CF_ZONE_ID, "active") == "active":
                all_zones.append({"zone_id": CF_ZONE_ID, "domain": CF_ZONE_DOMAIN, "is_primary": True})
            for z in db_zones:
                if z.get("zone_id") != CF_ZONE_ID and z.get("status", "active") == "active":
                    all_zones.append({"zone_id": z["zone_id"], "domain": z.get("domain", ""), "is_primary": False})
            if len(all_zones) == 0:
                no_zone_msg = "⚠️ در حال حاضر هیچ زون فعالی وجود ندارد. لطفاً با مدیر تماس بگیرید." if lang == "fa" else "⚠️ No active zones available. Please contact admin."
                await query.edit_message_text(no_zone_msg)
                return
            if len(all_zones) > 1:
                # Show zone selector first
                zone_buttons = []
                for z in all_zones:
                    label = f"🌐 {z['domain']}" + (" ⭐" if z.get("is_primary") else "")
                    zone_buttons.append([InlineKeyboardButton(label, callback_data=f"add_zone_{z['zone_id']}")])
                zone_buttons.append([InlineKeyboardButton(t(lang, "btn_back"), callback_data="main_menu")])
                zone_msg = "🌐 لطفاً دامنه مورد نظر را انتخاب کنید:" if lang == "fa" else "🌐 Select the domain:"
                await query.edit_message_text(zone_msg, reply_markup=InlineKeyboardMarkup(zone_buttons))
                return
            else:
                # Single zone - store it and go to type selection
                context.user_data["add_zone_id"] = all_zones[0]["zone_id"] if all_zones else None
                context.user_data["add_zone_domain"] = all_zones[0]["domain"] if all_zones else CF_ZONE_DOMAIN
            enabled_types = await _get_enabled_record_types()
            if not enabled_types:
                await query.edit_message_text(t(lang, "add_types_disabled"), reply_markup=back_menu_kb(lang))
                return
            type_rows = []
            _row = []
            for _tp in enabled_types:
                _row.append(InlineKeyboardButton(f"{TYPE_EMOJI.get(_tp, '')} {_tp}".strip(), callback_data=f"add_type_{_tp}"))
                if len(_row) == 2:
                    type_rows.append(_row); _row = []
            if _row:
                type_rows.append(_row)
            type_rows.append([InlineKeyboardButton(t(lang, "btn_back"), callback_data="main_menu")])
            kb = InlineKeyboardMarkup(type_rows)
            await query.edit_message_text(t(lang, "add_choose_type"), reply_markup=kb, parse_mode="HTML")

        elif data.startswith("add_zone_"):
            zone_id = data.replace("add_zone_", "")
            # Look up domain for this zone
            zone_domain = CF_ZONE_DOMAIN
            if zone_id == CF_ZONE_ID:
                zone_domain = CF_ZONE_DOMAIN
            else:
                zone_doc = await db.cf_zones.find_one({"zone_id": zone_id}, {"_id": 0})
                if zone_doc:
                    zone_domain = zone_doc.get("domain", CF_ZONE_DOMAIN)
            context.user_data["add_zone_id"] = zone_id
            context.user_data["add_zone_domain"] = zone_domain
            enabled_types = await _get_enabled_record_types()
            if not enabled_types:
                await query.edit_message_text(t(lang, "add_types_disabled"), reply_markup=back_menu_kb(lang))
                return
            type_rows = []
            _row = []
            for _tp in enabled_types:
                _row.append(InlineKeyboardButton(f"{TYPE_EMOJI.get(_tp, '')} {_tp}".strip(), callback_data=f"add_type_{_tp}"))
                if len(_row) == 2:
                    type_rows.append(_row); _row = []
            if _row:
                type_rows.append(_row)
            type_rows.append([InlineKeyboardButton(t(lang, "btn_back"), callback_data="main_menu")])
            kb = InlineKeyboardMarkup(type_rows)
            await query.edit_message_text(t(lang, "add_choose_type"), reply_markup=kb, parse_mode="HTML")

        elif data.startswith("add_type_"):
            record_type = data.replace("add_type_", "")
            enabled_types = await _get_enabled_record_types()
            if record_type not in enabled_types:
                await query.edit_message_text(t(lang, "add_types_disabled"), reply_markup=back_menu_kb(lang))
                return
            context.user_data["add_type"] = record_type
            context.user_data["add_step"] = "name"
            zone_domain = context.user_data.get("add_zone_domain", CF_ZONE_DOMAIN)
            example = t(lang, f"add_example_{record_type}", domain=zone_domain)
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="main_menu")]])
            await query.edit_message_text(
                t(lang, "add_enter_name", type=record_type, example=example),
                reply_markup=kb, parse_mode="HTML")

        # ── Delete Record: List ──
        elif data == "delete_list":
            if not user:
                await send_not_logged_in(query, lang, chat_id)
                return
            records = await db.dns_records.find({"user_id": user["id"]}, {"_id": 0}).to_list(100)
            if not records:
                await query.edit_message_text(t(lang, "delete_no_records"), reply_markup=back_menu_kb(lang))
                return
            buttons = []
            for r in records:
                label = f"🗑 {r['record_type']} | {r.get('full_name', r['name'] + '.' + CF_ZONE_DOMAIN)}"
                buttons.append([InlineKeyboardButton(label, callback_data=f"del_{r['id']}")])
            buttons.append([InlineKeyboardButton(t(lang, "btn_back"), callback_data="main_menu")])
            await query.edit_message_text(t(lang, "delete_title"), reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")

        elif data.startswith("del_") and not data.startswith("confirm_del_"):
            record_id = data[4:]
            record = await db.dns_records.find_one({"id": record_id}, {"_id": 0})
            if not record:
                await query.edit_message_text(t(lang, "delete_not_found"), reply_markup=back_menu_kb(lang))
                return
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(t(lang, "btn_yes_delete"), callback_data=f"confirm_del_{record_id}"),
                 InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="main_menu")]
            ])
            await query.edit_message_text(
                t(lang, "delete_confirm", type=record['record_type'], name=record['full_name'], value=record['content']),
                reply_markup=kb, parse_mode="HTML")

        elif data.startswith("confirm_del_"):
            record_id = data[12:]
            if not user:
                await send_not_logged_in(query, lang, chat_id)
                return
            try:
                record = await db.dns_records.find_one({"id": record_id, "user_id": user["id"]}, {"_id": 0})
                if not record:
                    await query.edit_message_text(t(lang, "delete_not_found"), reply_markup=back_menu_kb(lang))
                    return
                await cf_delete_record(record["cf_record_id"], zone_id=record.get("zone_id"))
                await db.dns_records.delete_one({"id": record_id})
                await db.users.update_one({"id": user["id"]}, {"$inc": {"record_count": -1}})
                await log_activity(user["id"], user["email"], "record_deleted", f"{record['record_type']} {record['full_name']} (via Telegram)")
                await query.edit_message_text(
                    t(lang, "delete_success", type=record['record_type'], name=record['full_name']),
                    reply_markup=back_menu_kb(lang), parse_mode="HTML")
            except Exception as e:
                logger.error(f"User record delete error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=back_menu_kb(lang))

        # ── Logout ──
        elif data == "logout":
            if not user:
                await send_not_logged_in(query, lang, chat_id)
                return
            kb = InlineKeyboardMarkup([
                [InlineKeyboardButton(t(lang, "btn_yes_logout"), callback_data="confirm_logout"),
                 InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="main_menu")]
            ])
            await query.edit_message_text(t(lang, "logout_confirm"), reply_markup=kb)

        elif data == "confirm_logout":
            if user:
                await db.users.update_one({"id": user["id"]}, {"$unset": {"telegram_chat_id": ""}})
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_relogin"), callback_data="help_login")]])
            await query.edit_message_text(t(lang, "logout_success"), reply_markup=kb)

        # ── Change Own Password ──
        elif data == "chpass_start":
            if not user:
                await send_not_logged_in(query, lang, chat_id)
                return
            context.user_data["chpass_step"] = "current"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="main_menu")]])
            await query.edit_message_text(t(lang, "chpass_enter_current"), reply_markup=kb, parse_mode="HTML")

        # ── Admin: Change Any User's Password ──
        elif data == "adm_chpass":
            if not is_admin_user(user, chat_id):
                return
            try:
                users_list = await db.users.find({}, {"_id": 0, "password_hash": 0}).to_list(100)
                if not users_list:
                    await query.edit_message_text("❌ No users", reply_markup=admin_back_kb(lang))
                    return
                buttons = []
                for u in users_list:
                    role_icon = "🛡" if u.get("role") == "admin" else "👤"
                    buttons.append([InlineKeyboardButton(f"{role_icon} {u['name']} ({u['email']})", callback_data=f"adm_chpass_{u['id']}")])
                buttons.append([InlineKeyboardButton("🔙", callback_data="adm_panel")])
                await query.edit_message_text(t(lang, "admin_chpass_select"), reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
            except Exception as e:
                logger.error(f"Admin chpass list error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))

        elif data.startswith("adm_chpass_"):
            if not is_admin_user(user, chat_id):
                return
            try:
                uid = data[11:]
                target = await db.users.find_one({"id": uid}, {"_id": 0, "password_hash": 0})
                if not target:
                    await query.edit_message_text("❌ User not found", reply_markup=admin_back_kb(lang))
                    return
                context.user_data["adm_chpass_uid"] = uid
                context.user_data["adm_chpass_step"] = "new_pass"
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="adm_panel")]])
                await query.edit_message_text(
                    t(lang, "admin_chpass_enter", email=target['email']),
                    reply_markup=kb, parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Admin chpass select error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))

        # ══════════════════════════════════════════════════════════
        #  ADMIN PANEL CALLBACKS
        # ══════════════════════════════════════════════════════════

        elif data == "adm_panel":
            if not is_admin_user(user, chat_id):
                await query.edit_message_text(t(lang, "admin_not_authorized"), reply_markup=back_menu_kb(lang))
                return
            await query.edit_message_text(t(lang, "admin_title"), reply_markup=admin_menu_kb(lang), parse_mode="HTML")

        # ── Admin Stats ──
        elif data == "adm_stats":
            if not is_admin_user(user, chat_id):
                return
            try:
                total_users = await db.users.count_documents({})
                total_records = await db.dns_records.count_documents({})
                total_plans = await db.plans.count_documents({})
                free_count = await db.users.count_documents({"plan": "free"})
                pro_count = await db.users.count_documents({"plan": "pro"})
                ent_count = await db.users.count_documents({"plan": "enterprise"})
                other_count = total_users - free_count - pro_count - ent_count
                text = t(lang, "admin_stats_text",
                         users=total_users, records=total_records, plans=total_plans,
                         free=free_count, pro=pro_count, enterprise=ent_count, other=other_count)
                await query.edit_message_text(text, reply_markup=admin_back_kb(lang), parse_mode="HTML")
            except Exception as e:
                logger.error(f"Admin stats error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))

        # ── Admin Users List (paginated) ──
        elif data.startswith("adm_users_"):
            if not is_admin_user(user, chat_id):
                return
            try:
                page = int(data.split("_")[-1])
                per_page = 8
                total = await db.users.count_documents({})
                pages = max(1, (total + per_page - 1) // per_page)
                users_list = await db.users.find({}, {"_id": 0, "password_hash": 0}).skip(page * per_page).limit(per_page).to_list(per_page)
                if not users_list:
                    await query.edit_message_text(t(lang, "admin_no_users"), reply_markup=admin_back_kb(lang))
                    return
                text = t(lang, "admin_users_title", page=page + 1, pages=pages)
                buttons = []
                for u in users_list:
                    rc = await db.dns_records.count_documents({"user_id": u["id"]})
                    role_icon = "🛡" if u.get("role") == "admin" else "👤"
                    label = f"{role_icon} {u['name']} | {u['plan']} | {rc} rec"
                    buttons.append([InlineKeyboardButton(label, callback_data=f"adm_user_{u['id']}")])
                nav = []
                if page > 0:
                    nav.append(InlineKeyboardButton(t(lang, "btn_prev"), callback_data=f"adm_users_{page - 1}"))
                if page < pages - 1:
                    nav.append(InlineKeyboardButton(t(lang, "btn_next"), callback_data=f"adm_users_{page + 1}"))
                if nav:
                    buttons.append(nav)
                buttons.append([InlineKeyboardButton("🔙", callback_data="adm_panel")])
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
            except Exception as e:
                logger.error(f"Admin users list error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))

        # ── Admin User Detail ──
        elif data.startswith("adm_user_") and not data.startswith("adm_user_plan_") and not data.startswith("adm_user_del_") and not data.startswith("adm_user_recs_"):
            if not is_admin_user(user, chat_id):
                return
            try:
                uid = data[9:]
                target = await db.users.find_one({"id": uid}, {"_id": 0, "password_hash": 0})
                if not target:
                    await query.edit_message_text("❌ User not found", reply_markup=admin_back_kb(lang))
                    return
                rc = await db.dns_records.count_documents({"user_id": uid})
                text = t(lang, "admin_user_detail",
                         id=target['id'][:8], email=target['email'], name=target['name'],
                         plan=target['plan'], count=rc, limit=_fmt_limit(target['record_limit'], lang),
                         ref_code=target.get('referral_code', '-'), ref_count=target.get('referral_count', 0),
                         date=target['created_at'][:10])
                buttons = [
                    [InlineKeyboardButton(t(lang, "btn_change_plan"), callback_data=f"adm_user_plan_{uid}"),
                     InlineKeyboardButton(t(lang, "btn_user_records"), callback_data=f"adm_user_recs_{uid}")],
                ]
                if target.get("role") != "admin":
                    buttons.append([InlineKeyboardButton(t(lang, "btn_del_user"), callback_data=f"adm_user_del_{uid}")])
                buttons.append([InlineKeyboardButton("🔙", callback_data="adm_users_0")])
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
            except Exception as e:
                logger.error(f"Admin user detail error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))

        # ── Admin Change User Plan ──
        elif data.startswith("adm_user_plan_") and not data.startswith("adm_setplan_"):
            if not is_admin_user(user, chat_id):
                return
            try:
                uid = data[14:]
                context.user_data["adm_plan_uid"] = uid
                plans_list = await db.plans.find({}, {"_id": 0}).sort("sort_order", 1).to_list(50)
                buttons = []
                for p in plans_list:
                    buttons.append([InlineKeyboardButton(f"📋 {p['name']} ({_fmt_limit(p['record_limit'], lang)} rec)", callback_data=f"adm_setplan_{p['plan_id']}")])
                buttons.append([InlineKeyboardButton("🔙", callback_data=f"adm_user_{uid}")])
                await query.edit_message_text(t(lang, "admin_select_plan"), reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
            except Exception as e:
                logger.error(f"Admin change plan menu error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))

        elif data.startswith("adm_setplan_"):
            if not is_admin_user(user, chat_id):
                return
            try:
                plan_id = data[12:]
                uid = context.user_data.get("adm_plan_uid")
                if not uid:
                    await query.edit_message_text("❌ Session expired. Please try again.", reply_markup=admin_back_kb(lang))
                    return
                plan_doc = await db.plans.find_one({"plan_id": plan_id}, {"_id": 0})
                if not plan_doc:
                    await query.edit_message_text("❌ Plan not found", reply_markup=admin_back_kb(lang))
                    return
                target = await db.users.find_one({"id": uid}, {"_id": 0})
                if not target:
                    await query.edit_message_text("❌ User not found", reply_markup=admin_back_kb(lang))
                    return
                await db.users.update_one({"id": uid}, {"$set": {"plan": plan_id, "record_limit": plan_doc["record_limit"]}})
                await log_activity("admin", "admin", "plan_changed", f"{target['email']} → {plan_id} (via Telegram)")
                await query.edit_message_text(
                    t(lang, "admin_plan_changed", email=target['email'], plan=plan_id),
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data=f"adm_user_{uid}")]]),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Admin set plan error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))

        # ── Admin Delete User (confirm) ──
        elif data.startswith("adm_user_del_") and not data.startswith("adm_user_del_yes_"):
            if not is_admin_user(user, chat_id):
                return
            try:
                uid = data[13:]
                target = await db.users.find_one({"id": uid}, {"_id": 0, "password_hash": 0})
                if not target:
                    await query.edit_message_text("❌ User not found", reply_markup=admin_back_kb(lang))
                    return
                rc = await db.dns_records.count_documents({"user_id": uid})
                text = t(lang, "admin_del_confirm", name=target['name'], email=target['email'], count=rc)
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅", callback_data=f"adm_user_del_yes_{uid}"),
                     InlineKeyboardButton("❌", callback_data=f"adm_user_{uid}")]
                ])
                await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Admin delete user confirm error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))

        elif data.startswith("adm_user_del_yes_"):
            if not is_admin_user(user, chat_id):
                return
            try:
                uid = data[17:]
                target = await db.users.find_one({"id": uid}, {"_id": 0})
                if not target or target.get("role") == "admin":
                    await query.edit_message_text("❌ Cannot delete", reply_markup=admin_back_kb(lang))
                    return
                # Delete user, CF records, and dns_records (best-effort)
                rec_count = await _delete_user_with_records(uid)
                await log_activity("admin", "admin", "user_deleted", f"{target['email']} + {rec_count} records (via Telegram)")
                await query.edit_message_text(
                    t(lang, "admin_del_success", email=target['email'], count=rec_count),
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="adm_users_0")]]),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Admin delete user error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))

        # ── Admin User Records ──
        elif data.startswith("adm_user_recs_"):
            if not is_admin_user(user, chat_id):
                return
            try:
                uid = data[14:]
                target = await db.users.find_one({"id": uid}, {"_id": 0, "password_hash": 0})
                if not target:
                    await query.edit_message_text("❌ User not found", reply_markup=admin_back_kb(lang))
                    return
                records = await db.dns_records.find({"user_id": uid}, {"_id": 0}).to_list(100)
                if not records:
                    await query.edit_message_text(t(lang, "admin_no_records"),
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data=f"adm_user_{uid}")]]))
                    return
                text = t(lang, "admin_user_records", name=target['name'], count=len(records))
                buttons = []
                for r in records:
                    proxy = "🟠" if r.get("proxied") else "⚪️"
                    text += f"{proxy} <code>{r['record_type']}</code> │ {r['full_name']} → <code>{r['content']}</code>\n"
                    buttons.append([InlineKeyboardButton(f"🗑 {r['record_type']} | {r['name']}", callback_data=f"adm_rec_del_{r['id']}")])
                buttons.append([InlineKeyboardButton("🔙", callback_data=f"adm_user_{uid}")])
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
            except Exception as e:
                logger.error(f"Admin user records error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))

        # ── Admin All Records (paginated) ──
        elif data.startswith("adm_records_"):
            if not is_admin_user(user, chat_id):
                return
            try:
                page = int(data.split("_")[-1])
                per_page = 8
                total = await db.dns_records.count_documents({})
                pages = max(1, (total + per_page - 1) // per_page)
                records = await db.dns_records.find({}, {"_id": 0}).skip(page * per_page).limit(per_page).to_list(per_page)
                if not records:
                    await query.edit_message_text(t(lang, "admin_no_records"), reply_markup=admin_back_kb(lang))
                    return
                text = f"📝 <b>{t(lang, 'admin_records')}</b> ({page + 1}/{pages})\n\n"
                buttons = []
                user_cache = {}
                for r in records:
                    uid = r["user_id"]
                    if uid not in user_cache:
                        u = await db.users.find_one({"id": uid}, {"_id": 0, "email": 1, "name": 1})
                        user_cache[uid] = u or {"email": "?", "name": "?"}
                    proxy = "🟠" if r.get("proxied") else "⚪️"
                    text += f"{proxy} <code>{r['record_type']}</code> │ {r['full_name']}\n   → <code>{r['content']}</code> | {user_cache[uid]['name']}\n"
                    buttons.append([InlineKeyboardButton(f"🗑 {r['record_type']} | {r['name']}", callback_data=f"adm_rec_del_{r['id']}")])
                nav = []
                if page > 0:
                    nav.append(InlineKeyboardButton(t(lang, "btn_prev"), callback_data=f"adm_records_{page - 1}"))
                if page < pages - 1:
                    nav.append(InlineKeyboardButton(t(lang, "btn_next"), callback_data=f"adm_records_{page + 1}"))
                if nav:
                    buttons.append(nav)
                buttons.append([InlineKeyboardButton("🔙", callback_data="adm_panel")])
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
            except Exception as e:
                logger.error(f"Admin all records error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))

        # ── Admin Delete Record (confirm + execute) ──
        elif data.startswith("adm_rec_del_") and not data.startswith("adm_rec_del_yes_"):
            if not is_admin_user(user, chat_id):
                return
            try:
                rid = data[12:]
                record = await db.dns_records.find_one({"id": rid}, {"_id": 0})
                if not record:
                    await query.edit_message_text(t(lang, "delete_not_found"), reply_markup=admin_back_kb(lang))
                    return
                rec_user = await db.users.find_one({"id": record["user_id"]}, {"_id": 0, "name": 1, "email": 1})
                text = t(lang, "admin_record_del_confirm",
                         type=record['record_type'], name=record['full_name'],
                         value=record['content'], user=(rec_user or {}).get('email', '?'))
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton("✅", callback_data=f"adm_rec_del_yes_{rid}"),
                     InlineKeyboardButton("❌", callback_data="adm_records_0")]
                ])
                await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Admin record delete confirm error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))

        elif data.startswith("adm_rec_del_yes_"):
            if not is_admin_user(user, chat_id):
                return
            try:
                rid = data[16:]
                record = await db.dns_records.find_one({"id": rid}, {"_id": 0})
                if not record:
                    await query.edit_message_text(t(lang, "delete_not_found"), reply_markup=admin_back_kb(lang))
                    return
                await cf_delete_record(record["cf_record_id"], zone_id=record.get("zone_id"))
                await db.dns_records.delete_one({"id": rid})
                await db.users.update_one({"id": record["user_id"]}, {"$inc": {"record_count": -1}})
                await log_activity("admin", "admin", "record_deleted", f"{record['record_type']} {record['full_name']} (via Telegram)")
                await query.edit_message_text(
                    t(lang, "admin_record_del_success", type=record['record_type'], name=record['full_name']),
                    reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="adm_records_0")]]),
                    parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Admin record delete error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))

        # ── Admin Plans ──
        elif data == "adm_plans":
            if not is_admin_user(user, chat_id):
                return
            try:
                plans_list = await db.plans.find({}, {"_id": 0}).sort("sort_order", 1).to_list(50)
                if not plans_list:
                    await query.edit_message_text("📭 No plans", reply_markup=admin_back_kb(lang))
                    return
                text = t(lang, "admin_plans_title")
                for p in plans_list:
                    pop = " ⭐" if p.get("popular") else ""
                    text += t(lang, "admin_plan_line", name=p['name'], id=p['plan_id'], price=p.get('price', '-'), limit=_fmt_limit(p['record_limit'], lang)) + pop
                await query.edit_message_text(text, reply_markup=admin_back_kb(lang), parse_mode="HTML")
            except Exception as e:
                logger.error(f"Admin plans error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))

        # ── Admin Settings ──
        elif data == "adm_settings":
            if not is_admin_user(user, chat_id):
                return
            try:
                settings = await db.settings.find_one({"key": "site_settings"}, {"_id": 0})
                if not settings:
                    settings = {}
                text = t(lang, "admin_settings_title") + t(lang, "admin_settings_body",
                    tg_id=settings.get("telegram_id", "-"),
                    tg_url=settings.get("telegram_url", "-"),
                    bonus=settings.get("referral_bonus_per_invite", 1),
                    free_records=PLAN_LIMITS.get("free", 2),
                    msg_en=settings.get("contact_message_en", "-")[:50],
                    msg_fa=settings.get("contact_message_fa", "-")[:50])
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton(t(lang, "btn_edit_setting"), callback_data="adm_settings_edit")],
                    [InlineKeyboardButton("🔙", callback_data="adm_panel")]
                ])
                await query.edit_message_text(text, reply_markup=kb, parse_mode="HTML")
            except Exception as e:
                logger.error(f"Admin settings error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))

        elif data == "adm_settings_edit":
            if not is_admin_user(user, chat_id):
                return
            try:
                fields = [
                    ("telegram_id", "📱 Telegram ID"),
                    ("telegram_url", "🔗 Telegram URL"),
                    ("referral_bonus_per_invite", "🎁 Referral Bonus"),
                    ("contact_message_en", "💬 Contact EN"),
                    ("contact_message_fa", "💬 Contact FA"),
                ]
                buttons = []
                for fid, fname in fields:
                    buttons.append([InlineKeyboardButton(fname, callback_data=f"adm_set_{fid}")])
                buttons.append([InlineKeyboardButton("🔙", callback_data="adm_settings")])
                await query.edit_message_text(t(lang, "admin_setting_choose"), reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
            except Exception as e:
                logger.error(f"Admin settings edit error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))

        elif data.startswith("adm_set_"):
            if not is_admin_user(user, chat_id):
                return
            try:
                field = data[8:]
                context.user_data["adm_edit_field"] = field
                context.user_data["adm_edit_step"] = "value"
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="adm_settings")]])
                safe_field = field.replace("_", " ")
                await query.edit_message_text(
                    t(lang, "admin_setting_enter", field=safe_field),
                    reply_markup=kb, parse_mode="HTML"
                )
            except Exception as e:
                logger.error(f"Admin set field error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))

        # ── Admin Activity Logs (paginated) ──
        elif data.startswith("adm_logs_"):
            if not is_admin_user(user, chat_id):
                return
            try:
                page = int(data.split("_")[-1])
                per_page = 8
                total = await db.activity_logs.count_documents({})
                pages = max(1, (total + per_page - 1) // per_page)
                logs = await db.activity_logs.find({}, {"_id": 0}).sort("created_at", -1).skip(page * per_page).limit(per_page).to_list(per_page)
                if not logs:
                    await query.edit_message_text("📭 No logs", reply_markup=admin_back_kb(lang))
                    return
                text = t(lang, "admin_logs_title")
                for lg in logs:
                    text += t(lang, "admin_log_line",
                        date=lg.get('created_at', '-')[:16],
                        email=lg.get('user_email', '-'),
                        action=lg.get('action', '-'),
                        details=(lg.get('details', '') or '')[:60])
                # Trim if too long
                if len(text) > 3800:
                    text = text[:3800] + "\n..."
                nav = []
                if page > 0:
                    nav.append(InlineKeyboardButton(t(lang, "btn_prev"), callback_data=f"adm_logs_{page - 1}"))
                if page < pages - 1:
                    nav.append(InlineKeyboardButton(t(lang, "btn_next"), callback_data=f"adm_logs_{page + 1}"))
                buttons = []
                if nav:
                    buttons.append(nav)
                buttons.append([InlineKeyboardButton("🔙", callback_data="adm_panel")])
                await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(buttons), parse_mode="HTML")
            except Exception as e:
                logger.error(f"Admin logs error: {e}", exc_info=True)
                await query.edit_message_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))

    # ── Message Handler (for login & add record flows) ────────
    async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
        chat_id = update.effective_chat.id
        text = update.message.text.strip()
        lang = context.user_data.get("lang", "fa")
        logger.info(f"Telegram message from chat_id={chat_id}, step={context.user_data.get('login_step') or context.user_data.get('add_step', 'none')}")

        # ── User Change Own Password Flow ──
        chpass_step = context.user_data.get("chpass_step")
        if chpass_step == "current":
            current_user = await get_user_by_chat(chat_id)
            if not current_user:
                context.user_data.pop("chpass_step", None)
                return
            if not verify_password(text, current_user.get("password_hash", "")):
                context.user_data.pop("chpass_step", None)
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_back"), callback_data="main_menu")]])
                await update.message.reply_text(t(lang, "chpass_wrong_current"), reply_markup=kb)
                return
            context.user_data["chpass_step"] = "new_pass"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="main_menu")]])
            await update.message.reply_text(t(lang, "chpass_enter_new"), reply_markup=kb, parse_mode="HTML")
            return

        if chpass_step == "new_pass":
            current_user = await get_user_by_chat(chat_id)
            context.user_data.pop("chpass_step", None)
            if not current_user:
                return
            if len(text) < 6:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_back"), callback_data="main_menu")]])
                await update.message.reply_text(t(lang, "chpass_short"), reply_markup=kb)
                return
            await db.users.update_one({"id": current_user["id"]}, {"$set": {"password_hash": hash_password(text)}})
            await log_activity(current_user["id"], current_user["email"], "password_changed", "Self (via Telegram)")
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_back"), callback_data="main_menu")]])
            await update.message.reply_text(t(lang, "chpass_success"), reply_markup=kb)
            return

        # ── Admin Change User Password Flow ──
        adm_chpass_step = context.user_data.get("adm_chpass_step")
        if adm_chpass_step == "new_pass":
            adm_user = await get_user_by_chat(chat_id)
            if not is_admin_user(adm_user, chat_id):
                context.user_data.pop("adm_chpass_step", None)
                context.user_data.pop("adm_chpass_uid", None)
                return
            uid = context.user_data.get("adm_chpass_uid")
            context.user_data.pop("adm_chpass_step", None)
            context.user_data.pop("adm_chpass_uid", None)
            if not uid:
                return
            if len(text) < 6:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_back"), callback_data="adm_panel")]])
                await update.message.reply_text(t(lang, "admin_chpass_short"), reply_markup=kb)
                return
            target = await db.users.find_one({"id": uid}, {"_id": 0})
            if not target:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_back"), callback_data="adm_panel")]])
                await update.message.reply_text("❌ User not found", reply_markup=kb)
                return
            await db.users.update_one({"id": uid}, {"$set": {"password_hash": hash_password(text)}})
            await log_activity("admin", "admin", "password_changed", f"{target['email']} (via Telegram)")
            kb = InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="adm_panel")]])
            await update.message.reply_text(t(lang, "admin_chpass_success", email=target['email']), reply_markup=kb, parse_mode="HTML")
            return

        # ── Login Flow ──
        login_step = context.user_data.get("login_step")
        if login_step == "email":
            context.user_data["login_email"] = normalize_email(text)
            context.user_data["login_step"] = "password"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="main_menu")]])
            await update.message.reply_text(t(lang, "login_enter_password"), reply_markup=kb)
            return

        if login_step == "password":
            email = context.user_data.get("login_email", "")
            password = text
            context.user_data.pop("login_step", None)
            context.user_data.pop("login_email", None)

            user = await db.users.find_one({"email": email}, {"_id": 0})
            if not user or not verify_password(password, user.get("password_hash", "")):
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton(t(lang, "btn_login"), callback_data="help_login")],
                    [InlineKeyboardButton(t(lang, "btn_back"), callback_data="main_menu")]
                ])
                await update.message.reply_text(t(lang, "login_fail"), reply_markup=kb)
                return

            bot_lang = context.user_data.get("lang", "fa")
            await db.users.update_one({"id": user["id"]}, {"$set": {"telegram_chat_id": str(chat_id), "telegram_lang": bot_lang}})
            await log_activity(user["id"], user["email"], "telegram_linked", f"Telegram linked: {chat_id}")
            await update.message.reply_text(
                t(bot_lang, "login_success", name=user['name'], email=email),
                reply_markup=main_menu_kb(bot_lang, chat_id, user)
            )
            return

        # ── Registration Flow ──
        reg_step = context.user_data.get("reg_step")
        if reg_step == "name":
            name = text.strip()
            if len(name) < 2:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="main_menu")]])
                await update.message.reply_text("❌ " + (lang == "fa" and "نام باید حداقل ۲ کاراکتر باشد." or "Name must be at least 2 characters."), reply_markup=kb)
                return
            context.user_data["reg_name"] = name
            context.user_data["reg_step"] = "email"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="main_menu")]])
            await update.message.reply_text(t(lang, "register_email"), reply_markup=kb)
            return

        if reg_step == "email":
            email = normalize_email(text)
            if not email.endswith("@gmail.com"):
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="main_menu")]])
                await update.message.reply_text(t(lang, "register_email_invalid"), reply_markup=kb)
                return
            existing = await db.users.find_one({"email": email}, {"_id": 0})
            if existing:
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton(t(lang, "btn_login"), callback_data="help_login")],
                    [InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="main_menu")]
                ])
                await update.message.reply_text(t(lang, "register_email_exists"), reply_markup=kb)
                context.user_data.pop("reg_step", None)
                context.user_data.pop("reg_name", None)
                return
            context.user_data["reg_email"] = email
            context.user_data["reg_step"] = "password"
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="main_menu")]])
            await update.message.reply_text(t(lang, "register_password"), reply_markup=kb)
            return

        if reg_step == "password":
            password = text.strip()
            if len(password) < 6:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="main_menu")]])
                await update.message.reply_text(t(lang, "register_password_short"), reply_markup=kb)
                return

            reg_name = context.user_data.get("reg_name", "")
            reg_email = context.user_data.get("reg_email", "")
            context.user_data.pop("reg_step", None)
            context.user_data.pop("reg_name", None)
            context.user_data.pop("reg_email", None)

            # Use free plan limit (single source of truth: plans collection / PLAN_LIMITS cache)
            default_free = PLAN_LIMITS.get("free", 2)

            # Generate unique referral code
            ref_code = generate_referral_code()
            while await db.users.find_one({"referral_code": ref_code}):
                ref_code = generate_referral_code()

            user_id = str(uuid.uuid4())
            user_doc = {
                "id": user_id,
                "email": reg_email,
                "name": reg_name,
                "password_hash": hash_password(password),
                "plan": "free",
                "role": "user",
                "record_count": 0,
                "record_limit": default_free,
                "referral_code": ref_code,
                "referred_by": None,
                "referral_count": 0,
                "referral_bonus": 0,
                "telegram_chat_id": str(chat_id),
                "telegram_lang": lang,
                "created_at": datetime.now(timezone.utc).isoformat()
            }

            await db.users.insert_one(user_doc)
            await log_activity(user_id, reg_email, "register", "New account created via Telegram bot")

            # Link telegram prefs
            await set_chat_lang(chat_id, lang)

            # Check if email verification is needed
            verify_enabled = await is_email_verification_enabled()
            if verify_enabled:
                await db.users.update_one({"id": user_id}, {"$set": {"email_verified": False}})
                code = generate_verification_code()
                await db.verification_codes.delete_many({"email": reg_email})
                await db.verification_codes.insert_one({
                    "email": reg_email,
                    "code": code,
                    "user_id": user_id,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
                })
                await send_verification_email(reg_email, code)
                context.user_data["verify_email"] = reg_email
                context.user_data["verify_user_id"] = user_id
                context.user_data["reg_step"] = "verify"
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="main_menu")]])
                await update.message.reply_text(
                    t(lang, "verify_code_sent", email=reg_email),
                    reply_markup=kb, parse_mode="HTML"
                )
            else:
                await db.users.update_one({"id": user_id}, {"$set": {"email_verified": True}})
                # Show success + main menu
                new_user = await db.users.find_one({"id": user_id}, {"_id": 0})
                await update.message.reply_text(
                    t(lang, "register_success", name=reg_name, email=reg_email),
                    reply_markup=main_menu_kb(lang, chat_id, new_user),
                    parse_mode="HTML"
                )

            # Notify admin
            await notify_admin_new_user(reg_name, reg_email, "telegram")
            return

        # ── Email Verification Flow (bot) ──
        if reg_step == "verify":
            code_input = text.strip()
            verify_email_addr = context.user_data.get("verify_email", "")
            verify_uid = context.user_data.get("verify_user_id", "")

            record = await db.verification_codes.find_one({"email": verify_email_addr, "code": code_input})
            if not record:
                kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="main_menu")]])
                await update.message.reply_text(t(lang, "verify_invalid"), reply_markup=kb)
                return

            # Check expiry
            if record.get("expires_at"):
                expires = datetime.fromisoformat(record["expires_at"])
                if datetime.now(timezone.utc) > expires:
                    # Resend new code
                    new_code = generate_verification_code()
                    await db.verification_codes.delete_many({"email": verify_email_addr})
                    await db.verification_codes.insert_one({
                        "email": verify_email_addr,
                        "code": new_code,
                        "user_id": verify_uid,
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "expires_at": (datetime.now(timezone.utc) + timedelta(minutes=10)).isoformat()
                    })
                    await send_verification_email(verify_email_addr, new_code)
                    kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="main_menu")]])
                    await update.message.reply_text(t(lang, "verify_expired"), reply_markup=kb)
                    return

            # Mark verified
            await db.users.update_one({"email": verify_email_addr}, {"$set": {"email_verified": True}})
            await db.verification_codes.delete_many({"email": verify_email_addr})
            context.user_data.pop("reg_step", None)
            context.user_data.pop("verify_email", None)
            context.user_data.pop("verify_user_id", None)

            verified_user = await db.users.find_one({"id": verify_uid}, {"_id": 0})
            await update.message.reply_text(
                t(lang, "verify_success") + "\n" + t(lang, "register_success", name=verified_user['name'], email=verify_email_addr),
                reply_markup=main_menu_kb(lang, chat_id, verified_user),
                parse_mode="HTML"
            )
            return

        # ── Admin Settings Edit Flow ──
        adm_edit_step = context.user_data.get("adm_edit_step")
        if adm_edit_step == "value":
            adm_user = await get_user_by_chat(chat_id)
            if is_admin_user(adm_user, chat_id):
                try:
                    field = context.user_data.get("adm_edit_field", "")
                    context.user_data.pop("adm_edit_step", None)
                    context.user_data.pop("adm_edit_field", None)
                    value = text
                    # Convert numeric fields
                    if field in ("referral_bonus_per_invite",):
                        try:
                            value = int(value)
                        except ValueError:
                            await update.message.reply_text("❌ Must be a number", reply_markup=admin_back_kb(lang))
                            return
                    await db.settings.update_one({"key": "site_settings"}, {"$set": {field: value}}, upsert=True)
                    safe_field = field.replace("_", " ")
                    await update.message.reply_text(
                        t(lang, "admin_setting_updated", field=safe_field),
                        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("🔙", callback_data="adm_settings")]]),
                        parse_mode="HTML"
                    )
                except Exception as e:
                    logger.error(f"Admin settings save error: {e}", exc_info=True)
                    await update.message.reply_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=admin_back_kb(lang))
                return

        # ── Add Record Flow ──
        if not context.user_data.get("add_step"):
            return

        user = await get_user_by_chat(chat_id)
        lang = context.user_data.get("lang", "fa")
        if not user:
            await send_not_logged_in(update, lang, chat_id)
            context.user_data.pop("add_step", None)
            context.user_data.pop("add_type", None)
            context.user_data.pop("add_name", None)
            context.user_data.pop("add_zone_id", None)
            context.user_data.pop("add_zone_domain", None)
            return

        step = context.user_data.get("add_step")

        if step == "name":
            name = text.lower().replace(" ", "")
            if not name or len(name) > 63:
                await update.message.reply_text(t(lang, "add_name_invalid"))
                return
            context.user_data["add_name"] = name
            context.user_data["add_step"] = "value"
            record_type = context.user_data["add_type"]
            zone_domain = context.user_data.get("add_zone_domain", CF_ZONE_DOMAIN)
            hint = t(lang, f"add_enter_value_{record_type}")
            kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(lang, "btn_cancel"), callback_data="main_menu")]])
            await update.message.reply_text(
                t(lang, "add_name_confirm", name=name, domain=zone_domain, hint=hint),
                reply_markup=kb, parse_mode="HTML"
            )

        elif step == "value":
            content = text.strip()
            record_type = context.user_data["add_type"]
            enabled_types = await _get_enabled_record_types()
            if record_type not in enabled_types:
                saved_lang = context.user_data.get("lang", lang)
                context.user_data.clear()
                context.user_data["lang"] = saved_lang
                await update.message.reply_text(t(lang, "add_types_disabled"), reply_markup=back_menu_kb(lang))
                return
            name = context.user_data["add_name"]
            zone_id = context.user_data.get("add_zone_id")
            zone_domain = context.user_data.get("add_zone_domain", CF_ZONE_DOMAIN)
            full_name = f"{name}.{zone_domain}"
            # Clear flow data but preserve language
            saved_lang = context.user_data.get("lang", lang)
            context.user_data.clear()
            context.user_data["lang"] = saved_lang

            existing = await db.dns_records.find_one({"full_name": full_name, "record_type": record_type})
            if existing:
                await update.message.reply_text(
                    t(lang, "add_exists", name=full_name, type=record_type),
                    reply_markup=back_menu_kb(lang), parse_mode="HTML"
                )
                return
            try:
                # Block creation if the selected zone is disabled
                zone_status = await get_zone_status(zone_id or CF_ZONE_ID)
                if zone_status != "active":
                    disabled_msg = "⚠️ این دامنه در حال حاضر غیرفعال است." if lang == "fa" else "⚠️ This zone is currently disabled."
                    await update.message.reply_text(disabled_msg, reply_markup=back_menu_kb(lang))
                    return
                cf_result, used_zone = await cf_create_record(name=name, record_type=record_type, content=content, proxied=False, zone_id=zone_id)
                record_id = str(uuid.uuid4())
                record_doc = {
                    "id": record_id, "cf_record_id": cf_result["id"], "user_id": user["id"],
                    "name": name, "full_name": full_name, "record_type": record_type,
                    "content": content, "ttl": 1, "proxied": False,
                    "zone_id": used_zone["zone_id"],
                    "created_at": datetime.now(timezone.utc).isoformat()
                }
                await db.dns_records.insert_one(record_doc)
                await db.users.update_one({"id": user["id"]}, {"$inc": {"record_count": 1}})
                await log_activity(user["id"], user["email"], "record_created", f"{record_type} {full_name} → {content} (via Telegram)")
                kb = InlineKeyboardMarkup([
                    [InlineKeyboardButton(t(lang, "btn_view_records"), callback_data="records"),
                     InlineKeyboardButton(t(lang, "btn_add_another"), callback_data="add_start")],
                    [InlineKeyboardButton(t(lang, "btn_back"), callback_data="main_menu")]
                ])
                await update.message.reply_text(
                    t(lang, "add_success", type=record_type, name=full_name, value=content),
                    reply_markup=kb, parse_mode="HTML"
                )
            except Exception as e:
                await update.message.reply_text(t(lang, "error", err=_get_error_msg(e)), reply_markup=back_menu_kb(lang))

    # ── Global Error Handler ────────────────────────────────
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
        """Log errors caused by handlers."""
        logger.error(f"Telegram bot error: {context.error}", exc_info=context.error)
        # Try to notify user
        try:
            if update and hasattr(update, 'effective_chat') and update.effective_chat:
                chat_id = update.effective_chat.id
                user = await get_user_by_chat(chat_id)
                lang = user.get("telegram_lang", "fa") if user else context.user_data.get("lang", "fa")
                error_msg = t(lang, "error", err="Internal error. Please try /start again.")
                await context.bot.send_message(chat_id=chat_id, text=error_msg)
        except Exception:
            pass

    import asyncio

    # Stop any existing bot instance first (handles restart scenarios)
    await stop_telegram_bot()
    await asyncio.sleep(2)

    # ── Step 0: Force-close any stale polling connections via raw API ──
    try:
        async with httpx.AsyncClient(timeout=30.0) as hc:
            # Call deleteWebhook to clear any webhook
            await hc.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/deleteWebhook",
                json={"drop_pending_updates": False},
                timeout=10
            )
            # Force-close stale getUpdates by calling with short timeout
            # This will either succeed (no conflict) or return conflict error
            for _flush in range(3):
                resp = await hc.post(
                    f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
                    json={"offset": -1, "limit": 1, "timeout": 0},
                    timeout=10
                )
                data = resp.json()
                if data.get("ok"):
                    # Successfully claimed polling — clear offset
                    if data.get("result"):
                        last_id = data["result"][-1]["update_id"]
                        await hc.post(
                            f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
                            json={"offset": last_id + 1, "limit": 1, "timeout": 0},
                            timeout=10
                        )
                    logger.info("Telegram bot: pre-start flush OK, no conflict")
                    break
                elif "Conflict" in str(data.get("description", "")):
                    logger.warning(f"Telegram bot: conflict detected on flush attempt {_flush+1}, waiting...")
                    await asyncio.sleep(5)
                else:
                    break
    except Exception as e:
        logger.warning(f"Telegram bot: pre-start flush error (non-critical): {e}")

    # Wait for Telegram servers to release old long-poll connections
    logger.info("Telegram bot: waiting for old connections to fully close...")
    await asyncio.sleep(5)

    max_retries = 5
    for attempt in range(1, max_retries + 1):
        try:
            telegram_bot_app = (
                ApplicationBuilder()
                .token(TELEGRAM_BOT_TOKEN)
                .read_timeout(30)
                .write_timeout(30)
                .connect_timeout(15)
                .pool_timeout(5)
                .build()
            )

            # ── Wrapper to add logging and error handling to all handlers ──
            def wrap_handler(fn, handler_name):
                async def wrapped(update, context):
                    chat_id = update.effective_chat.id if update.effective_chat else "?"
                    logger.info(f"[TG-HANDLER] {handler_name} triggered | chat_id={chat_id}")
                    try:
                        return await fn(update, context)
                    except Exception as e:
                        # Silently ignore benign "Message is not modified" errors
                        # (happens when user double-clicks the same inline button)
                        err_str = str(e)
                        if "Message is not modified" in err_str:
                            logger.debug(f"[TG-HANDLER] {handler_name} ignored benign edit: {err_str}")
                            # Best-effort: acknowledge the callback query so the spinner stops
                            try:
                                if update.callback_query:
                                    await update.callback_query.answer()
                            except Exception:
                                pass
                            return
                        logger.error(f"[TG-HANDLER] {handler_name} FAILED | chat_id={chat_id} | error={e}", exc_info=True)
                        # Try to send a proper error message instead of generic "Internal error"
                        try:
                            err_msg = _get_error_msg(e)
                            user_obj = await get_user_by_chat(chat_id) if chat_id != "?" else None
                            _lang = "fa"
                            if user_obj:
                                _lang = user_obj.get("telegram_lang", "fa")
                            elif hasattr(context, 'user_data'):
                                _lang = context.user_data.get("lang", "fa")
                            error_text = t(_lang, "error", err=err_msg)
                            back_kb = InlineKeyboardMarkup([[InlineKeyboardButton(t(_lang, "btn_back"), callback_data="main_menu")]])
                            if update.callback_query:
                                await update.callback_query.edit_message_text(error_text, reply_markup=back_kb)
                            elif update.message:
                                await update.message.reply_text(error_text, reply_markup=back_kb)
                        except Exception as notify_err:
                            logger.warning(f"[TG-HANDLER] Failed to send error notification: {notify_err}")
                            # Don't re-raise, swallow the error to prevent "Internal error" message
                return wrapped

            telegram_bot_app.add_handler(CommandHandler("start", wrap_handler(cmd_start, "cmd_start")))
            telegram_bot_app.add_handler(CommandHandler("login", wrap_handler(cmd_login, "cmd_login")))
            telegram_bot_app.add_handler(CallbackQueryHandler(wrap_handler(callback_handler, "callback_handler")))
            telegram_bot_app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, wrap_handler(message_handler, "message_handler")))
            telegram_bot_app.add_error_handler(error_handler)

            commands = [
                BotCommand("start", "منوی اصلی / Main Menu"),
            ]

            await telegram_bot_app.initialize()

            # ── Step 1: Force delete webhook ──
            del_result = await telegram_bot_app.bot.delete_webhook(drop_pending_updates=False)
            logger.info(f"Telegram bot: delete_webhook result={del_result}")

            # ── Step 2: Verify webhook is actually deleted ──
            wh_info = await telegram_bot_app.bot.get_webhook_info()
            logger.info(f"Telegram bot: webhook_info url='{wh_info.url}' pending={wh_info.pending_update_count}")
            if wh_info.url:
                logger.warning(f"Telegram bot: webhook still set to '{wh_info.url}', deleting again...")
                await telegram_bot_app.bot.delete_webhook(drop_pending_updates=False)
                await asyncio.sleep(3)

            # ── Step 3: Test getUpdates before starting polling ──
            try:
                async with httpx.AsyncClient(timeout=30.0) as hc:
                    resp = await hc.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
                        json={"offset": -1, "limit": 1, "timeout": 0},
                        timeout=10
                    )
                    gu_data = resp.json()
                    if not gu_data.get("ok"):
                        desc = gu_data.get("description", "")
                        if "Conflict" in desc:
                            logger.warning(f"Telegram bot: 409 Conflict on attempt {attempt} — another instance is polling!")
                            raise Exception(f"409 Conflict: {desc}")
                        else:
                            logger.warning(f"Telegram bot: getUpdates test failed: {desc}")
                    else:
                        # Reset offset
                        if gu_data.get("result"):
                            last_id = gu_data["result"][-1]["update_id"]
                            await hc.post(
                                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
                                json={"offset": last_id + 1, "limit": 1, "timeout": 0},
                                timeout=10
                            )
                            logger.info(f"Telegram bot: offset reset to {last_id + 1}")
                        else:
                            logger.info("Telegram bot: no pending updates, offset OK")
            except httpx.HTTPError as e:
                logger.warning(f"Telegram bot: getUpdates test HTTP error: {e}")
            # Re-raise Conflict exceptions to trigger retry
            except Exception as e:
                if "409 Conflict" in str(e):
                    raise
                logger.warning(f"Telegram bot: getUpdates test error (non-critical): {e}")

            # ── Step 4: Start application & polling ──
            await telegram_bot_app.bot.set_my_commands(commands)
            await telegram_bot_app.start()
            await telegram_bot_app.updater.start_polling(
                drop_pending_updates=False,
                allowed_updates=Update.ALL_TYPES,
                poll_interval=1.0,
            )

            bot_info = await telegram_bot_app.bot.get_me()
            logger.info(f"Telegram bot started successfully: @{bot_info.username} (ID: {bot_info.id})")

            # ── Step 5: Verify polling is working by checking one cycle ──
            await asyncio.sleep(3)
            if telegram_bot_app.updater and telegram_bot_app.updater.running:
                logger.info("Telegram bot: polling confirmed running ✓")
            else:
                logger.warning("Telegram bot: polling NOT running after start! Retrying...")
                raise Exception("Polling not running after start")

            return  # Success — exit retry loop
        except Exception as e:
            logger.error(f"Telegram bot start attempt {attempt}/{max_retries} failed: {e}", exc_info=True)
            # Cleanup failed instance
            try:
                if telegram_bot_app:
                    if telegram_bot_app.updater and telegram_bot_app.updater.running:
                        await telegram_bot_app.updater.stop()
                    if telegram_bot_app.running:
                        await telegram_bot_app.stop()
                    await telegram_bot_app.shutdown()
            except Exception:
                pass
            telegram_bot_app = None
            if attempt < max_retries:
                # Exponential backoff: 5s, 10s, 15s, 20s
                wait = attempt * 5
                logger.info(f"Telegram bot: retrying in {wait}s ...")
                await asyncio.sleep(wait)

    logger.error("Telegram bot: all start attempts failed.")

async def stop_telegram_bot():
    """Stop the Telegram bot gracefully with timeout protection."""
    global telegram_bot_app
    if telegram_bot_app is None:
        return
    import asyncio
    try:
        # Stop updater (polling)
        if telegram_bot_app.updater and telegram_bot_app.updater.running:
            await asyncio.wait_for(telegram_bot_app.updater.stop(), timeout=10)
            logger.info("Telegram bot: updater stopped")
        # Stop application
        if telegram_bot_app.running:
            await asyncio.wait_for(telegram_bot_app.stop(), timeout=10)
            logger.info("Telegram bot: application stopped")
        # Shutdown (release resources)
        await asyncio.wait_for(telegram_bot_app.shutdown(), timeout=10)
        logger.info("Telegram bot stopped successfully")
    except asyncio.TimeoutError:
        logger.warning("Telegram bot: stop timed out, forcing cleanup")
    except Exception as e:
        logger.warning(f"Telegram bot stop error: {e}")
    finally:
        telegram_bot_app = None
        # Flush stale connections by calling getUpdates with short timeout
        if TELEGRAM_BOT_TOKEN:
            try:
                async with httpx.AsyncClient(timeout=30.0) as hc:
                    await hc.post(
                        f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
                        json={"offset": -1, "limit": 1, "timeout": 0},
                        timeout=5
                    )
            except Exception:
                pass

# ============== TELEGRAM BOT STATUS ==============

@api_router.get("/telegram/status")
async def telegram_status():
    """Health check for Telegram bot."""
    if not TELEGRAM_BOT_TOKEN:
        return {"status": "disabled", "reason": "No token configured"}
    if telegram_bot_app is None:
        return {"status": "stopped", "reason": "Bot not running"}
    try:
        bot_info = await telegram_bot_app.bot.get_me()
        running = telegram_bot_app.running
        polling = telegram_bot_app.updater.running if telegram_bot_app.updater else False
        return {
            "status": "running" if (running and polling) else "degraded",
            "bot_username": f"@{bot_info.username}",
            "bot_id": bot_info.id,
            "app_running": running,
            "polling_running": polling
        }
    except Exception as e:
        return {"status": "error", "reason": str(e)}

@api_router.get("/telegram/debug")
async def telegram_debug():
    """Deep diagnostic for Telegram bot issues."""
    result = {
        "token_configured": bool(TELEGRAM_BOT_TOKEN),
        "token_prefix": TELEGRAM_BOT_TOKEN[:15] + "..." if TELEGRAM_BOT_TOKEN else None,
        "app_instance": telegram_bot_app is not None,
        "app_running": False,
        "polling_running": False,
        "webhook_info": None,
        "bot_info": None,
        "pending_updates_check": None,
        "handler_count": 0,
        "errors": []
    }

    if not TELEGRAM_BOT_TOKEN:
        result["errors"].append("No TELEGRAM_BOT_TOKEN in .env")
        return result

    # Check bot info
    try:
        async with httpx.AsyncClient(timeout=30.0) as hc:
            resp = await hc.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe",
                timeout=10
            )
            data = resp.json()
            if data.get("ok"):
                result["bot_info"] = {
                    "id": data["result"]["id"],
                    "username": data["result"]["username"],
                    "is_bot": data["result"]["is_bot"]
                }
            else:
                result["errors"].append(f"getMe failed: {data}")
    except Exception as e:
        result["errors"].append(f"getMe error: {str(e)}")

    # Check webhook
    try:
        async with httpx.AsyncClient(timeout=30.0) as hc:
            resp = await hc.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getWebhookInfo",
                timeout=10
            )
            data = resp.json()
            if data.get("ok"):
                wh = data["result"]
                result["webhook_info"] = {
                    "url": wh.get("url", ""),
                    "has_custom_certificate": wh.get("has_custom_certificate", False),
                    "pending_update_count": wh.get("pending_update_count", 0),
                    "last_error_date": wh.get("last_error_date"),
                    "last_error_message": wh.get("last_error_message"),
                }
                if wh.get("url"):
                    result["errors"].append(f"WEBHOOK IS SET: {wh['url']} — this blocks polling!")
    except Exception as e:
        result["errors"].append(f"getWebhookInfo error: {str(e)}")

    # Check for pending updates via raw API
    try:
        async with httpx.AsyncClient(timeout=30.0) as hc:
            resp = await hc.post(
                f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getUpdates",
                json={"offset": -1, "limit": 1, "timeout": 1},
                timeout=10
            )
            data = resp.json()
            if data.get("ok"):
                updates = data.get("result", [])
                result["pending_updates_check"] = {
                    "count": len(updates),
                    "last_update_id": updates[-1]["update_id"] if updates else None,
                    "last_update_type": list(updates[-1].keys()) if updates else None
                }
            else:
                result["errors"].append(f"getUpdates failed: {data.get('description', 'unknown')}")
                if "Conflict" in str(data):
                    result["errors"].append("CONFLICT: Another bot instance is using getUpdates!")
    except Exception as e:
        result["errors"].append(f"getUpdates error: {str(e)}")

    # Check app state
    if telegram_bot_app:
        result["app_running"] = telegram_bot_app.running
        result["polling_running"] = telegram_bot_app.updater.running if telegram_bot_app.updater else False
        result["handler_count"] = len(telegram_bot_app.handlers.get(0, []))

    return result

# Include router
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

async def _normalize_existing_user_emails():
    """One-time migration for accounts created before emails were normalized.

    Lookups now go through normalize_email(), so a row still stored as
    'Foo@Gmail.com' would become unreachable. Rows whose normalized form
    would collide with another account are left alone and reported, so no
    account is silently merged or lost."""
    migrated = 0
    collisions = []
    async for u in db.users.find({}, {"_id": 0, "id": 1, "email": 1}):
        raw = u.get("email") or ""
        norm = normalize_email(raw)
        if norm == raw:
            continue
        clash = await db.users.find_one({"email": norm}, {"_id": 0, "id": 1})
        if clash and clash.get("id") != u.get("id"):
            collisions.append(raw)
            continue
        await db.users.update_one({"id": u["id"]}, {"$set": {"email": norm}})
        migrated += 1
    if migrated:
        logger.info(f"Normalized {migrated} user email(s) to lowercase")
    if collisions:
        logger.warning(
            "These accounts differ from an existing account only by email case and were "
            f"left unchanged — resolve them manually: {', '.join(collisions)}"
        )


@app.on_event("startup")
async def startup():
    # Auto-detect Cloudflare zone domain
    await cf_fetch_zone_domain()

    # Must run before the admin seed below, which looks users up by email.
    await _normalize_existing_user_emails()

    # Create indexes
    await db.users.create_index("email", unique=True)
    await db.users.create_index("id", unique=True)
    await db.dns_records.create_index("user_id")
    await db.dns_records.create_index("id", unique=True)
    await db.plans.create_index("plan_id", unique=True)
    await db.users.create_index("referral_code", unique=True, sparse=True)
    
    await db.activity_logs.create_index("user_id")
    await db.activity_logs.create_index("created_at")
    await db.users.create_index("telegram_chat_id", sparse=True)
    await db.telegram_prefs.create_index("chat_id", unique=True)
    
    # Seed admin user if not exists
    admin_email = normalize_email(os.environ.get('ADMIN_EMAIL', f'admin@{DOMAIN_NAME}'))
    admin_pass = os.environ.get('ADMIN_PASSWORD', 'admin123456')
    existing_admin = await db.users.find_one({"email": admin_email})
    if not existing_admin:
        admin_doc = {
            "id": str(uuid.uuid4()),
            "email": admin_email,
            "name": "Admin",
            "password_hash": hash_password(admin_pass),
            "plan": "admin",
            "role": "admin",
            "record_count": 0,
            "record_limit": 0,
            "referral_code": generate_referral_code(),
            "referred_by": None,
            "referral_count": 0,
            "referral_bonus": 0,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        await db.users.insert_one(admin_doc)
        logger.info(f"Admin user created: {admin_email}")
    else:
        # Ensure existing admin has unlimited records and admin plan
        update_fields = {}
        if not existing_admin.get("referral_code"):
            update_fields["referral_code"] = generate_referral_code()
            update_fields["referred_by"] = None
            update_fields["referral_count"] = 0
            update_fields["referral_bonus"] = 0
        if existing_admin.get("record_limit") != 0 or existing_admin.get("plan") != "admin":
            update_fields["plan"] = "admin"
            update_fields["record_limit"] = 0
        # Always sync admin password from env
        if not verify_password(admin_pass, existing_admin.get("password_hash", "")):
            update_fields["password_hash"] = hash_password(admin_pass)
            logger.info("Admin password synced from environment")
        if update_fields:
            await db.users.update_one({"email": admin_email}, {"$set": update_fields})
    
    # Seed default plans if empty
    plans_count = await db.plans.count_documents({})
    if plans_count == 0:
        for p in DEFAULT_PLANS:
            await db.plans.insert_one(dict(p))
        logger.info("Default plans seeded")
    else:
        # Update existing plans: sync prices from DEFAULT_PLANS
        for dp in DEFAULT_PLANS:
            existing = await db.plans.find_one({"plan_id": dp["plan_id"]}, {"_id": 0})
            if existing and (existing.get("price") != dp["price"] or existing.get("price_fa") != dp["price_fa"]):
                await db.plans.update_one(
                    {"plan_id": dp["plan_id"]},
                    {"$set": {"price": dp["price"], "price_fa": dp["price_fa"]}}
                )
                logger.info(f"Updated plan '{dp['plan_id']}' prices")
        # Load plan limits from DB into cache
        db_plans = await db.plans.find({}, {"_id": 0}).to_list(50)
        for p in db_plans:
            PLAN_LIMITS[p["plan_id"]] = p["record_limit"]
    
    # Seed default settings if not exists
    existing_settings = await db.settings.find_one({"key": "site_settings"})
    if not existing_settings:
        await db.settings.insert_one({
            "key": "site_settings",
            "telegram_id": "",
            "telegram_url": "https://t.me/",
            "contact_message_en": "Contact us on Telegram for pricing",
            "contact_message_fa": "برای استعلام قیمت در تلگرام تماس بگیرید",
            "referral_bonus_per_invite": 1,
        })
    else:
        # Ensure new fields exist in settings
        updates = {}
        if "referral_bonus_per_invite" not in (existing_settings or {}):
            updates["referral_bonus_per_invite"] = 1
        # Drop legacy setting key (now derived from Free plan record_limit)
        if "default_free_records" in (existing_settings or {}):
            await db.settings.update_one({"key": "site_settings"}, {"$unset": {"default_free_records": ""}})
        if updates:
            await db.settings.update_one(
                {"key": "site_settings"},
                {"$set": updates}
            )
    
    logger.info("Database indexes created")
    
    # Start Telegram bot
    await start_telegram_bot()
    
    # Start backup scheduler
    start_backup_scheduler()

@app.on_event("shutdown")
async def shutdown_db_client():
    global backup_task_handle
    if backup_task_handle and not backup_task_handle.done():
        backup_task_handle.cancel()
    await stop_telegram_bot()
    client.close()
