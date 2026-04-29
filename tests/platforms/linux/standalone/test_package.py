import os
import stat
import sys
from zipfile import ZipFile

import pytest

from briefcase.platforms.linux.standalone import LinuxStandalonePackageCommand

from ....utils import create_file


@pytest.fixture
def package_command(dummy_console, tmp_path, first_app_config):
    command = LinuxStandalonePackageCommand(
        console=dummy_console,
        base_path=tmp_path / "base_path",
        data_path=tmp_path / "briefcase",
    )
    command.tools.host_arch = "x86_64"

    (tmp_path / "base_path/dist").mkdir(parents=True)

    return command


@pytest.fixture
def populated_bundle(tmp_path):
    """Lay out a fake standalone bundle on disk."""
    package_path = (
        tmp_path / "base_path/build/first-app/linux/standalone/first-app-0.0.1"
    )
    create_file(package_path / "bin/first-app", "fake elf binary")
    create_file(
        package_path / "python/bin/python3.13",
        "#!/embedded/python\n",
    )
    create_file(
        package_path / "app/first_app/__main__.py",
        "print('hello world')",
    )
    create_file(package_path / "app_packages/README", "deps go here")
    return package_path


def test_packaging_format(package_command):
    """The standalone format only supports zip packaging by default."""
    assert package_command.packaging_formats == ["zip"]
    assert package_command.default_packaging_format == "zip"


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Standalone Linux packaging is only exercised on POSIX hosts.",
)
def test_package_app_basic(
    package_command, first_app_config, populated_bundle, tmp_path
):
    """The standalone bundle directory is zipped with a versioned root."""
    package_command.package_app(first_app_config)

    zip_path = tmp_path / "base_path/dist/first-app-0.0.1-x86_64.zip"
    assert zip_path.exists()

    with ZipFile(zip_path) as archive:
        names = sorted(archive.namelist())

    # All bundle entries are nested under the versioned root.
    assert all(name.startswith("first-app-0.0.1/") for name in names)
    # The bootstrap binary, embedded interpreter, and app code all made it in.
    assert "first-app-0.0.1/bin/first-app" in names
    assert "first-app-0.0.1/python/bin/python3.13" in names
    assert "first-app-0.0.1/app/first_app/__main__.py" in names
    assert "first-app-0.0.1/app_packages/README" in names


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Symlink preservation is only meaningful on POSIX hosts.",
)
def test_package_app_preserves_executable_bit(
    package_command,
    first_app_config,
    populated_bundle,
    tmp_path,
):
    """Executable permissions on the bootstrap binary survive the round trip."""
    binary = populated_bundle / "bin/first-app"
    binary.chmod(0o755)

    package_command.package_app(first_app_config)

    zip_path = tmp_path / "base_path/dist/first-app-0.0.1-x86_64.zip"
    with ZipFile(zip_path) as archive:
        info = archive.getinfo("first-app-0.0.1/bin/first-app")

    file_mode = (info.external_attr >> 16) & 0xFFFF
    # The owner-execute bit (0o100) must be preserved.
    assert file_mode & 0o100


@pytest.mark.skipif(
    sys.platform == "win32",
    reason="Symlink preservation is only meaningful on POSIX hosts.",
)
def test_package_app_preserves_symlinks(
    package_command,
    first_app_config,
    populated_bundle,
    tmp_path,
):
    """PBS-style symlinks (e.g. python3 -> python3.X) are stored as symlinks."""
    link_path = populated_bundle / "python/bin/python3"
    os.symlink("python3.13", link_path)

    package_command.package_app(first_app_config)

    zip_path = tmp_path / "base_path/dist/first-app-0.0.1-x86_64.zip"
    with ZipFile(zip_path) as archive:
        info = archive.getinfo("first-app-0.0.1/python/bin/python3")
        assert stat.S_ISLNK((info.external_attr >> 16) & 0xFFFF)
        assert archive.read(info).decode("utf-8") == "python3.13"
