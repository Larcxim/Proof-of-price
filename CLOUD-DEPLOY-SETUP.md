# Password-protected hosted demo (Render)

This adds an HTTPS-hosted version of the read-only dashboard so judges can open it from a laptop, phone, or tablet. It keeps Binance Web3 API credentials on the server and requires a shared username/password for dashboard and API routes. The `/health` path is public only so the host can verify the process is alive; it returns no project data. Signed live checks are rate-limited, and the Binance client already caches per-ticker results briefly.

This is a limited hackathon demo setup, not a production trading service. It does not connect a wallet, submit transactions, or expose an execution route.

## 1. Add the deployment files to the public GitHub repo

Upload these files into the matching paths in the repository:

- `cloud_serve.py` — repository root
- `render.yaml` — repository root
- `tests/test_cloud_serve.py` — inside the existing `tests/` folder
- `CLOUD-DEPLOY-SETUP.md` — repository root (this guide)

Do **not** upload a `.env` file or any API key, secret, or demo password. The `render.yaml` contains only `sync: false` secret placeholders.

## 2. Create the Render service in a browser

1. Sign in to Render and choose **New → Blueprint**.
2. Connect the public `Larcxim/Proof-of-price` GitHub repository and its `main` branch.
3. Render reads the root `render.yaml` and proposes a Python web service named `proof-of-price-judge-demo`. Review the service before creating it.
4. In the service's environment-variable setup, enter the secrets directly in Render's dashboard:
   - `OC_API_KEY` — your Binance Web3 API key
   - `OC_SECRET_KEY` — its matching secret
   - `DEMO_PASSWORD` — a new, unique password for judges; use at least 16 characters
   - `DEMO_USERNAME` is set to `judge`
5. If Render creates the service before you have added the secrets, open the service's **Environment** page, add the missing values there, save, and redeploy.

Never put these values in GitHub, this guide, a browser URL, a screenshot, or chat. Use only the Binance Web3 credentials created for this read-only API; do not enable trading or wallet permissions for this demo. Anyone who can access the hosted app can use the shared API quota, so only share the judge password with intended reviewers.

## 3. Check the deployed demo

1. Wait for Render's deploy status to become **Live**.
2. Open the service's HTTPS URL on your Mac. The browser will prompt for HTTP Basic Authentication. Enter username `judge` and the private password you set in Render.
3. Test the dashboard and the **Official RWA API check**. Select `SOXL`, then click **Fetch selected ticker**. The check remains read-only and separate from the saved Poll 7–10 history.
4. Open the same HTTPS URL on a phone or tablet and enter the same judge credentials. The layout is responsive; the wide comparison table may need horizontal scrolling.
5. Share the URL and password with judges only through the private submission field or another intended channel—not in the public README.

The host's free web service can spin down after 15 minutes without traffic and may take about a minute to wake on the next visit. Open the URL shortly before the demo. Render documents this free-tier behavior and its limitations in [Free Render Instances](https://render.com/docs/free). Render manages TLS for web-service URLs; see [Render Web Services](https://render.com/docs/web-services).

## Security and cleanup

- The hosted server binds to Render's supplied `PORT` on `0.0.0.0`, while all non-health routes require the demo password.
- The user interface calls the same-origin Python server. It never receives the Binance API secret; the Python backend signs the Binance requests.
- The live endpoint has a server-wide five-second cooldown; repeated reads for the same ticker are additionally served from the existing short-lived cache.
- `/health` returns only `{"ok":true}` and does not reveal dashboard or credential status.
- After judging, delete the hosted service and revoke the dedicated API key if it is no longer needed. Do not reuse a credential that has broader permissions than this read-only demo requires.

## If a judge cannot open it

- A 401/browser password prompt is expected. Confirm you supplied the URL, username `judge`, and password privately.
- A slow first load can be the free service waking up. Wait up to about a minute, then reload once.
- A live API error is distinct from a dashboard deployment failure. Check that both `OC_API_KEY` and `OC_SECRET_KEY` exist in Render's Environment page; never paste their values into issue reports or screenshots.
- If Render's deploy fails, use its deploy log's final error lines to diagnose the missing file or configuration. Redact any private values before sharing logs.
