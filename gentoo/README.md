# Gentoo overlay for pythondialog

This directory is a self-contained Portage overlay providing
`dev-python/pythondialog` (the maintained fork). It currently contains
3.6.0 (stable keywords) and 3.7.0 (`~amd64 ~x86`).

## Adding the overlay

Create `/etc/portage/repos.conf/pythondialog.conf`:

```ini
[pythondialog-overlay]
location = /path/to/pythondialog/gentoo
masters = gentoo
auto-sync = no
priority = 100
```

The high priority ensures this ebuild wins if a `dev-python/pythondialog`
package is still present in the main Gentoo tree.

Then install:

```bash
sudo emaint sync -r pythondialog-overlay   # optional; local overlay
sudo emerge -av dev-python/pythondialog
```

If you prefer to keep the overlay under `/var/db/repos`, copy or symlink
this directory as root:

```bash
sudo ln -s /path/to/pythondialog/gentoo /var/db/repos/pythondialog-overlay
```

## Building and updating the Manifest

The ebuild fetches the sdist attached to the matching GitHub release
(`v3.6.0` or `v3.7.0`). After changing the source or version, build the
sdist and refresh the Manifest from the project root:

```bash
make manifest
```

For a local (non-published) build, build the sdist as your user, then
copy it into the Portage distfiles directory:

```bash
make sdist
sudo make distfile
```

## Notes

- Runtime dependency: `dev-util/dialog` (>= 1.3 recommended).
- Documentation is built only with `USE=doc` (requires Sphinx through
  `distutils_enable_sphinx`).
- `PYTHON_COMPAT` covers CPython 3.11–3.14 and PyPy 3.
