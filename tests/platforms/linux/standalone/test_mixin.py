import sys
from unittest.mock import MagicMock

import pytest

import briefcase.platforms.linux.standalone
from briefcase.integrations.docker import Docker, DockerAppContext
from briefcase.integrations.subprocess import Subprocess
from briefcase.platforms.linux.standalone import (
    LinuxStandaloneBuildCommand,
    LinuxStandaloneCreateCommand,
)


@pytest.fixture
def create_command(dummy_console, tmp_path):
    command = LinuxStandaloneCreateCommand(
        console=dummy_console,
        base_path=tmp_path / "base_path",
        data_path=tmp_path / "briefcase",
    )
    return command


def test_binary_path(create_command, first_app_config, tmp_path):
    create_command.tools.host_arch = "x86_64"
    binary_path = create_command.binary_path(first_app_config)

    assert (
        binary_path
        == tmp_path
        / "base_path/build/first-app/linux/standalone/first-app-0.0.1/bin/first-app"
    )


def test_project_path(create_command, first_app_config, tmp_path):
    """The project path is the bundle path."""
    project_path = create_command.project_path(first_app_config)
    bundle_path = create_command.bundle_path(first_app_config)

    expected_path = tmp_path / "base_path/build/first-app/linux/standalone"
    assert expected_path == project_path == bundle_path


def test_bundle_package_path(create_command, first_app_config, tmp_path):
    """The bundle package path is the rooted directory that gets zipped."""
    package_path = create_command.bundle_package_path(first_app_config)

    assert (
        package_path
        == tmp_path / "base_path/build/first-app/linux/standalone/first-app-0.0.1"
    )


def test_distribution_path(create_command, first_app_config, tmp_path):
    create_command.tools.host_arch = "x86_64"
    distribution_path = create_command.distribution_path(first_app_config)

    assert distribution_path == tmp_path / "base_path/dist/first-app-0.0.1-x86_64.zip"


@pytest.mark.parametrize(
    ("manylinux", "tag"),
    [
        (None, "standalone"),
        ("manylinux1", "manylinux1-standalone"),
        ("manylinux_2_28", "manylinux_2_28-standalone"),
    ],
)
def test_docker_image_tag(create_command, first_app_config, manylinux, tag):
    if manylinux:
        first_app_config.manylinux = manylinux

    image_tag = create_command.docker_image_tag(first_app_config)

    assert image_tag == f"briefcase/com.example.first-app:{tag}"


def test_docker_image_tag_uppercase_name(
    create_command,
    uppercase_app_config,
):
    image_tag = create_command.docker_image_tag(uppercase_app_config)

    assert image_tag == "briefcase/com.example.first-app:standalone"


def test_verify_linux_no_docker(create_command, first_app_config):
    """If Docker is disabled on Linux, the app_context is Subprocess."""
    create_command.tools.host_os = "Linux"
    create_command.use_docker = False

    create_command.verify_tools()
    create_command.verify_app_tools(app=first_app_config)

    assert isinstance(create_command.tools[first_app_config].app_context, Subprocess)
    assert not hasattr(create_command.tools, "docker")


def test_verify_linux_docker(create_command, first_app_config, tmp_path, monkeypatch):
    """If Docker is enabled on Linux, the Docker alias is set."""
    create_command.tools.host_os = "Linux"
    create_command.use_docker = True
    create_command.extra_docker_build_args = ["--option-one", "--option-two"]

    mock__version_compat = MagicMock(spec=Docker._version_compat)
    mock__user_access = MagicMock(spec=Docker._user_access)
    mock__buildx_installed = MagicMock(spec=Docker._buildx_installed)
    mock__is_user_mapping_enabled = MagicMock(spec=Docker._is_user_mapping_enabled)
    monkeypatch.setattr(
        briefcase.platforms.linux.standalone.Docker,
        "_version_compat",
        mock__version_compat,
    )
    monkeypatch.setattr(
        briefcase.platforms.linux.standalone.Docker,
        "_user_access",
        mock__user_access,
    )
    monkeypatch.setattr(
        briefcase.platforms.linux.standalone.Docker,
        "_buildx_installed",
        mock__buildx_installed,
    )
    monkeypatch.setattr(
        briefcase.platforms.linux.standalone.Docker,
        "_is_user_mapping_enabled",
        mock__is_user_mapping_enabled,
    )
    mock_docker_app_context_verify = MagicMock(spec=DockerAppContext.verify)
    monkeypatch.setattr(
        briefcase.platforms.linux.standalone.DockerAppContext,
        "verify",
        mock_docker_app_context_verify,
    )

    create_command.verify_tools()
    create_command.verify_app_tools(app=first_app_config)

    mock__version_compat.assert_called_with(tools=create_command.tools)
    mock__user_access.assert_called_with(tools=create_command.tools)
    mock__buildx_installed.assert_called_with(tools=create_command.tools)
    mock__is_user_mapping_enabled.assert_called_with(None)
    assert isinstance(create_command.tools.docker, Docker)
    mock_docker_app_context_verify.assert_called_with(
        tools=create_command.tools,
        app=first_app_config,
        image_tag="briefcase/com.example.first-app:standalone",
        dockerfile_path=tmp_path
        / "base_path/build/first-app/linux/standalone/Dockerfile",
        app_base_path=tmp_path / "base_path",
        host_bundle_path=tmp_path / "base_path/build/first-app/linux/standalone",
        host_data_path=tmp_path / "briefcase",
        python_version=f"3.{sys.version_info.minor}",
        extra_build_args=["--option-one", "--option-two"],
    )


def test_verify_non_linux_docker(
    create_command,
    first_app_config,
    monkeypatch,
    tmp_path,
):
    """If Docker is enabled on non-Linux, the Docker alias is set."""
    create_command.tools.host_os = "Darwin"
    create_command.use_docker = True
    create_command.extra_docker_build_args = ["--option-one", "--option-two"]

    mock__version_compat = MagicMock(spec=Docker._version_compat)
    mock__user_access = MagicMock(spec=Docker._user_access)
    mock__buildx_installed = MagicMock(spec=Docker._buildx_installed)
    mock__is_user_mapping_enabled = MagicMock(spec=Docker._is_user_mapping_enabled)
    monkeypatch.setattr(
        briefcase.platforms.linux.standalone.Docker,
        "_version_compat",
        mock__version_compat,
    )
    monkeypatch.setattr(
        briefcase.platforms.linux.standalone.Docker,
        "_user_access",
        mock__user_access,
    )
    monkeypatch.setattr(
        briefcase.platforms.linux.standalone.Docker,
        "_buildx_installed",
        mock__buildx_installed,
    )
    monkeypatch.setattr(
        briefcase.platforms.linux.standalone.Docker,
        "_is_user_mapping_enabled",
        mock__is_user_mapping_enabled,
    )
    mock_docker_app_context_verify = MagicMock(spec=DockerAppContext.verify)
    monkeypatch.setattr(
        briefcase.platforms.linux.standalone.DockerAppContext,
        "verify",
        mock_docker_app_context_verify,
    )

    create_command.verify_tools()
    create_command.verify_app_tools(app=first_app_config)

    assert isinstance(create_command.tools.docker, Docker)
    mock_docker_app_context_verify.assert_called_with(
        tools=create_command.tools,
        app=first_app_config,
        image_tag="briefcase/com.example.first-app:standalone",
        dockerfile_path=tmp_path
        / "base_path/build/first-app/linux/standalone/Dockerfile",
        app_base_path=tmp_path / "base_path",
        host_bundle_path=tmp_path / "base_path/build/first-app/linux/standalone",
        host_data_path=tmp_path / "briefcase",
        python_version=f"3.{sys.version_info.minor}",
        extra_build_args=["--option-one", "--option-two"],
    )


def test_clone_options(dummy_console, tmp_path):
    """Docker options are cloned."""
    build_command = LinuxStandaloneBuildCommand(
        console=dummy_console,
        base_path=tmp_path / "base_path",
        data_path=tmp_path / "briefcase",
    )
    build_command.use_docker = True
    build_command.extra_docker_build_args = ["--option-one", "--option-two"]

    create_command = build_command.create_command

    assert create_command.is_clone
    assert create_command.use_docker
    assert create_command.extra_docker_build_args == ["--option-one", "--option-two"]
