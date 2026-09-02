"""Keep FCT planning/land-use active under state readiness gating.

Revision ID: 0019_fct_masterplan_readiness
Revises: 0018_national_admin_gis
Create Date: 2026-09-02
"""
from __future__ import annotations

from alembic import op

revision = "0019_fct_masterplan_readiness"
down_revision = "0018_national_admin_gis"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        INSERT INTO state_layer_registry (state_code, layer, version, status, source, notes, updated_at)
        VALUES ('FC', 'masterplan', '2026.09.seed', 'published', 'Existing FCT pilot layers', NULL, NOW())
        ON CONFLICT (state_code, layer) DO UPDATE SET
          version = '2026.09.seed',
          status = 'published',
          source = 'Existing FCT pilot layers',
          notes = NULL,
          updated_at = NOW()
        """
    )
    op.execute(
        """
        UPDATE states
        SET readiness = 'ready', published = TRUE, updated_at = NOW()
        WHERE code = 'FC'
        """
    )

def downgrade() -> None:
    op.execute(
        """
        UPDATE state_layer_registry
        SET version = 'unpublished',
            status = 'unpublished',
            source = NULL,
            notes = 'Awaiting admin upload or ETL publish',
            updated_at = NOW()
        WHERE state_code = 'FC' AND layer = 'masterplan'
        """
    )
