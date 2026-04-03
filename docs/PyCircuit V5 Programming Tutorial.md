# PyCircuit Programming Tutorial

**作者：Liao Heng**

**版本：1.2**（与 `compiler/frontend/pycircuit/v5.py` 对齐；新增函数式层次化设计章节）

> **包名**：Python 包为 **`pycircuit`**（全小写）。不要使用 `pyCircuit` 作为 import 目标。  
> **API 细则**：以 `docs/PyCurcit V5_CYCLE_AWARE_API.md` 为准。  
> **并存风格**：pyc4.0 的 `@module` / `Circuit` 流程仍是官方主路径之一，见 `docs/tutorial/unified-signal-model.md` 与 `docs/FRONTEND_API.md`。

---

## 目录

1. [概述](#概述)
2. [两种编程风格](#两种编程风格)
   - [风格 A：函数式（推荐）](#风格-a函数式推荐)
   - [风格 B：类式模块](#风格-b类式模块)
3. [核心概念](#核心概念)
   - [Clock Domain（时钟域）](#clock-domain时钟域)
   - [Signal（信号）](#signal信号)
   - [Module（模块）](#module模块)
   - [clock_domain.next()](#clock_domainnext)
   - [clock_domain.prev()](#clock_domainprev)
   - [clock_domain.push() / pop()](#clock_domainpush--pop)
   - [clock_domain.cycle()](#clock_domaincycle)
   - [Nested Module（嵌套模块）](#nested-module嵌套模块)
4. [函数式层次化设计](#函数式层次化设计)
   - [基本模式：子函数调用](#基本模式子函数调用)
   - [信号传递与共享上下文](#信号传递与共享上下文)
   - [子函数的周期隔离（push/pop）](#子函数的周期隔离pushpop)
   - [子函数的周期延续](#子函数的周期延续)
   - [命名约定：前缀隔离](#命名约定前缀隔离)
   - [返回值模式：子函数向父函数传递结果](#返回值模式子函数向父函数传递结果)
   - [与 m.instance() 的对比](#与-minstance-的对比)
5. [自动周期平衡](#自动周期平衡)
6. [两种输出模式](#两种输出模式)
7. [编程范例](#编程范例)
   - [范例1：频率分频器（testdivider.py）](#范例1频率分频器testdividerpy)
   - [范例2：实时时钟系统（testproject.py）](#范例2实时时钟系统testprojectpy)
   - [范例3：RISC-V CPU（riscv.py）](#范例3risc-v-cpuriscvpy)
   - [范例4：SoC 层次化集成（函数式风格）](#范例4soc-层次化集成函数式风格)
8. [生成的电路图](#生成的电路图)
9. [最佳实践](#最佳实践)

---

## 概述

PyCircuit 是一个基于 Python 的硬件描述语言（HDL）框架，专为数字电路设计而创建。它提供了一种直观的方式来描述时序逻辑电路，核心特性包括：

- **周期感知信号（Cycle-aware Signals）**：每个信号都携带其时序周期信息
- **多时钟域支持**：独立管理多个时钟域及其复位信号
- **自动周期平衡**：自动插入延迟（DFF）或反馈（FB）以对齐信号时序
- **自动变量名提取**：使用 JIT 方法从 Python 源码提取变量名
- **层次化/扁平化输出**：支持两种电路描述模式

### 安装与导入

```python
from pycircuit import (
    CycleAwareCircuit,    # V5 顶层电路（推荐入口）
    CycleAwareDomain,     # 周期感知时钟域
    pyc_ClockDomain,      # 别名，等同于 CycleAwareDomain
    pyc_Signal,           # 别名，等同于 CycleAwareSignal
    pyc_CircuitModule,    # 电路模块基类（配合 with self.module(...)）
    pyc_CircuitLogger,    # 电路日志器（文本描述，可选）
    compile_cycle_aware,  # V5 编译入口（JIT 或 eager）
    signal,               # 信号创建快捷方式（需在 module 上下文中）
    log,                  # 日志占位（当前为恒等）
    mux,                  # 多路选择器（支持周期对齐）
)
```

**Obsoleted**：`from pyVisualize import visualize_circuit` 及独立 `pyVisualize` 可视化链不再随本仓库维护；若需网表/MLIR 调试，请使用 `emit_mlir()` 或项目内既有仿真流程。

---

## 两种编程风格

PyCircuit V5 支持两种风格来描述硬件电路。对于新项目（尤其是大规模 SoC），**推荐使用函数式风格**。

### 风格 A：函数式（推荐）

以普通 Python 函数 `build_*(m, domain, ...)` 作为模块描述单元，通过 `compile_cycle_aware()` 编译。这是 V5 的核心编程模型，也是 XiangShan-pyc 等大型项目采用的风格。

```python
from pycircuit import (
    CycleAwareCircuit,
    CycleAwareDomain,
    CycleAwareSignal,
    cas,                  # 创建 cycle-aware 信号
    compile_cycle_aware,  # V5 编译入口
    mux,
    u,                    # 无符号字面量
)

def build_my_module(
    m: CycleAwareCircuit,
    domain: CycleAwareDomain,
    *,
    data_width: int = 32,
) -> None:
    """模块逻辑：直接操作 m 和 domain。"""

    # 输入
    data_in = cas(domain, m.input("data_in", width=data_width), cycle=0)
    valid   = cas(domain, m.input("valid", width=1), cycle=0)

    # 状态（反馈寄存器）
    acc_r = domain.state(width=data_width, reset_value=0, name="acc")
    acc   = cas(domain, acc_r.wire, cycle=0)

    # 组合逻辑
    acc_next = mux(valid, acc.wire + data_in.wire, acc.wire)

    # 流水线寄存器 (cycle 0 → cycle 1)
    result_w = domain.cycle(acc_next.wire, name="result_reg")

    domain.next()  # 推进到 cycle 1

    # 输出
    m.output("result", result_w)

    # 状态更新
    domain.next()
    acc_r.set(acc_next)

# 编译
if __name__ == "__main__":
    ir = compile_cycle_aware(build_my_module, name="my_module", eager=True,
                             data_width=16)
    print(ir.emit_mlir())
```

**核心优势：**
- `(m, domain)` 是贯穿上下文，所有信号操作直接在同一张信号图上
- `domain.next()` 推进时间线，代码按时序线性叙事
- 子函数调用天然构成层次，无需额外的例化 API
- Python 函数就是最自然的抽象边界

### 风格 B：类式模块

以 `pyc_CircuitModule` 子类 + `build()` 方法作为模块描述单元。适合小型独立模块或教学场景。

```python
class MyModule(pyc_CircuitModule):
    def __init__(self, name, clock_domain):
        super().__init__(name, clock_domain=clock_domain)

    def build(self, input1, input2):
        with self.module(inputs=[input1, input2], description="...") as mod:
            result = (input1 + input2) | "Sum"
            mod.outputs = [result]
        return result
```

> **选择建议**：函数式风格更简洁、更 Pythonic，适合大规模系统的层次化组合；类式风格提供更强的封装性，适合高复用 IP 核。本教程后续「核心概念」和「编程范例 1-3」沿用类式风格以保持向后兼容，「函数式层次化设计」章节和「范例 4」展示函数式风格。

---

## 核心概念

### Clock Domain（时钟域）

时钟域是 PyCircuit 中最基础的概念，它代表一个独立的时钟信号及其相关的时序逻辑。

#### 创建时钟域

`CycleAwareDomain` **不能**脱离电路单独构造。先创建 `CycleAwareCircuit`，再为每个域调用 `create_domain`：

```python
# 语法
m = CycleAwareCircuit("top")
clock_domain = m.create_domain(name, frequency_desc="", reset_active_high=False)

# 示例
m = CycleAwareCircuit("soc")
cpu_clk = m.create_domain("CPU_CLK", frequency_desc="100MHz CPU clock", reset_active_high=False)
rtc_clk = m.create_domain("RTC_CLK", frequency_desc="1Hz RTC domain", reset_active_high=False)
```

**参数说明：**
- `name`：时钟域名称（字符串）；名为 `"clk"` 时使用顶层 `clk`/`rst` 端口
- `frequency_desc` / `reset_active_high`：当前实现中保留给文档与后续扩展，不改变生成的端口名

#### 创建复位信号

```python
rst = clock_domain.create_reset()  # 创建复位信号
# 自动命名为 {domain_name}_rstn 或 {domain_name}_rst
```

#### 创建输入信号

`create_signal` 的位宽为 **关键字参数** `width=`（必选）：

```python
clk_in = clock_domain.create_signal("clock_input", width=1)
data_in = clock_domain.create_signal("data_input", width=32)
```

---

### Signal（信号）

信号是 PyCircuit 中的基本数据单元，每个信号都包含：
- 表达式（expression）
- 周期（cycle）
- 时钟域（domain）
- 位宽（width，可选）

#### 信号创建语法

```python
# 方式1：使用 signal 快捷方式（推荐）
counter = signal[7:0](value=0) | "8-bit counter"
data = signal[31:0](value="input_data") | "32-bit data"
flag = signal(value="condition") | "Boolean flag"

# 方式2：动态位宽
bits = 8
reg = signal[f"{bits}-1:0"](value=0) | "Dynamic width register"

# 方式3：位选择表达式
opcode = signal[6:0](value=f"{instruction}[6:0]") | "Opcode field"
```

**语法说明：**
- `signal[high:low](value=...)`：创建指定位宽的信号
- `| "description"`：管道运算符添加描述（可选但推荐）
- `value` 可以是：
  - 整数常量：`0`, `0xFF`
  - 字符串表达式：`"input_data"`, `"a + b"`
  - 格式化字符串：`f"{other_signal}[7:0]"`

#### 信号运算

PyCircuit 重载了 Python 运算符，支持硬件描述式的信号运算：

```python
# 算术运算
sum_val = (a + b) | "Addition"
diff = (a - b) | "Subtraction"
prod = (a * b) | "Multiplication"

# 逻辑运算
and_result = (a & b) | "Bitwise AND"
or_result = (a | b) | "Bitwise OR"
xor_result = (a ^ b) | "Bitwise XOR"
not_result = (~a) | "Bitwise NOT"

# 比较运算
eq = (a == b) | "Equal"
ne = (a != b) | "Not equal"
lt = (a < b) | "Less than"
gt = (a > b) | "Greater than"

# 多路选择器
result = mux(condition, true_value, false_value) | "Mux selection"
```

**说明**：`expr | "描述文字"` 在 `CycleAwareSignal` 上为可选的文档式写法（当前实现忽略该字符串，不改变硬件）；需要稳定调试名时请优先使用 `.named("...")`。

---

### Module（模块）

模块是电路设计的基本组织单元，封装了一组相关的信号和逻辑。

#### 定义模块类

```python
class MyModule(pyc_CircuitModule):
    """自定义电路模块"""
    
    def __init__(self, name, clock_domain):
        super().__init__(name, clock_domain=clock_domain)
        # 初始化模块参数
        
    def build(self, input1, input2):
        """构建模块逻辑"""
        with self.module(
            inputs=[input1, input2],
            description="Module description"
        ) as mod:
            # 模块内部逻辑
            result = (input1 + input2) | "Sum"
            
            # 设置输出
            mod.outputs = [result]
        
        return result
```

#### 模块上下文管理器

`self.module()` 返回一个上下文管理器，用于：
- 记录模块边界
- 管理输入/输出信号
- 在嵌套模块中正确处理时钟周期

```python
with self.module(
    inputs=[sig1, sig2],      # 输入信号列表
    description="描述文字"     # 模块描述
) as mod:
    # 模块逻辑
    mod.outputs = [out1, out2]  # 设置输出
```

---

### clock_domain.next()

`next()` 方法推进时钟周期边界，标记时序逻辑的分界点。

#### 语法

```python
self.clock_domain.next()  # 推进到下一个时钟周期
```

#### 语义

- 调用 `next()` 后，所有新创建的信号将属于新的周期
- 用于分隔组合逻辑和时序逻辑
- 在流水线设计中标记各级边界

#### 示例

```python
def build(self, input_data):
    with self.module(inputs=[input_data]) as mod:
        # Cycle 0: 输入处理
        processed = (input_data & 0xFF) | "Masked input"
        
        self.clock_domain.next()  # 推进到 Cycle 1
        
        # Cycle 1: 进一步处理
        result = (processed + 1) | "Incremented"
        
        self.clock_domain.next()  # 推进到 Cycle 2
        
        # Cycle 2: 输出
        output = result | "Final output"
        mod.outputs = [output]
```

---

### clock_domain.prev()

`prev()` 方法将时钟周期回退一步，与 `next()` 相反。

#### 语法

```python
self.clock_domain.prev()  # 回退到上一个时钟周期
```

#### 语义

- 调用 `prev()` 后，当前默认周期减 1
- 允许在过程式编程中灵活调整周期位置
- 周期计数可以变为负数（这是设计允许的）

#### 示例

```python
def build(self, input_data):
    with self.module(inputs=[input_data]) as mod:
        # Cycle 0
        a = input_data | "Input"
        
        self.clock_domain.next()  # -> Cycle 1
        b = (a + 1) | "Incremented"
        
        self.clock_domain.next()  # -> Cycle 2
        c = (b * 2) | "Doubled"
        
        self.clock_domain.prev()  # -> Cycle 1 (回退)
        # 现在我们回到了 Cycle 1，可以添加更多同周期的信号
        d = (a - 1) | "Decremented"
```

---

### clock_domain.push() / pop()

`push()` 和 `pop()` 方法提供周期状态的栈管理，允许子函数拥有独立的周期划分而不影响调用者。

#### 语法

```python
self.clock_domain.push()  # 保存当前周期到栈
# ... 进行周期操作 ...
self.clock_domain.pop()   # 恢复之前保存的周期
```

#### 语义

- `push()` 将当前周期状态保存到用户周期栈
- `pop()` 从栈中弹出并恢复周期状态
- 支持嵌套调用（多层 push/pop）
- 如果 `pop()` 在没有匹配的 `push()` 时调用，会抛出 `RuntimeError`

#### 使用场景

这些方法特别适合过程式编程，允许不同的子函数拥有独立的周期管理策略：

```python
class MyModule(pyc_CircuitModule):
    def helper_function_a(self, data):
        """子函数 A：使用 2 个周期"""
        self.clock_domain.push()  # 保存调用者的周期状态
        
        # 进行自己的周期划分
        result = data | "Input"
        self.clock_domain.next()
        result = (result + 1) | "Processed"
        self.clock_domain.next()
        final = (result * 2) | "Final"
        
        self.clock_domain.pop()   # 恢复调用者的周期状态
        return final
    
    def helper_function_b(self, data):
        """子函数 B：使用 1 个周期"""
        self.clock_domain.push()  # 保存调用者的周期状态
        
        # 不同的周期划分策略
        result = (data & 0xFF) | "Masked"
        self.clock_domain.next()
        output = (result | 0x100) | "Flagged"
        
        self.clock_domain.pop()   # 恢复调用者的周期状态
        return output
    
    def build(self, input_data):
        with self.module(inputs=[input_data]) as mod:
            # Cycle 0
            processed = input_data | "Input"
            
            # 调用子函数，它们各自管理自己的周期
            result_a = self.helper_function_a(processed)
            result_b = self.helper_function_b(processed)
            
            # 仍在 Cycle 0（子函数的周期操作不影响这里）
            combined = (result_a + result_b) | "Combined"
            
            mod.outputs = [combined]
```

#### 嵌套使用示例

```python
def outer_function(self, data):
    self.clock_domain.push()  # 保存周期 0
    
    self.clock_domain.next()  # -> 周期 1
    intermediate = self.inner_function(data)  # inner 也可以 push/pop
    
    self.clock_domain.next()  # -> 周期 2
    result = intermediate | "Result"
    
    self.clock_domain.pop()   # 恢复周期 0
    return result

def inner_function(self, data):
    self.clock_domain.push()  # 保存周期 1
    
    self.clock_domain.next()  # -> 周期 2
    self.clock_domain.next()  # -> 周期 3
    processed = data | "Processed"
    
    self.clock_domain.pop()   # 恢复周期 1
    return processed
```

---

### clock_domain.cycle()

`cycle()` 方法实现 D 触发器（单周期延迟），用于创建时序元件。

#### 语法

```python
registered = self.clock_domain.cycle(signal, description="", reset_value=None)
```

**参数：**
- `signal`：要寄存的信号
- `description`：描述（可选）
- `reset_value`：复位值（可选）

#### 语义

- 输出信号的周期 = 输入信号周期 + 1
- 如果指定 `reset_value`，生成带复位的 DFF
- 等效于 Verilog 的 `always @(posedge clk)` 块

#### 示例

```python
# 简单寄存器
data_reg = self.clock_domain.cycle(data, "Data register")

# 带复位值的计数器
counter_reg = self.clock_domain.cycle(counter_next, reset_value=0) | "Counter register"

# 流水线寄存器
stage1_reg = self.clock_domain.cycle(stage0_out, "Pipeline stage 1")
stage2_reg = self.clock_domain.cycle(stage1_reg, "Pipeline stage 2")
```

---

### Nested Module（嵌套模块）

PyCircuit 支持模块的层次化设计，允许在一个模块内实例化其他模块。

#### 语法

```python
# 在父模块的 build 方法中
submodule = SubModuleClass("instance_name", self.clock_domain)
outputs = submodule.build(input1, input2)
```

#### 子模块周期隔离

子模块内部调用 `clock_domain.next()` 不会影响父模块的周期状态：

```python
class ParentModule(pyc_CircuitModule):
    def build(self, input_data):
        with self.module(inputs=[input_data]) as mod:
            # 父模块 Cycle 0
            processed = input_data | "Input"
            
            self.clock_domain.next()  # 父模块推进到 Cycle 1
            
            # 实例化子模块
            child = ChildModule("child", self.clock_domain)
            result = child.build(processed)  # 子模块内部可以有自己的 next()
            
            # 仍在父模块 Cycle 1（子模块的 next() 不影响父模块）
            output = result | "Output"
            mod.outputs = [output]
```

#### 层次化 vs 扁平化

PyCircuit 支持两种输出模式：

1. **层次化模式（Hierarchical）**：保留模块边界，显示嵌套结构
2. **扁平化模式（Flatten）**：展开所有子模块，信号名带模块前缀

```python
# 层次化模式
hier_logger = pyc_CircuitLogger("circuit.txt", is_flatten=False)

# 扁平化模式
flat_logger = pyc_CircuitLogger("circuit.txt", is_flatten=True)
```

---

## 函数式层次化设计

在大规模系统（如多核处理器）中，设计必然包含层次关系：顶层调用子系统，子系统又包含更细粒度的模块。PyCircuit V5 的函数式风格提供了一种非常自然的方式来表达这种层次——**子函数调用**。

### 基本模式：子函数调用

每个子模块是一个 `build_*(m, domain, ...)` 函数。父模块通过直接调用子函数来「包含」子模块的全部逻辑。子函数的信号操作会**扁平展开**到同一张信号图中。

```python
def build_alu(m, domain, *, data_width=32, prefix="alu"):
    """ALU 子模块"""
    op_a = cas(domain, m.input(f"{prefix}_op_a", width=data_width), cycle=0)
    op_b = cas(domain, m.input(f"{prefix}_op_b", width=data_width), cycle=0)
    op   = cas(domain, m.input(f"{prefix}_op", width=4), cycle=0)

    add_result = op_a.wire + op_b.wire
    sub_result = op_a.wire - op_b.wire
    result = mux(op.wire[0], sub_result, add_result)

    m.output(f"{prefix}_result", result[0:data_width])

def build_regfile(m, domain, *, data_width=32, prefix="rf"):
    """寄存器文件子模块"""
    rs1_addr = cas(domain, m.input(f"{prefix}_rs1_addr", width=5), cycle=0)
    rd_data  = cas(domain, m.input(f"{prefix}_rd_data", width=data_width), cycle=0)
    # ... 寄存器读写逻辑 ...
    m.output(f"{prefix}_rs1_data", rd_data.wire)

def build_cpu_core(m, domain, *, data_width=32):
    """CPU 核心：组合 ALU + 寄存器文件"""

    # 直接调用子函数 — 子模块的逻辑展开到当前信号图
    build_regfile(m, domain, data_width=data_width, prefix="rf")
    build_alu(m, domain, data_width=data_width, prefix="alu")

    # 跨子模块连线由父函数自行编排
    # ...
```

**关键特性：**
- 一行 `build_alu(m, domain, ...)` 即表达「此处包含 ALU」，意图清晰
- 子函数直接操作同一个 `m` 和 `domain`，信号天然互通
- 阅读者可 Ctrl+Click 跳入子函数查看实现细节

### 信号传递与共享上下文

函数调用方式的最大优势是 **`(m, domain)` 作为共享上下文**，信号不需要通过端口映射传递：

```python
def build_decode(m, domain, *, prefix="dec"):
    """解码级：从 m 上直接读写信号"""
    # 读取前级流水线寄存器（由 build_fetch 写入 m）
    inst_w = cas(domain, m.input(f"{prefix}_inst", width=32), cycle=0)

    opcode = inst_w.wire[0:7]
    rd     = inst_w.wire[7:12]
    rs1    = inst_w.wire[15:20]

    m.output(f"{prefix}_opcode", opcode)
    m.output(f"{prefix}_rd", rd)
    m.output(f"{prefix}_rs1", rs1)

def build_pipeline(m, domain):
    """流水线顶层"""
    build_fetch(m, domain, prefix="fe")
    # fetch 的输出已经在 m 上，decode 可以直接读取
    build_decode(m, domain, prefix="dec")
    build_execute(m, domain, prefix="exe")
```

这种模式的信号流是**隐式共享**的：子函数通过 `m.input()`/`m.output()` 在同一个 Circuit 上声明端口，或者通过 `domain.state()`/`domain.cycle()` 创建的 Wire 对象在函数间传递。

### 子函数的周期隔离（push/pop）

当子函数有独立的多周期流水线，且不希望影响父函数的周期计数时，使用 `domain.push()` / `domain.pop()`：

```python
def build_bpu(m, domain, *, prefix="bpu"):
    """分支预测单元：内部 4 级流水线，不影响调用者的周期"""
    domain.push()  # 保存调用者的周期状态

    # Stage 0: 预测请求
    pc = cas(domain, m.input(f"{prefix}_pc", width=39), cycle=0)
    s0_pred = pc.wire  # 简化的预测逻辑

    s1_pred_w = domain.cycle(s0_pred, name=f"{prefix}_s1_pred")
    domain.next()

    # Stage 1: TAGE 预测
    s1_taken = s1_pred_w[0]
    s2_taken_w = domain.cycle(s1_taken, name=f"{prefix}_s2_taken")
    domain.next()

    # Stage 2: 最终预测
    m.output(f"{prefix}_taken", s2_taken_w)
    m.output(f"{prefix}_target", s1_pred_w)

    domain.pop()  # 恢复调用者的周期状态

def build_frontend(m, domain, *, prefix="fe"):
    """前端：调用 BPU + ICache + Decode"""
    # 调用前 domain 在 cycle 0
    build_bpu(m, domain, prefix=f"{prefix}_bpu")
    # 调用后仍在 cycle 0（BPU 的 push/pop 隔离了内部周期）

    build_icache(m, domain, prefix=f"{prefix}_ic")
    build_decode(m, domain, prefix=f"{prefix}_dec")
```

### 子函数的周期延续

另一种模式是让子函数**延续**父函数的周期进度，适合流水线各级之间有严格顺序的场景：

```python
def build_fetch(m, domain, *, prefix="fe"):
    """取指级（cycle 0 → cycle 1）"""
    pc = cas(domain, m.input(f"{prefix}_pc", width=32), cycle=0)
    inst_mem = cas(domain, m.input(f"{prefix}_imem_data", width=32), cycle=0)

    s1_pc_w = domain.cycle(pc.wire, name=f"{prefix}_s1_pc")
    s1_inst_w = domain.cycle(inst_mem.wire, name=f"{prefix}_s1_inst")
    domain.next()  # 推进到 cycle 1

    m.output(f"{prefix}_inst", s1_inst_w)
    m.output(f"{prefix}_pc_out", s1_pc_w)

def build_decode(m, domain, *, prefix="dec"):
    """解码级（接续 cycle 1 → cycle 2）"""
    # 此时 domain 已在 cycle 1（由 build_fetch 推进）
    inst = cas(domain, m.input(f"{prefix}_inst", width=32), cycle=0)
    # ... 解码逻辑 ...
    s2_opcode_w = domain.cycle(inst.wire[0:7], name=f"{prefix}_s2_opcode")
    domain.next()  # 推进到 cycle 2

def build_pipeline(m, domain):
    """按周期顺序组合"""
    build_fetch(m, domain, prefix="fe")    # cycle 0 → 1
    build_decode(m, domain, prefix="dec")  # cycle 1 → 2
    build_execute(m, domain, prefix="exe") # cycle 2 → 3
```

> **选择建议**：如果子模块是「独立 IP」（如 BPU、缓存控制器），使用 `push()/pop()` 隔离周期。如果子模块是流水线的一个阶段，使用周期延续模式。

### 命名约定：前缀隔离

函数调用方式的一个注意事项是**命名冲突**：多个子函数如果在同一个 `m` 上声明相同名称的 `input`/`output`/`state`，会产生冲突。解决方法是统一使用 **前缀（prefix）** 参数：

```python
def build_load_unit(m, domain, *, prefix="ldu", data_width=64):
    addr   = cas(domain, m.input(f"{prefix}_addr", width=data_width), cycle=0)
    valid  = cas(domain, m.input(f"{prefix}_valid", width=1), cycle=0)
    result = domain.state(width=data_width, reset_value=0, name=f"{prefix}_result")
    # ...
    m.output(f"{prefix}_data_out", result.wire)

def build_store_unit(m, domain, *, prefix="stu", data_width=64):
    addr   = cas(domain, m.input(f"{prefix}_addr", width=data_width), cycle=0)
    valid  = cas(domain, m.input(f"{prefix}_valid", width=1), cycle=0)
    # ... 同名 addr/valid，但因为前缀不同所以不冲突
    m.output(f"{prefix}_done", ...)

def build_memblock(m, domain, *, prefix="mem"):
    build_load_unit(m, domain, prefix=f"{prefix}_ldu")
    build_store_unit(m, domain, prefix=f"{prefix}_stu")
```

**推荐命名规则：**

| 元素 | 模式 | 示例 |
|------|------|------|
| 输入端口 | `{prefix}_{name}` | `fe_bpu_pc`, `be_rob_idx` |
| 输出端口 | `{prefix}_{name}` | `fe_dec_valid_0`, `mem_ldu_data` |
| 状态寄存器 | `{prefix}_{name}` | `fe_fetch_pc`, `be_stall` |
| 流水线寄存器 | `{prefix}_s{N}_{name}` | `fe_s1_inst`, `fe_s2_data` |

### 显式信号传递规范

子函数调用时，信号通过 **Python 函数参数和返回值** 在父子函数间传递。这是推荐的信号互联方式，因为它让数据流清晰可追踪，并且 **完整保留 `CycleAwareSignal` 的 cycle 属性**。

#### 核心原则

1. **输入信号**：父函数将自己的 `CycleAwareSignal` 作为参数传给子函数。子函数收到后直接使用——信号的 `.wire`（硬件线网）和 `cycle`（产生周期）都保持不变。
2. **输出信号**：子函数将内部产生的 `CycleAwareSignal` 通过返回值传回父函数。返回的信号天然携带在子函数中被赋值时的周期信息，父函数可以直接引用。
3. **双模兼容**：每个子函数既可以独立编译（`inputs=None` 时回退到 `m.input()`），也可以被父函数组合调用（`inputs` 传入信号）。

#### 子函数签名规范

```python
def build_xxx(
    m: CycleAwareCircuit,
    domain: CycleAwareDomain,
    *,
    prefix: str = "xxx",
    # 配置参数
    width: int = 64,
    # 显式信号输入（None = 独立模式，回退到 m.input）
    inputs: dict[str, CycleAwareSignal] | None = None,
) -> dict[str, CycleAwareSignal]:
    """模块描述。"""
    _in = inputs or {}
    _out: dict[str, CycleAwareSignal] = {}

    # 双模输入：优先使用传入信号，否则创建独立端口
    a = _in["a"] if "a" in _in else cas(domain, m.input(f"{prefix}_a", width=width), cycle=0)
    b = _in["b"] if "b" in _in else cas(domain, m.input(f"{prefix}_b", width=width), cycle=0)

    # 内部逻辑
    result = a + b                      # result 是 CycleAwareSignal，cycle=0

    domain.next()

    pipe_out_w = domain.cycle(result.wire, name=f"{prefix}_pipe")
    pipe_out = cas(domain, pipe_out_w, cycle=1)  # 现在是 cycle 1

    # 输出：同时写 m.output（独立模式端口）和 _out（组合模式返回值）
    m.output(f"{prefix}_result", pipe_out.wire)
    _out["result"] = pipe_out           # ← CycleAwareSignal, cycle=1

    return _out
```

#### 父函数调用模式

```python
def build_parent(m, domain, *, prefix="parent", width=64,
                 inputs=None):
    _in = inputs or {}
    _out: dict[str, CycleAwareSignal] = {}

    # 父函数自己的 cycle 0 信号
    x = _in["x"] if "x" in _in else cas(domain, m.input(f"{prefix}_x", width=width), cycle=0)

    # 调用子函数 —— 传入 CAS 信号，接收 CAS 信号
    domain.push()
    sub_out = build_xxx(m, domain, prefix=f"{prefix}_sub",
                        width=width,
                        inputs={"a": x, "b": x})
    domain.pop()

    # sub_out["result"] 是 CycleAwareSignal，cycle=1（来自子函数内部）
    # 父函数知道该信号在子函数中产生于 cycle 1
    final = sub_out["result"]           # 直接使用，cycle 信息完整

    m.output(f"{prefix}_final", final.wire)
    _out["final"] = final
    return _out
```

#### Cycle 属性传递详解

```
父函数 cycle 0          子函数（push 后 cycle 重置）         父函数 pop 后
──────────────          ────────────────────────          ──────────────
x (cycle=0)  ─传入→   a = _in["a"]  (cycle=0)
                       ↓ 内部计算
                       result = a + b  (cycle=0)
                       ↓ domain.next()
                       pipe_out  (cycle=1)
                       ↓ 返回
              ←返回──  _out["result"] = pipe_out (cycle=1)
                                                          final (cycle=1)
```

**关键点**：
- 传入的 `CycleAwareSignal` 保留原始 cycle，子函数看到的 cycle 与父函数赋予的一致
- 子函数返回的 `CycleAwareSignal` 携带产生时的 cycle，父函数可据此判断信号的时序位置
- `domain.push()/pop()` 隔离子函数内部的 `domain.next()` 对父函数周期计数的影响，但**不改变信号本身的 cycle 值**

#### 输入信号的双模写法

```python
# ✅ 推荐：dict 查找 + 回退
a = _in["a"] if "a" in _in else cas(domain, m.input(f"{prefix}_a", width=W), cycle=0)

# ❌ 不推荐：用 or（CAS 信号可能为零值，被误判为 falsy）
a = _in.get("a") or cas(domain, m.input(...), cycle=0)
```

#### 输出信号的收集

```python
# 模式 1：输出是 CAS 信号的 .wire
result = mux(cond, a, b)           # CAS 信号
m.output(f"{prefix}_result", result.wire)
_out["result"] = result            # ← 存 CAS 信号（含 cycle）

# 模式 2：输出是流水线寄存器的 wire（来自 domain.cycle）
out_w = domain.cycle(val.wire, name=f"{prefix}_pipe")
out_cas = cas(domain, out_w, cycle=domain.cycle_index)
m.output(f"{prefix}_out", out_w)
_out["out"] = out_cas              # ← 包装成 CAS 再存（含 cycle）
```

#### 完整范例：BPU 调用 ITTAGE

```python
def build_ittage(m, domain, *, prefix="ittage", pc_width=39,
                 inputs=None) -> dict[str, CycleAwareSignal]:
    _in = inputs or {}
    _out = {}

    # 双模输入
    s0_pc = _in["s0_pc"] if "s0_pc" in _in else \
        cas(domain, m.input(f"{prefix}_s0_pc", width=pc_width), cycle=0)
    global_hist = _in["global_hist"] if "global_hist" in _in else \
        cas(domain, m.input(f"{prefix}_global_hist", width=32), cycle=0)

    # ... ITTAGE 内部多表查找逻辑 ...
    # target 在 cycle 1 产生
    domain.next()
    target = cas(domain, target_w, cycle=1)

    m.output(f"{prefix}_target", target.wire)
    _out["target"] = target          # cycle=1

    m.output(f"{prefix}_valid", valid.wire)
    _out["valid"] = valid            # cycle=1

    return _out

def build_bpu(m, domain, *, prefix="bpu", pc_width=39,
              inputs=None) -> dict[str, CycleAwareSignal]:
    _in = inputs or {}
    _out = {}

    # BPU cycle 0：PC 生成
    s0_pc = _in["s0_pc"] if "s0_pc" in _in else \
        cas(domain, m.input(f"{prefix}_s0_pc", width=pc_width), cycle=0)
    global_hist = cas(domain, m.input(f"{prefix}_ghist", width=32), cycle=0)

    # 调用 ITTAGE —— 显式传入 CAS 信号
    domain.push()
    ittage_out = build_ittage(m, domain, prefix=f"{prefix}_ittage",
                              pc_width=pc_width,
                              inputs={
                                  "s0_pc": s0_pc,         # cycle=0, 传入
                                  "global_hist": global_hist,
                              })
    domain.pop()

    # ittage_out["target"] 是 CAS 信号, cycle=1
    # BPU 在 s3 阶段使用它
    s3_target = ittage_out["target"]  # cycle=1，来自 ITTAGE 内部

    _out["pred_target"] = s3_target
    return _out
```

#### 与隐式传递的对比

| 维度 | 显式传递（推荐） | 隐式传递（`m.input`/`m.output`） |
|------|-----------------|-------------------------------|
| **数据流** | 函数参数和返回值，一目了然 | 通过字符串名称间接关联 |
| **Cycle 信息** | CAS 信号天然携带，编译器可校验 | 需要人工确保 cycle 匹配 |
| **类型安全** | IDE 可推断 `dict[str, CAS]` | 字符串 key 无法静态检查 |
| **重构友好** | 改函数签名，编译器/IDE 立刻报错 | 改端口名称，只有运行时才报错 |
| **独立编译** | `inputs=None` 回退到 `m.input()` | 始终可独立编译 |
| **适用场景** | 父子函数间紧耦合信号 | 顶层模块对外端口 |

> **规范总结**：所有 `build_*` 函数应采用 `inputs: dict[str, CycleAwareSignal] | None = None` 参数接收输入信号，返回 `dict[str, CycleAwareSignal]` 传递输出信号。`m.input()`/`m.output()` 仅作为独立编译的回退通道保留。

### 与 m.instance() 的对比

PyCircuit 同时提供 `m.instance()` API 用于结构化子模块例化（生成 MLIR `pyc.instance` op，保留模块边界到 Verilog 输出）。以下对比两种方法：

| 维度 | 子函数调用 | `m.instance()` |
|------|-----------|----------------|
| **代码量** | 一行调用 | 需要显式列举所有端口绑定 |
| **信号传递** | 共享 `m`/`domain`，天然可见 | 端口映射，接口变更需同步改两处 |
| **V5 契合度** | 完美 — `(m, domain)` 贯穿上下文 | 需要 `DesignContext`，打破单 domain 流 |
| **时序叙事** | 保持连续 — `domain.next()` 按顺序推进 | 子模块是黑盒，时序关系不直观 |
| **命名空间** | 需手动前缀管理 | 天然隔离 |
| **Verilog 层次** | 扁平输出，需后处理生成 wrapper | 原生层次化输出 |
| **跨模块优化** | 综合工具可全局优化 | 模块边界可能阻碍优化 |
| **增量编译** | 修改子函数需重编父模块 | 只需重编修改过的子模块 |
| **适用场景** | **系统内部组合**（推荐） | 第三方 IP 核复用 |

> **结论**：对于用 PyCircuit 从头构建的系统，子函数调用是更自然、更高效的层次化手段。`m.instance()` 保留为集成外部 IP 或需要严格模块边界隔离的场景。

---

## 自动周期平衡

PyCircuit 的核心特性之一是自动周期平衡（Automatic Cycle Balancing）。

### 规则

当组合不同周期的信号时：
- **输出周期 ≥ max(输入周期)**
- 如果输入周期 < 输出周期：自动插入 `DFF`（延迟）
- 如果输入周期 > 输出周期：自动插入 `FB`（反馈）
- 如果输入周期 == 输出周期：直接使用

### 示例

```python
# sig_a 在 Cycle 0，sig_b 在 Cycle 2
result = (sig_a & sig_b) | "Combined"
# 输出：result 在 Cycle 2，sig_a 自动延迟 2 个周期
```

生成的描述：
```
result = (DFF(DFF(sig_a)) & sig_b)
  → Cycle balancing: inputs at [0, 2] → output at 2
```

---

## 两种输出模式

### 层次化模式（Hierarchical Mode）

保留模块层次结构，每个模块独立显示：

```
┌────────────────────────────────────────────────────────────────────────────┐
│ MODULE: ParentModule                                                       │
└────────────────────────────────────────────────────────────────────────────┘
  INPUTS:
    • input_signal                           [cycle=0, domain=CLK]
  
  SUBMODULES:
    • ChildModule
      - Inputs: processed
      - Outputs: result
  
  OUTPUTS:
    • output                                 [cycle=2, domain=CLK]
```

### 扁平化模式（Flatten Mode）

展开所有子模块，信号名带模块前缀：

```
┌────────────────────────────────────────────────────────────────────────────┐
│ MODULE: TopLevel                                                           │
└────────────────────────────────────────────────────────────────────────────┘
  SIGNALS:
    ChildModule.internal_sig = ...
    ChildModule.result = ...
    output = ChildModule.result
```

---

## 编程范例

### 范例1：频率分频器（testdivider.py）

这是一个简单的频率分频器，将输入时钟分频为指定倍数。

#### 代码

```python
class FrequencyDivider(pyc_CircuitModule):
    """
    频率分频器模块
    """
    
    def __init__(self, name, divide_by, input_clock_domain):
        super().__init__(name, clock_domain=input_clock_domain)
        self.divide_by = divide_by
        self.counter_bits = (divide_by - 1).bit_length()
        
    def build(self, clk_in):
        """构建分频器电路"""
        with self.module(
            inputs=[clk_in],
            description=f"Frequency Divider: Divide by {self.divide_by}"
        ) as mod:
            # 初始化计数器（Cycle -1：初始化信号）
            counter = signal[f"{self.counter_bits}-1:0"](value=0) | "Counter initial value"
            
            # 计数器逻辑
            counter_next = (counter + 1) | "Counter increment"
            counter_eq = (counter == (self.divide_by - 1)) | f"Counter == {self.divide_by-1}"
            counter_wrap = mux(counter_eq, 0, counter_next) | "Counter wrap-around"
            
            self.clock_domain.next()  # 推进到下一周期
            
            # 更新计数器（反馈）
            counter = counter_wrap | "update counter"
            
            # 输出使能信号
            clk_enable = (counter == (self.divide_by - 1)) | "Clock enable output"
            
            mod.outputs = [clk_enable]
        
        return clk_enable
```

#### 使用方法

```python
def main():
    m = CycleAwareCircuit("divider_top")
    clk_domain = m.create_domain("DIV_CLK", frequency_desc="Divider clock domain")
    clk_domain.create_reset()

    clk_domain.next()
    clk_in = clk_domain.create_signal("clock_in", width=1)

    divider = FrequencyDivider("Divider13", 13, clk_domain)
    clk_enable = divider.build(clk_in)
```

#### 生成的电路描述

**层次化模式（hier_testdivider.txt）：**

```
================================================================================
CIRCUIT DESCRIPTION (HIERARCHICAL MODE)
================================================================================

┌────────────────────────────────────────────────────────────────────────────┐
│ MODULE: Divider13                                                          │
│ Frequency Divider: Divide by 13                                           │
└────────────────────────────────────────────────────────────────────────────┘

  INPUTS:
    • clock_in                                 [cycle=-1, domain=DIV_CLK]

  SIGNALS:

    ──────────────────────────────────────────────────────────────────────
    CYCLE -1
    ──────────────────────────────────────────────────────────────────────

    counter = forward_declare("Counter initial value")
      // Counter initial value


    ──────────────────────────────────────────────────────────────────────
    CYCLE 1
    ──────────────────────────────────────────────────────────────────────

    counter_next = (counter + 1)
      // Counter increment
      → Cycle balancing: inputs at [-1] → output at 1

    counter_eq = (counter == (self.divide_by - 1))
      // Counter == 12
      → Cycle balancing: inputs at [-1] → output at 1

    counter_wrap = mux(counter_eq, 0, counter_next)
      // Counter wrap-around (mux)


    ──────────────────────────────────────────────────────────────────────
    CYCLE 2
    ──────────────────────────────────────────────────────────────────────

    counter = counter_wrap
      // Feedback: update counter
      → Cycle balancing: inputs at [1] → output at 2

    clk_enable = (counter == (self.divide_by - 1))
      // Clock enable output

  OUTPUTS:
    • clk_enable                               [cycle=2, domain=DIV_CLK]
```

#### 电路图

![Hierarchical Divider](hier_testdivider.pdf)

![Flatten Divider](flat_testdivider.pdf)

---

### 范例2：实时时钟系统（testproject.py）

这是一个完整的实时时钟系统，包含：
- 高频振荡器时钟域
- 频率分频器（1024分频）
- 带 SET/PLUS/MINUS 按钮的实时时钟

#### 多时钟域示例

```python
# 创建两个独立的时钟域（同一顶层电路下）
m = CycleAwareCircuit("rtc_system")
osc_domain = m.create_domain("OSC_CLK", frequency_desc="High-frequency oscillator domain")
rtc_domain = m.create_domain("RTC_CLK", frequency_desc="1Hz RTC domain")

osc_rst = osc_domain.create_reset()
rtc_rst = rtc_domain.create_reset()
```

#### 实时时钟模块

```python
class RealTimeClock(pyc_CircuitModule):
    """带按钮控制的实时时钟"""
    
    STATE_RUNNING = 0
    STATE_SETTING_HOUR = 1
    STATE_SETTING_MINUTE = 2
    STATE_SETTING_SECOND = 3
    
    def __init__(self, name, rtc_clock_domain):
        super().__init__(name, clock_domain=rtc_clock_domain)
        
    def build(self, clk_enable, set_btn, plus_btn, minus_btn):
        with self.module(
            inputs=[clk_enable, set_btn, plus_btn, minus_btn],
            description="Real-Time Clock with SET/PLUS/MINUS control"
        ) as mod:
            # 初始化时间计数器
            sec = signal[5:0](value=0) | "Seconds"
            min = signal[5:0](value=0) | "Minutes"
            hr = signal[4:0](value=0) | "Hours"
            state = signal[1:0](value=self.STATE_RUNNING) | "State"
            
            self.clock_domain.next()
            
            # 状态机逻辑
            state_is_running = (state == self.STATE_RUNNING) | "Check RUNNING"
            # ... 更多逻辑 ...
            
            self.clock_domain.next()
            
            # 寄存时间值
            seconds_out = self.clock_domain.cycle(sec_next, reset_value=0)
            minutes_out = self.clock_domain.cycle(min_next, reset_value=0)
            hours_out = self.clock_domain.cycle(hr_next, reset_value=0)
            
            mod.outputs = [seconds_out, minutes_out, hours_out, state]
```

#### 生成的电路描述

**层次化模式部分输出（hier_circuit.txt）：**

```
┌────────────────────────────────────────────────────────────────────────────┐
│ MODULE: FreqDiv1024                                                        │
│ Frequency Divider: Divide by 1024                                         │
└────────────────────────────────────────────────────────────────────────────┘

  INPUTS:
    • oscillator_in                            [cycle=-1, domain=OSC_CLK]

  SIGNALS:
    ...

  OUTPUTS:
    • clk_enable                               [cycle=3, domain=OSC_CLK]


┌────────────────────────────────────────────────────────────────────────────┐
│ MODULE: RTC                                                                │
│ Real-Time Clock with SET/PLUS/MINUS control buttons                       │
└────────────────────────────────────────────────────────────────────────────┘

  INPUTS:
    • clk_enable                               [cycle=3, domain=OSC_CLK]
    • SET_btn                                  [cycle=-1, domain=RTC_CLK]
    • PLUS_btn                                 [cycle=-1, domain=RTC_CLK]
    • MINUS_btn                                [cycle=-1, domain=RTC_CLK]
    ...
```

#### 电路图

**频率分频器模块：**

![FreqDiv1024](hier_FreqDiv1024.pdf)

**实时时钟模块：**

![RTC](hier_RTC.pdf)

**扁平化模式完整电路：**

![Flatten Circuit](flat_circuit_diagram.pdf)

---

### 范例3：RISC-V CPU（riscv.py）

这是一个完整的 RISC-V CPU 实现，展示了 PyCircuit 处理复杂层次化设计的能力。

#### CPU 结构

```
RISCVCpu
├── InstructionDecoder  (指令解码器)
├── RegisterFile        (寄存器文件)
├── ALU                 (算术逻辑单元)
└── ExceptionHandler    (异常处理器)
```

#### 5 级流水线实现

```python
class RISCVCpu(pyc_CircuitModule):
    def build(self, instruction_mem_data, data_mem_data, interrupt_req):
        with self.module(inputs=[...]) as mod:
            # ========== STAGE 1: INSTRUCTION FETCH ==========
            pc = signal[31:0](value=0) | "Program Counter"
            
            self.clock_domain.next()  # Cycle 1
            pc_next = pc + 4 | "PC + 4"
            instruction = instruction_mem_data | "Fetched instruction"
            
            # ========== STAGE 2: INSTRUCTION DECODE ==========
            self.clock_domain.next()  # Cycle 2
            instruction_reg = self.clock_domain.cycle(instruction)
            
            # 实例化解码器子模块
            decoder = InstructionDecoder("Decoder", self.clock_domain)
            (opcode, funct3, ...) = decoder.build(instruction_reg)
            
            # 实例化寄存器文件
            reg_file = RegisterFile("RegFile", self.clock_domain)
            rs1_data, rs2_data = reg_file.build(rs1, rs2, ...)
            
            # ========== STAGE 3: EXECUTE ==========
            self.clock_domain.next()  # Cycle 3
            
            # 实例化 ALU
            alu = ALU("ALU", self.clock_domain)
            alu_result, zero_flag, lt_flag = alu.build(...)
            
            # ========== STAGE 4: MEMORY ACCESS ==========
            self.clock_domain.next()  # Cycle 4
            
            # 异常处理
            exc_handler = ExceptionHandler("ExceptionHandler", self.clock_domain)
            exception_valid, exception_code, ... = exc_handler.build(...)
            
            # ========== STAGE 5: WRITE BACK ==========
            self.clock_domain.next()  # Cycle 5
            
            wb_data = mux(mem_read_wb, mem_data_wb, alu_result_wb) | "Write-back data"
```

#### 子模块示例：ALU

```python
class ALU(pyc_CircuitModule):
    """算术逻辑单元"""
    
    ALU_ADD = 0
    ALU_SUB = 1
    ALU_AND = 2
    # ... 更多操作码
    
    def build(self, operand_a, operand_b, alu_op):
        with self.module(inputs=[operand_a, operand_b, alu_op]) as mod:
            # 算术运算
            add_result = (operand_a + operand_b) | "ALU ADD"
            sub_result = (operand_a - operand_b) | "ALU SUB"
            
            # 逻辑运算
            and_result = (operand_a & operand_b) | "ALU AND"
            or_result = (operand_a | operand_b) | "ALU OR"
            
            # 使用 mux 链选择结果
            result = mux(alu_op == self.ALU_SUB, sub_result, add_result)
            result = mux(alu_op == self.ALU_AND, and_result, result)
            # ...
            
            mod.outputs = [result, zero_flag, lt_flag]
```

#### 生成的电路描述

**层次化模式（hier_riscv.txt）部分：**

```
┌────────────────────────────────────────────────────────────────────────────┐
│ MODULE: RISCVCpu                                                           │
│ RISC-V CPU: 5-stage pipeline with precise exception handling              │
└────────────────────────────────────────────────────────────────────────────┘

  INPUTS:
    • instruction_mem_data                     [cycle=-1, domain=CPU_CLK]
    • data_mem_data                            [cycle=-1, domain=CPU_CLK]
    • interrupt_req                            [cycle=-1, domain=CPU_CLK]

  SUBMODULES:
    • Decoder
    • RegFile
    • ALU
    • ExceptionHandler

  OUTPUTS:
    • pc                                       [cycle=6, domain=CPU_CLK]
    • instruction_mem_addr                     [cycle=6, domain=CPU_CLK]
    ...
```

#### 电路图

**RISC-V CPU 顶层模块（层次化）：**

![RISC-V CPU](hier_riscv_RISCVCpu.pdf)

**指令解码器模块：**

![Decoder](hier_riscv_Decoder.pdf)

**寄存器文件模块：**

![RegFile](hier_riscv_RegFile.pdf)

**ALU 模块：**

![ALU](hier_riscv_ALU.pdf)

**扁平化模式完整 CPU：**

![Flatten RISC-V](flat_riscv_RISCVCpu.pdf)

---

### 范例4：SoC 层次化集成（函数式风格）

这个范例展示如何用函数调用方式构建一个简化的 SoC，体现层次关系：

```
SoC Top
├── CPU Core
│   ├── Frontend (fetch + decode)
│   └── Backend (execute + writeback)
├── Memory Controller
└── UART Peripheral
```

#### 叶子模块：Frontend

```python
from pycircuit import (
    CycleAwareCircuit, CycleAwareDomain, cas,
    compile_cycle_aware, mux, u,
)

def build_frontend(m, domain, *, pc_width=32, inst_width=32, prefix="fe"):
    """Frontend: 2-stage fetch + decode pipeline."""

    # ── Cycle 0: Fetch ──
    redirect_valid  = cas(domain, m.input(f"{prefix}_redirect_valid", width=1), cycle=0)
    redirect_target = cas(domain, m.input(f"{prefix}_redirect_target", width=pc_width), cycle=0)

    pc_r = domain.state(width=pc_width, reset_value=0, name=f"{prefix}_pc")
    pc   = cas(domain, pc_r.wire, cycle=0)

    FOUR = cas(domain, m.const(4, width=pc_width), cycle=0)
    next_pc = mux(redirect_valid, redirect_target, pc.wire + FOUR.wire)

    inst_mem_data = cas(domain, m.input(f"{prefix}_imem_data", width=inst_width), cycle=0)
    m.output(f"{prefix}_imem_addr", pc.wire)

    s1_pc_w   = domain.cycle(pc.wire, name=f"{prefix}_s1_pc")
    s1_inst_w = domain.cycle(inst_mem_data.wire, name=f"{prefix}_s1_inst")
    domain.next()

    # ── Cycle 1: Decode ──
    opcode = s1_inst_w[0:7]
    rd     = s1_inst_w[7:12]
    rs1    = s1_inst_w[15:20]
    rs2    = s1_inst_w[20:25]

    m.output(f"{prefix}_dec_valid", cas(domain, m.const(1, width=1), cycle=0).wire)
    m.output(f"{prefix}_dec_opcode", opcode)
    m.output(f"{prefix}_dec_rd", rd)
    m.output(f"{prefix}_dec_rs1", rs1)
    m.output(f"{prefix}_dec_rs2", rs2)
    m.output(f"{prefix}_dec_pc", s1_pc_w)

    # 状态更新
    domain.next()
    pc_r.set(next_pc)

    return s1_pc_w, opcode, rd, rs1, rs2
```

#### 叶子模块：Backend

```python
def build_backend(m, domain, *, data_width=32, prefix="be"):
    """Backend: execute + writeback (simplified)."""

    op_a   = cas(domain, m.input(f"{prefix}_op_a", width=data_width), cycle=0)
    op_b   = cas(domain, m.input(f"{prefix}_op_b", width=data_width), cycle=0)
    alu_op = cas(domain, m.input(f"{prefix}_alu_op", width=4), cycle=0)

    ZERO4 = cas(domain, m.const(0, width=4), cycle=0)
    ONE4  = cas(domain, m.const(1, width=4), cycle=0)

    add_r = op_a.wire + op_b.wire
    sub_r = op_a.wire - op_b.wire
    result = mux(alu_op.wire == ONE4.wire, sub_r, add_r)

    wb_data_w = domain.cycle(result[0:data_width], name=f"{prefix}_wb_data")
    domain.next()

    m.output(f"{prefix}_wb_data", wb_data_w)
    m.output(f"{prefix}_wb_valid", cas(domain, m.const(1, width=1), cycle=0).wire)

    return wb_data_w
```

#### 中间层：CPU Core（组合 Frontend + Backend）

```python
def build_cpu_core(m, domain, *, data_width=32, pc_width=32, prefix="cpu"):
    """CPU Core = Frontend + Backend，通过子函数调用组合。"""

    # Frontend: fetch + decode (cycle 0 → 1)
    domain.push()
    pc, opcode, rd, rs1, rs2 = build_frontend(
        m, domain, pc_width=pc_width, prefix=f"{prefix}_fe")
    domain.pop()

    # Backend: execute + writeback (独立周期)
    domain.push()
    wb_data = build_backend(
        m, domain, data_width=data_width, prefix=f"{prefix}_be")
    domain.pop()

    m.output(f"{prefix}_commit_pc", pc)
```

#### 顶层：SoC（组合 CPU + Memory + UART）

```python
def build_uart(m, domain, *, prefix="uart"):
    """UART peripheral stub."""
    tx_data = cas(domain, m.input(f"{prefix}_tx_data", width=8), cycle=0)
    tx_valid = cas(domain, m.input(f"{prefix}_tx_valid", width=1), cycle=0)
    busy_r = domain.state(width=1, reset_value=0, name=f"{prefix}_busy")
    m.output(f"{prefix}_tx_ready", ~cas(domain, busy_r.wire, cycle=0).wire)

def build_soc_top(m, domain, *, data_width=32, pc_width=32):
    """SoC Top: CPU Core + Memory Controller + UART"""

    # ── CPU Core ──
    build_cpu_core(m, domain,
                   data_width=data_width, pc_width=pc_width, prefix="cpu")

    # ── Memory Controller ──
    build_mem_ctrl(m, domain, data_width=data_width, prefix="memctrl")

    # ── UART ──
    build_uart(m, domain, prefix="uart")

build_soc_top.__pycircuit_name__ = "soc_top"

if __name__ == "__main__":
    ir = compile_cycle_aware(
        build_soc_top, name="soc_top", eager=True,
        data_width=32, pc_width=32,
    )
    print(ir.emit_mlir())
```

#### 设计要点

1. **层次清晰**：`build_soc_top` → `build_cpu_core` → `build_frontend` / `build_backend`，函数调用链即设计层次
2. **周期管理**：`push()/pop()` 确保各子系统周期独立，不互相干扰
3. **命名隔离**：前缀 `cpu_fe_*` / `cpu_be_*` / `uart_*` 避免端口冲突
4. **灵活参数化**：`data_width` / `pc_width` 通过 Python 函数参数传递，可全局配置
5. **渐进开发**：每个 `build_*` 可以独立 `compile_cycle_aware(build_frontend, ...)` 编译和测试

---

## 生成的电路图

**Obsoleted**：下文所述基于 **`pyVisualize`** 的 PDF/PNG 流程已废弃，仓库内不再提供该依赖。历史示例中的示意图文件名仍可作为概念参考；当前请以 **`CycleAwareCircuit.emit_mlir()`**、仿真波形或外部综合工具为准。

### ~~使用方法~~（已废弃）

```python
# Obsoleted — do not use as a supported workflow
# from pyVisualize import visualize_circuit
# visualize_circuit(logger, ...)
```

### 输出文件列表（历史参考）

| 文件名 | 说明 |
|--------|------|
| `hier_testdivider.txt` | 分频器层次化描述 |
| `flat_testdivider.txt` | 分频器扁平化描述 |
| `hier_testdivider.pdf` | 分频器层次化电路图 |
| `flat_testdivider.pdf` | 分频器扁平化电路图 |
| `hier_circuit.txt` | RTC系统层次化描述 |
| `flat_circuit.txt` | RTC系统扁平化描述 |
| `hier_FreqDiv1024.pdf` | 频率分频器电路图 |
| `hier_RTC.pdf` | 实时时钟电路图 |
| `hier_riscv.txt` | RISC-V CPU 层次化描述 |
| `flat_riscv.txt` | RISC-V CPU 扁平化描述 |
| `hier_riscv_*.pdf` | 各模块层次化电路图 |
| `flat_riscv_*.pdf` | 扁平化电路图 |

---

## 最佳实践

### 1. 模块设计原则

**函数式风格（推荐）：**

```python
def build_my_module(m, domain, *, data_width=32, prefix="mod"):
    """模块签名：(m, domain, *, 参数...) -> 返回值（可选）"""
    inp = cas(domain, m.input(f"{prefix}_data_in", width=data_width), cycle=0)

    acc_r = domain.state(width=data_width, reset_value=0, name=f"{prefix}_acc")
    acc = cas(domain, acc_r.wire, cycle=0)
    acc_next = acc.wire + inp.wire

    m.output(f"{prefix}_result", acc_next[0:data_width])

    domain.next()
    acc_r.set(acc_next)

build_my_module.__pycircuit_name__ = "my_module"
```

**类式风格（适合独立 IP）：**

```python
class GoodModule(pyc_CircuitModule):
    def __init__(self, name, clock_domain, param1, param2):
        super().__init__(name, clock_domain=clock_domain)
        self.param1 = param1
        self.param2 = param2

    def build(self, input1, input2):
        with self.module(
            inputs=[input1, input2],
            description=f"Module with param1={self.param1}"
        ) as mod:
            result = ...
            mod.outputs = [result]
        return result
```

### 2. 信号命名规范

```python
# ✓ 函数式风格：用前缀避免冲突
addr = cas(domain, m.input(f"{prefix}_addr", width=32), cycle=0)
valid_r = domain.state(width=1, reset_value=0, name=f"{prefix}_valid")
s1_data_w = domain.cycle(data.wire, name=f"{prefix}_s1_data")

# ✓ 类式风格：用描述辅助调试
counter_next = (counter + 1) | "Counter next value"
data_valid_reg = self.clock_domain.cycle(data_valid) | "Registered valid"

# ✗ 避免
x = (a + b) | "Some signal"
temp = result | ""
```

### 3. 周期管理

```python
# ✓ 明确标记周期边界
domain.next()  # Cycle N -> N+1

# ✓ 使用 cycle() 创建流水线寄存器
registered_data = domain.cycle(data.wire, reset_value=0, name="reg_data")

# ✓ 使用 state() 创建反馈寄存器
counter_r = domain.state(width=8, reset_value=0, name="counter")
# ... 在后续周期中 ...
counter_r.set(counter_next)

# ✓ 理解自动周期平衡
# 当组合不同周期的信号时，系统会自动插入延迟
```

### 4. 层次化设计

**推荐：子函数调用（函数式风格）**

```python
def build_soc(m, domain, *, data_width=32):
    # 子系统通过函数调用组合，前缀隔离命名空间
    build_cpu_core(m, domain, data_width=data_width, prefix="cpu")
    build_mem_ctrl(m, domain, data_width=data_width, prefix="memctrl")
    build_uart(m, domain, prefix="uart")
```

**适用原则：**
- 系统内部子模块 → 子函数调用（简洁、灵活）
- 独立子系统需要周期隔离 → `domain.push()` / `domain.pop()`
- 流水线各级按顺序 → 子函数延续 `domain.next()`
- 第三方 IP 核 → `m.instance()`

**类式风格（向后兼容）：**

```python
class TopLevel(pyc_CircuitModule):
    def build(self, ...):
        with self.module(...) as mod:
            decoder = Decoder("decoder", self.clock_domain)
            alu = ALU("alu", self.clock_domain)
            decoded = decoder.build(instruction)
            result = alu.build(op_a, op_b, alu_op)
```

### 5. 调试技巧

```python
# 单独编译子模块进行隔离测试
if __name__ == "__main__":
    ir = compile_cycle_aware(build_frontend, name="frontend", eager=True,
                             pc_width=16, inst_width=32, prefix="fe")
    print(ir.emit_mlir())

# 检查 MLIR 输出确认：
#   - 信号名和位宽是否正确
#   - 寄存器和反馈环路是否如预期
# 检查 Verilog 输出确认：
#   - 端口列表、模块名是否正确
#   - 综合结果是否通过
```

### 6. 大型项目组织

```
designs/my_soc/
├── top/
│   ├── parameters.py        # 全局参数（位宽、深度等）
│   ├── soc_top.py           # build_soc_top：顶层
│   └── cpu_core.py          # build_cpu_core：中间层
├── frontend/
│   ├── frontend.py          # build_frontend
│   ├── bpu/
│   │   └── bpu.py           # build_bpu
│   └── icache/
│       └── icache.py        # build_icache
├── backend/
│   ├── backend.py           # build_backend
│   └── ctrlblock/
│       └── ctrlblock.py     # build_ctrlblock
├── tests/
│   ├── test_bpu.py          # 单独编译测试 BPU
│   ├── test_frontend.py     # 单独编译测试 Frontend
│   └── test_integration.py  # 集成测试
└── build_verilog.py          # 构建脚本
```

**原则：**
- 每个 `build_*` 函数独占一个文件，文件名 = 模块名
- 全局参数集中在 `parameters.py`，通过 `from top.parameters import *` 引入
- 每个 `build_*` 可独立 `compile_cycle_aware(...)` 编译测试
- 构建脚本负责批量编译 + Verilog 层次化组装

---

## 附录：API 参考

### CycleAwareCircuit（V5 顶层电路）

| 方法 | 说明 |
|------|------|
| `CycleAwareCircuit(name)` | 创建顶层电路对象 |
| `create_domain(name, ...)` | 创建时钟域，返回 `CycleAwareDomain` |
| `input(name, *, width)` | 声明输入端口 |
| `output(name, signal)` | 声明输出端口 |
| `const(value, *, width)` | 创建常量信号 |
| `emit_mlir()` | 导出 MLIR 文本 |

### CycleAwareDomain（`pyc_ClockDomain` 为其别名）

| 方法 | 说明 |
|------|------|
| （构造） | 由 `CycleAwareCircuit.create_domain(...)` 创建，勿直接 `pyc_ClockDomain(...)` |
| `create_reset()` | 返回 **i1** `Wire`（**1** = 复位有效），经 `pyc.reset_active` 从 `!pyc.reset` 端口导出，可用于 `mux` |
| `create_signal(name, *, width)` | 创建输入端口；`width` 关键字必选 |
| `create_const(value, *, width, name="")` | 常量 |
| `state(*, width, reset_value=0, name="")` | 反馈寄存器（`StateSignal`），需在后续周期调用 `.set(value)` |
| `next()` / `prev()` | 推进 / 回退逻辑 occurrence 周期 |
| `push()` / `pop()` | 周期栈（需配对）；子函数用于隔离内部周期操作 |
| `cycle(sig, reset_value=None, name="")` | 单级寄存器，返回 `q` 的 `Wire` |

### compile_cycle_aware（V5 编译入口）

```python
ir = compile_cycle_aware(
    build_fn,          # build_*(m, domain, ...) 函数
    name="module_name",
    eager=True,        # True: 立即编译; False: JIT 延迟编译
    **kwargs,          # 传递给 build_fn 的关键字参数
)
ir.emit_mlir()         # 导出 MLIR
```

### cas（创建 cycle-aware 信号）

```python
sig = cas(domain, wire_or_input, cycle=0)
# 将一个 Wire 对象包装为带周期信息的 CycleAwareSignal
# cycle=0 表示当前周期，cycle=N 表示第 N 个周期
```

### mux（多路选择器）

```python
result = mux(condition, true_value, false_value)
# condition: 1-bit 信号
# 自动对齐 condition / true / false 的周期
```

### pyc_CircuitModule（类式风格）

| 方法 | 说明 |
|------|------|
| `__init__(name, clock_domain)` | 初始化模块 |
| `module(inputs, description)` | 模块上下文管理器 |
| `build(...)` | 构建模块逻辑（需重写） |

### pyc_CircuitLogger

| 方法 | 说明 |
|------|------|
| `__init__(filename, is_flatten)` | 创建日志器 |
| `write_to_file()` | 写入电路描述文件 |
| `reset()` | 重置日志器状态 |

### 全局函数

| 函数 | 说明 |
|------|------|
| `signal[high:low](value=...)` | 创建信号（类式风格） |
| `mux(condition, true_val, false_val)` | 多路选择器 |
| `cas(domain, wire, cycle=N)` | 创建 cycle-aware 信号（函数式风格） |
| `u(value, width)` | 无符号字面量 |
| `log(signal)` | 记录信号（用于调试） |

---

**Copyright © 2024-2026 Liao Heng. All rights reserved.**

