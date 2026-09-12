"""Module 4 - quantum-inspired optimisation.

Classical algorithms derived from quantum mechanics, run on a normal CPU with NumPy
only. No quantum hardware, no quantum SDK. Every run is seeded and reproducible, and
small instances are checked against brute force.

* ``qubo``            - QUBO / Ising model builder + exact brute-force solver
* ``annealer``        - simulated annealing + simulated *quantum* annealing (path-integral)
* ``pq_risk``         - per-signature Quantum Exposure Score + PQC migration planner (hero)
* ``tuning``          - detection weight/threshold tuning as a QUBO
* ``correlation_qubo``- max-weight-clique / community incident grouping as a QUBO
"""
