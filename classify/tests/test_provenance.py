from pathlib import Path

import pytest

from classify import config, prompts, provenance
from classify.tests.conftest import lot

COMPONENTS = ("input_sha", "prompt_sha", "buckets_sha", "profile_sha", "passes_sha",
              "contract_version", "worker_sha", "instructions_sha", "model")


def parts(repo):
    lots = [lot(i) for i in range(1, 6)]
    path = config.pass_input_path("test", "a")
    config.write_json(path, lots)
    return provenance.components(input_path=path, prompt_text=prompts.build("a", lots))


def test_every_documented_component_is_present(repo):
    assert set(parts(repo)) == set(COMPONENTS)


def test_model_is_the_exact_id_not_the_alias(repo):
    assert parts(repo)["model"] == "claude-sonnet-5"
    assert provenance.MODEL_ID != "sonnet"


@pytest.mark.parametrize("target,label", [
    ("buckets.yaml", "buckets_sha"),
    ("profile.yaml", "profile_sha"),
    ("passes.yaml", "passes_sha"),
    (".claude/agents/lot-classifier.md", "worker_sha"),
    ("CLAUDE.md", "instructions_sha"),
])
def test_each_component_moves_independently(repo, target, label):
    before = parts(repo)
    path = repo / target
    path.write_text(path.read_text(encoding="utf-8") + "\n# edit\n", encoding="utf-8")
    after = parts(repo)
    assert after[label] != before[label], f"{label} should track {target}"
    assert provenance.fingerprint(after) != provenance.fingerprint(before)


def test_editing_the_input_changes_the_fingerprint(repo):
    before = parts(repo)
    config.write_json(config.pass_input_path("test", "a"), [lot(i) for i in range(1, 7)])
    after = provenance.components(
        input_path=config.pass_input_path("test", "a"),
        prompt_text=prompts.build("a", [lot(i) for i in range(1, 7)]),
    )
    assert after["input_sha"] != before["input_sha"]


def test_instructions_sha_is_path_independent(tmp_path, monkeypatch):
    """The repo lives at different paths on the two machines; identical content
    must produce an identical hash, or every cross-machine run looks stale."""
    shas = []
    for name in ("projects", "code"):
        root = tmp_path / name / "encore-browser"
        (root / ".claude").mkdir(parents=True)
        (root / "CLAUDE.md").write_text("# same instructions\n", encoding="utf-8")
        home = tmp_path / name / "home"
        (home / ".claude").mkdir(parents=True)
        monkeypatch.setattr(config, "REPO_ROOT", root)
        monkeypatch.setattr(Path, "home", classmethod(lambda cls, h=home: h))
        shas.append(provenance.instructions_sha())
    assert shas[0] == shas[1]


def test_a_user_level_claude_md_appearing_changes_the_hash(tmp_path, monkeypatch):
    """Absence must be part of the hash — this is the silent-divergence case."""
    root = tmp_path / "repo"
    (root / ".claude").mkdir(parents=True)
    (root / "CLAUDE.md").write_text("# project\n", encoding="utf-8")
    home = tmp_path / "home"
    (home / ".claude").mkdir(parents=True)
    monkeypatch.setattr(config, "REPO_ROOT", root)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))

    without = provenance.instructions_sha()
    (home / ".claude" / "CLAUDE.md").write_text("# personal prefs\n", encoding="utf-8")
    assert provenance.instructions_sha() != without


def test_absent_files_are_recorded_rather_than_skipped(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / ".claude").mkdir(parents=True)
    (root / "CLAUDE.md").write_text("# project\n", encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(config, "REPO_ROOT", root)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    entries = provenance.instruction_entries()
    roles = {e["role"]: e["sha"] for e in entries}
    assert roles["user:CLAUDE.md"] == provenance.ABSENT
    assert roles["project:CLAUDE.md"] != provenance.ABSENT


def test_nested_claude_md_is_included(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    (root / "sub").mkdir(parents=True)
    (root / "CLAUDE.md").write_text("# project\n", encoding="utf-8")
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setattr(config, "REPO_ROOT", root)
    monkeypatch.setattr(Path, "home", classmethod(lambda cls: home))
    before = provenance.instructions_sha()
    (root / "sub" / "CLAUDE.md").write_text("# nested\n", encoding="utf-8")
    assert provenance.instructions_sha() != before
    assert any(e["role"] == "project:sub/CLAUDE.md"
               for e in provenance.instruction_entries())
