import json
import os

import pytest

from nandatown.bundle import load_bundle
from nandatown.campaign import run_campaign
from nandatown.cli import main
from nandatown.replay import render_replay
from nandatown.schemas import export_schemas
from nandatown.sim.runner import run_lab
from nandatown.skills import (
    SkillParseError,
    builtin_skills,
    get_skill,
    parse_skill,
    validate_skill,
)
from nandatown.visualizer import render_visualizer


def test_campaign_precommits_and_aggregates(tmp_path):
    campaign_dir, aggregate = run_campaign("voting", 3, str(tmp_path),
                                           seed_base=500)
    with open(os.path.join(campaign_dir, "campaign.json")) as f:
        plan = json.load(f)
    assert plan["seeds"] == [500, 501, 502]
    assert aggregate["verdicts"] == {"passed": 3}
    assert aggregate["stages"]["tally"]["passed"] == 3
    assert len(aggregate["trial_records"]) == 3
    with open(os.path.join(campaign_dir, "campaign-report.md")) as f:
        text = f.read()
    assert "distribution" in text
    assert "precommitted" in text


def test_campaign_unknown_target(tmp_path):
    with pytest.raises(KeyError):
        run_campaign("nonsense", 2, str(tmp_path))


def test_builtin_skills_parse_and_validate():
    skills = builtin_skills()
    assert "town-protocol" in skills
    assert "quote.read" in skills
    for name in skills:
        from nandatown.skills import skill_source
        assert validate_skill(skill_source(name)) == [], name
    assert get_skill("quote.read").role == "seller"


def test_skill_validation_catches_problems():
    with pytest.raises(SkillParseError):
        parse_skill("no frontmatter here")
    bad = "---\nname: BadName\nversion: 1\ncapability: c\nrole: r\n" \
          "protocol: p\nsummary: s\n---\nbody"
    problems = validate_skill(bad)
    assert any("lowercase" in p for p in problems)
    empty_body = "---\nname: ok.skill\nversion: 1\ncapability: c\n" \
                 "role: r\nprotocol: p\nsummary: s\n---\n"
    assert any("body is empty" in p for p in validate_skill(empty_body))


def test_replay_renders_events(tmp_path):
    bundle_dir, _ = run_lab("auction", str(tmp_path))
    bundle = load_bundle(bundle_dir)
    text = render_replay(bundle, limit=5)
    assert "run_created" in text
    assert "Verdict: PASSED" in text
    only_bids = render_replay(bundle, kind="bid_placed")
    assert only_bids.count("bid_placed") == 2


def test_visualizer_embeds_run(tmp_path):
    bundle_dir, _ = run_lab("marketplace", str(tmp_path))
    bundle = load_bundle(bundle_dir)
    html = render_visualizer(bundle)
    assert "<svg" in html
    assert "escrow_released" in html
    assert "buyer-1" in html
    assert "one scoped observation" in html
    assert "</script>" in html


def test_schema_export(tmp_path):
    written = export_schemas(str(tmp_path))
    names = {os.path.basename(p) for p in written}
    for expected in ["run_plan.schema.json", "agent_message.schema.json",
                     "town_event.schema.json", "release_ref.schema.json",
                     "evidence_record.schema.json", "scenario.schema.json"]:
        assert expected in names
    with open(os.path.join(str(tmp_path), "town_event.schema.json")) as f:
        schema = json.load(f)
    assert "observer" in schema["properties"]


def test_cli_listing_commands(capsys):
    assert main(["scenarios"]) == 0
    assert main(["profiles"]) == 0
    assert main(["layers"]) == 0
    assert main(["skills"]) == 0
    out = capsys.readouterr().out
    assert "marketplace" in out
    assert "quote-crash-restart" in out
    assert "transport" in out and "data_facts" in out
    assert "town-protocol" in out


def test_cli_lab_run_and_tools(tmp_path, capsys):
    out_dir = str(tmp_path / "runs")
    assert main(["run", "voting", "--out", out_dir]) == 0
    run_dir = os.path.join(out_dir, os.listdir(out_dir)[0])
    assert main(["verify", run_dir]) == 0
    assert main(["replay", run_dir, "--limit", "3"]) == 0
    assert main(["visualize", run_dir]) == 0
    assert os.path.exists(os.path.join(run_dir, "town.html"))
    out = capsys.readouterr().out
    assert "Verdict:   PASSED" in out


def test_cli_unknown_target(tmp_path, capsys):
    assert main(["run", "not-a-thing", "--out", str(tmp_path)]) == 2
    out = capsys.readouterr().out
    assert "lab scenarios" in out
