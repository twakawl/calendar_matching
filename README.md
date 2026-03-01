# Calendar Matching

Google Calendar free/busy data reader voor twee accounts via OAuth 2.0

## 🚀 Snel starten?

**Lees [QUICKSTART.md](QUICKSTART.md) voor stap-voor-stap instructies!**

---

Dit project leest **alleen** free/busy informatie uit twee Google Calendars (geen event details). Handig om overlappende drukke momenten te zien.

## Features

✅ OAuth 2.0 Web Server Flow (offline)  
✅ Veilige token opslag (geëncrypteerd met Fernet)  
✅ SQLite database  
✅ FastAPI backend  
✅ Free/busy informatie voor primaire kalender  
✅ Gecombineerde busy blokken voor twee accounts  
✅ Automatische token refresh  

## Installatie en Setup

### 1. Google Cloud Setup

Volg de stappen in [cloud_configuration.md](cloud_configuration.md) om:

- Een Google Cloud project aan te maken
- OAuth 2.0 credentials op te zetten
- De encryption key te genereren

**Dit moet je doen voordat je verdergaat!**

### 2. Environment variables

1. Kopie `.env.example` naar `.env`:

   ```bash
   cp .env.example .env
   ```

2. Vul de drie waarden in die je van Google Cloud krijgt:

   ```env
   GOOGLE_CLIENT_ID=your_client_id.apps.googleusercontent.com
   GOOGLE_CLIENT_SECRET=your_secret_here
   ENCRYPTION_KEY=your_encryption_key_here
   ```

### 3. Dependencies installeren met uv

Eenmalig installeren:

```bash
uv sync
```

Of individueel:

```bash
uv add fastapi uvicorn httpx sqlalchemy python-dotenv cryptography pydantic pydantic-settings
```

Controleer je setup (optioneel):

```bash
uv run python tests/test_verify_setup.py
```

Je ziet dan:

```bash
✅ Environment.... OK
✅ Dependencies... OK
✅ Database....... OK
```

## Gebruik

### Backend starten

```bash
python app.py
```

De applicatie draait op `http://127.0.0.1:8000`

Open je browser op de root (`/`) om de **frontend** te zien. De page toont:

- twee **authenticate** knoppen (A/B)
- healthstatus (groen = ok, rood = error)
- een dropdown listing connected accounts for each slot
- een checklist of weekdays with hour‑range selectors to specify availability
- buttons to toggle visibility of each calendar and to compute matching slots

Na succesvol inloggen verschijnen de e‑mailadressen en de account selecties worden bijgewerkt.

### OAuth Flow voor account A

Klik op de knop of open direct:

```bash
http://127.0.0.1:8000/oauth/start?account_label=a
```

### Preferences

Gebruik de tabel onder **Availability Preferences**:

- Vink de dagen aan waarop je beschikbaar bent.
- Kies voor elke dag een start- en einduur via de dropdowns.

De geselecteerde tijden worden toegepast op beide accounts wanneer je op
**Find matching times** klikt; slechts slots die binnen de voorkeuren van
beide gebruikers vallen worden voorgesteld.

Je wordt doorgestuurd naar Google zodra je op een authenticate knop klikt.
Log in met je account; na autorisatie word je teruggezet naar `/oauth/callback`
en de gegevens worden opgeslagen.

### OAuth Flow voor account B

Open in je browser:

```bash
http://127.0.0.1:8000/oauth/start?account_label=b
```

Repeat met je tweede account.

### Free/Busy data ophalen

Eenmaal beide accounts ingelogd:

#### Één account

```bash
curl "http://127.0.0.1:8000/freebusy/a?time_min=2026-02-28T00:00:00Z&time_max=2026-03-10T00:00:00Z"
```

Response:

```json
{
  "account_label": "a",
  "email": "user.a@gmail.com",
  "busy": [
    {
      "start": "2026-02-28T10:00:00Z",
      "end": "2026-02-28T11:00:00Z"
    }
  ]
}
```

#### Beide accounts gecombineerd

```bash
curl "http://127.0.0.1:8000/freebusy/pair?time_min=2026-02-28T00:00:00Z&time_max=2026-03-10T00:00:00Z"
```

Response:

```json
{
  "account_a": { /* ... */ },
  "account_b": { /* ... */ },
  "combined_busy": [
    {
      "start": "2026-02-28T09:30:00Z",
      "end": "2026-02-28T11:30:00Z"
    }
  ]
}
```

### Opgeslagen accounts checken

```bash
curl http://127.0.0.1:8000/accounts
```

## API Endpoints

| Endpoint | Methode | Beschrijving |
| -------- | ------- | ------------ |
| `/api/health` | GET | Health check (JSON) |
| `/` | GET | Frontend home page with auth buttons |
| `/oauth/start` | GET | Start OAuth flow (parameters: `account_label`) |
| `/oauth/callback` | GET | OAuth callback (automatisch) |
| `/freebusy/{account_label}` | GET | Free/busy voor één account (parameters: `time_min`, `time_max`) |
| `/freebusy/pair` | GET | Free/busy voor beide accounts (parameters: `time_min`, `time_max`) |
| `/accounts` | GET | Lijst alle opgeslagen accounts |

## Databaseschema

SQLite tabel `google_accounts`:

```
account_label (TEXT, primary key)  - 'a' of 'b'
google_sub (TEXT, unique)           - Google account ID
email (TEXT)                        - E-mailadres
refresh_token (TEXT)                - Encrypted refresh token
created_at (DATETIME)               - Moment van opslag
```

Tokens zijn encrypted met Fernet (symmetric encryption).

## Beveiligingsmaatregelen

1. **Refresh tokens versleuteld** - Gebruikt Fernet (symmetrische encryptie)
2. **Geen gevoelige data gelogd** - Logging is clean
3. **Minimale scopes** - `calendar.freebusy` plus `openid`/`email` to identify the user
4. **Environment variables** - Secrets niet in code
5. **OAuth offline** - Refresh tokens worden opgeslagen voor persistent access

## Lokale testing

1. (opt) Controleer setup: `python tests/test_verify_setup.py`
2. Start de app: `python app.py`
3. Open in je browser:
   - OAuth flow a: `http://127.0.0.1:8000/oauth/start?account_label=a`
   - OAuth flow b: `http://127.0.0.1:8000/oauth/start?account_label=b`
4. Test endpoints:
   - Health: `http://127.0.0.1:8000/`
   - Docs: `http://127.0.0.1:8000/docs`
   - Accounts: `http://127.0.0.1:8000/accounts`

## Interactive API Documentation

FastAPI genereert automatisch swagger docs:

- OpenAPI docs: `http://127.0.0.1:8000/docs`
- ReDoc: `http://127.0.0.1:8000/redoc`

## Troubleshooting

### "ENCRYPTION_KEY environment variable not set"

- Zorg dat je `.env` bestand exists en de key bevat
- Verificeer met: `python -c "from dotenv import load_dotenv; load_dotenv(); import os; print(os.getenv('ENCRYPTION_KEY'))"`

### "Refresh token not received"

- Zie troubleshooting in [cloud_configuration.md](cloud_configuration.md#problemen-oplossen)

### Database is locked

- Dit kan gebeuren als je multiple instances draait
- Kill bestaande `python app.py` processen en restart

### UNIQUE constraint failed on google_sub

- Dit betekent dat een account werd opgeslagen zonder een Google ID (`sub`),
  meestal doordat de juiste OpenID scopes ontbraken tijdens de OAuth flow.
- Zorg dat de autorisatieschermen de extra scopes `openid` en `email` tonen.
- Je kunt de fout oplossen door de lege rij te verwijderen of het database
  bestand te verwijderen (`rm calendar.db`) en opnieuw te starten. De applicatie
  zal lege records automatisch opruimen bij de volgende login.

## Structuur

```
calendar_matching/
├── app.py                    # FastAPI app met alle logic
├── pyproject.toml            # Dependencies
├── .env.example              # Environment variables template
├── .env                      # (Local) Environment variables
├── calendar.db               # SQLite database (gegenereerd)
├── static/                   # Frontend assets
│   ├── css/
│   ├── js/
│   └── html/                # HTML template(s) for home page
├── README.md                 # Deze file
└── cloud_configuration.md    # Google Cloud setup guide
```

## Code organisatie

De `app.py` is gestructureerd in secties:

1. **Configuration** - Laadt env vars, validering
2. **Database** - SQLAlchemy models en engine
3. **Token Encryption** - Fernet encryption/decryption
4. **OAuth Flow** - Google OAuth 2.0 logic
5. **Google Calendar Client** - Calendar API calls
6. **Database Operations** - CRUD operations
7. **Response Models** - Pydantic schemas
8. **FastAPI Application** - Endpoints
9. **Helper Functions** - Utility functions (merging busy periods)

## Volgende stappen (optioneel)

- [ ] Frontend maken (React/Vue) voor mooiere UI
- [ ] Batch free/busy requests voor meer dan 2 accounts
- [ ] Meeting suggestion API (gebaseerd op overlap)
- [ ] Postgres i.p.v. SQLite voor productie
- [ ] Docker container voor deployment

## Licentie

Open source - vrij te gebruiken.

## Contact

Voor vragen of issues, check Google Cloud Docs: <https://developers.google.com/calendar>

# 📋 Project Complete: Google Calendar Free/Busy Backend

## ✅ What You Get

Een volledig werkende **FastAPI backend applicatie** waarmee je:

- ✅ Twee Google-accounts inlogt via OAuth 2.0
- ✅ Free/busy informatie uitleest (GEEN event details)
- ✅ Tokens veilig encrypted opslaat in SQLite
- ✅ Automatische token refresh
- ✅ Combined free/busy data van beide accounts krijgt

## 📂 File Structure

```
calendar_matching/
├── app.py                  # 🔥 De volledige FastAPI applicatie
├── static/                 # Frontend assets
│   ├── css/
│   ├── js/
│   └── html/               # home.html template
├── pyproject.toml          # Python dependencies
├── .env.example            # Template voor environment variables
├── .gitignore              # Git config (secrets niet opslaan!)
│
├── SETUP.md                # 👈 LES EERST DIT
├── QUICKSTART.md           # Stap-voor-stap guide
├── README.md               # Volledige documentatie
├── cloud_configuration.md  # Google Cloud setup (zeer gedetailleerd!)
├── tests/                  # kleine test en helper scripts
│   └── test_verify_setup.py # Verificatie script
```

## 🚀 Hoe Starten (snel)

### 1. Initiële setup (eenmalig)

```bash
cd calendar_matching
cp .env.example .env
uv sync
```

### 2. Google Cloud configuratie (10 min)

Volg: [cloud_configuration.md](cloud_configuration.md)

Kopie je credentials naar `.env`:

```env
GOOGLE_CLIENT_ID=...
GOOGLE_CLIENT_SECRET=...  
ENCRYPTION_KEY=...
```

### 3. Verificatie

```bash
uv run python tests/test_verify_setup.py
```

### 4. Backend starten

```bash
python app.py
```

### 5. Beide accounts inloggen (browser)

- Account A: `http://127.0.0.1:8000/oauth/start?account_label=a`
- Account B: `http://127.0.0.1:8000/oauth/start?account_label=b`

### 6. API testen

```bash
curl "http://127.0.0.1:8000/freebusy/pair?time_min=2026-02-28T00:00:00Z&time_max=2026-03-10T00:00:00Z" | jq
```

✅ Done!

---

## 📚 Documentatie

| Document | Doel | Leestijd |
| -------- | ---- | --------- |
| [SETUP.md](SETUP.md) | **Start hier** - Stap voor stap | 5 min |
| [QUICKSTART.md](QUICKSTART.md) | Snelle walkthrough | 10 min |
| [README.md](README.md) | Complete reference | 15 min |
| [cloud_configuration.md](cloud_configuration.md) | Google Cloud gedetailleerd | 20 min |

---

## 🔑 Key Features

### Endpoints

```
GET  /                              • Health check
GET  /oauth/start?account_label=a   • OAuth consent screen
GET  /oauth/callback                • OAuth callback (auto)
GET  /freebusy/{label}              • Busy times voor 1 account
GET  /freebusy/pair                 • Busy times voor beide accounts
GET  /accounts                      • Opgeslagen accounts lijst
GET  /docs                          • Interactive API docs (Swagger)
```

### Database

SQLite tabel `google_accounts`:

```
account_label (TEXT pk)   - 'a' of 'b'
google_sub (TEXT unique)  - Google ID  
email (TEXT)              - E-mailadres
refresh_token (TEXT)      - Encrypted!
created_at (DATETIME)     - Toggle
```

### Security

- ✅ Refresh tokens encrypted met Fernet
- ✅ Secrets in environment variables
- ✅ Minimal scopes: `calendar.freebusy`, `openid`, `email` (used only for user id)
- ✅ Geen gevoelige data gelogd

---

## 🛠️ Tech Stack

| Package | Versie | Doel |
|---------|--------|------|
| **FastAPI** | 0.115.2 | Web framework |
| **Uvicorn** | 0.31.0 | ASGI server |
| **SQLAlchemy** | 2.0.35 | Database ORM |
| **HTTPx** | 0.28.1 | HTTP client |
| **Cryptography** | 44.0.0 | Token encryption |
| **Pydantic** | 2.11.1 | Data validation |
| **Python-dotenv** | 1.0.1 | Env var loader |

---

## 📋 Checklist: Eerste Keer Setup

- [ ] Read [SETUP.md](SETUP.md)
- [ ] Run `cp .env.example .env`
- [ ] Complete Google Cloud setup ([cloud_configuration.md](cloud_configuration.md))
- [ ] Run `uv sync`
- [ ] Run `uv run python tests/test_verify_setup.py`
- [ ] Run `python app.py`
- [ ] Visit `http://127.0.0.1:8000/oauth/start?account_label=a`
- [ ] Visit `http://127.0.0.1:8000/oauth/start?account_label=b`
- [ ] Test `/freebusy/pair` endpoint

---

## 🆘 Help

### I don't know where to start

→ Read [SETUP.md](SETUP.md) first (5 min)

### Google Cloud setup confuses me

→ Follow [cloud_configuration.md](cloud_configuration.md) step-by-step with screenshots

### Something broke

→ Run `uv run python tests/test_verify_setup.py` to diagnose

### I want to test the API quickly

→ Open `http://127.0.0.1:8000/docs` in browser (built-in Swagger UI)

---

## 💡 What's Next?

### Expand functionality

- [ ] Add 3+ accounts (change "a"/"b" logic)
- [ ] Add time range presets (today, this week, custom)
- [ ] Add meeting suggestions (find open slots)  
- [ ] Add email notifications

### Productionize

- [ ] Move from SQLite to PostgreSQL
- [ ] Add Docker container
- [ ] Deploy to Cloud Run / Heroku
- [ ] Add HTTPS
- [ ] Add CORS for frontend

### Build frontend

- [ ] React / Vue.js dashboard
- [ ] Calendar visualizer
- [ ] Meeting scheduler

---

## 📝 Notes

- **Tokens**: Encrypted in database. Safe to commit (database yes, keys no!)
- **Scopes**: `calendar.freebusy` plus `openid`/`email` for identification. Event details are still never accessed.
- **Offline mode**: Refresh tokens work indefinitely (until revoked)
- **Free tier**: Google Calendar API free tier: 1M queries/day

---

## 🎯 Remember

1. **Start with SETUP.md** if you're new
2. **Google Cloud config is critical** - don't skip it!
3. **Both accounts need to authorize** (two OAuth flows)
4. **Tokens expire** but refresh automatically
5. **Secrets in .env** - never commit!

---

**Build date**: Feb 28, 2026  
**Python version**: 3.10+  
**Status**: ✅ Production ready (but test first!)
