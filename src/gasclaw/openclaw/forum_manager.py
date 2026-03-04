"""Forum topic management for Telegram supergroups.

This module handles auto-creation of forum topics when the bot joins a group,
and persists topic thread IDs for routing notifications.
"""

from __future__ import annotations

import contextlib
import json
import logging
import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

logger = logging.getLogger(__name__)

__all__ = [
    "ForumTopicManager",
    "TopicConfig",
    "ForumTopicError",
]

# Default configuration
DEFAULT_STATE_DIR = "/workspace/state"
TOPIC_CONFIG_FILE = "forum_topics.json"

# Required topic names
REQUIRED_TOPICS = [
    "pull-request",
    "issue",
    "maintenance",
    "discussion",
]


class ForumTopicError(Exception):
    """Raised when forum topic operations fail."""

    def __init__(self, message: str, chat_id: str | None = None) -> None:
        """Initialize forum topic error.

        Args:
            message: Error message.
            chat_id: Chat ID where the error occurred.
        """
        super().__init__(message)
        self.chat_id = chat_id


@dataclass
class TopicConfig:
    """Configuration for a forum topic."""

    name: str
    thread_id: int | None = None
    created_at: float | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert topic config to dictionary."""
        return {
            "name": self.name,
            "thread_id": self.thread_id,
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> TopicConfig:
        """Create topic config from dictionary."""
        return cls(
            name=data.get("name", ""),
            thread_id=data.get("thread_id"),
            created_at=data.get("created_at"),
        )


@dataclass
class GroupForumState:
    """Forum state for a specific group chat."""

    chat_id: str
    is_forum: bool = False
    topics: dict[str, TopicConfig] = field(default_factory=dict)
    admin_checked: bool = False
    is_admin: bool = False

    def to_dict(self) -> dict[str, Any]:
        """Convert group state to dictionary."""
        return {
            "chat_id": self.chat_id,
            "is_forum": self.is_forum,
            "topics": {k: v.to_dict() for k, v in self.topics.items()},
            "admin_checked": self.admin_checked,
            "is_admin": self.is_admin,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GroupForumState:
        """Create group state from dictionary."""
        topics = {
            k: TopicConfig.from_dict(v)
            for k, v in data.get("topics", {}).items()
        }
        return cls(
            chat_id=data.get("chat_id", ""),
            is_forum=data.get("is_forum", False),
            topics=topics,
            admin_checked=data.get("admin_checked", False),
            is_admin=data.get("is_admin", False),
        )

    def has_all_topics(self) -> bool:
        """Check if all required topics exist."""
        return all(
            topic in self.topics and self.topics[topic].thread_id is not None
            for topic in REQUIRED_TOPICS
        )

    def get_thread_id(self, topic_name: str) -> int | None:
        """Get thread ID for a topic."""
        if topic_name in self.topics:
            return self.topics[topic_name].thread_id
        return None


class ForumTopicManager:
    """Manage forum topics for Telegram supergroups."""

    def __init__(
        self,
        bot_token: str,
        state_dir: str | Path = DEFAULT_STATE_DIR,
    ) -> None:
        """Initialize the forum topic manager.

        Args:
            bot_token: Telegram bot token.
            state_dir: Directory to store topic configuration.
        """
        self.bot_token = bot_token
        self.state_dir = Path(state_dir)
        self._states: dict[str, GroupForumState] = {}
        self._base_url = f"https://api.telegram.org/bot{bot_token}"

    @property
    def state_file(self) -> Path:
        """Path to the topic configuration file."""
        return self.state_dir / TOPIC_CONFIG_FILE

    def _load_all_states(self) -> dict[str, GroupForumState]:
        """Load all group forum states from disk."""
        if self.state_file.is_file():
            try:
                data = json.loads(self.state_file.read_text())
                return {
                    k: GroupForumState.from_dict(v)
                    for k, v in data.items()
                }
            except (json.JSONDecodeError, OSError) as e:
                logger.warning("Failed to load forum topic state: %s", e)
        return {}

    def _save_all_states(self, states: dict[str, GroupForumState]) -> None:
        """Save all group forum states to disk atomically."""
        self.state_dir.mkdir(parents=True, exist_ok=True)

        data = {k: v.to_dict() for k, v in states.items()}

        # Write to temp file in same directory, then rename atomically
        fd, temp_path = tempfile.mkstemp(
            dir=self.state_dir, prefix=".forum-topics-", suffix=".tmp"
        )
        try:
            with os.fdopen(fd, "w") as f:
                json.dump(data, f, indent=2)
            os.replace(temp_path, self.state_file)
            self._states = states
        except (OSError, TypeError, ValueError) as e:
            # Clean up temp file on failure
            with contextlib.suppress(OSError):
                os.unlink(temp_path)
            logger.error("Failed to save forum topic state: %s", e)
            raise

    def get_group_state(self, chat_id: str) -> GroupForumState:
        """Get forum state for a group (cached or loaded)."""
        if not self._states:
            self._states = self._load_all_states()

        if chat_id not in self._states:
            self._states[chat_id] = GroupForumState(chat_id=chat_id)

        return self._states[chat_id]

    def _make_request(
        self, method: str, params: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Make a request to the Telegram Bot API.

        Args:
            method: API method name.
            params: Request parameters.

        Returns:
            Response data.

        Raises:
            ForumTopicError: If the request fails.
        """
        url = f"{self._base_url}/{method}"
        try:
            response = httpx.post(
                url,
                json=params or {},
                timeout=30.0,
            )
            response.raise_for_status()
            data = response.json()

            if not data.get("ok"):
                error_code = data.get("error_code")
                description = data.get("description", "Unknown error")
                raise ForumTopicError(
                    f"Telegram API error {error_code}: {description}"
                )

            result: dict[str, Any] = data.get("result", {})
            return result
        except httpx.HTTPError as e:
            raise ForumTopicError(f"HTTP error: {e}") from e

    def check_is_forum(self, chat_id: str) -> bool:
        """Check if a chat is a forum supergroup.

        Args:
            chat_id: Chat ID to check.

        Returns:
            True if the chat is a forum, False otherwise.
        """
        try:
            chat_info = self._make_request("getChat", {"chat_id": chat_id})
            is_forum: bool = chat_info.get("is_forum", False)

            state = self.get_group_state(chat_id)
            state.is_forum = is_forum
            self._save_all_states(self._states)

            return is_forum
        except ForumTopicError as e:
            logger.warning("Failed to check if chat %s is forum: %s", chat_id, e)
            return False

    def check_is_admin(self, chat_id: str) -> bool:
        """Check if the bot is an admin in the chat.

        Args:
            chat_id: Chat ID to check.

        Returns:
            True if bot is admin, False otherwise.
        """
        try:
            member_info = self._make_request(
                "getChatMember",
                {"chat_id": chat_id, "user_id": "me"},
            )
            status = member_info.get("status", "")
            is_admin = status in ("administrator", "creator")
            can_manage_topics = member_info.get("can_manage_topics", False)

            state = self.get_group_state(chat_id)
            state.admin_checked = True
            state.is_admin = is_admin and can_manage_topics
            self._save_all_states(self._states)

            return state.is_admin
        except ForumTopicError as e:
            logger.warning("Failed to check admin status in %s: %s", chat_id, e)
            return False

    def create_forum_topic(
        self,
        chat_id: str,
        name: str,
        icon_color: int | None = None,
    ) -> int | None:
        """Create a forum topic in a supergroup.

        Args:
            chat_id: Chat ID to create topic in.
            name: Topic name.
            icon_color: Optional icon color (1-6).

        Returns:
            Thread ID of the created topic, or None if failed.
        """
        params: dict[str, Any] = {
            "chat_id": chat_id,
            "name": name,
        }
        if icon_color is not None:
            params["icon_color"] = icon_color

        try:
            result = self._make_request("createForumTopic", params)
            thread_id: int | None = result.get("message_thread_id")

            if thread_id:
                logger.info(
                    "Created forum topic '%s' in chat %s (thread_id=%s)",
                    name,
                    chat_id,
                    thread_id,
                )
                return thread_id
        except ForumTopicError as e:
            logger.warning("Failed to create forum topic '%s': %s", name, e)

        return None

    def setup_group_topics(self, chat_id: str) -> dict[str, int]:
        """Set up all required forum topics for a group.

        Args:
            chat_id: Chat ID to set up topics in.

        Returns:
            Dict mapping topic names to thread IDs.

        Raises:
            ForumTopicError: If setup fails.
        """
        state = self.get_group_state(chat_id)

        # Check if it's a forum
        if not state.is_forum:
            is_forum = self.check_is_forum(chat_id)
            if not is_forum:
                raise ForumTopicError(
                    f"Chat {chat_id} is not a forum supergroup", chat_id
                )

        # Check admin status
        if not state.is_admin:
            is_admin = self.check_is_admin(chat_id)
            if not is_admin:
                raise ForumTopicError(
                    f"Bot is not admin in chat {chat_id}", chat_id
                )

        created_topics: dict[str, int] = {}

        # Create each required topic
        for topic_name in REQUIRED_TOPICS:
            # Check if topic already exists
            if topic_name in state.topics and state.topics[topic_name].thread_id:
                created_topics[topic_name] = state.topics[topic_name].thread_id  # type: ignore
                continue

            # Create the topic
            import time

            thread_id = self.create_forum_topic(chat_id, topic_name)
            if thread_id:
                state.topics[topic_name] = TopicConfig(
                    name=topic_name,
                    thread_id=thread_id,
                    created_at=time.time(),
                )
                created_topics[topic_name] = thread_id

        # Save state
        self._save_all_states(self._states)

        return created_topics

    def get_topic_thread_id(self, chat_id: str, topic_name: str) -> int | None:
        """Get the thread ID for a specific topic in a group.

        Args:
            chat_id: Chat ID.
            topic_name: Topic name (e.g., 'pull-request', 'issue').

        Returns:
            Thread ID if found, None otherwise.
        """
        state = self.get_group_state(chat_id)
        return state.get_thread_id(topic_name)

    def get_notification_thread_id(
        self, chat_id: str, notification_type: str
    ) -> int | None:
        """Get the appropriate thread ID for a notification type.

        Args:
            chat_id: Chat ID.
            notification_type: Type of notification (pr, issue, maintenance, discussion).

        Returns:
            Thread ID if configured, None otherwise.
        """
        mapping = {
            "pr": "pull-request",
            "pull-request": "pull-request",
            "issue": "issue",
            "issues": "issue",
            "maintenance": "maintenance",
            "health": "maintenance",
            "watchdog": "maintenance",
            "discussion": "discussion",
            "general": "discussion",
        }

        topic_name = mapping.get(notification_type.lower())
        if not topic_name:
            return None

        return self.get_topic_thread_id(chat_id, topic_name)

    def request_admin_promotion(self, chat_id: str) -> bool:
        """Send a message asking to be promoted to admin.

        Args:
            chat_id: Chat ID to send request to.

        Returns:
            True if message sent successfully, False otherwise.
        """
        message = (
            "🤖 *Admin Required*\n\n"
            "To create forum topics and manage notifications, "
            "please promote me to administrator with the following permissions:\n\n"
            "• Manage topics\n"
            "• Delete messages\n\n"
            "Once promoted, I'll automatically create the required topics:\n"
            "• pull-request — PR notifications\n"
            "• issue — Issue tracking\n"
            "• maintenance — System alerts\n"
            "• discussion — General chat"
        )

        try:
            self._make_request(
                "sendMessage",
                {
                    "chat_id": chat_id,
                    "text": message,
                    "parse_mode": "Markdown",
                },
            )
            return True
        except ForumTopicError as e:
            logger.warning("Failed to send admin request: %s", e)
            return False

    def handle_bot_added(self, chat_id: str, chat_type: str) -> dict[str, Any]:
        """Handle the bot being added to a group.

        This is the main entry point for setting up forum topics when
        the bot joins a new group.

        Args:
            chat_id: Chat ID the bot was added to.
            chat_type: Type of chat (supergroup, group, etc.).

        Returns:
            Dict with result information.
        """
        result = {
            "success": False,
            "is_forum": False,
            "is_admin": False,
            "topics_created": {},
            "admin_requested": False,
            "error": None,
        }

        try:
            # Check if it's a forum
            is_forum = self.check_is_forum(chat_id)
            result["is_forum"] = is_forum

            if not is_forum:
                logger.info("Chat %s is not a forum supergroup, skipping topic setup", chat_id)
                result["success"] = True
                return result

            # Check admin status
            is_admin = self.check_is_admin(chat_id)
            result["is_admin"] = is_admin

            if not is_admin:
                logger.info("Bot not admin in %s, requesting promotion", chat_id)
                result["admin_requested"] = self.request_admin_promotion(chat_id)
                return result

            # Set up topics
            topics = self.setup_group_topics(chat_id)
            result["topics_created"] = topics
            result["success"] = True

            logger.info(
                "Successfully set up %d forum topics in chat %s",
                len(topics),
                chat_id,
            )

        except ForumTopicError as e:
            result["error"] = str(e)
            logger.error("Failed to handle bot added to %s: %s", chat_id, e)

        return result

    def get_all_group_states(self) -> dict[str, GroupForumState]:
        """Get all group forum states.

        Returns:
            Dict mapping chat IDs to their forum states.
        """
        if not self._states:
            self._states = self._load_all_states()
        # Return deep copy to prevent external modification of internal state
        return {
            k: GroupForumState.from_dict(v.to_dict())
            for k, v in self._states.items()
        }
