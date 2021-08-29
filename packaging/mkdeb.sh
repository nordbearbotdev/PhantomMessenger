#!/bin/bash -e
# Build a debian package.
VERSION="$(git describe)"
DEB_FILE="phantom-${VERSION}.deb"
PHANTOM_DIR="$( readlink -f "$( dirname "${PWD}/${BASH_SOURCE}" )/.." )"

source "${PHANTOM_DIR}"/packaging/changelog.sh

tmpdir="$(mktemp -d)"
for d in "DEBIAN" "usr" "usr/bin" "usr/share" "usr/share/doc"\
	"usr/share/doc/phantom" "usr/share/doc/phantom/html" "usr/share/applications"\
	"usr/share/pixmaps" "usr/share/pixmaps/phanom" "usr/share/phantom" \
	"usr/share/phantom/SocksiPy" "usr/share/phantom/translations"\
	"usr/share/phantom/Tor"; do
	mkdir "${tmpdir}/${d}"
done

cp "${PHANTOM_DIR}"/packaging/debian/* "${tmpdir}/DEBIAN"
	mv "${tmpdir}/DEBIAN/phantom.desktop" "${tmpdir}/usr/share/applications"
cp "${PHANTOM_DIR}"/translations/*.{py,txt}\
	"${tmpdir}/usr/share/phantom/translations"
cp "${PHANTOM_DIR}"/icons/* "${tmpdir}/usr/share/pixmaps/phantom"
cp "${PHANTOM_DIR}"/SocksiPy/{__init__.py,socks.py,BUGS,LICENSE,README}\
	"${tmpdir}/usr/share/phantom/SocksiPy"
cp "${PHANTOM_DIR}"/Tor/{torrc.txt,tor.sh} "${tmpdir}/usr/share/phantom/Tor"
cp "${PHANTOM_DIR}"/*.py "${tmpdir}/usr/share/phantom/"
changelog > "${tmpdir}/usr/share/doc/phantom/changelog.txt"

sed -i -e "s/PHANTOM_VERSION/${VERSION}/" "${tmpdir}/DEBIAN/control"

fakeroot dpkg -b "$tmpdir" "$DEB_FILE"
rm -rf "$tmpdir"
