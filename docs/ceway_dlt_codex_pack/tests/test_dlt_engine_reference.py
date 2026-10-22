from reference.dlt_engine_reference import (
    Draw,
    Ticket,
    aggregate_collision_profiles,
    bet_cost_yuan,
    collision_profile,
    compound_bet_count,
    current_omission,
    dantuo_bet_count,
    front_structure,
    generate_random_singles,
    hit_pair,
)


def fixture_draws():
    return [
        Draw.create("1", [1, 2, 3, 4, 5], [1, 2]),
        Draw.create("2", [1, 6, 7, 8, 9], [1, 3]),
        Draw.create("3", [10, 11, 12, 13, 14], [4, 5]),
    ]


def test_hit_pair_and_collision_profile():
    draws = fixture_draws()
    t = Ticket.create([1, 2, 6, 10, 20], [1, 5])
    assert hit_pair(t, draws[0]) == (2, 1)  # total 3
    assert hit_pair(t, draws[1]) == (2, 1)  # total 3
    assert hit_pair(t, draws[2]) == (1, 1)  # total 2
    p = collision_profile(t, draws)
    assert p.n_total_hits == (0, 0, 1, 2, 0, 0, 0, 0)
    assert p.n_front_back[2][1] == 2
    assert p.n_front_back[1][1] == 1
    assert sum(p.n_total_hits) == 3
    assert sum(sum(r) for r in p.n_front_back) == 3
    assert p.scarcity_key == (0, 0, 0, 0, 2, 1, 0)


def test_aggregate_m_and_u():
    draws = fixture_draws()
    p1 = collision_profile(Ticket.create([1, 2, 6, 10, 20], [1, 5]), draws)
    p2 = collision_profile(Ticket.create([30, 31, 32, 33, 34], [11, 12]), draws)
    agg = aggregate_collision_profiles([p1, p2])
    assert agg["m_total_hits"][0] == 3  # second ticket misses all three draws
    assert agg["m_total_hits"][2] == 1
    assert agg["m_total_hits"][3] == 2
    assert agg["u_total_hits"][0] == 1
    assert agg["u_total_hits"][2] == 1
    assert agg["u_total_hits"][3] == 1


def test_compound_formula():
    assert compound_bet_count(6, 3) == 18
    assert bet_cost_yuan(18, addon=False, multiplier=1) == 36
    assert bet_cost_yuan(18, addon=True, multiplier=1) == 54


def test_dantuo_formula():
    # 2 front dan + 5 tuo => C(5,3)=10; 1 back dan + 3 tuo => C(3,1)=3
    assert dantuo_bet_count(2, 5, 1, 3) == 30


def test_structure():
    s = front_structure([2, 13, 19, 28, 31])
    assert s["zones"] == (1, 2, 2)
    assert s["odd"] == 3
    assert s["sum"] == 93


def test_random_seed_reproducible_and_unique():
    a = generate_random_singles(10, seed=42)
    b = generate_random_singles(10, seed=42)
    assert a == b
    assert len({(t.front, t.back) for t in a}) == 10


def test_omission():
    draws = fixture_draws()
    o = current_omission(draws, zone="front")
    assert o[10] == 0
    assert o[1] == 1
    assert o[35] == 3
