# Quantum-inspired subsystem

> **Quantum-inspired = classical algorithms derived from quantum mechanics, run on a
> normal CPU with NumPy only.** No quantum hardware, no quantum SDK. Every run is seeded
> and reproducible; small instances are checked against exhaustive brute force.

Source: `backend/app/services/quantum/`. Tests: `backend/tests/quantum/`.

---

## 1. QUBO / Ising core (`qubo.py`)

A problem is expressed as **QUBO** — minimise `E(x) = xᵀ Q x` over `x ∈ {0,1}ⁿ`, with `Q`
upper-triangular and its diagonal holding the linear coefficients.

`QUBOModel` provides `add_linear`, `add_quadratic`, `add_constant`, and `add_one_hot`
(expands `(Σxᵢ − k)²` into linear + pairwise penalty terms). It converts to the **Ising**
form `E(s) = sᵀ J s + h·s + c`, `s ∈ {−1,+1}ⁿ`, via `xᵢ = (1 + sᵢ)/2`; the conversion is
verified against `QUBOModel.energy` for random instances in `test_qubo_annealer.py`.

`brute_force()` returns the exact global optimum for `n ≤ 22` and is used both as a solver
for tiny instances and as the correctness oracle in tests.

## 2. Solvers (`annealer.py`)

### Simulated Annealing (SA)
Single-spin-flip Metropolis on the Ising model. Inverse temperature `β` follows a
geometric schedule `β₀ → β₁`; `restarts` independent chains are run and the best kept.
The best-so-far energy is recorded every sweep (the convergence curve shown in the UI).

### Simulated Quantum Annealing (SQA)
Discrete-time **path-integral Monte Carlo**. The system is replicated into `P` Trotter
slices coupled along imaginary time by a ferromagnetic term

```
J⊥(Γ) = −(P / 2β) · ln( tanh(β Γ / P) )
```

which **grows without bound as the transverse field `Γ → 0`**, chaining the replicas into
agreement by the end of the schedule. A spin flip in replica `k` costs

```
ΔH_eff = (1/P)·ΔE_classical(sᵏ)  +  2·J⊥·sᵢᵏ·(sᵢᵏ⁻¹ + sᵢᵏ⁺¹)
```

accepted with probability `min(1, e^(−β ΔH_eff))`. `Γ` is swept `Γ₀ → Γ₁ ≈ 0` linearly.
The reported solution is the lowest **true classical** energy across all replicas.

Because SQA can tunnel through energy barriers that trap SA, it matches or beats SA on
frustrated instances; on the Max-Cut benchmark in the test-suite both reach the
brute-force optimum on every trial (`n = 9…13`).

`solve(model, method="auto")` uses brute force for `n ≤ 18`, otherwise SQA.

---

## 3. Application A (hero) — Quantum Exposure Score (`pq_risk.py`)

Per signature / certificate, a **Quantum Exposure Score `QES ∈ [0,100]`** with an
explainable factor breakdown:

| Factor | Meaning | Source |
|---|---|---|
| `algo_factor` | **hard gate.** RSA / DSA / ECDSA / ECDH / EdDSA → 1.0 (Shor-breakable). ML-DSA, SLH-DSA, Falcon, LMS/XMSS → 0.0. | algorithm family |
| `strength_factor` | key size vs. published CRQC resource estimates. RSA-1024→1.0 … RSA-15360→0.22; P-256→0.95 … P-521→0.68 (ECC needs far fewer logical qubits than RSA of equal classical strength, so it is scored *sooner-broken*). | key bits / curve |
| `longevity_factor` | `clip(data_lifetime_years / (qc_year − now), 0, 1)` — the "how long must this stay trustworthy" axis of harvest-now-decrypt-later. | operator input |
| `exposure_factor` | `public 1.0 · transmitted 0.75 · internal 0.35 · sealed 0.1` — can an adversary harvest the artifact today. | operator input |

```
context = weighted_mean(strength, longevity, exposure)
QES     = 100 · algo_factor · (0.2 + 0.8 · context)
band    = ok (<25) · monitor (<50) · plan (<75) · immediate (≥75)
```

The `algo_factor` gate means a post-quantum signature scores **0 regardless** of how
long-lived or exposed the data is. `qc_year` (default `2035`) and the factor weights are
configurable per request and echoed back in `assumptions`.

### Portfolio + migration planner
`/quantum/pq-risk/portfolio` scores every signing identity seen in the lookback window and
persists a `quantum_exposure_scores` row per identity (drives the UI heatmap).

`/quantum/pq-risk/plan` then solves a **scheduling QUBO**: assign each identity to one of
`W` migration waves,

* binary `x[i][w]` with a one-hot penalty (`exactly one wave per identity`),
* objective `Σᵢ QESᵢ · f(criticalityᵢ) · wave(i)` — front-load high risk × criticality,
* per-wave capacity penalty `μ (Σᵢ effortᵢ x[i][w] − C)²`,

solved with SQA and compared against a risk-sorted greedy baseline. The response gives the
wave plan, per-wave load, cumulative risk-exposure-time and the `improvement_pct` over
greedy.

## 4. Application B — Detection tuning (`tuning.py`)

Pick one **weight level** per detection rule from `{0, 0.5, 1.0, 2.0}` so the blended score
`S(event) = Σ_r level(r)·fired(r,event)` best separates malicious from benign events.

* binary `x[r][l]`, one-hot per rule,
* linear reward `−(TP_rate_r − fp_cost · FP_rate_r) · level` (favour high levels for rules
  that fire on attacks and not on benign traffic),
* pairwise penalty on two **redundant** rules (high malicious co-occurrence) both taking a
  high level — keeps the weight vector minimal.

Labelled events come from history (an event is *malicious* if `verdict = invalid` or it
raised an alert) with a synthetic fallback. The response reports precision / recall / F1
**before and after** on the same data; `/quantum/tuning/apply` (admin) writes the tuned
weights into `detection_rules`.

## 5. Application C — Threat correlation (`correlation_qubo.py`)

On the event-similarity graph (`services/detection/correlation.similarity`), repeatedly
extract the subset `S` maximising `Σ_{i<j∈S} (w_ij − γ)` — a resolution-controlled
weighted-clique / densest-subgraph objective. Penalising **every** pair in `S` (not just
`|S|`) stops the solver from merging two disjoint dense clusters. Each `S` becomes one
incident; the residual graph is re-solved for the next. Output includes the Newman
**modularity** of the QUBO grouping and of the Module 3 greedy baseline, side by side.

---

## Reproducibility & limits

* Every solver call takes an explicit `seed`; identical seed ⇒ identical bitstring and
  identical energy trajectory (asserted in tests).
* `optimal` / `optimality_gap` are populated whenever `n ≤ 22` (brute-force oracle).
* Instance sizes are deliberately small (portfolios of tens of identities, correlation
  windows of ≤ 40 events) — this is a decision-support tool, not a large-scale optimiser.
