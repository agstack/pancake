#!/usr/bin/env bash
# Fail if the license posture regresses.
#
# Two invariants, both mechanical:
#   1. LICENSE is the canonical EUPL-1.2 English text, byte for byte.
#      (Its predecessor here was a silently truncated license file that GitHub
#      reported as NOASSERTION -- a hash comparison cannot fail that quietly.)
#   2. Every git-tracked Python file carries the SPDX EUPL-1.2 header.
set -euo pipefail

# sha256 of https://joinup.ec.europa.eu/sites/default/files/custom-page/attachment/2020-03/EUPL-1.2%20EN.txt
# computed 2026-08-26 (287 lines).
want="6fc9e709ccbfe0d77fbffa2427a983282be2eb88e47b1cdb49f21a83b4d1e665"
got=$(shasum -a 256 LICENSE | cut -d' ' -f1)
if [ "$got" != "$want" ]; then
  echo "FAIL: LICENSE is not the canonical EUPL-1.2 text (sha256 $got)"
  exit 1
fi

fail=0
while IFS= read -r f; do
  if ! head -5 "$f" | grep -q "SPDX-License-Identifier: EUPL-1.2"; then
    echo "FAIL: missing SPDX EUPL-1.2 header: $f"
    fail=1
  fi
done < <(git ls-files '*.py')

if [ "$fail" -eq 0 ]; then
  echo "license posture OK: canonical EUPL-1.2 + headers on all tracked .py files"
fi
exit "$fail"
