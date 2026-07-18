#!/usr/bin/env bash

# Compatibility shim for the historical misspelling. New code uses progress.sh.
# shellcheck source=lib/progress.sh
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/progress.sh"
