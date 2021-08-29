#!/usr/bin/python
# -*- coding: utf-8 -*-

import sys
sys.path.append('../')
import version
import os


def zipSource(zip_filename, zip_options):
    os.system('zip %s %s doc/*' % (zip_options, zip_filename))
    os.system('zip %s %s src/* -x *offline.txt *.ini *.pyc *.pyo *.log src/buddy-list.txt src/test*'
               % (zip_options, zip_filename))
    os.system('zip %s %s src/icons/*' % (zip_options, zip_filename))
    os.system('zip %s %s src/Tor/tor.sh' % (zip_options, zip_filename))
    os.system('zip %s %s src/Tor/torrc.txt' % (zip_options,
              zip_filename))
    os.system('zip %s %s src/translations/* -x *.pyc *.pyo'
              % (zip_options, zip_filename))
    os.system('zip %s %s src/SocksiPy/* -x *.pyc *.pyo' % (zip_options,
              zip_filename))


def zipWindowsBin(zip_filename, zip_options):
    os.system('zip %s %s bin/* -x bin/buddy-list.txt *.log *.ini'
              % (zip_options, zip_filename))
    os.system('zip %s %s bin/Tor/* -x *.log' % (zip_options,
              zip_filename))
    os.system('zip %s %s bin/icons/*' % (zip_options, zip_filename))


dir = os.getcwd()
try:
    os.mkdir('../release')
except:
    pass
os.chdir('..')
zip_options = '-9'

zip_filename = 'release/phantom-windows-%s.zip' % version.VERSION
os.system('rm %s' % zip_filename)
zipWindowsBin(zip_filename, zip_options)
zipSource(zip_filename, zip_options)

zip_filename = 'release/phantom-source-%s.zip' % version.VERSION
os.system('rm %s' % zip_filename)
zipSource(zip_filename, zip_options)

