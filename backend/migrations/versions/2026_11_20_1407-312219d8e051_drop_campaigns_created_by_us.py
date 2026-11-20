"""drop campaigns created_by_us

Revision ID: 312219d8e051
Revises: 2257e6247b94
Create Date: 2026-11-20 14:07:43.337663

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '312219d8e051'
down_revision: Union[str, Sequence[str], None] = '2257e6247b94'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """«Наша» кампания определяется префиксом названия (FR-2.1), отдельный флаг не нужен."""
    op.drop_column('campaigns', 'created_by_us')


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        'campaigns',
        sa.Column('created_by_us', sa.Boolean(), server_default=sa.false(), nullable=False),
    )
