# Password-protected hosted demo — Frankfurt

## Why Frankfurt
The first Render service was created without a region in `render.yaml`, so Render used its Oregon default. Binance Web3 lists the United States as restricted and enforces IP checks at the API server. The dashboard may load from a U.S. service while the signed API request is rejected.

For the live API demo, use `render-frankfurt.yaml`, which explicitly sets `region: frankfurt`. References: [Binance Web3 restricted regions](https://web3.binance.com/en/dev-docs/web3-api-prohibited-regions) · [Render Blueprint region defaults](https://render.com/docs/blueprint-spec).

## Deploy
1. In Render, select **New → Blueprint** and connect the `Larcxim/Proof-of-price` repository on `main`.
2. Set **Blueprint Path** to `render-frankfurt.yaml`. Confirm the service is `proof-of-price-judge-demo-frankfurt`, the region is **Frankfurt**, and the plan is **Free**.
3. Enter `OC_API_KEY`, `OC_SECRET_KEY`, and a unique `DEMO_PASSWORD` of at least 16 characters in Render's environment settings. `DEMO_USERNAME` is `judge`.
4. Open the new service's HTTPS URL. Sign in as `judge`, select `SOXL`, and click **Fetch selected ticker**. The live result is separate from the saved historical polls.
5. Test the same URL on a phone or tablet. The wide comparison table may need horizontal scrolling.

Keep API credentials and the judge password out of GitHub, screenshots, URLs, and chat. Share the judge password only with intended reviewers. The app is read-only: no wallet connection, trades, or transactions.

Keep the old U.S.-region service until the Frankfurt live check succeeds. If cleaning up the old deployment, disconnect its Blueprint and delete only the old U.S. service; do not delete the Frankfurt service or Blueprint. Disconnecting a Blueprint alone does not delete its services.

Render's free web services can sleep after 15 minutes without traffic and may take about a minute to wake. Open the demo shortly before judging.
