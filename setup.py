#!/usr/bin/env python3

import sys
import os

import setuptools

exec(compile(open('webwg/version.py').read(),'version.py','exec'))

setuptools.setup(
    name             = 'WebWG',
    author           = 'Matthew Shaw',
    author_email     = 'mshaw.cx@gmail.com',
    version          = __version__,
    description      = 'WireGuard Web UI',
    long_description = open('README.rst').read(),
    license          = 'Proprietary',
    packages         = setuptools.find_packages(),
    entry_points = {
        'console_scripts' : [
            'webwg-server = webwg.application:main',
            ]
        },
    include_package_data = True,
    install_requires = [
        'tornado',
        'aiosqlite',
        'redis',
        'hiredis',
        'cryptography',
        'qrcode',
        ],
    zip_safe = False
    )
