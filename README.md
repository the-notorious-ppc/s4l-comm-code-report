# S4L Comm Code Performance Report

Google Ads Shopping and PMax spend for Shelters4Less (customer `3119628801`),
rolled up from item ID to comm code and published as a static dashboard.

Forked from the RF report. Same pipeline, same shared lookup, one addition:
a confidence floor on the ROAS column. See below for why.

## Setup

1. Create the repo and push this directory.
2. Add the repository secrets. **These are the same values as the RF repo** —
   S4L sits under the same manager account, so the developer token, client ID,
   client secret, refresh token and `login_customer_id` all carry over unchanged.
   Only `CUSTOMER_ID` in `pull.py` differs.

   ```
   GOOGLE_ADS_DEVELOPER_TOKEN
   GOOGLE_ADS_CLIENT_ID
   GOOGLE_ADS_CLIENT_SECRET
   GOOGLE_ADS_REFRESH_TOKEN
   GOOGLE_ADS_LOGIN_CUSTOMER_ID
   ```

3. Settings → Pages → Source: GitHub Actions.
4. Run the backfill once, locally, with a `google-ads.yaml` in the working
   directory:

   ```
   pip install -r requirements.txt
   python pull.py --backfill      # 36 months
   python build.py
   git add data/daily.csv.gz && git commit -m "Backfill" && git push
   ```

5. Actions → *Daily report refresh* → Run workflow, to confirm the scheduled
   path works. After that it runs itself at 06:00 UTC.

`google-ads.yaml` and `client_secret.json` are gitignored. Keep them that way.

## The `-sh` suffix

Half the S4L catalogue carries a trailing `-sh` on the item ID that does not
exist in the lookup. `pull.py` strips it, anchored to the end only.

Validated against the Aug-25 to Aug-26 product report (7,024 SKUs):

| join | SKUs matched | spend matched |
|---|---|---|
| raw item ID | 49.8% | 83.4% |
| `-sh` stripped | **99.3%** | **97.7%** |

Colour suffixes (`-blu`, `-grn`, `-blk`, `-sil`, `-ut`, and the rest) are keyed
that way in the lookup and must not be stripped. A global replace rather than an
anchored one would also corrupt IDs like `bespoke-shs02` and `cc-sheet`.

If the unmapped share climbs much above ~2.5% of spend, check here first: it
almost certainly means a new suffix convention has appeared in the feed.

## The confidence floor

The problem this solves: over the trailing year, only 33 of 167 comm codes with
spend recorded a single Purchase conversion. Rendered naively, four fifths of
the table reads `0.00x` — which looks like failure but is mostly silence. Acting
on it means cutting codes that were never measured.

`build.py` derives a click threshold from the account's own blended CVR:

```
n = ln(1 - CONFIDENCE) / ln(1 - CVR)
```

the number of clicks at which a code performing at the account average would
have converted at least once, with the stated confidence. At the S4L blended
CVR of 1.37% and 90% confidence, that lands near 170 clicks.

The table then shows three states rather than one:

- **`2.54x`** — the code converted. Real ROAS.
- **`0.00x`** in red — no conversions, but past the floor. A real result.
- **`insufficient`** — no conversions and under the floor. Not a judgement.

Sorting by ROAS always files `insufficient` codes last, in both directions, so
they cannot surface as the worst performers. The toggle above the table hides
them entirely.

Tunable at the top of `build.py`: `CONFIDENCE` (0.90), `FLOOR_WINDOW_DAYS`
(365), and the `FLOOR_MIN` / `FLOOR_MAX` clamp.

**Note on short date ranges.** The floor is a click count applied to whichever
range is selected. On a 7-day view most codes will legitimately read
`insufficient`, because at this spend level a week genuinely does not contain
enough traffic to judge a long-tail code. That is the honest answer, not a bug.
For code-level decisions use 90 days or a custom range.

## Known limits

- Conversions are **Purchase** only. Enquiries, phone and offline orders are
  invisible here, so every ROAS figure is a floor on true performance. This
  matters more for S4L than it did for RF given the considered purchase and the
  quote-led path — weigh it before cutting spend on any code.
- `shopping_performance_view` covers Shopping and PMax product traffic only.
  Search is out of scope by design.
- Product impressions count once per product shown, so they exceed campaign
  impressions and CTR reads correspondingly lower.
- The daily job pulls a 35-day window. If the S4L conversion window is ever
  widened past 30 days, raise `DAILY_LOOKBACK_DAYS` to match or late
  conversions will be permanently missed from the archive.
