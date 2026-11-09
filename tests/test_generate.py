import json

from danews.generate import iter_slots, render_messages, run_generate, status


def test_slot_count_matches_spec_ratio(fixture_cfg):
    slots = iter_slots(fixture_cfg)
    # 3 fixture sources × (1 + 3 + 1 + 2 + 1 + 1) archetype-slots = 27; at 40 sources = 360
    assert len(slots) == 27


def test_render_messages_includes_styleguide_and_source(fixture_cfg):
    slot = next(s for s in iter_slots(fixture_cfg) if s.task.id == "t2_rubrik")
    msgs = render_messages(fixture_cfg, slot)
    assert msgs[0]["role"] == "system" and "dansk journalist" in msgs[0]["content"]
    assert "Lynposten" in msgs[1]["content"] or "Landsavisen" in msgs[1]["content"]
    assert slot.source.meta.title in msgs[1]["content"]


def test_generate_is_idempotent_and_writes_valid_outputs(fixture_cfg):
    counts = run_generate(fixture_cfg, models=["fake-echo"])
    assert counts == {"fake-echo": 27}
    again = run_generate(fixture_cfg, models=["fake-echo"])
    assert again == {"fake-echo": 0}
    forced = run_generate(fixture_cfg, models=["fake-echo"], force=True, dry_run=True)
    assert forced == {"fake-echo": 27}
    f = (
        fixture_cfg.paths.outputs
        / "fake-echo"
        / "t4_versionering"
        / "fx-ft-2026-l45__lynposten.json"
    )
    rec = json.loads(f.read_text())
    assert rec["archetype"] == "lynposten" and rec["error"] is None
    assert rec["params"]["max_tokens"] == 275 * 3 + 200
    st = status(fixture_cfg)
    assert st["fake-echo"] == {"expected": 27, "present": 27, "errors": 0}
