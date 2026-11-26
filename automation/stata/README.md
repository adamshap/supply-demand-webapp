# Native Stata cross-check

`sd_zero_exact_fit.do` is the same helper embedded by the installer in the two original constructors. Only residuals with unit projection leverage are zeroed. No date/category exceptions or small-shock threshold are used.

Run `python automation/stata/prepare_reference.py ABSOLUTE_SCRATCH_FOLDER` to prepare the four public-data scenarios. In Stata run each `reference_SCENARIO.do`, supplying the absolute scratch folder and absolute helper-file path as two quoted arguments. These scripts execute the original regressions and float-storage conventions in native Stata. They write separate `stata_ref_corrected_SCENARIO.dta` results in scratch. They never edit live source data or publish dashboard files.

The checked-in `tests/fixtures/stata_revision_reference.csv.gz` concatenates those results. Missing Stata standardized scores are interpreted using Stata's missing-value ordering. The automated tests compare both unit-leverage flags and classifications at the baseline/ambiguity cutoffs across all 130 categories, monthly and quarterly, for 9,360 model points / 18,720 classifications. Scenarios include original inputs, rebasing, historical revisions that remove the old exact fits, and simultaneous benchmark revisions.

`tests/fixtures/stata_unit_leverage_corrections.csv` records the independently calculated native Stata corrections to the original seven-file reference. The original archived CSV/workbook fixtures remain unchanged. Revisions are test inputs only; cached inputs cannot be used in publishing mode.

# Work-computer installation

The Dropbox constructors were patched and verified on the research computer. Their runners still call P:, which was not mounted here. On the work computer, run `Install-StataPrecisionFix.ps1` in PowerShell. Its default target is `P:\Dividing Inflation\Supply Demand\Working Paper\JMCB\Programs`; use `-ProgramsPath` only if the actual constructor folder differs. It makes byte backups, preserves line endings, checks for concurrent changes, and safely reports already-current files. It does not change either runner's paths.
