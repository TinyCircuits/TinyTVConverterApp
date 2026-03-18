from tkinter import IntVar, DoubleVar, StringVar, BOTH, Text, Menu, END, X, W, E, NW, PhotoImage, Image, Canvas, Listbox, Toplevel, Grid, messagebox, simpledialog

class VideoOutputSettingsClass():
    def __init__(self):
        self.outputFormat = IntVar()
        self.videoBitDepth = IntVar()
        self.normalizeAudio = IntVar()
        self.audioEnable = IntVar()
        self.TVTypeOption = IntVar()
        self.videoWindowOption = IntVar()

        self.outputWidth=210
        self.outputHeight=135
        self.outputFrameRate=30.0
        self.outputAudioSampleRate=10000
        self.outputBytesPerSecond=30000
        self.tsvAudioSampleBitDepth=10
        self.tsvAudioSampleCountPerFrame=1024

        pass

    def dumpJSONSettingsStr(self):
        settings = {
            "outputFormat": self.outputFormat.get(),
            "videoBitDepth": self.videoBitDepth.get(),
            "normalizeAudio": self.normalizeAudio.get(),
            "audioEnable": self.audioEnable.get(),
            "TVTypeOption": self.TVTypeOption.get(),
            "videoWindowOption": self.videoWindowOption.get(),

            "outputWidth": self.outputWidth,
            "outputHeight": self.outputHeight,
            "outputFrameRate": self.outputFrameRate,
            "outputAudioSampleRate": self.outputAudioSampleRate,
            "outputBytesPerSecond": self.outputBytesPerSecond,
        }
        print(json.dumps(settings))
        return json.dumps(settings)

    def loadJSONSettings(self, settingsJSONFile):
        settings = json.load(settingsJSONFile)

        self.outputFormat.set(settings["outputFormat"])
        self.videoBitDepth.set(settings["videoBitDepth"])
        self.normalizeAudio.set(settings["normalizeAudio"])
        self.audioEnable.set(settings["audioEnable"])
        self.TVTypeOption.set(settings["TVTypeOption"])
        self.videoWindowOption.set(settings["videoWindowOption"])

        self.outputWidth = settings["outputWidth"]
        self.outputHeight = settings["outputHeight"]
        self.outputFrameRate = settings["outputFrameRate"]
        self.outputAudioSampleRate = settings["outputAudioSampleRate"]
        self.outputBytesPerSecond = settings["outputBytesPerSecond"]

    def calculateVideoData(self):
        if (self.TVTypeOption.get() == 3):
            self.outputWidth=210
            self.outputHeight=135
            if(self.outputFormat.get() == 1):
                self.outputFrameRate=24.0
                self.outputAudioSampleRate=10000
                self.outputBytesPerSecond=187500
            elif(self.outputFormat.get() == 2):
                self.outputFrameRate=30.0
                self.outputAudioSampleRate=self.outputFrameRate*self.tsvAudioSampleCountPerFrame
                self.outputBytesPerSecond= self.outputFrameRate*self.outputWidth*self.outputHeight*2 + self.outputAudioSampleRate*2
            else:
                self.outputFrameRate=24.0
                self.outputAudioSampleRate=10000
                self.outputBytesPerSecond=(96+32)*1024/8
        if (self.TVTypeOption.get() == 2):
            self.outputWidth=64
            self.outputHeight=64
            if(self.outputFormat.get() == 1):
                self.outputFrameRate=24.0
                self.outputAudioSampleRate=10000
                self.outputBytesPerSecond=37500
            elif(self.outputFormat.get() == 2):
                self.outputFrameRate=30.0
                self.outputAudioSampleRate=self.outputFrameRate*self.VideoOutputSettings.tsvAudioSampleCountPerFrame
                self.outputBytesPerSecond= self.outputFrameRate*self.outputWidth*self.outputHeight*2 + self.outputAudioSampleRate*2
            else:
                self.outputFrameRate=24.0
                self.outputAudioSampleRate=10000
                self.outputBytesPerSecond=96*1024/8
        if (self.TVTypeOption.get() == 1):
            self.outputWidth=96
            self.outputHeight=64
            if(self.outputFormat.get() == 1):
                self.outputFrameRate=24.0
                self.outputAudioSampleRate=10000
                self.outputBytesPerSecond=37500
            elif(self.outputFormat.get() == 2):
                self.outputFrameRate=30.0
                self.outputAudioSampleRate=self.outputFrameRate*self.tsvAudioSampleCountPerFrame
                self.outputBytesPerSecond= self.outputFrameRate*self.outputWidth*self.outputHeight*2 + self.outputAudioSampleRate*2
            else:
                # MP4 not implemented for TinyTV Kit
                pass
