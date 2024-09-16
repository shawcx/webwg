#!/usr/bin/env python3

import argparse
import collections
import configparser
import json
import logging
import os
import subprocess
import sys
import time

import urllib.request

import webwg

from . import database

configs = {}

def run(*args, stdin=None):
    if stdin:
        stdin = stdin.encode('utf-8')
    out = subprocess.run(
        ('wg',) + args,
        capture_output=True,
        input=stdin,
        )
    return out.stdout.decode('utf-8').strip()


def status():
    output = run('show','all','dump')
    output = output.split('\n')

    status = {}
    interface = None
    for line in output:
        if not line:
            logging.warning('Unable to query status')
            return None
        line = line.split()
        if line[0] != interface:
            interface = line[0]
            priv,pub,port,fwmark = line[1:]
            status[interface] = []
        else:
            pub,psk,endpoint,ips,handshake,rx,tx,keepalive = line[1:]
            status[interface].append({
                'pub'       : pub,
                'endpoint'  : endpoint,
                'ips'       : ips,
                'handshake' : handshake,
                'rx'        : rx,
                'tx'        : tx,
                })
    return status


class ServerConfig:
    @classmethod
    def loadAll(cls):
        db = database.Sync()
        db.open()
        servers = db.list_servers()
        db.close()

        for root,directories,filenames in os.walk('/etc/wireguard'):
            for filename in filenames:
                if not filename.endswith('.conf'):
                    continue
                interface = filename[:-5]
                if interface not in servers:
                    continue
                self = cls(interface)
                ok = self.load()
                if not ok:
                    continue
                configs[filename[:-5]] = self
        return len(configs)

    def __init__(self, name):
        self.name      = name
        self.path      = f'/etc/wireguard/{name}.conf'
        self.interface = None
        self.peers     = {}

    def load(self):
        try:
            fp = open(self.path, 'r')
        except FileNotFoundError:
            return False

        logging.info('Loading %s', self.path)

        state = 0
        for line in fp.readlines():
            line = line.strip()
            if not line:
                continue

            if line == '[Interface]':
                state = 1
                if self.interface:
                    raise ValueError('Interface already defined')
                self.interface = current = {}
                continue

            if line == '[Peer]':
                state = 2
                current = {}
                continue

            name,value = [w.strip() for w in line.split('=',1)]
            current[name] = value

            if state == 2:
                if name == 'PublicKey':
                    self.peers[value] = current
            #if state == 1:
            #    if name == 'Address':
            #        current['Address'],current['Netmask'] = value.split('/',1)
            #        self.serverAddress = current['Address'].split('.')
            #        self.serverNetmask = current['Netmask']
            #    else:
            #        current[name] = value
            #elif state == 2:
            #    if name == 'AllowedIPs':
            #        current['Address'] = value
            #    else:
            #        current[name] = value
            #else:
            #    current[name] = value

        try:
            self.serverPub = run('pubkey', stdin=self.interface.get('PrivateKey'))
        except:
            return False

        return True

    def save(self):
        if not self.interface:
            return False

        if webwg.args.debug:
            print('-' * 80)
            print(self.path)
            print('-' * 80)
            for k,v in self.interface.items():
                print(f'{k} = {v}')
            for pub,peer in self.peers.items():
                print('[Peer]')
                for k,v in peer.items():
                    print(f'{k} = {v}')
            print('-' * 80)

        fp = open(self.path, 'w')
        fp.write('[Interface]\n')
        for k,v in self.interface.items():
            fp.write(f'{k} = {v}\n')
        for pub,peer in self.peers.items():
            fp.write('[Peer]\n')
            for k,v in peer.items():
                fp.write(f'{k} = {v}\n')
        fp.close()

    def up(self):
        os.system(f'systemctl enable wg-quick@{self.name}.service')
        os.system(f'systemctl start wg-quick@{self.name}.service')
        #os.system(f'wg-quick up {self.name}')

    def down(self):
        os.system(f'systemctl stop wg-quick@{self.name}.service')
        os.system(f'systemctl disable wg-quick@{self.name}.service')
        #os.system(f'wg-quick down {self.name}')

    def sync(self):
        os.system(f'bash -c "wg syncconf {self.name} <(wg-quick strip {self.name})"')

    @classmethod
    def create(cls, server, key):
        interface = server['interface']
        self = cls(interface)
        if server['type'] == 'hub':
            self.interface = {
                'Address'    : f"{server['network']}/24",
                'ListenPort' : server['port'],
                'PrivateKey' : key,
                'MTU'        : server['mtu'],
                'SaveConfig' : 'false',
            }

        configs[self.name] = self

        self.save()
        self.up()

        return self

    def destroy(self):
        self.down()
        os.unlink(self.path)
        configs.pop(self.name, None)

    def addPeer(self, **peer):
        self.peers[peer['pub']] = {
            'PublicKey'    : peer['pub'],
            'PresharedKey' : peer['psk'],
            'AllowedIPs'   : peer['address'] + '/32',
        }
        self.save()
        self.sync()

    def removePeer(self, peer):
        self.peers.pop(peer['pub'])
        self.save()
        self.sync()
