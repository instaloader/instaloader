import hashlib
import os
import re
import shutil
import subprocess
import sys

# copy the required files into repo root
shutil.copy('docs/favicon.ico', '.')
shutil.copy('deploy/windows/instaloader.spec', '.')
shutil.unpack_archive('deploy/windows/ps', '.', 'xztar')

code = """
import psutil
import subprocess

def __main():
    grandparentpid = psutil.Process(os.getppid()).ppid()
    grandparentpidsearchstring = ' ' + str(grandparentpid) + ' '
    if hasattr(sys, "_MEIPASS"):
        ps = os.path.join(sys._MEIPASS, 'tasklist.exe')
    else:
        ps = 'tasklist'
    popen = subprocess.Popen(ps, stdout=subprocess.PIPE, universal_newlines=True)
    for examine in iter(popen.stdout.readline, ""):
        if grandparentpidsearchstring in examine:
            pname = examine
            break
    popen.stdout.close()
    return_code = popen.wait()
    if return_code:
        raise subprocess.CalledProcessError(return_code, ps)
    if pname[0:12] == 'explorer.exe':
        subprocess.Popen("cmd /K \\\"{0}\\\"".format(os.path.splitext(os.path.basename(sys.argv[0]))[0]))
    else:
        main()


if __name__ == "__main__":
    __main()
"""

with open('instaloader/__main__.py', 'r') as f:
    # adjust imports for changed file structure
    regex = re.compile(r'from (?:(\.[^ ]+ )|\.( ))import')
    lines = [regex.sub(r'from instaloader\1\2import', line) for line in f.readlines()]

    # insert code for magic exe behavior
    index = lines.index('if __name__ == "__main__":\n')
    code_lines = [cl + '\n' for cl in code.splitlines()]
    for i, code_line in enumerate(code_lines):
        if i + index < len(lines):
            lines[i + index] = code_line
        else:
            lines.extend(code_lines[i:])
            break

with open('__main__.py', 'w+') as f:
    f.writelines(lines)

# install dependencies and invoke PyInstaller
commands = ["pip install pipenv==2018.11.26",
            "pipenv sync --dev",
            "pipenv run pyinstaller --log-level=DEBUG instaloader.spec"]

for command in commands:
    print()
    print('#' * (len(command) + 6))
    print('## {} ##'.format(command))
    print('#' * (len(command) + 6))
    print(flush=True)
    err = subprocess.Popen(command).wait()
    if err != 0:
        sys.exit(err)

# calculate and store MD5 hash for created executable
hash_md5 = hashlib.md5()
with open('dist/instaloader.exe', 'rb') as f:
    for chunk in iter(lambda: f.read(4096), b''):
        hash_md5.update(chunk)

with open('dist/instaloader.exe.md5', 'w+') as f:
    f.write('{} *instaloader.exe\n'.format(hash_md5.hexdigest()))

# Create ZIP file
shutil.make_archive('instaloader-{}-windows-standalone'.format(os.getenv('VERSION_TAG')), 'zip', 'dist')
