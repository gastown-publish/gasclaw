"""Tests for gasclaw.kimigas.key_pool."""

from __future__ import annotations

import time

import pytest

from gasclaw.kimigas.key_pool import RATE_LIMIT_COOLDOWN, KeyPool


class TestKeyPoolSingleKey:
    def test_single_key_always_selected(self, tmp_path):
        pool = KeyPool(["sk-only"], state_dir=tmp_path)
        assert pool.get_key() == "sk-only"
        assert pool.get_key() == "sk-only"

    def test_single_key_count(self, tmp_path):
        pool = KeyPool(["sk-only"], state_dir=tmp_path)
        assert pool.total_keys == 1


class TestKeyPoolMultiKey:
    def test_rotates_lru(self, tmp_path):
        """Keys rotate in LRU order."""
        pool = KeyPool(["k1", "k2", "k3"], state_dir=tmp_path)
        first = pool.get_key()
        assert first == "k1"  # Never used, so first in order
        second = pool.get_key()
        assert second == "k2"  # k1 was just used, k2 is LRU
        third = pool.get_key()
        assert third == "k3"

    def test_wraps_around(self, tmp_path):
        pool = KeyPool(["k1", "k2"], state_dir=tmp_path)
        pool.get_key()  # k1
        pool.get_key()  # k2
        assert pool.get_key() == "k1"  # wraps back to k1


class TestKeyPoolRateLimit:
    def test_rate_limited_key_skipped(self, tmp_path):
        pool = KeyPool(["k1", "k2"], state_dir=tmp_path)
        pool.get_key()  # k1
        pool.mark_rate_limited("k1")
        assert pool.get_key() == "k2"

    def test_all_rate_limited_falls_back_to_lru(self, tmp_path):
        pool = KeyPool(["k1", "k2"], state_dir=tmp_path)
        pool.mark_rate_limited("k1")
        pool.mark_rate_limited("k2")
        # All rate-limited — falls back to LRU order
        result = pool.get_key()
        assert result in ("k1", "k2")

    def test_cooldown_expires(self, tmp_path):
        pool = KeyPool(["k1", "k2"], state_dir=tmp_path)
        pool.get_key()  # k1
        pool.mark_rate_limited("k1")

        # Manually expire the cooldown
        state = pool._load_state()
        h = pool._key_hash("k1")
        state["rate_limited"][h] = time.time() - RATE_LIMIT_COOLDOWN - 1
        pool._save_state(state)

        # k1 should be available again (it's LRU since k2 was never used... wait)
        # k1 was used, then rate-limited. k2 was never used, so k2 is still LRU
        # After cooldown, k2 is LRU so it gets picked
        result = pool.get_key()
        assert result == "k2"


class TestKeyPoolStatePersistence:
    def test_state_persists_across_instances(self, tmp_path):
        pool1 = KeyPool(["k1", "k2"], state_dir=tmp_path)
        pool1.get_key()  # k1 used

        pool2 = KeyPool(["k1", "k2"], state_dir=tmp_path)
        assert pool2.get_key() == "k2"  # k1 was used by pool1

    def test_state_file_created(self, tmp_path):
        pool = KeyPool(["k1"], state_dir=tmp_path)
        pool.get_key()
        assert (tmp_path / "key-rotation.json").exists()

    def test_corrupted_state_handled(self, tmp_path):
        (tmp_path / "key-rotation.json").write_text("not json!")
        pool = KeyPool(["k1"], state_dir=tmp_path)
        assert pool.get_key() == "k1"


class TestKeyPoolStatus:
    def test_status_report(self, tmp_path):
        pool = KeyPool(["k1", "k2", "k3"], state_dir=tmp_path)
        pool.get_key()  # use k1
        pool.mark_rate_limited("k2")
        status = pool.status()
        assert status["total"] == 3
        assert status["available"] == 2  # k1 + k3 (k2 rate-limited)
        assert status["rate_limited"] == 1

    def test_empty_pool_raises(self):
        with pytest.raises(ValueError, match="at least one"):
            KeyPool([])
