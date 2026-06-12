"""
Google Calendar Free/Busy Backend Application
OAuth 2.0 Web Server Flow with secure token storage
"""

import os
import json
import logging
import hashlib
import secrets
import uuid
from datetime import datetime, timedelta
from typing import Optional
from urllib.parse import urlencode
from pathlib import Path as SysPath

import httpx
from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    Query,
    Path as FastAPIPath,
    Request,
    Response,
)
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from matching import find_matching_options
from sqlalchemy import create_engine, Column, String, DateTime, Integer, text
from sqlalchemy.orm import declarative_base, Session, sessionmaker
from cryptography.fernet import Fernet
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# ============================================================================
# CONFIGURATION
# ============================================================================

# Debug mode - set to True for verbose logging
DEBUG = True

CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")
ENCRYPTION_KEY = os.getenv("ENCRYPTION_KEY", "")
DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./calendar.db")
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")


def _resolve_redirect_uri() -> str:
    """Resolve the Google OAuth callback URI for local or hosted deployments."""
    redirect_uri = os.getenv("GOOGLE_REDIRECT_URI")
    if redirect_uri and redirect_uri.strip():
        return redirect_uri.strip()
    if PUBLIC_BASE_URL:
        return f"{PUBLIC_BASE_URL}/oauth/callback"
    return "http://127.0.0.1:8000/oauth/callback"


REDIRECT_URI = _resolve_redirect_uri()
# include openid/email scopes so we can identify the user (sub + email)
SCOPES = [
    "https://www.googleapis.com/auth/calendar.freebusy",
    "openid",
    "email",
]

# Logging configuration
log_level = logging.DEBUG if DEBUG else logging.INFO
logging.basicConfig(
    level=log_level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
logger.info(f"Debug mode: {DEBUG}")
logger.info(f"Logging level: {logging.getLevelName(log_level)}")

# ============================================================================
# VALIDATION
# ============================================================================


def _validate_config():
    """Validate configuration - called when endpoints are accessed"""
    logger.debug("Validating configuration...")
    if not CLIENT_ID:
        logger.error("GOOGLE_CLIENT_ID not set")
        raise ValueError("GOOGLE_CLIENT_ID environment variable not set")
    if not CLIENT_SECRET:
        logger.error("GOOGLE_CLIENT_SECRET not set")
        raise ValueError("GOOGLE_CLIENT_SECRET environment variable not set")
    if not ENCRYPTION_KEY:
        logger.error("ENCRYPTION_KEY not set")
        raise ValueError("ENCRYPTION_KEY environment variable not set")

    # Validate encryption key format
    try:
        key = (
            ENCRYPTION_KEY.encode()
            if isinstance(ENCRYPTION_KEY, str)
            else ENCRYPTION_KEY
        )
        Fernet(key)
        logger.debug("Encryption key format validated")
    except Exception as e:
        logger.error(f"Invalid ENCRYPTION_KEY format: {e}")
        raise ValueError(f"Invalid ENCRYPTION_KEY format: {e}")


# ============================================================================
# DATABASE
# ============================================================================

Base = declarative_base()
engine_kwargs = {}
if DATABASE_URL.startswith("sqlite"):
    engine_kwargs["connect_args"] = {"check_same_thread": False}
engine = create_engine(DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, expire_on_commit=False, bind=engine)


class GoogleAccount(Base):
    """Database model for stored Google accounts"""

    __tablename__ = "google_accounts"

    account_label = Column(String, primary_key=True)
    owner_user_id = Column(String, nullable=True, index=True)
    google_sub = Column(String, nullable=False, unique=True)
    email = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)  # Encrypted
    cached_busy = Column(String, nullable=True)  # JSON of last 30‑day busy periods
    created_at = Column(DateTime, default=datetime.utcnow)
    selected_as = Column(
        String, nullable=True
    )  # legacy UI selection marker for older prototype screens


class User(Base):
    """First-party application user for the authenticated MVP foundation."""

    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, nullable=False, unique=True, index=True)
    display_name = Column(String, nullable=True)
    phone_number = Column(String, nullable=True)
    timezone_preference = Column(String, nullable=False, default="UTC")
    time_presets = Column(String, nullable=True)
    linked_calendar_label = Column(String, nullable=True)
    linked_calendar_labels = Column(String, nullable=True)
    password_hash = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserSession(Base):
    """Hashed bearer/cookie session token for a logged-in application user."""

    __tablename__ = "user_sessions"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, nullable=False, index=True)
    token_hash = Column(String, nullable=False, unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)


class OAuthState(Base):
    """One-time OAuth state tying a Google callback to a user-owned slot."""

    __tablename__ = "oauth_states"

    state = Column(String, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    account_label = Column(String, nullable=False)
    return_path = Column(String, nullable=False, default="/account")
    request_id = Column(String, nullable=True, index=True)
    request_role = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)


class MeetingRequest(Base):
    """SQLite-backed meeting request draft for the MVP frontend workflow."""

    __tablename__ = "meeting_requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    owner_user_id = Column(String, nullable=False, index=True)
    title = Column(String, nullable=False)
    invitee_email = Column(String, nullable=False)
    invitee_emails = Column(String, nullable=True)
    friend_ids = Column(String, nullable=True)
    time_preset_id = Column(String, nullable=True)
    owner_calendar_label = Column(String, nullable=True)
    invitee_calendar_label = Column(String, nullable=True)
    duration_minutes = Column(Integer, nullable=False, default=30)
    earliest_date = Column(String, nullable=False)
    latest_date = Column(String, nullable=False)
    timezone = Column(String, nullable=False, default="UTC")
    window_start = Column(String, nullable=False, default="09:00")
    window_end = Column(String, nullable=False, default="17:00")
    allowed_weekdays = Column(String, nullable=False, default="[]")
    allowed_windows = Column(String, nullable=False, default="[]")
    notes = Column(String, nullable=True)
    status = Column(String, nullable=False, default="draft")
    invite_token_hash = Column(String, nullable=True, unique=True, index=True)
    invite_expires_at = Column(DateTime, nullable=True)
    invite_opened_at = Column(DateTime, nullable=True)
    invite_accepted_at = Column(DateTime, nullable=True)
    invite_declined_at = Column(DateTime, nullable=True)
    invitee_user_id = Column(String, nullable=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow)


class RequestAuditEvent(Base):
    """Append-only audit event for meeting request lifecycle changes."""

    __tablename__ = "request_audit_events"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    request_id = Column(String, nullable=False, index=True)
    actor_user_id = Column(String, nullable=True, index=True)
    action = Column(String, nullable=False)
    details = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class FriendRequest(Base):
    """Email-based friend invitation between application users."""

    __tablename__ = "friend_requests"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    requester_user_id = Column(String, nullable=False, index=True)
    requester_email = Column(String, nullable=False)
    recipient_email = Column(String, nullable=False, index=True)
    recipient_user_id = Column(String, nullable=True, index=True)
    status = Column(String, nullable=False, default="pending")
    created_at = Column(DateTime, default=datetime.utcnow)
    responded_at = Column(DateTime, nullable=True)


Base.metadata.create_all(bind=engine)


def _run_lightweight_migrations() -> None:
    """Apply tiny additive migrations for existing prototype SQLite databases."""
    if not DATABASE_URL.startswith("sqlite"):
        return

    with engine.begin() as connection:
        google_columns = {
            row[1]
            for row in connection.execute(text("PRAGMA table_info(google_accounts)"))
        }
        if "owner_user_id" not in google_columns:
            connection.execute(
                text("ALTER TABLE google_accounts ADD COLUMN owner_user_id VARCHAR")
            )

        request_tables = {
            row[0]
            for row in connection.execute(
                text("SELECT name FROM sqlite_master WHERE type='table'")
            )
        }
        if "oauth_states" in request_tables:
            oauth_columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(oauth_states)"))
            }
            if "return_path" not in oauth_columns:
                connection.execute(
                    text("ALTER TABLE oauth_states ADD COLUMN return_path VARCHAR DEFAULT '/account'")
                )

        if "users" in request_tables:
            user_columns = {
                row[1] for row in connection.execute(text("PRAGMA table_info(users)"))
            }
            user_additive_columns = {
                "phone_number": "VARCHAR",
                "timezone_preference": "VARCHAR DEFAULT 'UTC'",
                "time_presets": "VARCHAR",
                "linked_calendar_label": "VARCHAR",
                "linked_calendar_labels": "VARCHAR",
            }
            for column_name, column_type in user_additive_columns.items():
                if column_name not in user_columns:
                    connection.execute(text(f"ALTER TABLE users ADD COLUMN {column_name} {column_type}"))

        if "meeting_requests" in request_tables:
            request_columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(meeting_requests)"))
            }
            additive_columns = {
                "invitee_emails": "VARCHAR",
                "friend_ids": "VARCHAR",
                "time_preset_id": "VARCHAR",
                "owner_calendar_label": "VARCHAR",
                "invitee_calendar_label": "VARCHAR",
                "invite_token_hash": "VARCHAR",
                "invite_expires_at": "DATETIME",
                "invite_opened_at": "DATETIME",
                "invite_accepted_at": "DATETIME",
                "invite_declined_at": "DATETIME",
                "invitee_user_id": "VARCHAR",
            }
            for column_name, column_type in additive_columns.items():
                if column_name not in request_columns:
                    connection.execute(
                        text(
                            f"ALTER TABLE meeting_requests ADD COLUMN {column_name} {column_type}"
                        )
                    )

        if "oauth_states" in request_tables:
            oauth_columns = {
                row[1]
                for row in connection.execute(text("PRAGMA table_info(oauth_states)"))
            }
            oauth_additive_columns = {
                "request_id": "VARCHAR",
                "request_role": "VARCHAR",
            }
            for column_name, column_type in oauth_additive_columns.items():
                if column_name not in oauth_columns:
                    connection.execute(
                        text(
                            f"ALTER TABLE oauth_states ADD COLUMN {column_name} {column_type}"
                        )
                    )


_run_lightweight_migrations()


# ============================================================================
# APPLICATION AUTHENTICATION
# ============================================================================

SESSION_COOKIE_NAME = "calendar_matching_session"
SESSION_DURATION_DAYS = int(os.getenv("SESSION_DURATION_DAYS", "14"))
INVITE_DURATION_DAYS = int(os.getenv("INVITE_DURATION_DAYS", "14"))
PASSWORD_HASH_ITERATIONS = 260_000


def _normalize_email(email: str) -> str:
    """Normalize and minimally validate a user email address."""
    normalized = email.strip().lower()
    if "@" not in normalized or normalized.startswith("@") or normalized.endswith("@"):
        raise ValueError("A valid email address is required")
    return normalized


def _hash_password(password: str) -> str:
    """Hash a password with PBKDF2 using only Python standard-library tools."""
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        "sha256", password.encode(), salt.encode(), PASSWORD_HASH_ITERATIONS
    ).hex()
    return f"pbkdf2_sha256${PASSWORD_HASH_ITERATIONS}${salt}${digest}"


def _verify_password(password: str, stored_hash: str) -> bool:
    """Verify a candidate password against a stored PBKDF2 hash."""
    try:
        algorithm, iterations, salt, expected = stored_hash.split("$", 3)
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), salt.encode(), int(iterations)
        ).hex()
        return secrets.compare_digest(digest, expected)
    except Exception:
        return False


def _hash_session_token(token: str) -> str:
    """Hash a session token before lookup/storage."""
    return hashlib.sha256(token.encode()).hexdigest()


def _hash_invite_token(token: str) -> str:
    """Hash an invite token so only a non-reversible digest is stored."""
    return hashlib.sha256(token.encode()).hexdigest()


def _provision_development_users() -> None:
    """Create disposable test users for local SQLite containers if missing."""
    if not DATABASE_URL.startswith("sqlite"):
        return

    seed_users = [
        ("twan.houwers92@gmail.com", "Twan Houwers"),
        ("twan@dutchwebshark.com", "Dutchwebshark"),
    ]
    db = SessionLocal()
    try:
        for email, display_name in seed_users:
            normalized_email = _normalize_email(email)
            if db.query(User).filter_by(email=normalized_email).first():
                continue
            db.add(
                User(
                    id=str(uuid.uuid4()),
                    email=normalized_email,
                    display_name=display_name,
                    password_hash=_hash_password("Test123!"),
                    created_at=datetime.utcnow(),
                )
            )
        db.commit()
    finally:
        db.close()


_provision_development_users()


def _extract_session_token(request: Request, authorization: Optional[str]) -> Optional[str]:
    """Read a session token from Authorization: Bearer or the HTTP-only cookie."""
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value:
            return value.strip()
    return request.cookies.get(SESSION_COOKIE_NAME)


def _storage_account_label(user_id: str, account_label: str) -> str:
    """Map a user-owned calendar label to the legacy single-column account key."""
    return f"user:{user_id}:{account_label}"


def _display_account_label(account: GoogleAccount) -> str:
    """Return the public slot label for a stored Google account."""
    if account.account_label.startswith("user:"):
        return account.account_label.rsplit(":", 1)[-1]
    return account.account_label


class SQLiteIdentityRepository:
    """SQLite-backed identity/session repository boundary for auth workflows."""

    def __init__(self, db: Session):
        self.db = db

    def create_user(self, email: str, password: str, display_name: Optional[str]) -> User:
        normalized_email = _normalize_email(email)
        existing = self.db.query(User).filter_by(email=normalized_email).first()
        if existing:
            raise ValueError("A user with this email already exists")
        user = User(
            id=str(uuid.uuid4()),
            email=normalized_email,
            display_name=display_name.strip() if display_name else None,
            password_hash=_hash_password(password),
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def authenticate_user(self, email: str, password: str) -> Optional[User]:
        normalized_email = _normalize_email(email)
        user = self.db.query(User).filter_by(email=normalized_email).first()
        if not user or not _verify_password(password, user.password_hash):
            return None
        return user

    def create_session(self, user: User) -> tuple[str, UserSession]:
        token = secrets.token_urlsafe(32)
        session = UserSession(
            id=str(uuid.uuid4()),
            user_id=user.id,
            token_hash=_hash_session_token(token),
            expires_at=datetime.utcnow() + timedelta(days=SESSION_DURATION_DAYS),
        )
        self.db.add(session)
        self.db.commit()
        self.db.refresh(session)
        return token, session

    def get_user_by_session_token(self, token: str) -> Optional[User]:
        token_hash = _hash_session_token(token)
        session = self.db.query(UserSession).filter_by(token_hash=token_hash).first()
        if (
            not session
            or session.revoked_at is not None
            or session.expires_at <= datetime.utcnow()
        ):
            return None
        return self.db.query(User).filter_by(id=session.user_id).first()

    def revoke_session(self, token: str) -> bool:
        token_hash = _hash_session_token(token)
        session = self.db.query(UserSession).filter_by(token_hash=token_hash).first()
        if not session or session.revoked_at is not None:
            return False
        session.revoked_at = datetime.utcnow()
        self.db.add(session)
        self.db.commit()
        return True


def _current_user_from_token(token: str) -> Optional[User]:
    """Resolve a bearer/cookie token to a user, if the session is still valid."""
    db = SessionLocal()
    try:
        return SQLiteIdentityRepository(db).get_user_by_session_token(token)
    finally:
        db.close()


def _current_user_from_request(request: Request) -> Optional[User]:
    """Resolve the current user from the browser session cookie for page routing."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if not token:
        return None
    return _current_user_from_token(token)


def require_current_user(
    request: Request, authorization: Optional[str] = Header(default=None)
) -> User:
    """FastAPI dependency requiring a valid application session."""
    token = _extract_session_token(request, authorization)
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")

    user = _current_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid or expired session")
    return user


# ============================================================================
# TOKEN ENCRYPTION
# ============================================================================


class TokenManager:
    """Handles encryption and decryption of refresh tokens"""

    def __init__(self, key: str):
        if isinstance(key, str):
            key = key.encode()
        self.cipher = Fernet(key)

    def encrypt(self, token: str) -> str:
        """Encrypt a refresh token"""
        return self.cipher.encrypt(token.encode()).decode()

    def decrypt(self, encrypted_token: str) -> str:
        """Decrypt a refresh token"""
        try:
            decrypted = self.cipher.decrypt(encrypted_token.encode()).decode()
            logger.debug("Token decryption successful")
            return decrypted
        except Exception as e:
            logger.error(f"Token decryption failed: {type(e).__name__}: {e}")
            raise ValueError("Failed to decrypt refresh token")


# Lazy initialization of token_manager
_token_manager = None


def get_token_manager():
    """Get or create token manager (lazy initialization)"""
    global _token_manager
    if _token_manager is None:
        try:
            _token_manager = TokenManager(ENCRYPTION_KEY)
        except Exception as e:
            raise RuntimeError(f"Failed to initialize token manager: {e}")
    return _token_manager


# ============================================================================
# OAUTH FLOW
# ============================================================================


class OAuthHandler:
    """Handles Google OAuth 2.0 Web Server flow"""

    @staticmethod
    def get_authorization_url(account_label: str) -> str:
        """Generate Google authorization URL"""
        params = {
            "client_id": CLIENT_ID,
            "redirect_uri": REDIRECT_URI,
            "response_type": "code",
            "scope": " ".join(SCOPES),
            "access_type": "offline",
            "prompt": "consent",
            "state": account_label,  # Store account_label in state for verification
        }
        return f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"

    @staticmethod
    async def exchange_code_for_tokens(code: str) -> dict:
        """Exchange authorization code for access and refresh tokens"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "code": code,
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "redirect_uri": REDIRECT_URI,
                    "grant_type": "authorization_code",
                },
            )
            response.raise_for_status()
            return response.json()

    @staticmethod
    async def refresh_access_token(refresh_token: str) -> str:
        """Get a new access token using the refresh token"""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "refresh_token": refresh_token,
                    "grant_type": "refresh_token",
                },
            )
            response.raise_for_status()
            data = response.json()
            return data["access_token"]


# ============================================================================
# GOOGLE CALENDAR API CLIENT
# ============================================================================


class GoogleCalendarClient:
    """Handles Google Calendar API interactions"""

    @staticmethod
    async def get_freebusy(access_token: str, time_min: str, time_max: str) -> dict:
        """
        Get free/busy information for primary calendar

        Args:
            access_token: Google API access token
            time_min: RFC 3339 formatted start time
            time_max: RFC 3339 formatted end time

        Returns:
            Dictionary with busy periods
        """
        payload = {
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [{"id": "primary"}],
        }

        async with httpx.AsyncClient() as client:
            response = await client.post(
                "https://www.googleapis.com/calendar/v3/freeBusy",
                json=payload,
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()

            # Extract busy periods for primary calendar
            if "calendars" in data and "primary" in data["calendars"]:
                return {
                    "busy": data["calendars"]["primary"].get("busy", []),
                    "calendar_id": "primary",
                }
            return {"busy": [], "calendar_id": "primary"}


# ============================================================================
# DATABASE OPERATIONS
# ============================================================================


class DatabaseService:
    """Handles database operations"""

    @staticmethod
    def save_account(
        account_label: str,
        owner_user_id: str,
        google_sub: str,
        email: str,
        refresh_token: str,
        db: Session,
    ) -> GoogleAccount:
        """Save or update a Google account in the database"""
        # require valid sub
        if not google_sub:
            raise ValueError("google_sub cannot be empty")

        # Encrypt the refresh token before storing
        encrypted_token = get_token_manager().encrypt(refresh_token)
        storage_label = _storage_account_label(owner_user_id, account_label)

        # Check if account already exists for this user-owned slot or Google subject.
        existing = (
            db.query(GoogleAccount).filter_by(account_label=storage_label).first()
        )
        existing_by_sub = db.query(GoogleAccount).filter_by(google_sub=google_sub).first()
        if existing_by_sub and existing_by_sub.account_label != storage_label:
            if existing:
                db.delete(existing)
                db.flush()
            existing = existing_by_sub
            existing.account_label = storage_label

        if existing:
            existing.owner_user_id = owner_user_id
            existing.google_sub = google_sub
            existing.email = email
            existing.refresh_token = encrypted_token
            db.commit()
            return existing
        else:
            account = GoogleAccount(
                account_label=storage_label,
                owner_user_id=owner_user_id,
                google_sub=google_sub,
                email=email,
                refresh_token=encrypted_token,
            )
            db.add(account)
            db.commit()
            db.refresh(account)
            return account

    @staticmethod
    def get_account(
        account_label: str, db: Session, owner_user_id: str
    ) -> Optional[GoogleAccount]:
        """Retrieve a Google account from the database"""
        logger.debug(f"Retrieving account '{account_label}' from database")
        return (
            db.query(GoogleAccount)
            .filter_by(account_label=_storage_account_label(owner_user_id, account_label))
            .first()
        )

    @staticmethod
    def get_all_accounts(db: Session, owner_user_id: str) -> list[GoogleAccount]:
        """Get stored accounts for one authenticated user."""
        return db.query(GoogleAccount).filter_by(owner_user_id=owner_user_id).all()


# ============================================================================
# RESPONSE MODELS
# ============================================================================


class BusyPeriod(BaseModel):
    start: str
    end: str


class TimeWindow(BaseModel):
    day: int
    start: str
    end: str


class AuthRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(AuthRequest):
    display_name: Optional[str] = None


class TimePreset(BaseModel):
    id: str
    name: str
    windows: list[TimeWindow] = Field(default_factory=list)


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    phone_number: Optional[str] = None
    timezone_preference: str = "UTC"
    linked_calendar_label: Optional[str] = None
    linked_calendar_labels: list[str] = Field(default_factory=list)
    time_presets: list[TimePreset] = Field(default_factory=list)
    created_at: datetime


class ProfileUpdate(BaseModel):
    display_name: Optional[str] = None
    phone_number: Optional[str] = None
    timezone_preference: str = "UTC"
    linked_calendar_label: Optional[str] = None
    linked_calendar_labels: list[str] = Field(default_factory=list)
    time_presets: list[TimePreset] = Field(default_factory=list)


class AuthResponse(BaseModel):
    user: UserResponse
    session_token: str
    expires_at: datetime


class MeetingRequestCreate(BaseModel):
    title: str
    invitee_email: str = ""
    invitee_emails: list[str] = Field(default_factory=list)
    friend_ids: list[str] = Field(default_factory=list)
    time_preset_id: Optional[str] = None
    owner_calendar_label: Optional[str] = None
    invitee_calendar_label: Optional[str] = None
    duration_minutes: int = 30
    earliest_date: str
    latest_date: str
    timezone: str = "UTC"
    window_start: str = "09:00"
    window_end: str = "17:00"
    allowed_weekdays: list[str] = Field(default_factory=list)
    allowed_windows: list[TimeWindow] = Field(default_factory=list)
    notes: Optional[str] = None


class MeetingRequestResponse(MeetingRequestCreate):
    id: str
    status: str
    invite_url: Optional[str] = None
    invite_expires_at: Optional[datetime] = None
    invite_opened_at: Optional[datetime] = None
    invite_accepted_at: Optional[datetime] = None
    invite_declined_at: Optional[datetime] = None
    invitee_user_id: Optional[str] = None
    created_at: datetime
    updated_at: datetime


class InvitePreviewResponse(BaseModel):
    request_id: str
    title: str
    requester_email: str
    invitee_email: str
    duration_minutes: int
    earliest_date: str
    latest_date: str
    timezone: str
    window_start: str
    window_end: str
    allowed_weekdays: list[str]
    allowed_windows: list[TimeWindow] = Field(default_factory=list)
    status: str
    expires_at: datetime


class InviteActionResponse(BaseModel):
    request_id: str
    status: str
    message: str


class RequestCalendarSelection(BaseModel):
    calendar_label: str


class AuditEventResponse(BaseModel):
    id: str
    request_id: str
    actor_user_id: Optional[str] = None
    action: str
    details: Optional[str] = None
    created_at: datetime


class FreeBusyResponse(BaseModel):
    account_label: str
    email: str
    busy: list[BusyPeriod]


class PairedFreeBusyResponse(BaseModel):
    account_a: FreeBusyResponse
    account_b: FreeBusyResponse
    combined_busy: list[BusyPeriod]


class MatchingOptionsRequest(BaseModel):
    time_min: str
    time_max: str
    duration_minutes: int = 30
    allowed_windows: list[TimeWindow] = Field(default_factory=list)
    account_label: Optional[str] = None
    max_options: int = 3


class MeetingOption(BaseModel):
    start: str
    end: str
    score: int
    reason: str


class MatchingOptionsResponse(BaseModel):
    duration_minutes: int
    slot_granularity_minutes: int
    options: list[MeetingOption]


class FriendRequestCreate(BaseModel):
    recipient_email: str


class FriendRequestResponse(BaseModel):
    id: str
    requester_email: str
    recipient_email: str
    status: str
    created_at: datetime
    responded_at: Optional[datetime] = None


class DemoMatchingRequest(MatchingOptionsRequest):
    busy_a: list[BusyPeriod] = Field(default_factory=list)
    busy_b: list[BusyPeriod] = Field(default_factory=list)


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(
    title="Google Calendar Free/Busy API",
    description="OAuth 2.0 authenticated free/busy reader for Google Calendar",
    version="0.1.0",
)

# mount static directory for css/js/html assets
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/api/health", tags=["Health"])
async def health():
    """Health check endpoint"""
    return {"status": "healthy"}


def _serve_html(filename: str) -> HTMLResponse:
    """Serve a static HTML page from the prototype frontend directory."""
    template_path = SysPath(__file__).parent / "static" / "html" / filename
    return HTMLResponse(content=template_path.read_text(), status_code=200)


@app.get("/", response_class=HTMLResponse)
async def home():
    """Serve the public informational landing page."""
    return _serve_html("home.html")


def _serve_authenticated_html(request: Request, filename: str) -> HTMLResponse:
    """Serve an app page only when the browser has a valid session cookie."""
    if not _current_user_from_request(request):
        return RedirectResponse(url="/login", status_code=303)
    return _serve_html(filename)


def _not_implemented_page(feature_name: str) -> HTMLResponse:
    """Render an app-style placeholder for planned functionality."""
    safe_feature_name = feature_name.replace("<", "&lt;").replace(">", "&gt;")
    content = f"""<!doctype html>
<html lang="en">
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <title>{safe_feature_name} not implemented · Calendar Matching</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/css/bootstrap.min.css" rel="stylesheet">
    <link rel="stylesheet" href="/static/css/style.css">
</head>
<body class="auth-page">
    <div id="health" title="API health"></div>
    <nav class="navbar navbar-expand-lg app-navbar sticky-top"><div class="container"><a class="navbar-brand fw-bold" href="/">Calendar Matching</a></div></nav>
    <main class="container py-5 py-lg-6">
        <div class="row justify-content-center"><div class="col-lg-8 col-xl-7">
            <div class="auth-card card shadow-lg rounded-5 border-0"><div class="card-body p-4 p-lg-5 text-center">
                <p class="text-uppercase small fw-semibold text-primary mb-2">Planned functionality</p>
                <h1 class="display-6 fw-bold mb-3">{safe_feature_name} is not implemented yet.</h1>
                <p class="lead text-secondary">This page is a safe placeholder so unfinished Google, Microsoft, and other future actions do not fail silently.</p>
                <div class="d-flex flex-column flex-sm-row gap-2 justify-content-center mt-4">
                    <a class="btn btn-primary btn-lg" href="/">Back to home</a>
                    <button class="btn btn-outline-primary btn-lg" type="button" onclick="history.back()">Back to previous page</button>
                </div>
            </div></div>
        </div></div>
    </main>
    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.3/dist/js/bootstrap.bundle.min.js"></script>
    <script src="/static/js/app.js"></script>
</body>
</html>"""
    return HTMLResponse(content=content, status_code=200)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the standalone login page for unauthenticated users."""
    if _current_user_from_request(request):
        return RedirectResponse(url="/dashboard", status_code=303)
    return _serve_html("login.html")


@app.get("/register", response_class=HTMLResponse)
async def register_page(request: Request):
    """Serve the standalone registration page."""
    if _current_user_from_request(request):
        return RedirectResponse(url="/dashboard", status_code=303)
    return _serve_html("register.html")


@app.get("/profile", response_class=HTMLResponse)
async def profile_page(request: Request):
    """Serve the personal profile page."""
    return _serve_authenticated_html(request, "profile.html")


@app.get("/friends", response_class=HTMLResponse)
async def friends_page(request: Request):
    """Serve the friends page."""
    return _serve_authenticated_html(request, "friends.html")


@app.get("/requests/demo", response_class=HTMLResponse)
async def demo_request_page(request: Request):
    """Serve the demo request page for trying matching with connected Google calendars."""
    return _serve_authenticated_html(request, "demo_request.html")


@app.get("/account", response_class=HTMLResponse)
async def account_page(request: Request):
    """Redirect legacy account links to profile-owned calendar connections."""
    return RedirectResponse(url="/profile")


@app.get("/not-implemented/{feature_slug}", response_class=HTMLResponse)
async def not_implemented_page(feature_slug: str):
    """Serve an app page for non-working planned features."""
    feature_names = {
        "google-login": "Google app login",
        "microsoft-login": "Microsoft app login",
        "microsoft-calendar": "Microsoft Calendar connection",
        "google-contact-import": "Google contact import",
        "apple-contact-import": "Apple contact import",
        "microsoft-contact-import": "Microsoft contact import",
        "android-contact-import": "Android contact import",
    }
    feature_name = feature_names.get(
        feature_slug,
        feature_slug.replace("-", " ").strip().title() or "This feature",
    )
    return _not_implemented_page(feature_name)


@app.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    """Serve the meeting request dashboard page."""
    return _serve_authenticated_html(request, "dashboard.html")


@app.get("/requests/new", response_class=HTMLResponse)
async def new_request_page(request: Request):
    """Serve the request creation and matching prototype page."""
    return _serve_authenticated_html(request, "requests_new.html")


@app.get("/invite/{token}", response_class=HTMLResponse)
async def invite_page(token: str):
    """Serve the invite landing page placeholder for a request token."""
    return _serve_html("invite.html")


@app.get("/requests/{request_id}", response_class=HTMLResponse)
async def request_detail_page(request_id: str, request: Request):
    """Serve the request detail placeholder page."""
    return _serve_authenticated_html(request, "request_detail.html")


@app.get("/requests/{request_id}/availability", response_class=HTMLResponse)
async def availability_page(request_id: str, request: Request):
    """Serve the privacy-safe availability preview placeholder page."""
    return _serve_authenticated_html(request, "availability.html")


DEFAULT_TIME_PRESETS = [
    TimePreset(id="week-evening", name="Week-evening", windows=[TimeWindow(day=d, start="18:00", end="21:00") for d in range(5)]),
    TimePreset(id="weekend", name="Weekend", windows=[TimeWindow(day=4, start="18:00", end="23:59"), TimeWindow(day=5, start="00:00", end="23:59"), TimeWindow(day=6, start="00:00", end="21:00")]),
    TimePreset(id="weekend-day", name="Weekend day", windows=[TimeWindow(day=d, start="10:00", end="18:00") for d in [5, 6]]),
    TimePreset(id="weekend-evening", name="Weekend evening", windows=[TimeWindow(day=d, start="18:00", end="23:59") for d in [4, 5]]),
    TimePreset(id="working-hours", name="Working hours", windows=[TimeWindow(day=d, start="08:00", end="18:00") for d in range(5)]),
]


def _presets_for_user(user: User) -> list[TimePreset]:
    if user.time_presets:
        try:
            return [TimePreset(**item) for item in json.loads(user.time_presets)]
        except Exception:
            return DEFAULT_TIME_PRESETS
    return DEFAULT_TIME_PRESETS


def _linked_calendar_labels_for_user(user: User) -> list[str]:
    """Return the profile's selected calendar labels, preserving legacy single-label data."""
    if getattr(user, "linked_calendar_labels", None):
        try:
            labels = json.loads(user.linked_calendar_labels)
            if isinstance(labels, list):
                return [str(label) for label in labels if str(label).strip()]
        except Exception:
            pass
    return [user.linked_calendar_label] if user.linked_calendar_label else []


def _user_response(user: User) -> UserResponse:
    """Serialize a user without credentials."""
    linked_labels = _linked_calendar_labels_for_user(user)
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
        phone_number=user.phone_number,
        timezone_preference=user.timezone_preference or "UTC",
        linked_calendar_label=user.linked_calendar_label or (linked_labels[0] if linked_labels else None),
        linked_calendar_labels=linked_labels,
        time_presets=_presets_for_user(user),
        created_at=user.created_at,
    )


def _set_session_cookie(response: Response, token: str) -> None:
    """Set the browser session cookie used by the local prototype UI."""
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        max_age=SESSION_DURATION_DAYS * 24 * 60 * 60,
        secure=PUBLIC_BASE_URL.startswith("https://"),
    )


@app.post("/auth/register", response_model=AuthResponse, tags=["Authentication"])
async def register_user(request: RegisterRequest, response: Response):
    """Create a first-party user and start an authenticated session."""
    db = SessionLocal()
    try:
        repository = SQLiteIdentityRepository(db)
        try:
            user = repository.create_user(
                email=request.email,
                password=request.password,
                display_name=request.display_name,
            )
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        token, session = repository.create_session(user)
        _set_session_cookie(response, token)
        return AuthResponse(
            user=_user_response(user), session_token=token, expires_at=session.expires_at
        )
    finally:
        db.close()


@app.post("/auth/login", response_model=AuthResponse, tags=["Authentication"])
async def login_user(request: AuthRequest, response: Response):
    """Authenticate a user and start a new bearer/cookie session."""
    db = SessionLocal()
    try:
        repository = SQLiteIdentityRepository(db)
        try:
            normalized_email = _normalize_email(request.email)
            existing_user = db.query(User).filter_by(email=normalized_email).first()
            if not existing_user:
                raise HTTPException(
                    status_code=404,
                    detail="No registered account exists for this email. Please register first.",
                )
            user = repository.authenticate_user(normalized_email, request.password)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        if not user:
            raise HTTPException(status_code=401, detail="Invalid email or password")
        token, session = repository.create_session(user)
        _set_session_cookie(response, token)
        return AuthResponse(
            user=_user_response(user), session_token=token, expires_at=session.expires_at
        )
    finally:
        db.close()


@app.post("/auth/logout", tags=["Authentication"])
async def logout_user(
    response: Response,
    request: Request,
    authorization: Optional[str] = Header(default=None),
):
    """Revoke the current session token and clear the session cookie."""
    token = _extract_session_token(request, authorization)
    if token:
        db = SessionLocal()
        try:
            SQLiteIdentityRepository(db).revoke_session(token)
        finally:
            db.close()
    response.delete_cookie(SESSION_COOKIE_NAME)
    return {"message": "Logged out"}


@app.get("/auth/me", response_model=UserResponse, tags=["Authentication"])
async def get_me(current_user: User = Depends(require_current_user)):
    """Return the currently authenticated user."""
    return _user_response(current_user)


@app.get("/api/profile", response_model=UserResponse, tags=["Profile"])
async def get_profile(current_user: User = Depends(require_current_user)):
    """Return editable personal profile settings."""
    return _user_response(current_user)


@app.put("/api/profile", response_model=UserResponse, tags=["Profile"])
async def update_profile(payload: ProfileUpdate, current_user: User = Depends(require_current_user)):
    """Update display name, phone, timezone, linked calendar, and ordered presets."""
    db = SessionLocal()
    try:
        user = db.query(User).filter_by(id=current_user.id).one()
        user.display_name = payload.display_name.strip() if payload.display_name else None
        user.phone_number = payload.phone_number.strip() if payload.phone_number else None
        user.timezone_preference = payload.timezone_preference.strip() or "UTC"
        linked_labels = [label.strip() for label in payload.linked_calendar_labels if label.strip()]
        if not linked_labels and payload.linked_calendar_label:
            linked_labels = [payload.linked_calendar_label.strip()]
        user.linked_calendar_label = linked_labels[0] if linked_labels else None
        user.linked_calendar_labels = json.dumps(linked_labels)
        user.time_presets = json.dumps([preset.model_dump() for preset in payload.time_presets])
        db.add(user)
        db.commit()
        db.refresh(user)
        return _user_response(user)
    finally:
        db.close()


@app.get("/api/time-presets", response_model=list[TimePreset], tags=["Profile"])
async def list_time_presets(current_user: User = Depends(require_current_user)):
    """Return the current user's ordered time presets."""
    return _presets_for_user(current_user)


@app.get("/auth/oauth/{provider}", response_class=HTMLResponse, tags=["Authentication"])
async def oauth_login_placeholder(provider: str):
    """Advertise future app-login OAuth providers without mixing them with calendar linking."""
    if provider not in {"google", "microsoft"}:
        raise HTTPException(status_code=404, detail="Unsupported login provider")
    return _not_implemented_page(f"{provider.title()} app login")


def _allowed_weekdays_for(record: MeetingRequest) -> list[str]:
    """Decode allowed weekdays from the JSON column used by the prototype."""
    try:
        value = json.loads(record.allowed_weekdays or "[]")
        return value if isinstance(value, list) else []
    except json.JSONDecodeError:
        return []


def _allowed_windows_for(record: MeetingRequest) -> list[TimeWindow]:
    """Decode added availability windows, falling back to legacy weekday/hour fields."""
    try:
        value = json.loads(record.allowed_windows or "[]")
        if isinstance(value, list) and value:
            return [TimeWindow(**item) for item in value]
    except Exception:
        pass

    day_lookup = {"Mon": 0, "Tue": 1, "Wed": 2, "Thu": 3, "Fri": 4, "Sat": 5, "Sun": 6}
    return [
        TimeWindow(day=day_lookup[day], start=record.window_start, end=record.window_end)
        for day in _allowed_weekdays_for(record)
        if day in day_lookup
    ]


def _invitee_emails_for(record: MeetingRequest) -> list[str]:
    """Decode all invitee emails, falling back to the legacy single email column."""
    try:
        value = json.loads(record.invitee_emails or "[]")
        if isinstance(value, list) and value:
            return value
    except json.JSONDecodeError:
        pass
    return [record.invitee_email] if record.invitee_email else []


def _meeting_request_response(
    record: MeetingRequest, invite_token: Optional[str] = None
) -> MeetingRequestResponse:
    """Serialize a stored meeting request for the frontend."""
    return MeetingRequestResponse(
        id=record.id,
        title=record.title,
        invitee_email=record.invitee_email,
        invitee_emails=_invitee_emails_for(record),
        friend_ids=json.loads(record.friend_ids or "[]"),
        time_preset_id=record.time_preset_id,
        owner_calendar_label=record.owner_calendar_label,
        invitee_calendar_label=record.invitee_calendar_label,
        duration_minutes=record.duration_minutes,
        earliest_date=record.earliest_date,
        latest_date=record.latest_date,
        timezone=record.timezone,
        window_start=record.window_start,
        window_end=record.window_end,
        allowed_weekdays=_allowed_weekdays_for(record),
        allowed_windows=_allowed_windows_for(record),
        notes=record.notes,
        status=record.status,
        invite_url=f"/invite/{invite_token}" if invite_token else None,
        invite_expires_at=record.invite_expires_at,
        invite_opened_at=record.invite_opened_at,
        invite_accepted_at=record.invite_accepted_at,
        invite_declined_at=record.invite_declined_at,
        invitee_user_id=record.invitee_user_id,
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _audit_event(
    db: Session,
    request_id: str,
    action: str,
    actor_user_id: Optional[str] = None,
    details: Optional[dict] = None,
) -> RequestAuditEvent:
    """Append a lifecycle audit event for request traceability."""
    event = RequestAuditEvent(
        id=str(uuid.uuid4()),
        request_id=request_id,
        actor_user_id=actor_user_id,
        action=action,
        details=json.dumps(details or {}),
        created_at=datetime.utcnow(),
    )
    db.add(event)
    return event


def _issue_invite(record: MeetingRequest, db: Session, actor_user_id: str) -> str:
    """Create or replace the secure invite token for a meeting request."""
    token = secrets.token_urlsafe(32)
    record.invite_token_hash = _hash_invite_token(token)
    record.invite_expires_at = datetime.utcnow() + timedelta(days=INVITE_DURATION_DAYS)
    record.status = "sent"
    record.updated_at = datetime.utcnow()
    db.add(record)
    _audit_event(
        db,
        record.id,
        "invite_generated",
        actor_user_id,
        {"expires_at": record.invite_expires_at.isoformat()},
    )
    return token


def _request_visible_to_user(record: MeetingRequest, user: User) -> bool:
    """Return whether a user can see a request after authentication."""
    return (
        record.owner_user_id == user.id
        or record.invitee_user_id == user.id
        or user.email in _invitee_emails_for(record)
    )


def _get_visible_request_or_404(db: Session, request_id: str, user: User) -> MeetingRequest:
    """Fetch a request and enforce requester/invitee authorization."""
    record = db.query(MeetingRequest).filter_by(id=request_id).first()
    if not record or not _request_visible_to_user(record, user):
        raise HTTPException(status_code=404, detail="Meeting request not found")
    return record


def _requester_email_for(db: Session, record: MeetingRequest) -> str:
    requester = db.query(User).filter_by(id=record.owner_user_id).first()
    return requester.email if requester else "unknown requester"


def _get_invite_record_or_404(db: Session, token: str) -> MeetingRequest:
    """Resolve a raw invite token against its stored hash."""
    token_hash = _hash_invite_token(token)
    record = db.query(MeetingRequest).filter_by(invite_token_hash=token_hash).first()
    if not record or not record.invite_expires_at:
        raise HTTPException(status_code=404, detail="Invite not found")
    if record.invite_expires_at <= datetime.utcnow():
        raise HTTPException(status_code=410, detail="Invite has expired")
    return record


def _validate_calendar_label(calendar_label: Optional[str]) -> Optional[str]:
    """Validate a user-owned calendar slot label from the prototype account list."""
    if not calendar_label:
        return None
    normalized = calendar_label.strip()
    if normalized not in {"a", "b"}:
        raise HTTPException(status_code=400, detail="Calendar selection must be account 'a' or 'b'")
    return normalized


def _validate_meeting_request_payload(payload: MeetingRequestCreate) -> None:
    """Validate the request fields that are currently persisted by SQLite."""
    if not payload.title.strip():
        raise HTTPException(status_code=400, detail="Meeting title is required")
    emails = payload.invitee_emails or ([payload.invitee_email] if payload.invitee_email else [])
    if not emails:
        raise HTTPException(status_code=400, detail="At least one invitee email is required")
    try:
        [_normalize_email(email) for email in emails]
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="A valid invitee email is required") from exc
    if payload.duration_minutes not in {15, 30, 45, 60, 90, 120}:
        raise HTTPException(status_code=400, detail="Duration must be a supported meeting length")
    try:
        earliest = datetime.fromisoformat(payload.earliest_date)
        latest = datetime.fromisoformat(payload.latest_date)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Dates must use YYYY-MM-DD format") from exc
    if latest < earliest:
        raise HTTPException(status_code=400, detail="Latest date must be on or after earliest date")
    if payload.window_start >= payload.window_end:
        raise HTTPException(status_code=400, detail="Start time must be before end time")
    _validate_calendar_label(payload.owner_calendar_label)
    _validate_calendar_label(payload.invitee_calendar_label)


@app.get("/api/requests", response_model=list[MeetingRequestResponse], tags=["Meeting requests"])
async def list_meeting_requests(current_user: User = Depends(require_current_user)):
    """List meeting requests visible to the current requester or invitee."""
    db = SessionLocal()
    try:
        records = db.query(MeetingRequest).order_by(MeetingRequest.created_at.desc()).all()
        return [
            _meeting_request_response(record)
            for record in records
            if _request_visible_to_user(record, current_user)
        ]
    finally:
        db.close()


@app.post("/api/requests", response_model=MeetingRequestResponse, tags=["Meeting requests"])
async def create_meeting_request(
    payload: MeetingRequestCreate, current_user: User = Depends(require_current_user)
):
    """Create a SQLite-backed request draft and secure invite link."""
    _validate_meeting_request_payload(payload)
    now = datetime.utcnow()
    normalized_invitees = [_normalize_email(email) for email in (payload.invitee_emails or [payload.invitee_email])]
    owner_calendar_label = _validate_calendar_label(payload.owner_calendar_label)
    invitee_calendar_label = _validate_calendar_label(payload.invitee_calendar_label)
    record = MeetingRequest(
        id=str(uuid.uuid4()),
        owner_user_id=current_user.id,
        title=payload.title.strip(),
        invitee_email=normalized_invitees[0],
        invitee_emails=json.dumps(normalized_invitees),
        friend_ids=json.dumps(payload.friend_ids),
        time_preset_id=payload.time_preset_id,
        owner_calendar_label=owner_calendar_label,
        invitee_calendar_label=invitee_calendar_label,
        duration_minutes=payload.duration_minutes,
        earliest_date=payload.earliest_date,
        latest_date=payload.latest_date,
        timezone=payload.timezone.strip() or "UTC",
        window_start=payload.window_start,
        window_end=payload.window_end,
        allowed_weekdays=json.dumps(payload.allowed_weekdays),
        allowed_windows=json.dumps([window.model_dump() for window in payload.allowed_windows]),
        notes=payload.notes.strip() if payload.notes else None,
        status="draft",
        created_at=now,
        updated_at=now,
    )
    db = SessionLocal()
    try:
        if owner_calendar_label and not DatabaseService.get_account(owner_calendar_label, db, current_user.id):
            raise HTTPException(status_code=400, detail="Selected calendar is not linked to your account")
        db.add(record)
        db.flush()
        _audit_event(db, record.id, "created", current_user.id)
        invite_token = _issue_invite(record, db, current_user.id)
        db.commit()
        db.refresh(record)
        return _meeting_request_response(record, invite_token)
    finally:
        db.close()


@app.get("/api/requests/{request_id}", response_model=MeetingRequestResponse, tags=["Meeting requests"])
async def get_meeting_request(
    request_id: str, current_user: User = Depends(require_current_user)
):
    """Return one request visible to the current requester or invitee."""
    db = SessionLocal()
    try:
        record = _get_visible_request_or_404(db, request_id, current_user)
        return _meeting_request_response(record)
    finally:
        db.close()


@app.post("/api/requests/{request_id}/calendar", response_model=MeetingRequestResponse, tags=["Meeting requests"])
async def select_request_calendar(
    request_id: str,
    payload: RequestCalendarSelection,
    current_user: User = Depends(require_current_user),
):
    """Select one linked calendar slot for the current user's side of a request."""
    calendar_label = _validate_calendar_label(payload.calendar_label)
    db = SessionLocal()
    try:
        record = _get_visible_request_or_404(db, request_id, current_user)
        if not DatabaseService.get_account(calendar_label, db, current_user.id):
            raise HTTPException(status_code=400, detail="Selected calendar is not linked to your account")

        if record.owner_user_id == current_user.id:
            record.owner_calendar_label = calendar_label
            role = "owner"
        else:
            if current_user.email not in _invitee_emails_for(record) and record.invitee_user_id != current_user.id:
                raise HTTPException(status_code=403, detail="This request is for a different invitee")
            record.invitee_user_id = current_user.id
            record.invitee_calendar_label = calendar_label
            role = "invitee"

        record.updated_at = datetime.utcnow()
        if record.status in {"opened", "sent", "awaiting_calendar_connection"}:
            record.status = "ready_for_matching" if record.owner_calendar_label and record.invitee_calendar_label else "awaiting_calendar_connection"
        _audit_event(db, record.id, "calendar_selected", current_user.id, {"role": role, "calendar_label": calendar_label})
        db.add(record)
        db.commit()
        db.refresh(record)
        return _meeting_request_response(record)
    finally:
        db.close()


@app.post("/api/requests/{request_id}/invite", response_model=MeetingRequestResponse, tags=["Meeting requests"])
async def regenerate_request_invite(
    request_id: str, current_user: User = Depends(require_current_user)
):
    """Regenerate a hard-to-guess invite link for a requester-owned request."""
    db = SessionLocal()
    try:
        record = db.query(MeetingRequest).filter_by(id=request_id, owner_user_id=current_user.id).first()
        if not record:
            raise HTTPException(status_code=404, detail="Meeting request not found")
        if record.status in {"agreed", "cancelled", "expired"}:
            raise HTTPException(status_code=400, detail="Cannot regenerate invite for this request status")
        invite_token = _issue_invite(record, db, current_user.id)
        db.commit()
        db.refresh(record)
        return _meeting_request_response(record, invite_token)
    finally:
        db.close()


@app.get("/api/requests/{request_id}/audit", response_model=list[AuditEventResponse], tags=["Meeting requests"])
async def list_request_audit_events(
    request_id: str, current_user: User = Depends(require_current_user)
):
    """Return lifecycle audit events for a visible request."""
    db = SessionLocal()
    try:
        _get_visible_request_or_404(db, request_id, current_user)
        events = (
            db.query(RequestAuditEvent)
            .filter_by(request_id=request_id)
            .order_by(RequestAuditEvent.created_at.asc())
            .all()
        )
        return [
            AuditEventResponse(
                id=event.id,
                request_id=event.request_id,
                actor_user_id=event.actor_user_id,
                action=event.action,
                details=event.details,
                created_at=event.created_at,
            )
            for event in events
        ]
    finally:
        db.close()


@app.get("/api/invites/{token}", response_model=InvitePreviewResponse, tags=["Meeting requests"])
async def preview_invite(token: str):
    """Return non-sensitive request details for an unexpired invite token."""
    db = SessionLocal()
    try:
        record = _get_invite_record_or_404(db, token)
        if not record.invite_opened_at:
            record.invite_opened_at = datetime.utcnow()
            if record.status == "sent":
                record.status = "opened"
            record.updated_at = datetime.utcnow()
            _audit_event(db, record.id, "opened", details={"source": "invite_preview"})
            db.commit()
            db.refresh(record)
        return InvitePreviewResponse(
            request_id=record.id,
            title=record.title,
            requester_email=_requester_email_for(db, record),
            invitee_email=record.invitee_email,
            duration_minutes=record.duration_minutes,
            earliest_date=record.earliest_date,
            latest_date=record.latest_date,
            timezone=record.timezone,
            window_start=record.window_start,
            window_end=record.window_end,
            allowed_weekdays=_allowed_weekdays_for(record),
            allowed_windows=_allowed_windows_for(record),
            status=record.status,
            expires_at=record.invite_expires_at,
        )
    finally:
        db.close()


@app.post("/api/invites/{token}/accept", response_model=InviteActionResponse, tags=["Meeting requests"])
async def accept_invite(token: str, current_user: User = Depends(require_current_user)):
    """Accept an invite when the logged-in user's email matches the invitee."""
    db = SessionLocal()
    try:
        record = _get_invite_record_or_404(db, token)
        if current_user.email not in _invitee_emails_for(record):
            raise HTTPException(status_code=403, detail="This invite is for a different email address")
        if record.invite_declined_at:
            raise HTTPException(status_code=400, detail="This invite was already declined")
        now = datetime.utcnow()
        record.invitee_user_id = current_user.id
        record.invite_accepted_at = now
        record.status = "awaiting_calendar_connection"
        record.updated_at = now
        _audit_event(db, record.id, "accepted", current_user.id)
        db.commit()
        return InviteActionResponse(
            request_id=record.id,
            status=record.status,
            message="Invite accepted. Connect your calendar before matching.",
        )
    finally:
        db.close()


@app.post("/api/invites/{token}/decline", response_model=InviteActionResponse, tags=["Meeting requests"])
async def decline_invite(token: str, current_user: User = Depends(require_current_user)):
    """Decline an invite when the logged-in user's email matches the invitee."""
    db = SessionLocal()
    try:
        record = _get_invite_record_or_404(db, token)
        if current_user.email not in _invitee_emails_for(record):
            raise HTTPException(status_code=403, detail="This invite is for a different email address")
        now = datetime.utcnow()
        record.invitee_user_id = current_user.id
        record.invite_declined_at = now
        record.status = "disagreed"
        record.updated_at = now
        _audit_event(db, record.id, "declined", current_user.id)
        db.commit()
        return InviteActionResponse(
            request_id=record.id,
            status=record.status,
            message="Invite declined.",
        )
    finally:
        db.close()


def _friend_response(record: FriendRequest) -> FriendRequestResponse:
    return FriendRequestResponse(
        id=record.id,
        requester_email=record.requester_email,
        recipient_email=record.recipient_email,
        status=record.status,
        created_at=record.created_at,
        responded_at=record.responded_at,
    )


@app.get("/api/friends", response_model=list[FriendRequestResponse], tags=["Friends"])
async def list_friends(current_user: User = Depends(require_current_user)):
    """List pending and accepted email-based friend relationships."""
    db = SessionLocal()
    try:
        records = (
            db.query(FriendRequest)
            .filter(
                (FriendRequest.requester_user_id == current_user.id)
                | (FriendRequest.recipient_email == current_user.email)
                | (FriendRequest.recipient_user_id == current_user.id)
            )
            .order_by(FriendRequest.created_at.desc())
            .all()
        )
        return [_friend_response(record) for record in records]
    finally:
        db.close()


@app.post("/api/friends", response_model=FriendRequestResponse, tags=["Friends"])
async def send_friend_request(payload: FriendRequestCreate, current_user: User = Depends(require_current_user)):
    """Send a friend request to an email address."""
    recipient_email = _normalize_email(payload.recipient_email)
    if recipient_email == current_user.email:
        raise HTTPException(status_code=400, detail="You cannot friend yourself")
    db = SessionLocal()
    try:
        recipient = db.query(User).filter_by(email=recipient_email).first()
        record = FriendRequest(
            id=str(uuid.uuid4()),
            requester_user_id=current_user.id,
            requester_email=current_user.email,
            recipient_email=recipient_email,
            recipient_user_id=recipient.id if recipient else None,
            status="pending",
            created_at=datetime.utcnow(),
        )
        db.add(record)
        db.commit()
        db.refresh(record)
        return _friend_response(record)
    finally:
        db.close()


@app.post("/api/friends/{friend_request_id}/accept", response_model=FriendRequestResponse, tags=["Friends"])
async def accept_friend_request(friend_request_id: str, current_user: User = Depends(require_current_user)):
    """Accept a friend request addressed to the current user's email."""
    db = SessionLocal()
    try:
        record = db.query(FriendRequest).filter_by(id=friend_request_id).first()
        if not record or record.recipient_email != current_user.email:
            raise HTTPException(status_code=404, detail="Friend request not found")
        record.status = "accepted"
        record.recipient_user_id = current_user.id
        record.responded_at = datetime.utcnow()
        db.add(record)
        db.commit()
        db.refresh(record)
        return _friend_response(record)
    finally:
        db.close()


@app.post("/api/demo/options", response_model=MatchingOptionsResponse, tags=["Matching"])
async def demo_matching_options(request: DemoMatchingRequest):
    """Run matching against two demo calendars, separate from personal connections."""
    try:
        matching_result = find_matching_options(
            time_min=request.time_min,
            time_max=request.time_max,
            duration_minutes=request.duration_minutes,
            busy_periods=_merge_busy_periods(request.busy_a + request.busy_b),
            allowed_windows=request.allowed_windows,
            max_options=request.max_options,
        )
        return MatchingOptionsResponse(
            duration_minutes=matching_result.duration_minutes,
            slot_granularity_minutes=matching_result.slot_granularity_minutes,
            options=[MeetingOption(**option.__dict__) for option in matching_result.options],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _safe_oauth_return_path(return_to: Optional[str]) -> str:
    """Allow OAuth callbacks to return only to in-app relative paths."""
    if not return_to:
        return "/account"
    cleaned = return_to.strip()
    if not cleaned.startswith("/") or cleaned.startswith("//") or "\\" in cleaned:
        return "/account"
    return cleaned


@app.get("/oauth/start", tags=["OAuth"])
async def oauth_start(
    account_label: Optional[str] = Query(
        None, description="Optional profile calendar label"
    ),
    request_id: Optional[str] = Query(
        default=None,
        description="Visible meeting request to mark ready when this calendar connects",
    ),
    current_user: User = Depends(require_current_user),
):
    """
    Start OAuth flow
    Redirects to Google consent screen
    """
    _validate_config()  # Validate config before using

    if not account_label:
        account_label = f"cal_{secrets.token_urlsafe(6)}"
    if not account_label.replace("_", "").replace("-", "").isalnum():
        raise HTTPException(
            status_code=400,
            detail="account_label may contain only letters, numbers, hyphens, and underscores",
        )

    db = SessionLocal()
    try:
        request_role = None
        safe_return_path = _safe_oauth_return_path(return_to)
        if request_id:
            record = _get_visible_request_or_404(db, request_id, current_user)
            if record.owner_user_id == current_user.id:
                request_role = "owner"
            else:
                request_role = "invitee"
                record.invitee_user_id = current_user.id
                db.add(record)
            if not return_to:
                safe_return_path = f"/requests/{request_id}"

        oauth_state = OAuthState(
            state=secrets.token_urlsafe(32),
            user_id=current_user.id,
            account_label=account_label,
            return_path=safe_return_path,
            request_id=request_id,
            request_role=request_role,
            expires_at=datetime.utcnow() + timedelta(minutes=15),
        )
        db.add(oauth_state)
        db.commit()
    finally:
        db.close()

    auth_url = OAuthHandler.get_authorization_url(oauth_state.state)
    return RedirectResponse(url=auth_url)


@app.get("/oauth/callback", tags=["OAuth"])
async def oauth_callback(code: str = Query(...), state: str = Query(...)):
    """
    OAuth callback endpoint
    Exchanges authorization code for tokens and stores them
    """
    _validate_config()  # Validate config before using

    account_label = state

    try:
        # Exchange code for tokens
        tokens = await OAuthHandler.exchange_code_for_tokens(code)
        access_token = tokens.get("access_token")
        refresh_token = tokens.get("refresh_token")

        if not refresh_token:
            logger.warning(
                "No refresh token received. Ensure access_type=offline and prompt=consent"
            )
            raise HTTPException(
                status_code=400,
                detail="Failed to obtain refresh token. Ensure you're allowing offline access.",
            )

        # Get user info from ID token or by making an API call
        # For simplicity, we'll decode the ID token
        id_token = tokens.get("id_token", "")
        if id_token:
            # Simple JWT decode (without verification for now)
            import base64

            parts = id_token.split(".")
            if len(parts) >= 2:
                payload = parts[1]
                # Add padding if necessary
                padding = 4 - (len(payload) % 4)
                if padding != 4:
                    payload += "=" * padding
                user_data = json.loads(base64.urlsafe_b64decode(payload))
                google_sub = user_data.get("sub", "")
                email = user_data.get("email", "")
            else:
                google_sub = ""
                email = ""
        else:
            # no id_token because openid scope might be missing
            google_sub = ""
            email = ""

        # if we still don't have a sub, try userinfo endpoint as fallback
        if not google_sub and access_token:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        "https://openidconnect.googleapis.com/v1/userinfo",
                        headers={"Authorization": f"Bearer {access_token}"},
                    )
                    resp.raise_for_status()
                    info = resp.json()
                    google_sub = info.get("sub", "")
                    email = info.get("email", "")
            except Exception as e:
                logger.warning(f"Failed to fetch userinfo: {e}")

        # if we still have no sub, abort - we need it for unique key
        if not google_sub:
            raise HTTPException(
                status_code=400,
                detail="Unable to determine user identifier (sub); ensure OpenID scope is granted.",
            )

        # Resolve the one-time OAuth state to the authenticated user and slot.
        db = SessionLocal()
        try:
            oauth_state = db.query(OAuthState).filter_by(state=state).first()
            if (
                not oauth_state
                or oauth_state.used_at is not None
                or oauth_state.expires_at <= datetime.utcnow()
            ):
                raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")
            oauth_state.used_at = datetime.utcnow()
            account_label = oauth_state.account_label
            return_path = _safe_oauth_return_path(oauth_state.return_path)

            # remove any stale rows where sub is empty (was causing duplicates)
            db.query(GoogleAccount).filter(GoogleAccount.google_sub == "").delete()
            db.commit()

            account_obj = DatabaseService.save_account(
                account_label=account_label,
                owner_user_id=oauth_state.user_id,
                google_sub=google_sub,
                email=email,
                refresh_token=refresh_token,
                db=db,
            )
            logger.info(f"Account '{account_label}' ({email}) saved successfully")

            if oauth_state.request_id:
                request_record = db.query(MeetingRequest).filter_by(id=oauth_state.request_id).first()
                if request_record:
                    role = oauth_state.request_role or ("owner" if request_record.owner_user_id == oauth_state.user_id else "invitee")
                    if role == "owner":
                        request_record.owner_calendar_label = account_label
                    else:
                        request_record.invitee_user_id = oauth_state.user_id
                        request_record.invitee_calendar_label = account_label
                    request_record.status = (
                        "ready_for_matching"
                        if request_record.owner_calendar_label and request_record.invitee_calendar_label
                        else "awaiting_calendar_connection"
                    )
                    request_record.updated_at = datetime.utcnow()
                    _audit_event(
                        db,
                        request_record.id,
                        "calendar_connected",
                        oauth_state.user_id,
                        {"role": role, "calendar_label": account_label},
                    )
                    db.add(request_record)
                    db.commit()

            # fetch and store busy for next 30 days
            try:
                now_dt = datetime.utcnow()
                later_dt = now_dt + timedelta(days=30)
                busy = await GoogleCalendarClient.get_freebusy(
                    access_token, now_dt.isoformat() + "Z", later_dt.isoformat() + "Z"
                )
                account_obj.cached_busy = json.dumps(busy)
                db.add(account_obj)
                db.commit()
            except Exception as e:
                logger.warning(f"Failed to cache busy data for {account_label}: {e}")

        finally:
            db.close()

        # Redirect back to the profile page so users manage all calendar accounts there.
        redirect_url = f"/profile?account_label={account_label}&email={email}"
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        raise HTTPException(status_code=400, detail=f"OAuth error: {str(e)}")


@app.get(
    "/freebusy/{account_label}", response_model=FreeBusyResponse, tags=["Calendar"]
)
async def get_freebusy_account(
    account_label: str = FastAPIPath(..., description="Profile calendar account label"),
    time_min: str = Query(
        ..., description="Start time (RFC 3339, e.g., 2026-02-28T00:00:00Z)"
    ),
    time_max: str = Query(
        ..., description="End time (RFC 3339, e.g., 2026-03-10T00:00:00Z)"
    ),
    current_user: User = Depends(require_current_user),
):
    """
    Get free/busy information for a specific account
    """
    logger.debug(f"get_freebusy_account called for account '{account_label}'")
    db = SessionLocal()
    try:
        # Retrieve account
        account = DatabaseService.get_account(account_label, db, current_user.id)
        if not account:
            logger.warning(f"Account '{account_label}' not found in database")
            raise HTTPException(
                status_code=404, detail=f"Account '{account_label}' not found"
            )
        logger.debug(f"Account '{account_label}' ({account.email}) retrieved")

        # Decrypt refresh token
        try:
            refresh_token = get_token_manager().decrypt(account.refresh_token)
            logger.debug(f"Refresh token decrypted for {account_label}")
        except ValueError as e:
            logger.error(f"Failed to decrypt token for {account_label}: {e}")
            raise HTTPException(status_code=500, detail="Token decryption failed")

        # Get new access token
        try:
            logger.debug(f"Refreshing access token for {account_label}")
            access_token = await OAuthHandler.refresh_access_token(refresh_token)
            logger.debug(f"Access token refreshed for {account_label}")
        except Exception as e:
            logger.error(
                f"Token refresh failed for {account_label}: {type(e).__name__}: {e}"
            )
            raise HTTPException(
                status_code=401, detail="Failed to refresh access token"
            )

        # Get free/busy data
        try:
            logger.debug(
                f"Fetching free/busy for {account_label} from {time_min} to {time_max}"
            )
            freebusy_data = await GoogleCalendarClient.get_freebusy(
                access_token, time_min, time_max
            )
            logger.debug(
                f"Got free/busy for {account_label}: {len(freebusy_data.get('busy', []))} busy periods"
            )
        except Exception as e:
            logger.error(
                f"Failed to get free/busy data for {account_label}: {type(e).__name__}: {e}",
                exc_info=DEBUG,
            )
            raise HTTPException(
                status_code=500, detail="Failed to fetch free/busy data"
            )

        # Convert busy periods to response format
        busy_periods = [
            BusyPeriod(start=period["start"], end=period["end"])
            for period in freebusy_data.get("busy", [])
        ]
        logger.info(
            f"FreeBusyResponse for {account_label} ({account.email}): {len(busy_periods)} busy periods"
        )

        return FreeBusyResponse(
            account_label=account_label,
            email=account.email,
            busy=busy_periods,
        )

    finally:
        db.close()


def _resolve_pair_account_labels(
    accounts: list[GoogleAccount], selected_label: Optional[str] = None
) -> tuple[str, str]:
    """Resolve the selected profile calendar and a second prototype comparison account."""
    labels = [_display_account_label(account) for account in accounts]
    if not labels:
        raise HTTPException(
            status_code=404,
            detail="Connect a calendar account in your profile first",
        )

    primary = selected_label or labels[0]
    if primary not in labels:
        raise HTTPException(status_code=404, detail=f"Account '{primary}' not found")

    secondary = next((label for label in labels if label != primary), None)
    if not secondary:
        raise HTTPException(
            status_code=404,
            detail="A second participant calendar is needed before live matching can compare availability",
        )
    return primary, secondary


@app.get("/pair", response_model=PairedFreeBusyResponse, tags=["Calendar"])
async def get_freebusy_pair(
    time_min: str = Query(
        ..., description="Start time (RFC 3339, e.g., 2026-02-28T00:00:00Z)"
    ),
    time_max: str = Query(
        ..., description="End time (RFC 3339, e.g., 2026-03-10T00:00:00Z)"
    ),
    account_label: Optional[str] = Query(
        None, description="Selected profile calendar account label"
    ),
    current_user: User = Depends(require_current_user),
):
    """
    Get free/busy information for both accounts and combine results
    Shows when at least one person is busy
    """
    logger.info(
        f"get_freebusy_pair called with time_min={time_min}, time_max={time_max}"
    )
    db = SessionLocal()
    try:
        accounts = DatabaseService.get_all_accounts(db, current_user.id)
        account_a_label, account_b_label = _resolve_pair_account_labels(accounts, account_label)
        account_a = DatabaseService.get_account(account_a_label, db, current_user.id)
        account_b = DatabaseService.get_account(account_b_label, db, current_user.id)
        logger.debug(
            f"Selected accounts: {account_a.email if account_a else 'None'}, {account_b.email if account_b else 'None'}"
        )

        # Get free/busy for both; wrap so we can log per-account failures
        try:
            freebusy_a = await get_freebusy_account(
                account_label=account_a_label, time_min=time_min, time_max=time_max, current_user=current_user
            )
            logger.info(
                f"Fetched freebusy for account a: {len(freebusy_a.busy)} busy periods"
            )
            logger.debug(f"Account abusy periods: {freebusy_a.busy}")
        except HTTPException as e:
            logger.error("error fetching freebusy for account a: %s", e.detail)
            raise
        except Exception as e:
            logger.error("unexpected error fetching freebusy for account a", exc_info=e)
            raise HTTPException(
                status_code=500, detail="Failed to retrieve busy for account a"
            )

        try:
            freebusy_b = await get_freebusy_account(
                account_label=account_b_label, time_min=time_min, time_max=time_max, current_user=current_user
            )
            logger.info(
                f"Fetched freebusy for account b: {len(freebusy_b.busy)} busy periods"
            )
            logger.debug(f"Account b busy periods: {freebusy_b.busy}")
        except HTTPException as e:
            logger.error("error fetching freebusy for account b: %s", e.detail)
            raise
        except Exception as e:
            logger.error("unexpected error fetching freebusy for account b", exc_info=e)
            raise HTTPException(
                status_code=500, detail="Failed to retrieve busy for account b"
            )

        # Combine busy periods (merge overlapping periods)
        combined = _merge_busy_periods(freebusy_a.busy + freebusy_b.busy)
        logger.debug(f"Combined busy periods: {combined}")

        return PairedFreeBusyResponse(
            account_a=freebusy_a,
            account_b=freebusy_b,
            combined_busy=combined,
        )

    except HTTPException as e:
        # re-raise after logging
        logger.info(f"get_freebusy_pair returning HTTP {e.status_code}: {e.detail}")
        raise
    except Exception as e:
        logger.error("Unhandled error in get_freebusy_pair", exc_info=e)
        raise
    finally:
        db.close()


@app.post("/matching/options", response_model=MatchingOptionsResponse, tags=["Matching"])
async def get_matching_options(
    request: MatchingOptionsRequest,
    current_user: User = Depends(require_current_user),
):
    """Return the best meeting options for the two connected calendar accounts."""
    db = SessionLocal()
    try:
        accounts = DatabaseService.get_all_accounts(db, current_user.id)
        account_a_label, account_b_label = _resolve_pair_account_labels(accounts, request.account_label)

        freebusy_a = await get_freebusy_account(
            account_label=account_a_label,
            time_min=request.time_min,
            time_max=request.time_max,
            current_user=current_user,
        )
        freebusy_b = await get_freebusy_account(
            account_label=account_b_label,
            time_min=request.time_min,
            time_max=request.time_max,
            current_user=current_user,
        )
        busy_periods = _merge_busy_periods(freebusy_a.busy + freebusy_b.busy)

        matching_result = find_matching_options(
            time_min=request.time_min,
            time_max=request.time_max,
            duration_minutes=request.duration_minutes,
            busy_periods=busy_periods,
            allowed_windows=request.allowed_windows,
            max_options=request.max_options,
        )
        return MatchingOptionsResponse(
            duration_minutes=matching_result.duration_minutes,
            slot_granularity_minutes=matching_result.slot_granularity_minutes,
            options=[
                MeetingOption(**option.__dict__) for option in matching_result.options
            ],
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        db.close()


@app.get("/accounts", tags=["Admin"])
async def list_accounts(current_user: User = Depends(require_current_user)):
    """List all stored accounts (email and label only, no tokens)"""
    db = SessionLocal()
    try:
        accounts = DatabaseService.get_all_accounts(db, current_user.id)
        return [
            {
                "account_label": _display_account_label(acc),
                "email": acc.email,
                "google_sub": acc.google_sub,
                "created_at": acc.created_at.isoformat(),
                "cached_busy": acc.cached_busy,
                "selected_as": "",  # this field is not stored but can be used by frontend to mark which account is selected for display
            }
            for acc in accounts
        ]
    finally:
        db.close()


@app.post("/accounts/select", tags=["Admin"])
async def select_account(
    account_label: str = Query(
        ...,
        description="Account label to mark as selected for legacy frontend display purposes",
    ),
    selected_as: str = Query(..., description="Legacy selection target"),
    current_user: User = Depends(require_current_user),
):
    """
    Mark an account as selected for display purposes
    This is a simple endpoint to allow the frontend to indicate which account is currently selected for display
    The selection state is not persisted in the database, but can be used by the frontend to manage UI state
    """
    logger.info(
        f"select_account called with account_label={account_label}, selected_as={selected_as}"
    )
    if not selected_as.strip():
        raise HTTPException(status_code=400, detail="selected_as cannot be empty")
    # Validate that the selected account belongs to the current user.
    db = SessionLocal()
    try:
        accounts = DatabaseService.get_all_accounts(db, current_user.id)
        for acc in accounts:
            if _display_account_label(acc) == account_label:
                logger.info(f"Account '{account_label}' marked as selected for display")
                return {"message": f"Account '{account_label}' selected for display"}
        logger.warning(f"Account '{account_label}' not found to select")
        raise HTTPException(
            status_code=404, detail=f"Account '{account_label}' not found"
        )
    finally:
        db.close()


# ============================================================================
# HELPER FUNCTIONS
# ============================================================================


def _merge_busy_periods(periods: list[BusyPeriod]) -> list[BusyPeriod]:
    """
    Merge overlapping busy periods

    Args:
        periods: List of busy periods

    Returns:
        List of merged non-overlapping periods
    """
    if not periods:
        return []

    # Convert to tuples and sort
    time_periods = sorted([(p.start, p.end) for p in periods])

    merged = []
    current_start, current_end = time_periods[0]

    for start, end in time_periods[1:]:
        # Check if periods overlap or are adjacent
        if start <= current_end:
            current_end = max(current_end, end)
        else:
            merged.append(BusyPeriod(start=current_start, end=current_end))
            current_start, current_end = start, end

    merged.append(BusyPeriod(start=current_start, end=current_end))
    return merged


if __name__ == "__main__":
    import uvicorn

    host = os.getenv("HOST", "127.0.0.1")
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run(app, host=host, port=port)
