"""Tests for gasclaw.kimigas.key_pool."""

from __future__ import annotations

import contextlib
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

    def test_expired_cooldown_unused_key_still_lru(self, tmp_path):
        """When cooldown expires, unused key still has priority over recently used key.

        This tests the LRU principle: k3 has never been used (timestamp=0),
        so even when k1 and k2 come off cooldown, k3 should be selected first.
        """
        pool = KeyPool(["k1", "k2", "k3"], state_dir=tmp_path)

        # Use k1 and k2, leaving k3 unused
        pool.get_key()  # k1 (now has recent timestamp)
        pool.get_key()  # k2 (now has recent timestamp)

        # Rate-limit both k1 and k2
        pool.mark_rate_limited("k1")
        pool.mark_rate_limited("k2")

        # Manually expire both cooldowns
        state = pool._load_state()
        h1 = pool._key_hash("k1")
        h2 = pool._key_hash("k2")
        expired_time = time.time() - RATE_LIMIT_COOLDOWN - 1
        state["rate_limited"][h1] = expired_time
        state["rate_limited"][h2] = expired_time
        pool._save_state(state)

        # All keys are now available, but k3 was never used
        # LRU should pick k3 (timestamp=0) over k1 and k2 (recent timestamps)
        result = pool.get_key()
        assert result == "k3"

        # After using k3, the next call should pick between k1 and k2
        # (k3 now has a timestamp, so k1 or k2 might be LRU depending on exact timing)
        second_result = pool.get_key()
        assert second_result in ("k1", "k2")


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

    def test_partial_rate_limited_availability(self, tmp_path):
        """Test with 4 keys where 2 are rate-limited."""
        pool = KeyPool(["k1", "k2", "k3", "k4"], state_dir=tmp_path)
        pool.mark_rate_limited("k1")
        pool.mark_rate_limited("k3")
        status = pool.status()
        assert status["total"] == 4
        assert status["available"] == 2
        assert status["rate_limited"] == 2

    def test_rate_limiting_unused_key(self, tmp_path):
        """Marking a key as rate-limited before it's used works."""
        pool = KeyPool(["k1", "k2"], state_dir=tmp_path)
        # Mark k1 as rate-limited before ever using it
        pool.mark_rate_limited("k1")
        # k2 should be selected since k1 is rate-limited
        assert pool.get_key() == "k2"

    def test_all_keys_used_then_rotated(self, tmp_path):
        """After all keys are used, rotation starts over with LRU."""
        pool = KeyPool(["k1", "k2", "k3"], state_dir=tmp_path)
        # Use all keys once
        assert pool.get_key() == "k1"
        assert pool.get_key() == "k2"
        assert pool.get_key() == "k3"
        # Next should be k1 again (LRU)
        assert pool.get_key() == "k1"

    def test_status_with_no_rate_limited_keys(self, tmp_path):
        """Status shows all available when no keys are rate-limited."""
        pool = KeyPool(["k1", "k2", "k3"], state_dir=tmp_path)
        status = pool.status()
        assert status["available"] == 3
        assert status["rate_limited"] == 0


class TestKeyPoolAtomicWrite:
    def test_state_file_written_atomically(self, tmp_path):
        """State file is written using atomic rename to avoid corruption."""
        pool = KeyPool(["k1"], state_dir=tmp_path)
        pool.get_key()

        # The state file should exist, but no temp files should remain
        state_file = tmp_path / "key-rotation.json"
        assert state_file.exists()

        # Check no temp files left behind
        temp_files = list(tmp_path.glob(".key-rotation-*.tmp"))
        assert len(temp_files) == 0

    def test_corrupted_temp_file_cleaned_up(self, tmp_path, monkeypatch):
        """Temp file is cleaned up if write fails."""
        pool = KeyPool(["k1"], state_dir=tmp_path)

        # Make os.fdopen fail to trigger cleanup
        original_fdopen = __builtins__.get("open", open)

        def fail_on_fdopen(*args, **kwargs):
            if args and hasattr(args[0], "__class__") and "int" in str(type(args[0])):
                raise OSError("Write failed")
            return original_fdopen(*args, **kwargs)

        monkeypatch.setattr("os.fdopen", fail_on_fdopen)

        with contextlib.suppress(OSError):
            pool._save_state({"test": "data"})

        # Temp file should be cleaned up
        temp_files = list(tmp_path.glob(".key-rotation-*.tmp"))
        assert len(temp_files) == 0

    def test_oserror_on_unlink_is_ignored(self, tmp_path, monkeypatch):
        """OSError during temp file cleanup is ignored (line 71-72 coverage)."""
        pool = KeyPool(["k1"], state_dir=tmp_path)

        # Track if unlink was called
        unlink_calls = []

        def fail_unlink(*args, **kwargs):
            unlink_calls.append(args)
            raise OSError("Cannot unlink")

        monkeypatch.setattr("os.unlink", fail_unlink)

        # Make os.fdopen fail to trigger cleanup path
        def fail_fdopen(*a, **kw):
            raise OSError("Write failed")

        monkeypatch.setattr("os.fdopen", fail_fdopen)

        # Should raise the original OSError, not the unlink error
        with pytest.raises(OSError, match="Write failed"):
            pool._save_state({"test": "data"})

        # Unlink should have been attempted
        assert len(unlink_calls) >= 1


class TestKeyPoolEdgeCases:
    def test_creates_state_dir_if_not_exists(self, tmp_path):
        """State directory is created if it doesn't exist."""
        nested_dir = tmp_path / "nested" / "state"
        pool = KeyPool(["k1"], state_dir=nested_dir)
        pool.get_key()
        assert nested_dir.exists()
        assert (nested_dir / "key-rotation.json").exists()

    def test_duplicate_keys_treated_as_separate(self, tmp_path):
        """Duplicate keys in list are treated as separate entries."""
        # This tests the behavior when duplicate keys are provided
        pool = KeyPool(["k1", "k1", "k2"], state_dir=tmp_path)
        assert pool.total_keys == 3

    def test_empty_string_key_is_valid(self, tmp_path):
        """Empty string can be a key (edge case)."""
        pool = KeyPool([""], state_dir=tmp_path)
        assert pool.get_key() == ""

    def test_key_hash_consistency(self, tmp_path):
        """Same key produces same hash across instances."""
        pool1 = KeyPool(["k1"], state_dir=tmp_path)
        pool2 = KeyPool(["k1"], state_dir=tmp_path)
        assert pool1._key_hash("k1") == pool2._key_hash("k1")

    def test_mark_nonexistent_key_rate_limited(self, tmp_path):
        """Marking a key not in pool raises ValueError with key hash."""
        pool = KeyPool(["k1"], state_dir=tmp_path)
        expected_hash = pool._key_hash("nonexistent-key")
        with pytest.raises(ValueError, match=f"Key {expected_hash} does not belong"):
            pool.mark_rate_limited("nonexistent-key")

    def test_clear_cooldown_removes_rate_limit(self, tmp_path):
        """clear_cooldown removes rate-limited status and returns True."""
        pool = KeyPool(["k1", "k2"], state_dir=tmp_path)
        pool.mark_rate_limited("k1")

        # k1 is rate-limited, so k2 is selected
        assert pool.get_key() == "k2"

        # Clear cooldown for k1
        result = pool.clear_cooldown("k1")
        assert result is True

        # k1 is now available again (it's LRU)
        assert pool.get_key() == "k1"

    def test_clear_cooldown_returns_false_if_not_rate_limited(self, tmp_path):
        """clear_cooldown returns False if key was not rate-limited."""
        pool = KeyPool(["k1", "k2"], state_dir=tmp_path)

        # k1 was never rate-limited
        result = pool.clear_cooldown("k1")
        assert result is False

    def test_clear_cooldown_raises_for_invalid_key(self, tmp_path):
        """clear_cooldown raises ValueError with key hash for key not in pool."""
        pool = KeyPool(["k1"], state_dir=tmp_path)
        expected_hash = pool._key_hash("nonexistent-key")

        with pytest.raises(ValueError, match=f"Key {expected_hash} does not belong"):
            pool.clear_cooldown("nonexistent-key")

    def test_state_file_is_json(self, tmp_path):
        """State file contains valid JSON with expected structure."""
        import json

        pool = KeyPool(["k1", "k2"], state_dir=tmp_path)
        pool.get_key()
        pool.mark_rate_limited("k2")

        state_file = tmp_path / "key-rotation.json"
        state = json.loads(state_file.read_text())

        assert "last_used" in state
        assert "rate_limited" in state
        assert isinstance(state["last_used"], dict)
        assert isinstance(state["rate_limited"], dict)
