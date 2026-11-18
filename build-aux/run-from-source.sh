#!/bin/sh
# Build Penfold and run it from the source code, without installing anything in the system.
# Everything goes into the _build folder of the project. Arguments are passed on to Penfold.
set -eu

cd "$(dirname "$0")/.."
build_dir=_build
install_dir="$PWD/$build_dir/install"

if [ ! -d "$build_dir" ]; then
    meson setup "$build_dir" --prefix="$install_dir"
fi
meson install -C "$build_dir" --quiet

export GSETTINGS_SCHEMA_DIR="$install_dir/share/glib-2.0/schemas"
export XDG_DATA_DIRS="$install_dir/share:${XDG_DATA_DIRS:-/usr/local/share:/usr/share}"
exec "$install_dir/bin/penfold" "$@"
