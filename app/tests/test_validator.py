"""Tests for validator module."""

import pytest

from app.validator import Validator, ValidFileName, ValidFolderName


class TestValidator:
    """Tests for Validator class."""

    @pytest.fixture
    def validator(self) -> Validator:
        """Create a validator instance."""
        return Validator()

    class TestValidateFolderName:
        """Tests for validate_folder_name method."""

        def test_valid_folder_names(self, validator: Validator):
            """Test that valid folder names are accepted."""
            valid_names = [
                "test-folder",
                "test_folder",
                "TestFolder",
                "test123",
                "folder-with-many_parts",
                "a",
                "ABC123-xyz_789",
            ]
            for name in valid_names:
                result = validator.validate_folder_name(name)
                assert isinstance(result, ValidFolderName)
                assert result == name

        def test_empty_folder_name(self, validator: Validator):
            """Test that empty folder name raises ValueError."""
            with pytest.raises(ValueError, match="Path cannot be empty"):
                validator.validate_folder_name("")

        def test_folder_name_with_path_traversal(self, validator: Validator):
            """Test that path traversal attempts are rejected."""
            invalid_names = [
                "..",
                "../test",
                "test/..",
                "../../etc/passwd",
            ]
            for name in invalid_names:
                with pytest.raises(
                    ValueError,
                    match="Path traversal attempt detected",
                ):
                    validator.validate_folder_name(name)

        def test_folder_name_with_special_characters(self, validator: Validator):
            """Test that special characters are rejected."""
            invalid_names = [
                "test folder",  # space
                "test@folder",  # special character
                "test.folder",  # dot (not allowed in folder names)
                "test*folder",  # asterisk
                "test?folder",  # question mark
                "test|folder",  # pipe
                "test<folder",  # less than
                "test>folder",  # greater than
            ]
            for name in invalid_names:
                with pytest.raises(ValueError, match="Invalid path"):
                    validator.validate_folder_name(name)

        def test_folder_name_with_slashes(self, validator: Validator):
            """Test that folder names with slashes are rejected as path traversal."""
            invalid_names = [
                "test/folder",  # forward slash
                "test\\folder",  # backslash
            ]
            for name in invalid_names:
                with pytest.raises(ValueError, match="Path traversal attempt detected"):
                    validator.validate_folder_name(name)

    class TestValidateFileName:
        """Tests for validate_file_name method."""

        def test_valid_file_names(self, validator: Validator):
            """Test that valid file names are accepted."""
            valid_names = [
                "test.txt",
                "test-file.txt",
                "test_file.txt",
                "TestFile.TXT",
                "file123.csv",
                "data-file_v2.json",
                "report.2024.pdf",
            ]
            for name in valid_names:
                result = validator.validate_file_name(name)
                assert isinstance(result, ValidFileName)
                assert result == name

        def test_empty_file_name(self, validator: Validator):
            """Test that empty file name raises ValueError."""
            with pytest.raises(ValueError, match="File name cannot be empty"):
                validator.validate_file_name("")

        def test_file_name_without_extension(self, validator: Validator):
            """Test that file names without extensions are rejected."""
            invalid_names = [
                "test",
                "testfile",
                "test-file",
            ]
            for name in invalid_names:
                with pytest.raises(ValueError, match="Invalid file name"):
                    validator.validate_file_name(name)

        def test_file_name_with_path_traversal(self, validator: Validator):
            """Test that path traversal attempts are rejected."""
            invalid_names = [
                "../test.txt",
                "test/../file.txt",
                "../../etc/passwd.txt",
                "..\\test.txt",
                "file..txt",  # double dots
            ]
            for name in invalid_names:
                with pytest.raises(
                    ValueError,
                    match="Path traversal attempt detected",
                ):
                    validator.validate_file_name(name)

        def test_file_name_with_special_characters(self, validator: Validator):
            """Test that special characters are rejected."""
            invalid_names = [
                "test file.txt",  # space
                "test@file.txt",  # special character
                "test*file.txt",  # asterisk
                "test?file.txt",  # question mark
                "test|file.txt",  # pipe
                "test<file.txt",  # less than
                "test>file.txt",  # greater than
            ]
            for name in invalid_names:
                with pytest.raises(
                    ValueError,
                    match="Invalid file name",
                ):
                    validator.validate_file_name(name)

        def test_file_name_with_slashes(self, validator: Validator):
            """Test that file names with slashes are rejected as path traversal."""
            invalid_names = [
                "test/file.txt",  # forward slash
                "test\\file.txt",  # backslash
            ]
            for name in invalid_names:
                with pytest.raises(ValueError, match="Path traversal attempt detected"):
                    validator.validate_file_name(name)


class TestValidFolderName:
    """Tests for ValidFolderName type."""

    def test_valid_folder_name_is_string(self):
        """Test that ValidFolderName is a string subclass."""
        name = ValidFolderName("test")
        assert isinstance(name, str)
        assert name == "test"


class TestValidFileName:
    """Tests for ValidFileName type."""

    def test_valid_file_name_is_string(self):
        """Test that ValidFileName is a string subclass."""
        name = ValidFileName("test.txt")
        assert isinstance(name, str)
        assert name == "test.txt"
