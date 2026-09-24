import unittest

from keepalive_testing import load_script, run_main

plan = load_script("scripts/plan.py")


class RungDelaysTest(unittest.TestCase):
    def test_eight_hours_every_forty_starting_at_twenty(self):
        self.assertEqual(plan.rung_delays(8, 40, 20), list(range(20, 461, 40)))

    def test_a_rung_exactly_at_the_horizon_is_included(self):
        self.assertEqual(plan.rung_delays(1, 20, 20), [20, 40, 60])

    def test_a_first_rung_beyond_the_horizon_yields_nothing(self):
        self.assertEqual(plan.rung_delays(0.5, 40, 40), [])


class PlanCliTest(unittest.TestCase):
    def test_prints_index_total_and_minutes_per_rung(self):
        code, out, _ = run_main(plan, "--hours", "8", "--every", "40", "--first", "20")
        lines = out.splitlines()
        self.assertEqual(code, 0)
        self.assertEqual(len(lines), 12)
        self.assertEqual((lines[0], lines[-1]), ("1/12 20", "12/12 460"))

    def test_fractional_minutes_print_without_trailing_zeros(self):
        _, out, _ = run_main(plan, "--hours", "1", "--every", "30", "--first", "0.5")
        self.assertEqual(out.splitlines(), ["1/2 0.5", "2/2 30.5"])

    def test_rejects_a_gap_longer_than_fifty_minutes(self):
        code, _, err = run_main(plan, "--hours", "8", "--every", "51")
        self.assertEqual(code, 2)
        self.assertIn("--every must be <= 50", err)

    def test_requires_hours(self):
        code, _, err = run_main(plan)
        self.assertEqual(code, 2)
        self.assertIn("--hours", err)


if __name__ == "__main__":
    unittest.main()
