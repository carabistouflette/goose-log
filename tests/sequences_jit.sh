#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
test "$#" -eq 1
sequence_root="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
exec "${GOOSE:-$sequence_root/.toolchain/goose/build/goose}" run "$sequence_root/tests/sequences.goose" -- "$1"
