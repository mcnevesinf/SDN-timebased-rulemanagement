#!/usr/bin/python

#==================
#Arguments
#==================
# -> Number of flows
# -> Packet interarrival distribution - Poisson | Weibull
# -> Flow duration distribution - Lognormal | Exponential

import argparse
import random
import numpy

def generateRandomNumber( distribution, duration ):
    randomNumber = -1 

    if distribution == "Lognormal":
        mu = 4
        sigma = 1
        randomNumber = random.lognormvariate(mu, sigma)
    elif distribution == "Exponential":
        lam = 0.02
        randomNumber = random.expovariate(lam)
    elif distribution == "Poisson":
        lam = 10
        randomNumber = numpy.random.poisson(lam)
    elif distribution == "Weibull":
        scale = 4
        shape = 0.6
        randomNumber = random.weibullvariate(scale, shape)


    return int(randomNumber)


if __name__ == "__main__":

    #-------------------------------------------------
    #Parse input arguments
    #-------------------------------------------------

    #Describe args
    parser = argparse.ArgumentParser()
    parser.add_argument("-d", "--durationDist", help="Flow duration probability distribution - Lognormal | Exponential", action="store", dest="PARAM_durationDist")
    parser.add_argument("-i", "--interPacketDist", help="Packet interarrival probability distribution - Poisson | Weibull", action="store", dest="PARAM_interPacketDist")
    parser.add_argument("-f", "--nFlows", help="Number of flows", action="store", type=int, dest="PARAM_numberOfFlows")

    #Get args
    args = parser.parse_args()

    if args.PARAM_durationDist:
        flowDurationDist = args.PARAM_durationDist
    else:
        flowDurationDist = "Lognormal"


    if args.PARAM_interPacketDist:
        packetInterarrivalDist = args.PARAM_interPacketDist
    else:
        packetInterarrivalDist = "Poisson"


    if args.PARAM_numberOfFlows:
        numberOfFlows = args.PARAM_numberOfFlows
    else:
        numberOfFlows = 3

    DURATION = 0
    INTER_ARRIVAL = 1

    random.seed()

    for iterator in range(1, numberOfFlows+1):
        flowDuration = 0

        while flowDuration == 0:
            flowDuration = generateRandomNumber( flowDurationDist, DURATION )
        print( str(flowDuration) )

        interArrivalList = []

        currentDuration = 0
        numberOfPackets = 0

        while currentDuration < flowDuration:
            interPacketTime = generateRandomNumber( packetInterarrivalDist, \
                                                    INTER_ARRIVAL )

            if interPacketTime != 0:
                if currentDuration + interPacketTime > flowDuration:
                    interPacketTime = flowDuration - currentDuration

                interArrivalList.append( interPacketTime )
                numberOfPackets += 1
                currentDuration += interPacketTime

        print("Number of packets: "+str(numberOfPackets))
        print(interArrivalList)

        file = open("flows/flow"+str(iterator)+".txt", "w")

        file.write("START_FLOW_DURATION\n")
        file.write( str(flowDuration)+"\n" )
        file.write("END_FLOW_DURATION\n")

        file.write("START_NUMBER_OF_PACKETS\n")
        file.write( str(numberOfPackets)+"\n" )
        file.write("END_NUMBER_OF_PACKETS\n")

        file.write("START_FLOW\n")
        
        for i in interArrivalList:
            file.write( str(i)+"\n" )

        file.write("END_FLOW\n")

        file.close()
