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
from sqlalchemy import create_engine, Column, String, DateTime, text
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
    )  # 'a' or 'b' to indicate which slot this account is selected for display as


class User(Base):
    """First-party application user for the authenticated MVP foundation."""

    __tablename__ = "users"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    email = Column(String, nullable=False, unique=True, index=True)
    display_name = Column(String, nullable=True)
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
    created_at = Column(DateTime, default=datetime.utcnow)
    expires_at = Column(DateTime, nullable=False)
    used_at = Column(DateTime, nullable=True)


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


_run_lightweight_migrations()


# ============================================================================
# APPLICATION AUTHENTICATION
# ============================================================================

SESSION_COOKIE_NAME = "calendar_matching_session"
SESSION_DURATION_DAYS = int(os.getenv("SESSION_DURATION_DAYS", "14"))
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


def _extract_session_token(request: Request, authorization: Optional[str]) -> Optional[str]:
    """Read a session token from Authorization: Bearer or the HTTP-only cookie."""
    if authorization:
        scheme, _, value = authorization.partition(" ")
        if scheme.lower() == "bearer" and value:
            return value.strip()
    return request.cookies.get(SESSION_COOKIE_NAME)


def _storage_account_label(user_id: str, account_label: str) -> str:
    """Map a user-owned slot label to the legacy single-column account key."""
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


class AuthRequest(BaseModel):
    email: str
    password: str


class RegisterRequest(AuthRequest):
    display_name: Optional[str] = None


class UserResponse(BaseModel):
    id: str
    email: str
    display_name: Optional[str] = None
    created_at: datetime


class AuthResponse(BaseModel):
    user: UserResponse
    session_token: str
    expires_at: datetime


class FreeBusyResponse(BaseModel):
    account_label: str
    email: str
    busy: list[BusyPeriod]


class PairedFreeBusyResponse(BaseModel):
    account_a: FreeBusyResponse
    account_b: FreeBusyResponse
    combined_busy: list[BusyPeriod]


class TimeWindow(BaseModel):
    day: int
    start: str
    end: str


class MatchingOptionsRequest(BaseModel):
    time_min: str
    time_max: str
    duration_minutes: int = 30
    allowed_windows: list[TimeWindow] = Field(default_factory=list)
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


def _current_user_from_token(token: Optional[str]) -> Optional[User]:
    """Return a user for a session token, or None when absent/invalid."""
    if not token:
        return None

    db = SessionLocal()
    try:
        user = SQLiteIdentityRepository(db).get_user_by_session_token(token)
        if user:
            db.expunge(user)
        return user
    finally:
        db.close()


def _current_user_from_request(request: Request) -> Optional[User]:
    """Return the current cookie-authenticated user for page routing."""
    return _current_user_from_token(request.cookies.get(SESSION_COOKIE_NAME))


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Serve the app shell only to authenticated users."""
    if not _current_user_from_request(request):
        return RedirectResponse(url="/login", status_code=303)

    template_path = SysPath(__file__).parent / "static" / "html" / "home.html"
    return HTMLResponse(content=template_path.read_text(), status_code=200)


@app.get("/login", response_class=HTMLResponse)
async def login_page(request: Request):
    """Serve the standalone login page for unauthenticated users."""
    if _current_user_from_request(request):
        return RedirectResponse(url="/", status_code=303)

    template_path = SysPath(__file__).parent / "static" / "html" / "login.html"
    return HTMLResponse(content=template_path.read_text(), status_code=200)


def _user_response(user: User) -> UserResponse:
    """Serialize a user without credentials."""
    return UserResponse(
        id=user.id,
        email=user.email,
        display_name=user.display_name,
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
            user = repository.authenticate_user(request.email, request.password)
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


@app.get("/oauth/start", tags=["OAuth"])
async def oauth_start(
    account_label: str = Query(..., description="Account label: 'a' or 'b'"),
    current_user: User = Depends(require_current_user),
):
    """
    Start OAuth flow
    Redirects to Google consent screen
    """
    _validate_config()  # Validate config before using

    if account_label not in ["a", "b"]:
        raise HTTPException(status_code=400, detail="account_label must be 'a' or 'b'")

    db = SessionLocal()
    try:
        oauth_state = OAuthState(
            state=secrets.token_urlsafe(32),
            user_id=current_user.id,
            account_label=account_label,
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

        # redirect back to home with params for UI display
        redirect_url = f"/?account_label={account_label}&email={email}"
        return RedirectResponse(url=redirect_url)

    except Exception as e:
        logger.error(f"OAuth callback error: {e}")
        raise HTTPException(status_code=400, detail=f"OAuth error: {str(e)}")


@app.get(
    "/freebusy/{account_label}", response_model=FreeBusyResponse, tags=["Calendar"]
)
async def get_freebusy_account(
    account_label: str = FastAPIPath(..., description="Account label: 'a' or 'b'"),
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
    if account_label not in ["a", "b"]:
        raise HTTPException(status_code=400, detail="account_label must be 'a' or 'b'")

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


@app.get("/pair", response_model=PairedFreeBusyResponse, tags=["Calendar"])
async def get_freebusy_pair(
    time_min: str = Query(
        ..., description="Start time (RFC 3339, e.g., 2026-02-28T00:00:00Z)"
    ),
    time_max: str = Query(
        ..., description="End time (RFC 3339, e.g., 2026-03-10T00:00:00Z)"
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
    logger.debug(f"Account A: {DatabaseService.get_account('a', db, current_user.id)}")
    logger.debug(f"Account B: {DatabaseService.get_account('b', db, current_user.id)}")
    try:
        # Get both accounts
        account_a = DatabaseService.get_account("a", db, current_user.id)
        account_b = DatabaseService.get_account("b", db, current_user.id)
        logger.debug(
            f"Account A: {account_a.email if account_a else 'None'}, Account B: {account_b.email if account_b else 'None'}"
        )

        if not account_a or not account_b:
            logger.warning(
                "one or both accounts missing: a=%s b=%s",
                bool(account_a),
                bool(account_b),
            )
            raise HTTPException(
                status_code=404,
                detail="Both account 'a' and 'b' must be configured",
            )

        # Get free/busy for both; wrap so we can log per-account failures
        try:
            freebusy_a = await get_freebusy_account(
                account_label="a", time_min=time_min, time_max=time_max, current_user=current_user
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
                account_label="b", time_min=time_min, time_max=time_max, current_user=current_user
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
        account_a = DatabaseService.get_account("a", db, current_user.id)
        account_b = DatabaseService.get_account("b", db, current_user.id)
        if not account_a or not account_b:
            raise HTTPException(
                status_code=404,
                detail="Both account 'a' and 'b' must be configured before matching",
            )

        freebusy_a = await get_freebusy_account(
            account_label="a",
            time_min=request.time_min,
            time_max=request.time_max,
            current_user=current_user,
        )
        freebusy_b = await get_freebusy_account(
            account_label="b",
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
        description="Account label to mark as selected (for frontend display purposes), e.g., 'a' or 'b'",
    ),
    selected_as: str = Query(
        ..., description="Which slot to mark as selected: 'a' or 'b'"
    ),
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
    if selected_as not in ["a", "b"]:
        raise HTTPException(status_code=400, detail="selected_as must be 'a' or 'b'")
    # write to the database tha a or b is selected given below response
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
