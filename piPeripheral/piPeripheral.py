#!/usr/bin/python3
# Copyright:	None, placed in the PUBLIC DOMAIN by its author (Ron Burkey)
# Filename: 	piPeripheral.py
# Purpose:	This is the skeleton of a program that can be used for creating
#		a Python-language based peripheral for the AGC simulator program,
#		yaAGC.  You can see an example of how to use it in piDSKY.py.  
# Reference:	http://www.ibiblio.org/apollo/developer.html
# Mod history:	2017-11-17 RSB	Began.
#
# The parts which need to be modified to be target-system specific are the 
# outputFromAGC() and inputsForAGC() functions.
#
# To run the program in its present form, assuming you had a directory setup in 
# which all of the appropriate files could be found, you could run (presumably 
# from different consoles)
#
#	yaAGC --core=Luminary099.bin --port=19797 --cfg=LM.ini
#	piPeripheral.py


# Hardcoded characteristics of the host and port being used.  Change these as
# required.  I will assume the port for a secondary LM DSKY, which is not
# something that usually would exist (which is why I chose it).
TCP_IP = 'localhost'
TCP_PORT = 19798

###################################################################################
# Hardware abstraction / User-defined functions.  Also, any other platform-specific
# initialization.  This is the section to customize for specific applications.

# This function is automatically called periodically by the event loop to check for 
# conditions that will result in sending messages to yaAGC that are interpreted
# as changes to bits on its input channels.  The return
# value is supposed to be a list of 3-tuples of the form
#	[ (channel0,value0,mask0), (channel1,value1,mask1), ...]
# and may be an empty list.  The "values" are written to the AGC's input "channels",
# while the "masks" tell which bits of the "values" are valid.  (The AGC will ignore
# the invalid bits.)
def inputsForAGC():
	return []

# This function is called by the event loop only when yaAGC has written
# to an output channel.  The function should do whatever it is that needs to be done
# with this output data, which is not processed additionally in any way by the 
# generic portion of the program.
def outputFromAGC(channel, value):
	return

###################################################################################
# Generic initialization (TCP socket setup).  Has no target-specific code, and 
# shouldn't need to be modified unless there are bugs.

import time
import socket

s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
s.setblocking(0)

def connectToAGC():
	while True:
		try:
			s.connect((TCP_IP, TCP_PORT))
			print("Connected to yaAGC (" + TCP_IP + ":" + str(TCP_PORT) + ")")
			break
		except socket.error as msg:
			print("Could not connect to yaAGC (" + TCP_IP + ":" + str(TCP_PORT) + "), exiting: " + str(msg))
			time.sleep(1)

connectToAGC()

###################################################################################
# Event loop.  Just check periodically for output from yaAGC (in which case the
# user-defined callback function outputFromAGC is executed) or data in the 
# user-defined function inputsForAGC (in which case a message is sent to yaAGC).
# But this section has no target-specific code, and shouldn't need to be modified
# unless there are bugs.

# Given a 3-tuple (channel,value,mask), creates packet data and sends it to yaAGC.
def packetize(tuple):
	outputBuffer = bytearray(4)
	# First, create and output the mask command.
	outputBuffer[0] = 0x20 | ((tuple[0] >> 3) & 0x0F)
	outputBuffer[1] = 0x40 | ((tuple[0] << 3) & 0x38) | ((tuple[2] >> 12) & 0x07)
	outputBuffer[2] = 0x80 | ((tuple[2] >> 6) & 0x3F)
	outputBuffer[3] = 0xC0 | (tuple[2] & 0x3F)
	s.send(outputBuffer)
	# Now, the actual data for the channel.
	outputBuffer[0] = 0x00 | ((tuple[0] >> 3) & 0x0F)
	outputBuffer[1] = 0x40 | ((tuple[0] << 3) & 0x38) | ((tuple[1] >> 12) & 0x07)
	outputBuffer[2] = 0x80 | ((tuple[1] >> 6) & 0x3F)
	outputBuffer[3] = 0xC0 | (tuple[1] & 0x3F)
	s.send(outputBuffer)

# Buffer for a packet received from yaAGC.
packetSize = 4
inputBuffer = bytearray(packetSize)
leftToRead = packetSize
view = memoryview(inputBuffer)

didSomething = False
while True:
	if not didSomething:
		time.sleep(0.05)
	didSomething = False
	
	# Check for packet data received from yaAGC and process it.
	# While these packets are always exactly 4
	# bytes long, since the socket is non-blocking, any individual read
	# operation may yield less bytes than that, so the buffer may accumulate data
	# over time until it fills.	
	try:
		numNewBytes = s.recv_into(view, leftToRead)
	except:
		numNewBytes = 0
	if numNewBytes > 0:
		view = view[numNewBytes:]
		leftToRead -= numNewBytes
		if leftToRead == 0:
			# Prepare for next read attempt.
			view = memoryview(inputBuffer)
			leftToRead = packetSize
			# Parse the packet just read, and call outputFromAGC().
			# Start with a sanity check.
			ok = 1
			if (inputBuffer[0] & 0xF0) != 0x00:
				ok = 0
			elif (inputBuffer[1] & 0xC0) != 0x40:
				ok = 0
			elif (inputBuffer[2] & 0xC0) != 0x80:
				ok = 0
			elif (inputBuffer[3] & 0xC0) != 0xC0:
				ok = 0
			# Packet has the various signatures we expect.
			if ok == 0:
				# Note that, depending on the yaAGC version, it occasionally
				# sends either a 1-byte packet (just 0xFF, older versions)
				# or a 4-byte packet (0xFF 0xFF 0xFF 0xFF, newer versions)
				# just for pinging the client.  These packets hold no
				# data and need to be ignored, but for other corrupted packets
				# we print a message. And try to realign past the corrupted
				# bytes.
				if inputBuffer[0] != 0xff or inputBuffer[1] != 0xff or inputBuffer[2] != 0xff or inputBuffer[2] != 0xff:
					if inputBuffer[0] != 0xff:
						print("Illegal packet: " + hex(inputBuffer[0]) + " " + hex(inputBuffer[1]) + " " + hex(inputBuffer[2]) + " " + hex(inputBuffer[3]))
					for i in range(1,packetSize):
						if (inputBuffer[i] & 0xF0) == 0:
							j = 0
							for k in range(i,4):
								inputBuffer[j] = inputBuffer[k]
								j += 1
							view = view[j:]
							leftToRead = packetSize - j
			else:
				channel = (inputBuffer[0] & 0x0F) << 3
				channel |= (inputBuffer[1] & 0x38) >> 3
				value = (inputBuffer[1] & 0x07) << 12
				value |= (inputBuffer[2] & 0x3F) << 6
				value |= (inputBuffer[3] & 0x3F)
				outputFromAGC(channel, value)
			didSomething = True
	
	# Check for locally-generated data for which we must generate messages
	# to yaAGC over the socket.  In theory, the externalData list could contain
	# any number of channel operations, but in practice (at least for something
	# like a DSKY implementation) it will actually contain only 0 or 1 operations.
	externalData = inputsForAGC()
	for i in range(0, len(externalData)):
		packetize(externalData[i])
		didSomething = True
		