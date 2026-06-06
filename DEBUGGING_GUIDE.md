# Debugging Guide - Calendar Matching App

## Logging Overview

The application now includes comprehensive logging at DEBUG and INFO levels to help diagnose issues with the `/pair` endpoint.

### Backend Logging Points (app.py)

#### 1. Configuration Validation

- **Log Level**: DEBUG
- **When**: Application startup or first request
- **What to look for**:

  ```
  Validating configuration...
  Encryption key format validated
  Debug mode: True
  Logging level: DEBUG
  ```

- **If it fails**: Check environment variables `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `ENCRYPTION_KEY`

#### 2. OAuth Flow (OAuth Callback)

- **Log Level**: INFO
- **When**: User authenticates via Google
- **Key message**:

  ```
  Account 'a' (user@example.com) saved successfully
  ```

- **If it fails**: Watch for "No refresh token received" or "Unable to determine user identifier"

#### 3. Individual Account Free/Busy (get_freebusy_account)

**Sequence of DEBUG logs:**

1. `get_freebusy_account called for account 'a'`
2. `Account 'a' (user@example.com) retrieved`
3. `Refresh token decrypted for a`
4. `Refreshing access token for a`
5. `Access token refreshed for a`
6. `Fetching free/busy for a from 2026-03-01T00:00:00Z to 2026-03-08T00:00:00Z`
7. `Got free/busy for a: 5 busy periods`
8. **INFO log**: `FreeBusyResponse for a (user@example.com): 5 busy periods`

**If any step fails:**

- Account not found → Check if authentication completed
- Token decryption failed → Check encryption key matches
- Token refresh failed → Refresh token may have expired, re-authenticate
- API call failed → Google API may be down or rate limited

#### 4. Pair Free/Busy (/pair)

- **Log Level**: INFO (entry), DEBUG/ERROR (details)
- **Entry point**:

  ```
  get_freebusy_pair called with time_min=2026-03-01T00:00:00Z, time_max=2026-03-08T00:00:00Z
  ```

- **If one account fails**:

  ```
  error fetching freebusy for account a: <error detail>
  ```

- **Final result**: Both account responses logged as part of the pair response

### Frontend Logging Points (app.js)

#### 1. Account Loading

- **Console Log**: `cached busy for a: {"busy": [...]}`
- Shows the cached 30-day busy data retrieved from server
- Appears once per account when `/accounts` endpoint is called

#### 2. Preferences Submission

- **Console Log**: `preferences [{"day": "Mon", "start": "09:00", "end": "17:00"}, ...]`
- Shows the user's selected availability before sending to API
- Day names are converted to 0-6 (Sun=0, Sat=6)

#### 3. Button Guard

- **Alert if triggered**: "Both calendars must be connected first"
- Indicates `accountsLoaded < 2` counter hasn't reached 2 yet

## How to Debug the 400 Error

### Step 1: Start the Server with Debug Output

```bash
cd /Users/twanhouwers/Documents/4.\ Prive/calendar_matching
uv run python app.py
```

The server will output:

```
2026-02-28 14:32:15,234 - __main__ - INFO - Debug mode: True
2026-02-28 14:32:15,235 - __main__ - INFO - Logging level: DEBUG
```

### Step 2: Open Browser Console

1. Open <http://127.0.0.1:8000> in Chrome/Firefox
2. Press F12 to open Developer Tools
3. Go to **Console** tab (not Network yet)

### Step 3: Authenticate Both Accounts

1. Click "Auth Account A" and complete Google login
2. Watch server output for: `Account 'a' ... saved successfully`
3. Repeat for Account B

### Step 4: Check Frontend Console

After both accounts load, you should see in browser console:

```javascript
cached busy for a: {"busy": [{"start": "2026-03-02T09:00:00Z", "end": "2026-03-02T10:00:00Z"}, ...]}
cached busy for b: {"busy": [{"start": "2026-03-02T14:00:00Z", ...]}
```

### Step 5: Set Preferences and Click Find

1. Check a few days in the table
2. Set hour ranges (e.g., 09:00-17:00)
3. Click "Find matching times"
4. Watch browser console for:

   ```javascript
   preferences: Array(3) [
     { day: "Mon", start: "09:00", end: "17:00" },
     ...
   ]
   ```

### Step 6: Monitor Server Logs

Watch the terminal where server is running. You should see:

**If successful:**

```
2026-02-28 14:35:42,123 - __main__ - INFO - get_freebusy_pair called with time_min=..., time_max=...
2026-02-28 14:35:43,456 - __main__ - DEBUG - get_freebusy_account called for account 'a'
2026-02-28 14:35:43,457 - __main__ - DEBUG - Account 'a' (user@example.com) retrieved
2026-02-28 14:35:43,458 - __main__ - DEBUG - Refresh token decrypted for a
2026-02-28 14:35:43,460 - __main__ - DEBUG - Refreshing access token for a
2026-02-28 14:35:43,650 - __main__ - DEBUG - Access token refreshed for a
2026-02-28 14:35:43,651 - __main__ - DEBUG - Fetching free/busy for a from ... to ...
2026-02-28 14:35:44,123 - __main__ - DEBUG - Got free/busy for a: 3 busy periods
2026-02-28 14:35:44,124 - __main__ - INFO - FreeBusyResponse for a (user@example.com): 3 busy periods
2026-02-28 14:35:45,456 - __main__ - DEBUG - get_freebusy_account called for account 'b'
...
```

**If error at token refresh:**

```
2026-02-28 14:35:43,650 - __main__ - ERROR - Token refresh failed for a: HTTPError: 401 Client Error...
```

**If error at API call:**

```
2026-02-28 14:35:44,123 - __main__ - ERROR - Failed to get free/busy data for a: BadRequest: 400 Client Error...
```

## Common Issues & Solutions

### Issue: "Both calendars must be connected first"

- **Cause**: `accountsLoaded` counter hasn't reached 2
- **Check**: Browser console should show `cached busy for a:` and `cached busy for b:` messages
- **Solution**: Wait for both accounts to load, then click Find again

### Issue: 401 on Token Refresh

- **Cause**: Refresh token has expired or been revoked
- **Solution**: Re-authenticate the account (click Auth button again)

### Issue: 400 on FreeBusy API Call

- **Cause**: Usually invalid time format or missing required scopes
- **Check in logs**: What are the exact `time_min` and `time_max` values being sent?
- **Solution**: Verify time format is RFC 3339 (e.g., `2026-03-01T00:00:00Z`)

### Issue: 500 Token Decryption Failed

- **Cause**: `ENCRYPTION_KEY` environment variable doesn't match the key used to encrypt
- **Solution**: Check `.env` file has correct `ENCRYPTION_KEY`

## Server Log Filtering

To see only ERROR and WARNING messages:

```bash
# Start server and pipe through grep
cd /Users/twanhouwers/Documents/4.\ Prive/calendar_matching
uv run python app.py 2>&1 | grep -E 'ERROR|WARNING'
```

To see everything about account 'a':

```bash
uv run python app.py 2>&1 | grep "for a"
```

To follow logs in real-time on macOS:

```bash
uv run python app.py 2>&1 | tail -f /dev/stdin
```

## Critical Metrics to Note

When debugging, capture these values from the logs:

1. **Request ID / Timestamp** - When did the error occur?
2. **Account Label** - Which account failed (a or b)?
3. **User Email** - Malformed email could cause issues
4. **Time Range** - Are start and end times valid RFC 3339?
5. **Token Status** - Did decryption/refresh succeed?
6. **API Response** - What exact error did Google return?

All of these should appear in the logs when DEBUG=True.
