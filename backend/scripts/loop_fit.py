"""Fit the book-value model from the loop's runs so far (2026-11-07; DECISIONS.md, "The book-value
loop").

    uv run python scripts/loop_fit.py

Regresses each run's Forgotten Tomes score (English bits per byte, lower is better) on the shelf:
the realised share of every stratum (kind x original/translated; the shares sum to one, so there is
no intercept and each coefficient is the predicted score of a shelf made only of that stratum),
log2 of the passes, the family entropy and the mean book size in MB, by ridge regression on
standardised extras. Reports the five-fold cross-validated R^2 (how much of the run-to-run spread
the shelf explains) and the coefficients with bootstrap intervals, and writes data/loop/fit.md and
data/loop/fit.json.
"""

from __future__ import annotations

import csv
import json

import numpy as np

from thorp.paths import ROUTER as ROOT  # noqa: E402  (the repository, routed: backend, ships, data)

LOOP = ROOT / "data/loop"
EXTRAS = ["log2_passes", "family_entropy", "mean_book_mb"]


def load():
    rows = [
        r
        for r in csv.DictReader(open(LOOP / "runs.csv", encoding="utf-8"))
        if r["exit"] == "0" and r["ft_bpb_en"]
    ]
    strata = sorted(k[len("share/") :] for k in rows[0] if k.startswith("share/")) if rows else []
    X, y = [], []
    for r in rows:
        shares = [float(r[f"share/{k}"]) for k in strata]
        extras = [
            np.log2(float(r["passes"])),
            float(r["family_entropy"]),
            float(r["mean_book_kb"]) / 1024,
        ]
        X.append(shares + extras)
        y.append(float(r["ft_bpb_en"]))
    return np.array(X), np.array(y), strata


def fit(X, y, k, lam=1e-3):
    mu = X[:, k:].mean(0) if len(X) else 0
    sd = X[:, k:].std(0) + 1e-9 if len(X) else 1
    Z = np.hstack([X[:, :k], (X[:, k:] - mu) / sd])
    pen = np.diag([lam] * k + [1.0] * (Z.shape[1] - k))
    beta = np.linalg.solve(Z.T @ Z + pen, Z.T @ y)
    return beta, mu, sd


def predict(beta, mu, sd, X, k):
    return np.hstack([X[:, :k], (X[:, k:] - mu) / sd]) @ beta


def main() -> None:
    X, y, strata = load()
    k = len(strata)
    n = len(y)
    out = {"runs": n, "strata": strata, "extras": EXTRAS}
    lines = [f"# Book-value fit: {n} runs", ""]
    if n < 12:
        lines.append("Too few runs to fit (need 12); the loop keeps going.")
        (LOOP / "fit.md").write_text("\n".join(lines) + "\n")
        (LOOP / "fit.json").write_text(json.dumps(out, indent=1))
        print("\n".join(lines))
        return
    rng = np.random.default_rng(0)
    idx = rng.permutation(n)
    folds = np.array_split(idx, 5)
    pred = np.zeros(n)
    for f in folds:
        tr = np.setdiff1d(idx, f)
        b, mu, sd = fit(X[tr], y[tr], k)
        pred[f] = predict(b, mu, sd, X[f], k)
    r2 = 1 - ((y - pred) ** 2).sum() / ((y - y.mean()) ** 2).sum()
    beta, mu, sd = fit(X, y, k)
    boots = []
    for _ in range(200):
        s = rng.integers(0, n, n)
        boots.append(fit(X[s], y[s], k)[0])
    lo, hi = np.percentile(boots, [5, 95], axis=0)
    names = [f"pure {s}" for s in strata] + [f"{e} (+1 sd)" for e in EXTRAS]
    out.update(
        {
            "cv_r2": float(r2),
            "score_mean": float(y.mean()),
            "score_sd": float(y.std()),
            "coef": {
                nm: [float(b), float(a), float(c)]
                for nm, b, a, c in zip(names, beta, lo, hi, strict=True)
            },
        }
    )
    lines += [
        f"Forgotten Tomes score across runs: mean {y.mean():.3f}, sd {y.std():.3f} bits per byte (lower is better).",
        f"Cross-validated R^2: {r2:.2f} (share of the run-to-run spread the shelf explains).",
        "",
        "| term | estimate | 90% interval |",
        "| --- | ---: | --- |",
    ]
    for nm, b, a, c in zip(names, beta, lo, hi, strict=True):
        lines.append(f"| {nm} | {b:.3f} | {a:.3f} to {c:.3f} |")
    lines += [
        "",
        "Pure-stratum rows are the predicted score of a shelf made only of that kind (lower is a more valuable kind).",
        "Extra rows are the change in score for one standard deviation more of that feature (negative helps).",
    ]
    (LOOP / "fit.md").write_text("\n".join(lines) + "\n")
    (LOOP / "fit.json").write_text(json.dumps(out, indent=1))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
