#!/usr/bin/python

#PARAMETERS
#	FIRST: Server IP
#	SECOND: Server port

import sys

from socket import *


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



if __name__ == "__main__":

	flowID = sys.argv[1]
	serverIP = sys.argv[2]
	serverPort = sys.argv[3]

	numberOfPackets = getNumberOfPackets( flowID )
	#print(numberOfPackets)

	sock = socket(AF_INET, SOCK_STREAM) #Create the socket
	sock.bind( (serverIP, int(serverPort)) ) #Listen in the specific port and IP
	sock.listen(1) #Listen just one connection

	#print "Wait connection..."
	client = sock.accept() #Accept and wait for connecitons
	clientSock = client[0]

	packetsReceived = 0

	while( packetsReceived < numberOfPackets ):
		msg = clientSock.recv(1024)
		#print msg
		packetsReceived = packetsReceived + 1

		


	
	
