import contextlib
import io
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import run_report_pipeline as pipeline


class PipelineTranscriptBackupTests(unittest.TestCase):
    def fixture(self, root, *, dry_run=False, missing_zh=0):
        manifest = root / "manifest.json"
        manifest.write_text(json.dumps({"run_id": "fixture", "summary": {"new_episode_count": 1}}))
        evidence = root / "evidence.json"
        evidence.write_text(json.dumps({"summary": {"missing_count": 0}}))
        audit = root / "languages.json"
        audit.write_text(json.dumps({"summary": {"chinese_missing_count": missing_zh}}))
        args = SimpleNamespace(manifest=manifest, move_imported_transcripts=False,
                               require_zh_transcripts=False, dry_run=dry_run,
                               gemini_mode="single", model="fixture")
        def run(command):
            name = Path(command[0]).name
            if name == "build_evidence_pack.py":
                return str(evidence)
            if name == "audit_transcript_languages.py":
                return str(audit)
            if name == "build_gemini_input_package.py":
                return str(root / "package")
            if name == "backup_spotify_transcripts_to_drive.py":
                return str(root / "backup-receipt.json")
            if name == "generate_gemini_report.py":
                raise pipeline.PipelineStepError(command, 1, "", "provider quota fixture")
            return "fixture-output"
        return args, run

    def test_dry_run_never_uploads_or_generates(self):
        with tempfile.TemporaryDirectory() as directory:
            args, run = self.fixture(Path(directory), dry_run=True)
            with patch.object(pipeline, "load_project_env"), patch.dict(os.environ, {"SPOTIFY_TRANSCRIPT_BACKUP_ENABLED": "1"}), \
                    patch.object(pipeline, "_run", side_effect=run) as calls, contextlib.redirect_stdout(io.StringIO()):
                result = pipeline.run(args)
            self.assertEqual(result["status"], "dry_run_ready_for_gemini")
            self.assertFalse(any("backup_spotify" in c.args[0][0] or "generate_gemini" in c.args[0][0] for c in calls.call_args_list))

    def test_failed_backup_blocks_generation(self):
        with tempfile.TemporaryDirectory() as directory:
            args, run = self.fixture(Path(directory))
            def failure(command):
                if "backup_spotify" in command[0]:
                    raise pipeline.PipelineStepError(command, 1, "", "backup failed fixture")
                return run(command)
            with patch.object(pipeline, "load_project_env"), patch.dict(os.environ, {"SPOTIFY_TRANSCRIPT_BACKUP_ENABLED": "1"}), \
                    patch.object(pipeline, "_run", side_effect=failure) as calls, contextlib.redirect_stdout(io.StringIO()):
                result = pipeline.run(args)
            self.assertEqual(result["status"], "blocked_transcript_drive_backup")
            self.assertFalse(any("generate_gemini" in c.args[0][0] for c in calls.call_args_list))

    def test_single_report_can_back_up_english_while_chinese_is_pending(self):
        with tempfile.TemporaryDirectory() as directory:
            args, run = self.fixture(Path(directory), missing_zh=1)
            with patch.object(pipeline, "load_project_env"), patch.dict(os.environ, {"SPOTIFY_TRANSCRIPT_BACKUP_ENABLED": "1"}), \
                    patch.object(pipeline, "_run", side_effect=run) as calls, contextlib.redirect_stdout(io.StringIO()):
                result = pipeline.run(args)
            commands = [c.args[0] for c in calls.call_args_list]
            backup = next(c for c in commands if "backup_spotify" in c[0])
            self.assertEqual(backup[-2:], ["--language", "english"])
            self.assertEqual(result["transcript_backup_pending_chinese"], 1)
            self.assertEqual(result["status"], "blocked_gemini_generation")
