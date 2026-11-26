# Automatic supply/demand dashboard updates

The pipeline runs on GitHub Actions using public BEA data. It does not run Stata, use Haver or require either personal computer to be on. All six CSVs and supply_demand_public.xlsx are prepared and verified before one Git commit publishes them together with data-update.json. The two Stata constructors receive the same numerical-zero correction described below; the runners, source data and exporter retain their original method.

## Timing and retries

The official Personal Income and Outlays iCalendar feed supplies the release date, time and reference month: https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics . Eastern-time checks start at 8:34 a.m. on release morning, retry every ten minutes through 9:24 a.m., then hourly at :34 (9:34, 10:34, and so on), including overnight and weekends until the expected release is published. America/New_York scheduling handles daylight saving changes automatically. The three-minute offset from ISMI reduces contention on the shared BEA API key. The calendar permits a due release one minute after official publication, replacing the former fifteen-minute buffer. GitHub can delay a scheduled start.

No BEA data tables are downloaded when the scheduled reference month is already published or the next release is not due. When a due release is missing or incomplete in the API, published files remain untouched and the next check retries, including weekends. Changed or postponed calendar dates are read automatically. Calendar failures fail closed; stale calendars are flagged instead of guessed. Manual Actions runs bypass the calendar unless follow_calendar is selected.

The source uses bounded retries, gzip, BEA's Retry-After header, and spacing between large tables to respect the 100 MB/minute API limit. Scheduled runs are gated by repository variable BEA_AUTO_UPDATE_ENABLED=true. The encrypted repository secret BEA_API_KEY supplies access. No credentials are present in source, logs or saved inputs.

## Inputs and model

BEA NIUnderlyingDetail tables U20404 (price indexes), U20405 (nominal expenditures), and U20403 (quantity indexes) supply all required inputs. The 130 category mapping is explicit in categories.csv. Quantity series use the RA counterpart of each RG price code. Package tours uses DHOL; the two foreign-expenditure offsets retain the Stata sign convention. Core nominal expenditures use DPCCRC.

The active Stata specifications estimate separate price and quantity equations on levels of logs, with twelve lags of both variables and a constant. Each monthly window covers t-120 through t inclusive. Quarterly inputs average the available monthly levels before logs and use four lags, t-40 through t inclusive. The current partial quarter is included, matching the existing dashboard. Price log regressors, residual predictions, standardized residual scores, contributions and accumulations preserve the Stata float/double conventions. Classification cutoffs are 0, 0.10, 0.15 and 0.30 as specified in the original code. Contributions use lagged category spending divided by lagged aggregate spending.

Ordinary updates mirror the code, including its actual window lengths: aggregate and precision monthly outputs update 25 months, goods/services outputs update 18 months, and quarterly outputs update 25 quarters. Initial missing annual contributions within an incremental window keep their existing historical values, matching Stata merge, update replace. Annual contributions compound each precision component before combination, preserving the original scripts' arithmetic and export rounding. Non-housing services subtract housing contributions; their denominator remains total headline or core expenditures.

September DATA trigger a full historical benchmark, including a catch-up when September was missed and the next successful release is October. Manual benchmark mode, an explicit full_history request, changed model version, or a checksum mismatch in any of the seven published files also forces a full rebuild. Windows CRLF and Linux LF checkouts share canonical CSV hashes. Concurrent Git uploads cause push to fail instead of overwriting the other change.

## Revision-safe numerical precision

The former 16 frozen historical classifications and their input-signature guard have been removed. All category/date classifications are recalculated from the supplied data, including after historical revisions and rebasing.

Those 16 observations have unit OLS leverage: their residual is mathematically zero for any dependent variable. The shared Python/Mata correction sets only these exactly fitted residuals to zero before computing their sample standard deviation and standardized score. It identifies unit leverage using a centered/scaled full-design SVD, including the intercept, with a machine-precision tolerance (64 times double epsilon times sample size). This is a projection-identity check, not a cutoff for small economic shocks. Nonzero residuals and all original economic cutoffs remain unchanged. If revised data remove an exact fit, the observation is classified normally. Constant-dependent-series missing-score conventions remain as in Stata.

The correction changes 116 saved baseline cells in 1970-72, across the aggregate, goods/services and quarterly CSVs and their corresponding Excel sheets. The largest aggregate change is 0.01 percentage point. Recent values, the ambiguity and precision series are unchanged. The original published Stata fixtures are retained; independently calculated corrected Stata values are in tests/fixtures/stata_unit_leverage_corrections.csv.

The two Dropbox constructors have the matching Mata helper embedded immediately after setup, with a call after each residual prediction. Their regressions, lag orders, windows, weights, float storage and strict classification comparisons are preserved. automation/stata/Install-StataPrecisionFix.ps1 performs the same minimal, backed-up, concurrency-checked patch on the work computer's P: Programs folder. P: was unavailable on the research computer, so those copies have not been verified or patched. The installer is also saved in the supplied Dropbox Programs folder. It is safe to rerun when the correction is already present; it does not change runner paths. Dashboard automation runs independently of either local folder.

## Validation

Public BEA prices, spending and quantities were checked against the available Haver inputs: 814 monthly observations, 393 input series, identical missingness and zero maximum difference. Before the v2 numerical correction, a full BEA reconstruction reproduced all six dashboard CSVs (76,808 cells including matched startup missing values) through October 2026, within saved numerical precision. All six Excel sheets were also checked, including their original column labels, dates and quarterly units. The workbook stores q/q fractions while the dashboard CSV stores percentage points; that existing distinction is preserved. Full reconstruction and validation reports are retained in validation-initial.json and GitHub run artifacts.

Run python -m pip install -r automation/requirements.txt, then python -m unittest discover -s automation/tests -v and node automation/tests/test_dashboard_status.js. Tests cover the complete historical exports against fixed Stata output fixtures, workbook round-trip checks, incremental windows and preservation, September/catch-up benchmarks, revised and rebased historical inputs, direct native-Stata parity for 9,360 model points / 18,720 classifications, a full revised-history benchmark, release-calendar postponements and retries, all-seven-file installation, failed-update protection, and the homepage date display. Hosted updates run these checks before calculating the new release.

The updater checks date continuity, schemas, missing-value locations and finite/range bounds. Both Excel and CSV candidates are saved as workflow artifacts for 30 days. The updater reopens and validates all six Excel sheets before installation. Calendar-only checks skip dependency installation, tests and data downloads.

## Homepage and publishing

The homepage shows Last updated using the BEA release date, separately from Data through (the reference month). data-update.json also records the successful export timestamp. Routine checks and delayed releases do not advance the displayed date. The browser only displays the date if metadata and the loaded baseline CSV cover the same month.

GitHub Pages uses an explicit Actions deployment after a data commit, because a GITHUB_TOKEN push does not trigger another push workflow. Only the public dashboard HTML, six CSVs, workbook, date metadata and preview are staged into the Pages artifact. Analytics settings and the high-resolution PNG download are preserved.

## Source scripts checked

create_benchmark_sd.do; update_monthly_sd.do; main_construct.do; main_construct_goodsserv.do; main_publicdata.do, in Adam's supplied JMCB Programs folder. audited-source-hashes.json records their hashes. Only the two constructors received the shared numerical-zero correction, with original-byte backups; runner routing and the exporter are unchanged. The old runner scripts have unbounded flag-wait loops; this replacement instead has a bounded GitHub job timeout and never publishes a failed partial run.

## Freshness after uploads

Pages deployment now packages the CSVs, Excel workbook and release metadata as one content-versioned snapshot. The dashboard first checks `data-manifest.json`, then loads files from that snapshot's unique URLs. New uploads and same-month revisions therefore get new file URLs rather than reusing a cached CSV or workbook. Existing root filenames remain available for external links.

An open dashboard checks the small manifest once per minute while visible, when returning to the tab, after browser back/forward restoration, and after reconnecting. It downloads data again only when a new snapshot appears. It preserves the selected series, decomposition and date range, rolls a selected trailing preset forward, and leaves an explicitly historical window in place. Failed, incomplete or older snapshots do not replace the loaded release; checks retry automatically. Excel downloads recheck the current snapshot when clicked.

A new upload still needs its GitHub Pages deployment to finish. The site cannot show an upload before GitHub has published it. The displayed Last updated remains the BEA release date, not the time of a background check.

`node automation/tests/test_data_refresh.js` checks new months, same-month revisions, preserved selections, versioned Excel links, failed/older-release protection and refresh triggers. `python -m unittest discover -s automation/tests -p test_package_site.py` checks immutable snapshot paths and byte preservation. These run during Pages publishing as well as the release-update checks.
