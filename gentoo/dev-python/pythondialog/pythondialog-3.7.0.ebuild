# Copyright 2026 Gentoo Authors
# Distributed under the terms of the GNU General Public License v2

EAPI=8

DISTUTILS_USE_PEP517=setuptools
PYTHON_COMPAT=( python3_{11..14} pypy3 )

inherit distutils-r1

DESCRIPTION="Python interface to the UNIX dialog utility"
HOMEPAGE="https://github.com/grivital/pythondialog"
SRC_URI="https://github.com/grivital/pythondialog/releases/download/v${PV}/pythondialog-${PV}.tar.gz"

LICENSE="LGPL-2.1+"
SLOT="0"
KEYWORDS="amd64 x86"
IUSE=""

RDEPEND="dev-util/dialog"

distutils_enable_sphinx doc

python_test() {
	"${EPYTHON}" -m unittest discover -s tests -v \
		|| die "Tests failed with ${EPYTHON}"
}

python_install_all() {
	dodoc -r examples
	docompress -x /usr/share/doc/${PF}/examples
	distutils-r1_python_install_all
}
