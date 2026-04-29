import subprocess
from unittest import mock

import pytest

from briefcase.console import LogLevel
from briefcase.exceptions import UnsupportedHostError
from briefcase.integrations.subprocess import Subprocess
from briefcase.platforms.linux.standalone import LinuxStandaloneRunCommand


@pytest.fixture
def run_command(dummy_console, tmp_path):
    command = LinuxStandaloneRunCommand(
        console=dummy_console,
        base_path=tmp_path / "base_path",
        data_path=tmp_path / "briefcase",
    )
    command.tools.home_path = tmp_path / "home"
    command.tools.host_arch = "x86_64"
    command.tools.subprocess = mock.MagicMock(spec_set=Subprocess)
    command._stream_app_logs = mock.MagicMock()
    return command


@pytest.mark.parametrize("host_os", ["Darwin", "Windows", "WeirdOS"])
def test_unsupported_host_os(run_command, host_os):
    """Error raised for an unsupported OS."""
    run_command.tools.host_os = host_os
    run_command.apps = {"app": None}

    with pytest.raises(
        UnsupportedHostError,
        match=r"Linux standalone projects can only be executed on Linux\.",
    ):
        run_command()


def test_run_gui_app(run_command, first_app_config, tmp_path):
    """A linux standalone GUI App can be started."""
    log_popen = mock.MagicMock()
    run_command.tools.subprocess.Popen.return_value = log_popen

    run_command.run_app(first_app_config, passthrough=[])

    run_command.tools.subprocess.Popen.assert_called_with(
        [
            tmp_path
            / "base_path/build/first-app/linux/standalone/first-app-0.0.1/bin/first-app"
        ],
        cwd=tmp_path / "home",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )

    run_command._stream_app_logs.assert_called_once_with(
        first_app_config,
        popen=log_popen,
        clean_output=False,
    )


def test_run_gui_app_with_passthrough(run_command, first_app_config, tmp_path):
    """A linux standalone GUI App can be started in debug mode with args."""
    run_command.console.verbosity = LogLevel.DEBUG

    log_popen = mock.MagicMock()
    run_command.tools.subprocess.Popen.return_value = log_popen

    run_command.run_app(
        first_app_config,
        passthrough=["foo", "--bar"],
    )

    run_command.tools.subprocess.Popen.assert_called_with(
        [
            tmp_path
            / "base_path/build/first-app/linux/standalone/first-app-0.0.1/bin/first-app",
            "foo",
            "--bar",
        ],
        cwd=tmp_path / "home",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        env={"BRIEFCASE_DEBUG": "1"},
    )

    run_command._stream_app_logs.assert_called_once_with(
        first_app_config,
        popen=log_popen,
        clean_output=False,
    )


def test_run_gui_app_failed(run_command, first_app_config, tmp_path):
    """If there's a problem starting the GUI app, an exception is raised."""
    run_command.tools.subprocess.Popen.side_effect = OSError("Some error")

    with pytest.raises(OSError, match="Some error"):
        run_command.run_app(first_app_config, passthrough=[])

    run_command.tools.subprocess.Popen.assert_called_with(
        [
            tmp_path
            / "base_path/build/first-app/linux/standalone/first-app-0.0.1/bin/first-app"
        ],
        cwd=tmp_path / "home",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
    )

    run_command._stream_app_logs.assert_not_called()


def test_run_console_app(run_command, first_app_config, tmp_path):
    """A linux standalone console App can be started."""
    first_app_config.console_app = True

    run_command.run_app(first_app_config, passthrough=[])

    run_command.tools.subprocess.run.assert_called_with(
        [
            tmp_path
            / "base_path/build/first-app/linux/standalone/first-app-0.0.1/bin/first-app"
        ],
        cwd=tmp_path / "home",
        bufsize=1,
        stream_output=False,
    )

    run_command._stream_app_logs.assert_not_called()


def test_run_console_app_with_passthrough(run_command, first_app_config, tmp_path):
    """A linux standalone console App can be started in debug mode with args."""
    run_command.console.verbosity = LogLevel.DEBUG

    first_app_config.console_app = True

    run_command.run_app(
        first_app_config,
        passthrough=["foo", "--bar"],
    )

    run_command.tools.subprocess.run.assert_called_with(
        [
            tmp_path
            / "base_path/build/first-app/linux/standalone/first-app-0.0.1/bin/first-app",
            "foo",
            "--bar",
        ],
        cwd=tmp_path / "home",
        bufsize=1,
        stream_output=False,
        env={"BRIEFCASE_DEBUG": "1"},
    )


@pytest.mark.parametrize("is_console_app", [True, False])
def test_run_app_test_mode(run_command, first_app_config, is_console_app, tmp_path):
    """A linux standalone app can be started in test mode (always streamed)."""
    first_app_config.console_app = is_console_app
    first_app_config.test_mode = True

    log_popen = mock.MagicMock()
    run_command.tools.subprocess.Popen.return_value = log_popen

    run_command.run_app(first_app_config, passthrough=[])

    run_command.tools.subprocess.Popen.assert_called_with(
        [
            tmp_path
            / "base_path/build/first-app/linux/standalone/first-app-0.0.1/bin/first-app"
        ],
        cwd=tmp_path / "home",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        env={"BRIEFCASE_MAIN_MODULE": "tests.first_app"},
    )

    run_command._stream_app_logs.assert_called_once_with(
        first_app_config,
        popen=log_popen,
        clean_output=False,
    )
