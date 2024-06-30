# Configuration file for the Sphinx documentation builder.
#
# For the full list of built-in configuration values, see the documentation:
# https://www.sphinx-doc.org/en/master/usage/configuration.html

import os
import platform
import subprocess
import sys

sys.path.insert(0, os.path.abspath('..'))


# -- Project information -----------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#project-information

project = 'Instaloader'
copyright = '2023, Alexander Graf and Andre Koch-Kramer'
author = 'Alexander Graf and Andre Koch-Kramer'

# -- General configuration ---------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#general-configuration

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.extlinks",
    "sphinx.ext.githubpages",
    "sphinx.ext.intersphinx",
    "sphinxcontrib.jquery",
]

# autodoc options

autodoc_default_options = {
    'show-inheritance': True,
    'members': True,
    'undoc-members': True,
}

# extlinks options

extlinks = {
    'issue': (
        'https://github.com/instaloader/instaloader/issues/%s',
        'Issue #%s'
    ),
    'example': (
        'https://raw.githubusercontent.com/instaloader/instaloader/master/docs/codesnippets/%s',
        'Example %s'
    ),
}

# intersphinx options

intersphinx_mapping = {
    'python': ('https://docs.python.org/3', None),
    'requests': ('https://requests.readthedocs.io/en/latest/', None),
}

# other options

templates_path = ['_templates']
exclude_patterns = ['_build', 'Thumbs.db', '.DS_Store']

# ignore TypeVar as it is currently unsupported by Sphinx
nitpick_ignore = [('py:class', 'instaloader.nodeiterator.T')]

# -- Options for HTML output -------------------------------------------------
# https://www.sphinx-doc.org/en/master/usage/configuration.html#options-for-html-output

pygments_style = 'fruity'

html_theme = 'basic'
html_static_path = ['_static']

html_logo = "logo.png"

html_css_files = ['instaloaderdoc.css']
html_js_files = ['instaloaderdoc.js']

# get release number

current_release = subprocess.check_output(["git", "describe", "--abbrev=0"]).decode("ascii")[1:-1]
date_format = "%e %b %Y" if platform.system() != "Windows" else "%d %b %Y"
current_release_date = subprocess.check_output(
    ["git", "log", "-1", "--tags", "--format=%ad", "--date=format:"+date_format]).decode("ascii")[:-1]

html_context = {'current_release': current_release, 'current_release_date': current_release_date}
