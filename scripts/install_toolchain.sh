#!/usr/bin/env bash
# Editable-install the six wavetest_* packages from a sibling toolchain checkout.
#
# Usage: ./scripts/install_toolchain.sh [PATH_TO_RAI_TOOLCHAIN]
#
# Default path: ~/Documents/GitHub/RAI-TOOLCHAIN

set -euo pipefail

TOOLCHAIN="${1:-$HOME/Documents/GitHub/RAI-TOOLCHAIN}"

if [[ ! -d "$TOOLCHAIN" ]]; then
    echo "❌ Toolchain not found at: $TOOLCHAIN"
    echo "   Pass the correct path as the first argument."
    exit 1
fi

PACKAGES=(
    "wavetest_fairness"
    "wavetest_explain"
    "wavetest_dataquality"
    "wavetest_logging"
    "wavetest_monitoring"
    "wavetest_report"
)

echo "Installing toolchain packages from: $TOOLCHAIN"
for pkg in "${PACKAGES[@]}"; do
    pkg_path="$TOOLCHAIN/$pkg"
    if [[ ! -f "$pkg_path/pyproject.toml" ]]; then
        echo "  ⚠️  $pkg has no pyproject.toml — skipping"
        continue
    fi
    echo "  → $pkg"
    pip install -e "$pkg_path" --quiet
done

echo "✅ All wavetest_* packages installed editable from $TOOLCHAIN"
