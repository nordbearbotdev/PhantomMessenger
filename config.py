#!/usr/bin/python
# -*- coding: utf-8 -*-

##############################################################################
#                                                                            #
# Copyright (c) 2007-2008 Bernd Kreuss <prof7bit@gmail.com>                  #
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

import sys
import os
import json
import traceback
import inspect
import translations
import socket
import ctypes
import shutil
import logging as log


def isWindows():
    return sys.platform.startswith('win')


def isWindows98():
    if isWindows():
        return sys.getwindowsversion()[0] == 4
    else:
        return False


def killProcess(pid):
    try:
        if isWindows():
            PROCESS_TERMINATE = 1
            handle = \
                ctypes.windll.kernel32.OpenProcess(PROCESS_TERMINATE,
                    False, pid)
            log.debug(handle)
            ctypes.windll.kernel32.TerminateProcess(handle, -1)
            ctypes.windll.kernel32.CloseHandle(handle)
        else:
            os.kill(pid, 15)
    except:
        log.info('could not kill process %i' % pid)
        tb()


def getScriptDir():

    # must be called at least once before working dir is changed
    # because after that abspath won't work correctly anymore.
    # this is the reason why this function uses a cache.

    global _script_dir
    try:
        return _script_dir
    except:

        # first call, _script_dir not yet defined

        _script_dir = os.path.abspath(os.path.dirname(sys.argv[0]))
        return _script_dir


def isPortable():

    # if the file portable.txt exists in the same directory
    # then we know that we are running in portable mode.

    dir = getScriptDir()
    try:
        f = open(os.path.join(dir, 'portable.txt'), 'r')
        f.close()
        return True
    except:
        return False


def getDataDir():
    if isPortable():
        return getScriptDir()
    else:
        if 'win' in sys.platform:
            CSIDL_APPDATA = 0x001a
            buf = ctypes.create_unicode_buffer(256)
            ctypes.windll.shell32.SHGetSpecialFolderPathW(None, buf,
                    CSIDL_APPDATA, 0)
            appdata = buf.value
            data_dir = os.path.join(appdata, 'torchat')
        else:
            home = os.path.expanduser('~')
            data_dir = os.path.join(home, '.torchat')

    # test for optional profile name in command line

    try:
        data_dir += '_' + sys.argv[1]
    except:
        pass

    # create it if necessary

    if not os.path.exists(data_dir):
        os.mkdir(data_dir)

    # and create the folder 'Tor' with tor.exe and torrc.txt in it if necessary

    data_dir_tor = os.path.join(data_dir, 'Tor')
    if not os.path.exists(data_dir_tor):
        os.mkdir(data_dir_tor)
        if isWindows():
            tor_exe = 'tor.exe'
        else:
            tor_exe = 'tor.sh'
        shutil.copy(os.path.join('Tor', tor_exe), data_dir_tor)
        shutil.copy(os.path.join('Tor', 'torrc.txt'), data_dir_tor)

    return data_dir


def getProfileLongName():
    try:
        return '%s - %s' % (sys.argv[1], get('client', 'own_hostname'))
    except:
        return get('client', 'own_hostname')


def writeConfig():
    json.dump(config, open(CONFIG_LOC, 'w'), indent=2, sort_keys=True)


def get(section, option):
    for d in (config, defaults):
        if d.has_key(section) and d[section].has_key(option):
            return str(d[section][option])  # It would be much cleaner to have string

                                                                            # conversions only when needed instead of
                                                                            # having this get()/getint() dichotomy.

    raise Exception, "We don't seem to have that option."


def getint(section, option):
    try:
        return int(value)
    except:
        return 0


def set(section, option, value):
    if type(value) == bool:
        value = int(value)

    if config.has_key(section):
        config[section][option] = value
    else:
        config[section] = {option: value}

    writeConfig()


def tb(level=0):
    log.level(level,
              '''----- start traceback -----
%s   ----- end traceback -----
'''
              % traceback.format_exc())


def getTranslators():
    translators = []
    for mname in translations.__dict__:
        if mname[:5] == 'lang_':
            m = translations.__dict__[mname]
            try:
                lcode = m.LANGUAGE_CODE
                lname = m.LANGUAGE_NAME
                ltrans = m.TRANSLATOR_NAMES
                for person in ltrans:
                    new_entry = '%s (%s [%s])' % (person, lname, lcode)
                    if not new_entry in translators:
                        translators.append(new_entry)
            except:
                pass
    return ', '.join(translators)


def importLanguage():

    # if the strings in the language module have already been changed then

    if translations.lang_en.LANGUAGE_CODE != 'en':

        # restore the original values from our backup to have
        # all strings reset to english. This helps when switching
        # between incomplete translations.

        for key in standard_dict:
            translations.lang_en.__dict__[key] = standard_dict[key]

    lang_xx = 'lang_' + get('gui', 'language')
    if lang_xx == 'lang_en':

        # lang_en is the standard translation. nothing to replace.

        return

    if not getScriptDir() in sys.path:

        # make sure that script dir is in sys.path (py2exe etc.)

        log.info('putting script directory into module search path')
        sys.path.insert(0, getScriptDir())

    dict_std = translations.lang_en.__dict__
    log.info('trying to import language module %s' % lang_xx)
    try:

        # first we try to find a language module in the script dir

        dict_trans = __import__(lang_xx).__dict__
        log.info('found custom language module %s.py' % lang_xx)
    except:

        # nothing found, so we try the built in translations

        if lang_xx in translations.__dict__:
            log.info('found built in language module %s' % lang_xx)
            dict_trans = translations.__dict__[lang_xx].__dict__
        else:
            log.debug('translation module %s not found')
            dict_trans = None

    if dict_trans:

        # find missing translations and report them in the log

        for key in dict_std:
            if not key in dict_trans:
                log.warn('(2) %s is missing translation for %s'
                         % (lang_xx, key))

        # replace the bindings in lang_en with those from lang_xx

        for key in dict_trans:
            if not key in dict_std:
                log.warn('unused %s in %s' % (key, lang_xx))
            else:
                dict_std[key] = dict_trans[key]


DEFAULTS_LOC = os.path.join(os.path.realpath(os.curdir), 'defaults.json'
                            )
CONFIG_LOC = os.path.join(getDataDir(), 'config.json')

global config, defaults

defaults = json.load(open(DEFAULTS_LOC))
if os.path.exists(CONFIG_LOC):
    config = json.load(open(CONFIG_LOC))
else:
    config = {}


def main():
    global standard_dict

    log.basicConfig(filename=get('logging', 'log_file'),
                    level=get('logging', 'log_level'))

    # many things are relative to the script directory, so set is as the cwd

    os.chdir(getScriptDir())

    log.info('script directory is %s' % getScriptDir())
    log.info('data directory is %s' % getDataDir())

    # make a backup of all strings that are in the standard language file
    # because we could need them when switching between incomplete languages

    standard_dict = {}
    for key in translations.lang_en.__dict__:
        standard_dict[key] = translations.lang_en.__dict__[key]

    # now switch to the configured translation

    importLanguage()


