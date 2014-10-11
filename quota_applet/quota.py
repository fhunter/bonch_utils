#! /usr/bin/python
#
# $Id: quota.py,v 1.4 2014/08/22 12:52:17 osd1000 Exp $
#
# jp107 did some changes to show quota.
# Much tidying up and bug-fixes by df224.
#
# based on code from David Collie <dccollie@engmail.uwaterloo.ca>
# Copyright David Collie 2005

import os, sys, re, pygtk
import gtk, gtk.glade, gobject
pygtk.require('2.0')

# used for the TrayIcon to let us include 'progressbar' etc
try:
    import egg.trayicon
except:
    print "ERROR: unable to import egg.trayicon"
    sys.exit(-1)

# Set to where we install it and so where the glade file lives
basedir='./'

# where the getquota.pl script can be found
#getquotacmd='./getquota.pl'
getquotacmd='./getquota.sh'
# Count how many times we have called the getquota command
getquotact=0

# turn up for debugging
#debug=3
debug=0

REFRESH = 1000 * 30 * 1    # 0.5 minute
# while testing bring this down...
REFRESH = 1000 * 20

# 10% of a normal quota is currently about 100MB.
MAX_WARN   = 95        # warn users if their quota reaches X% full
MAX_WARNMB = 80        # and they have under Y MB left
MAX_PANIC  = 97        # Percent for a real alarm
MAX_PANICMB= 50        # in MB

# Width to pad the tooltip integers (MB used/free etc) to
padwid = 7

def paddedNumber(s, width):
    '''
    Returns a string with twice as much padding as you might *think* we need!
    '''
    l=len(s)
    if (l < width):
        s = (' ' * (2 * (width - l))) + s
    return s

def strSize(i):
    '''
    Returns a string of the size in MBytes or GBytes padded to the
    width set above
    '''
    u='M'
    v=float(i)
    if (v >= 1024):
        v=v/1024
        u='G'
    return paddedNumber("%.2f"%v, padwid)+" %sB"%u

def strPerc(i, p):
    '''
    Returns a padded string of the percentage
    
    '''
    return paddedNumber("%d"%i, p)+"%"

# the quota class
class Quota:
    '''
    Class that contains an interface for notifying users of their quota status
    '''

    def __init__(self):
        '''
        Initiliases the warning dialog using the glade file.  Then creates
        the system tray applet and connects the necessary signals and handlers
        for it to work.
        '''
        # initialize the latch to keep warning users about quota
        self.latch = False

        # initialize the quota dialog
        # Should put a proper full path here...
        gladefile = basedir+"/quota.glade"
        self.windowname = "warning"
        self.wTree = gtk.glade.XML(gladefile, self.windowname)

        signalDic = {"on_warning_destroy": gtk.main_quit,
                     "on_button1_clicked": self.toggleVisible,
                     "on_checkbutton1_toggled": self.toggleLatch
                    }
        self.wTree.signal_autoconnect(signalDic)

        # Detect whether we have an XFCE panel, in which case size will
        # be wrong and we need to correct it.

        have_xfce_panel = not (os.system("xwininfo -name xfce4-panel >/dev/null 2>&1"))

        # create trayicon
        self.trayicon = egg.trayicon.TrayIcon("Quota")
        self.trayicon.connect('destroy', gtk.main_quit)
        self.trayicon.connect('button_press_event', self.toggleVisible)
        self.event_box = gtk.EventBox()

        self.progressbar = gtk.ProgressBar()
# we can override the default 'style' but then we need to set everything
# by hand or it will look really ugly...
#        sty = gtk.Style();
#        self.progressbar.set_style(sty);
        self.tip = gtk.Tooltips()

        self.progressbar.set_orientation(gtk.PROGRESS_BOTTOM_TO_TOP)
        self.event_box.add(self.progressbar)
        self.progressbar.show()
        self.trayicon.add(self.event_box)

        if (have_xfce_panel):
            self.trayicon.set_size_request(40,22)

        # update quota information as we would on a refresh...
        self.refresh_handler()

        self.trayicon.show_all()

        # initialize the timer
        gobject.timeout_add(REFRESH, self.refresh_handler)

        return

    def updateTip(self, quotaInfo):
        '''
        Updates the tooltip member variable with quotaInfo
        '''
        if (quotaInfo[1] > 0):
            used = float(quotaInfo[0]) / 1024
            total = float(quotaInfo[1]) / 1024
            free = float(quotaInfo[2]) / 1024
            percent = int(quotaInfo[3])
            freepercent = 100 - percent
            
            if ((percent <= 0) or (percent >= 100)):
                pw=3
            else:
                pw=2
                
            ttl = self.tip
        
            text = "Maths Quota usage\n%s (%s) used\n%s (%s) free\n%s total" %(strSize(used), strPerc(percent,pw), strSize(free), strPerc(freepercent,pw), strSize(total))
        else:
            text = "Unable to read quota "+quotaInfo[3]

        # assocaite the tooltip with trayicon
        self.tip.set_tip(self.trayicon, text)
        return

    def refresh_handler(self):
        '''
        At every REFRESH interval check the status of the user quota and 
        decide if a warning needs to be displayed.
        '''
        while gtk.events_pending():
            gtk.main_iteration(False)

        quotaInfo = self.getQuota()

        self.updateLabel(quotaInfo)
        self.updateProgressBar(quotaInfo)
        self.updateTip(quotaInfo)
        
        if (quotaInfo[1] > 0):
            used = float(quotaInfo[0]) / 1024
            total = float(quotaInfo[1]) / 1024
            free = float(quotaInfo[2]) / 1024
            percent = int(quotaInfo[3])

            # over MAX_WARN%, under MB_WARN MBs, they haven't clicked the checkbox 
            # and the window is not currently being displayed
            if percent >= MAX_WARN and free <= MAX_WARNMB and self.latch is False:
                window = self.wTree.get_widget('warning')
                value = window.get_property('visible')
                if value is False: window.set_property('visible', True)

        return True
            
    def updateProgressBar(self, quotaInfo):
        '''
        Update the status of the progress bar with the current quota 
        information.
        '''
        if (quotaInfo[1] > 0):
            percent=quotaInfo[3]
            value = float(percent) / 100.0

            # the progress bar colour doesn't change in our default theme since it
            # is using a pixmap not a simple colour to draw the bar.

            # Change the color of the progress bar based on the usage.
            # This does not work for certain gtk/gnome themes, so don't
            # worry too much!
            if percent >= MAX_WARN:
                self.progressbar.modify_bg(gtk.STATE_PRELIGHT, self.progressbar.get_colormap().alloc_color("red"))
            elif percent >= 70:
                self.progressbar.modify_bg(gtk.STATE_PRELIGHT, self.progressbar.get_colormap().alloc_color("yellow"))
            else:
                self.progressbar.modify_bg(gtk.STATE_PRELIGHT, self.progressbar.get_colormap().alloc_color("green"))


            # Don't allow value to be > 1.0 here or the progressbar will die
            if (value > 1.0):
                value = 1.0
            
            self.progressbar.set_fraction(value)
            self.progressbar.set_text(percent+'%')
        else:
            # Error state of some kind...
            # Does not work in some gtk/gnome themes...
            self.progressbar.modify_bg(gtk.STATE_PRELIGHT, self.progressbar.get_colormap().alloc_color("red"))
            self.progressbar.set_fraction(0)
            self.progressbar.set_text('N/A')

    def updateLabel(self, quotaInfo):
        '''
        Update the label on the quota warning dialog with the user quota
        information in percentage.
        '''
        link="http://www.maths.cam.ac.uk/computing/quota.html"
        report="\n\nSee "+link+"\nor email help@maths for further assistance."
        
        label = self.wTree.get_widget("label1")
        if (quotaInfo[1] > 0):
            used  = float(quotaInfo[0]) / 1024
            total = float(quotaInfo[1]) / 1024
            free  = float(quotaInfo[2]) / 1024
            percent = quotaInfo[3]

            # give users some feedback if they're getting close to their limit
            if int(percent) >= MAX_PANIC and free <= MAX_PANICMB: 
                percent = '''<b><span foreground="red">''' + percent + "</span></b>"
                warning = "<b>WARNING</b>:"
            elif int(percent) >= MAX_WARN and free <= MAX_WARNMB: 
                percent = '''<b><span foreground="blue">''' + percent + "</span></b>"
                warning ="<b>Warning</b>\n"
            else:
                percent = "<b>" + percent + "</b>"
                warning = ""

            string = warning+"You are currently using " + percent + "% of your Quota.\n\nIf you exceed your quota programs may malfunction and you may lose data."+report
        else:
            string="<b>WARNING</b>: Unable to read quota "+quotaInfo[3]+" information."+report

        label.set_text(string)
        label.set_property('use-markup', 1)

    def toggleLatch(self, widget):
        '''
        Toggle the value of the latch that indicates if the user has asked not
        to be warned about quota usage.
        '''
        if self.latch is False: 
            self.latch = True
        else:   
            self.latch = False

    def toggleVisible(self, widget=None, callback_data=None):
        '''
        Toggle the visibility of the warning dialog.
        '''
        window = self.wTree.get_widget('warning')
        value = window.get_property('visible')

        if value is True: window.set_property('visible', False)
        else: window.set_property('visible', True)

    def getQuota(self):
        '''
        Return the quota information about the userid running the applet.  This
        function calls getquota using os.popen call. It will return a tuple 
        containing the amount used in kilobytes, the total availible in 
        kilobytes, and the amount free.  From the first two we calculate the
        percentage used and add that to what we return.
        os.popen needs replacing with Popen when we move to python 2.6
        '''
        global getquotacmd, getquotact
        
        # We don't need os.popen2 since we are just reading from stdout
        # and don't send anything to stdin!
        if getquotact <= 0:
            stdout = os.popen(getquotacmd, 'r')
        else:
            stdout = os.popen(getquotacmd+" -sverb 4", 'r')
        output = stdout.readlines()    
        if len(output) < 1:
            if debug > 0:
                print "ERROR: invalid output (lines)"
            return (-1,-1,-1,"usage")

        
        output = re.split('\s+', output[0])
        quotau=int(output[0])
        quotat=int(output[1])
        quotaf=int(output[2])

        # Testing error conditions...
        ##quotat=0

        # increment counter modulo 20...
        getquotact = (getquotact + 1) % 20

        if debug > 1:
            print "got o 0=%s 1=%s 2=%s" % (quotau,quotat,quotaf)

        # quit if they don't seem to have a quota - will this go wrong if
        # the file-server is temporarily down?
        if quotat < 1:
            if debug > 0:
                print "ERROR: invalid output zero or negative quota limit"
            return (-1,-1,-1,"limit")

        perc = int(0.5 + 100 * float(quotau) / float(quotat))
        if debug > 1:
            print "perc seems to be %s from (%s / %s)" %(perc, quotau, quotat)
        return (quotau, quotat, quotaf, str(perc))

if __name__ == "__main__":
    try:
        q = Quota()
        gtk.main()
    except KeyboardInterrupt:
        sys.exit(0)
