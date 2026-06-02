"""
hmm.py — Gaussian Hidden Markov Model, pure Python (no numpy/hmmlearn).

A diagonal-covariance Gaussian HMM trained by Baum-Welch (EM), with:
  * fit()            — EM training in log-space (numerically stable)
  * filter_states()  — CAUSAL posterior P(state_t | obs_1..t): uses ONLY past data.
                       THIS is what trading decisions must use (no look-ahead).
  * smooth_states()  — forward-backward posterior P(state_t | ALL obs): uses the
                       full sequence => look-ahead. For visualization ONLY.
  * viterbi()        — most-likely path (also full-sequence => look-ahead label).
  * score()          — log-likelihood of a sequence (for model selection).

Why pure Python: it runs in this sandbox and on your machine with zero install.
For production you can swap in hmmlearn.GaussianHMM behind the same interface; this
implementation is validated against synthetic data with planted regimes (see
verify_hmm.py). 7 states x 3 features x a few thousand hourly bars trains in seconds.
"""
from __future__ import annotations

import math
import random

NEG_INF = float("-inf")


def logsumexp(vals: list[float]) -> float:
    m = max(vals)
    if m == NEG_INF:
        return NEG_INF
    return m + math.log(sum(math.exp(v - m) for v in vals))


class GaussianHMM:
    def __init__(self, n_states: int, n_features: int,
                 max_iter: int = 60, tol: float = 1e-4,
                 min_var: float = 1e-6, self_trans_prior: float = 0.95,
                 seed: int = 1337):
        self.N = n_states
        self.D = n_features
        self.max_iter = max_iter
        self.tol = tol
        self.min_var = min_var
        self.self_trans_prior = self_trans_prior
        self.seed = seed
        # parameters (set by fit)
        self.log_start: list[float] = []
        self.log_trans: list[list[float]] = []
        self.means: list[list[float]] = []
        self.vars: list[list[float]] = []
        self.converged_ = False
        self.loglik_ = NEG_INF
        self.n_iter_ = 0

    # ------------------------------------------------------------------ #
    # emissions
    # ------------------------------------------------------------------ #
    def _log_gaussian(self, x: list[float], k: int) -> float:
        mean, var = self.means[k], self.vars[k]
        s = 0.0
        for d in range(self.D):
            v = var[d]
            diff = x[d] - mean[d]
            s += math.log(2.0 * math.pi * v) + (diff * diff) / v
        return -0.5 * s

    def _log_emit_matrix(self, X) -> list[list[float]]:
        return [[self._log_gaussian(x, k) for k in range(self.N)] for x in X]

    # ------------------------------------------------------------------ #
    # init
    # ------------------------------------------------------------------ #
    def _init_params(self, X, seed):
        rng = random.Random(seed)
        T = len(X)
        # global per-feature mean/var
        gmean = [sum(x[d] for x in X) / T for d in range(self.D)]
        gvar = [max(self.min_var, sum((x[d] - gmean[d]) ** 2 for x in X) / T)
                for d in range(self.D)]
        # means seeded from distinct random observations
        idx = rng.sample(range(T), self.N) if T >= self.N else [rng.randrange(T) for _ in range(self.N)]
        self.means = [list(X[i]) for i in idx]
        self.vars = [list(gvar) for _ in range(self.N)]
        self.log_start = [math.log(1.0 / self.N)] * self.N
        # sticky transitions: regimes persist (a sensible prior for markets)
        p = self.self_trans_prior
        off = (1.0 - p) / (self.N - 1) if self.N > 1 else 0.0
        self.log_trans = [[math.log(p if j == k else off) for k in range(self.N)]
                          for j in range(self.N)]

    # ------------------------------------------------------------------ #
    # forward / backward (log-space)
    # ------------------------------------------------------------------ #
    def _forward(self, log_emit) -> tuple[list[list[float]], float]:
        T = len(log_emit)
        la = [[NEG_INF] * self.N for _ in range(T)]
        for k in range(self.N):
            la[0][k] = self.log_start[k] + log_emit[0][k]
        for t in range(1, T):
            for k in range(self.N):
                la[t][k] = log_emit[t][k] + logsumexp(
                    [la[t - 1][j] + self.log_trans[j][k] for j in range(self.N)])
        return la, logsumexp(la[T - 1])

    def _backward(self, log_emit) -> list[list[float]]:
        T = len(log_emit)
        lb = [[NEG_INF] * self.N for _ in range(T)]
        for k in range(self.N):
            lb[T - 1][k] = 0.0
        for t in range(T - 2, -1, -1):
            for k in range(self.N):
                lb[t][k] = logsumexp(
                    [self.log_trans[k][j] + log_emit[t + 1][j] + lb[t + 1][j]
                     for j in range(self.N)])
        return lb

    # ------------------------------------------------------------------ #
    # training
    # ------------------------------------------------------------------ #
    def _snapshot(self):
        return ([r[:] for r in [self.log_start]][0][:], [r[:] for r in self.log_trans],
                [m[:] for m in self.means], [v[:] for v in self.vars])

    def _restore(self, snap):
        ls, lt, mu, vr = snap
        self.log_start, self.log_trans, self.means, self.vars = ls[:], [r[:] for r in lt], \
            [m[:] for m in mu], [v[:] for v in vr]

    def fit(self, X, n_init: int = 1, backend: str = "python"):
        """Fit by Baum-Welch EM with n_init random restarts (keeps best log-lik).

        backend: "python" (default) uses the pure implementation here; "hmmlearn"
        (or "auto" if hmmlearn is installed) fits ~100x faster via hmmlearn and loads
        the resulting params back into THIS object — so filter/smooth/viterbi (and the
        causal no-look-ahead guarantee) are identical regardless of backend.
        """
        if len(X) < self.N:
            raise ValueError("need at least n_states observations")
        if backend in ("auto", "hmmlearn"):
            try:
                return self._fit_hmmlearn(X, n_init)
            except ImportError:
                if backend == "hmmlearn":
                    raise  # explicitly requested but unavailable
                # backend == "auto": silently fall through to pure-Python
        best = None
        for i in range(max(1, n_init)):
            self._init_params(X, seed=self.seed + i * 101)
            loglik, n_iter, conv = self._em(X)
            if best is None or loglik > best[0]:
                best = (loglik, self._snapshot(), n_iter, conv)
        self._restore(best[1])
        self.loglik_, self.n_iter_, self.converged_ = best[0], best[2], best[3]
        return self

    def _fit_hmmlearn(self, X, n_init):
        """Fit with hmmlearn, then copy params into self for our own inference."""
        import numpy as np
        from hmmlearn.hmm import GaussianHMM as _HL  # ImportError -> caller decides

        arr = np.asarray(X, dtype=float)
        best = None
        for i in range(max(1, n_init)):
            m = _HL(n_components=self.N, covariance_type="diag", n_iter=self.max_iter,
                    tol=self.tol, min_covar=self.min_var, random_state=self.seed + i,
                    init_params="stmc", params="stmc")
            m.fit(arr)
            try:
                ll = float(m.score(arr))
            except Exception:
                ll = float("-inf")
            if best is None or ll > best[0]:
                best = (ll, m)
        ll, m = best
        eps = 1e-300
        cov = np.asarray(m.covars_)
        if cov.ndim == 3:                       # (N,d,d) -> diagonal
            cov = np.stack([np.diag(c) for c in cov])
        self.log_start = [math.log(max(float(p), eps)) for p in m.startprob_]
        self.log_trans = [[math.log(max(float(p), eps)) for p in row] for row in m.transmat_]
        self.means = [[float(v) for v in row] for row in m.means_]
        self.vars = [[max(self.min_var, float(v)) for v in row] for row in cov]
        self.loglik_ = ll
        self.n_iter_ = int(getattr(m.monitor_, "iter", self.max_iter))
        self.converged_ = bool(getattr(m.monitor_, "converged", True))
        return self

    def _em(self, X):
        """One EM run from current init. Mutates params; returns (loglik, iters, conv)."""
        prev = NEG_INF
        converged = False
        n_iter = 0
        for it in range(self.max_iter):
            log_emit = self._log_emit_matrix(X)
            la, loglik = self._forward(log_emit)
            lb = self._backward(log_emit)
            T = len(X)

            # gamma[t][k] = P(state_t=k | X)
            gamma = [[0.0] * self.N for _ in range(T)]
            for t in range(T):
                tot = logsumexp([la[t][k] + lb[t][k] for k in range(self.N)])
                for k in range(self.N):
                    gamma[t][k] = math.exp(la[t][k] + lb[t][k] - tot)

            # xi sums: sum_t P(state_t=j, state_{t+1}=k | X)
            xi_sum = [[0.0] * self.N for _ in range(self.N)]
            for t in range(T - 1):
                denom = logsumexp(
                    [la[t][j] + self.log_trans[j][k] + log_emit[t + 1][k] + lb[t + 1][k]
                     for j in range(self.N) for k in range(self.N)])
                for j in range(self.N):
                    for k in range(self.N):
                        xi_sum[j][k] += math.exp(
                            la[t][j] + self.log_trans[j][k] + log_emit[t + 1][k]
                            + lb[t + 1][k] - denom)

            # M-step
            self.log_start = [math.log(max(gamma[0][k], 1e-300)) for k in range(self.N)]
            for j in range(self.N):
                row = sum(xi_sum[j])
                if row <= 0:
                    self.log_trans[j] = [math.log(1.0 / self.N)] * self.N
                else:
                    self.log_trans[j] = [math.log(max(xi_sum[j][k] / row, 1e-300))
                                         for k in range(self.N)]
            for k in range(self.N):
                w = sum(gamma[t][k] for t in range(T))
                if w <= 0:
                    continue
                self.means[k] = [sum(gamma[t][k] * X[t][d] for t in range(T)) / w
                                 for d in range(self.D)]
                self.vars[k] = [max(self.min_var,
                                    sum(gamma[t][k] * (X[t][d] - self.means[k][d]) ** 2
                                        for t in range(T)) / w)
                                for d in range(self.D)]

            n_iter = it + 1
            if loglik - prev < self.tol and it > 0:
                converged = True
                break
            prev = loglik
        return loglik, n_iter, converged

    # ------------------------------------------------------------------ #
    # inference
    # ------------------------------------------------------------------ #
    def filter_states(self, X) -> list[list[float]]:
        """CAUSAL posterior at each t using only obs_1..t. Use this for trading."""
        log_emit = self._log_emit_matrix(X)
        T = len(X)
        out = []
        la_prev = None
        for t in range(T):
            if t == 0:
                la = [self.log_start[k] + log_emit[0][k] for k in range(self.N)]
            else:
                la = [log_emit[t][k] + logsumexp(
                    [la_prev[j] + self.log_trans[j][k] for j in range(self.N)])
                    for k in range(self.N)]
            la_prev = la
            z = logsumexp(la)
            out.append([math.exp(v - z) for v in la])
        return out

    def smooth_states(self, X) -> list[list[float]]:
        """Full-sequence posterior (forward-backward). LOOK-AHEAD — viz only."""
        log_emit = self._log_emit_matrix(X)
        la, _ = self._forward(log_emit)
        lb = self._backward(log_emit)
        T = len(X)
        out = []
        for t in range(T):
            z = logsumexp([la[t][k] + lb[t][k] for k in range(self.N)])
            out.append([math.exp(la[t][k] + lb[t][k] - z) for k in range(self.N)])
        return out

    def viterbi(self, X) -> list[int]:
        """Most-likely state path. Full-sequence => look-ahead label; viz only."""
        log_emit = self._log_emit_matrix(X)
        T = len(X)
        dp = [[NEG_INF] * self.N for _ in range(T)]
        bp = [[0] * self.N for _ in range(T)]
        for k in range(self.N):
            dp[0][k] = self.log_start[k] + log_emit[0][k]
        for t in range(1, T):
            for k in range(self.N):
                best, arg = NEG_INF, 0
                for j in range(self.N):
                    val = dp[t - 1][j] + self.log_trans[j][k]
                    if val > best:
                        best, arg = val, j
                dp[t][k] = best + log_emit[t][k]
                bp[t][k] = arg
        last = max(range(self.N), key=lambda k: dp[T - 1][k])
        path = [last]
        for t in range(T - 1, 0, -1):
            path.append(bp[t][path[-1]])
        return path[::-1]

    def score(self, X) -> float:
        _, ll = self._forward(self._log_emit_matrix(X))
        return ll
