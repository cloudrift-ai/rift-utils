import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock
import sys
import os

# Add the parent directory to the path so we can import the module
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from configure.commands.configure_libvirt import ensure_qemu_conf_lines, verify_qemu_conf


@pytest.fixture
def mock_qemu_conf():
    """Fixture to mock the QEMU_CONF path."""
    with patch('configure.commands.configure_libvirt.QEMU_CONF') as mock:
        mock.parent.mkdir = MagicMock()
        yield mock


@pytest.fixture
def capture_file_write(mock_qemu_conf):
    """Fixture to capture file write operations."""
    written_content = None

    def capture_write(*args, **kwargs):
        nonlocal written_content
        mock_file = MagicMock()
        mock_file.__enter__ = MagicMock()
        mock_file.__exit__ = MagicMock()

        def write_handler(content):
            nonlocal written_content
            written_content = content

        mock_file.__enter__.return_value.write = write_handler
        return mock_file

    mock_qemu_conf.open = MagicMock(side_effect=capture_write)
    return lambda: written_content


class TestEnsureQemuConfLines:
    """Test cases for the ensure_qemu_conf_lines function."""

    def test_empty_file(self, mock_qemu_conf, capture_file_write):
        """Test with an empty qemu.conf file."""
        mock_qemu_conf.exists.return_value = True
        mock_qemu_conf.read_text.return_value = ""

        result = ensure_qemu_conf_lines()

        assert result is True, "Should return True for modifications made"
        written_content = capture_file_write()
        assert 'user = "root"' in written_content
        assert 'group = "root"' in written_content

    def test_commented_user_and_group(self, mock_qemu_conf, capture_file_write):
        """Test with commented user and group lines."""
        mock_qemu_conf.exists.return_value = True
        mock_qemu_conf.read_text.return_value = """# Some config
#user = "qemu"
#group = "qemu"
# Other config"""

        result = ensure_qemu_conf_lines()

        assert result is True
        written_content = capture_file_write()
        lines = written_content.splitlines()
        assert 'user = "root"' in lines
        assert 'group = "root"' in lines
        assert '#user = "qemu"' not in lines
        assert '#group = "qemu"' not in lines

    def test_commented_with_spaces(self, mock_qemu_conf, capture_file_write):
        """Test with commented lines that have spaces."""
        mock_qemu_conf.exists.return_value = True
        mock_qemu_conf.read_text.return_value = """# Some config
# user = "qemu"
#  group = "qemu"
# Other config"""

        result = ensure_qemu_conf_lines()

        assert result is True
        written_content = capture_file_write()
        lines = written_content.splitlines()
        assert 'user = "root"' in lines
        assert 'group = "root"' in lines

    def test_already_configured(self, mock_qemu_conf):
        """Test when user and group are already set to root."""
        mock_qemu_conf.exists.return_value = True
        mock_qemu_conf.read_text.return_value = """# Config
user = "root"
group = "root"
# Other settings"""

        result = ensure_qemu_conf_lines()

        assert result is False, "Should return False when already configured"

    def test_wrong_user_values(self, mock_qemu_conf, capture_file_write):
        """Test with user and group set to non-root values."""
        mock_qemu_conf.exists.return_value = True
        mock_qemu_conf.read_text.return_value = """# Config
user = "qemu"
group = "kvm"
# Other settings"""

        result = ensure_qemu_conf_lines()

        assert result is True
        written_content = capture_file_write()
        lines = written_content.splitlines()
        assert 'user = "root"' in lines
        assert 'group = "root"' in lines
        assert 'user = "qemu"' not in lines
        assert 'group = "kvm"' not in lines

    def test_mixed_commented_uncommented(self, mock_qemu_conf, capture_file_write):
        """Test with one commented and one uncommented line."""
        mock_qemu_conf.exists.return_value = True
        mock_qemu_conf.read_text.return_value = """# Config
#user = "qemu"
group = "kvm"
# Other settings"""

        result = ensure_qemu_conf_lines()

        assert result is True
        written_content = capture_file_write()
        lines = written_content.splitlines()
        assert 'user = "root"' in lines
        assert 'group = "root"' in lines
        assert '#user = "qemu"' not in lines
        assert 'group = "kvm"' not in lines

    def test_file_not_exists(self, mock_qemu_conf, capture_file_write):
        """Test when qemu.conf doesn't exist."""
        mock_qemu_conf.exists.return_value = False
        mock_qemu_conf.read_text.return_value = ""

        result = ensure_qemu_conf_lines()

        assert result is True
        written_content = capture_file_write()
        assert 'user = "root"' in written_content
        assert 'group = "root"' in written_content

    def test_real_world_qemu_conf(self, mock_qemu_conf, capture_file_write):
        """Test with a realistic qemu.conf file content."""
        mock_qemu_conf.exists.return_value = True
        mock_qemu_conf.read_text.return_value = """# Master configuration file for the QEMU driver.

# The user for QEMU processes run by the system instance.
#
#       user = "qemu"   # A user named "qemu"
#       user = "+0"     # Super user (uid=0)
#
#user = "root"
#group = "root"

# Whether libvirt should dynamically change file ownership
#dynamic_ownership = 1"""

        result = ensure_qemu_conf_lines()

        assert result is True

        written_content = capture_file_write()
        assert 'user = "root"' in written_content
        assert 'group = "root"' in written_content

        lines = written_content.splitlines()
        user_lines = [line for line in lines if 'user = "root"' in line]
        group_lines = [line for line in lines if 'group = "root"' in line]

        uncommented_user = [line for line in user_lines if not line.strip().startswith('#')]
        uncommented_group = [line for line in group_lines if not line.strip().startswith('#')]

        assert len(uncommented_user) == 1, f"Should have exactly one uncommented user line, got: {uncommented_user}"
        assert len(uncommented_group) == 1, f"Should have exactly one uncommented group line, got: {uncommented_group}"

    def test_only_user_configured(self, mock_qemu_conf, capture_file_write):
        """Test when only user is already configured."""
        mock_qemu_conf.exists.return_value = True
        mock_qemu_conf.read_text.return_value = """# Config
user = "root"
#group = "qemu"
# Other settings"""

        result = ensure_qemu_conf_lines()

        assert result is True
        written_content = capture_file_write()
        lines = written_content.splitlines()
        assert 'user = "root"' in lines
        assert 'group = "root"' in lines
        # Should only have one user = "root" line
        user_count = sum(1 for line in lines if line.strip() == 'user = "root"')
        assert user_count == 1

    def test_only_group_configured(self, mock_qemu_conf, capture_file_write):
        """Test when only group is already configured."""
        mock_qemu_conf.exists.return_value = True
        mock_qemu_conf.read_text.return_value = """# Config
#user = "qemu"
group = "root"
# Other settings"""

        result = ensure_qemu_conf_lines()

        assert result is True
        written_content = capture_file_write()
        lines = written_content.splitlines()
        assert 'user = "root"' in lines
        assert 'group = "root"' in lines
        # Should only have one group = "root" line
        group_count = sum(1 for line in lines if line.strip() == 'group = "root"')
        assert group_count == 1


class TestVerifyQemuConf:
    """Test cases for the verify_qemu_conf function."""

    def test_verify_success(self, mock_qemu_conf):
        """Test verify_qemu_conf when configuration is correct."""
        mock_qemu_conf.exists.return_value = True
        mock_qemu_conf.read_text.return_value = """# Config
user = "root"
group = "root"
# Other settings"""

        result = verify_qemu_conf()

        assert result is True

    def test_verify_failure_wrong_values(self, mock_qemu_conf):
        """Test verify_qemu_conf when configuration has wrong values."""
        mock_qemu_conf.exists.return_value = True
        mock_qemu_conf.read_text.return_value = """# Config
user = "qemu"
group = "kvm"
# Other settings"""

        result = verify_qemu_conf()

        assert result is False

    def test_verify_failure_partial(self, mock_qemu_conf):
        """Test verify_qemu_conf when only one setting is correct."""
        mock_qemu_conf.exists.return_value = True
        mock_qemu_conf.read_text.return_value = """# Config
user = "root"
group = "kvm"
# Other settings"""

        result = verify_qemu_conf()

        assert result is False

    def test_verify_failure_commented(self, mock_qemu_conf):
        """Test verify_qemu_conf when settings are commented out."""
        mock_qemu_conf.exists.return_value = True
        mock_qemu_conf.read_text.return_value = """# Config
#user = "root"
#group = "root"
# Other settings"""

        result = verify_qemu_conf()

        assert result is False

    def test_verify_file_not_exists(self, mock_qemu_conf):
        """Test verify_qemu_conf when file doesn't exist."""
        mock_qemu_conf.exists.return_value = False

        result = verify_qemu_conf()

        assert result is False

    def test_verify_empty_file(self, mock_qemu_conf):
        """Test verify_qemu_conf with an empty file."""
        mock_qemu_conf.exists.return_value = True
        mock_qemu_conf.read_text.return_value = ""

        result = verify_qemu_conf()

        assert result is False


@pytest.mark.parametrize("input_content,expected_result,expected_modifications", [
    ("", True, True),  # Empty file
    ("user = \"root\"\ngroup = \"root\"", False, False),  # Already configured
    ("#user = \"qemu\"\n#group = \"qemu\"", True, True),  # Commented lines
    ("user = \"qemu\"\ngroup = \"kvm\"", True, True),  # Wrong values
])
def test_parametrized_ensure_qemu_conf_lines(mock_qemu_conf, capture_file_write,
                                             input_content, expected_result,
                                             expected_modifications):
    """Parametrized test for various qemu.conf configurations."""
    mock_qemu_conf.exists.return_value = True
    mock_qemu_conf.read_text.return_value = input_content

    result = ensure_qemu_conf_lines()

    assert result == expected_result

    if expected_modifications:
        written_content = capture_file_write()
        assert 'user = "root"' in written_content
        assert 'group = "root"' in written_content