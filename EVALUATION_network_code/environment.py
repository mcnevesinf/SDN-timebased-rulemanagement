#!/usr/bin/python

#"""
#This example creates a multi-controller network from
#semi-scratch; note a topo object could also be used and
#would be passed into the Mininet() constructor.
#"""

#======================================
#            PARAMETERS
#======================================
#  -> Simulation time (in seconds)
#  -> Number of flows



import argparse

from mininet.net import Mininet
from mininet.node import Controller, RemoteController, OVSKernelSwitch
from mininet.link import TCLink
#from mininet.cli import CLI
#from mininet.log import setLogLevel

from TopoParser import *
import random
import os
import time

global flowList
flowList = []

global PARAM_useFlowList
PARAM_useFlowList = False


def readFlowDuration( flowID ):
    file = open("flows/flow"+str(flowID)+".txt", "r")

    line = file.readline()
    flowDuration = file.readline()

    file.close()

    return flowDuration


def executeEmulation(hostDescriptionList, switchDescriptionList, \
                     linkDescriptionList, numberOfActiveFlows, \
                     numberOfFlowDescriptors, simulationTime):

    net = Mininet(switch=OVSKernelSwitch, link=TCLink)

    controllerList = []
    switchList = []
    hostList = []
    linkList = []

    global PARAM_useFlowList
    global flowList

    print "*** Creating controller"
    controllerList.append( net.addController( 'c1', controller=RemoteController, defaultIP='0.0.0.0', port=6633) )

    print "*** Creating switches"
    for switch in switchDescriptionList:
        switchList.append( net.addSwitch( switch ) )

    print "*** Creating hosts"
    for host in hostDescriptionList:
        hostList.append( net.addHost( host ) )

    print "*** Creating links"
    for link in linkDescriptionList:
        node1 = net.getNodeByName( link[0] )
        node2 = net.getNodeByName( link[1] )
        linkList.append( net.addLink( node1, node2, bw=int(link[2]) ) )


    print "*** Starting network"
    net.build()
    net.start()

    print "*** Testing network"
    
    net.pingAll()

    print "*** Network tested"

    flowStartTimeList = []
    flowDurationList = []
    flowListIterator = 0

    activeFlows = 0

    random.seed()
    #print(len(hostList))
    #print( random.randrange(0, len(hostList)) )
    #print( random.randrange(0, len(hostList)) )

    startTime = time.time()
    currentTime = time.time()
    elapsedTime = currentTime - startTime

    print "*** Start evaluation process"

    simulationProcessed = 0.0
    print("Processed "+str(simulationProcessed)+"%")

    while( elapsedTime < simulationTime ):

        #Delete finished flows from the control structure
        flowControlIterator = len( flowDurationList ) - 1

        while( flowControlIterator >= 0 ):
            flowEndTime = flowStartTimeList[flowControlIterator] + flowDurationList[flowControlIterator] - startTime
            
            if( elapsedTime > flowEndTime ):
                #Delete flow
                flowStartTimeList[flowControlIterator] = -1
                flowStartTimeList.remove( -1 )

                flowDurationList[flowControlIterator] = -1
                flowDurationList.remove( -1 )

                activeFlows -= 1

            flowControlIterator -= 1



        if( activeFlows < numberOfActiveFlows ):

            #print("Will create flows")

            while( activeFlows < numberOfActiveFlows ):
                #-----------------
                #CREATE A NEW FLOW
                #-----------------

                #Choose one host to be a server
                server = hostList[ random.randrange(0, len(hostList)) ]
    
                #Choose a different host to be a client
                client = hostList[ random.randrange(0, len(hostList)) ]

                while( client.IP() == server.IP() ):
                    client = hostList[ random.randrange(0, len(hostList)) ]

                #Choose connection ports
                serverPort = random.randrange(15002, 25001)
                clientPort = random.randrange(5001, 15001)
                #print("Server port: " + str(serverPort))
                #print("Client port: " + str(clientPort))

                #Choose a flow descriptor
                if PARAM_useFlowList:
                    #From a flow list

                    #Use the flow list as a circular data structure
                    if flowListIterator == len(flowList):
                        flowListIterator = 0

                    flowID = flowList[flowListIterator]
                    flowListIterator += 1
                else:
                    #Randonly
                    flowID = random.randrange(1, numberOfFlowDescriptors + 1)
                
                #print("Flow ID: " + str(flowID) )

                #Execute the server
                #print "Server"
                server.cmd("./server.py "+str(flowID)+" "+str(server.IP())+" "+
                  str(serverPort)+" &")

                #server.cmd("./server.py "+str(flowID)+" "+str(server.IP())+" "+
                #  str(serverPort)+" &")
                
                #Duracao da simulacao deve ser muito maior que a duracao dos 
                #fluxos para evitar que esse sleep interfira na avaliacao
                #Sleep necessario para evitar connections refused onde o
                #cliente tenta se conectar num servidor cujo processo ainda
                #nao foi instanciado

                #time.sleep(2)
                time.sleep(0.05) #-------- MAC OSX --------


                #Execute the client
                #print "Client"
                print client.cmd("./client.py "+str(flowID)+" "+str(client.IP())+" "+
                  str(clientPort)+" "+str(server.IP())+" "+str(serverPort)+" &")

                #Save in a control structure <START_TIME, FLOW_DURATION>
                flowStartTimeList.append( time.time() )

                flowDuration = readFlowDuration( flowID )
                flowDurationList.append( int(flowDuration) + 3 )
                
                #Update the number of active flows
                activeFlows += 1

                print(str(server.IP()) + "  " + str(serverPort) + "  " + str(client.IP()) + 
                 "  " + str(clientPort) + "  " + str(time.time() - startTime) + "  " + str(flowDuration))

        #Time update
        currentTime = time.time()
        elapsedTime = currentTime - startTime

        newSimulationProcessed = (elapsedTime / simulationTime) * 100

        if newSimulationProcessed <= 100.0:
            if (newSimulationProcessed) - simulationProcessed > 3.0:
                print("Processed "+str( round(newSimulationProcessed, 2) )+"%")
                simulationProcessed = newSimulationProcessed
        else:
            print("Processed 100%")


    print "*** Evaluation time finished"
    print "*** Waiting for the end of every flows"

    #Once the simulation time finished, wait until all active flows finish too
    while( activeFlows > 0 ):

        #Delete finished flows from the control structure
        flowControlIterator = len( flowDurationList ) - 1

        while( flowControlIterator >= 0 ):
            flowEndTime = flowStartTimeList[flowControlIterator] + flowDurationList[flowControlIterator] - startTime

            currentTime = time.time()
            elapsedTime = currentTime - startTime

            if( elapsedTime > flowEndTime ):
                #Delete flow
                flowStartTimeList[flowControlIterator] = -1
                flowStartTimeList.remove( -1 )

                flowDurationList[flowControlIterator] = -1
                flowDurationList.remove( -1 )
        
                activeFlows -= 1

            flowControlIterator -= 1
    
    print "*** End of evaluation process"

    #net.pingAll()

    print "*** Stopping network"
    net.stop()



if __name__ == '__main__':
    #setLogLevel( 'info' )  # for CLI output
  
    #---------------------------------------------
    #Parse input arguments
    #---------------------------------------------

    #Describe args
    parser = argparse.ArgumentParser()
    parser.add_argument("-t", "--topo", help="Name of the file describing the network topology.", action="store", dest="topoFileName")
    parser.add_argument("-f", "--flowList", help="List of flows to be used. Default is random.", action="store", dest="flowListName")
    parser.add_argument("-n", "--nFlows", help="Number of active flows in the network", action="store", type=int, dest="PARAM_numberOfActiveFlows")
    parser.add_argument("-d", "--nDescriptors", help="Number of flow descriptors in the flow base", action="store", type=int, dest="PARAM_numberOfFlowDescriptors")
    parser.add_argument("-s", "--duration", help="Duration of the simulation (in seconds)", action="store", type=int, dest="PARAM_simulationTime")

    #Get args
    args = parser.parse_args()

    #Verify whether a topo file was informed
    if args.topoFileName:
        print args.topoFileName
    else:
        args.topoFileName = "default.txt"
        #print args.topoFileName


    #Verify whether a flow list was informed
    if args.flowListName:
        print args.flowListName
        PARAM_useFlowList = True
    else:
        args.flowListName = "random"
        #print args.flowListName

    if PARAM_useFlowList:
        flowListFile = open("flowLists/"+str(args.flowListName), "r")

        line = flowListFile.readline()

        while( line != "" ):
            line = line[:len(line)-1]
            flowList.append( line )

            line = flowListFile.readline()

        flowListFile.close()

        print(flowList)

    #Verify whether a number of active flows was informed
    if args.PARAM_numberOfActiveFlows:
        numberOfActiveFlows = args.PARAM_numberOfActiveFlows
    else:
        numberOfActiveFlows = 5


    #Verify whether a number of flow descriptors was informed
    if args.PARAM_numberOfFlowDescriptors:
        numberOfFlowDescriptors = args.PARAM_numberOfFlowDescriptors
    else:
        numberOfFlowDescriptors = 3


    #Verify whether a duration for the emulation was informed
    if args.PARAM_simulationTime:
        simulationTime = args.PARAM_simulationTime
    else:
        simulationTime = 60

    #---------------------------------------------
    #Parse input data
    #---------------------------------------------
    print "*** Reading network topology"
    hostDescriptionList = []
    switchDescriptionList = []
    linkDescriptionList = []

    parseTopo(args.topoFileName, hostDescriptionList, switchDescriptionList, linkDescriptionList)


    #---------------------------------------------
    #Execute the emulation
    #---------------------------------------------
    executeEmulation(hostDescriptionList, switchDescriptionList, \
                     linkDescriptionList, numberOfActiveFlows, \
                     numberOfFlowDescriptors, simulationTime)
