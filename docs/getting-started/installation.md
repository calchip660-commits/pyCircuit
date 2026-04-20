# Installation Guide

This guide covers the supported ways to install and verify pyCircuit
(`pyc4.0` / `pyc0.40`). The most common developer setup is:

1. install Python + LLVM/MLIR 19 + build tools
2. build the staged toolchain with `bash flows/scripts/pyc build`
3. install the Python frontend with `python3 -m pip install -e ".[dev]"`
4. run the smoke gates

If you do not want to build LLVM-backed tools locally, install the published
wheel instead.

## Choose an Installation Path

| Path | Best for | Installs |
| --- | --- | --- |
| Full source developer setup | Contributors and local backend/frontend development | `pycc`, runtime, editable Python package |
| Editable frontend-only install | Frontend work when you already have a toolchain | Editable Python package only |
| Published or local wheel | Fastest way to use pyCircuit without a local LLVM build | Python package plus bundled toolchain |

## Supported Tool Versions

| Component | Version | Notes |
| --- | --- | --- |
| Python | 3.10+ | Package metadata supports 3.10 and newer |
| LLVM / MLIR | 19 | The repo build scripts expect LLVM 19 |
| CMake | 3.20+ | Required by the top-level CMake project |
| Ninja | 1.10+ | Used by the build scripts and CI |
| C/C++ compiler | Clang, GCC, or AppleClang | Platform default is fine in most cases |

Optional tools:

- `verilator` for `bash flows/scripts/run_sims.sh`
- `iverilog` for broader simulation flows used in CI on Linux

Current CI validates Linux and macOS source builds. The commands below focus on
Ubuntu/Debian and macOS because those are the best-covered setups in this repo.

## Clone the Repository

```bash
git clone https://github.com/LinxISA/pyCircuit.git
cd pyCircuit
```

## Install System Dependencies

### Ubuntu/Debian

```bash
sudo apt-get update
sudo apt-get install -y \
  wget gnupg software-properties-common \
  cmake ninja-build clang \
  python3 python3-pip python3-venv

# Install LLVM/MLIR 19
wget https://apt.llvm.org/llvm.sh
chmod +x llvm.sh
sudo ./llvm.sh 19
sudo apt-get install -y llvm-19-dev mlir-19-tools libmlir-19-dev

# Optional simulation tools
sudo apt-get install -y verilator iverilog

# Make the LLVM tools visible in the current shell
export PATH="/usr/lib/llvm-19/bin:$PATH"

# Verify the toolchain
llvm-config-19 --version
mlir-opt --version
```

If you do not want to modify `PATH`, you can still build pyCircuit by passing
`--llvm-config /usr/lib/llvm-19/bin/llvm-config` to `flows/scripts/pyc build`.

### macOS

```bash
# Install Homebrew first if it is not already present:
# /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

brew update
brew install cmake ninja llvm@19 python@3

# Optional simulation tool
brew install verilator

export PATH="$(brew --prefix llvm@19)/bin:$PATH"

llvm-config --version
mlir-opt --version
```

## Full Source Developer Setup

This is the recommended path if you want to contribute to pyCircuit or build the
backend locally.

### 1) Create a Python environment

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### 2) Build the staged toolchain

The repo's canonical build entrypoint is `flows/scripts/pyc build`:

```bash
bash flows/scripts/pyc build
```

This stages the install tree under:

```text
.pycircuit_out/toolchain/install
```

If LLVM auto-detection does not work, pass `llvm-config` explicitly:

```bash
bash flows/scripts/pyc build \
  --llvm-config /usr/lib/llvm-19/bin/llvm-config
```

On macOS:

```bash
bash flows/scripts/pyc build \
  --llvm-config "$(brew --prefix llvm@19)/bin/llvm-config"
```

### 3) Install the Python package

For contributor workflows, install the editable package with development tools:

```bash
python -m pip install -e ".[dev]"
```

If you only want the runtime frontend package and not the dev extras:

```bash
python -m pip install -e .
```

### 4) Export the toolchain location

Editable installs do not put the locally built `pycc` on your global `PATH`.
Point the frontend at the staged toolchain:

```bash
export PYC_TOOLCHAIN_ROOT="$PWD/.pycircuit_out/toolchain/install"
export PATH="$PYC_TOOLCHAIN_ROOT/bin:$PATH"
```

### 5) Verify the install

```bash
pycc --version
python -m pycircuit.cli --help
```

## Editable Frontend-Only Install

Use this when you only need the Python frontend and already have a valid pyc
toolchain from either:

- `bash flows/scripts/pyc build`
- a previous staged install tree
- an installed wheel

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e .
```

Then point pyCircuit at an existing toolchain:

```bash
export PYC_TOOLCHAIN_ROOT=/path/to/pyc-toolchain-install
python -m pycircuit.cli --help
```

If `PYC_TOOLCHAIN_ROOT` is not set and `pycc` is not discoverable, frontend
commands that require compilation will fail with a missing-toolchain error.

## Install a Published or Local Wheel

Use this path if you want a working `pycc` without building LLVM-backed tools
from source.

### Install from PyPI

```bash
python3 -m pip install pycircuit-hisi
```

### Install a local wheel artifact

```bash
python3 -m pip install /path/to/pycircuit_hisi-<version>-py3-none-<platform>.whl
```

Verify the installed commands:

```bash
pycc --version
python3 -m pycircuit.cli --help
```

The distribution name is `pycircuit-hisi` to avoid the unrelated `pycircuit`
package on PyPI. The Python import path remains `pycircuit`.

The wheel is platform-specific because it bundles the matching toolchain. Use a
wheel built for your OS and architecture.

## Using Repo Smoke Scripts with an Installed Wheel

If you want to run this repository's smoke scripts against an installed wheel,
point the scripts at the bundled toolchain and tell them to use the installed
Python package rather than the repo source tree:

```bash
export PYC_TOOLCHAIN_ROOT="$(python -c 'import pycircuit, pathlib; print((pathlib.Path(pycircuit.__file__).resolve().parent / "_toolchain").as_posix())')"
export PYC_USE_INSTALLED_PYTHON_PACKAGE=1
unset PYCC
```

Then run:

```bash
bash flows/scripts/run_examples.sh
```

## Advanced: Manual CMake Build

Most users should prefer `bash flows/scripts/pyc build`, but you can also build
the toolchain manually:

```bash
LLVM_CONFIG_BIN="${LLVM_CONFIG_BIN:-llvm-config-19}"
# On macOS, you can set:
# LLVM_CONFIG_BIN="$(brew --prefix llvm@19)/bin/llvm-config"

LLVM_DIR="$("${LLVM_CONFIG_BIN}" --cmakedir)"
MLIR_DIR="$(dirname "$LLVM_DIR")/mlir"

cmake -G Ninja -S . -B .pycircuit_out/toolchain/build \
  -DCMAKE_BUILD_TYPE=Release \
  -DCMAKE_INSTALL_PREFIX="$PWD/.pycircuit_out/toolchain/install" \
  -DLLVM_DIR="$LLVM_DIR" \
  -DMLIR_DIR="$MLIR_DIR"

ninja -C .pycircuit_out/toolchain/build pycc pyc4_runtime
ninja -C .pycircuit_out/toolchain/build pyc-opt || true
cmake --install .pycircuit_out/toolchain/build --prefix "$PWD/.pycircuit_out/toolchain/install"
```

`pyc-opt` is built on a best-effort basis. Some LLVM/MLIR package layouts do
not provide everything needed for that binary, but `pycc` and the runtime are
the required pieces for normal pyCircuit usage.

## Verify Your Setup

### Compile smoke

```bash
bash flows/scripts/run_examples.sh
```

This is the fastest repo-level verification step and is the default smoke gate
used throughout the docs and CI.

### Simulation smoke

```bash
bash flows/scripts/run_sims.sh
```

Run this after installing simulation dependencies. It exercises the
`@testbench` flow, C++ execution, and Verilator-backed simulation.

### Manual single-design build

```bash
PYTHONPATH=compiler/frontend \
PYC_TOOLCHAIN_ROOT=.pycircuit_out/toolchain/install \
python3 -m pycircuit.cli build \
  designs/examples/counter/tb_counter.py \
  --out-dir /tmp/pyc_counter \
  --target both \
  --jobs 8
```

## Common Environment Variables

| Variable | Purpose |
| --- | --- |
| `PYC_TOOLCHAIN_ROOT` | Points pyCircuit at a staged or bundled install tree containing `bin/pycc`, runtime libs, and CMake metadata |
| `PYCC` | Explicit path to the `pycc` executable if you do not want auto-detection |
| `LLVM_CONFIG` | Optional override consumed by `flows/scripts/pyc build` |
| `LLVM_DIR` / `MLIR_DIR` | Explicit CMake package locations for manual or scripted builds |
| `PYC_USE_INSTALLED_PYTHON_PACKAGE=1` | Tells repo scripts to use the installed wheel package instead of repo-local frontend sources |

## Troubleshooting

### `flows/scripts/pyc build` cannot find LLVM or MLIR

Provide `llvm-config` directly:

```bash
bash flows/scripts/pyc build \
  --llvm-config /usr/lib/llvm-19/bin/llvm-config
```

Or set the CMake package locations yourself:

```bash
export LLVM_DIR=/path/to/lib/cmake/llvm
export MLIR_DIR=/path/to/lib/cmake/mlir
bash flows/scripts/pyc build
```

### `mlir-opt` is installed but not found on Ubuntu

The Debian/Ubuntu LLVM packages install MLIR tools under a versioned prefix.
Add them to `PATH`:

```bash
export PATH="/usr/lib/llvm-19/bin:$PATH"
```

### `pycc` is missing after `pip install -e .`

That is expected. Editable installs only provide the Python frontend. Either:

- build the toolchain with `bash flows/scripts/pyc build`, then export
  `PYC_TOOLCHAIN_ROOT="$PWD/.pycircuit_out/toolchain/install"`
- or install a wheel with `python3 -m pip install pycircuit-hisi`

### `pyc-opt` failed to build

`pyc-opt` is optional in the current build flow. If `pycc` builds and the smoke
gates pass, you can continue working.

### Start from a clean build

```bash
rm -rf .pycircuit_out/toolchain
bash flows/scripts/pyc build
```
