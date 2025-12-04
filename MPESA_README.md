Mpesa webhook integration

This project exposes `/contributions/webhook` to receive Mpesa (Daraja) callbacks. By default the webhook will accept payloads but you should secure it before going to production.

Recommended setup

1. Set a shared secret in your environment (on the server):

   - `MPESA_WEBHOOK_SECRET` — a random secret used to compute/verify HMAC-SHA256 over the raw JSON body. Example export in PowerShell:

```powershell
$env:MPESA_WEBHOOK_SECRET = "your_long_random_secret_here"
```

2. Configure Safaricom Daraja callback URL to point to:

   - `https://YOUR_DOMAIN/contributions/webhook`

   Daraja will send the STK Push or C2B confirmation JSON to this URL.

3. Signature expectations

   - This app expects the provider to set an HTTP header containing an HMAC-SHA256 of the raw request body. Common header names checked: `X-Mpesa-Signature`, `X-Signature`, `X-Callback-Signature`.
   - The HMAC should be computed as:
     - HMAC-SHA256(secret, rawBody)
     - base64-encode the result
     - set header value to the base64 string

4. Example cURL (local test) — compute signature in PowerShell and send a signed request:

```powershell
$secret = 'my_secret_here'
$body = '{"amount":1000, "msisdn":"2547xxxxxxx", "name":"Test"}'
$bytes = [System.Text.Encoding]::UTF8.GetBytes($body)
$hmac = (New-Object System.Security.Cryptography.HMACSHA256([System.Text.Encoding]::UTF8.GetBytes($secret))).ComputeHash($bytes)
$signature = [System.Convert]::ToBase64String($hmac)
Invoke-RestMethod -Uri 'https://localhost:5000/contributions/webhook' -Method Post -Body $body -ContentType 'application/json' -Headers @{ 'X-Mpesa-Signature' = $signature }
```

5. Testing without signature

   - If `MPESA_WEBHOOK_SECRET` is not set, the webhook will still accept requests but will log a warning. Only use this in development.

6. Production hardening

   - Use HTTPS and a valid certificate.
   - Use a unique secret per environment and rotate regularly.
   - Validate payload structure and transaction status (e.g., `ResultCode` in STK callbacks) before crediting.
   - Consider validating SSL client certificates or IP allowlist if available.
   - Move from `contributions.json` to a proper database (SQLite, Postgres) for concurrency and durability.

7. Removing the simulate endpoint

   - The app includes `/contributions/simulate` for local testing. Remove or protect it when moving to production.

8. Disabling the simulate endpoint (recommended for production)

   - By default the simulate endpoint is disabled. To enable it temporarily for local testing set:

     ```powershell
     $env:ENABLE_MPESA_SIMULATE = 'true'
     ```

   - When deploying to production, do NOT set `ENABLE_MPESA_SIMULATE` and remove the test UI from templates (already removed by default).

   - Prefer using the real webhook from Mpesa (Daraja) to post transactions to `/contributions/webhook`.

If you want, I can:
- Add an environment check that rejects unsigned requests on production servers.
- Replace the JSON file with SQLite and add migrations.
- Add logging of webhook events to a dedicated log file.

Tell me which of those you'd like next.