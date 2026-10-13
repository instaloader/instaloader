import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import urllib.request

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

# packages bundled into the executable, whose licenses have to be shipped along with it
with open('Pipfile.lock') as f:
    locked_packages = json.load(f)['default']
bundled_packages = ' '.join(list(locked_packages) + ['psutil', 'pyinstaller'])
os.makedirs('dist/licenses', exist_ok=True)

# install dependencies, invoke PyInstaller and collect licenses
commands = ["pip install pipenv==2026.8.0",
            f"pipenv --python {sys.version_info.major}.{sys.version_info.minor} sync --dev",
            "pipenv run pyinstaller --log-level=DEBUG instaloader.spec",
            f"pipenv run pip-licenses --packages {bundled_packages} --with-license-file "
            "--with-notice-file --no-license-path --format=plain-vertical --output-file dist/licenses/third-party.txt"]

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

# include the remaining license texts
shutil.copy('LICENSE', 'dist/LICENSE.txt')
shutil.copy('deploy/windows/NOTICE.txt', 'dist/licenses/NOTICE.txt')
shutil.copy('deploy/windows/GPL-3.0.txt', 'dist/licenses/GPL-3.0.txt')
shutil.copy(os.path.join(sys.base_prefix, 'LICENSE.txt'), 'dist/licenses/Python.txt')
urllib.request.urlretrieve('https://raw.githubusercontent.com/python/cpython/v{}/Doc/license.rst'
                           .format(platform.python_version()), 'dist/licenses/Python-incorporated-software.txt')

# Create ZIP file
shutil.make_archive('instaloader-{}-windows-standalone'.format(os.getenv('VERSION_TAG')), 'zip', 'dist')
