"""
Video Queue Discovery, Hashing, and Sequencing Manager.
Complies with Section 5.2 of the Reliability & Observability Specification.
Supports deterministic seeded random, sequential, alphabetical, and looping modes.
"""

import os
import re
import hashlib
import random
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Iterator


@dataclass
class SourceVideo:
    path: Path
    filename: str
    sha256: str
    size_bytes: int


@dataclass
class QueueItem:
    job_index: int
    job_id: str
    source: SourceVideo
    submitted_filename: str


class QueueManager:
    """
    Discovers test videos, computes SHA-256 hashes, and yields structured QueueItems
    in configured deterministic sequence modes.
    """

    SUPPORTED_EXTENSIONS = {".braw", ".mp4", ".mov", ".mkv", ".ts"}

    def __init__(
        self,
        source_dir: str = "./test-videos",
        order_mode: str = "seeded_random",  # sequential | alphabetical | random | seeded_random | loop
        random_seed: Optional[int] = 42,
    ):
        self.source_dir = Path(source_dir).resolve()
        self.order_mode = order_mode.lower()
        self.random_seed = random_seed
        self.discovered_sources: List[SourceVideo] = []
        self._current_index = 0
        self._rng = random.Random(self.random_seed) if self.random_seed is not None else random.Random()
        self._discover_and_hash()

    @staticmethod
    def calculate_sha256(file_path: Path, block_size: int = 65536) -> str:
        """Calculates SHA-256 digest of a file in chunks."""
        hasher = hashlib.sha256()
        with open(file_path, "rb") as f:
            for block in iter(lambda: f.read(block_size), b""):
                hasher.update(block)
        return hasher.hexdigest()

    @staticmethod
    def sanitize_filename(name: str) -> str:
        """Removes spaces, special characters, and path separators."""
        stem = Path(name).stem
        sanitized = re.sub(r"[^\w\-.]", "_", stem)
        return sanitized

    def _discover_and_hash(self):
        """Scans the source directory and computes cryptographic hashes."""
        if not self.source_dir.exists():
            return

        candidates = []
        for root, _, files in os.walk(self.source_dir):
            for file in files:
                p = Path(root) / file
                if p.suffix.lower() in self.SUPPORTED_EXTENSIONS and not p.name.startswith("."):
                    candidates.append(p)

        # Sort initially for determinism before ordering
        candidates.sort(key=lambda p: str(p))

        self.discovered_sources = []
        for p in candidates:
            try:
                sha = self.calculate_sha256(p)
                size = p.stat().st_size
                self.discovered_sources.append(
                    SourceVideo(
                        path=p,
                        filename=p.name,
                        sha256=sha,
                        size_bytes=size,
                    )
                )
            except Exception:
                pass

    def get_ordered_sources(self) -> List[SourceVideo]:
        """Returns a copy of discovered sources in the configured order."""
        if not self.discovered_sources:
            return []

        sources = list(self.discovered_sources)

        if self.order_mode == "alphabetical":
            sources.sort(key=lambda s: s.filename.lower())
        elif self.order_mode == "sequential":
            # Natural discovery order
            pass
        elif self.order_mode == "seeded_random":
            rng = random.Random(self.random_seed)
            rng.shuffle(sources)
        elif self.order_mode == "random":
            random.shuffle(sources)
        elif self.order_mode == "loop":
            # Sequential base for loop
            pass

        return sources

    def next_item(self) -> Optional[QueueItem]:
        """
        Retrieves the next QueueItem. In 'loop' mode, restarts when reaching the end.
        """
        if not self.discovered_sources:
            return None

        ordered = self.get_ordered_sources()
        if not ordered:
            return None

        if self.order_mode == "loop":
            idx = self._current_index % len(ordered)
            source = ordered[idx]
        elif self.order_mode in ("seeded_random", "random"):
            idx = self._current_index % len(ordered)
            # Re-pick or advance
            source = ordered[idx]
        else:
            if self._current_index >= len(ordered):
                return None
            source = ordered[self._current_index]

        self._current_index += 1
        sanitized = self.sanitize_filename(source.filename)
        suffix = source.path.suffix
        job_id = f"job_{self._current_index:04d}_{sanitized}"
        submitted_filename = f"{job_id}{suffix}"

        return QueueItem(
            job_index=self._current_index,
            job_id=job_id,
            source=source,
            submitted_filename=submitted_filename,
        )

    def reset(self):
        """Resets iteration index."""
        self._current_index = 0
