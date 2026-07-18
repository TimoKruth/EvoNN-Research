#!/usr/bin/env bash
set -euo pipefail
source "$(dirname -- "${BASH_SOURCE[0]}")/_common.sh"
run_python_package_checks evonn-primordia EvoNN-Primordia evonn_primordia primordia
