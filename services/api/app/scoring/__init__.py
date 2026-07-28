"""Scoring engine (TDD §4.4).

Each domain score is a weighted multi-criteria aggregation of normalised
indicators. Weights live in the `scoring_profiles` table (configuration, not
code) so methodology updates are auditable and reproducible. The composite
"AIA Index" is deliberately secondary — per-domain scores with evidence are
the primary product.
"""
