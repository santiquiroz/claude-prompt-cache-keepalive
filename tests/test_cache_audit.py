import json
import os
import pathlib
import tempfile
import unittest

from keepalive_testing import load_script, run_main

cache_audit = load_script("scripts/cache_audit.py")


def assistant(message_id, read, written, timestamp="2026-09-23T10:00:00Z", **extra):
    usage = {"cache_read_input_tokens": read, "cache_creation_input_tokens": written}
    return {"type": "assistant", "timestamp": timestamp, "message": {"id": message_id, "usage": usage}, **extra}


def write_transcript(path, entries, mtime=None):
    path.write_text("\n".join(json.dumps(entry) for entry in entries) + "\n", encoding="utf-8")
    if mtime is not None:
        os.utime(path, (mtime, mtime))
    return path


class CacheAuditTest(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.dir = pathlib.Path(temp.name)

    def test_counts_each_main_thread_assistant_message_once(self):
        transcript = write_transcript(self.dir / "s.jsonl", [
            {"type": "user", "message": {"content": "hola"}},
            assistant("m1", 100, 0, timestamp="t1"),
            assistant("m1", 100, 0, timestamp="t1-again"),
            assistant("m2", 5, 0, isSidechain=True),
            {"type": "assistant", "message": {"id": "m3"}},
            assistant("m4", 200, 10, timestamp="t4"),
        ])
        timestamps = [timestamp for timestamp, _ in cache_audit.assistant_usages(transcript)]
        self.assertEqual(timestamps, ["t1", "t4"])

    def test_flags_a_large_write_without_reads_as_cold(self):
        transcript = write_transcript(self.dir / "s.jsonl", [
            assistant("m1", 400_000, 2_000, timestamp="warm-turn"),
            assistant("m2", 1_000, 400_000, timestamp="cold-turn"),
            assistant("m3", 0, 40_000, timestamp="small-write"),
        ])
        _, out, _ = run_main(cache_audit, str(transcript))
        verdicts = {line.split()[0]: line.rsplit("  ", 1)[-1] for line in out.splitlines()}
        self.assertEqual(verdicts, {"warm-turn": "warm", "cold-turn": "COLD (cache lost)", "small-write": "warm"})

    def test_last_limits_the_rows_to_the_most_recent_turns(self):
        transcript = write_transcript(self.dir / "s.jsonl", [assistant(f"m{i}", i, 0, timestamp=f"t{i}") for i in range(5)])
        _, out, _ = run_main(cache_audit, str(transcript), "--last", "2")
        self.assertEqual([line.split()[0] for line in out.splitlines()], ["t3", "t4"])

    def test_a_folder_audits_its_newest_transcript(self):
        write_transcript(self.dir / "old.jsonl", [assistant("m1", 1, 0, timestamp="old")], mtime=1_000_000)
        write_transcript(self.dir / "new.jsonl", [assistant("m1", 1, 0, timestamp="new")], mtime=1_000_000 + 7200)
        _, out, _ = run_main(cache_audit, str(self.dir))
        lines = out.splitlines()
        self.assertEqual(lines[0], "auditing new.jsonl")
        self.assertEqual(lines[1].split()[0], "new")
        self.assertNotIn("warning", out)

    def test_warns_when_another_session_changed_in_the_last_hour(self):
        write_transcript(self.dir / "a.jsonl", [assistant("m1", 1, 0)], mtime=1_000_000)
        write_transcript(self.dir / "b.jsonl", [assistant("m1", 1, 0)], mtime=1_000_000 + 60)
        _, out, _ = run_main(cache_audit, str(self.dir))
        self.assertIn("warning: 2 sessions changed in the last hour", out)

    def test_a_folder_without_transcripts_exits_with_a_message(self):
        code, _, _ = run_main(cache_audit, str(self.dir))
        self.assertEqual(code, f"no *.jsonl transcripts in {self.dir}")


if __name__ == "__main__":
    unittest.main()
