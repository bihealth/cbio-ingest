import re


class ValidFolderName(str):
    """A validated folder name that is safe to use in filesystem operations."""

    pass


class ValidFileName(str):
    """A validated file name that is safe to use in filesystem operations."""

    pass


class Validator:
    def validate_folder_name(self, name: str) -> ValidFolderName:
        """Validate that a folder name is safe and doesn't contain malicious characters.

        Args:
            name: The folder name to validate

        Raises:
            ValueError: If the name contains unsafe characters
        """
        if not name:
            raise ValueError("Path cannot be empty")

        # Explicitly check for path traversal attempts first (security-critical)
        if ".." in name or "/" in name or "\\" in name:
            raise ValueError(f"Path traversal attempt detected: {name}")

        # Only allow alphanumeric characters, hyphens, and underscores
        if not re.match(r"^[a-zA-Z0-9_-]+$", name):
            raise ValueError(
                f"Invalid path: {name}. Only alphanumeric, hyphens, and underscores allowed"
            )

        return ValidFolderName(name)

    def validate_file_name(self, name: str) -> ValidFileName:
        """Validate that a file name is safe and doesn't contain malicious characters.

        Args:
            name: The file name to validate

        Raises:
            ValueError: If the name contains unsafe characters
        """
        if not name:
            raise ValueError("File name cannot be empty")

        # Explicitly check for path traversal attempts first (security-critical)
        if ".." in name or "/" in name or "\\" in name:
            raise ValueError(f"Path traversal attempt detected: {name}")

        # Only allow alphanumeric characters, hyphens, underscores, dots, and a single extension
        if not re.match(r"^[a-zA-Z0-9._-]+\.[a-zA-Z0-9]+$", name):
            raise ValueError(
                f"Invalid file name: {name}. "
                "Only alphanumeric, hyphens, underscores, and a single extension allowed"
            )

        return ValidFileName(name)
