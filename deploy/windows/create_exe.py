import hashlib
import os
import re
import shutil
import subprocess
import sys

# copy the required files into repo root
shutil.copy('docs/favicon.ico', '.')
shutil.copy('deploy/windows/instaloader.spec', '.')

code = """
import contextlib
import psutil
import subprocess

def __main():
    with contextlib.suppress(AttributeError, psutil.Error):
        if psutil.Process().parent().parent().name() == "explorer.exe":
            subprocess.Popen("powershell -NoExit -Command \\\"& '{0}'\\\"".format(sys.argv[0]))
            return
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
commands = ["pip install pipenv==2020.11.15",
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
