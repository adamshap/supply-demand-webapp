param([string]$ProgramsPath = 'P:\Dividing Inflation\Supply Demand\Working Paper\JMCB\Programs')
$ErrorActionPreference = 'Stop'
$sdHelper = @'
* BEGIN SD EXACT-FIT POLICY v2
* Shared numerical-zero policy; equations and economic cutoffs are unchanged.
capture program drop sd_zero_exact_fit
program define sd_zero_exact_fit, rclass
    version 15
    syntax varname(numeric), Regressors(string)
    tempvar sd_sample
    quietly generate byte `sd_sample' = e(sample)
    quietly fvrevar `regressors'
    local sd_xvars `r(varlist)'
    mata: sd_zero_unit_fit("`varlist'", "`sd_xvars'", "`sd_sample'")
    return scalar unit_last = `sd_unit_last'
    return scalar unit_count = `sd_unit_count'
end
capture mata: mata drop sd_zero_unit_fit()
mata:
void sd_zero_unit_fit(string scalar residual, string scalar regressors, string scalar sample)
{
    real matrix X, U, Vt
    real colvector observations, singular, h, unit, selected
    real rowvector varying
    real scalar n, rank, tolerance
    observations = selectindex(st_data(., sample) :== 1)
    X = st_data(observations, tokens(regressors))
    n = rows(X)
    varying = selectindex(colmax(X) :> colmin(X))
    if (cols(varying)) {
        X = X[, varying]
        X = X :- mean(X)
        X = X :/ sqrt(colsum(X:^2))
        X = (J(n, 1, 1/sqrt(n)), X)
    }
    else X = J(n, 1, 1/sqrt(n))
    U = Vt = J(0, 0, .)
    singular = J(0, 1, .)
    svd(X, U, singular, Vt)
    rank = sum(singular :> singular[1] * max((rows(X), cols(X))) * epsilon(1))
    h = rowsum(U[, 1..rank]:^2)
    tolerance = 64 * epsilon(1) * n
    unit = abs(1 :- h) :<= tolerance
    selected = selectindex(unit)
    if (rows(selected)) st_store(observations[selected], residual, J(rows(selected), 1, 0))
    st_local("sd_unit_last", strofreal(unit[n]))
    st_local("sd_unit_count", strofreal(sum(unit)))
}
end
* END SD EXACT-FIT POLICY v2

'@
$sdConfig = @'
[
  {
    "name": "main_construct.do",
    "calls": [
      {
        "old": "qui predict `i'_uq, resid",
        "new": "qui predict `i'_uq, resid\nqui sd_zero_exact_fit `i'_uq, regressors(\"l($cumul/`lagc').`i'_quant l($cumul/`lagc').`i'_plev trend*\")"
      },
      {
        "old": "qui predict `i'_up, resid",
        "new": "qui predict `i'_up, resid\nqui sd_zero_exact_fit `i'_up, regressors(\"l($cumul/`lagc').`i'_quant l($cumul/`lagc').`i'_plev trend*\")"
      }
    ]
  },
  {
    "name": "main_construct_goodsserv.do",
    "calls": [
      {
        "old": "qui predict `i'_uq, resid",
        "new": "qui predict `i'_uq, resid\nqui sd_zero_exact_fit `i'_uq, regressors(\"l(1/$lag).`i'_quant l(1/$lag).`i'_plev\")"
      },
      {
        "old": "qui predict `i'_up, resid",
        "new": "qui predict `i'_up, resid\nqui sd_zero_exact_fit `i'_up, regressors(\"l(1/$lag).`i'_quant l(1/$lag).`i'_plev\")"
      }
    ]
  }
]
'@ | ConvertFrom-Json
$sdRoot = [IO.Path]::GetFullPath($ProgramsPath).TrimEnd('\','/')
if (-not (Test-Path -LiteralPath $sdRoot -PathType Container)) { throw "Programs folder is unavailable: $sdRoot" }
$sdUtf8 = New-Object Text.UTF8Encoding($false, $true)
$sdChanges = @()
foreach ($sdFile in $sdConfig) {
    $sdPath = [IO.Path]::GetFullPath((Join-Path $sdRoot $sdFile.name))
    if (-not $sdPath.StartsWith($sdRoot + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) { throw 'Target outside Programs folder' }
    $sdBefore = [IO.File]::ReadAllBytes($sdPath)
    $sdText = $sdUtf8.GetString($sdBefore)
    if ($sdText.Contains("`r`r`n")) { throw "Unexpected line endings in $sdPath" }
    $sdNewline = if ($sdText.Contains("`r`n")) { "`r`n" } else { "`n" }
    $sdBlock = $sdHelper.Replace("`r`n", "`n").TrimEnd("`r", "`n").Replace("`n", $sdNewline) + $sdNewline
    if ($sdText.Contains('* BEGIN SD EXACT-FIT POLICY v2')) {
        if (-not $sdText.Contains($sdBlock)) { throw "Existing precision helper differs; preserving $sdPath" }
        foreach ($sdCall in $sdFile.calls) {
            if (-not $sdText.Contains($sdCall.new.Replace("`n", $sdNewline))) { throw "Existing precision calls differ; preserving $sdPath" }
        }
        Write-Output "Already current: $sdPath"
        continue
    }
    $sdAnchor = 'set more off' + $sdNewline
    if (($sdText.Split(@($sdAnchor), [StringSplitOptions]::None).Count - 1) -ne 1) { throw "Cannot find unique setup line in $sdPath" }
    $sdAfterText = $sdText.Replace($sdAnchor, $sdAnchor + $sdBlock)
    foreach ($sdCall in $sdFile.calls) {
        if (($sdAfterText.Split(@($sdCall.old), [StringSplitOptions]::None).Count - 1) -ne 1) { throw "Cannot find unique residual prediction in $sdPath" }
        $sdAfterText = $sdAfterText.Replace($sdCall.old, $sdCall.new.Replace("`n", $sdNewline))
    }
    $sdChanges += [pscustomobject]@{Path=$sdPath;Name=$sdFile.name;Before=$sdBefore;After=$sdUtf8.GetBytes($sdAfterText)}
}
# Prepare both patches before writing either file, and preserve original bytes.
$sdBackupRoot = Join-Path $env:LOCALAPPDATA ('SupplyDemandPrecisionFix\' + (Get-Date -Format 'yyyyMMdd_HHmmss_ffff'))
if ($sdChanges.Count) { [IO.Directory]::CreateDirectory($sdBackupRoot) | Out-Null }
foreach ($sdChange in $sdChanges) {
    [IO.File]::WriteAllBytes((Join-Path $sdBackupRoot ($sdChange.Name + '.before')), $sdChange.Before)
    if ([Convert]::ToBase64String([IO.File]::ReadAllBytes($sdChange.Path)) -ne [Convert]::ToBase64String($sdChange.Before)) { throw "File changed concurrently; preserving $($sdChange.Path)" }
}
foreach ($sdChange in $sdChanges) {
    if ([Convert]::ToBase64String([IO.File]::ReadAllBytes($sdChange.Path)) -ne [Convert]::ToBase64String($sdChange.Before)) { throw "File changed concurrently; preserving $($sdChange.Path)" }
    [IO.File]::WriteAllBytes($sdChange.Path, $sdChange.After)
    Write-Output "Updated: $($sdChange.Path)"
}
if ($sdChanges.Count) { Write-Output "Original-byte backups: $sdBackupRoot" }
