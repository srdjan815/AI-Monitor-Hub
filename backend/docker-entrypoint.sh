#!/bin/sh
set -eu

artifact_directory="${SUPPLIER_ARTIFACT_ROOT:-/app/data/supplier-artifacts}"
mkdir -p "$artifact_directory"
chown -R appuser:appuser "$artifact_directory"

export HOME=/home/appuser
export USER=appuser
export LOGNAME=appuser

exec setpriv --reuid=1000 --regid=1000 --init-groups "$@"
