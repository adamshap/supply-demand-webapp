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
