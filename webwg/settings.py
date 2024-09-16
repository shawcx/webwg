
import sys
import os
import argparse
import configparser
import logging

import webwg


def parse():
    argparser = argparse.ArgumentParser()

    argparser.add_argument('--addr',
        metavar='<ip>',
        help='address to listen on'
        )

    argparser.add_argument('--port',
        metavar='<port>', type=int,
        help='port to bind to'
        )

    argparser.add_argument('--ini',
        metavar='<ini file>',
        help='alternate configuration file'
        )

    argparser.add_argument('--init',
        action='store_true',
        help='initialized the database'
        )

    argparser.add_argument('--list-users',
        action='store_true',
        help='create user'
        )

    argparser.add_argument('--user',
        metavar='<user>', nargs=2,
        help='create user'
        )

    argparser.add_argument('--debug',
        action='store_true',
        help='enable debug options'
        )

    webwg.args = argparser.parse_args()

    # Setting default stdout logging
    logging.basicConfig(
        format  = '%(asctime)s %(levelname)-8s %(message)s',
        datefmt = '%Y-%m-%d %H:%M:%S',
        level   = logging.DEBUG if webwg.args.debug else logging.INFO
        )

    iniFiles = [
        os.path.join(webwg.root, 'webwg.ini'),
        ]

    if webwg.args.ini:
        iniFiles.append(webwg.args.ini)

    webwg.config = configparser.ConfigParser(
        allow_no_value = True,
        interpolation  = None,
        )
    webwg.config.optionxform = str

    try:
        ok = webwg.config.read(iniFiles)
    except Exception as e:
        raise webwg.error('Unable to parse file: %s', e)
    if not ok:
        raise webwg.error('Unable to read config file(s): %s', iniFiles)

    if not webwg.args.addr:
        webwg.args.addr = webwg.config.get('server', 'address')

    if not webwg.args.port:
        webwg.args.port = webwg.config.getint('server', 'port')
