from collections import Counter

from danews.pairs import schedule

MODELS = [f"m{i}" for i in range(8)]


def test_every_model_in_at_least_four_pairs():
    pairs = schedule(MODELS, "t4_versionering/src__lynposten")
    c = Counter()
    for p in pairs:
        c[p.left] += 1
        c[p.right] += 1
    assert all(c[m] >= 4 for m in MODELS)
    assert len(pairs) == 16  # 4 rounds × 4 pairs; nothing redundant
    assert len({frozenset((p.left, p.right)) for p in pairs}) == len(pairs)


def test_left_right_balanced_per_model():
    counts = {m: [0, 0] for m in MODELS}
    for slot in range(40):
        for p in schedule(MODELS, f"t2_rubrik/src{slot}__landsavisen"):
            counts[p.left][0] += 1
            counts[p.right][1] += 1
    for m, (left, right) in counts.items():
        assert abs(left - right) <= 0.15 * (left + right), (m, left, right)


def test_deterministic_and_varies_by_slot():
    a = schedule(MODELS, "t6_lydmanus/s1__lynposten")
    b = schedule(MODELS, "t6_lydmanus/s1__lynposten")
    c = schedule(MODELS, "t6_lydmanus/s2__lynposten")
    assert a == b
    assert a != c


def test_odd_and_small_counts():
    pairs = schedule(MODELS[:7], "x")
    c = Counter([p.left for p in pairs] + [p.right for p in pairs])
    assert all(v >= 4 for v in c.values())
    assert schedule(["a", "b"], "x") == [schedule(["a", "b"], "x")[0]]
    assert schedule(["a"], "x") == []
