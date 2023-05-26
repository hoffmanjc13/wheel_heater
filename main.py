#!/usr/bin/env python3

"""
The main script that triggers the GUI construction and invokes the functionality
of the backend

TODO: This has some style issues. And by 'some', I mean more than a few.
    Someone, maybe Julia, maybe some other unfortunate soul should go through
    and fix it. See note at the top of PrattGUI class.

TODO: Engine and build data, data points to graph, and custom calculations are
    all persistent though app close and re-open. Maybe could make graph setup
    the same way?
"""

__authors__ = ['Chris Cosgrove (m335285)', 'Julia Hoffman (m335686)']
__version__ = '0.1.0'

import os
from zipfile import ZipFile

import numpy as np
import pandas as pd
import tkinter as tk
from tkinter import ttk
# tk.messagebox sometimes fails. This fixes
from tkinter import messagebox, simpledialog
import matplotlib
from matplotlib import pyplot as plt
from matplotlib.figure import Figure
# NavigationToolbar2TkAgg was deprecated in Matplotlib version 2.2, but
# the t4z server farm still runs version 2.1.1
try:
    from matplotlib.backends.backend_tkagg import (
            FigureCanvasTkAgg,
            NavigationToolbar2Tk
        )
except:
    from matplotlib.backends.backend_tkagg import (
            FigureCanvasTkAgg,
            NavigationToolbar2TkAgg
        )

import AMT_backend as amt
from AMT_backend._parsing import _tokenize

# Sets working directory to the directory with this script file *which
# is normally default behavior*
os.chdir(os.path.abspath(os.path.dirname(__file__)))

# constants
LARGE_FONT = ("Verdana", 12)
NORM_FONT = ("Verdana", 10)
SMALL_FONT = ("Verdana", 8)
TYPED_COLOR = 'black'
PLACEHOLDER_COLOR = 'gray19'

# Global variables

# Maybe these two should be handled as attributes of some class?
xGraphParms = []
yGraphParms = []

# this is the global list of all plot boxes that show up as PlotBox objects on
# PageOne
# There's probably a better way to deal with this that isn't a global, because
# it's *mostly* only used in one class, but it has to be updated when importing
# setup files and cleared on start, so it shows up in a handful of other places
# Also, the boxes themselves need to edit the list...

# Maybe the soln is a BoxManager class?
# TODO: fix this lol
boxList = []

# UpdateFlag tracks if any graph-relevant data has changed (such as new ADR
# numbers, new parameters, etc). If it's set to false, there's no need to
# regenerate the graphs (suuuuuper time-intensive) nor to rebuild the tree on
# PageTwo (less time-intensive, but still not *quick*). This should probably be
# broken into two flags, since swapping parameters shouldn't need a new tree,
# but it's mostly fine.
UpdateFlag = True
# commentUpdateFlag tracks if any local comments have been changed. Again, it's
# and optimization to avoid rebuilding the tree on PageTwo unnecessarily.
commentUpdateFlag = True

# Setup matplotlib styles
matplotlib.style.use("ggplot")
matplotlib.use("TkAgg")


class Plot:
    """
    Essentially just a struct to organize the data for an individual plot.

    TODO: add validity checking to attributes?

    Attributes
    ----------
    subplotList : List[Tuple[str, str]]
        A list of the subplots in a given plot. The list takes the form
        [(xparm1, yparm1), (xparm2, yparm2), ...] up to four subplots.
    numSubplot : int
        The number of subplots in the plot. Should be between 1 and 4.
    dataType : str
        The type of data contained in the plot. Should be 'PDR', 'Raw',
        'Source', or 'Profile'.
    sigmaCut : float
        The cutoff to use for the shift detection, measured in standard
        deviations. Will default to 2.0 with no user input.
    """
    def __init__(self, subplotList, dataType, sigmaCut):
        self.subplotList = subplotList # List[Tuple[str, str]]
        self.numSubplot = len(subplotList)
        
        self.dataType = dataType
        self.sigmaCut = sigmaCut


class PlotBox(tk.Frame):
    """
    A custom widget containing the inputs for one plot and its subplots.

    The widget contains the following entry fields: 8 text boxes, one
    pair per subplot; one checkbox, to indicate whether to show trending
    analysis; one text box for the cutoff value for trending; and a
    dropdown for datatype selection. Additionally, there is a delete
    plot button.

    Attributes
    ----------
    parent : tkinter widget
        The widget this one is placed in. Mostly used to raise events.
    XParmGraph1Entry and others : Tkinter entry widgets
        This widget has 4 Xparm Graph Entries and 4 yparm Graph Entries,
        one for each subplot
    TypeVar : Tkinter string var
        The Tkinter variable corresponding to the selected data type
    CheckVar : Tkinter boolean var
        The Tkinter variable corresponding to the state of the checkbox
        for showing trend analysis.
    sigma : Tkinter entry widget
        The entry for users to input the sigma cutoff

    Methods
    -------
    get
        Gets widget data including parameters, data type, and trend
        analysis settings.
    destroy
        Destroys widget, as well as removing the widget from the global
        boxList, and creating an event to help coordinate PlotBox
        reordering.
    """
    
    def __init__(self, parent, label):
        """
        Parameters
        ----------
        parent : tkinter widget
            The widget this one is placed in. Mostly used to raise
            events, as well as to set up the 
            TODO: finish this thought. What was it??
        label : string
            The label to use for the PlotBox LabelFrame (ex 'Plot 1')
        """
        
        tk.Frame.__init__(self, parent)
        self.parent = parent
        
        pbLabel = tk.LabelFrame(self, text = label)
        pbLabel.grid(row  = 7, column = 0, sticky = "nesw", columnspan=4)
        
        deleteButton = ttk.Button(pbLabel, text = "Delete", command = self.destroy)
        deleteButton.grid(row = 2, column = 5, sticky = "nesw")

        # TODO: rewrite with loop?
        graph1Label = ttk.Label(pbLabel, text = "Graph 1", font = SMALL_FONT)
        graph1Label.grid(row = 2, column = 0, sticky = "nesw")

        self.XParmGraph1entry = ttk.Entry(pbLabel, foreground=PLACEHOLDER_COLOR)
        self.XParmGraph1entry.grid(row = 2, column = 1, sticky = "nesw")
        self.XParmGraph1entry.placeholder = "Enter X Parm to Graph"
        self.XParmGraph1entry.insert(0, self.XParmGraph1entry.placeholder)
        self.XParmGraph1entry.bind('<FocusIn>', self.__focus)
        self.XParmGraph1entry.bind('<FocusOut>', self.__out)
        self.XParmGraph1entry.bind('<Return>', self.__forceEnterParms)
        
        self.YParmGraph1entry = ttk.Entry(pbLabel, foreground=PLACEHOLDER_COLOR)
        self.YParmGraph1entry.grid(row = 2, column = 2, sticky = "nesw")
        self.YParmGraph1entry.placeholder = "Enter Y Parm to Graph"
        self.YParmGraph1entry.insert(0, self.YParmGraph1entry.placeholder)
        self.YParmGraph1entry.bind('<FocusIn>', self.__focus)
        self.YParmGraph1entry.bind('<FocusOut>', self.__out)
        self.YParmGraph1entry.bind('<Return>', self.__forceEnterParms)

        graph2Label = ttk.Label(pbLabel, text = "Graph 2", font = SMALL_FONT)
        graph2Label.grid(row = 3, column = 0, sticky = "nesw")
        
        self.XParmGraph2entry = ttk.Entry(pbLabel, foreground=PLACEHOLDER_COLOR)
        self.XParmGraph2entry.grid(row = 3, column = 1, sticky = "nesw")
        self.XParmGraph2entry.placeholder = "Enter X Parm to Graph"
        self.XParmGraph2entry.insert(0, self.XParmGraph2entry.placeholder)
        self.XParmGraph2entry.bind('<FocusIn>', self.__focus)
        self.XParmGraph2entry.bind('<FocusOut>', self.__out)
        self.XParmGraph2entry.bind('<Return>', self.__forceEnterParms)
        
        self.YParmGraph2entry = ttk.Entry(pbLabel, foreground=PLACEHOLDER_COLOR)
        self.YParmGraph2entry.grid(row = 3, column = 2, sticky = "nesw")
        self.YParmGraph2entry.placeholder = "Enter Y Parm to Graph"
        self.YParmGraph2entry.insert(0, self.YParmGraph2entry.placeholder)
        self.YParmGraph2entry.bind('<FocusIn>', self.__focus)
        self.YParmGraph2entry.bind('<FocusOut>', self.__out)
        self.YParmGraph2entry.bind('<Return>', self.__forceEnterParms)

        graph3Label = ttk.Label(pbLabel, text = "Graph 3", font = SMALL_FONT)
        graph3Label.grid(row = 4, column = 0, sticky = "nesw")
        
        self.XParmGraph3entry = ttk.Entry(pbLabel, foreground=PLACEHOLDER_COLOR)
        self.XParmGraph3entry.grid(row = 4, column = 1, sticky = "nesw")
        self.XParmGraph3entry.placeholder = "Enter X Parm to Graph"
        self.XParmGraph3entry.insert(0, self.XParmGraph3entry.placeholder)
        self.XParmGraph3entry.bind('<FocusIn>', self.__focus)
        self.XParmGraph3entry.bind('<FocusOut>', self.__out)
        self.XParmGraph3entry.bind('<Return>', self.__forceEnterParms)
        
        self.YParmGraph3entry = ttk.Entry(pbLabel, foreground=PLACEHOLDER_COLOR)
        self.YParmGraph3entry.grid(row = 4, column = 2, sticky = "nesw")
        self.YParmGraph3entry.placeholder = "Enter Y Parm to Graph"
        self.YParmGraph3entry.insert(0, self.YParmGraph3entry.placeholder)
        self.YParmGraph3entry.bind('<FocusIn>', self.__focus)
        self.YParmGraph3entry.bind('<FocusOut>', self.__out)
        self.YParmGraph3entry.bind('<Return>', self.__forceEnterParms)

        graph4Label = ttk.Label(pbLabel, text = "Graph 4", font = SMALL_FONT)
        graph4Label.grid(row = 5, column = 0, sticky = "nesw")
        
        self.XParmGraph4entry = ttk.Entry(pbLabel, foreground=PLACEHOLDER_COLOR)
        self.XParmGraph4entry.grid(row = 5, column = 1, sticky = "nesw")
        self.XParmGraph4entry.placeholder = "Enter X Parm to Graph"
        self.XParmGraph4entry.insert(0, self.XParmGraph4entry.placeholder)
        self.XParmGraph4entry.bind('<FocusIn>', self.__focus)
        self.XParmGraph4entry.bind('<FocusOut>', self.__out)
        self.XParmGraph4entry.bind('<Return>', self.__forceEnterParms)
        
        self.YParmGraph4entry = ttk.Entry(pbLabel, foreground=PLACEHOLDER_COLOR)
        self.YParmGraph4entry.grid(row = 5, column = 2, sticky = "nesw")
        self.YParmGraph4entry.placeholder = "Enter Y Parm to Graph"
        self.YParmGraph4entry.insert(0, self.YParmGraph4entry.placeholder)
        self.YParmGraph4entry.bind('<FocusIn>', self.__focus)
        self.YParmGraph4entry.bind('<FocusOut>', self.__out)
        self.YParmGraph4entry.bind('<Return>', self.__forceEnterParms)

        dataTypeLabel = ttk.Label(pbLabel, text='Data Type:', font=SMALL_FONT)
        dataTypeLabel.grid(row=4, column=5, sticky='news')

        typeList = ['RAW', 'PDR', 'SOURCE', 'PROFILE']
        self.TypeVar = tk.StringVar()
        self.TypeVar.set('PDR')
        dataTypeSel = tk.OptionMenu(pbLabel, self.TypeVar, *typeList)
        dataTypeSel.grid(row=5, column=5, sticky='ew')
        
        frame = tk.Frame(pbLabel)
        frame.grid(row = 6, column = 0, columnspan = 6, sticky = "nesw")

        self.CheckVar = tk.BooleanVar()
        self.CheckVar.set(True)
        checkbox = tk.Checkbutton(frame, text = "Show trend analysis labeling",
                                       variable=self.CheckVar, command = self.__toggleEntry)
        checkbox.pack(side=tk.LEFT, padx=10, pady=10)

        ttk.Label(frame, text="    Chose sensitivty").pack(side=tk.LEFT, pady=10)

        self.sigma = ttk.Entry(frame, foreground=PLACEHOLDER_COLOR)
        self.sigma.placeholder = "Enter value"
        self.sigma.insert(0, self.sigma.placeholder)
        self.sigma.bind('<FocusIn>', self.__focus)
        self.sigma.bind('<FocusOut>', self.__out) # TODO: fix placeholder bug
        # TODO: I left myself that todo too long ago and I don't remember what
        #   it means
        self.sigma.bind('<Return>', self.__forceEnterParms)
        self.sigma.pack(side=tk.LEFT, padx=10, pady=10)

    def get(self):
        """
        Get widget data

        Returns
        -------
        Plot object
            A Plot object as defined above, containing the user-entered data.
            Specifically, its subplotList is built from the user's chosen
            parameters, the dataType is the selected data type, and the sigmaCut
            is the users chosen sigmaCut, or the default of 2, unless trend
            detection is turned off, in which case it will be -1.
        """
        
        XentryList = [self.XParmGraph1entry,
                     self.XParmGraph2entry, 
                     self.XParmGraph3entry,
                     self.XParmGraph4entry]
        
        YentryList = [self.YParmGraph1entry,
                     self.YParmGraph2entry,
                     self.YParmGraph3entry,
                     self.YParmGraph4entry]
        subplotList = []
        for Xentry, Yentry in map(lambda x,y: (x,y), XentryList, YentryList):
            Xparm = Xentry.get()
            Yparm = Yentry.get()
            if Xparm == Xentry.placeholder or Xparm == "": continue
            elif Yparm == Yentry.placeholder or Yparm == "": continue
            subplotList.append((Xparm.upper(), Yparm.upper()))
            
        dataType = self.TypeVar.get()

        useTrendAnalysis = self.CheckVar.get()
        if useTrendAnalysis:
            sigmaCut = self.sigma.get()
            if sigmaCut == self.sigma.placeholder: sigmaCut = 2
            else:
                try: sigmaCut = float(sigmaCut)
                except:
                    messagebox.showerror("Error", "Invalid choice of sensitivity")
        else: sigmaCut = -1

        return Plot(subplotList, dataType, sigmaCut)

    def deleteBox(self):
        """Destroys PlotBox object and removes it from global boxList"""
        global boxList
        boxList.remove(self)
        # there's gotta be a better way to trigger this...
        self.parent.event_generate('<<deletebox>>')
        self.destroy()

    def __focus(self, event, isPass=False):
        """
        Private method called when clicking into an entry.

        Method designed to be bound to '<FocusIn>' event for entries. If
        the entry has placeholder text set and the text in the entry is
        the placeholder (ie, text has not been edited yet) delete the
        placeholder text and darken the text color when clicking into
        the entry
        """
        widget = event.widget
        try: placeholder = widget.placeholder
        except AttributeError: return
        if widget.get() == placeholder:
            widget.delete(0,tk.END)
        widget.config(foreground=TYPED_COLOR)

    def __out(self, event, isPass=False):
        """
        Private method called when clicking out of an entry.

        Method designed to be bound to '<FocusOut>' event for entries.
        If the entry is left blank, re-add the placeholder and change
        the text back to grey.
        """
        widget = event.widget
        try: placeholder = widget.placeholder
        except AttributeError: return
        if widget.get() == "":
            widget.insert(0, placeholder)
            widget.config(foreground=PLACEHOLDER_COLOR)
            if isPass: widget.config(show='')
            
    def __toggleEntry(self):
        """Private method to toggle the state of the sigma entry"""
        self.sigma.state(["!disabled" if self.CheckVar.get() else "disabled"])

    def __forceEnterParms(self, event):
        """
        Was a private method to forcibly load parameter data.

        Gave functionality to '<Return>' event normally handled by the
        PageOne class. If you hit enter while in any of the textboxes, you
        would load all parameter data. However, I didn't think the functionality
        was hugely intuitive, so it's disabled. To re-enable, remove the return
        statement
        """
        return
        global xGraphParms
        global yGraphParms
        
        xGraphParms, yGraphParms = ([], [])
        entries = [(self.XParmGraph1entry, self.YParmGraph1entry),
                   (self.XParmGraph2entry, self.YParmGraph2entry),
                   (self.XParmGraph3entry, self.YParmGraph3entry),
                   (self.XParmGraph4entry, self.YParmGraph4entry)]

        for entry in entries:
            xParm = entry[0].get().strip()
            yParm = entry[1].get().strip()
            
            if xParm == "Enter X Parm to Graph": continue
            elif xParm == "": continue
            elif yParm == "Enter Y Parm to Graph": continue
            elif yParm == "" : continue

            xGraphParms.append(xParm.upper())
            yGraphParms.append(yParm.upper())

        global UpdateFlag
        UpdateFlag = True


def GraphPage(msg):
    """
    Generates the popup to enter Unigraph-style equations.

    TODO this is a bit messy, and I feel weird about this being a function
        rather than a class. Rewrite this or otherwise clean this up?
    """
    popup = tk.Tk()

    popup.wm_title("Add Graph Page")
    wrapper1 = tk.LabelFrame(popup, text = msg, font = NORM_FONT)
    wrapper1.pack(fill = "both", expand = "yes", padx = 20, pady = 10)
    frame = tk.Frame(wrapper1)
    frame.pack(fill = "none", expand = "false", padx = 20, pady = 10)
    
    label1 = ttk.Label(frame, text = "Enter text into text box, whatever is entered will be written to the command file", font = SMALL_FONT)
    label1.grid(row = 0, column = 0, sticky = "nesw")
    # text widget
    t = tk.Text(frame, width = 100, height = 50)
    t.grid(row = 1, column = 0)
    if os.path.exists('amt_appdata/op_cache.txt'):
        with open("amt_appdata/op_cache.txt", 'r') as history_file:
            CmdFileInsert = history_file.read()
    else:
        print("No operations cache exists at expected location" + os.getcwd() + 'amt_appdata/op_cache.txt')
        try:
            open('amt_appdata/op_cache.txt', 'x').close()
            CmdFileInsert = ""
        except Exception as e:
            print("Unable to create operations cache at " + os.getcwd() + 'amt_appdata/op_cache.txt')
            raise e
    t.insert(1.0, CmdFileInsert)

    def FillHistoryFile(popup):
        token_str=t.get("1.0",tk.END)
        i = 1
        try:
            for line in token_str.split('\n'):
                token_list = _tokenize(line)
                i += 1
        except:
            # TODO: make a better error on tokenization failure so except can be
            #   more specific
            messagebox.showerror("Error",
                "The inputted equation contains one or more invalid tokens on line " + str(i))
        with open(amt.OP_CACHE, 'w') as history_file:
            history_file.write(token_str)
    def FHF_Helper():
        # ...I am not clear why this is done this way. We do not seem to use
        # popup anywhere in the FillHistoryFile function
        FillHistoryFile(popup)
        global UpdateFlag
        UpdateFlag = True

    button0 = ttk.Button(frame, text = "Enter", command = FHF_Helper)
    button0.grid(row = 1, column = 1, sticky ="nesw")

    popup.mainloop()

class GraphTabButton(tk.Frame):
    """
    A custom widget used to create tabs for the graph page (PageThree).

    Each instance of the widget is basically just a ttk Button with
    additional data used to define the graph it should prompt PageThree
    to draw when clicked.

    Attributes
    ----------
    parent : tkinter widget
        The widget this one is placed in. Used to coordinate against
        the selected tab saved in parent class (PageThree's TabFrame).
    index : int
        The index the GraphTabButton is drawn in. Used to coordinate
        with parent to determine if a button is selected.
    subplotList : List of Tuples of (str, str)
        List of all subplots associated with a given GraphTabButton.
        Each subplot is represented with a tuple: (Xparm, Ypam).
    dataType : str
        The data type used for the plot associated with the given
        GraphTabButton. Options are PDR, RAW, PROFILE, and SOURCE.
    sigmaCut : float
        The sensitivity cutoff for the given plot. See the trend
        analysis section of the backend for more.
    button : Tkinter widget
        A ttk Button.

    Methods
    ----------
    update
        Update button state to disabled if button is selected.
    """
    
    def __init__(self, parent, label, index, subplotList, dataType, sigmaCut, width=100):
        tk.Frame.__init__(self, parent)

        self.parent = parent

        self.index = index
        self.subplotList = subplotList
        self.dataType = dataType
        self.sigmaCut = sigmaCut
        self.button = ttk.Button(self, text=label, width=width,
                                 state='disabled' if self.index==parent.select else '!disabled',
                                 command=self.__onClick)
        self.button.pack()
        
    def update(self, *event):
        try: self.button.state(['disabled' if self.index==self.parent.select else '!disabled'])
        except: pass

    def __onClick(self):
        """fill in parent data when button is clicked."""
        self.parent.select = self.index
        self.parent.subplotList = self.subplotList
        self.parent.dataType = self.dataType
        self.parent.sigmaCut = self.sigmaCut
        self.parent.event_generate('<<tabswitch>>')
        self.update()

class PrattGUI(tk.Tk):
    """
    Main app class. Acts as controller for all other pages.

    TODO: This file is architecturally a bit messy. Hypothetically, it has a
        controller (this class) and it has nods towards a model, but overall, it
        does not hold to a MVC framework and it replaces its much of its model
        with jank and global variables. Refactoring it will be a project, but
        probably a worthwhile one. Tentatively Julia's problem...

    Attributes
    ----------
    plotList : List of plots (implemetion: List[List[Tuples[str, str]]])
        A list of all plots to be graphed. Each plot in the list is
        represented as a list of subplots, each of which is
        represented as a tuple in the form (Xparm, Yparm). A potentual
        improvement may be creating a Plot class
    """
    def __init__(self, *args, **kwargs):
        tk.Tk.__init__(self,*args, **kwargs)

        # set up app level variables
        # TODO: update boxList and updateFlag to be here too
        self.plotList = []

        # add a menu with file, edit, and png tabs
        # TODO: update the menu
        menubar = tk.Menu(self)
        filemenu = tk.Menu(menubar, tearoff=0)
        filemenu.add_command(label = "Open setup file", command = self.load_file)
        filemenu.add_command(label = "Save setup file", command = self.save_file)
        filemenu.add_separator()
        filemenu.add_command(label = "Save data as command file", command = self.CreateCmdFile)
        filemenu.add_separator()
        filemenu.add_command(label = "Exit", command = quit)
        menubar.add_cascade(label = "File", menu = filemenu)
        
        EditChanges = tk.Menu(menubar, tearoff=0)
        EditChanges.add_command(label = "Edit")
        menubar.add_cascade(label = "Edit", menu = EditChanges)
        
        PngCapture = tk.Menu(menubar, tearoff=0)
        PngCapture.add_command(label = "Png")
        menubar.add_cascade(label = "Png", menu = PngCapture)

        tk.Tk.config(self, menu = menubar)

        # Create a container in which all app content is drawn
        container = tk.Frame(self)
        container.pack(side="top", fill="both", expand = True)
        
        # The app draws all of the app content on top of itself and then
        # brings the relevant page to the top of the stack
        # Because of this, it's important the row/col is configured to
        # be a set size so everything is drawn with the same dimensions
        container.grid_rowconfigure(0, weight=1)
        container.grid_columnconfigure(0, weight=1)

        self.frames={}
        for F in (MenuPage, StartPage, PageOne, PageTwo, PageThree, PageFour):
            frame = F(container, self)
            self.frames[F] = frame
            frame.grid(row=0, column = 0, sticky="nsew")

        self.show_frame(MenuPage)

    def load_file(self):
        """
        Loads a setup file (which are just .zip files).

        Each setup file contains the operations cache (containing the Unigraph
        code), the JSON file with all the data points and their metadata (at a
        minimum, their ADR numbers and filepath, but likely other ITE data too),
        and .npz file containing the contents of the plot list. Loading a setup
        file consists of replacing the contents of amt_appdata with the files
        in the unzipped setup file.
        """

        file_name = tk.filedialog.askopenfilename(title='Load a Setup File',
                                    initialdir='/',
                                    filetypes=[('Zip Files', '*.zip'),
                                               ('All Files', '*.*')])
        if not file_name: return
        if not os.path.exists(file_name):
            messagebox.showerror("Error", "No valid file at path " + file_name)
            return
        elif file_name[-3:] != 'zip':
            messagebox.showerror("Error", "Invalid file type")
            return

        dir = 'amt_appdata'

        # we're overwriting the contents of the directory with the zipfile
        # contents, but we don't want to lose the contents of the local comments
        # file. So we save the contents and will add them back afterward.
        localCommentsFile = ""
        if os.path.isdir(dir):
            try:
                with open(amt.COMMENT_FILE_PATHS, 'r') as filepaths:
                    localCommentsFile = filepaths.read()
            except FileNotFoundError: pass
            
            for f in os.listdir(dir):
                os.remove(os.path.join(dir, f))
            os.rmdir(dir)
        
        with ZipFile(file_name, 'r') as zip:
            zip.printdir()

            print('Extracting all the files now...')
            zip.extractall(path='amt_appdata/..')

        # the .npz file shouldn't actually be in amt_appdata--it's just here for
        # us to reload the plotList. Load it, set the plotList, and then delete
        # the file.
        try:
            with np.load('amt_appdata/graphing_settings.npz', allow_pickle=True) as arr:
                self.plotList = arr["plotList"]
        except Exception as e:
            self.plotList = []
            print(e)
        os.remove('amt_appdata/graphing_settings.npz')

        # replace the local comments file
        with open(amt.COMMENT_FILE_PATHS, 'w') as filepaths:
            filepaths.write(localCommentsFile)

        # Basically everything (except the local comments) needs to be rebuilt,
        # so set the UpdateFlag to redraw the graph, update the tree on page 2,
        # and rebuild the boxList
        global UpdateFlag
        UpdateFlag = True
        self.frames[PageOne].rebuildBoxlist()
        self.frames[PageTwo].UpdateTree()
        
        try: self.frames[PageOne].EngineNumberentry.placeholder = str(amt.get_engine_no_from_JSON())
        except FileNotFoundError: self.frames[PageOne].EngineNumberentry.placeholder = "Engine Number"
        try: self.frames[PageOne].vehicleIDentry.placeholder = str(amt.get_build_no_from_JSON())
        except FileNotFoundError: self.frames[PageOne].vehicleIDentry.placeholder = "Build Number"

        print('Done!')
            
    def save_file(self):
        """Saves a setup file. Basically load_file in reverse"""

        file_name = tk.filedialog.asksaveasfilename(title='Load a Setup File',
                                      initialdir='/',
                                      filetypes=[('Zip Files', '*.zip'),
                                                 ('All Files', '*.*')],
                                      defaultextension = '.zip')
        
        if file_name: # do nothing if user leaves dialog blank
            np.savez('amt_appdata/graphing_settings',
                     plotList=self.plotList)
            
            f = ZipFile(file_name, 'w')
            fileList = [amt.OP_CACHE, amt.JSON_NAME, 'amt_appdata/graphing_settings.npz']
            for name in fileList:
                f.write(name)
            f.close()
            os.remove('amt_appdata/graphing_settings.npz')

    def CreateCmdFile(self):
        """Creates a Unigraph command file based on the current settings."""

        try:
            engineNo = amt.get_engine_no_from_JSON()
            buildNo = amt.get_build_no_from_JSON()
        except FileNotFoundError:
            messagebox.showerror("Command file creation failure", "Please input engine data before attempting to create a command file")
            return

        if not self.plotList:
            messagebox.showwarning("Creating empty command file", "Generating a command file before creating plots may result in undefined behavior or blank plots")
        elif not amt.get_adr_list_from_JSON():
            messagebox.showwarning("Creating empty command file", "Generating a command file before adding plot points may result in undefined behavior or blank plots")
            
        path = tk.filedialog.asksaveasfilename(defaultextension='.cmdfile',
                                 filetypes = [('Unigraph Command File', '.cmdfile'), ('All Files', '*')],
                                 initialfile = 'DHC_e%s-%s'%(engineNo, buildNo),
                                 initialdir = os.getcwd(),
                                 title = "Save Unigraph Command File with Data")
        # if user cancels, don't try to build a command file
        if path == "": return

        # unpack the plot list so it can be interpreted by the backend
        # (which doesn't know what the plot class is)
        fullPlotList = [plot.subplotList for plot in self.plotList]
        typesList = [plot.dataType for plot in self.plotList]
        amt.create_cmdfile_from_JSON(fullPlotList, typesList, out_path=path)
            
            
    #tk.raise raises the start page to the front and than the button raises whcichever is selected
    def show_frame(self, cont):
        frame = self.frames[cont]
        #.tkraise raises it to the front of what we see first
        frame.tkraise()
        frame.update()
        frame.UpdateData()


class MenuPage(tk.Frame):
    """
    Menu Page class holds labels and entries to prompt user
    for their ITE username and password to connect to
    CX Oracle database.
    """
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        #label for Menu Page
        label = ttk.Label(self, text = "This is beta testing for a Pratt&Whitney GUI ", font = LARGE_FONT)
        label.pack(pady=10, padx=10)
        
        #labels and entry bars for username 
        label = ttk.Label(self, text = "Please enter your username and password for ITE. Press enter when complete", font = SMALL_FONT)
        label.pack(pady = 10, padx = 10)
        self.controller = controller
        self.UserNameentry = ttk.Entry(self)
        self.UserNameentry.placeholder = "Enter Username Here"
        self.UserNameentry.config(foreground=PLACEHOLDER_COLOR)
        self.UserNameentry.pack(padx=10, pady=10)
        self.UserNameentry.insert(0, self.UserNameentry.placeholder)
        self.UserNameentry.bind('<FocusIn>', self.focus)
        self.UserNameentry.bind('<FocusOut>', self.out)
        self.UserNameentry.bind('<Return>', self.nextWidget)
        
        #labels and entry bars for password 
        self.Passwordentry = ttk.Entry(self)
        self.Passwordentry.placeholder = "Enter Password Here"
        self.Passwordentry.config(foreground=PLACEHOLDER_COLOR)
        self.Passwordentry.pack(padx=10, pady=10)
        self.Passwordentry.insert(0, "Enter Password Here")
        self.Passwordentry.bind('<FocusIn>', lambda event: self.focus(event, isPass=True))
        self.Passwordentry.bind('<FocusOut>', lambda event: self.out(event, isPass=True))
        self.Passwordentry.bind('<Return>', self.enterData)
        
        button0 = ttk.Button(self, text = "Enter", command=self.enterData)
        button0.pack()

    def focus(self, event, isPass=False):
        widget = event.widget
        try: placeholder = widget.placeholder
        except AttributeError: return
        if widget.get() == placeholder:
            widget.delete(0,tk.END)
        widget.config(foreground=TYPED_COLOR)
        if isPass: widget.config(show='\u2022')

    def out(self, event, isPass=False):
        widget = event.widget
        try: placeholder = widget.placeholder
        except AttributeError: return
        if widget.get() == "":
            widget.insert(0, placeholder)
            widget.config(foreground=PLACEHOLDER_COLOR)
            if isPass: widget.config(show='')
            
    def nextWidget(self, event):
        event.widget.tk_focusNext().focus()

    def enterData(self, *event):
        username = self.UserNameentry.get()
        password = self.Passwordentry.get()
        print("trying creds")
        if amt.check_credentials(username, password): self.controller.show_frame(StartPage)
        else:
            messagebox.showwarning("Incorrect Credentials", "Credential check with the provided credentials failed. Please check your username and password and try again.")
        
    def UpdateData(self):
        pass


class StartPage(tk.Frame):
    """
    Class for front page.

    TODO: this is so so ugly right now.
    """
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)
        #label for Start Page
        label = tk.Label(self, text = "Start Page For GUI", font = LARGE_FONT)
        label.pack(pady = 10, padx = 10)
        
        wrapper1 = tk.LabelFrame(self)
        wrapper1.pack( padx = 20, pady = 10)
    
        #button1 - 4 represents all 4 current pages in the GUI
        button1 = ttk.Button(self, text="Design Page", command = lambda:controller.show_frame(PageOne))
        button1.pack()
        button2 = ttk.Button(self, text="Data Entry", command = lambda:controller.show_frame(PageTwo))
        button2.pack()
        button3 = ttk.Button(self, text = "Plotting", command =lambda:controller.show_frame(PageThree))
        button3.pack()
        button4 = ttk.Button(self, text= "PDR Status", command = lambda:controller.show_frame(PageFour))
        button4.pack()

    def UpdateData(self):
        pass


class PageOne(tk.Frame):
    """
    Class for PageOne represents the design page.

    The design page is the main page where users can add parameters and
    calculations to command files. As well plot box formats are included
    to allow users to add multiple plot boxes and page up and down.
    The design page also pulls in user input such as the engine number and build
    I.D. This allows data to be pulled into the design page and data entry page.
    """
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)

        global boxList
        boxList = []

        #defining rowlength, numRows as numbers so you can change number of rows instantly without changing variable names
        self.rowLength = 3
        self.numRows = 2
        self.maxBox = self.rowLength*self.numRows
        
        self.startI = 0
        self.boxIndex = 0

        self.controller = controller
        
        labelFrame = tk.Frame(self)
        labelFrame.pack(fill='x', padx=20, pady=10)
        label = ttk.Label(labelFrame, text = "Graph Design", font = LARGE_FONT)
        label.pack(side=tk.LEFT)

        buttonFrame = tk.Frame(self)
        buttonFrame.pack(fill='x', padx=20, pady=10)
        homeButton = ttk.Button(buttonFrame, text = "Home Page", command = lambda:controller.show_frame(StartPage))
        homeButton.pack(side=tk.LEFT)
        p1Button = ttk.Button(buttonFrame, text = "Design page", state='disabled', command = lambda:controller.show_frame(PageOne))
        p1Button.pack(side=tk.LEFT)
        p2Button = ttk.Button(buttonFrame, text = "Data Entry", command = lambda:controller.show_frame(PageTwo))
        p2Button.pack(side=tk.LEFT)
        p3Button = ttk.Button(buttonFrame, text = "Plotting", command = lambda:controller.show_frame(PageThree))
        p3Button.pack(side=tk.LEFT)
        p4Button = ttk.Button(buttonFrame, text = "PDR Status", command = lambda:controller.show_frame(PageFour))
        p4Button.pack(side=tk.LEFT)

        topSection = tk.Frame(self)
        topSection.pack(fill='x')

        ITELabelFrame = tk.LabelFrame(topSection, text="Define ITE Parameters")
        ITELabelFrame.pack(side=tk.LEFT, padx=20, pady=10)
        
        #labels and entries for Engine Numbers 
        self.label3 = ttk.Label(ITELabelFrame, text = "Engine Number :",font = SMALL_FONT)
        self.label3.grid(row = 0, column = 0, sticky = "nesw", padx=10)
        self.EngineNumberentry = ttk.Entry(ITELabelFrame, foreground=PLACEHOLDER_COLOR)

        try: self.EngineNumberentry.placeholder = str(amt.get_engine_no_from_JSON())
        except FileNotFoundError: self.EngineNumberentry.placeholder = "Engine Number"
        self.EngineNumberentry.grid(row = 0, column = 1, padx=10, pady=20)
        self.EngineNumberentry.insert(0, self.EngineNumberentry.placeholder)
        self.EngineNumberentry.bind('<FocusIn>', self.focus)
        self.EngineNumberentry.bind('<FocusOut>', self.out)
        self.EngineNumberentry.bind('<Return>', self.nextWidget)
        
        #Labels and entries for vehicleID 
        self.label2 = ttk.Label(ITELabelFrame, text = "Build Number : ", font = SMALL_FONT)
        self.label2.grid(row = 1, column = 0, sticky = "nesw", padx=10)
        self.VehicleID = ""
        self.vehicleIDentry = ttk.Entry(ITELabelFrame, foreground=PLACEHOLDER_COLOR)
        self.vehicleIDentry.grid(row = 1, column = 1, padx=10, pady=20)
        try: self.vehicleIDentry.placeholder = str(amt.get_build_no_from_JSON())
        except FileNotFoundError: self.vehicleIDentry.placeholder = "Build Number"
        self.vehicleIDentry.insert(0, self.vehicleIDentry.placeholder)
        self.vehicleIDentry.bind('<FocusIn>', self.focus)
        self.vehicleIDentry.bind('<FocusOut>', self.out)
        
        #Wrapper and frame setup for edit calculation cmdfile button design page
        calcLabelFrame = tk.LabelFrame(topSection, text = "Custom calculations")
        calcLabelFrame.pack(side = tk.LEFT,)
        self.label7 = ttk.Label(calcLabelFrame, text = "Define custom calculations",font = SMALL_FONT)
        self.label7.pack(padx=20, pady=20)
        # Button 5 when pressed calls the GraphPage function at top of script
        button5 = ttk.Button(calcLabelFrame, text = "ENTER", command = lambda: GraphPage("Add graphs page"))
        button5.pack(padx=20, pady=20)

        plotLabelFrame = tk.LabelFrame(self, text = "Define Plots", height = 453)
        plotLabelFrame.pack(fill='x', padx = 20, pady = 10)
        plotLabelFrame.pack_propagate(0)

        self.formatFrame = tk.Frame(plotLabelFrame)
        self.formatFrame.pack(fill='x')
        self.formatFrame.bind('<<deletebox>>', self.reorderBox)
        
        #page up and page down allows users to move up and down when adding many new plot boxes that runs off page. 
        controlsFrame = tk.Frame(plotLabelFrame)
        controlsFrame.pack(side=tk.BOTTOM, fill='x')
        newPlotBut = ttk.Button(controlsFrame, text="Make New Plot", width=30, command = self.makeNewPlot)
        newPlotBut.pack(side=tk.BOTTOM, pady=10)
        self.downButton = ttk.Button(controlsFrame, width=10,text="Page Down",command = self.pgdown)
        self.downButton.pack(side=tk.RIGHT, padx=10)
        self.upButton = ttk.Button(controlsFrame, width=10,text="Page Up",command = self.pgup)
        self.upButton.pack(side=tk.RIGHT)
        self.pageLabel = ttk.Label(controlsFrame, text = "page 0/0")
        self.pageLabel.pack(side=tk.RIGHT, padx=10)
        
        if self.startI == 0: self.upButton.state(["disabled"])
        else: self.upButton.state(["!disabled"])
        if self.startI+self.maxBox > len(boxList): self.downButton.state(["disabled"])
        else: self.downButton.state(["!disabled"])
        
        confirmInputBut = ttk.Button(self, text='Confirm Graph Setup', width=50, command = self.confirmInput)
        confirmInputBut.pack(padx=10, pady=20)

        self.makeNewPlot()

    def focus(self, event, isPass=False):
        """Clears placeholder text"""
        widget = event.widget
        try: placeholder = widget.placeholder
        except AttributeError: return
        if widget.get() == placeholder:
            widget.delete(0,tk.END)
        widget.config(foreground=TYPED_COLOR)
        if isPass: widget.config(show='\u2022')

    def out(self, event, isPass=False):
        widget = event.widget
        try: placeholder = widget.placeholder
        except AttributeError: return
        if widget.get() == "":
            widget.insert(0, placeholder)
            widget.config(foreground=PLACEHOLDER_COLOR)
            if isPass: widget.config(show='')
            
    def nextWidget(self, event):
        event.widget.tk_focusNext().focus()

    def enterEngineData(self, *event):
        global UpdateFlag
        UpdateFlag = True

        # get data
        self.EngineNumber = self.EngineNumberentry.get()
        self.VehicleID = self.get_VehicleBuildID()

        # create the JSON file for the given data
        try: self.BuildJson(self.EngineNumber, self.VehicleID)
        except ValueError: return

        # figure out if the user's script knows where the local comments are
        try: hasLC = amt.has_local_comment_file(self.EngineNumber, self.VehicleID)
        except FileNotFoundError:
            hasLC = False
            open(amt.COMMENT_FILE_PATHS, 'x').close()
        except PermissionError:
            messagebox.showwarning("Permission Error", "Failed to find the local comment file. Ensure you have logged into secure storage."
                                   + "\nLocal comments will not be shown until you restart the app.")
            return
        # and check that the local comments exist
        if not hasLC:
            ans = messagebox.askyesno("No Local Comments File", "No saved comment file found matching that engine and build number."
                                      + "\nWould you like to create one?")
            if ans:
                # create new local comment file!
                while True:
                    path = simpledialog.askstring("Input", "Enter the path to the directory to create or locate the local comments file.")
                    if path == None: return
                    elif os.path.isdir(path): break
                    else: messagebox.showwarning("Error", "The provided entry is not a valid path or does not point to an existing directory.")
                amt.create_comment_file(self.EngineNumber, self.VehicleID, path)

    def enterParms(self, event):
        self.get_parms()

    def UpdateData(self):
        pass

    # creates JSON if one doesn't exist, or updates an extant one
    def BuildJson(self, engineNumber, buildNumber):
        if not engineNumber[1:].isnumeric():
            messagebox.showerror("Error", "Invalid engine number")
            raise ValueError
        if not buildNumber.isnumeric():
            messagebox.showerror("Error", "Invalid build number")
            raise ValueError
        try:
            curEngineNum = amt.get_engine_no_from_JSON()
            curBuildNum = amt.get_build_no_from_JSON()
        except FileNotFoundError:
            # build JSON if one does not exist
            amt.create_JSON_file(engineNumber, buildNumber, [])
            return

        if curEngineNum != engineNumber or curBuildNum != buildNumber:
            amt.create_JSON_file(engineNumber, buildNumber, [])
        
        #Getters and setters for defined variables
    def get_VehicleBuildID(self):
        return self.vehicleIDentry.get()

    def set_VehicleBuildID(self):
        self.VehicleID = self.get_VehicleBuildID()

    def set_EngineNumber(self):
        self.EngineNumber = self.get_EngineNumber
        
    def get_EngineNumber(self):
        return self.EngineNumberentry.get()

    # box setup to get X parms and Y parms 
    def get_parms(self):
        global xGraphParms
        global yGraphParms
        xGraphParms, yGraphParms = ([], [])
        entries = [(self.XParmGraph1entry, self.YParmGraph1entry),
                   (self.XParmGraph2entry, self.YParmGraph2entry),
                   (self.XParmGraph3entry, self.YParmGraph3entry),
                   (self.XParmGraph4entry, self.YParmGraph4entry)]

        for entry in entries:
            xParm = entry[0].get().strip()
            yParm = entry[1].get().strip()
            
            if xParm == "Enter X Parm to Graph": continue
            elif xParm == "": continue
            elif yParm == "Enter Y Parm to Graph": continue
            elif yParm == "" : continue

            xGraphParms.append(xParm.upper())
            yGraphParms.append(yParm.upper())

        global UpdateFlag
        UpdateFlag = True
        print(xGraphParms, yGraphParms)

    def UpdateType(self, choice):
        print(choice)
        global DataType
        DataType = choice
        global UpdateFlag
        UpdateFlag = True
    # Allows for man new plot boxes to be populated and is called above as a function
    def makeNewPlot(self):
        global boxList

        if self.startI == 0: self.upButton.state(["disabled"])
        else: self.upButton.state(["!disabled"])
        if self.startI+self.maxBox > len(boxList): self.downButton.state(["disabled"])
        else: self.downButton.state(["!disabled"])
        
        newPlotBox = PlotBox(self.formatFrame,("plot "+str(self.boxIndex+1)))
        boxList.append(newPlotBox)
        self.boxIndex += 1
        self.reorderBox()

    def reorderBox(self, *event):
        for box in self.formatFrame.grid_slaves(): box.grid_forget()
        global boxList
        drawList = boxList[self.startI:min(self.startI+self.maxBox, len(boxList))]
        for index, box in enumerate(drawList):
            box.grid(row = index // self.rowLength, column = index % self.rowLength,
                        padx=10, pady=10)
            
        if len(boxList) == 0:
            self.pageLabel['text'] = "page 0 / 0"
            return
        elif len(boxList) <= self.rowLength*self.numRows:
            self.pageLabel['text'] = "page 1 / 1"
            return
        numPages = (len(boxList)-1)//(self.rowLength)
        curPage = self.startI//(self.rowLength) + 1
        self.pageLabel['text'] = "page %d / %d" % (curPage, numPages)

    # rebuildBoxlist is called by PrattGUI class and rebuilds the BoxList from contents of appdata folder 
    def rebuildBoxlist(self):
        print("Rebuilding...")
        global boxList

        boxList = []
        self.boxIndex = 0

        for plot in self.controller.plotList:

            subplotList = plot.subplotList
            dataType = plot.dataType
            sigmaCut = plot.sigmaCut

            if self.startI == 0: self.upButton.state(["disabled"])
            else: self.upButton.state(["!disabled"])
            if self.startI+self.maxBox > len(boxList): self.downButton.state(["disabled"])
            else: self.downButton.state(["!disabled"])
            
            newPlotBox = PlotBox(self.formatFrame,("plot "+str(self.boxIndex+1)))
            
            try:
                newPlotBox.XParmGraph1entry.delete(0, tk.END)
                newPlotBox.XParmGraph1entry.insert(0, subplotList[0][0])
                newPlotBox.YParmGraph1entry.delete(0, tk.END)
                newPlotBox.YParmGraph1entry.insert(0, subplotList[0][1])
            except IndexError:
                newPlotBox.XParmGraph1entry.insert(0, newPlotBox.XParmGraph1entry.placeholder)

            try:
                newPlotBox.XParmGraph2entry.delete(0, tk.END)
                newPlotBox.XParmGraph2entry.insert(0, subplotList[1][0])
                newPlotBox.YParmGraph2entry.delete(0, tk.END)
                newPlotBox.YParmGraph2entry.insert(0, subplotList[1][1])
            except IndexError:
                newPlotBox.XParmGraph2entry.insert(0, newPlotBox.XParmGraph2entry.placeholder)

            try:
                newPlotBox.XParmGraph3entry.delete(0, tk.END)
                newPlotBox.XParmGraph3entry.insert(0, subplotList[2][0])
                newPlotBox.YParmGraph3entry.delete(0, tk.END)
                newPlotBox.YParmGraph3entry.insert(0, subplotList[2][1])
            except IndexError:
                newPlotBox.XParmGraph3entry.insert(0, newPlotBox.XParmGraph3entry.placeholder)

            try:
                newPlotBox.XParmGraph4entry.delete(0, tk.END)
                newPlotBox.XParmGraph4entry.insert(0, subplotList[3][0])
                newPlotBox.YParmGraph4entry.delete(0, tk.END)
                newPlotBox.YParmGraph4entry.insert(0, subplotList[3][1])
            except IndexError:
                newPlotBox.XParmGraph4entry.insert(0, newPlotBox.XParmGraph4entry.placeholder)

            newPlotBox.TypeVar.set(dataType)
            if sigmaCut > 0:
                newPlotBox.CheckVar.set(True)
                newPlotBox.sigma.delete(0, tk.END)
                newPlotBox.sigma.insert(0, sigmaCut)
            else:
                newPlotBox.CheckVar.set(False)
                newPlotBox.sigma.state(['disabled'])
            
            boxList.append(newPlotBox)
            self.boxIndex += 1
        self.startI = 0
        self.reorderBox()
    #pgup starts at not zero and increments upto to 0 when user pages up
    def pgup(self):
        if self.startI >= self.rowLength:
            self.startI -= self.rowLength
            self.reorderBox()
        
        if self.startI == 0: self.upButton.state(["disabled"])
        else: self.upButton.state(["!disabled"])
        if self.startI+self.maxBox > len(boxList): self.downButton.state(["disabled"])
        else: self.downButton.state(["!disabled"])
    
    # pg down starts at 0 and is incremented up from zero
    def pgdown(self):
        if self.startI + self.maxBox <= len(boxList):
            self.startI += self.rowLength
            self.reorderBox()
            
        if self.startI == 0: self.upButton.state(["disabled"])
        else: self.upButton.state(["!disabled"])
        if self.startI+self.maxBox >= len(boxList): self.downButton.state(["disabled"])
        else: self.downButton.state(["!disabled"])

    # all different lists are defined as empty where boxlist and updateflag are labeled as global variables inside of the confirminput function 
    def confirmInput(self):
        global boxList
        global UpdateFlag
        UpdateFlag = True
        self.enterEngineData()
        
        self.controller.plotList= []

        for box in boxList:
            self.controller.plotList.append(box.get())


class PageTwo(tk.Frame):
    """
    Class for PageTwo for data entry.

    Data entry page pulls data from ITE when Test engineer enters engine number
    and build I.D Treeview diagrams are native to pythons tkinter and are
    preinstalled within the module scroll bar functionality is also part of
    treeview class
    """
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)

        self.controller = controller

        labelFrame = tk.Frame(self)
        labelFrame.pack(fill='x', padx=20, pady=10)
        label = ttk.Label(labelFrame, text = "Data Entry", font = LARGE_FONT)
        label.pack(side=tk.LEFT)

        buttonFrame = tk.Frame(self)
        homeButton = ttk.Button(buttonFrame, text = "Home Page", command = lambda:controller.show_frame(StartPage))
        homeButton.pack(side=tk.LEFT)
        p1Button = ttk.Button(buttonFrame, text = "Design Page", command = lambda:controller.show_frame(PageOne))
        p1Button.pack(side=tk.LEFT)
        p2Button = ttk.Button(buttonFrame, text = "Data Entry", state= 'disabled', command = lambda:controller.show_frame(PageTwo))
        p2Button.pack(side=tk.LEFT)
        p3Button = ttk.Button(buttonFrame, text = "Plotting", command = lambda:controller.show_frame(PageThree))
        p3Button.pack(side=tk.LEFT)
        p4Button = ttk.Button(buttonFrame, text = "PDR Status", command = lambda:controller.show_frame(PageFour))
        p4Button.pack(side=tk.LEFT)
        buttonFrame.pack(fill='x', padx=20, pady=10)    

        plottingFrame = tk.LabelFrame(self, text = "Plotting Points")
        plottingFrame.pack(fill = "both", expand = "yes", padx = 20, pady = 10)
        trvFrame = tk.Frame(plottingFrame)
        trvFrame.pack(fill = "none", expand = "false", padx=20, pady=10)

        # table for plotting data
        self.trv = ttk.Treeview(trvFrame, columns=(0,1,2,3,4,5),
                                show = "headings", height = "14", selectmode='browse')
        self.trv.pack(side = tk.LEFT)
       
        self.trv.column(0, minwidth=25, width=25, anchor=tk.CENTER) 
        self.trv.heading(1, text = "ADR Number")
        self.trv.column(1, minwidth=100, width=100, anchor=tk.CENTER) 
        self.trv.heading(2, text = "Run Number")
        self.trv.column(2, minwidth=100, width=100, anchor=tk.CENTER) 
        self.trv.heading(3, text = "Time Stamp")
        self.trv.column(3, minwidth=150, width=150, anchor=tk.W) 
        self.trv.heading(4, text = "ITE Comments")
        self.trv.column(4, minwidth=250, width=250, anchor=tk.W) 
        self.trv.heading(5, text = "Local Comments")
        self.trv.column(5, minwidth=250, width=250, anchor=tk.W)
        self.UpdateTree()

        #vertical scrollbar
        yscrollbar = ttk.Scrollbar(trvFrame, orient = "vertical", command = self.trv.yview)
        yscrollbar.pack(side = tk.RIGHT, fill = "y")
        self.trv.configure(yscrollcommand=yscrollbar.set)
        
        self.trv.bind('<Button-1>', self.handleCheckbox)
        self.trv.bind('<<TreeviewSelect>>', self.itemSelected)

        controlsFrame = tk.Frame(plottingFrame)
        controlsFrame.pack(fill = "both", expand = "yes", padx = 20, pady = 10)
        
        # Button that calls AddAdrNumber method 
        addButton = ttk.Button(controlsFrame, text = "Add ADR Number", command = self.AddAdrNumber)
        addButton.pack(side = tk.LEFT)
        self.AddADRNumberentry = ttk.Entry(controlsFrame, foreground=PLACEHOLDER_COLOR)
        self.AddADRNumberentry.pack(side = tk.LEFT, padx=5)
        self.AddADRNumberentry.placeholder = "ADR number"
        self.AddADRNumberentry.insert(0, self.AddADRNumberentry.placeholder)
        self.AddADRNumberentry.bind('<FocusIn>', self.focus)
        self.AddADRNumberentry.bind('<FocusOut>', self.out)
        self.AddADRNumberentry.bind('<Return>', self.AddAdrNumber)

        # nothing label to help with spacing
        ttk.Label(controlsFrame, text="    ").pack(side=tk.LEFT)
        
        #Button that calls DeleteAdrNumber method 
        delButton = ttk.Button(controlsFrame, text = "Delete ADR Number", command = self.DeleteAdrNumber)
        delButton.pack(side = tk.LEFT)
        self.DeleteADRNumberentry = ttk.Entry(controlsFrame, foreground=PLACEHOLDER_COLOR)
        self.DeleteADRNumberentry.pack(side = tk.LEFT, padx=5)
        self.DeleteADRNumberentry.placeholder = "ADR number"
        self.DeleteADRNumberentry.insert(0, self.DeleteADRNumberentry.placeholder)
        self.DeleteADRNumberentry.bind('<FocusIn>', self.focus)
        self.DeleteADRNumberentry.bind('<FocusOut>', self.out)
        self.DeleteADRNumberentry.bind('<Return>', self.DeleteAdrNumber)

        # nothing label to help with spacing
        ttk.Label(controlsFrame, text="    ").pack(side=tk.RIGHT)

        self.commentEntry = ttk.Entry(controlsFrame, foreground=TYPED_COLOR, width = 30, state="disabled")
        self.commentEntry.pack(side = tk.RIGHT)
        self.commentEntry.bind('<Return>', self.saveComment)
        self.commentEntry.bind('<FocusOut>', self.saveComment)
        self.commentEntry.bind('<KeyRelease>', self.editComment)
        self.commentLabel = ttk.Label(controlsFrame, text = "")
        self.commentLabel.pack(side=tk.RIGHT)
        
        # wrapper for ITE search widgets
        ITESearchFrame = tk.LabelFrame(self, text = "Search for ITE Data")
        ITESearchFrame.pack(fill = "both", expand = "yes", padx = 20, pady = 10)
        
        searchBoxFrame = tk.Frame(ITESearchFrame)
        searchBoxFrame.pack(padx = 20, pady = 10)

        addDateLabel = ttk.Label(searchBoxFrame, text = "Search by Date : ")
        addDateLabel.pack(side=tk.LEFT)

        # entries and buttons to initiate ITE search functionality
        self.AddDateEntry = ttk.Entry(searchBoxFrame, foreground=PLACEHOLDER_COLOR)
        self.AddDateEntry.pack(side=tk.LEFT)
        self.AddDateEntry.placeholder = "mm/dd/yyyy"
        self.AddDateEntry.insert(0, self.AddDateEntry.placeholder)
        self.AddDateEntry.bind('<FocusIn>', self.focus)
        self.AddDateEntry.bind('<FocusOut>', self.out)
        self.AddDateEntry.bind('<Return>', self.UpdateITETree_date)
       
        AddDateButton = ttk.Button(searchBoxFrame, text = "ENTER", command=self.UpdateITETree_date)
        AddDateButton.pack(side=tk.LEFT)

        # nothing label to help with spacing
        ttk.Label(searchBoxFrame, text="\t\t\t\t\t").pack(side=tk.LEFT)

        addRunLabel = ttk.Label(searchBoxFrame, text = "Search by Run Number : ")
        addRunLabel.pack(side=tk.LEFT)

        self.AddRunEntry = ttk.Entry(searchBoxFrame, foreground=PLACEHOLDER_COLOR)
        self.AddRunEntry.pack(side=tk.LEFT)
        self.AddRunEntry.placeholder = "Run Number"
        self.AddRunEntry.insert(0, self.AddRunEntry.placeholder)
        self.AddRunEntry.bind('<FocusIn>', self.focus)
        self.AddRunEntry.bind('<FocusOut>', self.out)
        self.AddRunEntry.bind('<Return>', self.UpdateITETree_run)
        
        # CURRENTLY, SEARCHING BY RUN NUMBER IS NOT YET IMPLEMENTED
        # TODO: do that.
        AddRunButton = ttk.Button(searchBoxFrame, text = "ENTER", command=self.UpdateITETree_run)
        AddRunButton.pack(side=tk.LEFT)

        trvFrame = tk.Frame(ITESearchFrame)
        trvFrame.pack(fill = "none", expand = "false", padx = 20, pady = 10)
        
        # treeview where ITE data is displayed 
        self.ITEtrv = ttk.Treeview(trvFrame, columns=(0,1,2,3,4,5),
                                show = "headings", height = "14", selectmode='browse')
        self.ITEtrv.pack(side = tk.LEFT)
       
        self.ITEtrv.column(0, minwidth=25, width=25, anchor=tk.CENTER) 
        self.ITEtrv.heading(1, text = "ADR Number")
        self.ITEtrv.column(1, minwidth=100, width=100, anchor=tk.CENTER) 
        self.ITEtrv.heading(2, text = "Run Number")
        self.ITEtrv.column(2, minwidth=100, width=100, anchor=tk.CENTER) 
        self.ITEtrv.heading(3, text = "Time Stamp")
        self.ITEtrv.column(3, minwidth=150, width=150, anchor=tk.W) 
        self.ITEtrv.heading(4, text = "ITE Comments")
        self.ITEtrv.column(4, minwidth=250, width=250, anchor=tk.W) 
        self.ITEtrv.heading(5, text = "Local Comments")
        self.ITEtrv.column(5, minwidth=250, width=250, anchor=tk.W)

        #Vertical scrollbar capability 
        yscrollbar2 = ttk.Scrollbar(trvFrame, orient = "vertical", command = self.ITEtrv.yview)
        yscrollbar2.pack(side = tk.RIGHT, fill = "y")
        self.ITEtrv.configure(yscrollcommand = yscrollbar2.set)
        
        addButton = ttk.Button(ITESearchFrame, text = "Add Point to Graph Set", command=self.addSelPoint)
        addButton.pack()

        # dummy frame to force proper spacing
        ttk.Frame(self).pack(pady=25)
        
        global commentUpdateFlag
        commentUpdateFlag = False

    def focus(self, event, isPass=False):
        widget = event.widget
        try: placeholder = widget.placeholder
        except AttributeError: return
        if widget.get() == placeholder:
            widget.delete(0,tk.END)
        widget.config(foreground=TYPED_COLOR)
        if isPass: widget.config(show='\u2022')

    def out(self, event, isPass=False):
        widget = event.widget
        try: placeholder = widget.placeholder
        except AttributeError: return
        if widget.get() == "":
            widget.insert(0, placeholder)
            widget.config(foreground=PLACEHOLDER_COLOR)
            if isPass: widget.config(show='')
            
    def nextWidget(self, event):
        event.widget.tk_focusNext().focus()

    # Add adr number function 
    # *event is used to allow this to be called with or without event argument
    def AddAdrNumber(self, *event):
        global UpdateFlag
        UpdateFlag = True

        ADRNum = self.AddADRNumberentry.get()
        try: ADRNumInt = int(ADRNum)
        except ValueError: return
        amt.append_to_JSON([ADRNumInt])

        comment, RunNo, timestamp  = amt.return_run_data_from_JSON(ADRNumInt)
        EngineNumber = amt.get_engine_no_from_JSON()
        BuildNumber = amt.get_build_no_from_JSON()
        Box = '\u2612' if amt.get_graph_flag(ADRNumInt) else '\u2610'
        try: LocalComment = amt.get_local_comment(EngineNumber, BuildNumber, ADRNum)
        except Exception as e:
            LocalComment = ""
            print(e)
        print(LocalComment)
        
        for i, entry in enumerate(self.trv.get_children()):
            if self.trv.item(entry)["values"][1]==ADRNumInt:
                messagebox.showerror("Error", "ADR number is already in graph data")
                break
            elif self.trv.item(entry)["values"][1]>=ADRNumInt:
                self.trv.insert('', i, values=(Box, ADRNum, RunNo, timestamp, comment, LocalComment))
                break
        else:
            self.trv.insert('', tk.END, values=(Box, ADRNum, RunNo, timestamp, comment, LocalComment))
            
    # Delete adr number function with error checking if ADR number does not exist 
    # *event is used to allow this to be called with or without event argument
    def DeleteAdrNumber(self, *event):
        global UpdateFlag
        UpdateFlag = True
        
        if amt.get_adr_list_from_JSON() == []:
            messagebox.showerror("Error", "No ADR numbers to remove")
            return

        ADRNum = self.AddADRNumberentry.get()
        try: ADRNumInt = int(ADRNum)
        except ValueError: return
        amt.remove_from_JSON([ADRNumInt])
        for entry in self.trv.get_children():
            if self.trv.item(entry)["values"][1]==ADRNumInt:
                self.trv.delete(entry)
                break
        else:
            messagebox.showerror("Error", "ADR number is not in graph data")

    def UpdateTree(self):
        try:
            ADRList = amt.get_adr_list_from_JSON()
            EngineNumber = amt.get_engine_no_from_JSON()
            BuildNumber = amt.get_build_no_from_JSON()
        except FileNotFoundError: ADRList = []
        for entry in self.trv.get_children():
            self.trv.delete(entry)
        
        for i, ADRNumber in enumerate(ADRList):
            comment, RunNo, timestamp  = amt.return_run_data_from_JSON(ADRNumber)
            Box = '\u2612' if amt.get_graph_flag(ADRNumber) else '\u2610'
            try: LocalComment = amt.get_local_comment(EngineNumber, BuildNumber, ADRNumber)
            except Exception as e:
                #print(e)
                LocalComment = ""
            self.trv.insert('', tk.END, values=(Box, ADRNumber,RunNo, timestamp, comment, LocalComment))
            
    def DeleteFromTree(self):
        global UpdateFlag
        UpdateFlag = True
        for entry in self.trv.get_children():
            self.trv.delete(entry)
        self.UpdateTree()

    def handleCheckbox(self, event):
        x, y = event.x, event.y

        if self.trv.identify_column(x) != '#1': return

        iid = self.trv.identify_row(y)
        
        adr_no = self.trv.item(iid)['values'][1]
        curFlag = True if self.trv.item(iid)['values'][0] == '\u2612' else False
        amt.set_graph_flag(adr_no, flag_val=not curFlag)
        newBox = '\u2610' if curFlag else '\u2612'
        newVals = [newBox] + self.trv.item(iid)['values'][1:]
        self.trv.item(iid, values=newVals)
        global UpdateFlag
        UpdateFlag = True

    # called whenever an item in the data entry treeview is selected
    # used to load the local comment into the comment entry box for editing
    def itemSelected(self, event):
        item = self.trv.item(self.trv.selection()[0])
        localComment = item['values'][-1]
        self.curADRNum = int(item['values'][1])

        self.commentLabel["text"] = "Comment for ADR number %s : "%self.curADRNum
        
        self.commentEntry.state(["!disabled"])
        self.commentEntry.delete(0, tk.END)
        self.commentEntry.insert(0, localComment)
    
    # bound to any keyboard releases in the comment entry box (that is, whenvever
    # something is typed in the box)
    # edits the corresponding entry in the treeview and queues a save to the comment file
    def editComment(self, *event):
        try: app.after_cancel(self.saveCall)
        except: pass
        
        item = self.trv.item(self.trv.selection()[0])

        newVals = item['values']
        newVals[-1] = self.commentEntry.get()
        self.trv.item(self.trv.selection()[0], values = newVals)

        # if the user doesn't make an edit within 750ms, save the comment
        # (prevents the user from closing the app without saving but
        # prevents saving if they're still typing)
        self.saveCall = app.after(750, self.saveComment)
            
    # saves the currently active local comment to the corresponding file
    def saveComment(self, *event):
        # the file operations are time-consuming, so don't run them
        # until the user has clicked away from the box (and is thus done
        # editing) or until they've been idle
        localComment = self.commentEntry.get()
        EngineNumber = amt.get_engine_no_from_JSON()
        BuildNumber = amt.get_build_no_from_JSON()

        amt.add_local_comment(EngineNumber, BuildNumber, self.curADRNum, localComment)

        # flag local comments to be redrawn
        global commentUpdateFlag
        commentUpdateFlag = True
    
    # UpdateITETree function used to get user input data such as Enginer number and build I.D.
    # *event is used to allow this to be called with or without event argument
    def UpdateITETree_date(self, *event):
        #print('updating')
        DateStr = self.AddDateEntry.get()
        self.AddDateEntry.delete(0, tk.END)

        EngineNumber = amt.get_engine_no_from_JSON()
        BuildNumber = amt.get_build_no_from_JSON()
        #print(EngineNumber, BuildNumber)

        for entry in self.ITEtrv.get_children():
            self.ITEtrv.delete(entry)
            
        data = amt.get_ITE_data_for_date(EngineNumber, BuildNumber, DateStr)
        if data == []:
            messagebox.showinfo("No Data Found", "No ITE data was found from that date for the given engine")
        for i, point in enumerate(data):
            ADRNumber, RunNo, timestamp, comment = point 
            try: LocalComment = amt.get_local_comment(EngineNumber, BuildNumber, ADRNumber)
            except (FileNotFoundError, KeyError): LocalComment = ""
            self.ITEtrv.insert('', i, i, text='', values=("", ADRNumber, RunNo, timestamp, comment, LocalComment))

    def UpdateITETree_run(self, *args):
        pass

    def addSelPoint(self):
        global UpdateFlag
        UpdateFlag = True

        item = self.ITEtrv.item(self.ITEtrv.selection()[0])
        ADRNum = int(item['values'][1])
        amt.append_to_JSON([ADRNum])

        comment, RunNo, timestamp  = amt.return_run_data_from_JSON(ADRNum)
        EngineNumber = amt.get_engine_no_from_JSON()
        BuildNumber = amt.get_build_no_from_JSON()
        Box = '\u2612' if amt.get_graph_flag(ADRNum) else '\u2610'
        try: LocalComment = amt.get_local_comment(EngineNumber, BuildNumber, ADRNum)
        except Exception as e:
            LocalComment = ""
            print(e)
        print(LocalComment)
        
        for i, entry in enumerate(self.trv.get_children()):
            if self.trv.item(entry)["values"][1]==ADRNum:
                messagebox.showerror("Error", "ADR number is already in graph data")
                break
            elif self.trv.item(entry)["values"][1]>=ADRNum:
                self.trv.insert('', i, values=(Box, str(ADRNum), RunNo, timestamp, comment, LocalComment))
                break
        else:
            self.trv.insert('', tk.END, values=(Box, str(ADRNum), RunNo, timestamp, comment, LocalComment))

    def UpdateData(self):
        global commentUpdateFlag
        if commentUpdateFlag:
            self.UpdateTree()


class PageThree(tk.Frame):
    """
    Class for PageThree for plotting graphs

    Page three uses matplotlib to plot data into its correct format 
    The updatedata function allows for data to be automatically updated 
    and displayed to the plotting page. As well there is currently error
    checking to inform the user when the data they have pulled or the parameters
    they've selected are not valid anymore. This includes if there are improper
    SQL querys performed as well if there are missing JSON files that prevent
    parameters from being performed.
    """
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)

        self.controller = controller

        labelFrame = tk.Frame(self)
        labelFrame.pack(fill='x', padx=20, pady=10)
        label = ttk.Label(labelFrame, text = "Plotting", font = LARGE_FONT)
        label.pack(side=tk.LEFT)

        buttonFrame = tk.Frame(self)
        homeButton = ttk.Button(buttonFrame, text = "Home Page", command = lambda:controller.show_frame(StartPage))
        homeButton.pack(side=tk.LEFT)
        p1Button = ttk.Button(buttonFrame, text = "Design Page", command = lambda:controller.show_frame(PageOne))
        p1Button.pack(side=tk.LEFT)
        p2Button = ttk.Button(buttonFrame, text = "Data Entry", command = lambda:controller.show_frame(PageTwo))
        p2Button.pack(side=tk.LEFT)
        p3Button = ttk.Button(buttonFrame, text = "Plotting", state='disabled', command = lambda:controller.show_frame(PageThree))
        p3Button.pack(side=tk.LEFT)
        p4Button = ttk.Button(buttonFrame, text = "PDR Status", command = lambda:controller.show_frame(PageFour))
        p4Button.pack(side=tk.LEFT)

        buttonFrame.pack(fill='x', padx=20, pady=10)

        self.tabFrame = tk.Frame(self)
        self.tabFrame.select = 0
        self.tabFrame.subplotList = ""
        self.tabFrame.dataType = ""
        self.tabFrame.pack(fill='x', padx=20, pady=10)

        #Automatically updates page with data from data entry page
        self.tabFrame.bind('<<tabswitch>>', lambda e: self.UpdateData())
        
    def UpdateData(self):
        print("updating")
        self.plotList = self.controller.plotList
        self.width = self.controller.winfo_screenwidth()

        try: self.messageFrame.destroy()
        except: pass
        try:
            self.canvas.get_tk_widget().destroy()
            self.toolbar.destroy()
        except Exception as e: pass
        try:
            for child in self.tabFrame.winfo_children():
                child.destroy()
        except Exception as e: pass
        
        if self.plotList == []:
            self.messageFrame = tk.Frame(self)
            self.messageFrame.pack()
            warning = ttk.Label(self.messageFrame, text = "No Data to Display", font = LARGE_FONT)
            tk.Frame(self.messageFrame).pack(fill='y', expand='yes')
            warning.pack()
            tk.Frame(self.messageFrame).pack(fill='y', expand='yes')
            return
        
        global UpdateFlag
        if UpdateFlag:
            #there's an easier way, just would take time
            self.tabFrame.subplotList = self.plotList[0].subplotList
            self.tabFrame.dataType = self.plotList[0].dataType
            self.tabFrame.sigmaCut = self.plotList[0].sigmaCut

        width = min(10, self.width/len(self.plotList))
        for i, plot in enumerate(self.plotList):
            newtab = GraphTabButton(self.tabFrame, "Plot "+str(i+1), i, plot.subplotList,
                                    plot.dataType, plot.sigmaCut, width=width)
            newtab.pack(side=tk.LEFT)

        # using a set removes duplicates
        graphParms = set()
        for plot in self.plotList:
            for subplot in plot.subplotList:
                graphParms.add(subplot[0])
                graphParms.add(subplot[1])
                
        graphParms = list(graphParms)

        typeList = list(set([plot.dataType for plot in self.plotList]))
        
        if graphParms == []:
            self.messageFrame = tk.Frame(self)
            self.messageFrame.pack()
            warning = ttk.Label(self.messageFrame, text = "No Data to Display", font = LARGE_FONT)
            tk.Frame(self.messageFrame).pack(fill='y', expand='yes')
            warning.pack()
            tk.Frame(self.messageFrame).pack(fill='y', expand='yes')
            return

        try: self.messageFrame.destroy()
        except: pass
        self.messageFrame = tk.Frame(self)
        self.messageFrame.pack()
        warning = ttk.Label(self.messageFrame, text = "Data Loading...", font = LARGE_FONT)
        tk.Frame(self).pack(fill='y', expand='yes')
        warning.pack()
        tk.Frame(self).pack(fill='y', expand='yes')
        self.update()
        
        dataDict = dict()
        for DataType in typeList:
            if UpdateFlag or not os.path.exists("amt_appdata/graph_data_cache"+'_'+DataType+".pkl"):
                try:
                    ADRList = amt.get_adr_list_from_JSON()
                    if ADRList == []:
                        messagebox.showerror("Error", "Empty list of ADR numbers. Ensure data entry page is non-empty")
                    dataDict[DataType] = amt.generate_graph_frame(amt.get_dataframe_files(amt.get_engine_no_from_JSON(),
                                                                  amt.get_build_no_from_JSON(),
                                                                  ADRList,
                                                                  data_type=DataType),
                                      graphParms, data_type=DataType, cache_data=True)
                except (SyntaxError, ValueError) as e:
                    #raise e
                    messagebox.showerror("Error", "Error when parsing the following line: "+str(e.args))
                    dataDict[DataType] = pd.DataFrame()
                except NameError as e:
                    #raise e
                    messagebox.showerror("Error", "Variable "+str(e.args)+" referenced before definition")
                    dataDict[DataType] = pd.DataFrame()
                except FileNotFoundError as e:
                    #raise e
                    messagebox.showerror("Error", "Missing JSON file. Ensure engine number and build number are correct")
                    dataDict[DataType] = pd.DataFrame()
                except Exception as e:
                    #raise e
                    messagebox.showerror("Error", "Bad SQL query. See error log for more information")
                    dataDict[DataType] = pd.DataFrame()
                
            else: dataDict[DataType] = pd.read_pickle("amt_appdata/graph_data_cache"+'_'+DataType+".pkl")
        UpdateFlag = False
        
        self.messageFrame.destroy()

        self.messageFrame = tk.Frame(self)
        self.messageFrame.pack()
        warning = ttk.Label(self.messageFrame,
                                text = "Error generating graph data",
                                font = LARGE_FONT)
        warning2 = ttk.Label(self.messageFrame,
                                text = "Ensure all parameters are defined in dataset or command file",
                                font = NORM_FONT)
        warning3 = ttk.Label(self.messageFrame,
                                text = "See error log for more information",
                                font = NORM_FONT)
        tk.Frame(self.messageFrame).pack(fill='y', expand='yes')
        warning.pack()
        warning2.pack()
        warning3.pack()
        tk.Frame(self.messageFrame).pack(fill='y', expand='yes')

        #print(dataDict[self.tabFrame.dataType].columns)

        df, shift_dict = amt.get_shifts(dataDict[self.tabFrame.dataType],
                                        self.tabFrame.subplotList, self.tabFrame.sigmaCut)
        
        print(self.tabFrame.subplotList)
        if df.empty: return

        currParms = []
        for entry in self.tabFrame.subplotList:
            currParms.append(entry[0])
            currParms.append(entry[1])
        
        if not df.loc[:,currParms].notnull().all().all():
            parm_list = []
            for parm in currParms:
                if not df[parm].notnull().any(): parm_list.append(parm)
            if parm_list != []:
                warning3.destroy()
                warning3 = ttk.Label(self.messageFrame,
                                text = "The following are invalid: " + ', '.join(parm_list),
                                font = NORM_FONT)
                warning3.pack()
            return
            
        self.messageFrame.destroy()

        self.graph = Figure(figsize=(12,8), dpi = 100)

        if len(self.tabFrame.subplotList) == 1: rows, cols = (1,1)
        elif len(self.tabFrame.subplotList) == 2: rows, cols = (2,1)
        else: rows, cols = (2,2)
        
        i = 1 
        for xParm, yParm in self.tabFrame.subplotList:
            subplt = self.graph.add_subplot(rows, cols, i)
            color_list = ['tab:blue' if cond else 'tab:orange' for cond in df['valid_'+yParm+'_'+xParm]]
            subplt.scatter(df[xParm], df[yParm], c=color_list)
            subplt.set_title(yParm +" vs "+ xParm)

            if yParm == 'DELTA_YWFBQWFT' and xParm == 'YTAC':
                subplt.axhline(0, color='black')
                subplt.axhline(1, color='grey', dashes=(2,4))
                subplt.axhline(-1, color='grey', dashes=(2,4))
                subplt.axhline(2, color='lightgrey', dashes=(2,5))
                subplt.axhline(-2, color='lightgrey', dashes=(2,5))
            i+=1

            shift_list = shift_dict[yParm +'_'+ xParm]
            for shift in shift_list:
                subplt.axvline(shift, color = 'red')

        plt.tight_layout(h_pad=2)
        
        self.canvas = FigureCanvasTkAgg(self.graph, self)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack()

        try: self.toolbar = NavigationToolbar2Tk(self.canvas, self)
        except: self.toolbar = NavigationToolbar2TkAgg(self.canvas, self)
        self.toolbar.update()
        self.toolbar.pack(fill='x')

class PageFour(tk.Frame):
    """
    Class for PageFour for PDR status

    Page four contains final PDR data that has been checked through 
    the backend code. Once these checks are done in the backend
    it results in valid or not valid pdr data print checks in the treeview 
    diagram. Line 1522 inhibits the PDR data being populated. If you get rid of 
    the return statement on that line it will perform the PDR check but cause an increase
    of time needed to be calculated. This is specifically done by the update data function
    """
    def __init__(self, parent, controller):
        tk.Frame.__init__(self, parent)

        labelFrame = tk.Frame(self)
        labelFrame.pack(fill='x', padx=20, pady=10)
        label = ttk.Label(labelFrame, text = "PDR Status Table", font = LARGE_FONT)
        label.pack(side=tk.LEFT)

        buttonFrame = tk.Frame(self)
        homeButton = ttk.Button(buttonFrame, text = "Home Page", command = lambda:controller.show_frame(StartPage))
        homeButton.pack(side=tk.LEFT)
        p1Button = ttk.Button(buttonFrame, text = "Design Page", command = lambda:controller.show_frame(PageOne))
        p1Button.pack(side=tk.LEFT)
        p2Button = ttk.Button(buttonFrame, text = "Data Entry", command = lambda:controller.show_frame(PageTwo))
        p2Button.pack(side=tk.LEFT)
        p3Button = ttk.Button(buttonFrame, text = "Plotting", command = lambda:controller.show_frame(PageThree))
        p3Button.pack(side=tk.LEFT)
        p4Button = ttk.Button(buttonFrame, text = "PDR Status", state='disabled', command = lambda:controller.show_frame(PageFour))
        p4Button.pack(side=tk.LEFT)
        buttonFrame.pack(fill='x', padx=20, pady=10)
        
        wrapper1 = tk.LabelFrame(self, text = "Display Information")
        wrapper1.pack(fill = "both", expand = "yes", padx = 20, pady = 10)
        trvFrame = tk.Frame(wrapper1)
        trvFrame.pack(fill = "none", expand = "false", padx=20, pady=10)
        self.trv = ttk.Treeview(trvFrame, columns=(1,2,3,4,5), show = "headings", height = "30")
        self.trv.pack(side = tk.LEFT)
       
        self.trv.heading(1, text = "ADR Number")
        self.trv.column(1, minwidth=100, width=100, anchor=tk.CENTER) 
        self.trv.heading(2, text = "Run Number")
        self.trv.column(2, minwidth=100, width=100, anchor=tk.CENTER) 
        self.trv.heading(3, text = "Time Stamp")
        self.trv.column(3, minwidth=150, width=150, anchor=tk.W) 
        self.trv.heading(4, text = "Local Comment")
        self.trv.column(4, minwidth=250, width=250, anchor=tk.W) 
        self.trv.heading(5, text = "PDR Status")
        self.trv.column(5, minwidth=250, width=250, anchor=tk.W) 
        self.trv.bind('<<TreeviewSelect>>', self.itemSelected)
        
        #vertical scrollbar
        yscrollbar = ttk.Scrollbar(trvFrame, orient = "vertical", command = self.trv.yview)
        yscrollbar.pack(side = tk.RIGHT, fill = "y")
        self.trv.configure(yscrollcommand=yscrollbar.set)
        
        controlsFrame = tk.Frame(wrapper1)
        controlsFrame.pack(fill = "x", padx = 20, pady = 10)

        # dummy text for spacing
        ttk.Label(controlsFrame, text="\t"*7).pack(side=tk.RIGHT)
        
        self.commentEntry = ttk.Entry(controlsFrame, foreground=TYPED_COLOR, width = 30, state="disabled")
        self.commentEntry.pack(side = tk.RIGHT)
        self.commentEntry.bind('<Return>', self.saveComment)
        self.commentEntry.bind('<FocusOut>', self.saveComment)
        self.commentEntry.bind('<KeyRelease>', self.editComment)
        self.commentLabel = ttk.Label(controlsFrame, text = "")
        self.commentLabel.pack(side=tk.RIGHT)
        
    def UpdateData(self):
        if not UpdateFlag and not commentUpdateFlag: return
        
        try: ADRList = amt.get_adr_list_from_JSON()
        except FileNotFoundError: return
        if ADRList == []: return
        EngineNumber = amt.get_engine_no_from_JSON()
        BuildNumber = amt.get_build_no_from_JSON()
        for entry in self.trv.get_children():
            self.trv.delete(entry)
        df_file = amt.get_dataframe_files(EngineNumber, BuildNumber, ADRList, data_type='PDR')
        for i, point in enumerate(amt.check_PDR(df_file, ADRList)):
            adr_num, run_no, time, message = point
            try: localComment = amt.get_local_comment(EngineNumber, BuildNumber, adr_num)
            except Exception as e:
                #print(e)
                LocalComment = ""
            self.trv.insert('', i, i, text='', values=(adr_num, run_no, time, localComment, message))
            
    def itemSelected(self, event):
        item = self.trv.item(self.trv.selection()[0])
        localComment = item['values'][-2]
        self.curADRNum = int(item['values'][0])

        self.commentLabel["text"] = "Comment for ADR number %s : "%self.curADRNum
        
        self.commentEntry.state(["!disabled"])
        self.commentEntry.delete(0, tk.END)
        self.commentEntry.insert(0, localComment)

    def editComment(self, *event):
        try: app.after_cancel(self.saveCall)
        except: pass
        
        item = self.trv.item(self.trv.selection()[0])

        newVals = item['values']
        newVals[-2] = self.commentEntry.get()
        self.trv.item(self.trv.selection()[0], values = newVals)

        # if the user doesn't make an edit within 750ms, save the comment
        # (prevents the user from closing the app without saving but
        # prevents saving if they're still typing)
        self.saveCall = app.after(750, self.saveComment)
            
    def saveComment(self, *event):
        # the file operations are time-consuming, so don't run them
        # until the user has clicked away from the box (and is thus done
        # editing)
        localComment = self.commentEntry.get()
        EngineNumber = amt.get_engine_no_from_JSON()
        BuildNumber = amt.get_build_no_from_JSON()

        amt.add_local_comment(EngineNumber, BuildNumber, self.curADRNum, localComment)

        global commentUpdateFlag
        commentUpdateFlag = True
        
#function for master class 
app = PrattGUI()
app.geometry("1500x1000")
app.mainloop()
