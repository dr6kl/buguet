import os

def exec_cmd(cmd):
    print(f"Running: {cmd}")
    status = os.system(cmd)
    if status != 0:
        raise Exception(f"Command failed with status {status}: {cmd}")

VERSIONS = []
for i in range(10, 26):
    VERSIONS.append("0.4." + str(i))
for i in range(0, 10):
    VERSIONS.append("0.5." + str(i))

SOLC_ROOT = os.path.abspath("tests/solc")

def prepare_solc():
    if not os.path.exists(SOLC_ROOT):
        os.mkdir(SOLC_ROOT)

    for ver in VERSIONS:
        ver_dir = os.path.join(SOLC_ROOT, ver)
        if not os.path.exists(ver_dir):
            os.mkdir(ver_dir)
            solc_file = os.path.join(ver_dir, "solc")
            if ver == "0.4.10":
                fname =  "solc"
            else:
                fname = "solc-static-linux"
            url = f"https://github.com/ethereum/solidity/releases/download/v{ver}/{fname}"
            exec_cmd(f"wget -O {solc_file} {url}")
            exec_cmd(f"chmod +x {solc_file}")

def run_tests():
    for ver in VERSIONS:
        ver_dir = os.path.join(SOLC_ROOT, ver)
        solc_file = os.path.join(ver_dir, "solc")
        ver_major = ver.split(".")[1]
        exec_cmd(f"cd examples && SOLC_PATH={solc_file} SOLC_VER={ver_major} python deploy.py")
        exec_cmd(f"python -m unittest tests.debugger_test.TestDebugger")

prepare_solc()
run_tests()
