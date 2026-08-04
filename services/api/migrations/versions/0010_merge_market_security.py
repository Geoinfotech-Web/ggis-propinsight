"""merge market and FCT-wide security migration branches

Revision ID: 0010_merge_market_security
Revises: 0009_market_listing_details, 0008_fct_wide_security
Create Date: 2026-08-04
"""
from __future__ import annotations

revision = "0010_merge_market_security"
down_revision = ("0009_market_listing_details", "0008_fct_wide_security")
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
