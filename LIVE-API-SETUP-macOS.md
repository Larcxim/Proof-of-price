# Proof of Price: live API setup on macOS

This optional setup makes a **read-only** request to Binance's authenticated Web3 RWA Data API. It does not connect a wallet or submit a transaction.

## Keep the credentials private

- Use this in a private local copy on your Mac, not in the shared workspace preview.
- Never send the API Key or Secret Key in chat, add them to the dashboard/browser code, or commit them to GitHub.
- The launcher asks for both values with hidden typing. It passes them to the local server process and does not write them to a file.

## Start the live dashboard

1. Download and unzip `proof-of-price-live-api-kit.zip`.
2. Open the extracted `bnb-monitor` folder in Finder.
3. Double-click `Start-Proof-of-Price.command`. If macOS blocks it, Control-click the file, choose **Open**, and confirm.
4. In the Terminal window, paste the Web3 **API Key** at its prompt and press Return. The text stays hidden. Paste the **Secret Key** at the next prompt and press Return; its text is hidden too.
5. Leave the Terminal window open. In your browser, visit **http://127.0.0.1:8000**.
6. In the history selector, choose **SOXL**. In **Official RWA API check**, click **Fetch selected ticker**.
7. The live card should show the BSC chain, the bStocks and Ondo per-share values, their direct basis, and the local fetch time. Treat it as a new API observation; it does not change the saved Poll 7–10 history.
8. When finished, return to Terminal and press **Control-C**. That stops the local server; the credentials are no longer available to the running process.

## If it does not work

- **401 / API rejected:** check that the key is for the **Binance Web3 API** and that it is active for the RWA Data endpoints. Do not enable trading just to make this read-only check work.
- **Could not reach the API:** check internet access and retry.
- **No matching SOXL pair / partial result:** the API did not return both BSC token records or a required price/ratio. The dashboard will leave the basis unavailable rather than fill in a missing value.
- Share only the error text if you need help. Cover the API Key, Secret Key, email, and account details in any screenshot.

The saved offline `dashboard-preview.html` cannot make authenticated calls. Use the local server launched by the `.command` file for the live check.