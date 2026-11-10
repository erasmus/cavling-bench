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
    assert rec["params"]["reasoning_effort"] is None
    st = status(fixture_cfg)
    assert st["fake-echo"] == {"expected": 27, "present": 27, "errors": 0}


def test_generate_records_effective_params_for_reasoning_models(fixture_cfg):
    model = next(m for m in fixture_cfg.models if m.id == "fake-echo")
    model.reasoning_effort = "low"
    model.reasoning_budget_tokens = 1500
    run_generate(fixture_cfg, models=["fake-echo"])
    f = (
        fixture_cfg.paths.outputs
        / "fake-echo"
        / "t4_versionering"
        / "fx-ft-2026-l45__lynposten.json"
    )
    rec = json.loads(f.read_text())
    assert rec["params"]["max_tokens"] == 275 * 3 + 200 + 1500
    assert rec["params"]["reasoning_effort"] == "low"


def test_generate_records_tokens_and_cost_for_empty_completions(fixture_cfg):
    model = next(m for m in fixture_cfg.models if m.id == "fake-echo")
    model.litellm_model = "fake/empty"
    model.price_out_per_m = 2.0
    run_generate(fixture_cfg, models=["fake-echo"])
    f = (
        fixture_cfg.paths.outputs
        / "fake-echo"
        / "t4_versionering"
        / "fx-ft-2026-l45__lynposten.json"
    )
    rec = json.loads(f.read_text())
    assert rec["error"] and rec["error"].startswith("EmptyCompletion")
    assert rec["text"] == ""
    assert rec["completion_tokens"] > 0 and rec["cost_usd"] > 0


def test_generate_retries_outputs_that_recorded_an_error(fixture_cfg):
    run_generate(fixture_cfg, models=["fake-echo"])
    f = fixture_cfg.paths.outputs / "fake-echo" / "t1_telegram" / "fx-dst-2026-ledighed.json"
    rec = json.loads(f.read_text())
    rec["text"], rec["error"] = "", "RateLimitError: quota"
    f.write_text(json.dumps(rec))
    assert run_generate(fixture_cfg, models=["fake-echo"]) == {"fake-echo": 1}
    assert json.loads(f.read_text())["error"] is None
