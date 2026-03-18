import shutil   	# Copy files
import psutil   	# List disks/partitions
import os       	# General path checking
import time     	# Sleeping
import subprocess	# Calling other commands
import serial.tools.list_ports


# https://stackoverflow.com/a/287944
class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


class SerIO:
    ''' Wrapper to control Ender 3 over serial. '''
    def __init__(self):
        self.ser = None
        #self.connect(port, baudrate, bytesize, timeout)
    
    def get_port(self, hwid="VID:PID=03EB:8009"):
        ports = serial.tools.list_ports.comports()
        for port in ports:
            if hwid in port.hwid:
                #print("Found device at" + port.device)
                return port.device

    def connect(self, port: str, baudrate=115200, bytesize=8, timeout: int = None):
        '''Connects to 3D printer at specified serial port. Will fail if port is already connected. Cura will often block serial port.'''
        self.ser = serial.Serial(port, baudrate=baudrate, bytesize=bytesize, timeout=timeout)
        print("Connected to serial IO device ", self.ser.name, "!")
        
        for i in range(20):
            self.pinMode(i,'INPUT')
        self.pinMode(4,'OUTPUT')
        self.digitalWrite(4,'HIGH')
    
    def disconnect(self):
        '''Closes the connection to the 3D printer's serial port'''
        self.ser.close()
        
    def pinMode(self, pin, state):
        if 'OUTPUT' in state:
            state = 'O'
        elif 'INPUT' in state:
            state = 'I'
        elif 'INPUT_PULLUP' in state:
            state = 'U'
        elif 'INPUT_PULLDOWN' in state:
            state = 'D'
        else:
            print('Unexpected state: ', state)
            return
        #print(str.encode('$P' + str(pin).zfill(2) + state))
        self.ser.write(str.encode('$P' + str(pin).zfill(2) + state))
        
    def digitalWrite(self, pin, state):
        if 'HIGH' in state:
            state = 'H'
        elif 'LOW' in state:
            state = 'L'
        else:
            print('Unexpected state: ', state)
            return
        #print(str.encode('$W' + str(pin).zfill(2) + state))
        self.ser.write(str.encode('$W' + str(pin).zfill(2) + state))


# Pass a vendor:product id string like "2E8A:0005" and returns either:
# * str: "/dev/ttyACM0" or "COM1"
# * None: not found
def GetPortString(vendorAndProductID, timeoutMS=0):
    startTimeMS = time.time() * 1000
    endTimeMS = startTimeMS + timeoutMS

    while time.time() * 1000 < endTimeMS:
        ports = serial.tools.list_ports.comports()

        # Loop through ports until find one with the expected HWIDs
        for port, desc, hwid in sorted(ports):
            #print(port, desc, hwid)
            time.sleep(0.05)
            if vendorAndProductID in hwid:
                return port
                
    return None


def doesPicoBootDeviceExist(path_to_common):
    try:
        #print("1")
        picotool_path = path_to_common + "/" + "picotool-2.0.0"
        process = subprocess.Popen([picotool_path, 'info'], stdout=subprocess.PIPE)
        #print("2")
        output = process.stdout.read().decode("utf-8")
        #print("3")
        if "Program Information" in output:
            return True
    except Exception as e:
        print("exception:")
        print(e)
    return False


def PicoErase(path_to_common):
    picotool_path = path_to_common + "/" + "picotool-2.1.1"

    while True:
        process = subprocess.Popen([picotool_path, 'info'], stdout=subprocess.PIPE)
        output = process.stdout.read().decode("utf-8")

        # Check if we could get information on device, if so, connect and can load
        if "Program Information" in output:
            print(f"Found device, erasing...")
            
            with subprocess.Popen([picotool_path, 'erase'], stdout=subprocess.PIPE, universal_newlines=True) as process:
                for line in process.stdout:
                    print(line, end='')

            #print("Firmware loaded, rebooting device...")
            process = subprocess.Popen([picotool_path, 'reboot'], stdout=subprocess.PIPE)
            #print(bcolors.OKGREEN + "Firmware loaded and device rebooted!" + bcolors.ENDC)

            # Give device a bit to reboot so it doesn't get uploaded to again
            time.sleep(0.25)

            break
        else:
            print(output)

        # Only issuing info command every 1/8th of a second
        time.sleep(0.125)


def WaitLoadFirmware(path_to_common, firmware_folder_path):
	# Check that firmware folder exists
    if(os.path.isdir(firmware_folder_path) == False):
        print("Folder '" + firmware_folder_path + "' doesn't exist! Stopping script!")
        exit()
    
    firmware_file_path = None
    
    # Firmware folder must exist, copy it to the RP2040 device
    for root, dirs, files in os.walk(os.path.abspath(firmware_folder_path)):
    	if firmware_file_path == None:
		    for file in files:
		        firmware_file_path = os.path.join(root, file)

		        # Only copy over the first item in the firmware folder
		        break

    picotool_path = path_to_common + "/" + "picotool-2.0.0"

    while True:
        process = subprocess.Popen([picotool_path, 'info'], stdout=subprocess.PIPE)
        output = process.stdout.read().decode("utf-8")

        # Check if we could get information on device, if so, connect and can load
        if "Program Information" in output:
            print(f"Found device, loading firmware {firmware_file_path}...")
            
            with subprocess.Popen([picotool_path, 'load', firmware_file_path], stdout=subprocess.PIPE, universal_newlines=True) as process:
                for line in process.stdout:
                    if 'Loading into Flash' in line:
                        LINE_UP = '\033[1A'
                        LINE_CLEAR = '\x1b[2K'
                        print(LINE_UP, end=LINE_CLEAR)
                        print(line.strip())
                    else:
                        print(line, end='')

            #print("Firmware loaded, rebooting device...")
            process = subprocess.Popen([picotool_path, 'reboot'], stdout=subprocess.PIPE)
            #print(bcolors.OKGREEN + "Firmware loaded and device rebooted!" + bcolors.ENDC)

            # Give device a bit to reboot so it doesn't get uploaded to again
            time.sleep(0.25)

            break
        else:
            print(output)

        # Only issuing info command every 1/8th of a second
        time.sleep(0.125)


# Returns path to found removable drive. Does not timeout. If wanted, pass size of drive to look for to single it out (RP2040 in BOOTSEL for example)
def WaitForRemovableConnect():
    # Wait forever until a disk is found and the loop is broken by return
    while(True):
        # Get all disks/partitions connected to computer
        disks = psutil.disk_partitions()

        # Go through each disk/partition and check if it is both removable and FAT32 (signifies SD card)
        for disk in disks:
            if((disk.fstype == "FAT32" or disk.fstype == "FAT" or disk.fstype == "vfat") and (("removable" in disk.opts and "rw" in disk.opts) or ("rw" in disk.opts and "uid=1000" in disk.opts and "gid=1000" in disk.opts))):
                print("Found drive:", disk.mountpoint)
                return disk.mountpoint
        
        # Don't need to check too often
        time.sleep(0.1)


def EjectDrive(mountpoint):
    print("Ejecting " + mountpoint)

    if os.name == "posix":
        os.system("umount " + mountpoint)
    else:
        # https://stackoverflow.com/a/70075381
        # https://superuser.com/a/1761373
        os.system('powershell $driveEject = New-Object -comObject Shell.Application; $driveEject.Namespace(17).ParseName("""E:""").InvokeVerb("""Eject"""); Start-Sleep -Seconds 2')


def CheckRemovableConnected(mountpoint_path):
    # Go through each disk/partition and check if it is both removable and FAT32 (signifies SD card)
    disks = psutil.disk_partitions()
    for disk in disks:
        if((disk.fstype == "FAT32" or disk.fstype == "FAT" or disk.fstype == "vfat") and ("removable" in disk.opts or "rw" in disk.opts) and disk.mountpoint == mountpoint_path):
            return True
    
    return False


# Stalls 
def WaitForRemovableDisconnect(mountpoint_path):
    print("\nWaiting for drive", mountpoint_path, "to disconnect...")

    # Wait forever until the mountpoint_path is not found in a connected partition
    while(True):
        # The mountpoint was not found in a removable, FAT32 device, done stalling
        if(CheckRemovableConnected(mountpoint_path) == False):
            print(bcolors.OKGREEN + "Drive disconnected!" + bcolors.ENDC)
            return

        # Don't need to check too often
        time.sleep(0.1)


# For controlling the KORAD KA3005P power supply
class PowerSupply:
    def __init__(self, output_voltage, current_limit):
        self.vid = "0416"
        self.pid = "5011"
        self.serial = None
        self.current_limit = current_limit
        
        try:
            # Blocks until power supply connects
            self.connect()
            #self.printInfo()
            self.disableOverCurrentProtection()
            self.enableOverVoltageProtection()
            self.setOutputVoltage(output_voltage)
            self.setCurrentLimit(current_limit)
        except Exception as exc:
            print("Something failed during power supply init:", exc)
    
    # Connect serial PS serial parameters in page 14 of manual
    # -Baudrate: 9600
    # -Parity bit: None
    # -Data bit: 8
    # -Stop bit: 1
    # -Data flow control: None
    def connect(self):
        print("Waiting for power supply... ",end='')
        self.serial = None
        
        while self.serial == None:
            ports = serial.tools.list_ports.comports()
            
            # Loop through ports until find one with the expected HWIDs
            for port, desc, hwid in sorted(ports):
                if self.vid in hwid and self.pid  in hwid:
                    self.serial = serial.Serial(port, baudrate=9600, timeout=1, parity=serial.PARITY_NONE, bytesize=serial.EIGHTBITS, stopbits=serial.STOPBITS_ONE, dsrdtr=False)
                    print("Connected!", port)
    
    # Print power supply information
    def printInfo(self):
        time.sleep(0.05)
        self.serial.write("*IDN?".encode('utf-8'))
        print("\n" + self.serial.read(30).decode("utf-8"))
    
    def disableOverCurrentProtection(self):
        time.sleep(0.05)
        self.serial.write("OCP0".encode('utf-8'))
        #print("\tOCP: OFF")
    
    def enableOverVoltageProtection(self):
        time.sleep(0.05)
        self.serial.write("OVP1".encode('utf-8'))
        #print("\tOVP: ON")
    
    # [V]
    def setOutputVoltage(self, output_voltage):
        time.sleep(0.05)
        self.serial.write(("VSET1:" + str(output_voltage)).encode('utf-8'))
        #print("\tOutput Voltage:", str(output_voltage) + "V")
    
    # [A]
    def setCurrentLimit(self, current_limit):
        time.sleep(0.05)
        self.current_limit = current_limit
        self.serial.write(("ISET1:" + str(current_limit)).encode('utf-8'))
        #print("\tCurrent Limit:", str(current_limit) + "A\n")
    
    # Returns drawn current in [A]
    def readCurrent(self):
        time.sleep(0.05)
        self.serial.write("IOUT1?".encode('utf-8'))
        try:
            return round(float(self.serial.read(5)), 5)
        except:
            print("Power supply read current error")

    def turnOutputOn(self):
        time.sleep(0.05)
        self.serial.write("OUT1".encode('utf-8'))

    def turnOutputOff(self):
        time.sleep(0.05)
        self.serial.write("OUT0".encode('utf-8'))


