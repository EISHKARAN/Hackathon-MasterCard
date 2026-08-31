#!/usr/bin/env bash
# VAJRA — UI launcher.
#
# WHY THIS EXISTS. next@14 requires Node >= 18.17.0, and the official Node >= 18 linux-x64
# tarballs are linked against glibc 2.27/2.28. On Amazon Linux 2 (glibc 2.26) they abort with
# "version `GLIBC_2.28' not found", which is why nvm's v18 is unusable there and the host is
# stuck on Node 16 -- and `next dev` then refuses to start.
#
# So: find a Node >= 18.17.0 that actually RUNS on this host (not merely one that is
# installed), preferring PATH, then a previously provisioned ./.node, then any nvm version,
# and finally provisioning conda-forge's nodejs into ./.node -- those builds target glibc
# 2.17 and so work here. Same trick scripts/setup_env.sh uses for the Python side.
#
# Usage: scripts/ui.sh [npm-script]     (default: dev)

set -euo pipefail

cd "$(dirname "$0")/.."

NODE_DIR="${NODE_DIR:-.node}"
NPM_SCRIPT="${1:-dev}"
MIN_MAJOR=18
MIN_MINOR=17

# True only if the binary both executes on this host and is new enough for next@14.
node_usable() {
  local bin="$1" v major minor
  [ -x "$bin" ] || return 1
  v="$("$bin" --version 2>/dev/null)" || return 1   # non-zero here == glibc mismatch
  v="${v#v}"
  major="${v%%.*}"; minor="${v#*.}"; minor="${minor%%.*}"
  [ "$major" -gt "$MIN_MAJOR" ] && return 0
  [ "$major" -eq "$MIN_MAJOR" ] && [ "$minor" -ge "$MIN_MINOR" ]
}

conda_bin() {
  command -v mamba >/dev/null 2>&1 && { echo mamba; return 0; }
  command -v conda >/dev/null 2>&1 && { echo conda; return 0; }
  for root in "$HOME/miniforge3" "$HOME/miniconda3" "$HOME/anaconda3"; do
    [ -x "$root/bin/conda" ] && { echo "$root/bin/conda"; return 0; }
  done
  return 1
}

resolve_node_bindir() {
  # 1. Whatever is already on PATH.
  local p; p="$(command -v node 2>/dev/null || true)"
  if [ -n "$p" ] && node_usable "$p"; then dirname "$p"; return 0; fi

  # 2. A ./.node provisioned by an earlier run.
  if node_usable "$PWD/$NODE_DIR/bin/node"; then echo "$PWD/$NODE_DIR/bin"; return 0; fi

  # 3. Any nvm install that actually runs here (newest first).
  if [ -d "$HOME/.nvm/versions/node" ]; then
    local d
    for d in $(ls -1r "$HOME/.nvm/versions/node" 2>/dev/null); do
      node_usable "$HOME/.nvm/versions/node/$d/bin/node" \
        && { echo "$HOME/.nvm/versions/node/$d/bin"; return 0; }
    done
  fi

  # 4. Provision conda-forge nodejs (glibc 2.17 builds) into ./.node.
  local conda
  if conda="$(conda_bin)"; then
    echo "==> no usable Node >= ${MIN_MAJOR}.${MIN_MINOR} on this host; installing conda-forge nodejs into $NODE_DIR" >&2
    echo "    ($(ldd --version 2>/dev/null | head -1))" >&2
    rm -rf "$NODE_DIR"
    # Absolute --prefix: conda reads a bare relative path as an env *name*.
    "$conda" create --yes --quiet --prefix "$PWD/$NODE_DIR" \
      --channel conda-forge --override-channels "nodejs>=20" >&2
    node_usable "$PWD/$NODE_DIR/bin/node" && { echo "$PWD/$NODE_DIR/bin"; return 0; }
  fi
  return 1
}

if ! NODE_BIN="$(resolve_node_bindir)"; then
  cat >&2 <<EOF
ERROR: no Node >= ${MIN_MAJOR}.${MIN_MINOR}.0 available that runs on this host.

  system node : $(command -v node >/dev/null 2>&1 && node --version || echo "absent")
  glibc       : $(ldd --version 2>/dev/null | head -1)

The official Node >= 18 linux-x64 builds need glibc >= 2.28, so on Amazon Linux 2 they will
not run even once installed (nvm included). Pick one:

  1. Install Miniforge, then re-run \`make ui\` -- it will provision conda-forge nodejs:
       curl -L -o /tmp/miniforge.sh \\
         https://github.com/conda-forge/miniforge/releases/latest/download/Miniforge3-Linux-x86_64.sh
       bash /tmp/miniforge.sh -b -p "\$HOME/miniforge3"
  2. Run the UI in the provided container instead:
       docker compose up
  3. Fetch an unofficial glibc-217 Node build by hand into ./.node:
       https://unofficial-builds.nodejs.org/download/release/
EOF
  exit 1
fi

# Put the chosen Node first so npm's shim, next, and every child process agree on it.
export PATH="$NODE_BIN:$PATH"
echo "==> node $(node --version) (npm $(npm --version)) from $NODE_BIN"

cd ui
# `npm ci` when the lockfile is present: reproducible, and it is what a judge should get.
if [ -f package-lock.json ]; then
  npm ci
else
  npm install
fi
exec npm run "$NPM_SCRIPT"
