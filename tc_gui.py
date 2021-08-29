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

# this is a graphical User interface for the Phantom client library.

import config
import logging as log
import wx
import tc_client
import sys
import os
import time
import subprocess
import textwrap
import threading
import version
import dlg_settings
import translations
lang = translations.lang_en

ICON_NAMES = {
    tc_client.STATUS_OFFLINE: 'offline.png',
    tc_client.STATUS_ONLINE: 'online.png',
    tc_client.STATUS_HANDSHAKE: 'connecting.png',
    tc_client.STATUS_AWAY: 'away.png',
    tc_client.STATUS_XA: 'xa.png',
    }

_icon_images = {}  # this is a cache for getStatusBitmap()


def getStatusBitmap(status):
    global _icon_images
    if not status in _icon_images:
        image = wx.Image(os.path.join(config.get('internal', 'icon_dir'
                         ), ICON_NAMES[status]), wx.BITMAP_TYPE_PNG)
        image.ConvertAlphaToMask()
        _icon_images[status] = image
    bitmap = _icon_images[status].ConvertToBitmap()
    return bitmap


class TaskbarIcon(wx.TaskBarIcon):

    def __init__(self, main_window):
        wx.TaskBarIcon.__init__(self)
        self.mw = main_window
        self.showStatus(self.mw.buddy_list.own_status)
        self.timer = wx.Timer(self, -1)
        self.blink_phase = False
        self.Bind(wx.EVT_TASKBAR_LEFT_DOWN, self.onLeftClick)
        self.Bind(wx.EVT_TIMER, self.onTimer)

    def showEvent(self):
        try:
            icon = wx.IconFromBitmap(self.img_event.ConvertToBitmap())
        except:
            img = wx.Image(os.path.join(config.get('internal',
                           'icon_dir'), 'event.png'))
            img.ConvertAlphaToMask()
            self.img_event = img
            icon = wx.IconFromBitmap(self.img_event.ConvertToBitmap())
        self.SetIcon(icon, self.getToolTipText())

    def showStatus(self, status):
        icon = wx.IconFromBitmap(getStatusBitmap(status))
        self.SetIcon(icon, self.getToolTipText())

    def onLeftClick(self, evt):
        self.mw.Show(not self.mw.IsShown())

    def CreatePopupMenu(self):
        return TaskbarMenu(self.mw)

    def getToolTipText(self):
        text = 'TorChat: %s' % config.getProfileLongName()
        for window in self.mw.chat_windows:
            if not window.IsShown():
                text += '\n' + window.getTitleShort()
        return text

    def blink(self, start=True):
        if start:
            self.timer.Start(500, False)
        else:
            self.timer.Stop()
            self.showStatus(self.mw.buddy_list.own_status)

    def onTimer(self, evt):
        self.blink_phase = not self.blink_phase
        if self.blink_phase:
            self.showStatus(self.mw.buddy_list.own_status)
        else:
            self.showEvent()

        # stop blinking, if there are no more hidden windows

        found = False
        for window in self.mw.chat_windows:
            if not window.IsShown():
                found = True
                break

        if not found:
            self.blink(False)


class TaskbarMenu(wx.Menu):

    def __init__(self, main_window):
        wx.Menu.__init__(self)
        self.mw = main_window
        self.mw.taskbar_icon.blink(False)

        # show/hide

        item = wx.MenuItem(self, wx.NewId(), lang.MTB_SHOW_HIDE_TORCHAT)
        self.AppendItem(item)
        self.Bind(wx.EVT_MENU, self.onShowHide, item)

        self.AppendSeparator()

        # (hidden) chat windows

        cnt = 0
        self.wnd = {}
        for window in self.mw.chat_windows:
            if not window.IsShown():
                id = wx.NewId()
                self.wnd[id] = window
                item = wx.MenuItem(self, id, window.getTitleShort())
                item.SetBitmap(getStatusBitmap(window.buddy.status))
                self.AppendItem(item)
                self.Bind(wx.EVT_MENU, self.onChatWindow, item)
                cnt += 1

        if cnt:
            self.AppendSeparator()

        # status

        item = wx.MenuItem(self, wx.NewId(), lang.ST_AVAILABLE)
        item.SetBitmap(getStatusBitmap(tc_client.STATUS_ONLINE))
        self.AppendItem(item)
        self.Bind(wx.EVT_MENU, self.onAvailable, item)

        item = wx.MenuItem(self, wx.NewId(), lang.ST_AWAY)
        item.SetBitmap(getStatusBitmap(tc_client.STATUS_AWAY))
        self.AppendItem(item)
        self.Bind(wx.EVT_MENU, self.onAway, item)

        item = wx.MenuItem(self, wx.NewId(), lang.ST_EXTENDED_AWAY)
        item.SetBitmap(getStatusBitmap(tc_client.STATUS_XA))
        self.AppendItem(item)
        self.Bind(wx.EVT_MENU, self.onXA, item)

        self.AppendSeparator()

        # quit

        item = wx.MenuItem(self, wx.NewId(), lang.MTB_QUIT)
        self.AppendItem(item)
        self.Bind(wx.EVT_MENU, self.onExit, item)

    def onShowHide(self, evt):
        self.mw.Show(not self.mw.IsShown())

    def onChatWindow(self, evt):
        self.wnd[evt.GetId()].Show()

        # force update of the tooltip text (window list)

        self.mw.taskbar_icon.showStatus(self.mw.buddy_list.own_status)

    def onExit(self, evt):
        self.mw.exitProgram()

    def onAvailable(self, evt):
        self.mw.status_switch.setStatus(tc_client.STATUS_ONLINE)

    def onAway(self, evt):
        self.mw.status_switch.setStatus(tc_client.STATUS_AWAY)

    def onXA(self, evt):
        self.mw.status_switch.setStatus(tc_client.STATUS_XA)


class NotificationWindowAnimation(threading.Thread):

    def __init__(self, win):
        threading.Thread.__init__(self)
        self.win = win
        self.start()

    def run(self):
        (cx, cy, maxx, maxy) = wx.ClientDisplayRect()
        (w, h) = self.win.GetSize()
        self.x_end = maxx - w - 20
        self.y_end = maxy - h - 20
        self.win.SetPosition((-w, self.y_end))
        wx.CallAfter(self.win.Show)
        for x in range(-w, self.x_end, 20):
            wx.CallAfter(self.win.SetPosition, (x, self.y_end))
            time.sleep(0.01)
        wx.CallAfter(self.win.SetPosition, (self.x_end, self.y_end))

        time.sleep(5)

        (w, h) = self.win.GetSize()
        for y in reversed(range(-h, self.y_end, 20)):
            wx.CallAfter(self.win.SetPosition, (self.x_end, y))
            time.sleep(0.01)
        wx.CallAfter(self.win.Hide)
        wx.CallAfter(self.win.Close)


class NotificationWindow(wx.PopupWindow):

    def __init__(self, mw, text):
        wx.PopupWindow.__init__(self, mw)
        self.panel = wx.Panel(self)
        sizer = wx.BoxSizer()
        self.panel.SetSizer(sizer)

        bitmap = wx.Bitmap(config.get('internal', 'icon_dir')
                           + '/phantom.png', wx.BITMAP_TYPE_PNG)
        static_image = wx.StaticBitmap(self.panel, -1, bitmap)
        sizer.Add(static_image, 0, wx.ALL, 5)

        self.label = wx.StaticText(self.panel)
        font = self.label.GetFont()
        font.SetPointSize(12)
        self.label.SetFont(font)
        self.label.SetLabel(text)
        sizer.Add(self.label, 0, wx.ALL, 5)

        wsizer = wx.BoxSizer()
        wsizer.Add(self.panel, 0, wx.ALL, 0)
        self.SetSizerAndFit(wsizer)
        self.Layout()

        self.a = NotificationWindowAnimation(self)


class PopupMenu(wx.Menu):

    def __init__(self, main_window, type):
        wx.Menu.__init__(self)
        self.mw = main_window

        # options for buddy

        if type == 'contact':
            item = wx.MenuItem(self, wx.NewId(), lang.MPOP_CHAT)
            self.AppendItem(item)
            self.Bind(wx.EVT_MENU, self.mw.gui_bl.onDClick, item)

            item = wx.MenuItem(self, wx.NewId(), lang.MPOP_SEND_FILE)
            self.AppendItem(item)
            self.Bind(wx.EVT_MENU, self.onSendFile, item)

            item = wx.MenuItem(self, wx.NewId(),
                               lang.MPOP_SHOW_OFFLINE_MESSAGES)
            self.AppendItem(item)
            self.Bind(wx.EVT_MENU, self.onShowOffline, item)

            item = wx.MenuItem(self, wx.NewId(),
                               lang.MPOP_CLEAR_OFFLINE_MESSAGES)
            self.AppendItem(item)
            self.Bind(wx.EVT_MENU, self.onClearOffline, item)

            self.AppendSeparator()

            item = wx.MenuItem(self, wx.NewId(), lang.MPOP_EDIT_CONTACT)
            self.AppendItem(item)
            self.Bind(wx.EVT_MENU, self.onEdit, item)

            item = wx.MenuItem(self, wx.NewId(),
                               lang.MPOP_DELETE_CONTACT)
            self.AppendItem(item)
            self.Bind(wx.EVT_MENU, self.onDelete, item)

            self.AppendSeparator()

        item = wx.MenuItem(self, wx.NewId(), lang.MPOP_ADD_CONTACT)
        self.AppendItem(item)
        self.Bind(wx.EVT_MENU, self.onAdd, item)

        # ask bernd

        item = wx.MenuItem(self, wx.NewId(), lang.MPOP_ASK_AUTHOR
                           % config.get('internal', 'authors_name'))
        self.AppendItem(item)
        self.Bind(wx.EVT_MENU, self.onAskAuthor, item)

        self.AppendSeparator()

        # settings

        item = wx.MenuItem(self, wx.NewId(), lang.MPOP_SETTINGS)
        self.AppendItem(item)
        self.Bind(wx.EVT_MENU, self.onSettings, item)

        # about

        item = wx.MenuItem(self, wx.NewId(), lang.MPOP_ABOUT)
        self.AppendItem(item)
        self.Bind(wx.EVT_MENU, self.onAbout, item)

        # exit program

        self.AppendSeparator()
        item = wx.MenuItem(self, wx.NewId(), lang.MTB_QUIT)
        self.AppendItem(item)
        self.Bind(wx.EVT_MENU, self.onQuit, item)

    def onSendFile(self, evt):
        buddy = self.mw.gui_bl.getSelectedBuddy()
        title = lang.DFT_FILE_OPEN_TITLE \
            % buddy.getAddressAndDisplayName()
        dialog = wx.FileDialog(self.mw, title, style=wx.OPEN
                               | wx.FD_PREVIEW)
        if dialog.ShowModal() == wx.ID_OK:
            file_name = dialog.GetPath()
            transfer_window = FileTransferWindow(self.mw, buddy,
                    file_name)

    def onEdit(self, evt):
        buddy = self.mw.gui_bl.getSelectedBuddy()
        dialog = DlgEditContact(self.mw, self.mw, buddy)
        dialog.ShowModal()

    def onDelete(self, evt):
        buddy = self.mw.gui_bl.getSelectedBuddy()
        answer = wx.MessageBox(lang.D_CONFIRM_DELETE_MESSAGE
                               % (buddy.address, buddy.name),
                               lang.D_CONFIRM_DELETE_TITLE, wx.YES_NO
                               | wx.NO_DEFAULT)
        if answer == wx.YES:

            # remove from list without disconnecting
            # this will send a remove_me message
            # the other buddy will then disconnect,
            # because there is not much it can do with the
            # connections anymore.

            self.mw.buddy_list.removeBuddy(buddy, disconnect=False)

    def onShowOffline(self, event):
        buddy = self.mw.gui_bl.getSelectedBuddy()
        om = buddy.getOfflineMessages()
        if om:
            om = lang.MSG_OFFLINE_QUEUED % (buddy.address, om)
        else:
            om = lang.MSG_OFFLINE_EMPTY % buddy.address
        wx.MessageBox(om, lang.MSG_OFFLINE_TITLE, wx.ICON_INFORMATION)

    def onClearOffline(self, evt):
        buddy = self.mw.gui_bl.getSelectedBuddy()
        try:
            os.unlink(buddy.getOfflineFileName())
        except:
            pass

    def onAdd(self, evt):
        dialog = DlgEditContact(self.mw, self.mw)
        dialog.ShowModal()

    def onSettings(self, evt):
        dialog = dlg_settings.Dialog(self.mw)
        dialog.ShowModal()

    def onAbout(self, evt):
        wx.MessageBox(lang.ABOUT_TEXT % {
            'version': version.VERSION,
            'svn': version.VERSION_SVN,
            'copyright': config.get('internal', 'copyright'),
            'python': '.'.join(str(x) for x in sys.version_info),
            'wx': wx.version(),
            'translators': config.getTranslators(),
            }, lang.ABOUT_TITLE)

    def onAskAuthor(self, evt):
        if self.mw.buddy_list.getBuddyFromAddress(config.get('internal'
                , 'authors_id')):
            wx.MessageBox(lang.DEC_MSG_ALREADY_ON_LIST
                          % config.get('internal', 'authors_name'))
        else:
            dialog = DlgEditContact(self.mw, self.mw, add_author=True)
            dialog.ShowModal()

    def onQuit(self, evt):
        self.mw.exitProgram()


class DlgEditContact(wx.Dialog):

    def __init__(  # no buddy -> Add new
        self,
        parent,
        main_window,
        buddy=None,
        add_author=False,
        ):
        wx.Dialog.__init__(self, parent, -1)
        self.mw = main_window
        self.bl = self.mw.buddy_list
        self.buddy = buddy
        if buddy == None:
            self.SetTitle(lang.DEC_TITLE_ADD)
            address = ''
            name = ''
        else:
            self.SetTitle(lang.DEC_TITLE_EDIT)
            address = buddy.address
            name = buddy.name

        self.panel = wx.Panel(self)

        # setup the sizers

        sizer = wx.GridBagSizer(vgap=5, hgap=5)
        box_sizer = wx.BoxSizer()
        box_sizer.Add(sizer, 1, wx.EXPAND | wx.ALL, 5)

        # address

        row = 0
        lbl = wx.StaticText(self.panel, -1, lang.DEC_TORCHAT_ID)
        sizer.Add(lbl, (row, 0))

        self.txt_address = wx.TextCtrl(self.panel, -1, address)
        self.txt_address.SetMinSize((250, -1))
        sizer.Add(self.txt_address, (row, 1), (1, 2))

        # name

        row += 1
        lbl = wx.StaticText(self.panel, -1, lang.DEC_DISPLAY_NAME)
        sizer.Add(lbl, (row, 0))

        self.txt_name = wx.TextCtrl(self.panel, -1, name)
        self.txt_name.SetMinSize((250, -1))
        sizer.Add(self.txt_name, (row, 1), (1, 2))

        # add-me message (new buddies)

        if not self.buddy:
            row += 1
            lbl = wx.StaticText(self.panel, -1, lang.DEC_INTRODUCTION)
            sizer.Add(lbl, (row, 0))

            self.txt_intro = wx.TextCtrl(self.panel, -1,
                    'hello, my friend...')
            self.txt_intro.SetMinSize((250, -1))
            sizer.Add(self.txt_intro, (row, 1), (1, 2))

        if add_author:
            self.txt_address.SetValue(config.get('internal',
                    'authors_id'))
            self.txt_name.SetValue(config.get('internal', 'authors_name'
                                   ))

        # buttons

        row += 1
        self.btn_cancel = wx.Button(self.panel, -1, lang.BTN_CANCEL)
        sizer.Add(self.btn_cancel, (row, 1), flag=wx.EXPAND)

        self.btn_ok = wx.Button(self.panel, -1, lang.BTN_OK)
        self.btn_ok.SetDefault()
        sizer.Add(self.btn_ok, (row, 2), flag=wx.EXPAND)

        # fit the sizers

        self.panel.SetSizer(box_sizer)
        box_sizer.Fit(self)

        # bind the events

        self.btn_cancel.Bind(wx.EVT_BUTTON, self.onCancel)
        self.btn_ok.Bind(wx.EVT_BUTTON, self.onOk)

    def onOk(self, evt):
        address = self.txt_address.GetValue().rstrip().lstrip()
        if len(address) != 16:
            l = len(address)
            wx.MessageBox(lang.DEC_MSG_16_CHARACTERS % l)
            return

        for c in address:
            if c not in '0123456789abcdefghijklmnopqrstuvwxyz':
                wx.MessageBox(lang.DEC_MSG_ONLY_ALPANUM)
                return

        if self.buddy == None:
            buddy = tc_client.Buddy(address, self.bl,
                                    self.txt_name.GetValue())
            res = self.bl.addBuddy(buddy)
            if res == False:
                wx.MessageBox(lang.DEC_MSG_ALREADY_ON_LIST % address)
            else:
                buddy.storeOfflineChatMessage(self.txt_intro.GetValue())
        else:
            address_old = self.buddy.address
            offline_file_name_old = self.buddy.getOfflineFileName()
            self.buddy.address = address
            offline_file_name_new = self.buddy.getOfflineFileName()
            self.buddy.name = self.txt_name.GetValue()
            self.bl.save()
            if address != address_old:
                self.buddy.disconnect()
                try:
                    os.rename(offline_file_name_old,
                              offline_file_name_new)
                except:
                    pass

        self.Close()

    def onCancel(self, evt):
        self.Close()


class BuddyList(wx.ListCtrl):

    def __init__(self, parent, main_window):
        wx.ListCtrl.__init__(self, parent, -1, style=wx.LC_REPORT
                             | wx.LC_NO_HEADER)
        self.mw = main_window
        self.bl = self.mw.buddy_list

        self.InsertColumn(0, 'buddy')

        self.r_down = False

        self.il = wx.ImageList(16, 16)
        self.il_idx = {}
        for status in [tc_client.STATUS_OFFLINE,
                       tc_client.STATUS_HANDSHAKE,
                       tc_client.STATUS_ONLINE, tc_client.STATUS_AWAY,
                       tc_client.STATUS_XA]:
            self.il_idx[status] = self.il.Add(getStatusBitmap(status))

        img_event = wx.Image(os.path.join(config.get('internal',
                             'icon_dir'), 'event.png'))
        img_event.ConvertAlphaToMask()
        self.il_idx[100] = self.il.Add(img_event.ConvertToBitmap())

        self.SetImageList(self.il, wx.IMAGE_LIST_SMALL)
        self.blink_phase = False

        self.timer = wx.Timer(self, -1)
        self.Bind(wx.EVT_TIMER, self.onTimer, self.timer)
        self.old_sum = ''
        self.timer.Start(milliseconds=500, oneShot=False)

        self.Bind(wx.EVT_LEFT_DCLICK, self.onDClick)
        self.Bind(wx.EVT_LIST_ITEM_RIGHT_CLICK, self.onRClick)
        self.Bind(wx.EVT_RIGHT_DOWN, self.onRDown)

    def blinkBuddy(self, buddy, blink=True):
        name = buddy.getDisplayName()
        for index in xrange(0, self.GetItemCount()):
            if name == self.GetItemText(index):
                if blink:
                    if self.blink_phase:
                        self.SetItemImage(index, self.il_idx[100])
                    else:
                        self.SetItemImage(index,
                                self.il_idx[buddy.status])
                else:
                    self.SetItemImage(index, self.il_idx[buddy.status])

    def onTimer(self, evt):

        # first check if there have been any changes to the buddy list

        sum = ''
        for buddy in self.bl.list:
            sum += buddy.address + buddy.name + str(buddy.status)
        if sum != self.old_sum:

            # FIXME: This whole method is more than ugly
            # remove items which are not in list anymore

            for index in xrange(0, self.GetItemCount()):
                found = False
                for buddy in self.bl.list:
                    if buddy.getDisplayName() \
                        == self.GetItemText(index):
                        found = True
                        break
                if not found:
                    self.DeleteItem(index)
                    break

            # add new items to the list or change status icons

            for buddy in self.bl.list:
                line = buddy.getDisplayName()
                index = self.FindItem(0, line)
                if index == -1:
                    index = self.InsertImageStringItem(sys.maxint,
                            line, self.il_idx[tc_client.STATUS_OFFLINE])
                    self.SetColumnWidth(0, wx.LIST_AUTOSIZE)
                self.SetItemImage(index, self.il_idx[buddy.status])

            self.old_sum = sum

        # always: show unread messages

        self.blink_phase = not self.blink_phase
        for buddy in self.bl.list:
            found = False
            for window in self.mw.chat_windows:
                if not window.IsShown() and window.buddy == buddy:
                    found = True
                    break
            if found:
                self.blinkBuddy(buddy, True)
            else:
                self.blinkBuddy(buddy, False)

    def onDClick(self, evt):
        i = self.GetFirstSelected()
        address = self.GetItemText(i)[0:16]
        for buddy in self.bl.list:
            if buddy.address == address:
                found_window = False
                for window in self.mw.chat_windows:
                    if window.buddy == buddy:
                        found_window = True
                        break

                if not found_window:
                    window = ChatWindow(self.mw, buddy)

                if not window.IsShown():
                    window.Show()

                window.txt_out.SetFocus()
                break

        evt.Skip()

    def onRClick(self, evt):
        (index, flags) = self.HitTest(evt.GetPosition())
        if index != -1:
            self.mw.PopupMenu(PopupMenu(self.mw, 'contact'))

    def onRDown(self, evt):
        (index, flags) = self.HitTest(evt.GetPosition())
        if index == -1:
            self.mw.PopupMenu(PopupMenu(self.mw, 'empty'))
        else:
            evt.Skip()

    def getSelectedBuddy(self):
        index = self.GetFirstSelected()
        addr = self.GetItemText(index)[0:16]
        return self.bl.getBuddyFromAddress(addr)


class StatusSwitchList(wx.Menu):

    def __init__(self, status_switch):
        wx.Menu.__init__(self)
        self.status_switch = status_switch

        item = wx.MenuItem(self, wx.NewId(), lang.ST_AVAILABLE)
        item.SetBitmap(getStatusBitmap(tc_client.STATUS_ONLINE))
        self.AppendItem(item)
        self.Bind(wx.EVT_MENU, self.status_switch.onAvailable, item)

        item = wx.MenuItem(self, wx.NewId(), lang.ST_AWAY)
        item.SetBitmap(getStatusBitmap(tc_client.STATUS_AWAY))
        self.AppendItem(item)
        self.Bind(wx.EVT_MENU, self.status_switch.onAway, item)

        item = wx.MenuItem(self, wx.NewId(), lang.ST_EXTENDED_AWAY)
        item.SetBitmap(getStatusBitmap(tc_client.STATUS_XA))
        self.AppendItem(item)
        self.Bind(wx.EVT_MENU, self.status_switch.onXA, item)


class StatusSwitch(wx.Button):

    def __init__(self, parent, main_window):
        wx.Button.__init__(self, parent)
        self.parent = parent
        self.main_window = main_window
        self.status = self.main_window.buddy_list.own_status
        self.Bind(wx.EVT_BUTTON, self.onClick)
        self.setStatus(self.main_window.buddy_list.own_status)

    def onClick(self, evt):
        self.PopupMenu(StatusSwitchList(self))

    def onAvailable(self, evt):
        self.setStatus(tc_client.STATUS_ONLINE)

    def onAway(self, evt):
        self.setStatus(tc_client.STATUS_AWAY)

    def onXA(self, evt):
        self.setStatus(tc_client.STATUS_XA)

    def setStatus(self, status):
        self.status = status
        self.main_window.setStatus(status)
        if status == tc_client.STATUS_AWAY:
            status_text = lang.ST_AWAY
        if status == tc_client.STATUS_XA:
            status_text = lang.ST_EXTENDED_AWAY
        if status == tc_client.STATUS_ONLINE:
            status_text = lang.ST_AVAILABLE
        if status == tc_client.STATUS_OFFLINE:
            status_text = lang.ST_OFFLINE
        self.SetLabel(status_text)


class ChatWindow(wx.Frame):

    def __init__(
        self,
        main_window,
        buddy,
        message='',
        hidden=False,
        notify_offline_sent=False,
        ):

        wx.Frame.__init__(self, main_window, -1, size=(400, 400))

        self.mw = main_window
        self.buddy = buddy
        self.unread = 0
        self.updateTitle()

        self.panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)

        self.txt_in = wx.TextCtrl(self.panel, -1, style=wx.TE_READONLY
                                  | wx.TE_MULTILINE | wx.TE_AUTO_URL
                                  | wx.TE_AUTO_SCROLL | wx.TE_RICH2
                                  | wx.BORDER_SUNKEN)

        sizer.Add(self.txt_in, 1, wx.EXPAND | wx.ALL, 0)

        self.txt_out = wx.TextCtrl(self.panel, -1,
                                   style=wx.TE_MULTILINE | wx.TE_RICH2
                                   | wx.BORDER_SUNKEN)

        sizer.Add(self.txt_out, 0, wx.EXPAND | wx.ALL, 0)

        sizer.SetItemMinSize(self.txt_out, (-1, 50))

        self.panel.SetSizer(sizer)
        sizer.FitInside(self)

        om = self.buddy.getOfflineMessages()
        if om:
            om = '[%s]\n' % lang.NOTICE_DELAYED_MSG_WAITING + om
            self.writeColored((0, 0, 192), 'myself', om)

        if message != '':
            self.process(message)

        if notify_offline_sent:
            self.notifyOfflineSent()

        self.timer = wx.Timer(self, -1)
        self.timer.Start(1000, False)
        self.onTimer(None)

        self.Bind(wx.EVT_TIMER, self.onTimer)
        self.Bind(wx.EVT_CLOSE, self.onClose)
        self.txt_out.Bind(wx.EVT_KEY_DOWN, self.onKey)
        self.txt_in.Bind(wx.EVT_TEXT_URL, self.onURL)

        self.Bind(wx.EVT_ACTIVATE, self.onActivate)
        self.txt_in.Bind(wx.EVT_CONTEXT_MENU, self.OnContextMenu)

        self.drop_target_in = FileDropTarget(self)
        self.drop_target_out = FileDropTarget(self)
        self.txt_in.SetDropTarget(self.drop_target_in)
        self.txt_out.SetDropTarget(self.drop_target_out)

        if not hidden:
            self.Show()

        self.mw.chat_windows.append(self)

    def updateTitle(self):
        if self.unread == 1:
            title = '* '
        elif self.unread > 1:
            title = '*[%i] ' % self.unread
        else:
            title = ''

        title += self.buddy.address
        if self.buddy.name != '':
            title += ' (%s)' % self.buddy.name

        self.SetTitle(title + ' %s' % config.getProfileLongName())

    def getTitleShort(self):
        t = self.GetTitle()
        return t[:-19]

    def writeColored(
        self,
        color,
        name,
        text,
        ):
        self.txt_in.SetDefaultStyle(wx.TextAttr(wx.Color(128, 128,
                                    128)))
        self.txt_in.write('%s ' % time.strftime(config.get('gui',
                          'time_stamp_format')))
        (red, green, blue) = color
        self.txt_in.SetDefaultStyle(wx.TextAttr(wx.Color(red, green,
                                    blue)))
        self.txt_in.write('%s: ' % name)
        self.txt_in.SetDefaultStyle(wx.TextAttr(wx.Color(0, 0, 0)))
        self.txt_in.write('%s\n' % text)

        # workaround scroll bug on windows
        # https://sourceforge.net/tracker/?func=detail&atid=109863&aid=665381&group_id=9863

        self.txt_in.ScrollLines(-1)
        self.txt_in.ShowPosition(self.txt_in.GetLastPosition())

    def notify(self, name, message):

        # needs unicode

        if not self.IsActive():
            if config.getint('gui', 'notification_flash_window'):
                self.RequestUserAttention(wx.USER_ATTENTION_INFO)
            self.unread += 1
            self.updateTitle()

            if config.getint('gui', 'notification_popup'):
                nt = textwrap.fill('%s:\n%s' % (name, message), 40)
                try:
                    NotificationWindow(self.mw, nt)
                except:

                    # Some platforms (Mac) dont have wx.PopupWindow
                    # FIXME: need alternative solution

                    pass

        if not self.IsShown():
            self.mw.taskbar_icon.blink()

    def notifyOfflineSent(self):

        # all should be unicode here

        message = '[%s]' % lang.NOTICE_DELAYED_MSG_SENT
        self.writeColored((0, 0, 192), 'myself', message)
        self.notify('to %s' % self.buddy.address, message)

    def process(self, message):

        # message must be unicode

        if self.buddy.name != '':
            name = self.buddy.name
        else:
            name = self.buddy.address
        self.writeColored((192, 0, 0), name, message)
        self.notify(name, message)

    def onActivate(self, evt):
        self.unread = 0
        self.updateTitle()
        evt.Skip()

    def onClose(self, evt):
        self.mw.chat_windows.remove(self)
        self.Destroy()

    def onKey(self, evt):
        if evt.GetKeyCode() == 13 and not evt.ShiftDown():
            self.onSend(evt)
        else:
            evt.Skip()

    def onSend(self, evt):
        evt.Skip()
        text = self.txt_out.GetValue().rstrip().lstrip()
        wx.CallAfter(self.txt_out.SetValue, '')
        if self.buddy.status not in [tc_client.STATUS_OFFLINE,
                tc_client.STATUS_HANDSHAKE]:
            self.buddy.sendChatMessage(text)
            self.writeColored((0, 0, 192), 'myself', text)
        else:
            self.buddy.storeOfflineChatMessage(text)
            self.writeColored((0, 0, 192), 'myself', '[%s] %s'
                              % (lang.NOTICE_DELAYED, text))

    def onTimer(self, evt):
        bmp = getStatusBitmap(self.buddy.status)
        icon = wx.IconFromBitmap(bmp)
        self.SetIcon(icon)

    def onURL(self, evt):

        # all URL mouse events trigger this

        if evt.GetMouseEvent().GetEventType() == wx.wxEVT_LEFT_DOWN:

            # left button down, now we need the URL

            start = evt.GetURLStart()
            end = evt.GetURLEnd()
            url = self.txt_in.GetRange(start, end)
            if config.isWindows():

                # this works very reliable

                subprocess.Popen(('cmd /c start %s' % url).split(),
                                 creationflags=0x08000000)
            else:

                # FIXME: is this the way to go? better make it a config option.

                subprocess.Popen(('/etc/alternatives/x-www-browser %s'
                                 % url).split())
        else:
            evt.Skip()

    def OnContextMenu(self, evt):
        menu = wx.Menu()

        id = wx.NewId()
        item = wx.MenuItem(menu, id, lang.CPOP_COPY)
        self.Bind(wx.EVT_MENU, self.onCopy, id=id)
        menu.AppendItem(item)
        (sel_from, sel_to) = self.txt_in.GetSelection()
        empty = sel_from == sel_to
        if empty:
            item.Enable(False)

        id = wx.NewId()
        item = wx.MenuItem(menu, id, lang.MPOP_SEND_FILE)
        self.Bind(wx.EVT_MENU, self.onSendFile, id=id)
        menu.AppendItem(item)

        id = wx.NewId()
        item = wx.MenuItem(menu, id, lang.MPOP_EDIT_CONTACT)
        self.Bind(wx.EVT_MENU, self.onEditBuddy, id=id)
        menu.AppendItem(item)

        self.PopupMenu(menu)
        menu.Destroy()

    def onCopy(self, evt):
        (sel_from, sel_to) = self.txt_in.GetSelection()
        if sel_from == sel_to:
            return
        text = self.txt_in.GetRange(sel_from, sel_to)
        clipdata = wx.TextDataObject()
        clipdata.SetText(text)
        wx.TheClipboard.Open()
        wx.TheClipboard.SetData(clipdata)
        wx.TheClipboard.Close()

    def onSendFile(self, evt):
        title = lang.DFT_FILE_OPEN_TITLE \
            % self.buddy.getAddressAndDisplayName()
        dialog = wx.FileDialog(self, title, style=wx.OPEN
                               | wx.FD_PREVIEW)
        if dialog.ShowModal() == wx.ID_OK:
            file_name = dialog.GetPath()
            transfer_window = FileTransferWindow(self.mw, self.buddy,
                    file_name)

    def onEditBuddy(self, evt):
        dialog = DlgEditContact(self, self.mw, self.buddy)
        dialog.ShowModal()


class FileDropTarget(wx.FileDropTarget):

    def __init__(self, window):
        wx.FileDropTarget.__init__(self)
        self.window = window

    def OnDropFiles(
        self,
        x,
        y,
        filenames,
        ):
        if len(filenames) != 1:
            wx.MessageBox(lang.D_WARN_FILE_ONLY_ONE_MESSAGE,
                          lang.D_WARN_FILE_ONLY_ONE_TITLE)
            return

        file_name = filenames[0]

        # --- begin evel hack

        if not os.path.exists(file_name):

            # sometimes the file name is in utf8
            # but inside a unicode object!
            # FIXME: must report this bug to wx

            try:
                file_name_utf8 = ''
                for c in file_name:
                    file_name_utf8 += chr(ord(c))
                file_name = file_name_utf8.decode('utf-8')
            except:
                config.tb()
                wx.MessageBox('there is a strange bug in wx for your platform with wx.FileDropTarget and non-ascii characters in file names'
                              )
                return

        # --- end evel hack

        log.warn('file dropped: %s' % file_name)

        if not self.window.buddy.conn_in:
            wx.MessageBox(lang.D_WARN_BUDDY_OFFLINE_MESSAGE,
                          lang.D_WARN_BUDDY_OFFLINE_TITLE)
            return

        transfer_window = FileTransferWindow(self.window.mw,
                self.window.buddy, file_name)


class FileTransferWindow(wx.Frame):

    def __init__(
        self,
        main_window,
        buddy,
        file_name,
        receiver=None,
        ):

        # if receiver is given (a FileReceiver instance) we initialize
        # a Receiver Window, else we initialize a sender window and
        # let the client library create us a FileSender instance

        wx.Frame.__init__(self, main_window, -1)
        self.mw = main_window
        self.buddy = buddy

        self.bytes_total = 1
        self.bytes_complete = 0
        self.file_name = file_name
        self.file_name_save = ''
        self.completed = False
        self.error = False

        if not receiver:
            self.is_receiver = False
            self.transfer_object = self.buddy.sendFile(self.file_name,
                    self.onDataChange)
        else:
            self.is_receiver = True
            receiver.setCallbackFunction(self.onDataChange)
            self.transfer_object = receiver
            self.bytes_total = receiver.file_size
            self.file_name = file_name

        self.panel = wx.Panel(self)
        self.outer_sizer = wx.BoxSizer()
        grid_sizer = wx.GridBagSizer(vgap=5, hgap=5)
        grid_sizer.AddGrowableCol(0)
        self.outer_sizer.Add(grid_sizer, 1, wx.EXPAND | wx.ALL, 5)

        self.text = wx.StaticText(self.panel, -1, '')
        self.text.SetMinSize((300, -1))
        grid_sizer.Add(self.text, (0, 0), (1, 4), wx.EXPAND)

        self.progress_bar = wx.Gauge(self.panel)
        grid_sizer.Add(self.progress_bar, (1, 0), (1, 4), wx.EXPAND)

        self.btn_cancel = wx.Button(self.panel, wx.ID_CANCEL,
                                    lang.BTN_CANCEL)
        self.btn_cancel.Bind(wx.EVT_BUTTON, self.onCancel)

        if self.is_receiver:
            grid_sizer.Add(self.btn_cancel, (2, 2))

            self.btn_save = wx.Button(self.panel, wx.ID_SAVEAS,
                    lang.BTN_SAVE_AS)
            grid_sizer.Add(self.btn_save, (2, 3))
            self.btn_save.Bind(wx.EVT_BUTTON, self.onSave)
        else:
            grid_sizer.Add(self.btn_cancel, (2, 3))

        self.panel.SetSizer(self.outer_sizer)
        self.updateOutput()
        self.outer_sizer.Fit(self)

        self.Show()

    def updateOutput(self):
        if self.bytes_complete == -1:
            self.error = True
            self.completed = True
            self.bytes_complete = 0

        percent = 100.0 * self.bytes_complete / self.bytes_total
        peer_name = self.buddy.address
        if self.buddy.name != '':
            peer_name += ' (%s)' % self.buddy.name
        title = '%04.1f%% - %s' % (percent,
                                   os.path.basename(self.file_name))
        self.SetTitle(title)
        self.progress_bar.SetValue(percent)

        if self.is_receiver:
            text = lang.DFT_RECEIVE \
                % (os.path.basename(self.file_name), peer_name,
                   percent, self.bytes_complete, self.bytes_total)
        else:
            text = lang.DFT_SEND % (os.path.basename(self.file_name),
                                    peer_name, percent,
                                    self.bytes_complete,
                                    self.bytes_total)

        if self.error:
            text = self.error_msg
            self.btn_cancel.SetLabel(lang.BTN_CLOSE)
            if self.is_receiver:
                self.btn_save.Enable(False)

        self.text.SetLabel(text)

        if self.bytes_complete == self.bytes_total:
            self.completed = True
            self.progress_bar.SetValue(100)
            if self.is_receiver:
                if self.file_name_save != '':
                    self.btn_cancel.SetLabel(lang.BTN_CLOSE)
                    self.transfer_object.close()  # this will actually save the file
            else:
                self.btn_cancel.SetLabel(lang.BTN_CLOSE)

    def onDataChange(
        self,
        total,
        complete,
        error_msg='',
        ):

        # will be called from the FileSender/FileReceiver-object in the
        # protocol module to update gui

        self.bytes_total = total
        self.bytes_complete = complete
        self.error_msg = error_msg

        # we must use wx.Callafter to make calls into wx
        # because we are *NOT* in the context of the GUI thread here

        wx.CallAfter(self.updateOutput)

    def onCancel(self, evt):
        try:

            # this is not always a real "cancel":
            # FileReceiver.close() *after* successful transmission
            # will save the file (if file name is known)

            self.transfer_object.close()
        except:
            pass
        self.Close()

    def onSave(self, evt):
        title = lang.DFT_FILE_SAVE_TITLE \
            % self.buddy.getAddressAndDisplayName()
        dialog = wx.FileDialog(self, title, defaultFile=self.file_name,
                               style=wx.SAVE)
        if dialog.ShowModal() == wx.ID_OK:
            self.file_name_save = dialog.GetPath()

            if os.path.exists(self.file_name_save):
                overwrite = \
                    wx.MessageBox(lang.D_WARN_FILE_ALREADY_EXISTS_MESSAGE
                                  % self.file_name_save,
                                  lang.D_WARN_FILE_ALREADY_EXISTS_TITLE,
                                  wx.YES_NO)
                if overwrite != wx.YES:
                    self.file_name_save = ''
                    return

            self.transfer_object.setFileNameSave(self.file_name_save)
            if not self.transfer_object.file_handle_save:
                error = self.transfer_object.file_save_error
                wx.MessageBox(lang.D_WARN_FILE_SAVE_ERROR_MESSAGE
                              % (self.file_name_save, error),
                              lang.D_WARN_FILE_SAVE_ERROR_TITLE)
                self.file_name_save = ''
                return

            self.btn_save.Enable(False)
            if self.completed:
                self.onCancel(evt)
        else:
            pass


class MainWindow(wx.Frame):

    def __init__(self, socket=None):
        wx.Frame.__init__(self, None, -1, 'TorChat', size=(250, 350))
        self.conns = []
        self.chat_windows = []
        self.notification_window = None
        self.buddy_list = tc_client.BuddyList(self.callbackMessage,
                socket)

        self.SetTitle('TorChat: %s' % config.getProfileLongName())

        self.Bind(wx.EVT_CLOSE, self.onClose)

        # setup gui elements

        self.taskbar_icon = TaskbarIcon(self)
        self.main_panel = wx.Panel(self)
        sizer = wx.BoxSizer(wx.VERTICAL)
        self.gui_bl = BuddyList(self.main_panel, self)
        sizer.Add(self.gui_bl, 1, wx.EXPAND)

        self.status_switch = StatusSwitch(self.main_panel, self)
        sizer.Add(self.status_switch, 0, wx.EXPAND)

        self.main_panel.SetSizer(sizer)
        sizer.FitInside(self)

        icon = wx.Icon(name=os.path.join(config.get('internal',
                       'icon_dir'), 'torchat.ico'),
                       type=wx.BITMAP_TYPE_ICO)
        self.SetIcon(icon)

        if not config.getint('gui', 'open_main_window_hidden'):
            self.Show()

        if config.get('logging', 'log_file') and config.getint('logging'
                , 'log_level'):
            log.debug('logging to file may leave sensitive information on disk'
                      )
            wx.MessageBox(lang.D_LOG_WARNING_MESSAGE
                          % config.log_writer.file_name,
                          lang.D_LOG_WARNING_TITLE, wx.ICON_WARNING)

    def setStatus(self, status):
        self.buddy_list.setStatus(status)
        self.taskbar_icon.showStatus(status)

    def callbackMessage(self, callback_type, callback_data):

        # we must always use wx.CallAfter() to interact with
        # the GUI-Thread because this method will be called
        # in the context of one of the connection threads

        if callback_type == tc_client.CB_TYPE_CHAT:
            (buddy, message) = callback_data
            for window in self.chat_windows:
                if window.buddy == buddy:
                    wx.CallAfter(window.process, message)
                    return

            # no window found, so we create a new one

            hidden = config.getint('gui', 'open_chat_window_hidden')
            wx.CallAfter(ChatWindow, self, buddy, message, hidden)

            # we let this thread block until the window
            # shows up in our chat window list

            found = False
            while not found:
                time.sleep(1)
                for window in self.chat_windows:
                    if window.buddy == buddy:
                        found = True
                        break

        if callback_type == tc_client.CB_TYPE_OFFLINE_SENT:
            buddy = callback_data
            for window in self.chat_windows:
                if window.buddy == buddy:
                    wx.CallAfter(window.notifyOfflineSent)
                    return

            hidden = config.getint('gui', 'open_chat_window_hidden')
            wx.CallAfter(
                ChatWindow,
                self,
                buddy,
                '',
                hidden,
                notify_offline_sent=True,
                )

        if callback_type == tc_client.CB_TYPE_FILE:

            # this happens when an incoming file transfer was initialized
            # we must now create a FileTransferWindow and return its
            # event handler method to the caller

            receiver = callback_data
            buddy = receiver.buddy
            file_name = receiver.file_name

            # we cannot get return values from wx.CallAfter() calls
            # so we have to CallAfter() and then just wait for
            # the TransferWindow to appear.

            wx.CallAfter(FileTransferWindow, self, buddy, file_name,
                         receiver)

    def onClose(self, evt):
        self.Show(False)

    def exitProgram(self):
        found_unread = False
        for window in self.chat_windows:
            if not window.IsShown() or window.unread:
                found_unread = True
                break

        if found_unread:
            answer = wx.MessageBox(lang.D_WARN_UNREAD_MESSAGE,
                                   lang.D_WARN_UNREAD_TITLE, wx.YES_NO
                                   | wx.NO_DEFAULT)

            if answer == wx.NO:
                return

        self.taskbar_icon.RemoveIcon()
        self.buddy_list.stopClient()  # this will also stop portable Tor

        # All my threads wouldn't join properly. Don't know why.
        # sys.exit() would spew lots of tracebacks *sometimes*,
        # so let's do it the easy way and just kill ourself:

        config.killProcess(os.getpid())


