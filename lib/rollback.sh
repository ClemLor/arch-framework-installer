#!/usr/bin/env bash

# Domain rollbacks live next to the operation they can safely reverse. This
# module documents the boundary: irreversible storage writes are never restored.
rollback_is_safe() {
    case "$1" in
        mount|luks_mapping) return 0 ;;
        partition|luks_format|filesystem) return 1 ;;
        *) return 1 ;;
    esac
}
