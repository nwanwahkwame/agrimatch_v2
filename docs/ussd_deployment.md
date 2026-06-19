# USSD Deployment Guide

AgriMatch USSD service runs on Africa's Talking Ghana via shortcode `*384#`.
This document covers everything needed to go from sandbox to live.

---

## 1. Register a shortcode with Africa's Talking Ghana

1. Sign in at [account.africastalking.com](https://account.africastalking.com)
2. Go to **USSD** > **Create Channel**
3. Fill in:
   - **Shortcode**: request `*384#` (or an assigned shared code during testing)
   - **Country**: Ghana
   - **Callback URL**: `https://your-domain.com/api/ussd`
   - **HTTP Method**: POST
4. Africa's Talking will confirm the shortcode allocation within 1-3 business days
5. For sandbox testing, use the **Simulator** tab on your AT dashboard — no real shortcode needed

---

## 2. Required environment variables

Add these to your `.env` file (never commit this file):

```env
# Africa's Talking credentials
AT_USERNAME=sandbox          # change to your live AT username for production
AT_API_KEY=your_api_key_here
AT_SENDER_ID=AgriMatch       # or your approved sender ID
```

| Variable | Sandbox value | Production value |
|---|---|---|
| `AT_USERNAME` | `sandbox` | your AT account username |
| `AT_API_KEY` | sandbox key from AT dashboard | live key from AT dashboard |
| `AT_SENDER_ID` | `AgriMatch` (ignored in sandbox) | approved alphanumeric sender ID |

**Where to find your keys:**
- Log in at account.africastalking.com
- Go to **Settings** > **API Key**
- Sandbox key is shown on the sandbox dashboard

---

## 3. Callback URL Africa's Talking will POST to

```
POST https://your-domain.com/api/ussd
```

Africa's Talking sends `application/x-www-form-urlencoded` with these fields:

| Field | Description |
|---|---|
| `sessionId` | Unique session identifier |
| `serviceCode` | The USSD code dialled (`*384#`) |
| `phoneNumber` | Caller's phone in international format (`+233...`) |
| `text` | All keypresses so far, joined with `*` |

The endpoint must respond within **10 seconds** with a plain-text body starting with:
- `CON ...` — session continues (shows menu to user)
- `END ...` — session ends (dismisses USSD screen)

---

## 4. Sandbox vs production switching

The `AlertEngine` class reads `AT_USERNAME` and `AT_API_KEY` from `config/settings.py`.

**Sandbox** (default — no real SMS sent):
```env
AT_USERNAME=sandbox
AT_API_KEY=       # leave blank; engine logs status='failed' for SMS
```

**Sandbox with real AT sandbox SMS** (sends to AT sandbox simulator):
```env
AT_USERNAME=sandbox
AT_API_KEY=<your sandbox key from AT dashboard>
```

**Production** (real SMS delivery):
```env
AT_USERNAME=<your live AT username>
AT_API_KEY=<your live AT API key>
AT_SENDER_ID=AgriMatch
```

To enable dry-run logging without any SMS delivery (useful for load testing),
instantiate `AlertEngine(dry_run=True)` or set an env flag and pass it through.

---

## 5. Cost estimate (Ghana, as of 2026)

| Item | Approximate cost |
|---|---|
| USSD session (AT Ghana) | GHS 0.05 - 0.10 / session |
| SMS confirmation | GHS 0.03 - 0.05 / message |
| Shortcode monthly rental | ~$50 USD / month for dedicated code |
| Shared shortcode | Free or minimal — contact AT Ghana |

A farmer completing a full registration + declaration = 1 session + 2 SMS = ~GHS 0.20.
At 500 registrations/month, estimated monthly AT cost: ~GHS 100.

---

## 6. Security notes

- The `/api/ussd` endpoint accepts unauthenticated POST requests (required by AT)
- Africa's Talking signs requests with a hash in the `X-Africastalking-Signature` header
  - To verify, compute `HMAC-SHA256(request_body, AT_API_KEY)` and compare
  - Currently not enforced — add header verification before going to production
- Phone numbers are normalised to local format (`0244...`) before DB storage
- Session data is stored in `ussd_sessions` table with no sensitive personal data beyond the phone number

---

## 7. Testing the endpoint locally

Use the built-in USSD simulator at `http://localhost:3000/admin/ussd-test`, or via curl:

```bash
# Step 1: Welcome screen (empty text)
curl -X POST http://localhost:8000/api/ussd \
  -d "sessionId=test_001&phoneNumber=+233244123456&serviceCode=*384%23&text="

# Step 2: Full registration + declaration in one shot
curl -X POST http://localhost:8000/api/ussd \
  -d "sessionId=test_002&phoneNumber=+233244999001&serviceCode=*384%23&text=Ama*1*1"

# Step 3: List maize 50 bags, harvest 3 weeks, confirm
curl -X POST http://localhost:8000/api/ussd \
  -d "sessionId=test_003&phoneNumber=+233244999001&serviceCode=*384%23&text=1*1*50*3*1"
```

After a successful declaration, check:
```sql
SELECT * FROM farmer_declarations WHERE source = 'ussd' ORDER BY id DESC LIMIT 5;
SELECT * FROM alerts_log WHERE alert_type = 'ussd_confirmation' ORDER BY id DESC LIMIT 5;
```
