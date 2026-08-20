import unittest

from predictor_v9 import DLT, SSQ, generate_prediction_v9, score_numbers_v9


def make_history(spec, count=120):
    rows = []
    for issue in range(1, count + 1):
        if spec.game == "DLT":
            front = [((issue + offset * 3) % 35) + 1 for offset in range(5)]
            back = [((issue + offset * 5) % 12) + 1 for offset in range(2)]
            front = sorted(set(front))
            back = sorted(set(back))
            while len(front) < 5:
                front.append(len(front) + 1)
                front = sorted(set(front))
            while len(back) < 2:
                back.append(len(back) + 1)
                back = sorted(set(back))
        else:
            front = [((issue + offset * 3) % 33) + 1 for offset in range(6)]
            back = [((issue * 2) % 16) + 1]
            front = sorted(set(front))
            while len(front) < 6:
                front.append(len(front) + 1)
                front = sorted(set(front))
        rows.append(
            {
                "issue": str(issue),
                "date": f"2026-01-{((issue - 1) % 28) + 1:02d}",
                "front": front,
                "back": back,
            }
        )
    return rows


class PredictorV9Tests(unittest.TestCase):
    def test_score_table_is_complete(self):
        history = make_history(DLT)
        result = score_numbers_v9(history, DLT)
        self.assertEqual(len(result["front"]), 35)
        self.assertEqual(len(result["back"]), 12)
        self.assertEqual({row["number"] for row in result["front"]}, set(range(1, 36)))

    def test_prediction_respects_budget_and_unique_tickets(self):
        history = make_history(DLT)
        plan = generate_prediction_v9(history, DLT, budget=20, seed="test")
        self.assertEqual(plan["tickets"], 10)
        self.assertEqual(plan["budget"], 20)
        keys = {(tuple(item["front"]), tuple(item["back"])) for item in plan["items"]}
        self.assertEqual(len(keys), 10)

    def test_ssq_prediction_shape(self):
        history = make_history(SSQ)
        plan = generate_prediction_v9(history, SSQ, budget=20, seed="test")
        self.assertEqual(plan["tickets"], 10)
        self.assertTrue(all(len(item["front"]) == 6 for item in plan["items"]))
        self.assertTrue(all(len(item["back"]) == 1 for item in plan["items"]))

    def test_freeze_is_deterministic(self):
        history = make_history(DLT)
        first = generate_prediction_v9(
            history, DLT, budget=20, seed="freeze", history_cutoff_issue="120"
        )
        second = generate_prediction_v9(
            history, DLT, budget=20, seed="freeze", history_cutoff_issue="120"
        )
        self.assertEqual(first["items"], second["items"])

    def test_cutoff_blocks_future_data(self):
        history = make_history(DLT)
        baseline = generate_prediction_v9(
            history[:90], DLT, budget=20, seed="cutoff", history_cutoff_issue="90"
        )
        leaked_tail = generate_prediction_v9(
            history, DLT, budget=20, seed="cutoff", history_cutoff_issue="90"
        )
        self.assertEqual(baseline["items"], leaked_tail["items"])
        self.assertEqual(baseline["history_cutoff_issue"], "90")


if __name__ == "__main__":
    unittest.main()
