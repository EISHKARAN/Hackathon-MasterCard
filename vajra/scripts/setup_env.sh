#!/usr/bin/env bash
# VAJRA — environment bootstrap.
#
# WHY THIS EXISTS. requirements.txt is pinned to lower bounds that ship cp313 wheels, which
# is true on macOS arm64 and on Linux distros with glibc >= 2.28. On older hosts (notably
# Amazon Linux 2, glibc 2.26) the current numpy / lightgbm / duckdb wheels are tagged
# manylinux_2_28_x86_64, pip finds no compatible wheel, falls back to an sdist build, and
# dies on the system compiler ("NumPy requires GCC >= 10.3").
#
# So: if the host can use the manylinux_2_28 wheels, do the plain venv + pip path. If it
# cannot, build the same environment from conda-forge, whose linux-64 builds target
# glibc 2.17 and therefore install as binaries here. Either way the result is a usable
# interpreter at ./.venv/bin/python, so $(PY) in the Makefile is unchanged.
#
# Override the decision with VAJRA_ENV_BACKEND=venv|conda.

set -euo pipefail

cd "$(dirname "$0")/.."

VENV_DIR="${VENV_DIR:-.venv}"
PYTHON="${PYTHON:-python3}"
BACKEND="${VAJRA_ENV_BACKEND:-auto}"

# Compiled dependencies whose wheels are the ones that go missing on old glibc. Bounds are
# kept identical to requirements.txt; conda-forge is only a different delivery channel.
CONDA_PKGS=(
  "python=3.13"
  "numpy>=2.0,<3"
  "scipy>=1.14"
  "pyarrow>=17.0"
  "polars>=1.9,<2"
  "duckdb>=1.1"
  "lightgbm>=4.5"
  "scikit-learn>=1.5"
  "matplotlib>=3.9"
  "pip"
)

glibc_supports_2_28() {
  # `python -m pip debug` lists the platform tags pip will accept. If manylinux_2_28 is
  # absent, the modern numpy / lightgbm / duckdb wheels are unreachable on this host.
  "$1" -m pip debug --verbose 2>/dev/null | grep -q 'manylinux_2_28_x86_64' \
    || [ "$(uname -m)" = "arm64" ] || [ "$(uname -s)" = "Darwin" ]
}

conda_bin() {
  if command -v mamba >/dev/null 2>&1; then echo mamba; return 0; fi
  if command -v conda >/dev/null 2>&1; then echo conda; return 0; fi
  for root in "$HOME/miniforge3" "$HOME/miniconda3" "$HOME/anaconda3"; do
    [ -x "$root/bin/conda" ] && { echo "$root/bin/conda"; return 0; }
  done
  return 1
}

setup_venv() {
  echo "==> venv backend: $PYTHON -m venv $VENV_DIR"
  rm -rf "$VENV_DIR"
  "$PYTHON" -m venv "$VENV_DIR"
  "$VENV_DIR/bin/python" -m pip install --quiet --upgrade pip
  "$VENV_DIR/bin/python" -m pip install --quiet -r requirements.txt
}

setup_conda() {
  local conda="$1"
  echo "==> conda-forge backend: old glibc detected, installing compiled deps as binaries"
  echo "    ($(ldd --version 2>/dev/null | head -1))"
  rm -rf "$VENV_DIR"
  # Absolute --prefix: conda treats a bare relative path like ".venv" as an *env name* and
  # would silently create ~/miniforge3/envs/.venv instead.
  "$conda" create --yes --quiet --prefix "$PWD/$VENV_DIR" \
    --channel conda-forge --override-channels "${CONDA_PKGS[@]}"
  # The remainder of requirements.txt is pure Python (or has old-glibc wheels), so pip
  # handles it. numpy et al. are already satisfied, so pip leaves the conda builds alone.
  "$VENV_DIR/bin/python" -m pip install --quiet --upgrade pip
  "$VENV_DIR/bin/python" -m pip install --quiet -r requirements.txt
}

case "$BACKEND" in
  venv)  setup_venv ;;
  conda) setup_conda "$(conda_bin)" ;;
  auto)
    if glibc_supports_2_28 "$PYTHON"; then
      setup_venv
    elif conda=$(conda_bin); then
      setup_conda "$conda"
    else
      cat >&2 <<'EOF'
ERROR: this host's glibc is too old for the current numpy / lightgbm / duckdb wheels
       (they are tagged manylinux_2_28_x86_64) and no conda/mamba was found to install
       the conda-forge builds instead.

Pick one:
  1. Install Miniforge, then re-run `make venv`:
       curl -L -o /tmp/miniforge.sh \
         https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
       bash /tmp/miniforge.sh -b -p "$HOME/miniforge3"
  2. Run inside the provided container, which has a new enough base image:
       docker compose up
  3. Force the pip path with older, glibc-2.17-compatible pins (numpy<2.3, lightgbm<4):
       VAJRA_ENV_BACKEND=venv make venv
     Note lightgbm 3.x is the last linux-64 wheel for this glibc; the training code uses
     only the lgb.train / lgb.Dataset / lgb.Booster API, which is present in 3.3.
EOF
      exit 1
    fi
    ;;
  *) echo "ERROR: unknown VAJRA_ENV_BACKEND='$BACKEND' (want venv|conda|auto)" >&2; exit 2 ;;
esac

echo "==> environment ready:"
"$VENV_DIR/bin/python" - <<'PY'
import importlib.metadata as md, sys
print("    python", sys.version.split()[0], "@", sys.executable)
for name in ("numpy","scipy","pyarrow","polars","duckdb","lightgbm",
             "scikit-learn","matplotlib","fastapi","uvicorn","pydantic","pytest"):
    try:
        print(f"    {name:<14} {md.version(name)}")
    except md.PackageNotFoundError:
        print(f"    {name:<14} MISSING")
PY
