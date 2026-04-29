from unittest.mock import MagicMock

import pytest

from briefcase.exceptions import BriefcaseConfigError, UnsupportedHostError
from briefcase.platforms.linux.standalone import LinuxStandaloneCreateCommand


@pytest.fixture
def create_command(dummy_console, first_app_config, tmp_path):
    command = LinuxStandaloneCreateCommand(
        console=dummy_console,
        base_path=tmp_path / "base_path",
        data_path=tmp_path / "briefcase",
    )
    command.tools.host_arch = "x86_64"
    return command


def test_default_options(create_command):
    """The default options are as expected."""
    options, overrides = create_command.parse_options([])

    assert options == {}
    assert overrides == {}

    assert create_command.use_docker


def test_options(create_command):
    """The extra options can be parsed."""
    options, overrides = create_command.parse_options(["--no-docker"])

    assert options == {}
    assert overrides == {}

    assert not create_command.use_docker


@pytest.mark.parametrize("host_os", ["Windows", "WeirdOS"])
def test_unsupported_host_os_with_docker(create_command, host_os):
    """Error raised for an unsupported OS when using Docker."""
    create_command.use_docker = True
    create_command.tools.host_os = host_os

    with pytest.raises(
        UnsupportedHostError,
        match=(
            r"Linux standalone projects can only be built on Linux, "
            r"or on macOS using Docker\."
        ),
    ):
        create_command()


@pytest.mark.parametrize("host_os", ["Darwin", "Windows", "WeirdOS"])
def test_unsupported_host_os_without_docker(create_command, host_os):
    """Error raised for an unsupported OS when not using Docker."""
    create_command.use_docker = False
    create_command.tools.host_os = host_os

    with pytest.raises(
        UnsupportedHostError,
        match=(
            r"Linux standalone projects can only be built on Linux, "
            r"or on macOS using Docker\."
        ),
    ):
        create_command()


def test_finalize_docker(create_command, first_app_config, capsys):
    """No warning is generated when building inside Docker."""
    create_command.use_docker = True

    create_command.finalize_app_config(first_app_config)

    stdout = capsys.readouterr().out
    assert "WARNING: Building a Local standalone bundle!" not in stdout


def test_finalize_nodocker(create_command, first_app_config, capsys):
    """A warning is generated when building outside Docker."""
    create_command.use_docker = False

    create_command.finalize_app_config(first_app_config)

    stdout = capsys.readouterr().out
    assert "WARNING: Building a Local standalone bundle!" in stdout


@pytest.mark.parametrize(
    ("manylinux", "tag", "host_os", "host_arch", "is_user_mapped", "context"),
    [
        # No manylinux configured.
        (None, None, "Linux", "x86_64", False, {"use_non_root_user": True}),
        # Linux on x86_64 architecture
        (
            "manylinux1",
            "2023-03-05-271004f",
            "Linux",
            "x86_64",
            True,
            {
                "manylinux_image": "manylinux1_x86_64:2023-03-05-271004f",
                "vendor_base": "centos",
                "use_non_root_user": False,
            },
        ),
        (
            "manylinux2010",
            "latest",
            "Linux",
            "x86_64",
            False,
            {
                "manylinux_image": "manylinux2010_x86_64:latest",
                "vendor_base": "centos",
                "use_non_root_user": True,
            },
        ),
        (
            "manylinux2014",
            None,
            "Linux",
            "x86_64",
            True,
            {
                "manylinux_image": "manylinux2014_x86_64:latest",
                "vendor_base": "centos",
                "use_non_root_user": False,
            },
        ),
        (
            "manylinux_2_24",
            None,
            "Linux",
            "x86_64",
            True,
            {
                "manylinux_image": "manylinux_2_24_x86_64:latest",
                "vendor_base": "debian",
                "use_non_root_user": False,
            },
        ),
        (
            "manylinux_2_28",
            None,
            "Linux",
            "x86_64",
            False,
            {
                "manylinux_image": "manylinux_2_28_x86_64:latest",
                "vendor_base": "almalinux",
                "use_non_root_user": True,
            },
        ),
        # Linux on i686 hardware
        (
            "manylinux_2_28",
            None,
            "Linux",
            "i686",
            False,
            {
                "manylinux_image": "manylinux_2_28_i686:latest",
                "vendor_base": "almalinux",
                "use_non_root_user": True,
            },
        ),
        # Linux on i386 hardware (mapped to i686 manylinux)
        (
            "manylinux_2_28",
            None,
            "Linux",
            "i386",
            False,
            {
                "manylinux_image": "manylinux_2_28_i686:latest",
                "vendor_base": "almalinux",
                "use_non_root_user": True,
            },
        ),
        # Linux on aarch64 hardware
        (
            "manylinux_2_28",
            None,
            "Linux",
            "aarch64",
            False,
            {
                "manylinux_image": "manylinux_2_28_aarch64:latest",
                "vendor_base": "almalinux",
                "use_non_root_user": True,
            },
        ),
        # Linux on arm hardware
        (
            "manylinux_2_28",
            None,
            "Linux",
            "armv7l",
            False,
            {
                "manylinux_image": "manylinux_2_28_armhf:latest",
                "vendor_base": "almalinux",
                "use_non_root_user": True,
            },
        ),
        # macOS on x86_64
        (
            "manylinux2014",
            None,
            "Darwin",
            "x86_64",
            True,
            {
                "manylinux_image": "manylinux2014_x86_64:latest",
                "vendor_base": "centos",
                "use_non_root_user": False,
            },
        ),
    ],
)
def test_output_format_template_context(
    create_command,
    first_app_config,
    manylinux,
    tag,
    host_os,
    host_arch,
    is_user_mapped,
    context,
):
    """The template context reflects the manylinux name, tag and architecture."""
    create_command.tools.docker = MagicMock()
    create_command.tools.docker.is_user_mapped = is_user_mapped

    if manylinux:
        first_app_config.manylinux = manylinux
    if tag:
        first_app_config.manylinux_image_tag = tag

    create_command.tools.host_os = host_os
    create_command.tools.host_arch = host_arch

    assert create_command.output_format_template_context(first_app_config) == context


def test_output_format_template_context_unknown_arch(create_command, first_app_config):
    """An unknown host architecture produces a warning, but still emits context."""
    first_app_config.manylinux = "manylinux_2_28"
    create_command.tools.host_arch = "weirdarch"

    context = create_command.output_format_template_context(first_app_config)

    # The unknown arch is passed through verbatim into the manylinux image tag.
    assert context["manylinux_image"] == "manylinux_2_28_weirdarch:latest"


def test_output_format_template_context_bad_tag(create_command, first_app_config):
    """An unknown manylinux tag raises an error."""
    first_app_config.manylinux = "unknown"
    with pytest.raises(BriefcaseConfigError, match=r"Unknown manylinux tag 'unknown'"):
        assert create_command.output_format_template_context(first_app_config)


def test_output_format_no_docker(create_command, first_app_config):
    """If not using Docker, ``use_non_root_user`` is left to the template default."""
    context = create_command.output_format_template_context(first_app_config)

    assert "use_non_root_user" not in context


def test_cleanup_app_support_package_warns(create_command, first_app_config, capsys):
    """A warning is shown when the support package is being overlaid."""
    create_command._cleanup_app_support_package(MagicMock())

    stdout = capsys.readouterr().out
    assert "WARNING: Support package update may be imperfect" in stdout


def test_verify_host_linux_passes(create_command):
    """verify_host accepts native Linux execution."""
    create_command.tools.host_os = "Linux"
    create_command.use_docker = False
    create_command.verify_host()


def test_verify_host_docker_on_macos_passes(create_command):
    """verify_host accepts macOS when Docker is in use."""
    create_command.tools.host_os = "Darwin"
    create_command.use_docker = True
    create_command.verify_host()
