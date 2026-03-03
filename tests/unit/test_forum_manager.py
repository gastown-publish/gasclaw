"""Tests for gasclaw.openclaw.forum_manager."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

import httpx
import pytest
import respx

from gasclaw.openclaw.forum_manager import (
    DEFAULT_STATE_DIR,
    REQUIRED_TOPICS,
    TOPIC_CONFIG_FILE,
    ForumTopicError,
    ForumTopicManager,
    GroupForumState,
    TopicConfig,
)


class TestTopicConfig:
    """Tests for TopicConfig dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        config = TopicConfig(name="test-topic", thread_id=123, created_at=1234567890.0)
        result = config.to_dict()
        assert result == {
            "name": "test-topic",
            "thread_id": 123,
            "created_at": 1234567890.0,
        }

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {"name": "test-topic", "thread_id": 123, "created_at": 1234567890.0}
        config = TopicConfig.from_dict(data)
        assert config.name == "test-topic"
        assert config.thread_id == 123
        assert config.created_at == 1234567890.0

    def test_from_dict_with_defaults(self):
        """Test creation from dictionary with missing fields."""
        data = {"name": "test-topic"}
        config = TopicConfig.from_dict(data)
        assert config.name == "test-topic"
        assert config.thread_id is None
        assert config.created_at is None


class TestGroupForumState:
    """Tests for GroupForumState dataclass."""

    def test_to_dict(self):
        """Test conversion to dictionary."""
        topic = TopicConfig(name="test", thread_id=1)
        state = GroupForumState(
            chat_id="-1001234567890",
            is_forum=True,
            topics={"test": topic},
            admin_checked=True,
            is_admin=True,
        )
        result = state.to_dict()
        assert result["chat_id"] == "-1001234567890"
        assert result["is_forum"] is True
        assert result["topics"]["test"]["name"] == "test"
        assert result["admin_checked"] is True
        assert result["is_admin"] is True

    def test_from_dict(self):
        """Test creation from dictionary."""
        data = {
            "chat_id": "-1001234567890",
            "is_forum": True,
            "topics": {"test": {"name": "test", "thread_id": 1}},
            "admin_checked": True,
            "is_admin": True,
        }
        state = GroupForumState.from_dict(data)
        assert state.chat_id == "-1001234567890"
        assert state.is_forum is True
        assert "test" in state.topics
        assert state.topics["test"].thread_id == 1
        assert state.admin_checked is True
        assert state.is_admin is True

    def test_has_all_topics_true(self):
        """Test has_all_topics returns True when all required topics exist."""
        state = GroupForumState(chat_id="-1001234567890")
        for topic_name in REQUIRED_TOPICS:
            state.topics[topic_name] = TopicConfig(name=topic_name, thread_id=1)
        assert state.has_all_topics() is True

    def test_has_all_topics_false_missing_topic(self):
        """Test has_all_topics returns False when a topic is missing."""
        state = GroupForumState(chat_id="-1001234567890")
        for topic_name in REQUIRED_TOPICS[:-1]:
            state.topics[topic_name] = TopicConfig(name=topic_name, thread_id=1)
        assert state.has_all_topics() is False

    def test_has_all_topics_false_no_thread_id(self):
        """Test has_all_topics returns False when thread_id is None."""
        state = GroupForumState(chat_id="-1001234567890")
        for topic_name in REQUIRED_TOPICS:
            state.topics[topic_name] = TopicConfig(name=topic_name, thread_id=None)
        assert state.has_all_topics() is False

    def test_get_thread_id_exists(self):
        """Test getting thread ID for existing topic."""
        state = GroupForumState(chat_id="-1001234567890")
        state.topics["test"] = TopicConfig(name="test", thread_id=123)
        assert state.get_thread_id("test") == 123

    def test_get_thread_id_missing(self):
        """Test getting thread ID for missing topic."""
        state = GroupForumState(chat_id="-1001234567890")
        assert state.get_thread_id("missing") is None


class TestForumTopicManagerInit:
    """Tests for ForumTopicManager initialization."""

    def test_init_with_defaults(self):
        """Test initialization with default values."""
        manager = ForumTopicManager(bot_token="test_token")
        assert manager.bot_token == "test_token"
        assert manager.state_dir == Path(DEFAULT_STATE_DIR)
        assert manager._states == {}
        assert manager._base_url == "https://api.telegram.org/bottest_token"

    def test_init_with_custom_state_dir(self):
        """Test initialization with custom state directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            assert manager.state_dir == Path(tmpdir)

    def test_state_file_property(self):
        """Test state_file property returns correct path."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            assert manager.state_file == Path(tmpdir) / TOPIC_CONFIG_FILE


class TestForumTopicManagerStatePersistence:
    """Tests for state loading and saving."""

    def test_load_all_states_empty(self):
        """Test loading when no state file exists."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            states = manager._load_all_states()
            assert states == {}

    def test_load_all_states_existing(self):
        """Test loading existing state file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / TOPIC_CONFIG_FILE
            data = {
                "-1001234567890": {
                    "chat_id": "-1001234567890",
                    "is_forum": True,
                    "topics": {},
                    "admin_checked": False,
                    "is_admin": False,
                }
            }
            state_file.write_text(json.dumps(data))

            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            states = manager._load_all_states()
            assert "-1001234567890" in states
            assert states["-1001234567890"].is_forum is True

    def test_load_all_states_invalid_json(self):
        """Test loading invalid JSON logs warning and returns empty dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            state_file = Path(tmpdir) / TOPIC_CONFIG_FILE
            state_file.write_text("invalid json")

            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            states = manager._load_all_states()
            assert states == {}

    def test_save_all_states_creates_directory(self):
        """Test save creates state directory if needed."""
        with tempfile.TemporaryDirectory() as tmpdir:
            nested_dir = Path(tmpdir) / "nested" / "state"
            manager = ForumTopicManager(bot_token="test_token", state_dir=nested_dir)

            state = GroupForumState(chat_id="-1001234567890")
            manager._save_all_states({"-1001234567890": state})

            assert nested_dir.exists()
            assert (nested_dir / TOPIC_CONFIG_FILE).exists()

    def test_save_and_load_roundtrip(self):
        """Test save followed by load preserves data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)

            state = GroupForumState(
                chat_id="-1001234567890",
                is_forum=True,
                topics={"test": TopicConfig(name="test", thread_id=123)},
                admin_checked=True,
                is_admin=True,
            )
            manager._save_all_states({"-1001234567890": state})

            # Create new manager instance to test loading
            manager2 = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            states = manager2._load_all_states()

            assert "-1001234567890" in states
            loaded_state = states["-1001234567890"]
            assert loaded_state.is_forum is True
            assert loaded_state.topics["test"].thread_id == 123

    def test_save_updates_internal_state(self):
        """Test save updates internal _states dict."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            state = GroupForumState(chat_id="-1001234567890")
            manager._save_all_states({"-1001234567890": state})
            assert manager._states == {"-1001234567890": state}


class TestForumTopicManagerGetGroupState:
    """Tests for get_group_state method."""

    def test_get_group_state_creates_new(self):
        """Test get_group_state creates new state for unknown chat."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            state = manager.get_group_state("-1001234567890")
            assert state.chat_id == "-1001234567890"
            assert state.is_forum is False

    def test_get_group_state_returns_cached(self):
        """Test get_group_state returns cached state."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            state1 = manager.get_group_state("-1001234567890")
            state1.is_forum = True

            state2 = manager.get_group_state("-1001234567890")
            assert state2.is_forum is True
            assert state1 is state2

    def test_get_group_state_loads_from_disk(self):
        """Test get_group_state loads from disk when cache is empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            # Pre-populate state file
            state_file = Path(tmpdir) / TOPIC_CONFIG_FILE
            data = {
                "-1001234567890": {
                    "chat_id": "-1001234567890",
                    "is_forum": True,
                    "topics": {},
                    "admin_checked": True,
                    "is_admin": True,
                }
            }
            state_file.write_text(json.dumps(data))

            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            state = manager.get_group_state("-1001234567890")
            assert state.is_forum is True
            assert state.admin_checked is True


class TestForumTopicManagerApiRequests:
    """Tests for API request methods."""

    @respx.mock
    def test_make_request_success(self):
        """Test successful API request."""
        route = respx.post("https://api.telegram.org/bottest_token/getChat").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {"id": 123}})
        )

        manager = ForumTopicManager(bot_token="test_token")
        result = manager._make_request("getChat", {"chat_id": "-1001234567890"})

        assert route.called
        assert result == {"id": 123}

    @respx.mock
    def test_make_request_telegram_error(self):
        """Test API request with Telegram error."""
        respx.post("https://api.telegram.org/bottest_token/getChat").mock(
            return_value=httpx.Response(
                200, json={"ok": False, "error_code": 400, "description": "Bad Request"}
            )
        )

        manager = ForumTopicManager(bot_token="test_token")
        with pytest.raises(ForumTopicError) as exc_info:
            manager._make_request("getChat", {"chat_id": "-1001234567890"})
        assert "400" in str(exc_info.value)
        assert "Bad Request" in str(exc_info.value)

    @respx.mock
    def test_make_request_http_error(self):
        """Test API request with HTTP error."""
        respx.post("https://api.telegram.org/bottest_token/getChat").mock(
            return_value=httpx.Response(500, text="Internal Server Error")
        )

        manager = ForumTopicManager(bot_token="test_token")
        with pytest.raises(ForumTopicError) as exc_info:
            manager._make_request("getChat", {"chat_id": "-1001234567890"})
        assert "HTTP error" in str(exc_info.value)

    @respx.mock
    def test_make_request_network_error(self):
        """Test API request with network error."""
        respx.post("https://api.telegram.org/bottest_token/getChat").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )

        manager = ForumTopicManager(bot_token="test_token")
        with pytest.raises(ForumTopicError) as exc_info:
            manager._make_request("getChat", {"chat_id": "-1001234567890"})
        assert "HTTP error" in str(exc_info.value)


class TestForumTopicManagerCheckIsForum:
    """Tests for check_is_forum method."""

    @respx.mock
    def test_check_is_forum_true(self):
        """Test check_is_forum returns True for forum."""
        respx.post("https://api.telegram.org/bottest_token/getChat").mock(
            return_value=httpx.Response(
                200, json={"ok": True, "result": {"id": 123, "is_forum": True}}
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.check_is_forum("-1001234567890")
            assert result is True

            state = manager.get_group_state("-1001234567890")
            assert state.is_forum is True

    @respx.mock
    def test_check_is_forum_false(self):
        """Test check_is_forum returns False for non-forum."""
        respx.post("https://api.telegram.org/bottest_token/getChat").mock(
            return_value=httpx.Response(
                200, json={"ok": True, "result": {"id": 123, "is_forum": False}}
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.check_is_forum("-1001234567890")
            assert result is False

    @respx.mock
    def test_check_is_forum_api_error(self):
        """Test check_is_forum returns False on API error."""
        respx.post("https://api.telegram.org/bottest_token/getChat").mock(
            return_value=httpx.Response(400, json={"ok": False, "error_code": 400})
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.check_is_forum("-1001234567890")
            assert result is False


class TestForumTopicManagerCheckIsAdmin:
    """Tests for check_is_admin method."""

    @respx.mock
    def test_check_is_admin_true(self):
        """Test check_is_admin returns True when bot is admin with topic management."""
        respx.post("https://api.telegram.org/bottest_token/getChatMember").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {
                        "user": {"id": 123},
                        "status": "administrator",
                        "can_manage_topics": True,
                    },
                },
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.check_is_admin("-1001234567890")
            assert result is True

            state = manager.get_group_state("-1001234567890")
            assert state.is_admin is True
            assert state.admin_checked is True

    @respx.mock
    def test_check_is_admin_not_admin(self):
        """Test check_is_admin returns False when bot is not admin."""
        respx.post("https://api.telegram.org/bottest_token/getChatMember").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {"user": {"id": 123}, "status": "member"},
                },
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.check_is_admin("-1001234567890")
            assert result is False

    @respx.mock
    def test_check_is_admin_no_topic_permission(self):
        """Test check_is_admin returns False when bot can't manage topics."""
        respx.post("https://api.telegram.org/bottest_token/getChatMember").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {
                        "user": {"id": 123},
                        "status": "administrator",
                        "can_manage_topics": False,
                    },
                },
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.check_is_admin("-1001234567890")
            assert result is False

    @respx.mock
    def test_check_is_admin_creator_status(self):
        """Test check_is_admin returns True when bot is creator."""
        respx.post("https://api.telegram.org/bottest_token/getChatMember").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {
                        "user": {"id": 123},
                        "status": "creator",
                        "can_manage_topics": True,
                    },
                },
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.check_is_admin("-1001234567890")
            assert result is True


class TestForumTopicManagerCreateTopic:
    """Tests for create_forum_topic method."""

    @respx.mock
    def test_create_forum_topic_success(self):
        """Test successful topic creation."""
        respx.post("https://api.telegram.org/bottest_token/createForumTopic").mock(
            return_value=httpx.Response(
                200,
                json={"ok": True, "result": {"message_thread_id": 12345}},
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.create_forum_topic("-1001234567890", "Test Topic")
            assert result == 12345

    @respx.mock
    def test_create_forum_topic_with_icon_color(self):
        """Test topic creation with icon color."""
        route = respx.post("https://api.telegram.org/bottest_token/createForumTopic").mock(
            return_value=httpx.Response(
                200,
                json={"ok": True, "result": {"message_thread_id": 12345}},
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.create_forum_topic("-1001234567890", "Test Topic", icon_color=1)
            assert result == 12345

            request = json.loads(route.calls[0].request.content)
            assert request["icon_color"] == 1

    @respx.mock
    def test_create_forum_topic_failure(self):
        """Test topic creation failure returns None."""
        respx.post("https://api.telegram.org/bottest_token/createForumTopic").mock(
            return_value=httpx.Response(
                200,
                json={"ok": False, "error_code": 400, "description": "Topic exists"},
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.create_forum_topic("-1001234567890", "Test Topic")
            assert result is None


class TestForumTopicManagerSetupGroupTopics:
    """Tests for setup_group_topics method."""

    @respx.mock
    def test_setup_group_topics_success(self):
        """Test successful setup of all required topics."""
        respx.post("https://api.telegram.org/bottest_token/getChat").mock(
            return_value=httpx.Response(
                200, json={"ok": True, "result": {"id": 123, "is_forum": True}}
            )
        )
        respx.post("https://api.telegram.org/bottest_token/getChatMember").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {
                        "user": {"id": 123},
                        "status": "administrator",
                        "can_manage_topics": True,
                    },
                },
            )
        )
        respx.post("https://api.telegram.org/bottest_token/createForumTopic").mock(
            return_value=httpx.Response(
                200,
                json={"ok": True, "result": {"message_thread_id": 100}},
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.setup_group_topics("-1001234567890")

            # Should create all required topics
            assert len(result) == len(REQUIRED_TOPICS)
            for topic_name in REQUIRED_TOPICS:
                assert topic_name in result

    @respx.mock
    def test_setup_group_topics_not_forum(self):
        """Test setup raises error when chat is not forum."""
        respx.post("https://api.telegram.org/bottest_token/getChat").mock(
            return_value=httpx.Response(
                200, json={"ok": True, "result": {"id": 123, "is_forum": False}}
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            with pytest.raises(ForumTopicError) as exc_info:
                manager.setup_group_topics("-1001234567890")
            assert "not a forum supergroup" in str(exc_info.value)

    @respx.mock
    def test_setup_group_topics_not_admin(self):
        """Test setup raises error when bot is not admin."""
        respx.post("https://api.telegram.org/bottest_token/getChat").mock(
            return_value=httpx.Response(
                200, json={"ok": True, "result": {"id": 123, "is_forum": True}}
            )
        )
        respx.post("https://api.telegram.org/bottest_token/getChatMember").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {"user": {"id": 123}, "status": "member"},
                },
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            with pytest.raises(ForumTopicError) as exc_info:
                manager.setup_group_topics("-1001234567890")
            assert "not admin" in str(exc_info.value)

    @respx.mock
    def test_setup_group_topics_skips_existing(self):
        """Test setup skips topics that already exist."""
        respx.post("https://api.telegram.org/bottest_token/getChat").mock(
            return_value=httpx.Response(
                200, json={"ok": True, "result": {"id": 123, "is_forum": True}}
            )
        )
        respx.post("https://api.telegram.org/bottest_token/getChatMember").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {
                        "user": {"id": 123},
                        "status": "administrator",
                        "can_manage_topics": True,
                    },
                },
            )
        )
        respx.post("https://api.telegram.org/bottest_token/createForumTopic").mock(
            return_value=httpx.Response(
                200,
                json={"ok": True, "result": {"message_thread_id": 100}},
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            # First setup
            result1 = manager.setup_group_topics("-1001234567890")
            assert len(result1) == len(REQUIRED_TOPICS)

            # Second setup should use cached topics
            result2 = manager.setup_group_topics("-1001234567890")
            assert len(result2) == len(REQUIRED_TOPICS)


class TestForumTopicManagerGetThreadId:
    """Tests for thread ID lookup methods."""

    def test_get_topic_thread_id(self):
        """Test getting thread ID for a topic."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            state = manager.get_group_state("-1001234567890")
            state.topics["pull-request"] = TopicConfig(
                name="pull-request", thread_id=123
            )

            result = manager.get_topic_thread_id("-1001234567890", "pull-request")
            assert result == 123

    def test_get_topic_thread_id_missing(self):
        """Test getting thread ID for missing topic returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.get_topic_thread_id("-1001234567890", "missing")
            assert result is None

    def test_get_notification_thread_id_pr(self):
        """Test notification mapping for PR."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            state = manager.get_group_state("-1001234567890")
            state.topics["pull-request"] = TopicConfig(
                name="pull-request", thread_id=100
            )

            assert manager.get_notification_thread_id("-1001234567890", "pr") == 100
            assert (
                manager.get_notification_thread_id("-1001234567890", "pull-request")
                == 100
            )

    def test_get_notification_thread_id_issue(self):
        """Test notification mapping for issue."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            state = manager.get_group_state("-1001234567890")
            state.topics["issue"] = TopicConfig(name="issue", thread_id=200)

            assert manager.get_notification_thread_id("-1001234567890", "issue") == 200
            assert manager.get_notification_thread_id("-1001234567890", "issues") == 200

    def test_get_notification_thread_id_maintenance(self):
        """Test notification mapping for maintenance."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            state = manager.get_group_state("-1001234567890")
            state.topics["maintenance"] = TopicConfig(
                name="maintenance", thread_id=300
            )

            assert (
                manager.get_notification_thread_id("-1001234567890", "maintenance")
                == 300
            )
            assert manager.get_notification_thread_id("-1001234567890", "health") == 300
            assert manager.get_notification_thread_id("-1001234567890", "watchdog") == 300

    def test_get_notification_thread_id_discussion(self):
        """Test notification mapping for discussion."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            state = manager.get_group_state("-1001234567890")
            state.topics["discussion"] = TopicConfig(
                name="discussion", thread_id=400
            )

            assert (
                manager.get_notification_thread_id("-1001234567890", "discussion")
                == 400
            )
            assert manager.get_notification_thread_id("-1001234567890", "general") == 400

    def test_get_notification_thread_id_unknown(self):
        """Test notification mapping for unknown type returns None."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.get_notification_thread_id("-1001234567890", "unknown")
            assert result is None


class TestForumTopicManagerRequestAdminPromotion:
    """Tests for request_admin_promotion method."""

    @respx.mock
    def test_request_admin_promotion_success(self):
        """Test successful admin promotion request."""
        route = respx.post("https://api.telegram.org/bottest_token/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True, "result": {"message_id": 1}})
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.request_admin_promotion("-1001234567890")
            assert result is True
            assert route.called

            request = json.loads(route.calls[0].request.content)
            assert "Admin Required" in request["text"]
            assert request["parse_mode"] == "Markdown"

    @respx.mock
    def test_request_admin_promotion_failure(self):
        """Test admin promotion request failure."""
        respx.post("https://api.telegram.org/bottest_token/sendMessage").mock(
            return_value=httpx.Response(400, json={"ok": False})
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.request_admin_promotion("-1001234567890")
            assert result is False


class TestForumTopicManagerHandleBotAdded:
    """Tests for handle_bot_added method."""

    @respx.mock
    def test_handle_bot_added_non_forum(self):
        """Test handling bot added to non-forum group."""
        respx.post("https://api.telegram.org/bottest_token/getChat").mock(
            return_value=httpx.Response(
                200, json={"ok": True, "result": {"id": 123, "is_forum": False}}
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.handle_bot_added("-1001234567890", "supergroup")

            assert result["success"] is True
            assert result["is_forum"] is False
            assert result["topics_created"] == {}

    @respx.mock
    def test_handle_bot_added_not_admin(self):
        """Test handling bot added to forum but not admin."""
        respx.post("https://api.telegram.org/bottest_token/getChat").mock(
            return_value=httpx.Response(
                200, json={"ok": True, "result": {"id": 123, "is_forum": True}}
            )
        )
        respx.post("https://api.telegram.org/bottest_token/getChatMember").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {"user": {"id": 123}, "status": "member"},
                },
            )
        )
        respx.post("https://api.telegram.org/bottest_token/sendMessage").mock(
            return_value=httpx.Response(200, json={"ok": True})
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.handle_bot_added("-1001234567890", "supergroup")

            assert result["success"] is False
            assert result["is_forum"] is True
            assert result["is_admin"] is False
            assert result["admin_requested"] is True

    @respx.mock
    def test_handle_bot_added_success(self):
        """Test successful handling of bot added to forum."""
        respx.post("https://api.telegram.org/bottest_token/getChat").mock(
            return_value=httpx.Response(
                200, json={"ok": True, "result": {"id": 123, "is_forum": True}}
            )
        )
        respx.post("https://api.telegram.org/bottest_token/getChatMember").mock(
            return_value=httpx.Response(
                200,
                json={
                    "ok": True,
                    "result": {
                        "user": {"id": 123},
                        "status": "administrator",
                        "can_manage_topics": True,
                    },
                },
            )
        )
        respx.post("https://api.telegram.org/bottest_token/createForumTopic").mock(
            return_value=httpx.Response(
                200,
                json={"ok": True, "result": {"message_thread_id": 100}},
            )
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.handle_bot_added("-1001234567890", "supergroup")

            assert result["success"] is True
            assert result["is_forum"] is True
            assert result["is_admin"] is True
            assert len(result["topics_created"]) == len(REQUIRED_TOPICS)

    @respx.mock
    def test_handle_bot_added_api_error_graceful(self):
        """Test handling API error gracefully during bot added processing.

        When API fails, check_is_forum returns False and the bot treats it
        as a non-forum chat, returning success=True (skip rather than fail).
        """
        respx.post("https://api.telegram.org/bottest_token/getChat").mock(
            side_effect=httpx.ConnectError("Connection failed")
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.handle_bot_added("-1001234567890", "supergroup")

            # API errors are caught and treated as non-forum (graceful skip)
            assert result["success"] is True
            assert result["is_forum"] is False
            assert result["error"] is None


class TestForumTopicError:
    """Tests for ForumTopicError exception."""

    def test_error_with_chat_id(self):
        """Test error with chat ID."""
        error = ForumTopicError("Test error", chat_id="-1001234567890")
        assert str(error) == "Test error"
        assert error.chat_id == "-1001234567890"

    def test_error_without_chat_id(self):
        """Test error without chat ID."""
        error = ForumTopicError("Test error")
        assert str(error) == "Test error"
        assert error.chat_id is None


class TestForumTopicManagerGetAllGroupStates:
    """Tests for get_all_group_states method."""

    def test_get_all_group_states_empty(self):
        """Test getting all states when empty."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            result = manager.get_all_group_states()
            assert result == {}

    def test_get_all_group_states_populated(self):
        """Test getting all states when populated."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            manager._states = {
                "-1001234567890": GroupForumState(chat_id="-1001234567890"),
                "-1000987654321": GroupForumState(chat_id="-1000987654321"),
            }
            result = manager.get_all_group_states()
            assert len(result) == 2
            assert "-1001234567890" in result
            assert "-1000987654321" in result

    def test_get_all_group_states_returns_copy(self):
        """Test that get_all_group_states returns a copy."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = ForumTopicManager(bot_token="test_token", state_dir=tmpdir)
            manager._states = {
                "-1001234567890": GroupForumState(chat_id="-1001234567890"),
            }
            result = manager.get_all_group_states()
            result["-1001234567890"].is_forum = True
            assert manager._states["-1001234567890"].is_forum is False
