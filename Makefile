PYTHON ?= python3
RUFF ?= ruff
DISTDIR ?= /var/cache/distfiles
OVERLAY ?= /var/db/repos/overlay
EBUILD_DIR := gentoo/dev-python/pythondialog

.PHONY: all test check sdist distfile docs install install-ebuild manifest clean

all: test sdist

test:
	$(PYTHON) -m unittest discover -s tests -v

check:
	$(PYTHON) -m py_compile dialog.py tests/fake_dialog.py tests/test_dialog.py
	$(RUFF) check --select F,E9 dialog.py tests

sdist:
	$(PYTHON) -c "import setuptools.build_meta as b; print(b.build_sdist('dist'))"

docs:
	$(MAKE) -C doc html

install:
	$(PYTHON) -m pip install .

# Install this ebuild into a local Portage overlay (requires root).
install-ebuild: manifest
	install -d "$(OVERLAY)/dev-python/pythondialog"
	install -m 0644 $(EBUILD_DIR)/*.ebuild "$(OVERLAY)/dev-python/pythondialog/"
	install -m 0644 $(EBUILD_DIR)/metadata.xml "$(OVERLAY)/dev-python/pythondialog/"
	install -m 0644 $(EBUILD_DIR)/Manifest "$(OVERLAY)/dev-python/pythondialog/"

# Copy the sdist to the Portage distfiles directory (usually needs root).
# Run "make sdist" first (as your user, not as root).
distfile:
	install -m 0644 dist/pythondialog-*.tar.gz "$(DISTDIR)/"

# Regenerate the ebuild Manifest using the local sdist (no root needed).
# The newest ebuild is used; ebuild(1) keeps entries for older versions that
# are present in DISTDIR.
manifest: sdist
	cd $(EBUILD_DIR) && \
		DISTDIR="$(abspath dist)" \
		ebuild --force $$(ls -1 *.ebuild | sort -V | tail -1) manifest

clean:
	rm -rf build dist doc/_build .ruff_cache __pycache__ tests/__pycache__
	rm -rf *.egg-info
