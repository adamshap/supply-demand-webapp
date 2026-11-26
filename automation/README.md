# Automatic supply/demand dashboard updates

The pipeline runs on GitHub Actions using public BEA data. It does not run Stata, use Haver or require either personal computer to be on. All six CSVs and supply_demand_public.xlsx are prepared and verified before one Git commit publishes them together with data-update.json. The shared research do-files and datasets are unchanged.

## Timing and retries

The official Personal Income and Outlays iCalendar feed supplies the release date, time and reference month: https://www.bea.gov/news/schedule/ics/online-calendar-subscription.ics . Lightweight calendar checks run at 12:57, 13:57, 17:57 and 21:57 UTC daily. The first data check is normally around 8:57 a.m. Eastern on release morning, in winter and summer. The ten-minute offset from ISMI reduces contention on the shared BEA API key. GitHub can delay a scheduled start.

No BEA data tables are downloaded when the scheduled reference month is already published or the next release is not due. When a due release is missing or incomplete in the API, published files remain untouched and the next check retries, including weekends. Changed or postponed calendar dates are read automatically. Calendar failures fail closed; stale calendars are flagged instead of guessed. Manual Actions runs bypass the calendar unless follow_calendar is selected.

The source uses bounded retries, gzip, BEA's Retry-After header, and spacing between large tables to respect the 100 MB/minute API limit. Scheduled runs are gated by repository variable BEA_AUTO_UPDATE_ENABLED=true. The encrypted repository secret BEA_API_KEY supplies access. No credentials are present in source, logs or saved inputs.

## Inputs and model

BEA NIUnderlyingDetail tables U20404 (price indexes), U20405 (nominal expenditures), and U20403 (quantity indexes) supply all required inputs. The 130 category mapping is explicit in categories.csv. Quantity series use the RA counterpart of each RG price code. Package tours uses DHOL; the two foreign-expenditure offsets retain the Stata sign convention. Core nominal expenditures use DPCCRC.

The active Stata specifications estimate separate price and quantity equations on levels of logs, with twelve lags of both variables and a constant. Each monthly window covers t-120 through t inclusive. Quarterly inputs average the available monthly levels before logs and use four lags, t-40 through t inclusive. The current partial quarter is included, matching the existing dashboard. Price log regressors, residual predictions, standardized residual scores, contributions and accumulations preserve the Stata float/double conventions. Classification cutoffs are 0, 0.10, 0.15 and 0.30 as specified in the original code. Contributions use lagged category spending divided by lagged aggregate spending.

Ordinary updates mirror the code, including its actual window lengths: aggregate and precision monthly outputs update 25 months, goods/services outputs update 18 months, and quarterly outputs update 25 quarters. Initial missing annual contributions within an incremental window keep their existing historical values, matching Stata merge, update replace. Annual contributions compound each precision component before combination, preserving the original scripts' arithmetic and export rounding. Non-housing services subtract housing contributions; their denominator remains total headline or core expenditures.

September DATA trigger a full historical benchmark, including a catch-up when September was missed and the next successful release is October. Manual benchmark mode, an explicit full_history request, changed model version, or a checksum mismatch in any of the seven published files also forces a full rebuild. Windows CRLF and Linux LF checkouts share canonical CSV hashes. Concurrent Git uploads cause push to fail instead of overwriting the other change.

## Historical numerical compatibility

Sixteen guarded historical cases in information-processing equipment (drgim), confined to 1970-72, have degenerate/nearly zero residuals. Floating-point solvers can give those residuals different zero signs, affecting the zero-threshold baseline classification. The published Stata classifications are retained in historical-zero-ties.json for those cases. Every record requires the exact BEA model-input signature and a near-zero score; changed historical inputs stop publication for review. Precision and ambiguity classifications remain calculated normally. Constant rounded historical quantity indexes retain Stata's missing-score comparison convention. No current-month category classification is overridden.

These explicit compatibility records preserve the original methodology and published historical baseline rather than choosing a new epsilon threshold. The supplied public BEA fixture and already-public seven output files permit reproducible validation without Haver or a Stata license.

## Validation

Public BEA prices, spending and quantities were checked against the available Haver inputs: 814 monthly observations, 393 input series, identical missingness and zero maximum difference. A full BEA reconstruction reproduces all six dashboard CSVs (76,808 cells including matched startup missing values) through October 2026, within saved numerical precision. All six Excel sheets were also checked, including their original column labels, dates and quarterly units. The workbook stores q/q fractions while the dashboard CSV stores percentage points; that existing distinction is preserved. Full reconstruction and validation reports are retained in validation-initial.json and GitHub run artifacts.

Run python -m pip install -r automation/requirements.txt, then python -m unittest discover -s automation/tests -v and node automation/tests/test_dashboard_status.js. Tests cover the complete historical exports against fixed Stata output fixtures, workbook round-trip checks, incremental windows and preservation, September/catch-up benchmarks, changed historical-tie inputs, release-calendar postponements and retries, all-seven-file installation, failed-update protection, and the homepage date display. Hosted updates run these checks before calculating the new release.

The updater checks date continuity, schemas, missing-value locations and finite/range bounds. Both Excel and CSV candidates are saved as workflow artifacts for 30 days. The updater reopens and validates all six Excel sheets before installation. Calendar-only checks skip dependency installation, tests and data downloads.

## Homepage and publishing

The homepage shows Last updated using the BEA release date, separately from Data through (the reference month). data-update.json also records the successful export timestamp. Routine checks and delayed releases do not advance the displayed date. The browser only displays the date if metadata and the loaded baseline CSV cover the same month.

GitHub Pages uses an explicit Actions deployment after a data commit, because a GITHUB_TOKEN push does not trigger another push workflow. Only the public dashboard HTML, six CSVs, workbook, date metadata and preview are staged into the Pages artifact. Analytics settings and the high-resolution PNG download are preserved.

## Source scripts checked (read only)

create_benchmark_sd.do; update_monthly_sd.do; main_construct.do; main_construct_goodsserv.do; main_publicdata.do, in Adam's supplied JMCB Programs folder. audited-source-hashes.json records their hashes. No changes were installed into the shared research folder. The old runner scripts have unbounded flag-wait loops; this replacement instead has a bounded GitHub job timeout and never publishes a failed partial run.
