# Standalone

<table class="host-platform-support-table">
<colgroup>
<col style="width: 11%" />
<col style="width: 10%" />
<col style="width: 7%" />
<col style="width: 5%" />
<col style="width: 6%" />
<col style="width: 5%" />
<col style="width: 5%" />
<col style="width: 7%" />
<col style="width: 11%" />
<col style="width: 7%" />
<col style="width: 10%" />
</colgroup>
<thead>
<tr>
<th colspan="11"><a href="../../../../reference/platforms">Host Platform Support</a></th>
</tr>
<tr>
<th colspan="2">macOS</th>
<th colspan="5">Windows</th>
<th colspan="4">Linux</th>
</tr>
<tr>
<th>x86‑64</th>
<th>arm64</th>
<th>x86</th>
<th colspan="2">x86‑64</th>
<th colspan="2">arm64</th>
<th>x86</th>
<th>x86‑64</th>
<th>arm</th>
<th>arm64</th>
</tr>
</thead>
<tbody>
<tr>
<td>{{ not_tested }}</td>
<td>{{ not_tested }}</td>
<td></td>
<td colspan="2"></td>
<td colspan="2"></td>
<td>{{ not_tested }}</td>
<td>{{ not_tested }}</td>
<td>{{ not_tested }}</td>
<td>{{ not_tested }}</td>
</tr>
</tbody>
</table>

The `standalone` output format produces a self-contained, portable Linux application bundle, distributed as a `.zip` archive. Unlike the [system package][native-system-packages] format (which depends on the host distribution's Python interpreter and shared libraries), a standalone bundle embeds a [`python-build-standalone`](https://github.com/astral-sh/python-build-standalone) Python interpreter alongside the application's own code and dependencies. The result is a single archive that can be extracted and run on most Linux distributions of the same CPU architecture, regardless of the version of Python (or even the absence of Python) on the host.

A standalone bundle has the following layout:

```text
<app_name>-<version>/
├── bin/
│   └── <app_name>             # Native bootstrap binary launched by the user
├── lib/
│   └── python3.X/             # Embedded python-build-standalone interpreter
├── app/                        # Your application's Python code
├── app_packages/               # Installed Python dependencies
└── share/                      # Desktop integration files (optional)
```

To run the app, the end user extracts the archive and executes the bootstrap binary at `bin/<app_name>`; the bootstrap initializes the embedded interpreter and runs the application without requiring any system Python.

To ensure a build environment that is as compatible as possible across Linux distributions, Briefcase builds standalone bundles inside Docker. The Docker base image used by Briefcase can be configured to any [manylinux](https://github.com/pypa/manylinux) base using the `manylinux` application configuration option; if `manylinux` isn't specified, it falls back to `manylinux2014`. While it is *possible* to build a standalone bundle without Docker (using the `--no-docker` option), the resulting bundles will not be as portable as they could otherwise be — they will only reliably run on hosts whose `glibc` version is greater than or equal to that of the build host.

/// note | Choosing between Linux output formats

Briefcase provides four output formats for Linux:

- [System packages][native-system-packages] (`.deb`, `.rpm`, `.pkg`) integrate cleanly with the target distribution but must be built once per target distribution and Python version.
- [Flatpak][flatpak] bundles target the Flathub ecosystem and rely on a runtime to provide most dependencies.
- [AppImage][appimage] bundles a single executable file, but its library-relocation approach is fragile (see [AppImage's "Best effort support" notice][appimage]).
- The standalone format produces a portable `.zip` archive that embeds its own Python interpreter, similar to how the [Windows app folder][windows-app-folder] format works on Windows. It is the simplest option for distributing a single artefact that "just runs" across modern Linux distributions, at the cost of a larger archive size (the embedded interpreter typically adds ~25 MB).

If your distribution channel can't use system packages or Flatpaks, the standalone format is the recommended option for portable Linux distribution.

///

## Icon format

Standalone bundles use `.png` format icons. An application must provide icons in the following sizes:

- 16px
- 32px
- 64px
- 128px
- 256px
- 512px

Standalone bundles do not support splash screens or installer images.

## Packaging format

Standalone bundles are always packaged as a `.zip` archive. The archive preserves Unix file permissions and symlinks, so the extracted tree is directly executable on Linux without any post-extraction fix-up.

## Additional options

The following options can be provided at the command line.

### `--no-docker`

Use native execution, rather than using Docker to start a container.

When `--no-docker` is used, the bundle is built using the host's compiler toolchain. The resulting bundle will *only* be portable to systems with a `glibc` version greater than or equal to the build host's. Building inside Docker (the default) is strongly recommended.

-8<- "reference/platforms/linux/docker_build_options.md"

## Application configuration

The following options can be added to the `tool.briefcase.app.<appname>.linux.standalone` section of your `pyproject.toml` file.

### `manylinux`

The [manylinux](https://github.com/pypa/manylinux) tag to use as a base image when building the standalone bundle. Should be one of:

- `manylinux2014`
- `manylinux_2_24`
- `manylinux_2_28`

New projects will default to `manylinux2014`. The choice of `manylinux` tag determines the minimum `glibc` version that hosts running the bundle must have available — `manylinux2014` is broadly compatible, while `manylinux_2_28` provides more recent system libraries (including WebKit2) at the cost of restricting the runtime environments where the bundle will work.

### `manylinux_image_tag`

The specific tag of the `manylinux` image to use. Defaults to `latest`.

### `system_requires`

A list of operating system packages that must be installed for the standalone bundle build to succeed. The list is passed to the Docker context when building the container for the app build. The package names should match the package manager available in the chosen `manylinux` base image (`yum` for `manylinux2014`, `apt` for `manylinux_2_24`, and `dnf`/`microdnf` for `manylinux_2_28` and the `almalinux`-based images). For example, on a `manylinux_2_28` base:

```python
system_requires = ["gtk3-devel", "cairo-gobject-devel"]
```

If you see errors during `briefcase build` of the form:

```python
Could not find dependency: libSomething.so.1
```

but the app works under `briefcase dev`, the problem may be an incomplete `system_requires` definition. The `briefcase build` process generates a new environment that is completely isolated from your development environment, so if your app has any operating system dependencies, they *must* be listed in your `system_requires` definition.

### `dockerfile_extra_content`

Any additional Docker instructions that are required to configure the container used to build your standalone bundle. For example, any dependencies that cannot be configured with the system package manager could be installed. `dockerfile_extra_content` is a string literal that will be added verbatim to the end of the project Dockerfile.

## Platform quirks

### Use caution with `--update-support`

Care should be taken when using the `--update-support` option to the `update`, `build` or `run` commands. Support packages in Linux standalone bundles are overlaid with app content, so it isn't possible to remove all old support files before installing new ones.

Briefcase will unpack the new support package without cleaning up existing support package content. This *should* work; however, to ensure reproducible release artefacts, it is advisable to perform a clean app build before release.

### Bundle size

Because standalone bundles ship their own Python interpreter, the resulting `.zip` archive is significantly larger (typically 25–50 MB before app content) than a system package. If artefact size is a concern, prefer the [system package][native-system-packages] or [Flatpak][flatpak] formats.

### `glibc` compatibility

A standalone bundle built against a particular `manylinux` tag will only run on hosts whose `glibc` version is greater than or equal to that of the chosen tag. The default `manylinux2014` tag works on essentially all currently supported Linux distributions; newer tags trade compatibility for access to more recent system libraries.
