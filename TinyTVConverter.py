# http://stackoverflow.com/questions/29158220/tkinter-understanding-mainloop
# http://stackoverflow.com/questions/24330178/scrolling-progress-bar-in-tkinter
# http://www.programcreek.com/python/example/5376/subprocess.STARTUPINFO
# https://superuser.com/questions/547296/resizing-videos-with-ffmpeg-avconv-to-fit-into-static-sized-player

#drag and drop files- apparently this needs a Tk extension (DONE)
#unicode filenames- hopefully this works with python3, tbd
#better error messages?
#check with random file types
#check conversion command params
#adjust bit rate calculation (DONE)
#add version number

#Add settings to UI

import os
import sys
import argparse
import subprocess as sp
from multiprocessing import Process, Queue, Pool
import re
import json
import time

from tkinter import IntVar, DoubleVar, StringVar, BOTH, Text, Menu, END, X, W, E, NW, PhotoImage, Image, Canvas, Listbox, Toplevel, Grid, messagebox, simpledialog
from tkinter import Label as tkLabel
import tkinter.filedialog
from tkinter.ttk import Progressbar, Style, Button, Radiobutton, Checkbutton, Frame, Label, LabelFrame, Entry, Scrollbar, Combobox, Notebook, Scale

import threading

import sv_ttk
import darkdetect
import webbrowser

from tkinterdnd2 import Tk, DND_FILES

import serial.tools.list_ports
from common import SerIO
from serial import SerialException

from VideoOutputSettings import VideoOutputSettingsClass

from Tooltip import CreateToolTip

from FFMPEGCommands import getAVIConvertCommand, getMP4ConvertCommand, getPreviewFrameCommand

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        # PyInstaller creates a temp folder and stores path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)

FFMPEG_BIN = resource_path('ffmpeg') if sys.platform == 'darwin' else resource_path('ffmpeg.exe')

class TinyTVConverter(Frame):

    def __init__(self, parent):

        self.VideoOutputSettings = VideoOutputSettingsClass()

        self.vidPipe = None

        Frame.__init__(self, parent)   #, background="white"
        self.parent = parent
        self.initVideoData()
        self.progressBarVar = IntVar()

        self.batchDirectory = Text()
        self.batchDirectory.delete('1.0', tkinter.END)
        self.batchOutputDirectory = Text()
        self.batchOutputDirectory.delete('1.0', tkinter.END)
        self.filesToConvert = []
        self.ttvPort = None
        self.initUI()

    def initVideoData(self):
        #currently constants

        #variables that are displayed
        self.inputFile = '-'
        self.outputFile = '-'
        self.durationString = "--:--:--"
        self.outputSize = 0

        self.accumTime = 0
        self.totalTime = 0

        #variables that change when video or options selected
        self.durationSeconds = 0.0
        self.inputVidFrameBytes = 0
        self.outputVidFrameBytes = 0
        self.audioFrameBytes = 0
        self.totalFrames = 0.0
        self.volumeAdjust = 0.0

        self.loopVideoSetting = IntVar()
        self.liveVideoSetting = IntVar()
        self.alphabetizePlaybackSetting = IntVar()
        self.showStaticSetting = IntVar()
        self.showChannelNumberSetting = IntVar()
        self.showVolumeSetting = IntVar()
        self.randomStartTimeSetting = IntVar()
        self.randomStartChannelSetting = IntVar()

        self.inputVidFrameBytes = self.VideoOutputSettings.outputWidth*self.VideoOutputSettings.outputHeight*2
        if (self.VideoOutputSettings.videoBitDepth.get() == 8):
            self.outputVidFrameBytes=self.inputVidFrameBytes/2
        else:
            self.outputVidFrameBytes=self.inputVidFrameBytes

        self.audioFrameBytes=self.VideoOutputSettings.tsvAudioSampleCountPerFrame*2

        self.totalFrames=self.durationSeconds*self.VideoOutputSettings.outputFrameRate
        print("Duration: "+str(self.durationSeconds))
        print(self.VideoOutputSettings.outputBytesPerSecond)
        self.outputSize=self.durationSeconds*self.VideoOutputSettings.outputBytesPerSecond

    def click(self, event):
        # Here retrieving the size of the parent
        # widget relative to master widget
        x = event.x_root - self.winfo_rootx()
        y = event.y_root - self.winfo_rooty()

        # Here grid_location() method is used to
        # retrieve the relative position on the
        # parent widget
        z = self.grid_location(x, y)

    def showBatchDirectoryList(self):
        self.PreviewThumbnail.grid_forget()
        self.PreviewFrame.columnconfigure(0, weight=1)
        self.PreviewFrame.rowconfigure(1, weight=1)
        self.PreviewListbox.grid(row=1, column=0, sticky='nsew')
        self.ListScrollbar.grid(row=1,column=1,sticky='nsew')

    def showVideoThumbnail(self):
        self.PreviewListbox.grid_forget()
        self.ListScrollbar.grid_forget()
        self.PreviewThumbnail.grid(row=1, column=0)

    def serialWrite(self, command):
        if(self.ttvPort is not None):
            print(f"\n\rWriting serial command: \"{command}\"")
            self.ttvPort.ser.write(command.encode('utf-8'))
            self.ttvPort.ser.flush()
        else:
            messagebox.showwarning("No TinyTV device!", "Please select a device.")
            pass

    def writeLoopVideoSetting(self):
        if self.ttvPort is not None:
            if self.loopVideoSetting.get() != 0:
                self.serialWrite("{SET: loopVideo=true}")
            else:
                self.serialWrite("{SET: loopVideo=false}")
            # for i in range(10):
            #     line = self.ttvPort.ser.readline().decode("utf-8")
            #     print(line)
        else:
            self.loopVideoSetting.set(not self.loopVideoSetting.get())
            messagebox.showwarning("No TinyTV device!", "Please select a device.")

    def writeVolumeSetting(self, event):
        if self.ttvPort is not None:
            vol = int(self.volumeSliderVar.get() * 6 / 100 + 0.5)
            self.volumeSliderVar.set(vol * 100 / 6)
            self.serialWrite("{" + f"SET: volume={vol}" + "}")
            # for i in range(10):
            #     line = self.ttvPort.ser.readline().decode("utf-8")
            #     print(line)
        elif self.volumeSlider["state"] == 'enabled':
            messagebox.showwarning("No TinyTV device!", "Please select a device.")

    def writeLiveVideoSetting(self):
        if self.ttvPort is not None:
            if self.liveVideoSetting.get() != 0:
                self.serialWrite("{SET: liveVideo=true}")
            else:
                self.serialWrite("{SET: liveVideo=false}")
            # for i in range(10):
            #     line = self.ttvPort.ser.readline().decode("utf-8")
            #     print(line)
        else:
            self.liveVideoSetting.set(not self.liveVideoSetting.get())
            messagebox.showwarning("No TinyTV device!", "Please select a device.")

    def writeAlphabetizePlaybackSetting(self):
        if self.ttvPort is not None:
            if self.alphabetizePlaybackSetting.get() != 0:
                self.serialWrite("{SET: alphabetize=true}")
            else:
                self.serialWrite("{SET: alphabetize=false}")
            # for i in range(10):
            #     line = self.ttvPort.ser.readline().decode("utf-8")
            #     print(line)
        else:
            self.alphabetizePlaybackSetting.set(not self.alphabetizePlaybackSetting.get())
            messagebox.showwarning("No TinyTV device!", "Please select a device.")

    def writeShowStaticSetting(self):
        if self.ttvPort is not None:
            if self.showStaticSetting.get() != 0:
                self.serialWrite("{SET: static=true}")
            else:
                self.serialWrite("{SET: static=false}")
            # for i in range(10):
            #     line = self.ttvPort.ser.readline().decode("utf-8")
            #     print(line)
        else:
            self.showStaticSetting.set(not self.showStaticSetting.get())
            messagebox.showwarning("No TinyTV device!", "Please select a device.")

    def writeShowChannelNumberSetting(self):
        if self.ttvPort is not None:
            if self.showChannelNumberSetting.get() != 0:
                self.serialWrite("{SET: showChannel=true}")
            else:
                self.serialWrite("{SET: showChannel=false}")
            # for i in range(10):
            #     line = self.ttvPort.ser.readline().decode("utf-8")
            #     print(line)
        else:
            self.showChannelNumberSetting.set(not self.showChannelNumberSetting.get())
            messagebox.showwarning("No TinyTV device!", "Please select a device.")

    def writeShowVolumeSetting(self):
        if self.ttvPort is not None:
            if self.showVolumeSetting.get() != 0:
                self.serialWrite("{SET: showVolume=true}")
            else:
                self.serialWrite("{SET: showVolume=false}")
            # for i in range(10):
            #     line = self.ttvPort.ser.readline().decode("utf-8")
            #     print(line)
        else:
            self.showVolumeSetting.set(not self.showVolumeSetting.get())
            messagebox.showwarning("No TinyTV device!", "Please select a device.")

    def writeRandomStartTimeSetting(self):
        if self.ttvPort is not None:
            if self.randomStartTimeSetting.get() != 0:
                self.serialWrite("{SET: randStartTime=true}")
            else:
                self.serialWrite("{SET: randStartTime=false}")
            # for i in range(10):
            #     line = self.ttvPort.ser.readline().decode("utf-8")
            #     print(line)
        else:
            self.randomStartTimeSetting.set(not self.randomStartTimeSetting.get())
            messagebox.showwarning("No TinyTV device!", "Please select a device.")

    def writeRandomStartChannelSetting(self):
        if self.ttvPort is not None:
            if self.randomStartChannelSetting.get() != 0:
                self.serialWrite("{SET: randStartChan=true}")
            else:
                self.serialWrite("{SET: randStartChan=false}")
            #line = self.ttvPort.ser.readline().decode("utf-8")
            #print(line)
        else:
            self.randomStartChannelSetting.set(not self.randomStartChannelSetting.get())
            messagebox.showwarning("No TinyTV device!", "Please select a device.")

    def selectTTV(self):
        ports = [p for p in serial.tools.list_ports.comports() if p.hwid != "n/a"]

        if not ports:
            messagebox.showerror("No Devices", "No serial devices found.")
            return

        root = Tk()
        root.title("Select Serial Device")

        Label(root, text="Available Serial Devices:").pack(padx=10, pady=5)

        listbox = Listbox(root, width=60, height=10)
        listbox.pack(padx=10, pady=5)

        for p in ports:
            listbox.insert(END, f"{p.device}  |  {p.hwid}")

        selected_device = {"hwid": None}

        def on_ok():
            try:
                idx = listbox.curselection()[0]
            except IndexError:
                messagebox.showwarning("No Selection", "Please select a device.")
                return
            selected_device["hwid"] = ports[idx].hwid
            self.ttvPort = SerIO()  # your custom serial abstraction
            self.ttvPort.connect(
                self.ttvPort.get_port(hwid=selected_device["hwid"][4:21]),
                timeout=0.5
            )
            print("Set device to "+str(selected_device["hwid"][4:21]))

            self.serialWrite("{GET: loopVideo}")
            for i in range(10):
                line = self.ttvPort.ser.readline().decode("utf-8")
                if("\"loopVideo\"" in line):
                    p = line.index(":")
                    print(line[p+1:-3])
                    self.loopVideoSetting.set(1 if line[p+1:-3] == "true" else 0)
                    break

            self.serialWrite("{GET: randStartTime}")
            for i in range(10):
                line = self.ttvPort.ser.readline().decode("utf-8")
                if("\"randStartTime\"" in line):
                    p = line.index(":")
                    print(line[p+1:-3])
                    self.randomStartTimeSetting.set(1 if line[p+1:-3] == "true" else 0)
                    break

            self.serialWrite("{GET: randStartChan}")
            for i in range(10):
                line = self.ttvPort.ser.readline().decode("utf-8")
                if("\"randStartChan\"" in line):
                    p = line.index(":")
                    print(line[p+1:-3])
                    self.randomStartChannelSetting.set(1 if line[p+1:-3] == "true" else 0)
                    break

            self.serialWrite("{GET: liveVideo}")
            for i in range(10):
                line = self.ttvPort.ser.readline().decode("utf-8")
                if("\"liveVideo\"" in line):
                    p = line.index(":")
                    print(line[p+1:-3])
                    self.liveVideoSetting.set(1 if line[p+1:-3] == "true" else 0)
                    break

            self.serialWrite("{GET: alphabetize}")
            for i in range(10):
                line = self.ttvPort.ser.readline().decode("utf-8")
                if("\"alphabetize\"" in line):
                    p = line.index(":")
                    print(line[p+1:-3])
                    self.alphabetizePlaybackSetting.set(1 if line[p+1:-3] == "true" else 0)
                    break

            self.serialWrite("{GET: showVolume}")
            for i in range(10):
                line = self.ttvPort.ser.readline().decode("utf-8")
                if("\"showVolume\"" in line):
                    p = line.index(":")
                    print(line[p+1:-3])
                    self.showVolumeSetting.set(1 if line[p+1:-3] == "true" else 0)
                    break

            self.serialWrite("{GET: showChannel}")
            for i in range(10):
                line = self.ttvPort.ser.readline().decode("utf-8")
                if("\"showChannel\"" in line):
                    p = line.index(":")
                    print(line[p+1:-3])
                    self.showChannelNumberSetting.set(1 if line[p+1:-3] == "true" else 0)
                    break

            self.serialWrite("{GET: volume}")
            for i in range(10):
                line = self.ttvPort.ser.readline().decode("utf-8")
                if("\"volume\"" in line):
                    print(line)
                    p = line.index(":")
                    self.volumeSliderVar.set(float(line[p+1:-3]) * 100 / 6)
                    break

            self.setTVSettingsEnabled('enabled')

            self.selectTTVButton.configure(text="Connected to TinyTV")
            self.selectTTVButton.configure(state='disabled')

            root.destroy()

        ok_button = Button(root, text="OK", command=on_ok)
        ok_button.pack(pady=5)

        root.mainloop()
        # --------------------------------

        dev = selected_device["hwid"]
        if dev is None:
            print("User closed window...")
            return  # user closed window

        print(dev)
        print(dev[4:21])

    def showNoVideoWarning(self):
        warn = Toplevel(self.parent)
        warn.title('TinyTV Converter')
        warn.geometry("200x100")
        x = self.parent.winfo_x() + self.parent.winfo_width()//2 - 200 // 2
        y = self.parent.winfo_y() + self.parent.winfo_height()//2 - 100 // 2
        warn.geometry(f"+{x}+{y}")
        warn.resizable(False, False)
        warn.grab_set()
        Label(warn, text="No video selected!").pack(pady=15)

        Button(warn, text="Ok", command=warn.destroy).pack(side="left", padx=(15, 5), pady=(5, 15), anchor="sw")
        Button(warn, text="Open Video", command=lambda: [self.onOpen(), warn.destroy()]).pack(side="right", padx=(5, 15), pady=(5, 15), anchor="se")

    def onThemeChanged(self, theme):
        sv_ttk.set_theme(theme.lower())
        canvasBG = 'white'
        if sys.platform=='darwin' :
            canvasBG = '#737373'
        previewX=0
        previewY=0
        if os.name=='darwin':
            previewX=3
            previewY=2

        self.image = PhotoImage(file=(resource_path('splash_light.png') if theme.lower() == 'light' else resource_path('splash_dark.png')))
        self.PreviewThumbnail.create_image(previewX,previewY,image=self.image,anchor=NW)
        self.PreviewThumbnail.grid(row=1, column=0)

        self.VideoOutputSettings.calculateVideoData()
        self.reloadVideoSettings()
        self.displayVidData()

        self.parent.update_idletasks()

    def darkDetectPollLoop(self):
        if(self.currentTheme != darkdetect.theme()):
            self.onThemeChanged(darkdetect.theme())
            self.currentTheme = darkdetect.theme()
        self.after(500, self.darkDetectPollLoop)

    def serialDisconnectPollLoop(self):
        if(self.ttvPort is not None):
            try:
                test = self.ttvPort.ser.readline()
            except SerialException:
                self.ttvPort = None
                self.setTVSettingsEnabled('disabled')
                self.selectTTVButton.configure(text="Connect to TinyTV")
                self.selectTTVButton.configure(state='enabled')
        self.after(500, self.serialDisconnectPollLoop)

    def loadVideoThumbnailThreadDND(self):
        self.setVideoInfo(self.dndevent.data[1:-1] if self.dndevent.data[0] == '{' else self.dndevent.data)
        self.VideoOutputSettings.calculateVideoData()

        self.reloadVideoSettings()

        self.displayVidData()
        self.loadVideoLabel.grid_forget()

    def loadVideoThumbnailThreadOpen(self):
        self.setVideoInfo(self.loaderFilename)
        self.VideoOutputSettings.calculateVideoData()

        self.reloadVideoSettings()

        self.displayVidData()
        self.loadVideoLabel.grid_forget()

    def OnOutputFormatChange(self, event):
        self.checkboxFrameAudio.grid_forget()
        self.videoInfoFrame.grid_forget()
        self.formatWarningLabel.grid_forget()
        self.formatWarningLabel2.grid_forget()
        if(self.FormatCombo.get() == ".MP4"):

            def openPage():
                webbrowser.open_new("https://tinytv.us/Update")

            self.formatWarningLabel = Label(self.notebookFrame1, text="Requires new firmware!", foreground="red")
            self.formatWarningLabel.grid(column=1,row=3,columnspan=1,sticky="sw", padx=10, pady=(56, 0))
            self.formatWarningLabel2 = Label(self.notebookFrame1, text="tinytv.us/Update", foreground="blue", cursor="hand2")
            self.formatWarningLabel2.bind("<Button-1>", lambda e: openPage())
            self.formatWarningLabel2.grid(column=1,row=4,columnspan=1,sticky="sw", padx=10, pady=(0, 5))

            self.checkboxFrameAudio.grid(column=1,row=5,columnspan=1,sticky="new", padx=5, pady=0)
            self.videoInfoFrame.grid(column=1,row=6,columnspan=1,sticky="new", padx=5, pady=0)
        else:
            self.checkboxFrameAudio.grid(column=1,row=4,columnspan=1,sticky="new", padx=5, pady=0)
            self.videoInfoFrame.grid(column=1,row=5,columnspan=1,sticky="new", padx=5, pady=0)
        if(self.TVCombo.get() == "TinyTV DIY Kit" and self.FormatCombo.get() == ".MP4"):
            messagebox.showwarning("Unsupported format", ".MP4 not supported for TinyTV DIY Kit, setting to .AVI")
            self.FormatCombo.set(".AVI") # MP4 not supported for kit
            self.OnOutputFormatChange(None)
        self.VideoOutputSettings.outputFormat.set(self.formatTypes[self.FormatCombo.get()])
        self.VideoOutputSettings.TVTypeOption.set(self.TVTypes[self.TVCombo.get()])

        self.VideoOutputSettings.calculateVideoData()
        self.reloadVideoSettings()
        self.displayVidData()
        self.FormatCombo.selection_clear()

    def setTVSettingsEnabled(self, en):
        self.volumeSlider.configure(state=en)
        self.loopVideoSwitch.configure(state=en)
        self.liveVideoSwitch.configure(state=en)
        self.alphabetizeSwitch.configure(state=en)
        self.showStaticSwitch.configure(state=en)
        self.showChannelNumberSwitch.configure(state=en)
        self.showVolumeSwitch.configure(state=en)
        self.randomStartTimeSwitch.configure(state=en)
        self.randomStartChannelSwitch.configure(state=en)

    def initUI(self):

        sv_ttk.set_theme(darkdetect.theme())

        self.parent.title("TinyTV Converter")
        if os.name=='nt':
            self.parent.title("TinyTV Converter - 1.1.0")
        self.pack(fill=BOTH, expand=1)

        self.notebook = Notebook(self)
        self.notebookFrame1 = Frame(self.notebook, width=400, height=400)
        self.notebookFrame2 = Frame(self.notebook, width=400, height=400)

        # menubar = Menu(self.parent)
        # self.parent.config(menu=menubar)

        # FileOptionsMenu = Menu(menubar, tearoff=0)

        # menubar.add_cascade(label="File", menu=FileOptionsMenu)
        # FileOptionsMenu.add_command(label="Open...", command=self.onOpen, accelerator="Ctrl+O")
        # FileOptionsMenu.add_command(label="Open Directory...", command=self.onOpenDirectory, accelerator="Ctrl+O")
        # FileOptionsMenu.add_command(label="Convert", command=self.onConvert)
        # FileOptionsMenu.add_separator()
        # FileOptionsMenu.add_command(label="Exit", command=self.onQuit, accelerator="Ctrl+Q")


        # TVOptionsMenu = Menu(menubar, tearoff=0)
        # TVOptionsMenu.add_radiobutton(label="TinyTV 2", command=self.displayVidData, var=self.VideoOutputSettings.TVTypeOption, value=3)
        # TVOptionsMenu.add_radiobutton(label="TinyTV Mini",  command=self.displayVidData, var=self.VideoOutputSettings.TVTypeOption, value=2)
        # TVOptionsMenu.add_radiobutton(label="TinyTV DIY Kit",  command=self.displayVidData, var=self.VideoOutputSettings.TVTypeOption, value=1)
        #
        # menubar.add_cascade(label="Video Options", menu=TVOptionsMenu)

        def updateAndDisplay():
            self.initVideoData()
            self.displayVidData()

        # OutputFormatMenu = Menu(menubar, tearoff=0)
        # menubar.add_cascade(label="Output Format", menu=OutputFormatMenu)
        #
        # OutputFormatMenu.add_radiobutton(label=".AVI (Default, recommended)", command=updateAndDisplay, var=self.VideoOutputSettings.outputFormat, value=1)
        # OutputFormatMenu.add_radiobutton(label=".TSV (For original TinyTV Kit firmware, enormous file size!)",  command=updateAndDisplay, var=self.VideoOutputSettings.outputFormat, value=2)
        # OutputFormatMenu.add_radiobutton(label=".MP4 (For original TinyTV 2 and Mini firmware)",  command=updateAndDisplay, var=self.VideoOutputSettings.outputFormat, value=3)
        # OutputFormatMenu.add_separator()
        # OutputFormatMenu.add_command(label="Import Format Settings...", command = self.onOpenFormatSettings)
        # OutputFormatMenu.add_command(label="Export Format Settings...", command = self.onExportFormatSettings)

        # TVSettingsMenu = Menu(menubar, tearoff=0)
        # menubar.add_cascade(label="TinyTV Settings", menu=TVSettingsMenu)
        #
        # TVSettingsMenu.add_checkbutton(label="Loop Video", command=self.writeLoopVideoSetting, var=self.loopVideoSetting)
        # TVSettingsMenu.add_checkbutton(label="Random Start Time", command=self.writeRandomStartTimeSetting, var=self.randomStartTimeSetting)
        # TVSettingsMenu.add_checkbutton(label="Random Start Channel", command=self.writeRandomStartChannelSetting, var=self.randomStartChannelSetting)
        # TVSettingsMenu.add_separator()
        # TVSettingsMenu.add_command(label="Select TinyTV...", command=self.selectTTV)
        # TVSettingsMenu.add_command(label="Import Settings...", command=self.onOpenFormatSettings)
        # TVSettingsMenu.add_command(label="Export Settings...", command=self.onExportFormatSettings)

        self.parent.bind("<Button-1>", self.click)

        self.VideoOutputSettings.TVTypeOption.set(3)
        self.VideoOutputSettings.videoWindowOption.set(3)
        self.VideoOutputSettings.audioEnable.set(1)
        self.VideoOutputSettings.videoBitDepth.set(16)
        self.VideoOutputSettings.outputFormat.set(1)
        self.VideoOutputSettings.normalizeAudio.set(1)

        self.bind_all("<Control-o>", self.onOpen)
        self.bind_all("<Control-q>", self.onQuit)

        self.parent.protocol("WM_DELETE_WINDOW", self.onWindowClose)

        # Grid.columnconfigure(self.notebookFrame1, 0, weight=0)
        # Grid.columnconfigure(self.notebookFrame1, 1, weight=0, minsize=0)
        # Grid.columnconfigure(self.notebookFrame1, 2, weight=0, minsize=0)

        Grid.columnconfigure(self.notebookFrame1, 1, weight=1)
        Grid.columnconfigure(self.notebookFrame1, 2, weight=1)
        Grid.columnconfigure(self.notebookFrame1, 3, weight=0,minsize=0)

        Grid.rowconfigure(self.notebookFrame1, 10, weight=1)

        canvasBG = 'white'
        if sys.platform=='darwin' :
            canvasBG = '#737373'

        self.PreviewFrame = Frame(self.notebookFrame1, width = self.VideoOutputSettings.outputWidth*2, height = self.VideoOutputSettings.outputHeight*2)
        self.PreviewFrame.grid_propagate(0)

        def OnVideoFileDrop(event):
            print("File dropped!")
            print(event.data)
            root, extension = os.path.splitext(event.data[1:-1] if event.data[0] == '{' else event.data)
            print(root)
            print(extension)
            valid_exts = ('.mp4', '.mov', '.mpg', '.mpeg', '.avi', '.gif')
            if extension in valid_exts:
                print("Loading " + str(event.data))

                self.batchDirectory.delete('1.0', tkinter.END)

                self.thumbnailOpenButton.grid_forget()

                self.loadVideoLabel = Label(self.PreviewFrame, text="Loading video...")
                self.convertFileButton["text"] = "Convert Video"

                self.progressBarVar.set(0)
                self.loadVideoLabel.grid(row=1, column=0)

                self.dndevent = event
                loader = threading.Thread(target=self.loadVideoThumbnailThreadDND, args=())
                loader.start()

            elif extension == '':
                if messagebox.askyesno(
                    title="Open Directory",
                    message="Open \'"+str(event.data)+ "\'?"
                ):
                    self.batchDirectory.delete('1.0', tkinter.END)
                    self.batchDirectory.insert(tkinter.END, event.data[1:-1] if event.data[0] == '{' else event.data)
                    print("Set batch directory to "+str(self.batchDirectory.get('1.0', tkinter.END).strip()))
                    self.setBatchDirectoryConvert()

        self.PreviewFrame.drop_target_register(DND_FILES)
        self.PreviewFrame.dnd_bind('<<Drop>>', OnVideoFileDrop)

        self.PreviewThumbnail = Canvas(self.PreviewFrame, width = self.VideoOutputSettings.outputWidth*2, height = self.VideoOutputSettings.outputHeight*2, bg = canvasBG)
        self.PreviewThumbnail.grid(row=1, column=0)

        self.thumbnailOpenButton = Button(self.PreviewFrame, text='No Video Selected!', command=self.onOpen)
        self.thumbnailOpenButton.grid(row=1, column=0)

        previewX=0
        previewY=0
        if os.name=='darwin':
            previewX=3
            previewY=2

        self.image = PhotoImage(file=(resource_path('splash_light.png') if darkdetect.theme() == 'Light' else resource_path('splash_dark.png')))
        self.PreviewThumbnail.create_image(previewX,previewY,image=self.image,anchor=NW)

        self.filesToConvertVar = StringVar()
        self.ListScrollbar = Scrollbar(self.PreviewFrame, orient='vertical')
        self.PreviewListbox = Listbox(self.PreviewFrame, yscrollcommand = self.ListScrollbar.set, listvariable=self.filesToConvertVar)

        self.ListScrollbar.config(command=self.PreviewListbox.yview)

        self.openFileFrame = Frame(self.notebookFrame1)

        self.openButtonsFrame = LabelFrame(self.openFileFrame, text = 'Open...')

        self.openFileButton = Button(self.openButtonsFrame, text='Open Video', command=self.onOpen)
        self.openFileButton.grid(row=0, column=0, sticky='w', padx=(4,0), pady=(5,4))

        self.openDirectoryButton = Button(self.openButtonsFrame, text='Open Directory', command=self.onOpenDirectory)
        self.openDirectoryButton.grid(row=0, column=1,sticky='w', padx=(4,4), pady=(5,3))

        self.radioFrameTVType = LabelFrame(self.openFileFrame, text = 'TV Type')

        self.VideoOutputSettings.TVTypeOption = IntVar(value=3)

        self.TVTypes = {
            "TinyTV 2": 3,
            "TinyTV Mini": 2,
            "TinyTV DIY Kit": 1
        }

        self.TVCombo = Combobox(
            self.radioFrameTVType,
            state="readonly",
            values=list(self.TVTypes.keys()),
            width = 12
        )

        self.TVCombo.set("TinyTV 2")
        self.TVCombo.pack(fill='x', pady=(5,4), padx=(4,4))

        def OnTVTypeChange(event):

            if(self.FormatCombo.get() == ".MP4" and self.TVCombo.get() == "TinyTV DIY Kit"):
                messagebox.showwarning("Unsupported format", ".MP4 not supported for TinyTV DIY Kit, setting to .AVI")
                self.FormatCombo.set(".AVI") # MP4 not supported for kit
                self.VideoOutputSettings.outputFormat.set(self.formatTypes[".AVI"])
                self.OnOutputFormatChange(None)
            self.VideoOutputSettings.TVTypeOption.set(self.TVTypes[self.TVCombo.get()])
            self.VideoOutputSettings.calculateVideoData()
            self.reloadVideoSettings()
            self.displayVidData()
            self.TVCombo.selection_clear()

        self.TVCombo.bind("<<ComboboxSelected>>", OnTVTypeChange)

        self.radioFrameVid = LabelFrame(self.openFileFrame, text = 'Scaling Options')

        self.ScalingTypes = {
            "Contain/Letterbox": 3,
            "Cover/Zoom": 2,
            "Fill/Stretch": 1
        }

        self.ScalingCombo = Combobox(
            self.radioFrameVid,
            state="readonly",
            values=list(self.ScalingTypes.keys()),
            width = 16
        )

        self.ScalingCombo.set("Contain/Letterbox")
        self.ScalingCombo.pack(fill='x', pady=(5,4), padx=(4,4))

        def OnScalingTypeChange(event):
            self.VideoOutputSettings.videoWindowOption.set(self.ScalingTypes[self.ScalingCombo.get()])
            self.VideoOutputSettings.calculateVideoData()
            self.reloadVideoSettings()
            self.displayVidData()
            self.ScalingCombo.selection_clear()

        self.ScalingCombo.bind("<<ComboboxSelected>>", OnScalingTypeChange)

        self.convertFormatFrame = LabelFrame(self.notebookFrame1, text = 'Output Format')

        self.formatTypes = {
            ".AVI": 1,
            ".TSV": 2,
            ".MP4": 3
        }

        self.FormatCombo = Combobox(
            self.convertFormatFrame,
            state="readonly",
            values=list(self.formatTypes.keys()),
            width = 8
        )

        self.FormatCombo.set(".AVI")
        self.FormatCombo.pack(fill='x', pady=(5,4), padx=(4,4))

        self.FormatCombo.bind("<<ComboboxSelected>>", self.OnOutputFormatChange)

        self.checkboxFrameAudio = LabelFrame(self.notebookFrame1, text = 'Audio Options')
        self.audioCheckBox = Checkbutton(self.checkboxFrameAudio, text='Normalize', variable = self.VideoOutputSettings.normalizeAudio)
        self.audioCheckBox.pack(side='left', pady=(4,2), padx=(2,2))

        self.videoInfoFrame = LabelFrame(self.notebookFrame1, text = 'Video Info')

        self.TVConvertFrame = LabelFrame(self.notebookFrame1, text = 'Convert...')

        self.menuBarFrame = Frame(self.notebookFrame1)
        self.menuBarStyle = Style(self.notebookFrame1)

        self.menuBarStyle.configure("MenuBarButton.TButton", font=("Arial", 10), relief='flat', anchor="w", borderwidth=0, padding=0)

        self.FileMenuBarButton = Button(self.menuBarFrame, text='File', takefocus=0, width=5)
        def showFileOptionsMenu():
            FileOptionsMenu.tk_popup(self.FileMenuBarButton.winfo_rootx(), self.FileMenuBarButton.winfo_rooty()+24)
        self.FileMenuBarButton.configure(command = showFileOptionsMenu, style="MenuBarButton.TButton")
        self.FileMenuBarButton.grid(row=0, column=0, columnspan=1, padx=(0, 0), pady=(0, 2), sticky='w')

        self.VideoOptionsMenuBarButton = Button(self.menuBarFrame, text='TinyTV Options', takefocus=0, width=15)
        def showVideoOptionsMenu():
            TVOptionsMenu.tk_popup(self.VideoOptionsMenuBarButton.winfo_rootx(), self.VideoOptionsMenuBarButton.winfo_rooty()+24)
        self.VideoOptionsMenuBarButton.configure(command = showVideoOptionsMenu, style="MenuBarButton.TButton")
        self.VideoOptionsMenuBarButton.grid(row=0, column=1, columnspan=1, padx=(0, 0), pady=(0, 2), sticky='w')

        self.OutputFormatMenuBarButton = Button(self.menuBarFrame, text='Output Format', takefocus=0, width=14)
        def showOutputFormatMenu():
            OutputFormatMenu.tk_popup(self.OutputFormatMenuBarButton.winfo_rootx(), self.OutputFormatMenuBarButton.winfo_rooty()+24)
        self.OutputFormatMenuBarButton.configure(command = showOutputFormatMenu, style="MenuBarButton.TButton")
        self.OutputFormatMenuBarButton.grid(row=0, column=2, columnspan=1, padx=(0, 0), pady=(0, 2), sticky='w')

        #self.TVSettingsMenuBarButton = Button(self.menuBarFrame, text='TinyTV Settings', takefocus=0, width=15)
        self.TVSettingsMenuBarButton = Button(self.TVConvertFrame, text='TinyTV Settings', takefocus=0, width=12)

        def showTVSettingsMenu():
            TVSettingsMenu.tk_popup(self.TVSettingsButton.winfo_rootx(), self.TVSettingsButton.winfo_rooty()+24)
        self.TVSettingsMenuBarButton.configure(command = showTVSettingsMenu, style="MenuBarButton.TButton")
        #self.TVSettingsMenuBarButton.grid(row=6, column=0, columnspan=1, padx=(5, 2), pady=(0, 2), sticky='nsew')

        # firstRowButton = Button(self, text='Test', takefocus=0, width=15)
        # firstRowButton.grid(column=0,row=1)

        self.openButtonsFrame.grid(column=0,row=2,columnspan=2, sticky="we", padx=(0, 0), pady=(0,0))
        self.radioFrameTVType.grid(column=2,row=2,columnspan=1,sticky="s", padx=(4, 2), pady=(0, 0))
        self.radioFrameVid.grid(column=3,row=2,columnspan=1,sticky="ne", padx=(2, 2), pady=0)

        self.convertFileButton = Button(self.TVConvertFrame, text='Convert Video', width=14, style = "Accent.TButton", command=self.onConvert)
        self.convertFileButton.pack(side='left', pady=(5,4), padx=(4,4))
        self.cancelButton = Button(self.TVConvertFrame, text='Cancel', width=6, command=self.onCancelConvert)
        self.cancelButton.pack(side='left', pady=(5,4), padx=(0,4))

        self.openHelpButton = Button(self.TVConvertFrame, text='Help', width=4, style = "Accent.TButton", command=self.onOpenHelpFile)
        self.openHelpButton.pack(side='right', pady=(5,4), padx=(0,4))

        #self.TVSettingsMenuBarButton.pack(side='right', pady=(5,4), padx=(0,4))

        # self.TVSettingsButton = Button(self.TVConvertFrame, text='TinyTV Settings', width=12, command=showTVSettingsMenu)
        # self.TVSettingsButton.pack(side='right', pady=(5,4), padx=(0,4))
        self.importSettingsButton = Button(self.TVConvertFrame, text='Export Settings', width=12, command=self.onExportFormatSettings)
        self.importSettingsButton.pack(side='right', pady=(5,4), padx=(0,4))
        self.importSettingsButton = Button(self.TVConvertFrame, text='Import Settings', width=12, command=self.onOpenFormatSettings)
        self.importSettingsButton.pack(side='right', pady=(5,4), padx=(0,4))

        self.progressbar = Progressbar(self.notebookFrame1, variable=self.progressBarVar, maximum=100)
        self.durationStringLabel = Label(self.videoInfoFrame, text="Video Length:")
        self.durationStringField = Label(self.videoInfoFrame)
        self.outputSizeField = Label(self.videoInfoFrame)
        self.outputSizeLabel = Label(self.videoInfoFrame, text="Output Size:")
        self.audioBoostStringLabel = Label(self.checkboxFrameAudio, text="-- dB")
        self.formatWarningLabel = Label(self.notebookFrame1, text="Requires new firmware!", foreground="red")
        self.formatWarningLabel2 = Label(self.notebookFrame1, text="tinytv.us/Update", foreground="red")

        # self.durationStringLabel.grid(column=1,row=0, sticky=W, padx=5, pady=(5, 0))
        # self.durationStringField.grid(column=1,row=1, sticky=W, padx=(5, 5), pady=5)
        #
        # self.outputSizeLabel = Label(self.videoInfoFrame, text="Output Size:")
        # self.outputSizeLabel.grid(column=1,row=2, sticky=W, padx=5, pady=(5, 0))
        #
        # self.outputSizeField = Label(self.videoInfoFrame)
        # self.outputSizeField.grid(column=1,row=3, sticky=W, padx=(5, 5), pady=5)
        #
        # self.audioBoostStringLabel = Label(self.checkboxFrameAudio, text="-- dB")
        # self.audioBoostStringLabel.pack(side='right',pady=(4,2), padx=(0,8))
        #
        # self.convertFormatFrame.grid(column=1,row=3,columnspan=1,sticky="new", padx=5, pady=0)
        #
        # self.formatWarningLabel = Label(self, text="Requires new firmware!", foreground="red")
        # self.formatWarningLabel2 = Label(self, text="tinytv.us/Update", foreground="red")
        #
        # self.checkboxFrameAudio.grid(column=1,row=4,columnspan=1,sticky="new", padx=5, pady=0)
        # self.videoInfoFrame.grid(column=1,row=5,columnspan=1,sticky="new", padx=5, pady=0)
        #
        # self.TVConvertFrame.grid(column=0,row=9,columnspan=2,sticky="new", padx=5, pady=(0, 3))
        #
        # #self.progressBarStyle = Style(self.progressbar)
        # #self.progressBarStyle.configure("Custom.Horizontal.TProgressbar", thickness=8)
        # self.progressbar.grid(column=0,row=10,columnspan=2, rowspan=1, sticky='nsew', padx=(5, 5), pady=(0,3))

        self.openFileFrame.grid(column=0,row=2,columnspan=2, sticky="we", padx=(5, 4), pady=(0,0))
        #self.PreviewFrame = Frame(self, width = self.VideoOutputSettings.outputWidth*2, height = self.VideoOutputSettings.outputHeight*2)
        self.PreviewFrame.grid(column=0, row=3, rowspan=4, padx=(4,0), pady=5,  sticky='nsew')
        self.durationStringLabel.grid(column=1,row=0, sticky=W, padx=5, pady=(5, 0))
        self.durationStringField.grid(column=1,row=1, sticky=W, padx=(5, 5), pady=5)

        self.outputSizeLabel.grid(column=1,row=2, sticky=W, padx=5, pady=(5, 0))


        self.outputSizeField.grid(column=1,row=3, sticky=W, padx=(5, 5), pady=5)


        self.audioBoostStringLabel.pack(side='right',pady=(4,2), padx=(0,8))

        self.convertFormatFrame.grid(column=1,row=3,columnspan=1,sticky="new", padx=5, pady=0)

        self.checkboxFrameAudio.grid(column=1,row=4,columnspan=1,sticky="new", padx=5, pady=0)
        self.videoInfoFrame.grid(column=1,row=5,columnspan=1,sticky="new", padx=5, pady=0)

        self.TVConvertFrame.grid(column=0,row=9,columnspan=2,sticky="new", padx=5, pady=(0, 3))

        #self.progressBarStyle = Style(self.progressbar)
        #self.progressBarStyle.configure("Custom.Horizontal.TProgressbar", thickness=8)
        self.progressbar.grid(column=0,row=10,columnspan=2, rowspan=1, sticky='nsew', padx=(5, 5), pady=(0,3))

        self.onThemeChanged(darkdetect.theme())

        self.displayVidData()

        self.volumeSliderVar = DoubleVar()

        #sliderSwitch = Checkbutton(self.notebookFrame2, text='Switch', style='Switch.TCheckbutton')
        settingOptionsFrame = Frame(self.notebookFrame2)
        volumeLabelFrame = LabelFrame(settingOptionsFrame, text = 'Volume')
        self.volumeSlider = Scale(volumeLabelFrame, to=100, orient="horizontal", takefocus=False, variable=self.volumeSliderVar)
        self.loopVideoSwitch = Checkbutton(settingOptionsFrame, text='Loop Video', style='Switch.TCheckbutton', command = self.writeLoopVideoSetting, var=self.loopVideoSetting)
        self.liveVideoSwitch = Checkbutton(settingOptionsFrame, text='Live Video', style='Switch.TCheckbutton', command = self.writeLiveVideoSetting, var=self.liveVideoSetting)
        self.alphabetizeSwitch = Checkbutton(settingOptionsFrame, text='Alphabetize Playback', style='Switch.TCheckbutton', command = self.writeAlphabetizePlaybackSetting, var=self.alphabetizePlaybackSetting)
        self.showStaticSwitch = Checkbutton(settingOptionsFrame, text='Static Effect', style='Switch.TCheckbutton', command = self.writeShowStaticSetting, var=self.showStaticSetting)
        self.showChannelNumberSwitch = Checkbutton(settingOptionsFrame, text='Show Channel Number', style='Switch.TCheckbutton', command = self.writeShowChannelNumberSetting, var=self.showChannelNumberSetting)
        self.showVolumeSwitch = Checkbutton(settingOptionsFrame, text='Show Volume', style='Switch.TCheckbutton', command = self.writeShowVolumeSetting, var=self.showVolumeSetting)
        self.randomStartTimeSwitch = Checkbutton(settingOptionsFrame, text='Random Start Time', style='Switch.TCheckbutton', command = self.writeRandomStartTimeSetting, var=self.randomStartTimeSetting)
        self.randomStartChannelSwitch = Checkbutton(settingOptionsFrame, text='Random Start Channel', style='Switch.TCheckbutton', command = self.writeRandomStartChannelSetting, var=self.randomStartChannelSetting)
        self.selectTTVButton = Button(settingOptionsFrame, text="Connect to TinyTV", command=self.selectTTV, width=20)

        self.volumeSlider.bind("<ButtonRelease-1>", self.writeVolumeSetting)
        # importSettingsButton = Button(settingOptionsFrame, text="Import Settings...", command=self.onOpenFormatSettings, width=20)
        # exportSettingsButton = Button(settingOptionsFrame, text="Export Settings...", command=self.onExportFormatSettings, width=20)
                # TVSettingsMenu.add_checkbutton(label="Loop Video", command=self.writeLoopVideoSetting, var=self.loopVideoSetting)
                # TVSettingsMenu.add_checkbutton(label="Random Start Time", command=self.writeRandomStartTimeSetting, var=self.randomStartTimeSetting)
                # TVSettingsMenu.add_checkbutton(label="Random Start Channel", command=self.writeRandomStartChannelSetting, var=self.randomStartChannelSetting)
                # TVSettingsMenu.add_separator()
                # TVSettingsMenu.add_command(label="Select TinyTV...", command=self.selectTTV)
                # TVSettingsMenu.add_command(label="Import Settings...", command=self.onOpenFormatSettings)
                # TVSettingsMenu.add_command(label="Export Settings...", command=self.onExportFormatSettings)
        self.setTVSettingsEnabled('disabled')
        # loopVideoSwitch.grid(row=1, column=2, sticky="we")
        # randomStartTimeSwitch.grid(row=2, column=2, sticky="we")
        # randomStartChannelSwitch.grid(row=3, column=2, sticky="we")
        # selectTTVButton.grid(row=4, column=2, sticky="we")
        # importSettingsButton.grid(row=5, column=2, sticky="we")
        # exportSettingsButton.grid(row=6, column=2, sticky="we")

        settingOptionsFrame.pack(expand=True)
        self.loopVideoSwitch.grid(row=1, column=2, sticky="we")
        self.liveVideoSwitch.grid(row=2, column=2, sticky="we")
        self.alphabetizeSwitch.grid(row=3, column=2, sticky="we")
        self.showStaticSwitch.grid(row=4, column=2, sticky="we")
        self.showChannelNumberSwitch.grid(row=5, column=2, sticky="we")
        self.showVolumeSwitch.grid(row=6, column=2, sticky="we")
        self.randomStartTimeSwitch.grid(row=7, column=2, sticky="we")
        self.randomStartChannelSwitch.grid(row=8, column=2, sticky="we")
        volumeLabelFrame.grid(row=9, column=2, sticky="we")
        self.volumeSlider.pack(expand=True, fill='both', padx=(5, 5), pady=(0,3))
        self.selectTTVButton.grid(row=1, column=2, sticky="we")
        # importSettingsButton.grid(row=5, column=2, sticky="we")
        # exportSettingsButton.grid(row=6, column=2, sticky="we")

        self.notebook.grid(row=1, column=1)

        self.notebookFrame1.pack(fill='both', expand=True)
        self.notebookFrame2.pack(fill='both', expand=True)

        self.notebook.add(self.notebookFrame1, text="Video Converter")
        self.notebook.add(self.notebookFrame2, text="TV Settings")

        openFileButtonTip = CreateToolTip(self.openFileButton, 'Open a video file or GIF')
        TVComboTip = CreateToolTip(self.TVCombo, 'Select TinyTV type')
        scalingComboTip = CreateToolTip(self.ScalingCombo, 'Select scale and crop options')
        formatComboTip = CreateToolTip(self.FormatCombo, 'Select output format')
        normalizeAudioTip = CreateToolTip(self.audioCheckBox, 'Normalize per-video audio levels')
        #importSettingsTip = CreateToolTip(self.importSettingsButton, 'Load previously saved configuration')
        #exportSettingsTip = CreateToolTip(self.TVSettingsButton, 'Export current configuration')
        helpButtonTip = CreateToolTip(self.openHelpButton, 'View manual')
        cancelButtonTip = CreateToolTip(self.cancelButton, 'Stop current video conversion')
        # radButtonTinyTV2Tip = CreateToolTip(self.radButtonTV2, 'Convert video for TinyTV 2')
        # radButtonTinyTVMiniTip = CreateToolTip(self.radButtonTVMini, 'Convert video for TinyTV Mini')
        # radButtonTinyTVKitTip = CreateToolTip(self.radButtonTVKit, 'Convert video for TinyTV DIY Kit')
        # radButton3Tip = CreateToolTip(self.radButton3, 'Keep aspect ratio and add padding to fit TinyTV')
        # radButton2Tip = CreateToolTip(self.radButton2, 'Keep aspect ratio and crop to fit TinyTV')
        # radButton1Tip = CreateToolTip(self.radButton1, 'Stretch video to fit TinyTV')
        convertFileButtonTip = CreateToolTip(self.convertFileButton, 'Start video conversion')
        selectTTVButtonTip = CreateToolTip(self.selectTTVButton, 'Connect to TinyTV device port')
        openDirectoryButtonTip = CreateToolTip(self.openDirectoryButton, 'Open directory for video conversion(s)')

        self.currentTheme = None
        self.darkDetectPollLoop()
        self.serialDisconnectPollLoop()

        # self.displayVidData()




    def onOpenHelpFile(self):
        file_path = resource_path("instruction_manual.pdf")
        if sys.platform == "win32":
            os.startfile(file_path)
        elif sys.platform == "darwin":  # macOS
            sp.run(["open", file_path])
        else:
            sp.run(["xdg-open", file_path])

    def getScaleCommand(self,width,height):
        scaleCommand='scale=%d:%d,hqdn3d' % (width, height)
        if (self.VideoOutputSettings.videoWindowOption.get() == 2):
            scaleCommand='scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d:exact=1,hqdn3d' % (width, height, width, height) #,setsar=1 ?
        if (self.VideoOutputSettings.videoWindowOption.get() == 3):
            scaleCommand='scale=%d:%d:force_original_aspect_ratio=decrease,format=yuv444p,pad=%d:%d:(ow-iw)/2:(oh-ih)/2,format=yuv420p,hqdn3d' % (width,height,width,height)
        #https://forum.videohelp.com/threads/401057-padding-top-and-bottom-odd-number-ffmpeg
        return scaleCommand

    def displayPreviewFrame(self):
        if(self.durationSeconds>0):
            previewTime=self.durationSeconds/2
            m, s = divmod(previewTime, 60)
            h, m = divmod(m, 60)

            previewTime = '%02d:%02d:%02d' % (h, m, s)

            scaleCommand=self.getScaleCommand(self.VideoOutputSettings.outputWidth*2,self.VideoOutputSettings.outputHeight*2)
            vidcommand = getPreviewFrameCommand(FFMPEG_BIN, previewTime, scaleCommand, self.inputFile)
            infoPipe = '';
            if os.name=='nt' :
                startupinfo = sp.STARTUPINFO()
                startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
                infoPipe=sp.Popen(vidcommand, stdin = sp.PIPE, stdout = sp.PIPE, stderr = sp.DEVNULL, bufsize=(self.VideoOutputSettings.outputWidth*2 * self.VideoOutputSettings.outputHeight*2)*3, startupinfo=startupinfo)
            else:
                infoPipe=sp.Popen(vidcommand, stdin = sp.PIPE, stdout = sp.PIPE, stderr = sp.DEVNULL, bufsize=(self.VideoOutputSettings.outputWidth*2 * self.VideoOutputSettings.outputHeight*2)*3)

            vidFrame = infoPipe.stdout.read((self.VideoOutputSettings.outputWidth*2 * self.VideoOutputSettings.outputHeight*2)*3)

            infoPipe.terminate()
            infoPipe.stdout.close()
            infoPipe.wait()

            xdataPrependStr = 'P6 %s %s 255 ' % (self.VideoOutputSettings.outputWidth*2, self.VideoOutputSettings.outputHeight*2)
            xdata = bytes(xdataPrependStr, encoding="raw_unicode_escape") + bytearray(vidFrame)

            self.image = PhotoImage(width=self.VideoOutputSettings.outputWidth*2, height=self.VideoOutputSettings.outputHeight*2, data=xdata , format='PPM')

            xOffset = self.PreviewThumbnail.winfo_width() - self.image.width()
            if(xOffset):
                xOffset=xOffset/2
            yOffset = self.PreviewThumbnail.winfo_height() - self.image.height()
            if(yOffset):
                yOffset=yOffset/2

            self.PreviewThumbnail.create_image(xOffset,yOffset,image=self.image,anchor=NW)

    def displayVidData(self):
        self.VideoOutputSettings.calculateVideoData()

        size=self.outputSize
        sizeUnit='B';
        if (size>1024.0):
            size/=1024.0
            sizeUnit='KB'
        if (size>1024.0):
            size/=1024.0
            sizeUnit='MB'
        if (size>1024.0):
            size/=1024.0
            sizeUnit='GB'
        self.durationStringField.config(text=self.durationString)

        if size > 0:
            self.outputSizeField.config(text= "~%.0f %s" % (size, sizeUnit))
        else:
            self.outputSizeField.config(text = "-")
        #self.conversionTimeField.config(text = "--:--:--")
        self.progressBarVar.set(0.0)
        self.displayPreviewFrame()

    def onOpenDirectory(self):
        self.batchDirectory.delete('1.0', tkinter.END)
        self.batchDirectory.insert(tkinter.END, tkinter.filedialog.askdirectory(title="Choose Input Directory"))
        print("Set batch directory to "+str(self.batchDirectory.get('1.0', tkinter.END).strip()))
        self.setBatchDirectoryConvert()
        pass

    def setVideoInfo(self, fileName, init=True):
        if fileName != '':
            print(fileName)
            self.showVideoThumbnail()
            self.inputFile = fileName
            self.outputFile = "%s.avi" % (os.path.splitext(self.inputFile)[0])
            infoPipe = '';
            if os.name=='nt' :
                startupinfo = sp.STARTUPINFO()
                startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
                infoPipe=sp.Popen([FFMPEG_BIN,"-i",self.inputFile], stdin = sp.PIPE, stdout = sp.DEVNULL, stderr = sp.PIPE, bufsize=1000000, startupinfo=startupinfo)
            else:
                infoPipe=sp.Popen([FFMPEG_BIN,"-i",self.inputFile], stdin = sp.PIPE, stdout = sp.DEVNULL, stderr = sp.PIPE, bufsize=1000000)
            #infoPipe.stdout.read()  #removed for videos with chapter markers embedded
            info = infoPipe.stderr.read().decode('utf8')
            infoPipe.terminate()
            #infoPipe.stdout.close()
            infoPipe.stderr.close()  #added for videos with chapter markers embedded
            infoPipe.wait()
            #print(info)
            if 'Invalid' in info:
                if(init):
                    self.initVideoData()
                    self.displayVidData()
                self.inputNameField.config(text='Unsupported file!')
                print('FFmpeg unrecognized file')
                return

            lines = info.splitlines()

            try:
                keyword = 'Duration: '
                line = [l for l in lines if keyword in l][0]
                match = re.findall("([0-9][0-9]:[0-9][0-9]:[0-9][0-9].[0-9][0-9])", line)[0]
                self.durationString = match[0:8]
                self.durationSeconds = float(match[0:2])*60.0*60.0 + float(match[3:5])*60.0 + float(match[6:11])
                print("Duration: "+str(self.durationSeconds))
                print(self.VideoOutputSettings.outputBytesPerSecond)
            except:
                if 'N/A' in info:
                    #gif or image- need to 'decode' video to determine duration.
                    vidcommand = [ FFMPEG_BIN,
                    '-i', self.inputFile,
                    '-f', 'null', '-']
                    infoPipe = '';
                    if os.name=='nt' :
                        startupinfo = sp.STARTUPINFO()
                        startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
                        infoPipe=sp.Popen(vidcommand, stdin = sp.PIPE, stdout = sp.PIPE, stderr = sp.PIPE, bufsize=(self.VideoOutputSettings.outputWidth*2 * self.VideoOutputSettings.outputHeight*2)*3, startupinfo=startupinfo)
                    else:
                        infoPipe=sp.Popen(vidcommand, stdin = sp.PIPE, stdout = sp.PIPE, stderr = sp.PIPE, bufsize=(self.VideoOutputSettings.outputWidth*2 * self.VideoOutputSettings.outputHeight*2)*3)

                    info = infoPipe.stdout.readline()
                    infoerr = infoPipe.stderr.read().decode('utf8')
                    infoPipe.terminate()
                    infoPipe.stdout.close()
                    infoPipe.wait()
                    lines = infoerr.splitlines()
                    print(infoerr)
                    try:
                        keyword = 'time='
                        line = [l for l in lines if keyword in l][0]
                        finalTimeString=  line.split('time=')[1].split(' ')[0]
                        finalTimeStringSplit=  finalTimeString.split(':')
                        if len(finalTimeStringSplit) == 1:
                            self.durationSeconds = float(finalTimeStringSplit[0])
                        if len(finalTimeStringSplit) == 2:
                            self.durationSeconds = float(finalTimeStringSplit[0])*60.0
                            self.durationSeconds += float(finalTimeStringSplit[1])
                        if len(finalTimeStringSplit) == 3:
                            self.durationSeconds = float(finalTimeStringSplit[0])*60.0*60.0
                            self.durationSeconds += float(finalTimeStringSplit[1])*60.0
                            self.durationSeconds += float(finalTimeStringSplit[2])
                        hoursToDisplay=int(self.durationSeconds)/3600
                        minutesToDisplay=int(self.durationSeconds)/60
                        secondsToDisplay= int(self.durationSeconds)%60
                        if(hoursToDisplay==0 and minutesToDisplay==0 and secondsToDisplay==0):
                            secondsToDisplay=1
                        self.durationString = "%02d:%02d:%02d" % (hoursToDisplay, minutesToDisplay,secondsToDisplay)
                    except:
                        print ("Error finding video duration")
                        self.inputNameField.config(text='Error decoding file')
                        self.durationSeconds = 1.0/29.99
                        self.durationString = "--:--:--"
                else:
                    if(init):
                        self.initVideoData()
                        self.displayVidData()
                    print ("Video info error")
                    self.inputNameField.config(text="Video info error")
                    return

            if(init):
                self.displayVidData()

    def reloadVideoSettings(self):
        self.inputVidFrameBytes = self.VideoOutputSettings.outputWidth*self.VideoOutputSettings.outputHeight*2
        if (self.VideoOutputSettings.videoBitDepth.get() == 8):
            self.VideoOutputSettings.outputVidFrameBytes=self.inputVidFrameBytes/2
        else:
            self.VideoOutputSettings.outputVidFrameBytes=self.inputVidFrameBytes

        self.audioFrameBytes=self.VideoOutputSettings.tsvAudioSampleCountPerFrame*2

        self.totalFrames=self.durationSeconds*self.VideoOutputSettings.outputFrameRate
        self.outputSize=self.durationSeconds*self.VideoOutputSettings.outputBytesPerSecond

    def onOpen(self):
        self.batchDirectory.delete('1.0', tkinter.END)

        ftypes = [('Video files', '*.mp4;*.mov;*.mpg;*.mpeg;*.avi;*.gif'), ('All files', '*')]
        #dlg = tkinter.filedialog.Open(self, filetypes = ftypes) # makes macOS angry
        dlg = tkinter.filedialog.Open(self)
        fileName = dlg.show()

        if fileName != '':
            self.thumbnailOpenButton.grid_forget()
            self.convertFileButton["text"] = "Convert Video"
            self.progressBarVar.set(0)

            self.loadVideoLabel = Label(self.PreviewFrame, text="Loading video...")
            self.loadVideoLabel.grid(row=1, column=0)
            #
            self.loaderFilename = fileName
            loader = threading.Thread(target=self.loadVideoThumbnailThreadOpen, args=())
            loader.start()

    def onOpenFormatSettings(self):
        dlg = tkinter.filedialog.Open(self, title="Open format settings")
        fileName = dlg.show()
        if fileName != '':
            self.VideoOutputSettings.loadJSONSettings(open(fileName, 'r', encoding='utf-8'))
            self.VideoOutputSettings.calculateVideoData()
            self.reloadVideoSettings()
            self.displayVidData()

    def onExportFormatSettings(self):
        dlg = tkinter.filedialog.asksaveasfilename(title="Save format settings", defaultextension=".json")
        if(dlg):
            outfile = open(dlg, 'w')
            outfile.write(self.VideoOutputSettings.dumpJSONSettingsStr())

    def onWindowClose(self):
        self.onQuit('')

    def onQuit(self, event=''):
        print("Running quit handler!")
        if(self.vidPipe is not None):
            self.vidPipe.terminate()
            self.vidPipe.stdout.close()
            self.vidPipe.wait()
        if(self.ttvPort is not None):
            print("TV disconnected!")
            self.ttvPort.disconnect()
        self.quit()
        #self.onQuit()
        exit()

    def onCancelConvert(self):
        if(self.vidPipe is not None):
            if messagebox.askyesno(
                title="Confirm Cancel",
                message="Cancel video convert?"
            ):
                self.vidPipe.terminate()
                self.vidPipe.stdout.close()
                self.vidPipe.wait()
                self.vidPipe = None
                self.progressBarVar.set(0.0)

    def openFolder(self, event=''):
        if os.name=='nt' :
            infoPipe=sp.Popen(['explorer', os.path.normpath(os.path.split(self.inputFile)[0])])
        else:
            infoPipe=sp.Popen(['open', os.path.normpath(os.path.split(self.inputFile)[0])])

    def setBatchDirectoryConvert(self):
        if(len(self.batchDirectory.get('1.0', tkinter.END)) > 1):
            self.thumbnailOpenButton.grid_forget()
            self.convertFileButton["text"] = "Convert Directory"
            self.showBatchDirectoryList()
            self.progressBarVar.set(0)

            # Batch convert directory
            print(len(self.batchDirectory.get('1.0', tkinter.END)))
            print("Batch converting videos in "+str(self.batchDirectory.get('1.0', tkinter.END)))
            path = self.batchDirectory.get('1.0', tkinter.END).strip()

            self.filesToConvert = []

            for root_dir, _, files in os.walk(path):
                os.chdir(self.batchDirectory.get('1.0', tkinter.END).strip())
                for file in files:
                    print(file)
                    for extension in ('.mp4', '.mov', '.mpg', '.mpeg', '.avi', '.gif'):
                        if file.lower().endswith(extension):
                            full_path = os.path.join(root_dir, file)
                            self.filesToConvert.append(full_path)
                            break
            fileNames = []
            for file in self.filesToConvert:
                fileNames.append(os.path.basename(file))
            self.filesToConvertVar.set(fileNames if (len(fileNames) > 0) else ["No videos in directory!"])

        self.initVideoData()
        self.displayVidData()

    def onConvert(self, event=''):
        if(len(self.batchDirectory.get('1.0', tkinter.END)) > 1):
            # Batch convert directory
            global outDir

            path = self.batchDirectory.get('1.0', tkinter.END).strip()

            if self.filesToConvert:
                print(f"\nFound {len(self.filesToConvert)} files in '{path}':")
                for f in self.filesToConvert:
                    print(f)
            else:
                print(f"No files found in '{path}'.")
                return

            self.batchOutputDirectory.delete('1.0', tkinter.END)
            outDir = tkinter.filedialog.askdirectory(title="Choose Output Directory").strip()
            if(outDir != ''):
                self.batchOutputDirectory.insert(tkinter.END, outDir)
                outDir = self.batchOutputDirectory.get('1.0', tkinter.END).strip()
                if(len(outDir) < 1):
                    outDir = path
                print("Output dir: "+outDir)

                self.totalTime = 0
                for file in self.filesToConvert:
                    self.setVideoInfo(file, init = False)
                    self.totalTime += self.durationSeconds

                print("Converting "+str(self.totalTime)+" seconds of video")

                self.accumTime = 0

                videoIndex = 0
                for file in self.filesToConvert:
                    self.setVideoInfo(file)
                    self.outputFile = outDir + '/' + os.path.basename(file)[:-4] + (".mp4" if self.VideoOutputSettings.outputFormat.get() == 3 else (".tsv" if self.VideoOutputSettings.outputFormat.get() == 2 else ".avi"))
                    print(self.outputFile)
                    print("Set output file to "+self.outputFile)
                    self.volumeAdjust = 0.0
                    if self.VideoOutputSettings.normalizeAudio.get() == 1 :
                        self.volumeAdjust = (0-self.runVolumeDetect(True)) * 0.95
                        self.audioBoostStringLabel.configure(text="%.1f dB" % (self.volumeAdjust))

                    if(self.VideoOutputSettings.outputFormat.get() == 1):
                        self.convertAVI(self.inputFile, self.outputFile, self.inputVidFrameBytes, self.outputVidFrameBytes, videoIndex, len(self.filesToConvert))
                    elif(self.VideoOutputSettings.outputFormat.get() == 2):
                        self.convertTSV(self.inputFile, self.outputFile, self.inputVidFrameBytes, self.outputVidFrameBytes, videoIndex, len(self.filesToConvert))
                    elif(self.VideoOutputSettings.outputFormat.get() == 3):
                        self.convertMP4(self.inputFile, self.outputFile, self.inputVidFrameBytes, self.outputVidFrameBytes, videoIndex, len(self.filesToConvert))
                    videoIndex += 1

                    self.accumTime += self.durationSeconds

                self.convertFileButton["text"] = "Convert Directory"
                self.PreviewThumbnail.grid_forget()
                self.PreviewListbox.grid(row=1, column=0,sticky='nsew')
                self.ListScrollbar.grid(row=1,column=1,sticky='nsew')
                self.progressBarVar.set(0)
                self.outputSizeField.config(text = "-")
                self.durationStringField.config(text="--:--:--")

            return

        # Single video convert
        self.totalTime = self.durationSeconds
        self.accumTime = 0

        if(self.outputSize==0):
            self.showNoVideoWarning()
            return
        extStr = ".avi"
        fileTypeDescrip = 'AVI compatible with TinyTV'
        if self.VideoOutputSettings.outputFormat.get() == 2:
            extStr = ".tsv"
            fileTypeDescrip = 'TSV compatible with TinyTV DIY Kit'
        if self.VideoOutputSettings.outputFormat.get() == 3:
            extStr = ".mp4"
            fileTypeDescrip = 'MP4 compatible with TinyTV 2 / Mini'
        print(extStr)
        saveNewVideoAs = tkinter.filedialog.asksaveasfilename(initialfile=(os.path.splitext(os.path.split(self.inputFile)[1])[0]),defaultextension=extStr,filetypes=[(fileTypeDescrip, '*'+extStr)] ) #-confirmoverwrite, -defaultextension, -filetypes, -initialdir, -initialfile, -parent, -title, or -typevariable
        if(len(saveNewVideoAs) < 1):
            return
        if(os.path.splitext(saveNewVideoAs)[1] != extStr):
            messagebox.showwarning('TinyTV Converter', 'File extension should be ' + extStr + ', not ' + os.path.splitext(saveNewVideoAs)[1] + ', please retry!')
        self.outputFile = saveNewVideoAs

        self.volumeAdjust = 0.0
        if self.VideoOutputSettings.normalizeAudio.get() == 1 :
            self.volumeAdjust = (0-self.runVolumeDetect(True)) * 0.95
            #messagebox.showwarning('TinyTV Converter', 'Adjusting volume by ' + "%.1f dB" % (self.volumeAdjust))
            self.audioBoostStringLabel.configure(text="%.1f dB" % (self.volumeAdjust))


        convertThread = threading.Thread(target=self.convertAVI, args=(self.inputFile, self.outputFile, self.inputVidFrameBytes, self.outputVidFrameBytes, 0, 1))
        if(self.VideoOutputSettings.outputFormat.get() == 2):
            convertThread = threading.Thread(target=self.convertTSV, args=(self.inputFile, self.outputFile, self.inputVidFrameBytes, self.outputVidFrameBytes, 0, 1))
        if(self.VideoOutputSettings.outputFormat.get() == 3):
            convertThread = threading.Thread(target=self.convertMP4, args=(self.inputFile, self.outputFile, self.inputVidFrameBytes, self.outputVidFrameBytes, 0, 1))
        convertThread.daemon=True
        convertThread.start()

    def runVolumeDetect(self,afterResample):
        if(len(self.inputFile)<5):
            return 0.0
        filter = ''
        if afterResample :
            filter = 'aresample=10000,aresample=async=1000,asetnsamples=n=210:p=0,aresample=osf=u8,'
        volumeDetectCommand = [ FFMPEG_BIN,
            '-i', self.inputFile,
            '-vn',
            '-ac', '1',
            '-af', filter+'volumedetect',
            '-f', 'null', '/dev/null'
            ]

        cmdPipe = '';
        if os.name=='nt' :
            startupinfo = sp.STARTUPINFO()
            startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
            cmdPipe=sp.Popen(volumeDetectCommand, stdout = sp.PIPE, stderr=sp.STDOUT, universal_newlines=True, startupinfo=startupinfo)
        else:
            cmdPipe=sp.Popen(volumeDetectCommand, stdout = sp.PIPE, stderr=sp.STDOUT, universal_newlines=True)
        maxVolume = 0.0
        for line in cmdPipe.stdout:
            if 'max_volume' in line:
                db = line.split(':')[1]
                maxVolume = float(db.split('dB')[0].strip())

        cmdPipe.terminate()
        cmdPipe.stdout.close()
        cmdPipe.wait()

        return maxVolume

    def convertMP4(self, infile, outfile, inVidFrameBytes, outVidFrameBytes, videoIndex, numVideos):

        timer=time.time()

        scaleCommand= self.getScaleCommand(208,128) if (self.VideoOutputSettings.TVTypeOption.get() == 3) else self.getScaleCommand(64,64)

        bitRate = '94208'
        vidcommand = getMP4ConvertCommand(FFMPEG_BIN, scaleCommand, bitRate, infile, outfile, self.VideoOutputSettings.outputFrameRate, self.VideoOutputSettings.outputAudioSampleRate, self.volumeAdjust)

        self.vidPipe = None;
        if os.name=='nt' :
            startupinfo = sp.STARTUPINFO()
            startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
            self.vidPipe=sp.Popen(vidcommand, stdout = sp.PIPE, stderr=sp.STDOUT, universal_newlines=True, startupinfo=startupinfo)
        else:
            self.vidPipe=sp.Popen(vidcommand, stdout = sp.PIPE, stderr=sp.STDOUT, universal_newlines=True)

        for line in self.vidPipe.stdout:
            print(line)
            self.updateProgressBarTime(line)

        vidFrame = self.vidPipe.stdout.read()
        print(len(vidFrame))
        while len(vidFrame)==inVidFrameBytes:
            print(len(vidFrame))
            vidFrame = self.vidPipe.stdout.read(inVidFrameBytes)

        self.progressBarVar.set(100.0)

        print("Terminating vidpipe!")

        self.vidPipe.terminate()
        self.vidPipe.stdout.close()
        self.vidPipe.wait()
        self.vidPipe = None;

        timer=time.time()-timer

        m, s = divmod(timer, 60)
        h, m = divmod(m, 60)

        time.sleep(0.5)
        self.progressBarVar.set(0.0)

    def updateProgressBarTime(self, line):
        if('time=' in line):
            finalTimeString=  line.split('time=')[1].split(' ')[0]
            finalTimeStringSplit=  finalTimeString.split(':')
            currentTime=0
            if len(finalTimeStringSplit) == 1:
                currentTime = float(finalTimeStringSplit[0]) if finalTimeStringSplit[0] != 'N/A' else 0.0
            if len(finalTimeStringSplit) == 2:
                currentTime = float(finalTimeStringSplit[0])*60.0
                currentTime += float(finalTimeStringSplit[1])
            if len(finalTimeStringSplit) == 3:
                currentTime = float(finalTimeStringSplit[0])*60.0*60.0
                currentTime += float(finalTimeStringSplit[1])*60.0
                currentTime += float(finalTimeStringSplit[2])
            self.progressBarVar.set(100.0*(self.accumTime)/self.totalTime + (0 if self.durationSeconds == 0 else 100.0*(currentTime/self.totalTime)))
            self.parent.update()

    def convertAVI(self, infile, outfile, inVidFrameBytes, outVidFrameBytes, videoIndex, numVideos):
        timer=time.time()

        scaleCommand=self.getScaleCommand(self.VideoOutputSettings.outputWidth,self.VideoOutputSettings.outputHeight)

        bitRate = "1500k"
        if(self.VideoOutputSettings.outputHeight <= 64):
            bitRate = "300k"
        vidcommand = getAVIConvertCommand(FFMPEG_BIN, scaleCommand, bitRate, infile, outfile, self.VideoOutputSettings.outputFrameRate, self.VideoOutputSettings.outputAudioSampleRate, self.volumeAdjust)

        self.vidPipe = None;
        if os.name=='nt' :
            startupinfo = sp.STARTUPINFO()
            startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
            self.vidPipe=sp.Popen(vidcommand, stdout = sp.PIPE, stderr=sp.STDOUT, universal_newlines=True, startupinfo=startupinfo)
        else:
            self.vidPipe=sp.Popen(vidcommand, stdout = sp.PIPE, stderr=sp.STDOUT, universal_newlines=True)

        for line in self.vidPipe.stdout:
            self.updateProgressBarTime(line)

        vidFrame = self.vidPipe.stdout.read()
        print(len(vidFrame))
        while len(vidFrame)==inVidFrameBytes:
            print(len(vidFrame))
            vidFrame = self.vidPipe.stdout.read(inVidFrameBytes)

        self.progressBarVar.set(100.0)

        print("Terminating vidpipe!")

        self.vidPipe.terminate()
        self.vidPipe.stdout.close()
        self.vidPipe.wait()
        self.vidPipe = None;

        timer=time.time()-timer

        m, s = divmod(timer, 60)
        h, m = divmod(m, 60)

        time.sleep(0.5)
        self.progressBarVar.set(0.0)

    def convertTSV(self, infile, outfile, inVidFrameBytes, outVidFrameBytes, videoIndex, numVideos):
        timer=time.time()

        output=open(outfile, 'wb')
        devnull = open(os.devnull, 'wb')

        scaleCommand=self.getScaleCommand(self.VideoOutputSettings.outputWidth,self.VideoOutputSettings.outputHeight)

        vidcommand = [ FFMPEG_BIN,
            '-i', infile,
            '-f', 'image2pipe',
            '-r', '%d' % (self.VideoOutputSettings.outputFrameRate),
            '-vf', scaleCommand,
            '-vcodec', 'rawvideo',
            '-pix_fmt', 'bgr565be',
            '-strict', 'unofficial',
            '-f', 'rawvideo', '-']

        self.vidPipe = None;
        if os.name=='nt' :
            startupinfo = sp.STARTUPINFO()
            startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
            self.vidPipe=sp.Popen(vidcommand, stdin = sp.PIPE, stdout = sp.PIPE, stderr = devnull, bufsize=inVidFrameBytes*10, startupinfo=startupinfo)
        else:
            self.vidPipe=sp.Popen(vidcommand, stdin = sp.PIPE, stdout = sp.PIPE, stderr = devnull, bufsize=inVidFrameBytes*10)

        vidFrame = self.vidPipe.stdout.read(inVidFrameBytes)

        audioCommand = [ FFMPEG_BIN,
            '-i', infile,
            '-f', 's16le',
            '-acodec', 'pcm_s16le',
            '-ar', '%d' % (self.VideoOutputSettings.outputAudioSampleRate),
            '-ac', '1',
            '-']

        audioPipe=''
        if (self.VideoOutputSettings.audioEnable.get() == 1):
            if os.name=='nt' :
                startupinfo = sp.STARTUPINFO()
                startupinfo.dwFlags |= sp.STARTF_USESHOWWINDOW
                audioPipe = sp.Popen(audioCommand, stdin = sp.PIPE, stdout=sp.PIPE, stderr = devnull, bufsize=self.audioFrameBytes*10, startupinfo=startupinfo)
            else:
                audioPipe = sp.Popen(audioCommand, stdin = sp.PIPE, stdout=sp.PIPE, stderr = devnull, bufsize=self.audioFrameBytes*10)

            audioFrame = audioPipe.stdout.read(self.audioFrameBytes)

        currentFrame=0;

        while len(vidFrame)==inVidFrameBytes:
            currentFrame+=1
            if(currentFrame%30==0):
                self.progressBarVar.set(100.0*(self.accumTime)/self.totalTime + 100.0*self.durationSeconds*(currentFrame*1.0)/(self.totalFrames*self.totalTime))
                self.parent.update()
            if (self.VideoOutputSettings.videoBitDepth.get() == 16):
                output.write(vidFrame)
            else:
                b16VidFrame=bytearray(vidFrame)
                b8VidFrame=[]
                for p in range(outVidFrameBytes):
                    b8VidFrame.append(((b16VidFrame[(p*2)+0]>>0)&0xE0)|((b16VidFrame[(p*2)+0]<<2)&0x1C)|((b16VidFrame[(p*2)+1]>>3)&0x03))
                output.write(bytearray(b8VidFrame))

            vidFrame = self.vidPipe.stdout.read(inVidFrameBytes)
            if (self.VideoOutputSettings.audioEnable.get() == 1):
                if len(audioFrame)==self.audioFrameBytes:
                    audioData=bytearray(audioFrame)
                    # This is slow
                    for j in range(int(round(self.audioFrameBytes/2))):
                        sample = ((audioData[(j*2)+1]<<8) | audioData[j*2]) + 0x8000
                        sample = (sample>>(16-self.VideoOutputSettings.tsvAudioSampleBitDepth)) & (0x0000FFFF>>(16-self.VideoOutputSettings.tsvAudioSampleBitDepth))
                        audioData[j*2] = sample & 0xFF
                        audioData[(j*2)+1] = sample>>8

                    output.write(audioData)
                    audioFrame = audioPipe.stdout.read(self.audioFrameBytes)
                else:
                    emptySamples=[]
                    for samples in range(int(round(self.audioFrameBytes/2))):
                        emptySamples.append(0x00)
                        emptySamples.append(0x00)
                    output.write(bytearray(emptySamples))

        self.progressBarVar.set(100.0)

        self.vidPipe.terminate()
        self.vidPipe.stdout.close()
        self.vidPipe.wait()
        self.vidPipe = None;

        if (self.VideoOutputSettings.audioEnable.get() == 1):
            audioPipe.terminate()
            audioPipe.stdout.close()
            audioPipe.wait()

        output.close()

        timer=time.time()-timer

        m, s = divmod(timer, 60)
        h, m = divmod(m, 60)

        time.sleep(0.1)
        self.progressBarVar.set(0.0)


def main():
    root = Tk()
    style = Style()
    TinyTVC = TinyTVConverter(root)
    # root.geometry("550x175+300+300")
    root.resizable(width=False, height=False)
    if os.name=='nt' :
        root.iconbitmap(resource_path('icon.ico'))
    #if sys.platform=='darwin':
        #root.iconbitmap(resource_path('icon.gif'))
        #root.iconphoto(True, PhotoImage(file="icon.gif"))
        #iconImage = Image("photo", file=resource_path('icon.gif'))
        #iconImage = Image('photo', file='icon.gif')
        #iconImage = PhotoImage(file='icon.gif')
        #root.tk.call('wm','iconphoto',root._w, iconImage)
        #Give up on title bar icon!
        #root.lift()
        #root.attributes('-topmost', True)
        #root.after_idle(root.attributes,'-topmost',False)
    #program_directory=sys.path[0]

    #root.wm_overrideredirect(True)

    root.config(menu="") # Disable menubar

    root.mainloop()


if __name__ == '__main__':
    main()
