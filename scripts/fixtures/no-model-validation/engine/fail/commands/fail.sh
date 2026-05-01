#!/usr/bin/env bash

set -euo pipefail

printf 'fail fixture command intentionally exits non-zero\n' >&2
exit 7
