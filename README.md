# Buguet

Ethereum Debugger (for smart contracts in Solidity).

### Prerequisites

python3

Ethereum node running in archive mode with debug api. E.g. geth:
```
  geth --rpc --rpcapi eth,debug --gcmode archive
```
By default localhost:8545 endpoint is used.

Compiled contracts in format produced by `solc` with `--combined-json` option.
Each contract called in transaction should be compiled with the same solidity
version as it deployed on the blockchain (multiple versions can be used for one transaction).

### Installation

```
pip install buguet
```

### Usage

Basic usage is:
```
buguet contract1.json,contract2.json transaction_id
```
See ```buguet --help``` for all options.

### Commands
```
    help (h)                Print help
    step (s)                Step into function
    next (n)                Next line in current frame
    stepout (so)            Step out of current function
    continue (c)            Continue execution
    break {file}:{line}     Set breakpoint
    breakpoints             List breakpoints
    unbreak {idx}           Remove breakpoint
    stack                   Print current stack
    mem                     Print memory
    op                      Print and execute one instruction
    {expr}                  Evaluate expression
```

