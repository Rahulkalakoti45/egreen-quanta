"""Module 5 - optional local ML anomaly detection.

Off by default (``ML_ENABLED=false``). When enabled and a model is active, the detection
engine blends an advisory anomaly score into ``risk_score`` and may raise finding T19.
It never overrides a hard cryptographic verdict. All training and scoring is on-box
(scikit-learn); no network calls, no auto-training.
"""
