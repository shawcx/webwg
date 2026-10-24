WebWG
=====

WebWG runs WireGuard servers on a Linux machine and gives admins a web page
to manage them: approve devices that ask to join, add peers, hand out their
configs as a QR code or a file, and watch who is online.

Features
--------

- One page per server with its network, endpoint and public key, the requests
  waiting for approval and the peers with their last handshake and traffic,
  updated live over a WebSocket.
- Two kinds of server. A **hub** lets its peers reach each other through the
  server by turning on IPv4 forwarding for that interface only. An
  **isolated** server lets peers reach the server and nothing else.
- Devices ask to join on their own, from the **join page** in a browser or
  with the ``cliwg.py`` client, and an admin approves them.
- Private keys of joining devices are made on the device and never sent to
  the server. The preshared key comes from an ECDH exchange, so it is never
  sent either.
- WireGuard is configured in process over netlink with pyroute2, so the
  server needs ``CAP_NET_ADMIN`` but not root, and no ``wg`` or ``ip``
  commands.
- Admin users and sessions, with password logins and an optional GitLab
  login.

How devices join
----------------

The join page, at ``/join``, makes the device's WireGuard keys in the
browser with WebCrypto, sends only the public keys and shows the finished
config as a QR code, text and a download. Browsers only allow this on a page
served over HTTPS, or from ``localhost``.

From a terminal, ``cliwg.py`` does the same. Download it from the sign-in
page or from ``/static/cliwg.py``. It needs Python 3 and python3-cryptography::

    python3 cliwg.py https://vpn.example.com laptop -i home

``-i`` picks the server and defaults to the first one, and ``--qr`` also
prints the config as a QR code. The config is written to
``<server>-<name>.conf``, readable only by you.

Either way the request waits on the server's page until an admin approves
it, and the tunnel connects once they do. Admins can also add a peer
directly, and WebWG shows its config once.

Requirements
------------

- Linux with WireGuard in the kernel
- Python 3.10 or later
- `underscorepy <https://pypi.org/project/underscorepy/>`_ 0.10 or later,
  with SQLAlchemy 2, aiosqlite and alembic
- `pyroute2 <https://pypi.org/project/pyroute2/>`_ 0.9 or later
- cryptography and qrcode
- root or ``CAP_NET_ADMIN`` to manage the WireGuard interfaces

Debian and Ubuntu packages
--------------------------

Packages for Debian 13 and later and Ubuntu 25.04 and later are built in a
Debian 13 container, which needs Docker::

    make deb
    sudo apt install ./dist/*.deb

This builds three packages: ``webwg`` itself, plus ``python3-pyroute2`` and
``python3-underscorepy``, which those releases don't ship in new enough
versions. The packaging for those two is in ``packaging/``, built from their
PyPI releases.

The ``webwg`` service starts on install, listens on ``127.0.0.1:9999`` and
runs as the ``webwg`` user holding only ``CAP_NET_ADMIN``, with its
database in ``/var/lib/webwg``. Create the first admin user with::

    sudo -u webwg webwg-server --dblogin-add-user admin 'password'

Then put a reverse proxy with TLS in front of it. The join page needs HTTPS.

Installing from source
----------------------

The web assets are built with npm, using esbuild and sass. Then install into
a virtualenv, create an admin user and start the server with the rights to
manage WireGuard::

    make
    python3 -m venv .venv
    .venv/bin/pip install .
    .venv/bin/webwg-server --dblogin-add-user admin 'password'
    sudo .venv/bin/webwg-server

``webwg/support/webwg.service`` is a systemd unit that runs it as a
``webwg`` user with only ``CAP_NET_ADMIN`` instead of root.

Configuration
-------------

The defaults are in ``webwg/webwg.ini``. Settings in
``/etc/webwg/webwg.ini``, or in a file given with ``--ini``, override them.
For example, to listen on another address and port::

    [webwg]
    address = 0.0.0.0
    port    = 8080

The GitLab login needs an OAuth application on your GitLab instance::

    [gitlab]
    gitlab        = https://gitlab.example.com
    client_id     = <client-id>
    client_secret = <client-secret>

Run ``webwg-server --help`` for the command line options, or see the man
page from the Debian package.

Development
-----------

::

    make          # build webwg/static from src: scripts, styles, fonts and icons
    make run      # run python3 -m webwg --debug on 127.0.0.1:9999

The browser code is in ``src/js`` and the styles in ``src/sass``. Pages are
Tornado templates in ``webwg/templates``, and the WireGuard and netlink code
is in ``webwg/wireguard.py``. Managing interfaces needs ``CAP_NET_ADMIN``.
Without it the pages still work, and creating a server reports the missing
permission.

License
-------

WebWG is released under the MIT license, see ``LICENSE``. The bundled
Bootstrap, Bootstrap Icons, jQuery, Backbone, Underscore and qrcode-generator
are MIT licensed, and the IBM Plex fonts use the SIL Open Font License 1.1.
