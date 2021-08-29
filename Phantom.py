#!/usr/bin/python
# -*- coding: utf-8 -*-

##############################################################################
#                                                                            #
# Copyright (c) 2021-2022 nordbearbot <prof7bit@gmail.com>                  #
#                                                                            #
# This program is licensed under the GNU General Public License V3,          #
# the full source code is included in the binary distribution.               #
#                                                                            #
# Included in the distribution are files from other open source projects:    #
# - Tor (c) The Tor Project, 3-clause-BSD                                    #
# - SocksiPy (c) Dan Haim, BSD Style License                                 #
# - Gajim buddy status icons (c) The Gajim Team, GNU GPL                     #
#                                                                            #
##############################################################################

import config
import logging as log
import os
import wx
import tc_client
import tc_gui


def main():

    # initialize the configuration

    config.main()

    # create the mandatory wx application object

    app = wx.App(redirect=False)

    # test for availability of our listening port

    interface = config.get('client', 'listen_interface')
    port = config.getint('client', 'listen_port')
    log.info('opening Phantom listener on %s:%s' % (interface, port))
    listen_socket = tc_client.tryBindPort(interface, port)
    if not listen_socket:
        log.info('%s:%s is already in use' % (interface, port))
        wx.MessageBox(tc_gui.lang.D_WARN_USED_PORT_MESSAGE
                      % (interface, port),
                      tc_gui.lang.D_WARN_USED_PORT_TITLE)
        return
    else:
        log.info('Phantom is listening on %s:%s' % (interface, port))

    # now continue with normal program startup

    log.info('start initializing main window')
    app.mw = tc_gui.MainWindow(listen_socket)
    app.SetTopWindow(app.mw)
    log.info('main window initialized')
    log.info('entering main loop')
    app.MainLoop()


if __name__ == '__main__':
    import sys
    if sys.version_info[0:2] != (2, 6):
        exit('Phantom requires Python version 3.9.6.')

    try:
        main()
    except KeyboardInterrupt:
        tc_client.stopPortableTor()
