#!/usr/bin/python

#PARAMETERS
#	FIRST: Client IP
#	SECOND: Client port
#	THIRD: Server IP
#	FOURTH: Server port

from socket import *

import sys
import time


def getNumberOfPackets( flowID ):
	filePointer = open("flows/flow"+flowID+".txt", "r")

	line = filePointer.readline()
	line = line[:len(line)-1]

	numberNotFound = True

	while( numberNotFound ):
		  line = filePointer.readline()
		  line = line[:len(line)-1]

		  if( line == "START_NUMBER_OF_PACKETS" ):
				line = filePointer.readline()
				line = line[:len(line)-1]

				numberOfPackets = int(line)

				numberNotFound = False

	filePointer.close()

	return numberOfPackets



def getInterArrivalTimes( flowID ):
	filePointer = open("flows/flow"+flowID+".txt", "r")

	interArrivalTimes = []

	line = filePointer.readline()
	line = line[:len(line)-1]
 
	while( line != "END_FLOW" ):
		  line = filePointer.readline()
		  line = line[:len(line)-1]

		  if( line == "START_FLOW" ):
		      line = filePointer.readline()
		      line = line[:len(line)-1]

		      while( line != "END_FLOW" ):
		          interArrivalTimes.append( int(line) )

		          line = filePointer.readline()
		          line = line[:len(line)-1]

	filePointer.close()

	return interArrivalTimes



if __name__ == "__main__":

	flowID = sys.argv[1]
	clientIP = sys.argv[2]
	clientPort = sys.argv[3]
	serverIP = sys.argv[4]
	serverPort = sys.argv[5]

	sock = socket(AF_INET, SOCK_STREAM) #Create the socket
	sock.bind( (clientIP, int(clientPort)) )

        #print("Server IP: "+serverIP)
        #print("Server port: "+serverPort)
	sock.connect( (serverIP, int(serverPort)) )

	msg = "Just a message."

	numberOfPackets = getNumberOfPackets( flowID )
	#print(numberOfPackets)

	packetsSent = 0
	interArrivalTimes = getInterArrivalTimes( flowID )
	#print interArrivalTimes

	while( packetsSent < numberOfPackets ):
		sock.send( msg )
		packetsSent = packetsSent + 1
		#print("Packets sent: " + str(packetsSent) + " Number of packets: " + str(numberOfPackets))
		#print("Will sleep " + str(interArrivalTimes[packetsSent-1]) + " seconds")
		time.sleep( interArrivalTimes[packetsSent-1] )












