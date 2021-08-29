#!/usr/bin/python
# -*- coding: utf-8 -*-

##############################################################################
#                                                                            #
# Copyright (c) 2021-2022 nordbearbot                                        #
#                                                                            #
# Translation file for Phantom.                                              #
#                                                                            #
##############################################################################

LANGUAGE_CODE = u'en'
LANGUAGE_NAME = u'English'
LANGUAGE_NAME_ENGLISH = u'English'
TRANSLATOR_NAMES = []

# buttons

BTN_CANCEL = u'Cancel'
BTN_OK = u'Ok'
BTN_SAVE_AS = u'Save as...'
BTN_CLOSE = u'Close'

# status

ST_AVAILABLE = u'Avaliable'
ST_AWAY = u'Away'
ST_EXTENDED_AWAY = u'Extended away'
ST_OFFLINE = u'Offline'

# TaskbarMenu

MTB_SHOW_HIDE_TORCHAT = u'Show/Hide TorChat'
MTB_QUIT = u'Quit'

# popup menu

MPOP_CHAT = u'Chat...'
MPOP_SEND_FILE = u'Send file...'
MPOP_EDIT_CONTACT = u'Edit contact...'
MPOP_DELETE_CONTACT = u'Delete contact...'
MPOP_SHOW_OFFLINE_MESSAGES = u'Show queued offline messages'
MPOP_CLEAR_OFFLINE_MESSAGES = u'Clear queued offline messages'
MPOP_ADD_CONTACT = u'Add contact...'
MPOP_ABOUT = u'About PhanomChat'
MPOP_ASK_AUTHOR = u'Ask %s...'
MPOP_SETTINGS = u'Settings...'

# chat window popup menu

CPOP_COPY = u'Copy'

# confirm delete message box

D_CONFIRM_DELETE_TITLE = u'Confirm deletion'
D_CONFIRM_DELETE_MESSAGE = u'Really delete this contact?\n(%s %s)'

# warning about log

D_LOG_WARNING_TITLE = u'Phantom: Logging is active'
D_LOG_WARNING_MESSAGE = \
    u'''Logging to file is activated!

Log File: %s

Remember to delete the log file if you have finished debugging because the log file may contain sensitive information.'''

# warning about used port

D_WARN_USED_PORT_TITLE = u'Phantom: Port already in use'
D_WARN_USED_PORT_MESSAGE = \
    u'Something, probably another Phantom instance, is already listening at %s:%s. You must create another profile using different ports to be able to start Phantom a second time.'

# warnig about unread messages

D_WARN_UNREAD_TITLE = u'Phantom: Unread messages'
D_WARN_UNREAD_MESSAGE = \
    u'''There are unread messages.
They will be lost forever!

Do you really want to exit Phantom now?'''

# warning about offline buddy

D_WARN_BUDDY_OFFLINE_TITLE = u'Phantom: Buddy is offline'
D_WARN_BUDDY_OFFLINE_MESSAGE = \
    u'This operation is not possible with offline buddies'

# warning about multiple files

D_WARN_FILE_ONLY_ONE_TITLE = u'Phantom: Multiple files'
D_WARN_FILE_ONLY_ONE_MESSAGE = \
    u'You may not start multiple file transfers with one operation. Start the transfers individually or send a zip-file instead'

# warning about file save error

D_WARN_FILE_SAVE_ERROR_TITLE = u'Phantom: Error saving file'
D_WARN_FILE_SAVE_ERROR_MESSAGE = \
    u"""The file '%s' could not be created.

%s"""

# warning about file already exists

D_WARN_FILE_ALREADY_EXISTS_TITLE = u'Phantom: File exists'
D_WARN_FILE_ALREADY_EXISTS_MESSAGE = \
    u"The file '%s' already exists.\nOverwrite it?"

# dialog: add/edit contact

DEC_TITLE_ADD = u'Add new contact'
DEC_TITLE_EDIT = u'Edit contact'
DEC_TORCHAT_ID = u'Phantom ID'
DEC_DISPLAY_NAME = u'Display name'
DEC_INTRODUCTION = u'Introduction'
DEC_MSG_16_CHARACTERS = \
    u'The address must be 16 characters long, not %i.'
DEC_MSG_ONLY_ALPANUM = \
    u'The address must only contain numbers and lowercase letters'
DEC_MSG_ALREADY_ON_LIST = u'%s is already on your list'

# file transfer window

DFT_FILE_OPEN_TITLE = u'Send file to %s'
DFT_FILE_SAVE_TITLE = u'Save file from %s'
DFT_SEND = u'''Sending %s
to %s
%04.1f%% (%i of %i bytes)'''
DFT_RECEIVE = u'''Receiving %s
from %s
%04.1f%% (%i of %i bytes)'''

# settings dialaog

DSET_TITLE = u'Phantom configuration'
DSET_NET_TITLE = u'Network'
DSET_NET_ACTIVE = u'active'
DSET_NET_INACTIVE = u'inactive'
DSET_NET_TOR_ADDRESS = u'Tor proxy address'
DSET_NET_TOR_SOCKS = u'Socks port'
DSET_NET_TOR_CONTROL = u'Control port'
DSET_NET_OWN_HOSTNAME = u'Own Phantom-ID'
DSET_NET_LISTEN_INTERFACE = u'Listen interface'
DSET_NET_LISTEN_PORT = u'Listen port'
DSET_GUI_TITLE = u'User interface'
DSET_GUI_LANGUAGE = u'Language'
DSET_GUI_OPEN_MAIN_HIDDEN = u'Start with minimized main window'
DSET_GUI_OPEN_CHAT_HIDDEN = u"Don't automatically open new windows"
DSET_GUI_NOTIFICATION_POPUP = u'Notification pop-up'
DSET_GUI_FLASH_WINDOW = u'Flash window title on new message'
DSET_MISC_TITLE = u'Misc'
DSET_MISC_TEMP_IN_DATA = u'Store temporary files inside data directory'
DSET_MISC_TEMP_CUSTOM_DIR = \
    u'Temporary directory (leave empty for OS-default)'

# notices in the chat window (those in square brackets)

NOTICE_DELAYED_MSG_WAITING = u'delayed messages waiting to be sent'
NOTICE_DELAYED_MSG_SENT = u'delayed messages have been sent'
NOTICE_DELAYED = u'delayed'

# messagebox for offline messages

MSG_OFFLINE_TITLE = u'Phantom: queued messages'
MSG_OFFLINE_EMPTY = u'there are no (more) queued messages for %s'
MSG_OFFLINE_QUEUED = u'''queued offline messages for %s:

%s'''

# about box

ABOUT_TITLE = u'About Phantom'
ABOUT_TEXT = \
    u"""Phantom %(version)s (svn: r%(svn)s)
  %(copyright)s

Translations:
  %(translators)s

Runtime environment:
  Python: %(python)s
  wx: %(wx)s

Phantom is free software: you can redistribute it and/or \
modify it under the terms of the GNU General Public \
License as published by the Free Software Foundation, \
either version 3 of the License, or (at your option) \
any later version.

TorChat is distributed in the hope that it will be useful, \
but WITHOUT ANY WARRANTY; without even the implied \
warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. \
See the GNU General Public License for more details.

*

And now for something completely different:

If you happen to run a software company near Hannover, Germany and \
are in need of a new coder, feel free to regard this little program \
as my application documents and drop me a mail with your answer.
"""
