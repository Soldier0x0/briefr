"""SigmaHQ local detection rule index tables (SH-1).

Revision ID: 035_detection_rules_sigmahq
Revises: 034_ai_operation_payloads
Create Date: 2026-07-23

Postgres-native only — no SQLite dual dialect for these tables.
"""

from __future__ import annotations

from alembic import op

revision = "035_detection_rules_sigmahq"
down_revision = "034_ai_operation_payloads"
branch_labels = None
depends_on = None

_LICENSE_URL = (
    "https://github.com/SigmaHQ/Detection-Rule-License/"
    "blob/main/LICENSE.Detection.Rules.md"
)


def upgrade() -> None:
    op.execute(
        f"""
        CREATE TABLE IF NOT EXISTS detection_rules (
            id              BIGSERIAL PRIMARY KEY,
            source          TEXT NOT NULL CHECK (source = 'sigmahq'),
            repo_path       TEXT NOT NULL,
            rule_uid        TEXT NOT NULL,
            title           TEXT NOT NULL DEFAULT '',
            status          TEXT NOT NULL DEFAULT 'experimental',
            author          TEXT NOT NULL DEFAULT '',
            description     TEXT NOT NULL DEFAULT '',
            level           TEXT,
            rule_family     TEXT NOT NULL DEFAULT 'rules',
            tags            JSONB NOT NULL DEFAULT '[]'::jsonb,
            -- "references" is a Postgres reserved word (FK syntax); must be quoted.
            "references"    JSONB NOT NULL DEFAULT '[]'::jsonb,
            logsource       JSONB,
            content_yaml    TEXT NOT NULL,
            content_sha256  TEXT NOT NULL,
            commit_sha      TEXT NOT NULL,
            license_id      TEXT NOT NULL DEFAULT 'DRL-1.1',
            license_url     TEXT NOT NULL DEFAULT '{_LICENSE_URL}',
            html_url        TEXT NOT NULL DEFAULT '',
            retired_at      TIMESTAMPTZ,
            created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            updated_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
            UNIQUE (source, repo_path)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS detection_rules_active_idx
        ON detection_rules (source) WHERE retired_at IS NULL
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS detection_rule_cves (
            rule_id     BIGINT NOT NULL REFERENCES detection_rules(id) ON DELETE CASCADE,
            cve_id      TEXT NOT NULL,
            match_basis TEXT NOT NULL DEFAULT 'cve_exact'
                        CHECK (match_basis = 'cve_exact'),
            PRIMARY KEY (rule_id, cve_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS detection_rule_cves_cve_idx
        ON detection_rule_cves (cve_id)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS detection_rule_techniques (
            rule_id       BIGINT NOT NULL REFERENCES detection_rules(id) ON DELETE CASCADE,
            technique_id  TEXT NOT NULL,
            PRIMARY KEY (rule_id, technique_id)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS detection_rule_techniques_tid_idx
        ON detection_rule_techniques (technique_id)
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS detection_rule_techniques_tid_idx")
    op.execute("DROP TABLE IF EXISTS detection_rule_techniques")
    op.execute("DROP INDEX IF EXISTS detection_rule_cves_cve_idx")
    op.execute("DROP TABLE IF EXISTS detection_rule_cves")
    op.execute("DROP INDEX IF EXISTS detection_rules_active_idx")
    op.execute("DROP TABLE IF EXISTS detection_rules")
