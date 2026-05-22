"""Tests for auth module."""

import pytest
from fastapi import HTTPException
from fastapi.security import HTTPAuthorizationCredentials

from app.auth import verify_token


class TestVerifyToken:
    """Tests for verify_token function."""

    def test_valid_token(self, mock_token: str):
        """Test that valid token is accepted."""
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials=mock_token)
        result = verify_token(credentials)
        assert result == mock_token

    def test_invalid_token(self, mock_token: str):
        """Test that invalid token raises HTTPException."""
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="wrong-token")
        with pytest.raises(HTTPException) as exc_info:
            verify_token(credentials)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid token"

    def test_empty_token(self):
        """Test that empty token raises HTTPException."""
        credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="")
        with pytest.raises(HTTPException) as exc_info:
            verify_token(credentials)

        assert exc_info.value.status_code == 401
        assert exc_info.value.detail == "Invalid token"
