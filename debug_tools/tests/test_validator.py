"""
Unit tests for BitstreamValidator, MediaInspector, and failure classification.
"""

import os
import unittest
from pathlib import Path

from debug_tools.validation.bitstream_validator import BitstreamValidator, FailureCategory, ValidationResult
from debug_tools.validation.media_inspector import MediaInspector, MediaMetadata, VideoStreamInfo, AudioStreamInfo


class TestValidator(unittest.TestCase):

    def setUp(self):
        self.validator = BitstreamValidator(
            duration_tolerance_sec=0.5,
            fps_tolerance_percent=2.0,
            allow_missing_audio=False,
        )

    def test_classify_runtime_errors(self):
        self.assertEqual(
            BitstreamValidator.classify_runtime_error("Fatal: Out of memory in pipeline", exit_code=137),
            FailureCategory.OUT_OF_MEMORY
        )
        self.assertEqual(
            BitstreamValidator.classify_runtime_error("Error: no space left on device"),
            FailureCategory.DISK_FULL
        )
        self.assertEqual(
            BitstreamValidator.classify_runtime_error("Segmentation fault (core dumped)", exit_code=-11),
            FailureCategory.TRANSCODER_CRASH
        )
        self.assertEqual(
            BitstreamValidator.classify_runtime_error("Metal GPU device was lost during render"),
            FailureCategory.GPU_FAILURE
        )
        self.assertEqual(
            BitstreamValidator.classify_runtime_error("Job timed out after 600s"),
            FailureCategory.TRANSCODE_TIMEOUT
        )

    def test_missing_file_validation(self):
        res = self.validator.validate(Path("/nonexistent/output.mp4"), run_full_decode=False)
        self.assertFalse(res.is_valid)
        self.assertEqual(res.failure_category, FailureCategory.OUTPUT_NOT_CREATED)


if __name__ == "__main__":
    unittest.main()
