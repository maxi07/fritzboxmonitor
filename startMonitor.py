##!/usr/bin/env python
# Python script to monitor the status of your PiHole and FritzBox
# Author: Maximilian Krause
# Date 29.05.2021

# Define Error Logging
def printerror(ex):
	print('\033[31m' + str(ex) + '\033[0m')

def printwarning(warn):
	print('\033[33m' + str(warn) + '\033[0m')

# Load modules
import os
if not os.geteuid() == 0:
	printerror("Please run this script with sudo.")
	exit(2)

print("Welcome to network monitor for PiHole and FritzBox!")
print("Loading modules...")

try:
	import socket
	from cryptography.fernet import Fernet
	import configparser
	import time
	from signal import signal, SIGINT
	from sys import exit
	import os.path
	from gpiozero import CPUTemperature
	from os import path
	from datetime import datetime
	import base64
	import requests
	from fritzconnection.lib.fritzstatus import FritzStatus
	import json
	import argparse
	import lcddriver
	from urllib.request import urlopen
	import socket
except ModuleNotFoundError:
	printerror("The app could not be started.")
	printerror("Please run 'sudo ./install.sh' first.")
	exit(2)
except:
	printerror("An unknown error occured while loading modules.")
	exit(2)

# Define Var
version = 1.0
lcd_width = 16
fritzBoxIP = ""

# Ini Var - do not modify
hostname = None
piholeApi = None
webtoken = None
basicInfo = None
fritzUser = None
fritzPass = None
maxUpload = None
maxDownload = None


# Check for arguments
parser = argparse.ArgumentParser()
parser.add_argument("--version", "-v", help="Prints the version", action="store_true")
parser.add_argument("--backlightoff", "-b", help="Turns off the backlight of the lcd", action="store_true")


args = parser.parse_args()
if args.version:
	print(str(version))
	exit(0)

# Define print function for Display
def printLCD(msg, line=1):
	display.lcd_display_string(str(msg.ljust(lcd_width, ' ')[0:lcd_width]), line)

# Load driver for LCD display
try:
	print("Loading lcd drivers...")
	display = lcddriver.lcd()

	#Check backlight option
	if args.backlightoff:
		printwarning("Option: Backlight turned off!")
		display.backlight(0)
	else:
		display.backlight(1)

	printLCD("Loading Monitor..", 1)
	printLCD("V " + str(version), 2)
	time.sleep(1.5)
except IOError:
	printerror("The connection to the display failed.")
	printerror("Please check your connection for all pins.")
	printerror("From bash you can run i2cdetect -y 1")

	printerror("Would you like to proceed anyway (More errors might occur)? [y/n]")
	yes = {'yes', 'y'}
	no = {'no', 'n'}
	choice = input().lower()
	if choice in yes:
		print("Will continue...")
	elif choice in no:
		print("Shutting down... Bye!")
		exit(1)
	else:
		print("Please choose yes or no")
except Exception as e:
	printerror("An unknown error occured while connecting to the lcd.")
	printerror(e)

# Define custom LCD characters
# Char generator can be found at https://omerk.github.io/lcdchargen/
fontdata1 = [
	# char(0) - Check
	[0b00000,
	0b00001,
	0b00011,
	0b10110,
	0b11100,
	0b01000,
	0b00000,
	0b00000],

	# char(1) - Block
	[0b00000,
	0b11111,
	0b10011,
	0b10101,
	0b11001,
	0b11111,
	0b00000,
	0b00000],

	# char(2) - Box
	[0b11111,
	0b10001,
	0b10001,
	0b10001,
	0b10001,
	0b10001,
	0b10001,
	0b11111],

	# char(3) - Fill
	[0b11111,
	0b11111,
	0b11111,
	0b11111,
	0b11111,
	0b11111,
	0b11111,
	0b11111],

	# char(4) - Up Arrow
	[0b00100,
	0b01110, 
	0b10101, 
	0b00100, 
	0b00100, 
	0b00100, 
	0b00100, 
	0b00100],

	# char(5) - Down Arrow
	[0b00100,
	0b00100, 
	0b00100, 
	0b00100, 
	0b00100, 
	0b10101, 
	0b01110, 
	0b00100]
]
display.lcd_load_custom_chars(fontdata1)


#############
# FUNCTIONS #
#############


def detectFritzBox():
	isup = True if os.system("ping -c 1 " + str(fritzBoxIP) + "> /dev/null") is 0 else False
	return isup


#Handles Ctrl+C
def handler(signal_received, frame):
	# Handle any cleanup here
	print()
	printwarning('SIGINT or CTRL-C detected. Please wait until the service has stopped.')
	display.lcd_clear()
	printLCD("Manual cancel.", 1)
	printLCD("Exiting app.", 2)
	exit(0)


# Checks for updates
def checkUpdate():
	if is_connected == False:
		printwarning("No network, skipping update check.")
		return
	updateUrl = "https://raw.githubusercontent.com/maxi07/PiHole-Monitoring/main/doc/version"
	try:
		f = requests.get(updateUrl)
		latestVersion = float(f.text)
		if latestVersion > version:
			printwarning("There is an update available.")
			printwarning("Head over to https://github.com/maxi07/PiHole-Monitoring to get the hottest features.")
		else:
			print("Application is running latest version " + str(version) + ".")
	except Exception as e:
		printerror("An error occured while searching for updates.")
		printerror(e)


# Reads the local config file. If none exists, a new one will be created.
def readConfig():
	display.lcd_display_string("Reading config", 2)
	config = configparser.ConfigParser()
	if os.path.isfile(str(os.getcwd()) + "/config.ini"):
		print("Reading config...")
		config.read("config.ini")

		try:
			global fritzUser
			fritzUser = config["FritzBox"]["fritzUser"]
			global fritzPass
			key = config["FritzBox"]["key"].encode()
			fritzPass = config["FritzBox"]["fritzPass"].encode()
			fritzPass = decrypt(fritzPass, key)
			global maxUpload
			maxUpload = config["FritzBox"]["maxUpload"]
			global maxDownload
			maxDownload = config["FritzBox"]["maxDownload"]
			global fritzBoxIP
			fritzBoxIP = config["FritzBox"]["ip"]
			print("Config successfully loaded.")
			printLCD("Config loaded", 2)
		except Exception as e:
			printLCD("Config error", 2)
			printerror("Failed reading config.")
			printerror(str(e))
			exit(3)

	else:
		printwarning("Config does not exist, creating new file.")

		printLCD("Creating config", 2)
		# Detect pihole system
		print("Detecting your FritzBox...")
		fritzBoxIP = findFritzBox()
		while not fritzBoxIP:
			fritzBoxIP = input("Please enter your FritzBox address (e.g. 192.168.178.1): ")

		# Get FritzBox user and pass (ip will be detected automatically by module)
		fritzUser = ""
		while not fritzUser:
			fritzUser = input("Please enter your FritzBox username: ")
		fritzPass = ""
		while not fritzPass:
			fritzPass = input("Please enter your FritzBox password: ")
		maxUpload = ""
		while not maxUpload or maxUpload.isnumeric == False:
			maxUpload = input("Please enter your maximum upload in MBit/s (eg. 100): ")
		maxDownload = ""
		while not maxDownload or maxDownload.isnumeric == False:
			maxDownload = input("Please enter your maximum download in MBit/s (eg. 50): ")

		# Generate encryption key
		key = Fernet.generate_key()

		# Encrypt passwd for storage
		encPass = encrypt(fritzPass.encode(), key)

		config["FritzBox"] = {"fritzUser": fritzUser, "fritzPass": encPass.decode(), "key": key.decode(), "maxUpload": maxUpload, "maxDownload": maxDownload, "ip": fritzBoxIP}
		with open("config.ini", "w") as configfile:
			config.write(configfile)
			print("Stored a new config file.")
			printLCD("Stored config  ", 2)

def encrypt(message: bytes, key: bytes) -> bytes:
    return Fernet(key).encrypt(message)

def decrypt(token: bytes, key: bytes) -> bytes:
    return Fernet(key).decrypt(token)

# Detect PiHole by hostname
def findFritzBox():
	try:
		ip = socket.gethostbyname('fritz.box')
		print("Detected FritzBox at " + ip)
		return str(ip)
	except socket.gaierror:
		printwarning("No FritzBox could be detected.")
		return None

# Check or internet connection
def is_connected():
    try:
        # connect to the host -- tells us if the host is actually
        # reachable
        socket.create_connection(("www.google.com", 80))
        return True
    except:
        return False

def wait():
	time.sleep(2) #2 seconds

# Gets the transmission rate from the FritzBox
def getTransmissionRate():
	fc = FritzStatus(password=fritzPass, user=fritzUser)
	return fc.str_transmission_rate

# Converts the FritzBox transmission rate to Mbit/s
def convertToMbit(input):
	if input.endswith(" B"):
		value = input.split()[0]
		return round(float(value) / 125000, 2)
	elif input.endswith("KB"):
		value = input.split()[0]
		return round(float(value) / 125, 2)
	elif input.endswith("MB"):
		value = input.split()[0]
		return round(float(value) * 8, 2)
	else:
		printerror("Nothing matched! Value: " + str(input))
		return 0

# Converts the input to percent value of the max download or upload.
def convertPercent(input, max):
	value = int(round(input/int(max)*100, 0))
	if value <= 100:
		return value
	else:
		return 100

def printHeader():
	os.system('clear')
	print('##########################')
	print('    Network Monitoring     ')
	print('##########################')
	print()
	now = datetime.now()
	print("Last API call:\t\t" + now.strftime("%Y-%m-%d %H:%M:%S"))

	cpu = CPUTemperature()
	cpu_r = round(cpu.temperature, 2)
	print("Current CPU:\t\t" + str(cpu_r) + "°C")
	print("FritzBox IP:\t\t" + str(fritzBoxIP))



#Main
if __name__ == '__main__':
	# Tell Python to run the handler() function when SIGINT is recieved
	signal(SIGINT, handler)

	# Check version
	checkUpdate()

	# Read config first
	readConfig()

	lb = ""
	line1 = ""
	run = 0
	display.lcd_clear()
	printLCD("FritzBox IP:", 1)
	printLCD(str(fritzBoxIP), 2)
	while True:


		# Check if internet is reachable
		# Check if PiHole is reachable
		# Get basicInfo from API
		# Check if PiHole is enabled
		# Print to display

		# PiHole Enabled .
		# LastBlock

		if is_connected() == False:
			display.lcd_clear()
			printLCD("No network.", 1)
			printLCD("Check router.", 2)
			printerror("The network cannot be reached. Please check your router.")
			wait()
			continue

		# Now get the basic API info and store it
		print()

		# Get FritzBox Information and check if its reachable
		print("Checking for FritzBox...")
		if detectFritzBox == False:
			printwarning("FritzBox cannot be reached at " + str(fritzBoxIP) + ". ")
			display.lcd_clear()
			printLCD("No FritzBox.", 1)
			printLCD(str(fritzBoxIP), 2)
			wait()
			continue

		print("Retrieving FritzBox Updates..")
		try:
			tr = getTransmissionRate()
		except Exception as e:
			printerror("Failed reading FritzBox information.")
			printerror(e)
			wait()
			continue
		currentUpload = convertToMbit(tr[0])
		currentDownload = convertToMbit(tr[1])
		currentUploadPercent = convertPercent(convertToMbit(tr[0]), maxUpload)
		currentDownloadPercent = convertPercent(convertToMbit(tr[1]), maxDownload)

		printHeader()
		
		# Get Fritz Transmission Rate

		print("Upload:\t\t\t" + str(currentUpload) + " MBit/s | " + str(currentUploadPercent) + " %")
		print("Download:\t\t" + str(currentDownload) + " MBit/s | " + str(currentDownloadPercent) + " %")
		progressUploadString = ""
		progressDownloadString = ""
		for x in range(0,currentUploadPercent, 10):
			progressUploadString = progressUploadString + chr(3)
		for x in range(0,currentDownloadPercent, 10):
			progressDownloadString = progressDownloadString + chr(3)
		printLCD(progressUploadString.ljust(10, chr(2)) + chr(4) + " " + str(currentUploadPercent) + "%", 1)
		printLCD(progressDownloadString.ljust(10, chr(2)) + chr(5) + " " +  str(currentDownloadPercent) + "%", 2)

		wait()
