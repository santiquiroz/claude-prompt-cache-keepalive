import subprocess
import sys
import unittest

from keepalive_testing import REPO, load_script, run_main

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


class PlanCliValidationTest(unittest.TestCase):
    def run_plan(self, *args):
        return subprocess.run(
            [sys.executable, str(REPO / "scripts" / "plan.py"), *args],
            capture_output=True, text=True, timeout=2,
        )

    def assert_rejected(self, *args):
        result = self.run_plan(*args)
        self.assertEqual(result.returncode, 2, result.stdout)
        self.assertIn("error:", result.stderr)
        self.assertEqual(result.stdout, "")
        return result.stderr

    def test_rejects_a_zero_gap_instead_of_looping_forever(self):
        self.assertIn("--every must be > 0", self.assert_rejected("--hours", "1", "--every", "0"))

    def test_rejects_a_negative_gap_instead_of_looping_forever(self):
        self.assertIn("--every must be > 0", self.assert_rejected("--hours", "1", "--every", "-10"))

    def test_rejects_a_first_rung_at_zero(self):
        self.assertIn("--first must be > 0", self.assert_rejected("--hours", "8", "--first", "0"))

    def test_rejects_a_first_rung_after_the_cache_expires(self):
        self.assertIn("--first must be > 0 and <= 50", self.assert_rejected("--hours", "8", "--first", "55"))

    def test_rejects_zero_hours_instead_of_printing_nothing(self):
        self.assertIn("--hours must be", self.assert_rejected("--hours", "0"))

    def test_rejects_infinite_hours_instead_of_looping_forever(self):
        self.assertIn("--hours must be", self.assert_rejected("--hours", "inf"))

    def test_accepts_a_first_rung_right_at_fifty(self):
        result = self.run_plan("--hours", "1", "--first", "50")
        self.assertEqual((result.returncode, result.stdout.splitlines()), (0, ["1/1 50"]))

    def test_eight_hours_prints_the_twelve_rungs_without_warning(self):
        result = self.run_plan("--hours", "8", "--every", "40", "--first", "20")
        expected = [f"{index}/12 {20 + 40 * (index - 1)}" for index in range(1, 13)]
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.splitlines(), expected)
        self.assertEqual(result.stderr, "")

    def test_warns_when_the_ladder_has_more_than_twenty_ticks(self):
        result = self.run_plan("--hours", "16", "--every", "40", "--first", "20")
        self.assertEqual(result.returncode, 0)
        self.assertEqual(len(result.stdout.splitlines()), 24)
        self.assertIn("warning: 24 ticks", result.stderr)
        self.assertIn("more than 20", result.stderr)


if __name__ == "__main__":
    unittest.main()
