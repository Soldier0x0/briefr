"""SigmaHQ local index — parse + apply + watermark (SH-1 / U1)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from detection.sigmahq_index import (
    LICENSE_ID,
    LICENSE_URL,
    SOURCE,
    apply_rules_from_dir,
    extract_cve_ids,
    extract_technique_ids,
    find_index_rules_for_cve,
    index_active_count,
    is_rule_path,
    parse_sigma_file,
    rule_family_from_path,
    sync_sigmahq_index,
)
from feeds.file_identity import (
    SIGMAHQ_ARCHIVE_IDENTITY_KEY,
    get_file_identity,
)
from tests.conftest import run_db_test

FIXTURE_ROOT = Path(__file__).resolve().parent / "fixtures" / "sigmahq_mini"
_VERSIONS_DIR = Path(__file__).resolve().parents[1] / "alembic" / "versions"

pytestmark_pg = pytest.mark.skipif(
    not os.environ.get("DATABASE_URL", "").startswith("postgresql"),
    reason="DATABASE_URL not set to PostgreSQL",
)


def test_035_revision_file_and_chain():
    path = _VERSIONS_DIR / "035_detection_rules_sigmahq.py"
    source = path.read_text(encoding="utf-8")
    assert 'revision = "035_detection_rules_sigmahq"' in source
    assert 'down_revision = "034_ai_operation_payloads"' in source
    assert "detection_rules" in source
    assert "detection_rule_cves" in source
    assert "detection_rule_techniques" in source
    assert "DRL-1.1" in source


def test_rule_path_and_family():
    assert is_rule_path("rules/web/foo.yml")
    assert is_rule_path("rules-emerging-threats/bar.yml")
    assert is_rule_path("rules-threat-hunting/x.yml")
    assert is_rule_path("rules-compliance/y.yml")
    assert not is_rule_path("docs/README.md")
    assert not is_rule_path("tests/test.yml")
    assert rule_family_from_path("rules/web/a.yml") == "rules"
    assert rule_family_from_path("rules-emerging-threats/a.yml") == "emerging"
    assert rule_family_from_path("rules-threat-hunting/a.yml") == "hunting"
    assert rule_family_from_path("rules-compliance/a.yml") == "compliance"


def test_extract_cves_and_techniques():
    cves = extract_cve_ids(
        tags=["cve.2021.44228", "attack.t1190"],
        references=["https://nvd.nist.gov/vuln/detail/CVE-2021-44228"],
        title="Log4Shell",
        description="x",
        repo_path="rules/web/web_cve_2021_44228_shell.yml",
    )
    assert "CVE-2021-44228" in cves
    techs = extract_technique_ids(["attack.t1059.001", "attack.t1190", "cve.2021.1"])
    assert techs == ["T1059.001", "T1190"]


def test_parse_fixture_log4shell():
    path = FIXTURE_ROOT / "rules/web/web_cve_2021_44228_shell.yml"
    text = path.read_text(encoding="utf-8")
    rule = parse_sigma_file(
        repo_path="rules/web/web_cve_2021_44228_shell.yml",
        content=text,
        commit_sha="abc123deadbeefabc123deadbeefabc123deadbeef",
    )
    assert rule is not None
    assert rule.title.startswith("Web Shell")
    assert rule.author == "SigmaHQ Fixture Author"
    assert "CVE-2021-44228" in rule.cve_ids
    assert "T1190" in rule.technique_ids
    assert rule.rule_family == "rules"
    assert LICENSE_ID == "DRL-1.1"
    assert "author: SigmaHQ Fixture Author" in rule.content_yaml


def test_parse_corrupt_yaml():
    rule = parse_sigma_file(
        repo_path="rules/bad.yml",
        content="title: x\n detection: [\n",
        commit_sha="abc",
    )
    assert rule is None


def test_parse_path_only_cve():
    path = FIXTURE_ROOT / "rules-emerging-threats/cve_2024_1234_probe.yml"
    text = path.read_text(encoding="utf-8")
    rule = parse_sigma_file(
        repo_path="rules-emerging-threats/cve_2024_1234_probe.yml",
        content=text,
        commit_sha="abc",
    )
    assert rule is not None
    assert "CVE-2024-1234" in rule.cve_ids
    assert rule.rule_family == "emerging"


@pytest.mark.postgres_migrations
@pytestmark_pg
def test_apply_fixture_upsert_cve_and_technique():
    async def run():
        from database import get_db

        db = await get_db()
        # Isolate prior rows from other tests.
        await db.execute("DELETE FROM detection_rules WHERE source = $1", (SOURCE,))
        await db.commit()

        stats = await apply_rules_from_dir(
            db, FIXTURE_ROOT, commit_sha="fixturecommit001fixturecommit001fixture00"
        )
        assert not stats.failed
        assert stats.seen == 3
        assert stats.upserted == 3

        count = await index_active_count(db)
        assert count == 3

        cve_rows = await db.execute_fetchall(
            """
            SELECT c.cve_id, c.match_basis, r.repo_path, r.license_id, r.license_url, r.author
            FROM detection_rule_cves c
            JOIN detection_rules r ON r.id = c.rule_id
            WHERE c.cve_id = $1 AND r.retired_at IS NULL
            """,
            ("CVE-2021-44228",),
        )
        assert len(cve_rows) == 1
        assert cve_rows[0]["license_id"] == LICENSE_ID
        assert cve_rows[0]["license_url"] == LICENSE_URL
        assert "Fixture Author" in cve_rows[0]["author"]
        assert cve_rows[0]["match_basis"] == "cve_exact"

        tech_rows = await db.execute_fetchall(
            """
            SELECT t.technique_id FROM detection_rule_techniques t
            JOIN detection_rules r ON r.id = t.rule_id
            WHERE r.repo_path LIKE '%powershell%'
            """
        )
        tids = {r["technique_id"] for r in tech_rows}
        assert "T1059.001" in tids

        packed = await find_index_rules_for_cve(db, "CVE-2021-44228")
        assert len(packed) == 1
        assert packed[0]["match_basis"] == "cve_exact"
        assert packed[0]["license"] == LICENSE_ID
        assert "SigmaHQ" in packed[0]["attribution"]
        assert packed[0]["content"]

    run_db_test(run())


@pytest.mark.postgres_migrations
@pytestmark_pg
def test_apply_watermark_noop_and_retire():
    async def run():
        from database import get_db

        db = await get_db()
        await db.execute("DELETE FROM detection_rules WHERE source = $1", (SOURCE,))
        await db.commit()

        commit = "fixturecommit002fixturecommit002fixture00"
        r1 = await sync_sigmahq_index(
            db,
            tip_commit=commit,
            extract_root=FIXTURE_ROOT,
            force=True,
        )
        assert r1.status == "applied"
        assert r1.stats.seen == 3

        ident = await get_file_identity(db, SIGMAHQ_ARCHIVE_IDENTITY_KEY)
        assert ident is not None
        assert ident.get("commit_sha") == commit
        assert ident.get("sha256")

        r2 = await sync_sigmahq_index(
            db,
            tip_commit=commit,
            extract_root=FIXTURE_ROOT,
            force=False,
        )
        # Same tip + extract_root bypasses commit-skip when extract_root set;
        # second apply should mostly skip unchanged.
        assert r2.status == "applied"
        assert r2.stats.skipped_unchanged == 3
        assert r2.stats.upserted == 0

        # Retire: apply from a subset directory (only windows rule).
        subset = FIXTURE_ROOT / "rules" / "windows"
        # apply_rules_from_dir expects trees with rules/ prefix — build temp layout
        import tempfile
        from pathlib import Path as P

        with tempfile.TemporaryDirectory() as tmp:
            root = P(tmp)
            dest = root / "rules" / "windows"
            dest.mkdir(parents=True)
            src = FIXTURE_ROOT / "rules" / "windows" / "proc_powershell_enc.yml"
            (dest / src.name).write_text(src.read_text(encoding="utf-8"), encoding="utf-8")
            stats = await apply_rules_from_dir(db, root, commit_sha=commit)
            assert stats.retired == 2
            active = await index_active_count(db)
            assert active == 1

            # Re-add full tree → clear retired
            stats2 = await apply_rules_from_dir(db, FIXTURE_ROOT, commit_sha=commit)
            active_after = await index_active_count(db)
            assert active_after == 3
            assert stats2.upserted >= 2  # reactivated + any content touch

    run_db_test(run())


@pytest.mark.postgres_migrations
@pytestmark_pg
def test_content_sha_updates_on_change():
    async def run():
        import tempfile
        from pathlib import Path as P

        from database import get_db

        db = await get_db()
        await db.execute("DELETE FROM detection_rules WHERE source = $1", (SOURCE,))
        await db.commit()

        with tempfile.TemporaryDirectory() as tmp:
            root = P(tmp)
            dest = root / "rules" / "web"
            dest.mkdir(parents=True)
            path = dest / "one.yml"
            path.write_text(
                "title: One\nid: d4444444-4444-4444-8444-444444444444\n"
                "author: A\ntags: [cve.2020.1]\n"
                "logsource: {category: web}\n"
                "detection: {selection: {a: 1}, condition: selection}\n",
                encoding="utf-8",
            )
            s1 = await apply_rules_from_dir(db, root, commit_sha="c1")
            assert s1.upserted == 1
            row = await db.execute_fetchall(
                "SELECT content_sha256 FROM detection_rules WHERE repo_path = $1",
                ("rules/web/one.yml",),
            )
            sha1 = row[0]["content_sha256"]
            path.write_text(
                "title: One changed\nid: d4444444-4444-4444-8444-444444444444\n"
                "author: A\ntags: [cve.2020.1]\n"
                "logsource: {category: web}\n"
                "detection: {selection: {a: 2}, condition: selection}\n",
                encoding="utf-8",
            )
            s2 = await apply_rules_from_dir(db, root, commit_sha="c2")
            assert s2.upserted == 1
            row2 = await db.execute_fetchall(
                "SELECT content_sha256, title, commit_sha FROM detection_rules WHERE repo_path = $1",
                ("rules/web/one.yml",),
            )
            assert row2[0]["content_sha256"] != sha1
            assert row2[0]["title"] == "One changed"
            assert row2[0]["commit_sha"] == "c2"

    run_db_test(run())


@pytest.mark.postgres_migrations
@pytestmark_pg
def test_sync_skips_when_tip_unchanged():
    async def run():
        from database import get_db

        db = await get_db()
        await db.execute("DELETE FROM detection_rules WHERE source = $1", (SOURCE,))
        await db.commit()

        commit = "fixturecommit003fixturecommit003fixture00"
        r1 = await sync_sigmahq_index(
            db, tip_commit=commit, extract_root=FIXTURE_ROOT, force=True
        )
        assert r1.status == "applied"

        # No extract_root / archive → tip match should skip without re-apply.
        r2 = await sync_sigmahq_index(db, tip_commit=commit, force=False)
        assert r2.status == "skipped_commit"

    run_db_test(run())


def test_file_identity_sigmahq_payload_shape(tmp_path, monkeypatch):
    """Identity helper stores commit_sha + sha256 without requiring Postgres tables."""
    db_path = tmp_path / "sigma_id.db"
    monkeypatch.delenv("DATABASE_URL", raising=False)
    monkeypatch.setenv("BRIEFR_REQUIRE_POSTGRES", "0")
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("PROCRASTINATE_ENABLED", "0")

    from settings import settings as _settings

    monkeypatch.setattr(_settings, "database_url", "")
    monkeypatch.setattr(_settings, "db_path", str(db_path))
    monkeypatch.setattr(_settings, "briefr_require_postgres", False)

    from database import get_db, init_db
    from feeds.file_identity import (
        SIGMAHQ_ARCHIVE_IDENTITY_KEY,
        clear_file_identity,
        commit_identity_matches,
        get_file_identity,
        set_file_identity,
    )

    async def _run():
        await init_db()
        db = await get_db()
        try:
            await set_file_identity(
                db,
                SIGMAHQ_ARCHIVE_IDENTITY_KEY,
                sha256="deadbeef",
                commit_sha="abc",
                synced_at="2026-07-23T00:00:00Z",
                score_date=None,
            )
            await db.commit()
            ident = await get_file_identity(db, SIGMAHQ_ARCHIVE_IDENTITY_KEY)
            assert ident["sha256"] == "deadbeef"
            assert ident["commit_sha"] == "abc"
            assert "score_date" not in ident
            assert commit_identity_matches(ident, commit_sha="abc")
            await clear_file_identity(db, SIGMAHQ_ARCHIVE_IDENTITY_KEY)
            await db.commit()
            assert await get_file_identity(db, SIGMAHQ_ARCHIVE_IDENTITY_KEY) is None
        finally:
            await db.close()

    run_db_test(_run())
