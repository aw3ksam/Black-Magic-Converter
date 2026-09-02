"""
Bitstream Integrity Validator & Failure Classification Engine.
Complies with Section 4.5 & 5.3 of the Reliability & Observability Specification.
Executes null-mux decode passes and enforces strict tolerance deltas for transcoded media.
"""

import os
import re
import shutil
import subprocess
from enum import Enum
from pathlib import Path
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple, Any

from debug_tools.validation.media_inspector import MediaInspector, MediaMetadata


class FailureCategory(str, Enum):
    APP_CRASH = "APP_CRASH"
    HARNESS_CRASH = "HARNESS_CRASH"
    TRANSCODER_CRASH = "TRANSCODER_CRASH"
    WATCHDOG_FAILURE = "WATCHDOG_FAILURE"
    INPUT_COPY_FAILURE = "INPUT_COPY_FAILURE"
    INPUT_NOT_DETECTED = "INPUT_NOT_DETECTED"
    TRANSCODE_TIMEOUT = "TRANSCODE_TIMEOUT"
    APPLICATION_HANG = "APPLICATION_HANG"
    OUTPUT_NOT_CREATED = "OUTPUT_NOT_CREATED"
    OUTPUT_CORRUPT = "OUTPUT_CORRUPT"
    OUTPUT_VALIDATION_FAILURE = "OUTPUT_VALIDATION_FAILURE"
    FFMPEG_FAILURE = "FFMPEG_FAILURE"
    FFPROBE_FAILURE = "FFPROBE_FAILURE"
    DISK_FULL = "DISK_FULL"
    OUT_OF_MEMORY = "OUT_OF_MEMORY"
    GPU_FAILURE = "GPU_FAILURE"
    PERFORMANCE_DEGRADATION = "PERFORMANCE_DEGRADATION"
    UNKNOWN_FAILURE = "UNKNOWN_FAILURE"


@dataclass
class ValidationResult:
    is_valid: bool
    failure_category: Optional[FailureCategory] = None
    error_message: Optional[str] = None
    source_meta: Optional[MediaMetadata] = None
    output_meta: Optional[MediaMetadata] = None
    null_decode_stderr: Optional[str] = None
    duration_delta: Optional[float] = None
    fps_delta_percent: Optional[float] = None


class BitstreamValidator:
    """
    Validates transcoded output files using full decode passes and checks against source metadata.
    """

    def __init__(
        self,
        ffmpeg_path: Optional[str] = None,
        ffprobe_path: Optional[str] = None,
        duration_tolerance_sec: float = 0.5,
        fps_tolerance_percent: float = 1.0,
        allow_missing_audio: bool = False,
    ):
        self.ffmpeg_path = self._resolve_ffmpeg(ffmpeg_path)
        self.inspector = MediaInspector(ffprobe_path=ffprobe_path)
        self.duration_tolerance_sec = duration_tolerance_sec
        self.fps_tolerance_percent = fps_tolerance_percent
        self.allow_missing_audio = allow_missing_audio

    @staticmethod
    def _resolve_ffmpeg(custom_path: Optional[str] = None) -> str:
        if custom_path and shutil.which(custom_path):
            return custom_path
        candidates = [
            "/opt/homebrew/bin/ffmpeg",
            "/usr/local/bin/ffmpeg",
            "/usr/bin/ffmpeg",
            "ffmpeg",
        ]
        for c in candidates:
            if shutil.which(c):
                return c
        return "ffmpeg"

    def run_null_decode(self, file_path: Path, timeout_sec: float = 120.0) -> Tuple[bool, str]:
        """
        Executes `ffmpeg -v error -i <output_file> -f null -` to detect broken containers,
        corrupt macroblocks, PTS/DTS discontinuities, or undecodable packets.
        Returns (success: bool, stderr_output: str).
        """
        cmd = [
            self.ffmpeg_path,
            "-v", "error",
            "-i", str(file_path.resolve()),
            "-f", "null",
            "-",
        ]

        try:
            proc = subprocess.run(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
            stderr = proc.stderr.strip()
            # An error-free decode pass returns 0 and has empty or benign stderr
            if proc.returncode != 0 or ("error" in stderr.lower() or "corrupt" in stderr.lower() or "invalid" in stderr.lower()):
                return False, stderr
            return True, stderr
        except subprocess.TimeoutExpired:
            return False, "Null decode pass timed out"
        except Exception as e:
            return False, f"Null decode execution failed: {e}"

    def validate(
        self,
        output_file: Path,
        source_meta: Optional[MediaMetadata] = None,
        run_full_decode: bool = True,
    ) -> ValidationResult:
        """
        Performs full technical validation of the output file.
        """
        # 1. Existence and size check
        if not output_file.exists():
            return ValidationResult(
                is_valid=False,
                failure_category=FailureCategory.OUTPUT_NOT_CREATED,
                error_message=f"Output file does not exist: {output_file}",
            )

        try:
            if output_file.stat().st_size == 0:
                return ValidationResult(
                    is_valid=False,
                    failure_category=FailureCategory.OUTPUT_CORRUPT,
                    error_message=f"Output file is 0 bytes: {output_file}",
                )
        except OSError as e:
            return ValidationResult(
                is_valid=False,
                failure_category=FailureCategory.OUTPUT_NOT_CREATED,
                error_message=f"Could not stat output file: {e}",
            )

        # 2. Extract output metadata via ffprobe
        try:
            output_meta = self.inspector.inspect(output_file)
        except Exception as e:
            return ValidationResult(
                is_valid=False,
                failure_category=FailureCategory.FFPROBE_FAILURE,
                error_message=f"ffprobe failed on output file {output_file.name}: {e}",
            )

        # 3. Stream presence validation
        if not output_meta.has_video:
            return ValidationResult(
                is_valid=False,
                failure_category=FailureCategory.OUTPUT_VALIDATION_FAILURE,
                error_message=f"Output file contains no video stream: {output_file.name}",
                output_meta=output_meta,
            )

        if source_meta and source_meta.has_audio and not self.allow_missing_audio and not output_meta.has_audio:
            return ValidationResult(
                is_valid=False,
                failure_category=FailureCategory.OUTPUT_VALIDATION_FAILURE,
                error_message=f"Source had audio but output is missing audio stream: {output_file.name}",
                source_meta=source_meta,
                output_meta=output_meta,
            )

        # 4. Duration and FPS Delta Checks (if source metadata available)
        duration_delta = None
        fps_delta_pct = None

        if source_meta and source_meta.duration_sec > 0 and output_meta.duration_sec > 0:
            duration_delta = abs(output_meta.duration_sec - source_meta.duration_sec)
            if duration_delta > self.duration_tolerance_sec:
                return ValidationResult(
                    is_valid=False,
                    failure_category=FailureCategory.OUTPUT_VALIDATION_FAILURE,
                    error_message=(
                        f"Output duration ({output_meta.duration_sec:.2f}s) differs from source "
                        f"({source_meta.duration_sec:.2f}s) by {duration_delta:.2f}s (tolerance: {self.duration_tolerance_sec}s)"
                    ),
                    source_meta=source_meta,
                    output_meta=output_meta,
                    duration_delta=duration_delta,
                )

        if source_meta and source_meta.primary_video and output_meta.primary_video:
            s_fps = source_meta.primary_video.fps
            o_fps = output_meta.primary_video.fps
            if s_fps > 0 and o_fps > 0:
                fps_delta_pct = abs(o_fps - s_fps) / s_fps * 100.0
                if fps_delta_pct > self.fps_tolerance_percent:
                    return ValidationResult(
                        is_valid=False,
                        failure_category=FailureCategory.OUTPUT_VALIDATION_FAILURE,
                        error_message=(
                            f"Output FPS ({o_fps:.2f}) differs from source ({s_fps:.2f}) by "
                            f"{fps_delta_pct:.2f}% (tolerance: {self.fps_tolerance_percent}%)"
                        ),
                        source_meta=source_meta,
                        output_meta=output_meta,
                        fps_delta_percent=fps_delta_pct,
                    )

        # 5. Full Bitstream Null Decode Pass
        null_stderr = None
        if run_full_decode:
            decode_ok, null_stderr = self.run_null_decode(output_file)
            if not decode_ok:
                return ValidationResult(
                    is_valid=False,
                    failure_category=FailureCategory.OUTPUT_CORRUPT,
                    error_message=f"Bitstream decode pass failed for {output_file.name}: {null_stderr}",
                    source_meta=source_meta,
                    output_meta=output_meta,
                    null_decode_stderr=null_stderr,
                    duration_delta=duration_delta,
                    fps_delta_percent=fps_delta_pct,
                )

        return ValidationResult(
            is_valid=True,
            source_meta=source_meta,
            output_meta=output_meta,
            null_decode_stderr=null_stderr,
            duration_delta=duration_delta,
            fps_delta_percent=fps_delta_pct,
        )

    @staticmethod
    def classify_runtime_error(error_text: str, exit_code: Optional[int] = None) -> FailureCategory:
        """
        Classifies exceptions, crash outputs, and system error strings into FailureCategory enums.
        """
        err_lower = error_text.lower() if error_text else ""

        if "out of memory" in err_lower or "oom" in err_lower or "memoryerror" in err_lower or exit_code == 137:
            return FailureCategory.OUT_OF_MEMORY
        elif "no space left on device" in err_lower or "disk full" in err_lower:
            return FailureCategory.DISK_FULL
        elif "gpu" in err_lower and ("lost" in err_lower or "metal" in err_lower or "reset" in err_lower or "device" in err_lower):
            return FailureCategory.GPU_FAILURE
        elif "segfault" in err_lower or "segmentation fault" in err_lower or exit_code == 139 or exit_code == -11:
            return FailureCategory.TRANSCODER_CRASH
        elif "timed out" in err_lower or "timeout" in err_lower:
            return FailureCategory.TRANSCODE_TIMEOUT
        elif "ffprobe" in err_lower:
            return FailureCategory.FFPROBE_FAILURE
        elif "ffmpeg" in err_lower:
            return FailureCategory.FFMPEG_FAILURE
        elif exit_code is not None and exit_code != 0:
            return FailureCategory.APP_CRASH
        else:
            return FailureCategory.UNKNOWN_FAILURE
