import subprocess
import sys
from unittest import mock

import pytest

from briefcase.exceptions import BriefcaseCommandError
from briefcase.platforms.linux.standalone import LinuxStandaloneBuildCommand


@pytest.fixture
def build_command(dummy_console, tmp_path, first_app_config):
    command = LinuxStandaloneBuildCommand(
        console=dummy_console,
        base_path=tmp_path / "base_path",
        data_path=tmp_path / "briefcase",
        apps={"first": first_app_config},
    )
    command.tools.host_os = "Linux"
    command.tools.host_arch = "x86_64"
    command.use_docker = False

    # Mock subprocess and the app context.
    command.tools.subprocess = mock.MagicMock()
    command.tools.app_tools[first_app_config].app_context = mock.MagicMock()

    return command


@pytest.mark.skipif(sys.platform == "win32", reason="Can't build Linux apps on Windows")
def test_build_app(build_command, first_app_config, tmp_path):
    """A standalone app can be built."""
    build_command.build_app(first_app_config)

    bundle_path = tmp_path / "base_path/build/first-app/linux/standalone"
    build_command.tools[first_app_config].app_context.run.assert_called_with(
        ["make", "-C", "bootstrap", "install"],
        check=True,
        cwd=bundle_path,
    )

    build_command.tools.subprocess.check_output.assert_called_once_with(
        [
            "strip",
            bundle_path / "first-app-0.0.1/bin/first-app",
        ]
    )


@pytest.mark.skipif(sys.platform == "win32", reason="Can't build Linux apps on Windows")
def test_build_bootstrap_failed(build_command, first_app_config, tmp_path):
    """If the bootstrap binary can't be compiled, an error is raised."""
    build_command.tools[
        first_app_config
    ].app_context.run.side_effect = subprocess.CalledProcessError(
        cmd=["make ..."], returncode=-1
    )

    with pytest.raises(
        BriefcaseCommandError,
        match=r"Error building bootstrap binary for first-app.",
    ):
        build_command.build_app(first_app_config)

    bundle_path = tmp_path / "base_path/build/first-app/linux/standalone"
    build_command.tools[first_app_config].app_context.run.assert_called_with(
        ["make", "-C", "bootstrap", "install"],
        check=True,
        cwd=bundle_path,
    )

    # Strip was *not* invoked because the make step failed.
    build_command.tools.subprocess.check_output.assert_not_called()
