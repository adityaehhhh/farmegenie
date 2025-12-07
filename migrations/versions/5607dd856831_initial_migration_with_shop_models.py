"""Initial migration with shop models

Revision ID: 5607dd856831
Revises: 
Create Date: 2025-09-13 13:27:38.530647
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision = '5607dd856831'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Create the custom role enum
    role_enum = postgresql.ENUM('FARMER', 'COMPANY', 'FARM_IND', name='role', create_type=True)
    role_enum.create(op.get_bind(), checkfirst=True)

    # Add the role column to the existing user table
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.add_column(sa.Column('role', postgresql.ENUM('FARMER', 'COMPANY', 'FARM_IND', name='role'), nullable=False, server_default='FARMER'))
        batch_op.alter_column('username',
               existing_type=sa.VARCHAR(length=64),
               type_=sa.String(length=150),
               existing_nullable=False)
        batch_op.alter_column('email',
               existing_type=sa.VARCHAR(length=255),
               type_=sa.String(length=150),
               existing_nullable=False)
        batch_op.alter_column('password_hash',
               existing_type=sa.VARCHAR(length=512),
               type_=sa.String(length=128),
               existing_nullable=False)

    # Create new tables for shop functionality
    op.create_table('crop_post',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=200), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('soil_nutrients', sa.Text(), nullable=True),
        sa.Column('quality', sa.String(length=100), nullable=True),
        sa.Column('quantity', sa.Float(), nullable=True),
        sa.Column('rate', sa.Float(), nullable=True),
        sa.Column('farmer_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['farmer_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('product',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('type', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('price', sa.Float(), nullable=True),
        sa.Column('quantity_available', sa.Integer(), nullable=True),
        sa.Column('farm_ind_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['farm_ind_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('message',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('sender_id', sa.Integer(), nullable=False),
        sa.Column('receiver_id', sa.Integer(), nullable=False),
        sa.Column('crop_post_id', sa.Integer(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('is_read', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['crop_post_id'], ['crop_post.id'], ),
        sa.ForeignKeyConstraint(['receiver_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['sender_id'], ['user.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_table('purchase',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('buyer_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=True),
        sa.Column('total_price', sa.Float(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['buyer_id'], ['user.id'], ),
        sa.ForeignKeyConstraint(['product_id'], ['product.id'], ),
        sa.PrimaryKeyConstraint('id')
    )

def downgrade():
    with op.batch_alter_table('user', schema=None) as batch_op:
        batch_op.drop_column('role')
        batch_op.alter_column('password_hash',
               existing_type=sa.String(length=128),
               type_=sa.VARCHAR(length=512),
               existing_nullable=False)
        batch_op.alter_column('email',
               existing_type=sa.String(length=150),
               type_=sa.VARCHAR(length=255),
               existing_nullable=False)
        batch_op.alter_column('username',
               existing_type=sa.String(length=150),
               type_=sa.VARCHAR(length=64),
               existing_nullable=False)
    op.drop_table('purchase')
    op.drop_table('message')
    op.drop_table('product')
    op.drop_table('crop_post')
    op.execute('DROP TYPE role')