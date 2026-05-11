"""Tests for scheduler module."""

import os
from unittest.mock import patch


class TestScheduler:
    """Tests for scheduler module."""

    def test_queue_exists(self):
        """Test that queue object is available."""
        from app.scheduler import queue

        assert queue is not None
        assert hasattr(queue, "enqueue")

    def test_redis_host_from_env(self):
        """Test that Redis host is read from environment."""
        with patch.dict(os.environ, {"REDIS_HOST": "test-host", "REDIS_PORT": "1234"}):
            # Need to reload to pick up new env vars
            import importlib

            import app.scheduler

            importlib.reload(app.scheduler)

            assert app.scheduler.redis_host == "test-host"
            assert app.scheduler.redis_port == 1234

    def test_redis_defaults(self):
        """Test default Redis configuration values."""
        with patch.dict(os.environ, {}, clear=True):
            import importlib

            import app.scheduler

            importlib.reload(app.scheduler)

            # Should fall back to defaults when env vars not set
            assert app.scheduler.redis_host in [
                "localhost",
                os.getenv("REDIS_HOST", "localhost"),
            ]
            assert app.scheduler.redis_port in [
                6379,
                int(os.getenv("REDIS_PORT", "6379")),
            ]

    def test_queue_has_redis_connection(self):
        """Test that queue has a Redis connection."""
        from app.scheduler import queue

        # Verify queue has connection attribute
        assert hasattr(queue, "connection")
        assert queue.connection is not None

    def test_redis_port_type_conversion(self):
        """Test that Redis port is converted to integer."""
        with patch.dict(os.environ, {"REDIS_PORT": "9999"}):
            import importlib

            import app.scheduler

            importlib.reload(app.scheduler)

            assert isinstance(app.scheduler.redis_port, int)
            assert app.scheduler.redis_port == 9999
