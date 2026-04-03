# PyCircuit Cycle-Aware API Reference

**Version: 2.1** (aligned with `compiler/frontend/pycircuit/v5.py`)

> Filename uses historic spelling **PyCurcit**; the implementation lives in the **`pycircuit`** package.

---

## Overview

The cycle-aware system is a new programming paradigm for PyCircuit that tracks signal timing cycles automatically. Key features include:

- **Cycle-aware Signals**: Each signal carries its cycle information
- **Automatic Cycle Balancing**: Automatic DFF insertion when combining signals of different cycles
- **Domain-based Cycle Management**: `next()`, `prev()`, `push()`, `pop()` methods for cycle control
- **JIT Compilation**: Python source code compiles to MLIR hardware description

## Installation

```python
from pycircuit import (
    CycleAwareCircuit,
    CycleAwareDomain,
    CycleAwareSignal,
    compile_cycle_aware,
    mux,
)
```

---

## Core Components

### CycleAwareCircuit

Subclass of `Circuit` used for V5 cycle-aware authoring. All `Circuit` APIs (`m.clock`, `m.input`, `m.out`, `m.output`, `emit_mlir`, scopes, `@module` children when composed, etc.) remain available.

```python
m = CycleAwareCircuit("my_circuit")
```

**Methods (V5-specific and common):**

| Method | Description |
|--------|-------------|
| `create_domain(name, *, frequency_desc="", reset_active_high=False)` | Create a `CycleAwareDomain` (extra args accepted for documentation; not yet wired into codegen) |
| `const_signal(value, width, domain)` | Constant as `Wire` via `domain.create_const` |
| `input_signal(name, width, domain)` | Input port as `Wire` via `domain.create_signal` |
| `output(name, signal)` | Register a module output (inherited from `Circuit`) |
| `emit_mlir()` | Generate MLIR string (inherited from `Circuit`) |

### CycleAwareDomain

Manages clock cycle state for a specific clock domain.

```python
domain = m.create_domain("clk")
```

**Methods:**

| Method | Description |
|--------|-------------|
| `create_signal(name, *, width)` | Create an input port (`Wire`); `width` is **keyword-only** |
| `create_const(value, *, width, name="")` | Create a constant `Wire` |
| `create_reset()` | Return reset as **i1** `Wire` (**1** = asserted) via lowering `pyc.reset_active` on the domain’s `!pyc.reset` port — safe for `mux` / boolean logic |
| `next()` | Advance current occurrence cycle by 1 |
| `prev()` | Decrease current occurrence cycle by 1 |
| `push()` | Save current cycle on a stack |
| `pop()` | Restore cycle from stack (must pair with `push`) |
| `cycle(sig, reset_value=None, name="")` | One-deep register; returns **`Wire`** (the register’s `q`) |
| `state(*, width, reset_value=0, name="")` | Feedback register as `StateSignal` (read current value, then `domain.next()` and `.set(next)`) |
| `delay_to(w, *, from_cycle, to_cycle, width)` | Internal delay chain for cycle balancing |
| `cycle_index` | Property: current logical occurrence index |

### CycleAwareSignal

Wrapper that carries cycle information along with the underlying MLIR signal.

**Attributes:**

| Attribute | Description |
|-----------|-------------|
| `wire` / `w` | Underlying `Wire` |
| `sig` | Underlying `Signal` |
| `cycle` | Current logical cycle index |
| `domain` | Associated `CycleAwareDomain` |
| `name` | Debug string (wire repr) |
| `signed` | Whether the wire is signed |

**Operator Overloading:**

All standard Python operators are overloaded with automatic cycle balancing:

```python
# Arithmetic
result = a + b  # Addition
result = a - b  # Subtraction
result = a * b  # Multiplication

# Bitwise
result = a & b   # AND
result = a | b   # OR
result = a ^ b   # XOR
result = ~a      # NOT
result = a << n  # Left shift
result = a >> n  # Right shift

# Comparison (either form; both lower to the same hardware)
result = a == b   # Equal
result = a.eq(b)  # Equal (explicit)
result = a < b    # Less than
result = a.lt(b)  # Less than (explicit)
result = a > b
result = a.gt(b)
result = a <= b
result = a.le(b)
result = a >= b
result = a.ge(b)
```

**Signal Methods:**

| Method | Description |
|--------|-------------|
| `select(true_val, false_val)` | Conditional selection (mux) |
| `trunc(width)` | Truncate to width bits |
| `zext(width)` | Zero extend to width bits |
| `sext(width)` | Sign extend to width bits |
| `slice(high, low)` | Extract bit slice |
| `named(name)` | Add debug name |
| `as_signed()` | Mark as signed |
| `as_unsigned()` | Mark as unsigned |

---

## Automatic Cycle Balancing

When combining signals with different cycles, the system automatically inserts DFF chains to align timing.

### Rule

```
output_cycle = max(input_cycles)
earlier_signals → automatically delayed via DFF insertion
```

### Example

```python
def design(m: CycleAwareCircuit, domain: CycleAwareDomain):
    # Cycle 0: Input
    data_in = domain.create_signal("data_in", width=8)
    
    # Save reference at Cycle 0
    data_at_cycle0 = data_in
    
    domain.next()  # -> Cycle 1
    stage1 = domain.cycle(data_in, reset_value=0, name="stage1")
    
    domain.next()  # -> Cycle 2
    stage2 = domain.cycle(stage1, reset_value=0, name="stage2")
    
    # data_at_cycle0 is at Cycle 0, stage2 is at Cycle 2
    # System automatically inserts 2-level DFF chain for data_at_cycle0
    combined = data_at_cycle0 + stage2  # Output at Cycle 2
    
    m.output("result", combined.wire)
```

Generated MLIR shows automatic DFF insertion:

```mlir
%data_delayed1 = pyc.reg %clk, %rst, %en, %data_at_cycle0, %reset_val : i8
%data_delayed2 = pyc.reg %clk, %rst, %en, %data_delayed1, %reset_val : i8
%result = pyc.add %data_delayed2, %stage2 : i8
```

---

## Cycle Management

### next() / prev()

Advance or decrease the current cycle counter.

```python
# Cycle 0
a = domain.create_signal("a", width=8)

domain.next()  # -> Cycle 1
b = domain.cycle(a, name="b")

domain.next()  # -> Cycle 2
c = domain.cycle(b, name="c")

domain.prev()  # -> Cycle 1
# Can add more signals at Cycle 1
d = (a + 1)  # Also at Cycle 1 (with auto balancing)
```

### push() / pop()

Save and restore cycle state for nested function calls.

```python
def helper_function(domain: CycleAwareDomain, data):
    domain.push()  # Save caller's cycle
    
    # Internal cycle management
    domain.next()
    result = domain.cycle(data, name="helper_reg")
    domain.next()
    final = result + 1
    
    domain.pop()  # Restore caller's cycle
    return final

def main_design(m: CycleAwareCircuit, domain: CycleAwareDomain):
    data = domain.create_signal("data", width=8)
    
    # Call helper - its internal next() doesn't affect our cycle
    result = helper_function(domain, data)
    
    # Still at our original cycle
    domain.next()  # Our own cycle advancement
```

### cycle()

Insert a DFF register (single-cycle delay).

```python
# Basic register
reg = domain.cycle(data, name="data_reg")

# Register with reset value
counter_reg = domain.cycle(counter_next, reset_value=0, name="counter")
```

---

## JIT Compilation

### compile_cycle_aware()

Lowers `fn(m, domain, **kwargs)` either through **JIT** (`compile`) or **eager** construction.

```python
def my_design(m: CycleAwareCircuit, domain: CycleAwareDomain, width: int = 8):
    data = domain.create_signal("data", width=width)
    processed = data + 1
    domain.next()
    output_w = domain.cycle(processed, name="output")
    m.output("out", output_w)

# JIT (default): returns compiled module like compile()
mod = compile_cycle_aware(my_design, name="my_circuit", width=16)

# Eager: run Python body directly, returns CycleAwareCircuit
m2 = compile_cycle_aware(my_design, name="my_circuit", width=16, eager=True)
mlir_code = m2.emit_mlir()
```

### Parameters

| Parameter | Description |
|-----------|-------------|
| `fn` | `def fn(m: CycleAwareCircuit, domain: CycleAwareDomain, ...)` |
| `name` | Module/circuit name (optional) |
| `domain_name` | Domain name (default `"clk"`); `"clk"` maps to top `clk`/`rst` ports |
| `eager` | If `True`, no JIT; no `if Wire` / JIT control flow in the body |
| `structural` | Forwarded to JIT wrapper (`__pycircuit_emit_structural__`) when not eager |
| `value_params` | Optional runtime value-parameter map for the JIT wrapper |
| `**jit_params` | Extra kwargs passed to `fn` and/or `jit.compile` |

### Return Statement

The JIT compiler handles return statements by registering outputs:

```python
def design(m: CycleAwareCircuit, domain: CycleAwareDomain):
    data = domain.create_signal("data", width=8)
    result = data + 1
    return result  # Automatically becomes output "result"
```

---

## Global Functions

### cas()

Wrap a plain `Wire` (e.g. from `m.input`) as a `CycleAwareSignal` at the domain’s current `cycle_index` (or at `cycle=` if given). Used heavily when migrating `@module` ports into V5 pipelines.

```python
from pycircuit import cas

x = cas(domain, m.input("x", width=8), cycle=0)
```

### mux()

Conditional selection with automatic cycle balancing.

```python
result = mux(condition, true_value, false_value)
```

**Parameters:**

- `condition`: CycleAwareSignal (1-bit) for selection
- `true_value`: Value when condition is true (CycleAwareSignal or int)
- `false_value`: Value when condition is false (CycleAwareSignal or int)

**Example:**

```python
enable = domain.create_signal("enable", width=1)
data = domain.create_signal("data", width=8)
result = mux(enable, data + 1, data)  # Increment when enabled
```

---

## Complete Example

```python
# -*- coding: utf-8 -*-
"""Counter with enable - cycle-aware implementation."""

from pycircuit import (
    CycleAwareCircuit,
    CycleAwareDomain,
    compile_cycle_aware,
    mux,
)


def counter_with_enable(
    m: CycleAwareCircuit,
    domain: CycleAwareDomain,
    width: int = 8,
):
    """8-bit counter with enable control."""
    
    # Cycle 0: Inputs
    enable = domain.create_signal("enable", width=1)
    
    # Counter initial value
    count = domain.create_const(0, width=width, name="count_init")
    
    # Combinational logic
    count_next = count + 1
    count_with_enable = mux(enable, count_next, count)
    
    # Cycle 1: Register
    domain.next()
    count_reg = domain.cycle(count_with_enable, reset_value=0, name="count")
    
    # Output (`cycle` returns the register output `Wire`)
    m.output("count", count_reg)


if __name__ == "__main__":
    circuit = compile_cycle_aware(counter_with_enable, name="counter", width=8)
    print(circuit.emit_mlir())
```

---

## Migration from Legacy API

| Legacy API | Cycle-Aware API |
|------------|-----------------|
| `Circuit` | `CycleAwareCircuit` (subclass; `Circuit` APIs still valid) |
| `ClockDomain` ports | `CycleAwareDomain` + `create_domain` |
| `Wire` / `Reg` at ports | Often `cas(domain, m.input(...), cycle=...)` for typed cycles |
| Feedback `m.out` + `.set` | `domain.state(...)` + `domain.next()` + `.set(...)` |
| `compile()` | `compile_cycle_aware(...)` (JIT default) or `eager=True` |
| Manual delay alignment | `domain.cycle()`, `delay_to`, and operator-driven balancing |

---

## Best Practices

1. **Use descriptive names**: The `named()` method helps with debugging
   ```python
   result = (a + b).named("sum_ab")
   ```

2. **Mark cycle boundaries clearly**: Use comments to document pipeline stages
   ```python
   # === Stage 1: Fetch ===
   domain.next()
   ```

3. **Use push/pop for helper functions**: Avoid cycle state leakage
   ```python
   def helper(domain, data):
       domain.push()
       # ... logic ...
       domain.pop()
       return result
   ```

4. **Let automatic balancing work**: Trust the system to insert DFFs when needed

---

**Copyright (C) 2024-2026 PyCircuit Contributors**
