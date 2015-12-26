#!/usr/bin/python

#ARGUMENTS
# -> Flow list
# -> Simulation time
# -> Number of active flows
# -> Table size

import argparse
import numpy

PARAM_simulationTime = 0
PARAM_numberOfActiveFlows = 0
PARAM_numberOfFlowDescriptors = 0
PARAM_tableSize = 0

flowList = [] #Flow descriptor identification
flowBase = [] # Flow duration, packet times
flowTable = [] # Flow ID

flowEventsList = [] # Flow ID, end time, reinstallations, packet times
FLOW_EVENT = 0
FLOW_EVENT_ID_POS = 0
END_TIME_POS = 1
REINSTALLATION_POS = 2
FIRST_PACKET_TIME_POS = 3

packetEventsList = [] # Packet time, flow ID
PACKET_EVENT = 1
PACKET_EVENT_TIME_POS = 0
PACKET_EVENT_ID_POS = 1

flowID = 1
flowListIterator = 0

activeFlows = 0
time = 1

#Metrics
timelineTableUtil = []
reinstallationsPerFlow = []



def readFlowBase():
	
	iterator = 1;

	while iterator <= PARAM_numberOfFlowDescriptors:
		flowFile = open("flows/flow"+str(iterator)+".txt", "r")

		flow = []
		numberOfPackets = 0

		line = flowFile.readline()

		while( line != "" ):
			line = line[:len(line)-1]
			#print(line)

			if line == "START_FLOW_DURATION":
				line = flowFile.readline()
				line = line[:len(line)-1]
				#print(line)
				flow.append( int(line) )

			if line == "START_NUMBER_OF_PACKETS":
				line = flowFile.readline()
				line = line[:len(line)-1]
				numberOfPackets = int(line)

			if line == "START_FLOW":
				packetIterator = 0

				while packetIterator < numberOfPackets:
					line = flowFile.readline()
					line = line[:len(line)-1]

					#print(line)
					flow.append( int(line) )

					packetIterator += 1

			line = flowFile.readline()

		flowFile.close()

		flowBase.append( flow )

		iterator += 1

	#print( flowBase )


#=========================================
#						FLOW EVENT CODE
#=========================================
def printFlowEventsList():
	global flowEventsList

	print("\n\n------------------")
	print("  FLOW EVENTS")
	print("------------------")

	for event in flowEventsList:
		print(str(event))

	print("------------------\n\n")	



def deleteFlow( flowEventsListPosition ):
	global flowEventList
	global reinstallationsPerFlow
	global activeFlows

	#print("FLOW FINISHED.")

	#Remove from flow table
	flowID = flowEventsList[flowEventsListPosition][FLOW_EVENT_ID_POS]
	#print("Flow deletion - ID: " + str(flowID))

	if( inTable( flowID ) ):
		flowTableDelete( flowID )

	#Measure the number of reinstallations
	reinstallationsPerFlow.append( flowEventsList[flowEventsListPosition][REINSTALLATION_POS] )

	#Remove from flow event list
	flowEventsList.remove( flowEventsList[flowEventsListPosition] )

	#Update number of active flows
	activeFlows -= 1



#=========================================
#						PACKET EVENT CODE
#=========================================
def printPacketEventsList():
	global packetEventsList

	print("\n\n------------------")
	print("  PACKET EVENTS")
	print("------------------")

	for event in packetEventsList:
		print(str(event))

	print("------------------\n\n")	



def addPacketEvent( flowID, packetTime ):
	global packetEventsList

	#print "ADD PACKET."

	packetEvent = []
	packetEvent.append( packetTime )
	packetEvent.append( flowID )

	packetEventsListSize = len(packetEventsList)

	if(packetEventsListSize == 0):
		packetEventsList.append( packetEvent )
	else:
	
		iterator = 0

		while(packetTime > packetEventsList[iterator][PACKET_EVENT_TIME_POS] and
					iterator < packetEventsListSize-1):
			iterator += 1

		if(iterator == packetEventsListSize-1):
			if( packetTime > packetEventsList[iterator][PACKET_EVENT_TIME_POS] ):
				packetEventsList.append( packetEvent )
			else:
				packetEventsList.insert( iterator, packetEvent )
		else:
			packetEventsList.insert( iterator, packetEvent )






#=========================================
#						FLOW TABLE CODE
#=========================================
def printFlowTable():
	global flowTable

	print("\n\n------------------")
	print("   FLOW TABLE")
	print("------------------")

	for entry in flowTable:
		print(str(entry))

	print("------------------\n\n")



def optimalDeletion():
	global flowTable
	global flowEventsList

	nextPacketList = [] #Flow ID, packet time

	#Pick next packet time from entries in the flow table
	for entry in flowTable:
		nextPacket = []
		nextPacket.append( entry )

		iterator = 0
		flowFound = False

		while( iterator < len(flowEventsList) and 
					 not flowFound):
			if( flowEventsList[iterator][FLOW_EVENT_ID_POS] == entry ):

				#print(str(iterator))
				if( len(flowEventsList[iterator]) < 4 ):
					nextPacket.append( 1000000 )
				#print("Time: " + str(time))
				#print("Packet time: " + str(flowEventsList[iterator][FIRST_PACKET_TIME_POS]))
				else:
					nextPacket.append( flowEventsList[iterator][FIRST_PACKET_TIME_POS] )

				flowFound = True

			else:

				iterator += 1

		if(not flowFound):
			#To the case when the flow is still in the table but has already finished
			nextPacket.append( 1000000 )

		nextPacketList.append( nextPacket )

	#Compute the optimal entry
	maxPacketTime = 0
	optEntry = -1

	FLOW_ID_POS = 0
	TIME_POS = 1

	for packet in nextPacketList:
		#print(len(packet))
		#print(packet[0])

		if( packet[TIME_POS] > maxPacketTime ):
			maxPacketTime = packet[TIME_POS]
			optEntry = packet[FLOW_ID_POS]

	#Remove optimal entry
	flowTable.remove( optEntry )




def flowTableInsert( flowID, event ):
	global PARAM_tableSize
	global flowTable
	global flowEventsList

	#print "INSERT TABLE ENTRY."

	if(event == PACKET_EVENT):
		#Count a reinstallation
		iterator = 0
		flowFound = False

		while( iterator < len(flowEventsList) and 
					 not flowFound):
			if( flowEventsList[iterator][FLOW_EVENT_ID_POS] == flowID ):
				flowEventsList[iterator][REINSTALLATION_POS] += 1
				flowFound = True
			else:
				iterator += 1


	if( len(flowTable) == PARAM_tableSize ):
		#Table full
		#print("TABLE FULL.")
		optimalDeletion()
		flowTable.append( flowID )

	else:
		#Table not full
		flowTable.append( flowID )



		


def flowTableDelete( flowID ):
	global flowTable

	#print "DELETE TABLE ENTRY."
	flowTable.remove( flowID )


def inTable( flowID ):
	global flowTable

	#print "LOOK FOR TABLE ENTRY."
	iterator = 0
	entryFound = False

	while( iterator < len(flowTable) and 
				 not entryFound ):
		if( flowTable[iterator] == flowID ):
			entryFound = True
		else:
			iterator += 1

	return entryFound



#=========================================
#								MAIN CODE
#=========================================

if __name__ == '__main__':

	#Describe args
	parser = argparse.ArgumentParser()
	parser.add_argument("-f", "--flowList", help="Flow list.", action="store", dest="flowListName")
	parser.add_argument("-s", "--duration", help="Duration of the simulation (in seconds).", action="store", type=int, dest="PARAM_simulationTime")
	parser.add_argument("-n", "--nFlows", help="Number of active flows in the network.", action="store", type=int, dest="PARAM_numberOfActiveFlows")
	parser.add_argument("-d", "--nDescriptors", help="Number of flow descriptors in the flow base.", action="store", type=int, dest="PARAM_numberOfFlowDescriptors")
	parser.add_argument("-t", "--tableSize", help="Table size.", action="store", type=int, dest="PARAM_tableSize")

	#Get args
	args = parser.parse_args()


	print("\n\n--------------------------")
	print("    INPUT DATA")
	print("--------------------------")

	#Verify whether a flow list was informed
	if args.flowListName:
		#print args.flowListName
		PARAM_useFlowList = True
	else:
		args.flowListName = "random"
		#print args.flowListName

	print( "Flow list: " + str(args.flowListName) )

	if PARAM_useFlowList:
		flowListFile = open("flowLists/"+str(args.flowListName), "r")

		line = flowListFile.readline()

		while( line != "" ):
			line = line[:len(line)-1]
			flowList.append( line )

			line = flowListFile.readline()

		flowListFile.close()

	#print(flowList)

	#Verify whether a duration for the emulation was informed
	if args.PARAM_simulationTime:
		PARAM_simulationTime = args.PARAM_simulationTime
	else:
		PARAM_simulationTime = 60

	print( "Simulation time: " + str(PARAM_simulationTime) )

	#Verify whether a number of active flows was informed
	if args.PARAM_numberOfActiveFlows:
		PARAM_numberOfActiveFlows = args.PARAM_numberOfActiveFlows
	else:
		PARAM_numberOfActiveFlows = 5

	print( "Number of active flows: " + str(PARAM_numberOfActiveFlows) )

	#Verify whether a number of flow descriptors was informed
	if args.PARAM_numberOfFlowDescriptors:
		PARAM_numberOfFlowDescriptors = args.PARAM_numberOfFlowDescriptors
	else:
		PARAM_numberOfFlowDescriptors = 0

	print( "Number of flow descriptors: " + str(PARAM_numberOfFlowDescriptors) )

	#Verify whether a table size was informed
	if args.PARAM_tableSize:
		PARAM_tableSize = args.PARAM_tableSize
	else:
		PARAM_tableSize = 100

	print( "Table size: " + str(PARAM_tableSize) )

	print("--------------------------\n")

	#---------------------------------------
	# Read the flow base
	#---------------------------------------
	readFlowBase()

	processingEvolutionCounter = 0

	while time <= PARAM_simulationTime:
		#print("Time: " + str(time))

		#Print table state
		#printFlowTable()

		#------------------------------------------------
		#Verify which flows have finished
		#------------------------------------------------
		iterator = len(flowEventsList)
		#print("Flow event list - size: " + str(iterator+1))

		while(iterator > 0):
			#print("End time: " + str(flowEventsList[iterator][END_TIME_POS]))
			#print("Time: " + str(time))

			#print("End time: " + str(flowEventsList[iterator-1][END_TIME_POS]))

			if(flowEventsList[iterator-1][END_TIME_POS] <= time):

				#print("End time: " + str(flowEventsList[iterator-1][END_TIME_POS]))

				#Delete finished flow
				deleteFlow(iterator-1)

			iterator -= 1


		#------------------------------------------------			
		#Process packets that arrive at this instant
		#------------------------------------------------
		#printFlowEventsList()
		#printPacketEventsList()

		if( len(packetEventsList) > 0 ):
			processPacket = True

			while(processPacket == True and len(packetEventsList) > 0):
				if(packetEventsList[0][PACKET_EVENT_TIME_POS] == time):

					#Process packet
					packetData = packetEventsList[0]

					#Update flow table
					if( not inTable(packetData[PACKET_EVENT_ID_POS]) ):
						#Insert in the flow table
						#print("Packet not found in table.")

						flowTableInsert( packetData[PACKET_EVENT_ID_POS], PACKET_EVENT )

					#Update flow event list
					iterator = 0
					flowFound = False

					while( iterator < len(flowEventsList) and 
								 not flowFound ):
						if( flowEventsList[iterator][FLOW_EVENT_ID_POS] == packetData[PACKET_EVENT_ID_POS] ):
							flowEventsList[iterator][FIRST_PACKET_TIME_POS] = -1
							flowEventsList[iterator].remove( -1 )
							flowFound = True
						else:
							iterator += 1

					#Remove from packet event list
					packetEventsList.remove( packetData )

				else:
					processPacket = False


		#------------------------------------------------
		#Create new flows if necessary
		#------------------------------------------------
		if activeFlows < PARAM_numberOfActiveFlows:
			while activeFlows < PARAM_numberOfActiveFlows:

				flowCreationIterator = 1

				while(flowCreationIterator <= 2):
					#Create new flow
					flowEvent = []

					#Reset the flow list positioning mark
					if flowListIterator == len(flowList):
						flowListIterator = 0

					#print(str(flowListIterator))

					flowDescriptionID = flowList[flowListIterator]

					flowInformation = flowBase[int(flowDescriptionID)-1]

					flowEvent.append( flowID ) #Flow ID

					if( flowCreationIterator == 1 ):
						flowEvent.append( time + flowInformation[0] + 1 ) #End time
					else:
						flowEvent.append( time + 1 + flowInformation[0] + 1 ) #End time

					flowEvent.append(0) #Reinstallations

					#Packet times
					packetIterator = 1

					if( flowCreationIterator == 1 ):
						packetTime = time
					else:
						packetTime = time + 1

					while packetIterator < len(flowInformation):
						packetTime = packetTime + flowInformation[packetIterator]

						flowEvent.append( packetTime )

						addPacketEvent( flowID, packetTime )

						packetIterator += 1	

					#Insert the new flow in the flow table
					flowTableInsert( flowID, FLOW_EVENT )

					#Store the flow event

					flowEventsList.append( flowEvent )

					flowID += 1
					activeFlows += 1

					flowCreationIterator += 1

				flowListIterator += 1
				

		#Time update
		time += 1

		#Measure the flow table utilization
		timelineTableUtil.append( len(flowTable) )

		processingEvolutionCounter += 1

		if( processingEvolutionCounter == 20 ):
			print("Processed: " + str( (float(time)/float(PARAM_simulationTime)) * 100) + "%")
			processingEvolutionCounter = 0





	#print(timelineTableUtil)
	#print(reinstallationsPerFlow)

	percentUtil = []

	for utilMeasure in timelineTableUtil:
		percentUtil.append( float(utilMeasure) / float(PARAM_tableSize) )

	print("\n\n--------------------------")
	print("    UTILIZATION")
	print("--------------------------")
	print("NP mean size: "+str( numpy.mean(timelineTableUtil) ))
	print("NP std size: "+str( numpy.std(timelineTableUtil) ))

	print("NP mean util: " + str( numpy.mean(percentUtil) ))
	print("NP std util: " + str( numpy.std(percentUtil) ))
	print("--------------------------\n")


	print("\n\n--------------------------")
	print("    REINSTALLATIONS")
	print("--------------------------")
	print("Number of flows: "+str( len(reinstallationsPerFlow) ))
	print("NP sum: "+str( numpy.sum(reinstallationsPerFlow) ))
	print("NP mean: "+str( numpy.mean(reinstallationsPerFlow) ))
	print("NP std: "+str( numpy.std(reinstallationsPerFlow) ))
	print("NP 95th percentile: "+str( numpy.percentile(reinstallationsPerFlow, 95) ))
	print("--------------------------\n")
















