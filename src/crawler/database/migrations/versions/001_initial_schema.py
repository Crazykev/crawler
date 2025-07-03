"""Initial schema creation

Revision ID: 001
Revises: 
Create Date: 2025-07-03 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision: str = '001'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Create initial database schema."""
    
    # Create crawl_results table
    op.create_table(
        'crawl_results',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('job_id', sa.String(length=255), nullable=True),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('title', sa.String(length=1024), nullable=True),
        sa.Column('success', sa.Boolean(), nullable=False),
        sa.Column('status_code', sa.Integer(), nullable=True),
        sa.Column('content_markdown', sa.Text(), nullable=True),
        sa.Column('content_html', sa.Text(), nullable=True),
        sa.Column('content_text', sa.Text(), nullable=True),
        sa.Column('extracted_data', sa.JSON(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for crawl_results
    op.create_index('idx_crawl_results_job_url', 'crawl_results', ['job_id', 'url'])
    op.create_index('idx_crawl_results_success', 'crawl_results', ['success'])
    op.create_index('idx_crawl_results_status', 'crawl_results', ['status_code'])
    op.create_index('idx_crawl_results_created', 'crawl_results', ['created_at'])
    op.create_index('ix_crawl_results_job_id', 'crawl_results', ['job_id'])
    op.create_index('ix_crawl_results_url', 'crawl_results', ['url'])
    
    # Create crawl_links table
    op.create_table(
        'crawl_links',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('crawl_result_id', sa.Integer(), nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('text', sa.String(length=1024), nullable=True),
        sa.Column('link_type', sa.String(length=50), nullable=False),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['crawl_result_id'], ['crawl_results.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for crawl_links
    op.create_index('idx_crawl_links_url', 'crawl_links', ['url'])
    op.create_index('idx_crawl_links_type', 'crawl_links', ['link_type'])
    op.create_index('ix_crawl_links_crawl_result_id', 'crawl_links', ['crawl_result_id'])
    
    # Create crawl_media table
    op.create_table(
        'crawl_media',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('crawl_result_id', sa.Integer(), nullable=False),
        sa.Column('url', sa.String(length=2048), nullable=False),
        sa.Column('media_type', sa.String(length=50), nullable=False),
        sa.Column('alt_text', sa.String(length=1024), nullable=True),
        sa.Column('width', sa.Integer(), nullable=True),
        sa.Column('height', sa.Integer(), nullable=True),
        sa.Column('file_size', sa.Integer(), nullable=True),
        sa.Column('metadata', sa.JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.ForeignKeyConstraint(['crawl_result_id'], ['crawl_results.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create indexes for crawl_media
    op.create_index('idx_crawl_media_url', 'crawl_media', ['url'])
    op.create_index('idx_crawl_media_type', 'crawl_media', ['media_type'])
    op.create_index('ix_crawl_media_crawl_result_id', 'crawl_media', ['crawl_result_id'])
    
    # Create browser_sessions table
    op.create_table(
        'browser_sessions',
        sa.Column('session_id', sa.String(length=255), nullable=False),
        sa.Column('config', sa.JSON(), nullable=True),
        sa.Column('state_data', sa.JSON(), nullable=True),
        sa.Column('page_count', sa.Integer(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False),
        sa.Column('last_accessed', sa.DateTime(timezone=True), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('session_id')
    )
    
    # Create indexes for browser_sessions
    op.create_index('idx_browser_sessions_active', 'browser_sessions', ['is_active'])
    op.create_index('idx_browser_sessions_expires', 'browser_sessions', ['expires_at'])
    op.create_index('idx_browser_sessions_last_accessed', 'browser_sessions', ['last_accessed'])
    
    # Create cache_entries table
    op.create_table(
        'cache_entries',
        sa.Column('cache_key', sa.String(length=512), nullable=False),
        sa.Column('data_value', sa.JSON(), nullable=True),
        sa.Column('data_type', sa.String(length=100), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('access_count', sa.Integer(), nullable=False),
        sa.Column('last_accessed', sa.DateTime(timezone=True), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('cache_key')
    )
    
    # Create indexes for cache_entries
    op.create_index('idx_cache_entries_expires', 'cache_entries', ['expires_at'])
    op.create_index('idx_cache_entries_access_count', 'cache_entries', ['access_count'])
    op.create_index('idx_cache_entries_last_accessed', 'cache_entries', ['last_accessed'])
    
    # Create job_queue table
    op.create_table(
        'job_queue',
        sa.Column('job_id', sa.String(length=255), nullable=False),
        sa.Column('job_type', sa.Enum('SCRAPE_SINGLE', 'SCRAPE_BATCH', 'CRAWL_SITE', 'SESSION_OPERATION', name='jobtype'), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'RUNNING', 'COMPLETED', 'FAILED', 'CANCELLED', name='jobstatus'), nullable=False),
        sa.Column('priority', sa.Integer(), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('job_data', sa.JSON(), nullable=True),
        sa.Column('result_data', sa.JSON(), nullable=True),
        sa.Column('error_message', sa.String(length=2048), nullable=True),
        sa.Column('retry_count', sa.Integer(), nullable=False),
        sa.Column('max_retries', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('(CURRENT_TIMESTAMP)'), nullable=False),
        sa.PrimaryKeyConstraint('job_id')
    )
    
    # Create indexes for job_queue
    op.create_index('idx_job_queue_status_priority', 'job_queue', ['status', 'priority'])
    op.create_index('idx_job_queue_type', 'job_queue', ['job_type'])
    op.create_index('idx_job_queue_created', 'job_queue', ['created_at'])
    op.create_index('idx_job_queue_started', 'job_queue', ['started_at'])
    op.create_index('idx_job_queue_completed', 'job_queue', ['completed_at'])


def downgrade() -> None:
    """Drop all tables."""
    op.drop_table('job_queue')
    op.drop_table('cache_entries')
    op.drop_table('browser_sessions')
    op.drop_table('crawl_media')
    op.drop_table('crawl_links')
    op.drop_table('crawl_results')