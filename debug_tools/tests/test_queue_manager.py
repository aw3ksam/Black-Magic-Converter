"""
Unit tests for QueueManager discovery, hashing, and sequence modes.
"""

import os
import shutil
import tempfile
import unittest
from pathlib import Path

from debug_tools.harness.queue_manager import QueueManager, SourceVideo, QueueItem


class TestQueueManager(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.source_dir = os.path.join(self.temp_dir, "samples")
        os.makedirs(self.source_dir, exist_ok=True)

        # Create mock video sample files
        self.sample_files = ["clip_c.braw", "clip_a.braw", "clip_b.mp4"]
        for fname in self.sample_files:
            p = os.path.join(self.source_dir, fname)
            with open(p, "wb") as f:
                f.write(f"content-for-{fname}".encode("utf-8"))

    def tearDown(self):
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_discovery_and_hashing(self):
        qm = QueueManager(source_dir=self.source_dir, order_mode="sequential")
        self.assertEqual(len(qm.discovered_sources), 3)
        for s in qm.discovered_sources:
            self.assertTrue(len(s.sha256) == 64)
            self.assertGreater(s.size_bytes, 0)

    def test_alphabetical_order(self):
        qm = QueueManager(source_dir=self.source_dir, order_mode="alphabetical")
        ordered = qm.get_ordered_sources()
        filenames = [s.filename for s in ordered]
        self.assertEqual(filenames, ["clip_a.braw", "clip_b.mp4", "clip_c.braw"])

    def test_next_item_exhaustion(self):
        qm = QueueManager(source_dir=self.source_dir, order_mode="sequential")
        items = []
        for _ in range(4):
            item = qm.next_item()
            if item:
                items.append(item)
        self.assertEqual(len(items), 3)
        self.assertIsNone(qm.next_item())

    def test_loop_mode(self):
        qm = QueueManager(source_dir=self.source_dir, order_mode="loop")
        items = [qm.next_item() for _ in range(7)]
        self.assertEqual(len(items), 7)
        self.assertIsNotNone(items[0])
        self.assertIsNotNone(items[6])

    def test_deterministic_seeded_random(self):
        qm1 = QueueManager(source_dir=self.source_dir, order_mode="seeded_random", random_seed=123)
        qm2 = QueueManager(source_dir=self.source_dir, order_mode="seeded_random", random_seed=123)
        order1 = [s.filename for s in qm1.get_ordered_sources()]
        order2 = [s.filename for s in qm2.get_ordered_sources()]
        self.assertEqual(order1, order2)


if __name__ == "__main__":
    unittest.main()
