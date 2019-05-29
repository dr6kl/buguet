from termcolor import colored
from buguet.models import Breakpoint

class Repl:
    def __init__(self, debugger):
        self.debugger = debugger

    def repl(self):
        self.print_lines()
        while not self.debugger.is_ended():
            line = input("Command: ")
            if line == "next" or line == "n":
                self.debugger.next()
                if not self.debugger.is_ended():
                    self.print_lines()
            elif line == "step" or line == "s":
                self.debugger.step()
                if not self.debugger.is_ended():
                    self.print_lines()
            elif line == "stepout" or line == "so":
                self.debugger.stepout()
                if not self.debugger.is_ended():
                    self.print_lines()
            elif line == "continue" or line == "c":
                self.debugger.continu()
                if not self.debugger.is_ended():
                    self.print_lines()
            elif line == "stack" or line == "st":
                self.print_stack()
            elif line == "memory" or line == "mem":
                self.print_memory()
            elif str.startswith(line, "break "):
                bp = self.parse_breakpoint(line.split(" ")[1])
                if bp:
                    bp = self.debugger.add_breakpoint(bp)
                    if bp:
                        print(f"Breakpoint is set at {bp.src}:{bp.line}")
                    else:
                        print(f"Breakpoint is not set. Location is not found.")
                else:
                    print("Breakpoint is invalid. Specify in format file:line")
            elif str.startswith(line, "breakpoints"):
                for i, bp in enumerate(self.debugger.breakpoints):
                    print(f"[{i}] {bp.src}:{bp.line}")
            elif str.startswith(line, "unbreak "):
                arr = line.split(" ")
                if len(arr) == 2:
                    try:
                        num = int(arr[1])
                        if num < len(self.debugger.breakpoints) and num >= 0:
                            self.debugger.breakpoints.pop(num)
                    except ValueError:
                        pass
            elif line == "op":
                self.print_op()
                self.debugger.advance()
                if not self.debugger.is_ended():
                    self.print_lines()
            else:
                print(self.debugger.eval(line))

    def show_lines(self, n = 3):
        src_frag = self.debugger.current_src_fragment()
        if (src_frag.file_idx == -1):
            return []
        line_num = self.debugger.current_line_number()

        res = []
        for i in range(line_num - n, line_num + n + 1):
            if i >= 0  and i < len(self.debugger.current_source()):
                line = self.debugger.current_source()[i]

                offset = self.debugger.current_contract().source_offsets[src_frag.file_idx][i]
                start = src_frag.start - offset
                end = src_frag.start - offset + src_frag.length
                if start >= 0 and end <= len(line):
                    line = str(line[0:start], "utf8") + colored(str(line[start:end], "utf8"), 'red') + str(line[end:len(line)],"utf8")
                elif start >= 0 and start < len(line):
                    line = str(line[0:start], "utf8") + colored(str(line[start:len(line)], "utf8"), 'red')
                elif end > 0 and end <= len(line):
                    line = colored(str(line[0:end], "utf8"), 'red') + str(line[end:len(line)], "utf8")
                elif start < 0 and end > len(line):
                    line = colored(str(line, "utf8"), 'red')
                else:
                    line = str(line, "utf8")

                res.append([i + 1, line])
        return res

    def print_lines(self, n = 3):
        lines = self.show_lines(n)
        print()
        path = self.debugger.current_contract().source_list[self.debugger.current_src_fragment().file_idx]
        print(colored(self.debugger.current_contract_address(), "blue") + "#" + colored(path, "green"))
        for i, line in enumerate(lines):
            if len(lines) // 2 == i:
                print(" => ", end='')
            else:
                print("    ", end='')
            print(":" + str(line[0]) + ' ', end='')
            print(line[1])

    def parse_breakpoint(self, bp):
        arr = bp.split(":")
        if len(arr) != 2:
            return
        try:
            filename, line = arr[0], int(arr[1])
            return Breakpoint(filename, line)
        except ValueError:
            return

    def print_stack(self):
        stack = self.debugger.tracer.get_all_stack(self.debugger.position)
        for i, x in enumerate(reversed(stack)):
            print(x.hex())
            if (len(stack) - i - 1) in self.debugger.bp_stack:
                print()
        print("-----------")
        print("\n")

    def print_memory(self):
        mem = self.debugger.tracer.get_all_memory(self.debugger.position)
        for i, w in enumerate(mem):
            print(hex(i * 32) + ': ' + w)
        print("-----------")
        print("\n")

    def print_op(self):
        op = self.debugger.current_op()
        frag = self.debugger.current_src_fragment()
        print(op['op'], end = '')
        if op.get('arg'):
            print(' ' + int(op['arg']).to_bytes(32, 'big').hex(), end = '')
        if frag.jump != '-':
            print(' ' + frag.jump, end = '')
        print()

