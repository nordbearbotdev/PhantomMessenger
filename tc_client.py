#!/usr/bin/python
# -*- coding: utf-8 -*-

##############################################################################
#                                                                            #
# Copyright (c) 2021-2022 nordbearbot                                        #
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

# This is the Phantom client library. Import this module, make an instance
# of BuddyList, give it your call-back function and your client is running.

import SocksiPy.socks as socks
import socket
import threading
import random
import time
import sys
import os
import shutil
import subprocess
import tempfile
import hashlib
import logging as log
import config
import version

PHANTOM_PORT = 11009  # do NOT change this.
TOR_CONFIG = 'tor'  # the name of the active section in the .ini file
STATUS_OFFLINE = 0
STATUS_HANDSHAKE = 1
STATUS_ONLINE = 2
STATUS_AWAY = 3
STATUS_XA = 4

CB_TYPE_CHAT = 1
CB_TYPE_FILE = 2
CB_TYPE_OFFLINE_SENT = 3

tor_pid = None
tor_proc = None
tor_timer = None


def escape(text):
    text = text.replace('\\', '\\/')  # replace \ with \/
    text = text.replace('\n', '\\n')  # replace linebreak with \n
    return text


def unescape(text):
    text = text.replace('\\n', '\n')  # replace \n with linebreak
    text = text.replace('\\/', '\\')  # replace \/ with \
    return text


def createTemporaryFile(file_name):
    if config.getint('files', 'temp_files_in_data_dir'):
        dir = config.getDataDir()
    else:
        dir = config.get('files', 'temp_files_custom_dir')
    try:
        if dir == '':
            dir = None
        tmp = tempfile.mkstemp('_' + file_name, 'phantom_incoming_',
                               dir)
    except:
        log.info('could not create temporary file in %s' % dir)
        config.tb()
        log.info('trying system temporary folder')
        tmp = tempfile.mkstemp('_' + file_name, 'phantom_incoming_')
    (fd, file_name_tmp) = tmp
    file_handle_tmp = os.fdopen(fd, 'w+b')
    log.warn('created temporary file  %s' % file_name_tmp)
    return (file_name_tmp, file_handle_tmp)


# --- ### Client API


class Buddy(object):

    def __init__(
        self,
        address,
        buddy_list,
        name='',
        temporary=False,
        ):
        log.warn('(2) initializing buddy %s, temporary=%s' % (address,
                 temporary))
        self.bl = buddy_list
        self.address = address
        self.name = name
        self.random1 = os.urandom(32)
        self.random2 = os.urandom(32)
        self.conn_out = None
        self.conn_in = None
        self.status = STATUS_OFFLINE
        self.can_send = False
        self.version = ''
        self.timer = False
        self.last_status_time = 0
        self.count_failed_connects = 0
        self.active = True
        self.temporary = temporary
        self.startTimer()

    def connect(self):
        log.warn('%s.connect()' % self.address)
        if self.conn_out == None:
            self.conn_out = OutConnection(self.address + '.onion',
                    self.bl, self)
            self.sendPing()

    def disconnect(self):
        log.warn('%s.disconnect()' % self.address)
        if self.conn_out != None:
            self.conn_out.close()
            self.conn_out = None
        if self.conn_in != None:
            self.conn_in.close()
            self.conn_in = None
        self.setStatus(STATUS_OFFLINE)
        self.can_send = False

    def onOutConnectionFail(self):
        log.warn('%s.onOutConnectionFail()' % self.address)
        self.count_failed_connects += 1
        self.startTimer()

    def onInConnectionFail(self):
        log.warn('%s.onInConnectionFail()' % self.address)
        self.resetConnectionFailCounter()
        self.startTimer()

    def onOutConnectionSuccess(self):
        log.warn('%s.onOutConnectionSuccess()' % self.address)
        self.startTimer()

    def onInConnectionFound(self, connection):
        log.warn('s.onInConnectionFound()' % self.address)
        conn_old = self.conn_in
        if conn_old == connection:
            log.warn('this connection is already the current conn_in. doing nothing.'
                     )
            return

        self.conn_in = connection
        connection.buddy = self
        if conn_old:
            log.warn('closing old connection of %s, %s'
                     % (self.address, conn_old))
            log.warn('new connection is %s' % connection)
            conn_old.buddy = None
            conn_old.close()

    def resetConnectionFailCounter(self):
        self.count_failed_connects = 0

    def setActive(self, active):
        log.warn('%s.setActive(%s)' % (self.address, active))
        self.active = active

    def setTemporary(self, temporary):
        log.warn('%s.setTemporary(%s)' % (self.address, temporary))
        self.temporary = temporary

    def setStatus(self, status):
        if status != STATUS_OFFLINE or self.status != STATUS_OFFLINE:
            self.resetConnectionFailCounter()
        self.status = status
        self.last_status_time = time.time()

    def addToList(self):
        log.warn('%s.addToList()' % self.address)
        self.bl.addBuddy(self)

    def sendLine(self, line, conn=0):

        # conn: use outgiong or incoming connection

        if self.conn_out == None:
            self.connect()
        if conn == 0:
            self.conn_out.send(line + '\n')
        else:
            if self.conn_in:
                self.conn_in.send(line + '\n')
            else:

                # FIXME: handle this condition

                pass

    def sendChatMessage(self, text):

        # text must be unicode

        if self.can_send:
            message = ProtocolMsg(self.bl, None, 'message',
                                  text.encode('UTF-8'))
            message.send(self)
        else:
            self.storeOfflineChatMessage(text)

    def getOfflineFileName(self):
        return os.path.join(config.getDataDir(), self.address
                            + '_offline.txt')

    def storeOfflineChatMessage(self, text):

        # text must be unicode

        log.warn('storing offline message to %s' % self.address)
        file = open(self.getOfflineFileName(), 'a')
        file.write('[delayed] ' + text.encode('UTF-8') + '\n')
        file.close()

    def getOfflineMessages(self):

        # will return the string as unicode

        try:
            file = open(self.getOfflineFileName(), 'r')
            text = file.read().rstrip()
            file.close()
            return text.decode('UTF-8')
        except:
            return ''

    def sendOfflineMessages(self):

        # this will be called after the answer to the ping message

        text = self.getOfflineMessages()
        if text:
            os.unlink(self.getOfflineFileName())
            log.warn('sending offline messages to %s' % self.address)

            # we send it without checking online status. because we have sent
            # a pong before, the receiver will have set the status to online.
            # text is unicode, so we must encode it to UTF-8 again.

            message = ProtocolMsg(self.bl, None, 'message',
                                  text.encode('UTF-8'))
            message.send(self)
            self.bl.guiCallback(CB_TYPE_OFFLINE_SENT, self)
        else:
            pass

    def getDisplayNameOrAddress(self):
        if self.name == '':
            return self.address
        else:
            return self.name

    def getAddressAndDisplayName(self):
        if self.name == '':
            return self.address
        else:
            return self.address + ' (' + self.name + ')'

    def sendFile(self, filename, gui_callback):
        sender = FileSender(self, filename, gui_callback)
        return sender

    def startTimer(self):
        if not self.active:
            log.warn('%s is not active. Will not start a new timer'
                     % self.address)
            return

        if self.status == STATUS_OFFLINE:
            if self.count_failed_connects < 4:
                t = random.randrange(0, 15000) / 1000.0
            else:
                if self.count_failed_connects < 15:
                    t = random.randrange(30000, 60000) / 1000.0
                else:
                    t = random.randrange(300000, 600000) / 1000.0
            log.warn('%s had %i failed connections. Setting timer to %f seconds'
                      % (self.address, self.count_failed_connects, t))
        else:

            # whenever we are connected to someone we use a fixed timer.
            # otherwise we would create a unique pattern of activity
            # over time that could be identified at the other side

            t = 60

        if self.timer:
            self.timer.cancel()
        self.timer = threading.Timer(t, self.onTimer)
        self.timer.start()

    def onTimer(self):
        log.fatal('timer event for %s' % self.address)
        if not self.active:
            log.info("%s is not active, onTimer() won't do anything"
                     % self.address)
            return

        self.keepAlive()

        if self.status != STATUS_OFFLINE and time.time() \
            - self.last_status_time > config.get('internal',
                'dead_connection_timeout'):

            # long time without status is indicating a broken link
            # disconnect to give it a chance to reconnect

            log.info('%s reveived no status update for a long time. disconnecting'
                      % self.address)
            self.disconnect()  # this will trigger outConnectionFail()

        # only restart the timer automatically if we are connected (or handshaking).
        # else it will be restarted by outConnectionFail() / outConnectionSuccess()

        if self.status != STATUS_OFFLINE:
            self.startTimer()

    def keepAlive(self):
        if self.conn_out == None:
            self.connect()
        else:
            if self.conn_in:
                self.sendStatus()
            else:
                if self.status == STATUS_HANDSHAKE:
                    self.sendPing()

    def sendPing(self):
        log.warn('%s.sendPing()' % self.address)

        # self.random1 = str(random.getrandbits(256))

        ping = ProtocolMsg(self.bl, None, 'ping', (config.get('client',
                           'own_hostname'), self.random1))
        ping.send(self)

    def sendStatus(self):
        if self.conn_out != None:
            status = ''
            if self.bl.own_status == STATUS_ONLINE:
                status = 'available'
            if self.bl.own_status == STATUS_AWAY:
                status = 'away'
            if self.bl.own_status == STATUS_XA:
                status = 'xa'
            if status != '':
                msg = ProtocolMsg(self.bl, None, 'status', status)
                msg.send(self)

    def sendAddMe(self):
        msg = ProtocolMsg(self.bl, None, 'add_me', '')
        msg.send(self)

    def sendRemoveMe(self):
        if self.conn_in:
            msg = ProtocolMsg(self.bl, None, 'remove_me', '')
            msg.send(self)

    def sendVersion(self):
        msg = ProtocolMsg(self.bl, None, 'version', version.VERSION)
        msg.send(self)

    def getDisplayName(self):
        if self.name != '':
            line = '%s (%s)' % (self.address, self.name)
        else:
            line = self.address
        return line


class BuddyList(object):

    # the buddy list object is somewhat like a central API.
    # All functionality and access to all other objects should
    # be possible with it's methods. Most other objects carry
    # a reference to the one and only BuddyList object around
    # to be able to find and interact with other objects.

    def __init__(self, guiCallback, socket=None):
        log.info('initializing buddy list')
        self.guiCallback = guiCallback

        startPortableTor()

        self.file_sender = {}
        self.file_receiver = {}

        # temporary buddies, created from incoming pings with new hostnames
        # these buddies are not yet in the list and if they do not
        # answer and authenticate on the first try they will be deleted

        self.incoming_buddies = []

        self.listener = Listener(self, socket)
        self.own_status = STATUS_ONLINE

        filename = os.path.join(config.getDataDir(), 'buddy-list.txt')

        # create empty buddy list file if it does not already exist

        f = open(filename, 'a')
        f.close()

        f = open(filename, 'r')
        l = f.read().split('\n')
        f.close
        self.list = []
        for line in l:
            line = line.rstrip()
            if len(line) > 15:
                address = line[0:16]
                if len(line) > 17:
                    name = line[17:].decode('UTF-8')
                else:
                    name = ''
                buddy = Buddy(address, self, name)
                self.list.append(buddy)

        found = False
        for buddy in self.list:
            if buddy.address == config.get('client', 'own_hostname'):
                found = True

        if not found:
            log.info('adding own hostname %s to list'
                     % config.get('client', 'own_hostname'))
            if config.get('client', 'own_hostname') \
                != '0000000000000000':
                self.addBuddy(Buddy(config.get('client', 'own_hostname'
                              ), self, 'myself'))

        log.info('buddy list initialized')

    def save(self):
        f = open(os.path.join(config.getDataDir(), 'buddy-list.txt'),
                 'w')
        for buddy in self.list:
            line = '%s %s' % (buddy.address, buddy.name.encode('UTF-8'))
            f.write('%s\r\n' % line.rstrip())
        f.close()
        log.warn('buddy list saved')

    def addBuddy(self, buddy):
        if self.getBuddyFromAddress(buddy.address) == None:
            self.list.append(buddy)
            buddy.setTemporary(False)
            buddy.setActive(True)
            if buddy in self.incoming_buddies:
                self.incoming_buddies.remove(buddy)
            self.save()
            buddy.keepAlive()
            return buddy
        else:
            return False

    def removeBuddy(self, buddy_to_remove, disconnect=True):
        log.warn('removeBuddy(%s, %s)' % (buddy_to_remove.address,
                 disconnect))
        buddy_to_remove.setActive(False)
        if not disconnect:

            # send remove_me and leave the connections open
            # but remove them from this buddy.

            buddy_to_remove.sendRemoveMe()
            if buddy_to_remove.conn_out:
                buddy_to_remove.conn_out.buddy = None
                buddy_to_remove.conn_out = None
            if buddy_to_remove.conn_in:
                buddy_to_remove.conn_in.buddy = None
                buddy_to_remove.conn_in = None
        else:
            buddy_to_remove.disconnect()
        self.list.remove(buddy_to_remove)
        file_name = buddy_to_remove.getOfflineFileName()
        try:
            os.unlink(file_name)
        except:
            pass
        self.save()

    def removeBuddyWithAddress(self, address):
        buddy = self.getBuddyFromAddress(address)
        if buddy != None:
            self.removeBuddy(buddy)

    def getBuddyFromAddress(self, address):
        for buddy in self.list:
            if buddy.address == address:
                return buddy
        return None

    def getIncomingBuddyFromAddress(self, address):
        for buddy in self.incoming_buddies:
            if buddy.address == address:
                return buddy
        return None

    def getBuddyFromRandom(self, random):
        for buddy in self.list:
            if buddy.random1 == random:
                return buddy
        return None

    def getIncomingBuddyFromRandom(self, random):
        for buddy in self.incoming_buddies:
            if buddy.random1 == random:
                return buddy
        return None

    def getFileReceiver(self, address, id):
        try:
            return self.file_receiver[address, id]
        except:
            return None

    def getFileSender(self, address, id):
        try:
            return self.file_sender[address, id]
        except:
            return None

    def setStatus(self, status):
        self.own_status = status
        for buddy in self.list:
            buddy.sendStatus()

    def onErrorIn(self, connection):
        for buddy in self.incoming_buddies:
            if buddy.conn_in == connection:
                log.warn('in-connection %s of temporary buddy %s failed'
                          % (connection, buddy.address))
                log.warn('removing buddy instance %s' % buddy.address)
                buddy.setActive(False)
                buddy.disconnect()
                if buddy in self.incoming_buddies:
                    self.incoming_buddies.remove(buddy)
                break

        for buddy in self.list:
            if buddy.conn_in == connection:
                buddy.disconnect()
                buddy.onInConnectionFail()
                break

    def onErrorOut(self, connection):
        buddy = connection.buddy
        if buddy:
            if buddy.temporary:
                log.warn('out-connection of temporary buddy %s failed'
                         % buddy.address)
                log.warn('removing buddy instance %s' % buddy.address)
                buddy.setActive(False)
                if buddy in self.incoming_buddies:
                    self.incoming_buddies.remove(buddy)

            buddy.disconnect()
            buddy.onOutConnectionFail()
        else:
            log.warn('out-connection without buddy failed')

    def onConnected(self, connection):
        connection.buddy.setStatus(STATUS_HANDSHAKE)
        connection.buddy.onOutConnectionSuccess()

    def onChatMessage(self, buddy, message):
        self.guiCallback(CB_TYPE_CHAT, (buddy, message))

    def onFileReceive(self, file_receiver):
        self.guiCallback(CB_TYPE_FILE, file_receiver)

    def stopClient(self):
        stopPortableTor()
        self.listener.close()  # FIXME: does this really work?
        for buddy in self.list + self.incoming_buddies:
            buddy.disconnect()


class FileSender(threading.Thread):

    def __init__(
        self,
        buddy,
        file_name,
        guiCallback,
        ):
        threading.Thread.__init__(self)
        self.buddy = buddy
        self.bl = buddy.bl
        self.file_name = file_name
        self.file_name_short = os.path.basename(self.file_name)
        self.guiCallback = guiCallback
        self.id = os.urandom(4)
        self.buddy.bl.file_sender[self.buddy.address, self.id] = self
        self.file_size = 0
        self.block_size = 8192
        self.blocks_wait = 16
        self.start_ok = -1
        self.restart_at = 0
        self.restart_flag = False
        self.completed = False
        self.timeout_count = 0
        self.start()

    def testTimeout(self):

        # this will be called every 0.1 seconds whenever the sender
        # is waiting for confirmation messages. Either in the
        # sendBlocks() loop or when all blocks are sent in the
        # outer loop in run()
        # if a timeout is detected then the restart flag will be set

        if self.buddy.conn_in:

            # we only increase timeout if we are connected
            # otherwise other mechanisms are responsible and trying
            # to get us connected again and we just wait

            self.timeout_count += 1
        else:
            self.timeout_count = 0

        if self.timeout_count == 6000:

            # ten minutes without filedata_ok

            new_start = self.start_ok + self.block_size
            self.restart(new_start)

            # enforce a new connection

            try:
                self.buddy.conn_in.close()
            except:
                pass
            log.warn('timeout file sender restart at %i' % new_start)

    def canGoOn(self, start):
        position_ok = self.start_ok + self.blocks_wait * self.block_size
        if not self.running or self.restart_flag:
            return True
        else:
            return position_ok > start

    def sendBlocks(self, first):
        blocks = int(self.file_size / self.block_size) + 1

        # the inner loop (of the two loops)

        for i in range(blocks):
            start = i * self.block_size

            # jump over already sent blocks

            if start >= first:
                remaining = self.file_size - start
                if remaining > self.block_size:
                    size = self.block_size
                else:
                    size = remaining
                self.file_handle.seek(start)
                data = self.file_handle.read(size)
                hash = hashlib.md5(data).hexdigest()

                msg = ProtocolMsg(self.bl, None, 'filedata', (self.id,
                                  start, hash, data))

                # we can only send data if we are connected

                while not self.buddy.conn_in and not self.restart_flag:
                    time.sleep(0.1)
                    self.testTimeout()

                if self.buddy.conn_in:
                    msg.send(self.buddy, 1)

                # wait for confirmations more than blocks_wait behind

                while not self.canGoOn(start):
                    time.sleep(0.1)
                    self.testTimeout()  # this can trigger the restart flag

                if self.restart_flag:

                    # the outer loop in run() will start us again

                    break

                if not self.running:

                    # the outer loop in run() will also end

                    break

    def run(self):
        self.running = True
        try:
            self.file_handle = open(self.file_name, mode='rb')
            self.file_handle.seek(0, 2)  # SEEK_END
            self.file_size = self.file_handle.tell()
            self.guiCallback(self.file_size, 0)
            filename_utf8 = self.file_name_short.encode('utf-8')
            msg = ProtocolMsg(self.bl, None, 'filename', (self.id,
                              self.file_size, self.block_size,
                              filename_utf8))
            msg.send(self.buddy, 1)

            # the outer loop (of the two sender loops)
            # runs forever until completed ore canceled

            while not self.completed and self.running:
                self.restart_flag = False

                # (re)start the inner loop

                self.sendBlocks(self.restart_at)

                # wait for *last* filedata_ok or restart flag

                while not self.restart_flag and not self.completed \
                    and self.running:
                    time.sleep(0.1)
                    self.testTimeout()  # this can trigger the restart flag

            self.running = False
            self.file_handle.close()
        except:

            try:
                self.guiCallback(self.file_size, -1,
                                 'error while sending %s'
                                 % self.file_name)
            except:
                config.tb()
            self.close()
            config.tb()

    def receivedOK(self, start):
        self.timeout_count = 0  # we have received a sign of life
        end = start + self.block_size
        if end > self.file_size:
            end = self.file_size

        try:
            self.guiCallback(self.file_size, end)
        except:

            # cannot update gui

            config.tb()
            self.close()

        self.start_ok = start

        if end == self.file_size:

            # the outer sender loop can now stop waiting for timeout

            self.completed = True

    def restart(self, start):

        # trigger the reatart flag

        self.timeout_count = 0
        self.restart_at = start
        self.restart_flag = True

        # the inner loop will now immediately break and
        # the outer loop will start it again at position restart_at

    def sendStopMessage(self):
        msg = ProtocolMsg(self.buddy.bl, None, 'file_stop_receiving',
                          self.id)
        msg.send(self.buddy)

    def close(self):
        if self.running:
            self.running = False
            self.sendStopMessage()
            try:
                self.guiCallback(self.file_size, -1, 'transfer aborted')
            except:
                pass
        del self.buddy.bl.file_sender[self.buddy.address, self.id]


class FileReceiver:

    def __init__(
        self,
        buddy,
        id,
        block_size,
        file_size,
        file_name,
        ):
        self.buddy = buddy
        self.id = id
        self.closed = False
        self.block_size = block_size
        self.file_name = file_name
        self.file_name_save = ''
        tmp = createTemporaryFile(self.file_name)
        (self.file_name_tmp, self.file_handle_tmp) = tmp
        self.file_size = file_size
        self.next_start = 0
        self.wrong_block_number_count = 0
        self.buddy.bl.file_receiver[self.buddy.address, self.id] = self

        # this will (optionally) point to the file transfer GUI callback

        self.guiCallback = None

        # the following will result in a call into the GUI

        self.buddy.bl.onFileReceive(self)

    def setCallbackFunction(self, callback):
        self.guiCallback = callback

    def data(
        self,
        start,
        hash,
        data,
        ):
        if start > self.next_start:
            if self.wrong_block_number_count == 0:

                # not on every single out-of-order block in a row
                # we must send an error message...

                msg = ProtocolMsg(self.buddy.bl, None, 'filedata_error'
                                  , (self.id, self.next_start))
                msg.send(self.buddy)
                self.wrong_block_number_count += 1

                # ...only every 16
                # FIXME: This must be solved more elegantly

                if self.wrong_block_number_count == 16:
                    self.wrong_block_number_count = 0
            return

        self.wrong_block_number_count = 0
        hash2 = hashlib.md5(data).hexdigest()
        if hash == hash2:
            self.file_handle_tmp.seek(start)
            self.file_handle_tmp.write(data)
            self.next_start = start + len(data)
            msg = ProtocolMsg(self.buddy.bl, None, 'filedata_ok',
                              (self.id, start))
            msg.send(self.buddy)
            try:
                self.guiCallback(self.file_size, start + len(data))
            except:

                # The GUI has not (yet) provided a callback function

                log.warn('FileReceiver cannot call the GUI')
        else:

            log.critical('receiver wrong hash %i len: %i' % (start,
                         len(data)))
            msg = ProtocolMsg(self.buddy.bl, None, 'filedata_error',
                              (self.id, start))
            msg.send(self.buddy)

            # we try to avoid unnecessary wrong-block-number errors
            # the next block sure will be out of order, but we have sent
            # an error already because of the wrong hash

            self.wrong_block_number_count = 1

    def setFileNameSave(self, file_name_save):
        self.file_name_save = file_name_save
        try:
            self.file_handle_save = open(file_name_save, 'w')
            log.warn('created and opened placeholder file %s'
                     % self.file_name_save)
        except:
            self.file_handle_save = None
            self.file_name_save = None
            self.file_save_error = str(sys.exc_info()[1])
            log.warn('%s could not be created: %s'
                     % (self.file_name_save, self.file_save_error))

    def sendStopMessage(self):
        msg = ProtocolMsg(self.buddy.bl, None, 'file_stop_sending',
                          self.id)
        msg.send(self.buddy)

    def closeForced(self):
        try:
            self.guiCallback(self.file_size, -1, 'transfer aborted')
        except:
            pass
        self.sendStopMessage()
        self.file_name_save = ''
        self.close()

    def close(self):
        if self.closed:
            return
        try:
            self.file_handle_tmp.close()
            if self.file_name_save:
                self.file_handle_save.close()
                shutil.move(self.file_name_tmp, self.file_name_save)
                log.warn('moved temporary file to %s'
                         % self.file_name_save)
            else:
                os.unlink(self.file_name_tmp)
                log.warn('deleted temporary file %s'
                         % self.file_name_tmp)
            del self.buddy.bl.file_receiver[self.buddy.address, self.id]
        except:
            pass

        self.closed = True


# --- ### Protocol messages


class MProtocolMsg(type):

    # Meta-Class for ProtocolMsg. It automagically creates a hash for
    # mapping protocol-commands and corresponding ProtocolMsg-subclasses

    subclasses = {}

    def __init__(
        cls,
        name,
        bases,
        dict,
        ):

        # this will be executed whenever a ProtocolMsg gets *defined*
        # (happens once at the time when this module is imported).
        # the commands and their classes will be stored in
        # the static member MProtocolMsg.subclasses

        cls.subclasses[dict['command']] = cls
        super(MProtocolMsg, cls).__init__(name, bases, dict)


class ProtocolMsg(object):

    __metaclass__ = MProtocolMsg
    command = ''

    # the base class for all ProtocolMsg-classes. All message classes
    # must inherit from this and declare the static member command
    # which is used (by the metaclass-magic-voodoo;-) to map between the
    # command-string and the corresponding message class

    # Besides being the base class for all ProtocolMsg_* classes
    # this class has two other use cases:
    # - it is used for outgoing messages (therefore the send method)
    # - it is instantiated for every unknown incoming message

    def __init__(
        self,
        bl,
        connection,
        command,
        data,
        ):

        # connection may be None for outgoing messages
        # data can be a number, a string, a tuple or a list

        self.connection = connection
        if connection:
            self.buddy = connection.buddy
        else:
            self.buddy = None
        self.bl = bl
        self.command = command

        # self.text is always a string containing all arguments and data

        if type(data) in (list, tuple):
            self.text = ' '.join(str(x) for x in data)
        else:
            self.text = str(data)
        self.parse()

    def parse(self):
        pass

    def execute(self):

        # a generic message of this class will be automatically instantiated
        # if an incoming message with an unknown command is received
        # do nothing and just reply with "not_implemented"

        if self.buddy:
            log.warn('received unimplemented msg (%s) from %s'
                     % (self.command, self.buddy.address))
            message = ProtocolMsg(self.bl, None, 'not_implemented',
                                  self.command)
            message.send(self.buddy)
        else:
            log.warn('received unknown command on unknown connection. closing.'
                     )
            log.warn("unknown connection had '%s' in last ping. closing"
                      % self.connection.last_ping_address)
            self.connection.close()

    def getLine(self):

        # bring the message into a form we can transmit over the socket
        # it will escape newline characters, as they are the only
        # characters with a special meaning.
        # the opposite of this operation takes place in the function
        # ProtocolMsgFromLine() where incoming messages are instantiated.

        return self.command + ' ' + escape(self.text)

    def send(self, buddy, conn=0):

        # conn=0 use outgoing connection
        # conn=1 use incoming connection
        # FIXME: what if buddy is None?

        buddy.sendLine(self.getLine(), conn)


def ProtocolMsgFromLine(bl, conn, line):

    # this is the factory for producing instances of ProtocolMsg classes.
    # it separates the first word from the line, looks up the corresponding
    # ProtocolMsg subclass which can handle this kind of protocol message
    # and returns an instance. If no class matches the command string it
    # returns a ProtocolMsg instance which is generic and just does nothing.

    (command, text_escaped) = line.split(' ', 1)

    # the rest of the message can be arbitrary (but escaped) data.
    # unescape it, so it is in it's original (maybe even binary) form.

    data = unescape(text_escaped)
    try:
        return MProtocolMsg.subclasses[command](bl, conn, command, data)
    except:
        return ProtocolMsg(bl, conn, command, data)


class ProtocolMsg_not_implemented(ProtocolMsg):

    command = 'not_implemented'

    # FIXME: Maybe it would be better to have a *separate*
    # "not_implemented"-message for every protocol message.
    # I have to meditate over this for a while.

    def execute(self):
        if self.buddy:
            log.critical("%s says it can't handle '%s'"
                         % (self.buddy.address, self.text))


class ProtocolMsg_ping(ProtocolMsg):

    command = 'ping'

    # a ping message consists of sender address and a random string

    def parse(self):

        # the sender address is in the text. we take it for granted
        # and see if we can find a buddy in our list with that address.

        (self.address, self.answer) = self.text.split(' ', 1)
        self.buddy = self.bl.getBuddyFromAddress(self.address)

    def execute(self):
        log.critical('received ping from %s' % self.address)

        # first a little security check to detect mass pings
        # with faked host names over the same connection

        if self.connection.last_ping_address != '':

            # this is not the first ping over this connection
            # lets see if it has the correct address:

            if self.address != self.connection.last_ping_address:
                log.info('Possible Attack: in-connection sent fake address %s'
                          % self.address)
                log.info('Will disconnect incoming connection from fake %s'
                          % self.address)
                self.connection.close()
                return
        else:
            self.connection.last_ping_address = self.address

        # another check for faked pings: we search all our already
        # *connected* buddies and if there is one with the same address
        # but another incoming connection then this one must be a fake.

        found = False
        for buddy in self.bl.list + self.bl.incoming_buddies:
            if buddy.conn_in:
                if buddy.address == self.address:
                    if buddy.conn_in != self.connection:
                        found = True
                        break
        if found:
            log.warn('detected ping from %s on other connection.'
                     % self.address)
            log.warn('sending a ping to %s to find correct in-connection.'
                      % self.address)
            buddy.sendPing()

        # if someone is pinging us with our own address and the
        # random value is not from us, then someone is definitely
        # trying to fake and we can close.

        if self.address == config.get('client', 'own_hostname'):
            own_buddy = self.bl.getBuddyFromAddress(self.address)
            if own_buddy.random1 != self.answer:
                log.warn('faked ping with our own address. closing.')
                self.connection.send('message you are trying to use my ID!\n'
                        )
                return

        # ping messages must be answered with pong messages
        # the pong must contain the same random string as the ping.
        # note that we will NOT yet assign buddy.conn_in
        # this can only be done in reaction to a pong message

        if not self.buddy:
            log.warn('%s is not on the buddy-list' % self.address)

            # we have received a ping, but there is no buddy with
            # that address in our buddy-list. The only reason for that
            # can be that someone new has added our address to his list
            # and his client now has connected us. First we search if
            # we already have a connection to this buddy, if not we
            # create one.

            self.buddy = \
                self.bl.getIncomingBuddyFromAddress(self.address)
            if not self.buddy:

                # create it and put it in the temporary list

                log.warn('%s is new. creating a temporary buddy instance'
                          % self.address)
                self.buddy = Buddy(self.address, self.bl,
                                   temporary=True)
                self.bl.incoming_buddies.append(self.buddy)
            else:
                log.warn('%s is already in the incoming list'
                         % self.address)
                log.warn('%s status is %i' % (self.address,
                         self.buddy.status))

            # this will connect if necessary

            log.warn('%s.keepAlive()' % self.buddy.address)
            self.buddy.keepAlive()

        log.critical('sending pong and status to %s' % self.address)
        self.buddy.resetConnectionFailCounter()
        answer = ProtocolMsg(self.bl, None, 'pong', self.answer)
        answer.send(self.buddy)
        self.buddy.can_send = True
        self.buddy.sendStatus()

        if self.buddy in self.bl.list:
            self.buddy.sendAddMe()

        self.buddy.sendVersion()


class ProtocolMsg_pong(ProtocolMsg):

    command = 'pong'

    def parse(self):
        self.is_new_buddy = False

        # incoming pong messages are used to identify and authenticate
        # incoming connections. Basically we send out pings and see which
        # corresponding pongs come in on which connections.
        # we search all our known buddies for the corresponding random
        # string to identify which buddy is replying here.

        # first we search the buddy-list

        self.buddy = self.bl.getBuddyFromRandom(self.text)
        if not self.buddy:

            # we also try to find it in the temporary buddies list

            self.buddy = self.bl.getIncomingBuddyFromRandom(self.text)

    def execute(self):

        # if the pong is found to belong to a known buddy we can now
        # safely assign this incoming connection to this buddy and
        # regard the handshake as completed.

        if self.buddy:
            log.critical('received pong from %s' % self.buddy.address)

            # assign the in-connection to this buddy

            self.buddy.onInConnectionFound(self.connection)
        else:

            # there is no buddy for this pong. nothing to do.

            log.warn("unknown incoming 'pong'. ignoring.")


class ProtocolMsg_version(ProtocolMsg):

    command = 'version'

    def parse(self):
        self.version = self.text

    def execute(self):
        if self.buddy:
            log.warn('%s has version %s' % (self.buddy.address,
                     self.version))
            self.buddy.version = self.version


class ProtocolMsg_status(ProtocolMsg):

    command = 'status'

    # this is a status message.

    def execute(self):

        # set the status flag of the corresponding buddy

        if self.buddy:
            log.critical('received status %s from %s' % (self.text,
                         self.buddy.address))

            # send offline messages if buddy was previously offline

            if self.buddy.status == STATUS_HANDSHAKE:
                log.warn('%s came online, sending delayed messages'
                         % self.buddy.address)
                self.buddy.sendOfflineMessages()

            # set buddy status

            if self.text == 'available':
                self.buddy.setStatus(STATUS_ONLINE)
            if self.text == 'away':
                self.buddy.setStatus(STATUS_AWAY)
            if self.text == 'xa':
                self.buddy.setStatus(STATUS_XA)


class ProtocolMsg_add_me(ProtocolMsg):

    command = 'add_me'

    def execute(self):
        if self.buddy:
            log.warn('add me from %s' % self.buddy.address)
            if not self.buddy in self.bl.list:
                log.warn('received add_me from new buddy %s'
                         % self.buddy.address)
                self.buddy.addToList()
                msg = '<- has added you'
                self.bl.onChatMessage(self.buddy, msg)


class ProtocolMsg_remove_me(ProtocolMsg):

    command = 'remove_me'

    def execute(self):
        if self.buddy:
            log.warn('received remove_me from buddy %s'
                     % self.buddy.address)
            if self.buddy in self.bl.list:
                log.warn('removing %s from list' % self.buddy.address)
                self.bl.removeBuddy(self.buddy)
        else:
            log.warn("received 'remove_me' on unknown connection")
            log.warn("unknown connection had '%s' in last ping. closing"
                      % self.connection.last_ping_address)
            self.connection.close()


class ProtocolMsg_message(ProtocolMsg):

    command = 'message'

    # this is a normal text chat message.

    def parse(self):
        self.text = self.text.decode('UTF-8')

    def execute(self):

        # give buddy and text to bl. bl will then call into the gui
        # to open a chat window and/or display the text.

        if self.buddy:
            if self.buddy in self.bl.list:
                if self.text.strip() != '':
                    self.bl.onChatMessage(self.buddy, self.text)
            else:
                log.warn('***** wrong version reply to %s'
                         % self.buddy.address)
                msg = 'This is an automatic reply. '
                msg += 'Your version seems to be out of date.'
                msg += \
                    'Make sure you have the latest version of TorChat. '
                self.buddy.sendChatMessage(msg)
                self.buddy.sendRemoveMe()
        else:
            log.warn("received 'message' on unknown connection")
            log.warn("unknown connection had '%s' in last ping. closing"
                      % self.connection.last_ping_address)
            self.connection.close()


class ProtocolMsg_filename(ProtocolMsg):

    command = 'filename'

    # the first message in a file transfer, initiating the transfer.

    def parse(self):
        (self.id, text) = self.text.split(' ', 1)
        (file_size, text) = text.split(' ', 1)
        (block_size, self.file_name) = text.split(' ', 1)
        self.file_size = int(file_size)
        self.block_size = int(block_size)
        self.file_name = self.file_name.decode('utf-8')
        self.file_name = self.file_name.replace('\\', '')
        self.file_name = self.file_name.replace('/', '')

    def execute(self):
        if not self.buddy:
            log.warn("received 'filename' on unknown connection")
            log.warn("unknown connection had '%s' in last ping. closing"
                      % self.connection.last_ping_address)
            self.connection.close()
            return

        # we create a file receiver instance which can deal with the
        # file data we expect to receive now

        FileReceiver(self.buddy, self.id, self.block_size,
                     self.file_size, self.file_name)


class ProtocolMsg_filedata(ProtocolMsg):

    command = 'filedata'

    # after a filename message has initiated the transfer several
    # filedata messagess transport the actual data in blocks of fixed
    # size. The data blocks are transmitted as they are and only
    # newline characters are escaped. (see escape() and unescape())

    def parse(self):
        (self.id, text) = self.text.split(' ', 1)
        (start, text) = text.split(' ', 1)
        (self.hash, self.data) = text.split(' ', 1)
        self.start = int(start)

    def execute(self):
        if not self.buddy:
            log.warn("received 'filedata' on unknown connection")
            log.warn("unknown connection had '%s' in last ping. closing"
                      % self.connection.last_ping_address)
            self.connection.close()
            return

        # there should already be a receiver, because there should have been
        # a "filename"-message at the very beginning of the transfer.

        receiver = self.bl.getFileReceiver(self.buddy.address, self.id)
        if receiver:
            receiver.data(self.start, self.hash, self.data)
        else:

            # if there is no receiver for this data, we just reply
            # with a stop message and hope the sender gets it and
            # stops sending data. Not much else to do for us here.

            msg = ProtocolMsg(self.bl, None, 'file_stop_sending',
                              self.id)
            msg.send(self.buddy)


class ProtocolMsg_filedata_ok(ProtocolMsg):

    command = 'filedata_ok'

    # every received "filedata" must be confirmed with a "filedata_ok"
    # (or a "filedata_error")

    def parse(self):
        (self.id, start) = self.text.split(' ', 1)
        self.start = int(start)

    def execute(self):
        if self.buddy:
            sender = self.bl.getFileSender(self.buddy.address, self.id)
            if sender:
                sender.receivedOK(self.start)
            else:

                # there is no sender (anymore) to handle confirmation messages
                # so we can send a stop message to tell the other side
                # to stop receiving

                msg = ProtocolMsg(self.bl, None, 'file_stop_receiving',
                                  self.id)
                msg.send(self.buddy)
        else:
            log.warn("received 'filedata_ok' on unknown connection")
            log.warn("unknown connection had '%s' in last ping. closing"
                      % self.connection.last_ping_address)
            self.connection.close()


class ProtocolMsg_filedata_error(ProtocolMsg):

    command = 'filedata_error'

    def parse(self):
        (self.id, start) = self.text.split(' ', 1)
        self.start = int(start)

    def execute(self):
        if self.buddy:
            sender = self.bl.getFileSender(self.buddy.address, self.id)
            if sender:
                sender.restart(self.start)
            else:
                msg = ProtocolMsg(self.bl, None, 'file_stop_receiving',
                                  self.id)
                msg.send(self.buddy)
        else:
            log.warn("received 'filedata_error' on unknown connection")
            log.warn("unknown connection had '%s' in last ping. closing"
                      % self.connection.last_ping_address)
            self.connection.close()


class ProtocolMsg_file_stop_sending(ProtocolMsg):

    command = 'file_stop_sending'

    # if the file transfer is prematurely canceled by the receiver
    # then this message tells the sender to stop sending further data

    def parse(self):
        self.id = self.text

    def execute(self):
        if self.buddy:
            sender = self.bl.getFileSender(self.buddy.address, self.id)
            if sender:

                # close the sender (if not already closed)
                # otherwise just ignore it

                sender.close()
        else:
            log.warn("received 'file_stop_sending' on unknown connection"
                     )
            log.warn("(2) unknown connection had '%s' in last ping. closing"
                      % self.connection.last_ping_address)
            self.connection.close()


class ProtocolMsg_file_stop_receiving(ProtocolMsg):

    command = 'file_stop_receiving'

    # if the file transfer is prematurely canceled by the sender
    # then this message tells the receiving buddy to close its receiver

    def parse(self):
        self.id = self.text

    def execute(self):
        if self.buddy:
            receiver = self.bl.getFileReceiver(self.buddy.address,
                    self.id)
            if receiver:

                # close the receiver (if not already closed)
                # otherwise just ignore it

                receiver.closeForced()
        else:
            log.warn("received 'file_stop_receiving' on unknown connection"
                     )
            log.warn("unknown connection had '%s' in last ping. closing"
                      % self.connection.last_ping_address)
            self.connection.close()


# --- ### Low level network stuff


class Receiver(threading.Thread):

    def __init__(self, conn):
        threading.Thread.__init__(self)
        self.conn = conn
        self.socket = conn.socket
        self.running = True
        self.start()

    def run(self):
        readbuffer = ''

        # self.socket.settimeout(5)

        while self.running:
            try:
                recv = self.socket.recv(4096)
                if recv != '':
                    readbuffer = readbuffer + recv
                    temp = readbuffer.split('\n')
                    readbuffer = temp.pop()

                    for line in temp:
                        if self.running:
                            try:
                                message = \
                                    ProtocolMsgFromLine(self.conn.bl,
                                        self.conn, line)
                                message.execute()
                            except:
                                config.tb()
                else:
                    self.running = False
                    self.conn.onReceiverError()
            except socket.timeout:

                pass
            except socket.error:

                config.tb(2)
                self.running = False
                self.conn.onReceiverError()


class InConnection:

    def __init__(self, socket, buddy_list):
        self.buddy = None
        self.bl = buddy_list
        self.socket = socket
        self.receiver = Receiver(self)
        self.last_ping_address = ''  # used to detect mass pings with fake adresses
        self.timer = threading.Timer(config.get('internal',
                'dead_connection_timeout'), self.onTimeout)
        self.started = True
        self.timer.start()

    def send(self, text):
        try:
            self.socket.send(text)
        except:
            config.tb()
            log.warn('in-connection send error.')
            self.bl.onErrorIn(self)
            self.close()

    def onReceiverError(self):
        log.warn('in-connection receive error. %s' % self)
        self.bl.onErrorIn(self)
        self.close()

    def close(self):
        if not self.started:
            return
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except:
            pass
        try:
            self.socket.close()
        except:
            pass
        self.started = False
        log.warn('n-connection closing (%s, %s)'
                 % (self.last_ping_address, self))
        if self in self.bl.listener.conns:
            self.bl.listener.conns.remove(self)

    def onTimeout(self):

        # if after this long time the connection is still unused, close it.

        if self.buddy and self.buddy.conn_in == self:
            self.timer = threading.Timer(config.get('internal',
                    'dead_connection_timeout'), self.onTimeout)
            self.timer.start()
        else:
            log.warn('closing unused in-connection (%s, %s)'
                     % (self.last_ping_address, self))
            self.buddy = None
            self.close()
            log.warn('have now %i incoming connections'
                     % len(self.bl.listener.conns))


class OutConnection(threading.Thread):

    def __init__(
        self,
        address,
        buddy_list,
        buddy,
        ):
        threading.Thread.__init__(self)
        self.bl = buddy_list
        self.buddy = buddy
        self.address = address
        self.send_buffer = []
        self.start()

    def run(self):
        self.running = True
        try:
            self.socket = socks.socksocket()

            # self.socket.settimeout(60)

            self.socket.setproxy(socks.PROXY_TYPE_SOCKS4,
                                 config.get(TOR_CONFIG, 'tor_server'),
                                 config.getint(TOR_CONFIG,
                                 'tor_server_socks_port'))
            log.warn("trying to connect '%s'" % self.address)
            self.socket.connect((str(self.address), TORCHAT_PORT))
            log.warn('connected to %s' % self.address)
            self.bl.onConnected(self)
            self.receiver = Receiver(self)
            while self.running:
                if len(self.send_buffer) > 0:
                    text = self.send_buffer.pop(0)
                    try:
                        self.socket.send(text)
                    except:
                        log.warn('out-connection send error')
                        self.bl.onErrorOut(self)
                        self.close()

                time.sleep(0.05)
        except:

            log.warn('out-connection to %s failed: %s' % (self.address,
                     sys.exc_info()[1]))
            self.bl.onErrorOut(self)
            self.close()

    def send(self, text):
        self.send_buffer.append(text)

    def onReceiverError(self):
        log.warn('out-connection receiver error')
        self.bl.onErrorOut(self)
        self.close()

    def close(self):
        if not self.running:
            return
        self.running = False
        try:
            self.socket.shutdown(socket.SHUT_RDWR)
        except:
            pass
        try:
            self.socket.close()
        except:
            pass
        if self.buddy:
            log.warn('out-connection closing (%s)' % self.buddy.address)
        else:
            log.warn('out-connection closing (without buddy)')


class Listener(threading.Thread):

    def __init__(self, buddy_list, socket=None):
        threading.Thread.__init__(self)
        self.buddy_list = buddy_list
        self.conns = []
        self.socket = socket
        self.start()

    def run(self):
        self.running = True
        if not self.socket:
            interface = config.get('client', 'listen_interface')
            port = config.getint('client', 'listen_port')
            self.socket = tryBindPort(interface, port)
        self.socket.listen(5)
        while self.running:
            try:
                (conn, address) = self.socket.accept()
                self.conns.append(InConnection(conn, self.buddy_list))
                log.warn('new incoming connection')
                log.warn('have now %i incoming connections'
                         % len(self.conns))
            except:
                log.warn('socket listener error!')
                config.tb()
                self.running = False

    def close(self):
        self.running = False
        try:
            self.socket.close()
        except:
            pass


def tryBindPort(interface, port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        s.bind((interface, port))
        s.listen(5)
        return s
    except:
        config.tb()
        return False


def startPortableTor():
    log.info('entering function startPortableTor()')
    global tor_in, tor_out
    global TOR_CONFIG
    global tor_pid
    global tor_proc
    old_dir = os.getcwd()
    log.info('current working directory is %s' % os.getcwd())
    try:
        log.info('changing working directory')
        os.chdir(config.getDataDir())
        os.chdir('Tor')
        log.info('current working directory is %s' % os.getcwd())

        # completely remove all cache files from the previous run
        # for root, dirs, files in os.walk("tor_data", topdown=False):
        #    for name in files:
        #        os.remove(os.path.join(root, name))
        #    for name in dirs:
        #        os.rmdir(os.path.join(root, name))

        # now start tor with the supplied config file

        log.info('trying to start Tor')

        if config.isWindows():
            if os.path.exists('tor.exe'):

                # start the process without opening a console window

                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                tor_proc = \
                    subprocess.Popen('tor.exe -f torrc.txt'.split(),
                        startupinfo=startupinfo)
                tor_pid = tor_proc.pid
            else:
                log.info('there is no portable tor.exe')
                tor_pid = False
        else:
            if os.path.exists('tor.sh'):

                # let our shell script start a tor instance

                os.system('chmod +x tor.sh')
                tor_proc = subprocess.Popen('./tor.sh'.split())
                tor_pid = tor_proc.pid
                log.info('tor pid is %i' % tor_pid)
            else:
                log.info('there is no Tor starter script (tor.sh)')
                tor_pid = False

        if tor_pid:

            # tor = subprocess.Popen("tor.exe -f torrc.txt".split(), creationflags=0x08000000)

            log.info('successfully started Tor (pid=%i)' % tor_pid)

            # we now assume the existence of our hostname file
            # it WILL be created after the first start
            # if not, something must be totally wrong.

            cnt = 0
            found = False
            while cnt <= 20:
                try:
                    log.info('trying to read hostname file (try %i of 20)'
                              % (cnt + 1))
                    f = open(os.path.join('hidden_service', 'hostname'
                             ), 'r')
                    hostname = f.read().rstrip()[:-6]
                    log.info('found hostname: %s' % hostname)
                    log.info('writing own_hostname to torchat.ini')
                    config.set('client', 'own_hostname', hostname)
                    found = True
                    f.close()
                    break
                except:

                    # we wait 20 seconds for the file to appear

                    time.sleep(1)
                    cnt += 1

            if not found:
                log.debug('very strange: portable tor started but hostname could not be read'
                          )
                log.debug('will use section [tor] and not [tor_portable]'
                          )
            else:

                # in portable mode we run Tor on some non-standard ports:
                # so we switch to the other set of config-options

                log.info('switching active config section from [tor] to [tor_portable]'
                         )
                TOR_CONFIG = 'tor_portable'

                # start the timer that will periodically check that tor is still running

                startPortableTorTimer()
        else:
            log.info('no own Tor instance. Settings in [tor] will be used'
                     )
    except:

        log.info('an error occured while starting tor, see traceback:')
        config.tb(1)

    log.info('changing working directory back to %s' % old_dir)
    os.chdir(old_dir)
    log.info('current working directory is %s' % os.getcwd())


def stopPortableTor():
    if not tor_pid:
        return
    else:
        log.info('tor has pid %i, terminating.' % tor_pid)
        config.killProcess(tor_pid)


def startPortableTorTimer():
    global tor_timer
    tor_timer = threading.Timer(10, onPortableTorTimer)
    tor_timer.start()


def onPortableTorTimer():
    if tor_proc.poll() != None:
        log.info('Tor stopped running. Will restart it now')
        startPortableTor()
    else:
        startPortableTorTimer()


