#!/usr/bin/python

#Arguments

# -> List name
# -> Number of elements in the list
# -> Number of flows in the base

import random
import argparse

if __name__ == "__main__":

    #-----------------------------------------------------
    #Parse input arguments
    #-----------------------------------------------------

    #Describe args
    parser = argparse.ArgumentParser()
    parser.add_argument("-n", "--listName", help="Name of the flow list", action="store", dest="PARAM_listName")
    parser.add_argument("-b", "--baseSize", help="Number of flows in the flow base", action="store", type=int, dest="PARAM_flowBaseSize")
    parser.add_argument("-s", "--listSize", help="Number of elements in the list", action="store", type=int, dest="PARAM_listSize")

    #Get args
    args = parser.parse_args()

    if args.PARAM_listName:
        listName = args.PARAM_listName
    else:
        listName = "default_list.txt"

    if args.PARAM_flowBaseSize:
        flowBaseSize = args.PARAM_flowBaseSize
    else:
        flowBaseSize = 3

    if args.PARAM_listSize:
        listSize = args.PARAM_listSize
    else:
        listSize = 10

    flowList = []

    random.seed()

    for iterator in range(0, listSize):
        flowList.append( random.randrange(1, flowBaseSize+1) )

    print( flowList )

    file = open("flowLists/"+listName, "w")

    for flow in flowList:
        file.write( str(flow)+"\n" )

    file.close()
