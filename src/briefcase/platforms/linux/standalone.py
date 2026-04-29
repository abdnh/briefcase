from __future__ import annotations

import os
import stat
import subprocess
from collections.abc import Collection
from pathlib import PurePath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

from briefcase.commands import (
    BuildCommand,
    CreateCommand,
    DevCommand,
    PackageCommand,
    PublishCommand,
    RunCommand,
    UpdateCommand,
)
from briefcase.config import DraftAppConfig, FinalizedAppConfig
from briefcase.exceptions import (
    BriefcaseCommandError,
    BriefcaseConfigError,
    UnsupportedHostError,
)
from briefcase.integrations.docker import Docker, DockerAppContext
from briefcase.integrations.subprocess import NativeAppContext
from briefcase.platforms.linux import (
    DockerOpenCommand,
    LinuxMixin,
    LocalRequirementsMixin,
)


class LinuxStandalonePassiveMixin(LinuxMixin):
    # The Passive mixin honors the docker options, but doesn't try to verify
    # docker exists. It is used by commands that are "passive" from the
    # perspective of the build system, like open and run.
    output_format = "standalone"
    supported_host_os: Collection[str] = {"Darwin", "Linux"}
    supported_host_os_reason = (
        "Linux standalone projects can only be built on Linux, "
        "or on macOS using Docker."
    )
    platform_target_version: str | None = "0.3.X"

    def project_path(self, app):
        return self.bundle_path(app)

    def bundle_package_path(self, app):
        return self.bundle_path(app) / f"{app.app_name}-{app.version}"

    def binary_path(self, app):
        return self.package_path(app) / "bin" / app.app_name

    def distribution_filename(self, app):
        return f"{app.app_name}-{app.version}-{self.tools.host_arch}.zip"

    def distribution_path(self, app):
        return self.dist_path / self.distribution_filename(app)

    def add_options(self, parser):
        super().add_options(parser)
        parser.add_argument(
            "--no-docker",
            dest="use_docker",
            action="store_false",
            help="Don't use Docker for building the standalone bundle",
            required=False,
        )
        parser.add_argument(
            "--Xdocker-build",
            action="append",
            dest="extra_docker_build_args",
            help="Additional arguments to use when building the Docker image",
            required=False,
        )

    def parse_options(self, extra):
        """Extract the use_docker option."""
        options, overrides = super().parse_options(extra)
        self.use_docker = options.pop("use_docker")
        self.extra_docker_build_args = options.pop("extra_docker_build_args")
        return options, overrides

    def clone_options(self, command):
        """Clone the use_docker option."""
        super().clone_options(command)
        self.use_docker = command.use_docker
        self.extra_docker_build_args = command.extra_docker_build_args


class LinuxStandaloneMostlyPassiveMixin(LinuxStandalonePassiveMixin):
    # The Mostly Passive mixin verifies that Docker exists and can be run, but
    # doesn't require that we're actually in a Linux environment.
    def docker_image_tag(self, app):
        """The Docker image tag for an app."""
        try:
            return (
                f"briefcase/{app.bundle_identifier.lower()}:{app.manylinux}-standalone"
            )
        except AttributeError:
            return f"briefcase/{app.bundle_identifier.lower()}:standalone"

    def verify_tools(self):
        """If we're using docker, verify that it is available."""
        super().verify_tools()
        if self.use_docker:
            Docker.verify(tools=self.tools)

    def verify_app_tools(self, app: FinalizedAppConfig):
        """Verify App environment is prepared and available.

        When Docker is used, create or update a Docker image for the App.
        Without Docker, the host machine will be used as the App environment.

        :param app: The application being built
        """
        if self.use_docker:
            DockerAppContext.verify(
                tools=self.tools,
                app=app,
                image_tag=self.docker_image_tag(app),
                dockerfile_path=self.bundle_path(app) / "Dockerfile",
                app_base_path=self.base_path,
                host_bundle_path=self.bundle_path(app),
                host_data_path=self.data_path,
                python_version=self.python_version_tag,
                extra_build_args=self.extra_docker_build_args,
            )
        else:
            NativeAppContext.verify(tools=self.tools, app=app)

        # Establish Docker as app context before letting super set subprocess
        super().verify_app_tools(app)


class LinuxStandaloneMixin(LinuxStandaloneMostlyPassiveMixin):
    def verify_host(self):
        """If we're *not* using Docker, verify that we're actually on Linux."""
        super().verify_host()
        if not self.use_docker and self.tools.host_os != "Linux":
            raise UnsupportedHostError(self.supported_host_os_reason)


class LinuxStandaloneCreateCommand(
    LinuxStandaloneMixin,
    LocalRequirementsMixin,
    CreateCommand,
):
    description = "Create and populate a standalone Linux project."

    def finalize_app_config(self, app: DraftAppConfig, **kwargs) -> FinalizedAppConfig:
        """If we're *not* using Docker, warn the user about portability."""
        if not self.use_docker:
            self.console.warning("""\
*************************************************************************
** WARNING: Building a Local standalone bundle!                        **
*************************************************************************

    You are building a standalone bundle outside Docker. The resulting
    artefact will work, but will not be as portable as a Docker-based
    build. Any `manylinux` setting will be ignored.

*************************************************************************
""")
        return super().finalize_app_config(app, **kwargs)

    def output_format_template_context(self, app: FinalizedAppConfig):
        context = super().output_format_template_context(app)

        try:
            manylinux_arch = {
                "x86_64": "x86_64",
                "i386": "i686",
                "i686": "i686",
                "aarch64": "aarch64",
                "armv7l": "armhf",
            }[self.tools.host_arch]
        except KeyError:
            manylinux_arch = self.tools.host_arch
            self.console.warning(
                f"There is no manylinux base image for {manylinux_arch}"
            )

        # Add the manylinux tag to the template context.
        try:
            tag = getattr(app, "manylinux_image_tag", "latest")
            context["manylinux_image"] = f"{app.manylinux}_{manylinux_arch}:{tag}"
            if app.manylinux in {"manylinux1", "manylinux2010", "manylinux2014"}:
                context["vendor_base"] = "centos"
            elif app.manylinux == "manylinux_2_24":
                context["vendor_base"] = "debian"
            elif app.manylinux.startswith("manylinux_2_"):
                context["vendor_base"] = "almalinux"
            else:
                raise BriefcaseConfigError(f"Unknown manylinux tag {app.manylinux!r}")
        except AttributeError:
            pass

        # Use the non-root user if Docker is not mapping usernames
        try:
            context["use_non_root_user"] = not self.tools.docker.is_user_mapped
        except AttributeError:
            pass  # ignore if not using Docker

        return context

    def _cleanup_app_support_package(self, support_path):
        # The standalone bundle support path is co-mingled with app content.
        # This means updating the support package is imperfect.
        # Warn the user that there could be problems.
        self.console.warning("""
*************************************************************************
** WARNING: Support package update may be imperfect                    **
*************************************************************************

    Support packages in Linux standalone bundles are overlaid with app
    content, so it isn't possible to remove all old support files before
    installing new ones.

    Briefcase will unpack the new support package without cleaning up
    existing support package content. This *should* work; however, to
    ensure reproducible release artefacts, it is advisable to perform a
    clean app build before release.

*************************************************************************
""")


class LinuxStandaloneUpdateCommand(LinuxStandaloneCreateCommand, UpdateCommand):
    description = "Update an existing standalone Linux project."


class LinuxStandaloneOpenCommand(LinuxStandaloneMostlyPassiveMixin, DockerOpenCommand):
    description = (
        "Open a shell in a Docker container for an existing standalone Linux project."
    )


class LinuxStandaloneBuildCommand(LinuxStandaloneMixin, BuildCommand):
    description = "Build a standalone Linux project."

    def build_app(
        self,
        app: FinalizedAppConfig,
        **kwargs,
    ):  # pragma: no-cover-if-is-windows
        """Build an application.

        :param app: The application to build
        """
        self.console.info("Building application...", prefix=app.app_name)

        with self.console.wait_bar("Building bootstrap binary..."):
            try:
                self.tools[app].app_context.run(
                    [
                        "make",
                        "-C",
                        "bootstrap",
                        "install",
                    ],
                    check=True,
                    cwd=self.bundle_path(app),
                )
            except subprocess.CalledProcessError as e:
                raise BriefcaseCommandError(
                    f"Error building bootstrap binary for {app.app_name}."
                ) from e

        with self.console.wait_bar("Stripping binary..."):
            self.tools.subprocess.check_output(["strip", self.binary_path(app)])


class LinuxStandaloneRunCommand(LinuxStandalonePassiveMixin, RunCommand):
    description = "Run a standalone Linux project."
    supported_host_os: Collection[str] = {"Linux"}
    supported_host_os_reason = (
        "Linux standalone projects can only be executed on Linux."
    )

    def run_app(
        self,
        app: FinalizedAppConfig,
        passthrough: list[str],
        **kwargs,
    ):
        """Start the application.

        :param app: The config object for the app
        :param passthrough: The list of arguments to pass to the app
        """
        # Set up the log stream
        kwargs = self._prepare_app_kwargs(app=app)

        # Console apps must operate in non-streaming mode so that console input can
        # be handled correctly. However, if we're in test mode, we *must* stream so
        # that we can see the test exit sentinel
        if app.console_app and not app.test_mode:
            self.console.info("=" * 75)
            self.tools.subprocess.run(
                [self.binary_path(app), *passthrough],
                cwd=self.tools.home_path,
                bufsize=1,
                stream_output=False,
                **kwargs,
            )
        else:
            # Start the app in a way that lets us stream the logs
            app_popen = self.tools.subprocess.Popen(
                [self.binary_path(app), *passthrough],
                cwd=self.tools.home_path,
                **kwargs,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                bufsize=1,
            )

            # Start streaming logs for the app.
            self._stream_app_logs(
                app,
                popen=app_popen,
                clean_output=False,
            )


class LinuxStandaloneDevCommand(LinuxStandaloneMixin, DevCommand):
    description = "Run a standalone Linux app in development mode."


class LinuxStandalonePackageCommand(LinuxStandaloneMixin, PackageCommand):
    description = "Package a standalone Linux project."

    @property
    def packaging_formats(self):
        return ["zip"]

    @property
    def default_packaging_format(self):
        return "zip"

    def package_app(
        self,
        app: FinalizedAppConfig,
        **kwargs,
    ):  # pragma: no-cover-if-is-windows
        """Package the standalone Linux app as a portable zip archive.

        The contents of ``package_path`` are written into the zip rooted at
        ``<formal_name>-<version>/``. Unix file permissions and symlinks are
        preserved so the extracted tree is directly executable on Linux.

        :param app: The application to package
        """
        self.console.info("Building zip file...", prefix=app.app_name)
        with self.console.wait_bar("Packing..."):
            source = self.package_path(app)
            zip_root = f"{app.app_name}-{app.version}"

            with ZipFile(self.distribution_path(app), "w", ZIP_DEFLATED) as archive:
                for file_path in sorted(source.glob("**/*")):
                    relative_path = PurePath(file_path).relative_to(source)
                    archive_name = f"{zip_root}/{relative_path.as_posix()}"
                    file_stat = self.tools.os.lstat(file_path)
                    if stat.S_ISLNK(file_stat.st_mode):
                        # Preserve symlinks as symlinks inside the archive,
                        # rather than dereferencing them. PBS includes symlinks
                        # such as `python3 -> python3.X` that are required for
                        # the embedded interpreter to function correctly.
                        info = ZipInfo(archive_name)
                        info.create_system = 3  # Unix
                        info.external_attr = (file_stat.st_mode & 0xFFFF) << 16
                        target = self.tools.os.readlink(file_path)
                        archive.writestr(info, os.fsencode(target))
                    elif file_path.is_dir():
                        info = ZipInfo(archive_name + "/")
                        info.create_system = 3  # Unix
                        info.external_attr = ((file_stat.st_mode & 0xFFFF) << 16) | 0x10
                        archive.writestr(info, b"")
                    else:
                        with file_path.open("rb") as f:
                            data = f.read()
                        info = ZipInfo(archive_name)
                        info.create_system = 3  # Unix
                        info.external_attr = (file_stat.st_mode & 0xFFFF) << 16
                        info.compress_type = ZIP_DEFLATED
                        archive.writestr(info, data)


class LinuxStandalonePublishCommand(LinuxStandaloneMixin, PublishCommand):
    description = "Publish a standalone Linux project."


# Declare the briefcase command bindings
create = LinuxStandaloneCreateCommand
update = LinuxStandaloneUpdateCommand
open = LinuxStandaloneOpenCommand
build = LinuxStandaloneBuildCommand
run = LinuxStandaloneRunCommand
package = LinuxStandalonePackageCommand
publish = LinuxStandalonePublishCommand
dev = LinuxStandaloneDevCommand
