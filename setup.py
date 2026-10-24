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
    package_data={"webwg": ["*.*"]},
    entry_points = {
        'console_scripts' : [
            'webwg-server = webwg:WebWg.main',
            ]
        },
    include_package_data = True,
    install_requires = [
        'underscorepy[sqlite,migrations]>=0.10',
        'cryptography',
        'qrcode[pil]',
        ],
    zip_safe = False
    )
