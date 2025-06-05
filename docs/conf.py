#!/usr/bin/env python
# -*- coding: utf-8 -*-
import sys
import os
import sphinx

import pywisp

cwd = os.getcwd()
project_root = os.path.dirname(cwd)

sys.path.insert(0, project_root)
sys.path.append(os.path.abspath('../pywisp'))

# -- General configuration ---------------------------------------------

# Add any Sphinx extension module names here, as strings. They can be
# extensions coming with Sphinx (named 'sphinx.ext.*') or your custom ones.
extensions = [
    'sphinx.ext.autodoc',
    'sphinx.ext.todo',
    'sphinx.ext.viewcode',
    'sphinx.ext.imgmath',
]

numfig = True

# Add napoleon to the extension (to write/precompile google style docstrings)

if sphinx.version_info[0] <= 1 and sphinx.version_info[1] <= 2:
    # up to version 1.2 napoleon is not part of sphinx extensions
    extensions.append('sphinxcontrib.napoleon')
else:
    # from version 1.3 onwards napoleon is part of the extensions
    extensions.append('sphinx.ext.napoleon')

# Add any paths that contain templates here, relative to this directory.
templates_path = ['_templates']

# The suffix of source filenames.
source_suffix = '.rst'

# The master toctree document.
master_doc = 'index'

# General information about the project.
project = u'pyWisp'
copyright = u'2018-, IACE'

# The short X.Y version.
version = pywisp.__version__
# The full version, including alpha/beta/rc tags.
release = pywisp.__version__

# List of patterns, relative to source directory, that match files and
# directories to ignore when looking for source files.
exclude_patterns = ['_build']

# If true, the current module name will be prepended to all description
# unit titles (such as .. function::).
add_module_names = False

# The name of the Pygments (syntax highlighting) style to use.
pygments_style = 'sphinx'

autoclass_content = "both"

# Enable numbered references
numfig = True

# -- Options for HTML output -------------------------------------------

html_theme = 'alabaster'
html_theme_options = {
    'page_width': 'auto',
    'body_max_width': 'auto',
}

html_sidebars = {
    '**': [
        'about.html',
        'navigation.html',
        'relations.html',  # needs 'show_related': True theme option to display
        'searchbox.html',
    ]
}

# The name of an image file (relative to this directory) to place at the
# top of the sidebar.
html_logo = "../pywisp/resources/icons/icon128.png"

# The name of an image file (within the static path) to use as favicon
# of the docs.  This file should be a Windows icon file (.ico) being
# 16x16 or 32x32 pixels large.
html_favicon = "../pywisp/resources/icons/icon.ico"

# Output file base name for HTML help builder.
htmlhelp_basename = 'pywispdoc'
