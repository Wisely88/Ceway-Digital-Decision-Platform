from __future__ import annotations

import unittest

from multiregime_v25 import DLT, ROLE_WEIGHTS, generate_multiregime_plan, score_regimes


def make_history(count: int = 80) -> list[dict]:
    rows = []
    for index in range(1, count + 1):
        front = sorted({
            ((index * 3 + 0) % 35) + 1,
            ((index * 5 + 7) % 35) + 1,
            ((index * 7 + 11) % 35) + 1,
            ((index * 9 + 17) % 35) + 1,
            ((index * 11 + 23) % 35) + 1,
        })
        while len(front) < 5:
            candidate = ((index + len(front) * 13) % 35) + 1
            if candidate not in front:
                front.append(candidate)
                front.sort()
        back = sorted({((index * 2) % 12) + 1, ((index * 5 + 3) % 12) + 1})
        while len(back) < 2:
            candidate = ((index + 7) % 12) + 1
            if candidate not in back:
                back.append(candidate)
                back.sort()
        rows.append({"issue": f"26{index:03d}", "front": front, "back": back})
    return rows


class MultiRegimeV25Tests(unittest.TestCase):
    def test_scores_are_bounded_and_ranked(self) -> None:
        rows = score_regimes(make_history(), DLT, area="front")
        self.assertEqual(len(rows), 35)
        for row in rows:
            self.assertGreaterEqual(row["evidence_score"], 0.0)
            self.assertLessEqual(row["evidence_score"], 1.0)
            self.assertGreaterEqual(row["scarcity_score"], 0.0)
            self.assertLessEqual(row["scarcity_score"], 1.0)
            self.assertIn("evidence_rank", row)
            self.assertIn("scarcity_rank", row)

    def test_cutoff_blocks_future_data(self) -> None:
        history = make_history(80)
        cutoff = history[59]["issue"]
        base = score_regimes(history[:60], DLT, area="front", history_cutoff_issue=cutoff)
        with_future = score_regimes(history, DLT, area="front", history_cutoff_issue=cutoff)
        self.assertEqual(base, with_future)

    def test_short_term_absence_can_rank_as_scarce_without_overwriting_evidence(self) -> None:
        history = make_history(80)
        # Force number 35 to have long-window presence but no presence in the last 7 draws.
        for row in history[:-7:5]:
            if 35 not in row["front"]:
                row["front"][-1] = 35
                row["front"] = sorted(set(row["front"]))
                while len(row["front"]) < 5:
                    for candidate in range(1, 36):
                        if candidate not in row["front"]:
                            row["front"].append(candidate)
                            break
                row["front"].sort()
        for row in history[-7:]:
            if 35 in row["front"]:
                row["front"].remove(35)
                for candidate in range(1, 36):
                    if candidate not in row["front"]:
                        row["front"].append(candidate)
                        break
                row["front"].sort()
        rows = score_regimes(history, DLT, area="front")
        row35 = next(row for row in rows if row["number"] == 35)
        self.assertLessEqual(row35["scarcity_rank"], 12)
        self.assertNotEqual(row35["scarcity_rank"], row35["evidence_rank"])

    def test_plan_uses_preregistered_role_mix_and_is_deterministic(self) -> None:
        history = make_history(80)
        first = generate_multiregime_plan(history, DLT, budget=20)
        second = generate_multiregime_plan(history, DLT, budget=20)
        self.assertEqual(first["items"], second["items"])
        self.assertEqual(first["production_enabled"], False)
        front_targets = first["coverage_diagnostics"]["front"]["role_slot_targets"]
        self.assertEqual(sum(front_targets.values()), 50)
        self.assertEqual(front_targets["evidence"], round(50 * ROLE_WEIGHTS["evidence"]))
        self.assertEqual(front_targets["scarcity"], round(50 * ROLE_WEIGHTS["scarcity"]))
        self.assertLessEqual(first["coverage_diagnostics"]["front"]["max_pair_reuse"], 3)


if __name__ == "__main__":
    unittest.main()
