#!/usr/bin/env python3

import sys
import os

import setuptools

exec(compile(open('webwg/version.py').read(),'version.py','exec'))

setuptools.setup(
    name             = 'webwg',
    version          = __version__,
    author           = __author__,
    author_email     = __email__,
    description      = '_.py webwg',
    long_description = open('README.rst').read(),
    license          = 'TBD',
    packages         = setuptools.find_packages(),
    entry_points = {
        'console_scripts' : [
            'webwg-server = webwg:webwg.main',
            ]
        },
    include_package_data = True,
    install_requires = [
        'underscorepy',
        'aiosqlite',
        'cryptography',
        'qrcode',
        ],
    zip_safe = False
    )
