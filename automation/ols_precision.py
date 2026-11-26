"""Recognize exactly fitted OLS observations at machine precision."""
import numpy as np


def unit_leverage_rows(x: np.ndarray) -> np.ndarray:
    """h_ii=1 implies e_i=0 for every dependent variable in an OLS fit.

    Constant columns are removed explicitly. The intercept is included in the
    SVD itself, keeping the projection orthonormal even with ill-conditioned
    lag matrices. Scaling regressors does not change the OLS column space.
    """
    n = len(x)
    varying = np.ptp(x, axis=0) > 0
    design = np.ones((n, 1), dtype=float) / np.sqrt(n)
    if varying.any():
        centered = x[:, varying] - x[:, varying].mean(axis=0)
        centered /= np.linalg.norm(centered, axis=0)
        design = np.column_stack([design, centered])
    u, singular, _ = np.linalg.svd(design, full_matrices=False)
    rank = int(np.sum(singular > singular[0] * max(design.shape) * np.finfo(float).eps))
    h = np.sum(u[:, :rank] ** 2, axis=1)
    tolerance = 64 * np.finfo(float).eps * max(n, x.shape[1] + 1)
    return np.abs(1 - h) <= tolerance


def standardized_residuals(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """Same OLS and score convention as Stata, with exact-fit residuals zeroed."""
    xc, yc = x - x.mean(axis=0), y - y.mean(axis=0)
    beta = np.linalg.lstsq(xc, yc, rcond=None)[0]
    errors = (yc - xc @ beta).astype('float32').astype(float)
    unit = unit_leverage_rows(x)
    errors[unit] = 0
    sd = errors.std(axis=0, ddof=1)
    if not np.isfinite(sd).all():
        raise ValueError('Invalid residual dispersion')
    with np.errstate(divide='ignore', invalid='ignore'):
        score = (errors[-1] / sd).astype('float32')
    # Preserve Stata's missing-score ordering for a constant dependent series.
    score[(np.ptp(y, axis=0) == 0) | ~np.isfinite(score)] = np.inf
    return score, unit
