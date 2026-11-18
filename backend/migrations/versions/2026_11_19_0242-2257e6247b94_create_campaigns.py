"""create campaigns

Revision ID: 2257e6247b94
Revises: 
Create Date: 2026-11-19 02:42:12.417977

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = '2257e6247b94'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('campaigns',
    sa.Column('id', sa.BigInteger(), autoincrement=False, nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('alias', sa.String(length=255), nullable=False),
    sa.Column('domain_url', sa.String(length=255), nullable=True),
    sa.Column('created_by_us', sa.Boolean(), nullable=False),
    sa.Column('streams', postgresql.JSONB(astext_type=sa.Text()), nullable=False),
    sa.Column('version', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.PrimaryKeyConstraint('id', name=op.f('pk_campaigns'))
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('campaigns')
