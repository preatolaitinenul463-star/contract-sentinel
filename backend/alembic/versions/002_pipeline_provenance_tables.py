"""Add pipeline, provenance, verification, and approval tables.

Revision ID: 002_pipeline
Revises: 001_initial
Create Date: 2026-02-09
"""
from alembic import op
import sqlalchemy as sa

revision = "002_pipeline"
down_revision = None  # adjust to your actual head revision id
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pipeline_runs
    op.create_table(
        "pipeline_runs",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("run_id", sa.String(32), unique=True, index=True, nullable=False),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), index=True, nullable=True),
        sa.Column("feature", sa.String(20), nullable=False),
        sa.Column("mode", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), default="running"),
        sa.Column("input_hash", sa.String(64), nullable=True),
        sa.Column("jurisdiction", sa.String(10), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("ended_at", sa.DateTime(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), default=0),
        sa.Column("total_tokens_input", sa.Integer(), default=0),
        sa.Column("total_tokens_output", sa.Integer(), default=0),
        sa.Column("trace_id", sa.String(64), nullable=True),
        sa.Column("result_summary", sa.JSON(), nullable=True),
        sa.Column("artifact_paths", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # pipeline_events
    op.create_table(
        "pipeline_events",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("run_id", sa.String(32), sa.ForeignKey("pipeline_runs.run_id"), index=True),
        sa.Column("stage", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False),
        sa.Column("progress", sa.Integer(), default=0),
        sa.Column("message", sa.String(500), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("duration_ms", sa.Integer(), default=0),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # provenance_sources
    op.create_table(
        "provenance_sources",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("run_id", sa.String(32), sa.ForeignKey("pipeline_runs.run_id"), index=True),
        sa.Column("source_id", sa.String(10), nullable=False),
        sa.Column("trusted", sa.Boolean(), default=False),
        sa.Column("kind", sa.String(20), default="other"),
        sa.Column("title", sa.String(500), nullable=True),
        sa.Column("url", sa.String(2000), nullable=True),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("institution", sa.String(200), nullable=True),
        sa.Column("published_date", sa.DateTime(), nullable=True),
        sa.Column("retrieved_at", sa.DateTime(), nullable=True),
    )

    # verification_results
    op.create_table(
        "verification_results",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("run_id", sa.String(32), sa.ForeignKey("pipeline_runs.run_id"), index=True),
        sa.Column("rule_id", sa.String(50), nullable=False),
        sa.Column("passed", sa.Boolean(), default=True),
        sa.Column("detail", sa.Text(), nullable=True),
        sa.Column("action", sa.String(30), default="pass"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
    )

    # approval_tasks
    op.create_table(
        "approval_tasks",
        sa.Column("id", sa.Integer(), primary_key=True, index=True),
        sa.Column("run_id", sa.String(32), sa.ForeignKey("pipeline_runs.run_id"), unique=True, index=True),
        sa.Column("state", sa.String(20), default="draft"),
        sa.Column("reviewer_user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("comment", sa.Text(), nullable=True),
        sa.Column("export_enabled", sa.Boolean(), default=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_table("approval_tasks")
    op.drop_table("verification_results")
    op.drop_table("provenance_sources")
    op.drop_table("pipeline_events")
    op.drop_table("pipeline_runs")
