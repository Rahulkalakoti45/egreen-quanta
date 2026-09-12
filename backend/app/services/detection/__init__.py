"""Module 3 - threat detection engine.

The cryptographic core (Module 2) already emits deterministic findings (T01-T13, T16).
This package:

* persists each verification as a ``VerificationEvent`` with its ``Finding`` rows
* runs *history-aware* rules the stateless core cannot (T14 replay, T15 failure burst)
* blends finding severities and rule weights into a 0-100 risk score
* opens ``Alert`` rows above the threshold and correlates them into ``Incident`` rows
"""
