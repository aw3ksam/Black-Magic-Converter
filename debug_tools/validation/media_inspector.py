"""
Media Metadata Inspector using ffprobe.
Complies with Section 5.3 of the Reliability & Observability Specification.
Extracts comprehensive stream details, resolution, color profiles, frame rates, and audio parameters.
"""

import json
import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class VideoStreamInfo:
    index: int
    codec_name: str
    width: int
    height: int
    fps: float
    frame_count: Optional[int]
    pix_fmt: str
    color_primaries: Optional[str] = None
    color_transfer: Optional[str] = None
    color_space: Optional[str] = None
    bit_depth: Optional[int] = None


@dataclass
class AudioStreamInfo:
    index: int
    codec_name: str
    sample_rate: int
    channels: int
    bit_depth: Optional[int] = None
    bitrate: Optional[int] = None


@dataclass
class MediaMetadata:
    path: str
    filename: str
    size_bytes: int
    duration_sec: float
    format_name: str
    bitrate: int
    video_streams: List[VideoStreamInfo] = field(default_factory=list)
    audio_streams: List[AudioStreamInfo] = field(default_factory=list)
    raw_ffprobe: Dict[str, Any] = field(default_factory=dict)

    @property
    def has_video(self) -> bool:
        return len(self.video_streams) > 0

    @property
    def has_audio(self) -> bool:
        return len(self.audio_streams) > 0

    @property
    def primary_video(self) -> Optional[VideoStreamInfo]:
        return self.video_streams[0] if self.video_streams else None

    @property
    def primary_audio(self) -> Optional[AudioStreamInfo]:
        return self.audio_streams[0] if self.audio_streams else None


class MediaInspector:
    """
    Executes ffprobe to extract rich technical media attributes.
    """

    def __init__(self, ffprobe_path: Optional[str] = None):
        self.ffprobe_path = self._resolve_ffprobe(ffprobe_path)

    @staticmethod
    def _resolve_ffprobe(custom_path: Optional[str] = None) -> str:
        if custom_path and shutil.which(custom_path):
            return custom_path
        candidates = [
            "/opt/homebrew/bin/ffprobe",
            "/usr/local/bin/ffprobe",
            "/usr/bin/ffprobe",
            "ffprobe",
        ]
        for c in candidates:
            if shutil.which(c):
                return c
        return "ffprobe"

    @staticmethod
    def _eval_frame_rate(fps_str: str) -> float:
        try:
            if "/" in fps_str:
                num, den = fps_str.split("/", 1)
                return float(num) / float(den) if float(den) > 0 else float(num)
            return float(fps_str)
        except Exception:
            return 0.0

    def inspect(self, file_path: Path, timeout_sec: float = 30.0) -> MediaMetadata:
        """
        Runs ffprobe and returns a MediaMetadata object.
        """
        p = Path(file_path).resolve()
        if not p.is_file():
            raise FileNotFoundError(f"Media file not found: {p}")

        cmd = [
            self.ffprobe_path,
            "-v", "error",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(p),
        ]

        proc = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            timeout=timeout_sec,
            check=False,
        )

        if proc.returncode != 0:
            raise RuntimeError(f"ffprobe failed for {p.name}: {proc.stderr.strip()}")

        try:
            data = json.loads(proc.stdout)
        except Exception as e:
            raise ValueError(f"Failed to parse ffprobe JSON output for {p.name}: {e}\nRaw:\n{proc.stdout}")

        format_info = data.get("format", {})
        duration_sec = float(format_info.get("duration", 0.0))
        size_bytes = int(format_info.get("size", p.stat().st_size if p.exists() else 0))
        bitrate = int(format_info.get("bit_rate", 0))
        format_name = str(format_info.get("format_name", ""))

        video_streams: List[VideoStreamInfo] = []
        audio_streams: List[AudioStreamInfo] = []

        for stream in data.get("streams", []):
            codec_type = stream.get("codec_type")
            idx = int(stream.get("index", 0))
            codec_name = stream.get("codec_name", "")

            if codec_type == "video":
                fps = self._eval_frame_rate(stream.get("avg_frame_rate") or stream.get("r_frame_rate") or "0")
                nb_frames = None
                if "nb_frames" in stream and stream["nb_frames"].isdigit():
                    nb_frames = int(stream["nb_frames"])

                bit_depth = None
                bits_raw = stream.get("bits_per_raw_sample")
                if bits_raw and str(bits_raw).isdigit():
                    bit_depth = int(bits_raw)

                v_info = VideoStreamInfo(
                    index=idx,
                    codec_name=codec_name,
                    width=int(stream.get("width", 0)),
                    height=int(stream.get("height", 0)),
                    fps=round(fps, 3),
                    frame_count=nb_frames,
                    pix_fmt=stream.get("pix_fmt", ""),
                    color_primaries=stream.get("color_primaries"),
                    color_transfer=stream.get("color_transfer"),
                    color_space=stream.get("color_space"),
                    bit_depth=bit_depth,
                )
                video_streams.append(v_info)

            elif codec_type == "audio":
                sample_rate = int(stream.get("sample_rate", 48000))
                channels = int(stream.get("channels", 2))
                a_bitrate = int(stream.get("bit_rate", 0)) if "bit_rate" in stream and str(stream["bit_rate"]).isdigit() else None
                a_info = AudioStreamInfo(
                    index=idx,
                    codec_name=codec_name,
                    sample_rate=sample_rate,
                    channels=channels,
                    bitrate=a_bitrate,
                )
                audio_streams.append(a_info)

        return MediaMetadata(
            path=str(p),
            filename=p.name,
            size_bytes=size_bytes,
            duration_sec=duration_sec,
            format_name=format_name,
            bitrate=bitrate,
            video_streams=video_streams,
            audio_streams=audio_streams,
            raw_ffprobe=data,
        )
