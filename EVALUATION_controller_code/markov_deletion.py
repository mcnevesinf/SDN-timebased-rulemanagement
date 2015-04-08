
from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.addresses import IPAddr

from pox.openflow.of_json import *
import time
import random

baseTimeList = []
PARAM_deletionInterval = 0
PARAM_tableSize = 0

markovChain = []

switchList = []
flowTableList = []
flowMarkovStateList = []
flowPacketCountList = []
processedFlowFlagList = []


log = core.getLogger()


def _handle_delstats_received(event):
    global switchList
    global flowTableList
    global flowMarkovStateList
    global flowPacketCountList
    global processedFlowFlagList
    global baseTimeList

    global markovChain


    def getRuleIndex(rule, ruleList):
        #print("Will look for the rule")

        ruleIndex = -1
        ruleFound = False
        iterator = 0

        #print("Rule list len: "+str(len(ruleList)))

        while not ruleFound and iterator < len(ruleList):
            if rule[0] == ruleList[iterator][0] and \
               rule[1] == ruleList[iterator][1] and \
               rule[2] == ruleList[iterator][2] and \
               rule[3] == ruleList[iterator][3]:
                ruleFound = True
                ruleIndex = iterator

            iterator += 1

        return ruleIndex



    def decideRuleDeletion(markovState):
        deletionDecision = False

        if markovState >= len(markovChain):
            deletionDecision = True
        elif markovState >= 0:
            x = random.random() * 100

            if x < markovChain[markovState]:
                deletionDecision = True

        #print("Value: "+str(x)+"  Prob: "+str(markovChain[markovState]))

        return deletionDecision




    stats = flow_stats_to_list(event.stats) #'stats' is a list of dictionaries. Each dictionary represents a rule
    #print(stats)

    log.debug("Deletion stats received from %s", str(event.connection.dpid))

    #Identify the switch
    switchIndex = 0
    addedSwitch = False

    try:
        switchIndex = switchList.index( str(event.connection.dpid) )
    except:
        switchList.append( str(event.connection.dpid) )
        switchIndex = len(switchList) - 1
        baseTimeList.append( time.time() ) #To control the rule deletion
        addedSwitch = True

    #Make a list with the rules in the received stats
    receivedRules = []
    flowPacketCount = []

    if len(stats) > 0:
        for item in stats:
            try:
                receivedRule = []
                receivedRule.append( str(item['match']['nw_src']) )
                receivedRule.append( str(item['match']['tp_src']) )
                receivedRule.append( str(item['match']['nw_dst']) )
                receivedRule.append( str(item['match']['tp_dst']) )

                receivedRules.append( receivedRule )
                #print(receivedRule)

                flowPacketCount.append( int(item['packet_count']) )
            except:
                #print("Rule is not TCP")
                pass

    #for rule in receivedRules:
    #    print(rule)

    #IF it is a new switch THEN add the flow tabel
    if addedSwitch:
        flowTableList.append( receivedRules )

        #Add number of packets
        flowPacketCountList.append( flowPacketCount )

        #Initialize flow Markov states and the respective processed flow flag list
        flowMarkovState = []
        processedFlowFlag = []

        for rule in receivedRules:
            flowMarkovState.append(0)
            processedFlowFlag.append(True)

        flowMarkovStateList.append( flowMarkovState )
        processedFlowFlagList.append( processedFlowFlag )        

        #print("============ Markov data added ============")

    #ELSE update an existing table
    else:

        #Reset processed flow flags
        for iterator in range(0, len(processedFlowFlagList[switchIndex])):
            processedFlowFlagList[switchIndex][iterator] = False
            
        #FOR each rule received, update it in the rule control structure
        for iterator in range(0, len(receivedRules)):
            ruleIndex = getRuleIndex( receivedRules[iterator], flowTableList[switchIndex] )

            #Se a regra nao esta na estrutura de controle, esta e adicionada
            if ruleIndex == -1:
                #print("Rule added to the control structure")

                flowTableList[switchIndex].append( receivedRules[iterator] )
                flowMarkovStateList[switchIndex].append( 0 )
                flowPacketCountList[switchIndex].append( flowPacketCount[iterator] )
                processedFlowFlagList[switchIndex].append( True )
            #Se a regra ja esta na estrutura de controle, esta e atualizada
            else:
                #print("Rule found. Index: "+str(ruleIndex))

                #IF the rule has not received packets THEN its Markov state is incremented
                if flowPacketCountList[switchIndex][ruleIndex] == flowPacketCount[iterator]:
                    flowMarkovStateList[switchIndex][ruleIndex] += 1
                #ELSE the rule has received packets, therefore its Markov state is reseted and the packet count updated
                else:
                    flowMarkovStateList[switchIndex][ruleIndex] = 0
                    flowPacketCountList[switchIndex][ruleIndex] = flowPacketCount[iterator]

                #Mark the rule as processed
                processedFlowFlagList[switchIndex][ruleIndex] = True

        #Limpa regras que nao existem mais das tabelas de controle
        iterator = len( flowTableList[switchIndex] ) - 1

        while iterator >= 0:
            if processedFlowFlagList[switchIndex][iterator] == False:
                #Delete rule from the control tables
                flowTableList[switchIndex][iterator] = -1
                flowTableList[switchIndex].remove( -1 )

                flowPacketCountList[switchIndex][iterator] = -1
                flowPacketCountList[switchIndex].remove( -1 )

                flowMarkovStateList[switchIndex][iterator] = -1
                flowMarkovStateList[switchIndex].remove( -1 )

                processedFlowFlagList[switchIndex][iterator] = -1
                processedFlowFlagList[switchIndex].remove( -1 )

                #print("Rule deleted from the control structure")

            iterator -= 1


        #--------------------------------------------------------
        #Delete rules according to the states of the Markov chain
        #--------------------------------------------------------

        currentTime = time.time()

        #IF the time elapsed since the last deletion is greater than the deletion interval THEN apply the Markov deletion
        #ELSE nothing to do
        #print("Elapsed time: "+str(currentTime - baseTimeList[switchIndex]))
        #print("Deletion interval: "+str(PARAM_deletionInterval))

        if (currentTime - baseTimeList[switchIndex]) > PARAM_deletionInterval:
            
            for iterator in range(0, len(flowTableList[switchIndex])):
                #print("Rule will be deleted. Markov state: "+str(flowMarkovStateList[switchIndex][iterator]))

                #Deleta a regra com a probabilidade definida pelo estado na cadeia de Markov
                deleteRule = decideRuleDeletion( flowMarkovStateList[switchIndex][iterator] )

                if deleteRule:
                    #Create and send OF message to delete the rule
                    msg = of.ofp_flow_mod()
                    msg.command = of.OFPFC_DELETE
                    msg.match.dl_type = 0x800 # IPv4 message
                    msg.match.nw_proto = 6 # TCP rules
                    msg.match.nw_src = IPAddr( flowTableList[switchIndex][iterator][0] )
                    msg.match.tp_src = int( flowTableList[switchIndex][iterator][1] )
                    msg.match.nw_dst = IPAddr( flowTableList[switchIndex][iterator][2] )
                    msg.match.tp_dst = int( flowTableList[switchIndex][iterator][3] )

                    event.connection.send(msg)

                    #print("========== Rule deleted ==========")

            #Update the respective base time
            baseTimeList[switchIndex] += PARAM_deletionInterval
        

    #Do not need to delete rules in the control tables and switches for tables that have been just added
    #Therefore the identation above is inside the else command

   

def readMarkovChain( markovChainName ):
    global markovChain

    file = open("ext/markov_chains/"+markovChainName, "r")

    line = file.readline()

    while line != "":
        markovChain.append( float(line) )

        line = file.readline()

    file.close()

    print markovChain


def applyFullTableMode( switchIndex, localEvent ):

    IP_SRC = 0
    TP_SRC = 1
    IP_DST = 2
    TP_DST = 3

    global flowMarkovStateList

    #Look for a rule (the one that has the highest finishing probability) to delete
    iterator = 0
    mostProbableIndex = 0
    mostProbableState = 0

    for ruleState in flowMarkovStateList[switchIndex]:
        if ruleState > mostProbableState:
            mostProbableState = ruleState
            mostProbableIndex = iterator

        iterator += 1

    #print("MARKOV MODULE: Rule " + str(mostProbableIndex) + " will be deleted.")

    #Get the rule data
    ruleData = flowTableList[switchIndex][mostProbableIndex]
    #print("MARKOV MODULE: Rule data - " + str(ruleData))

    #Necessary to not interfere in the deletion process
    flowMarkovStateList[switchIndex][mostProbableIndex] = -2

    #Create and send OF message to delete the rule
    msg = of.ofp_flow_mod()
    msg.command = of.OFPFC_DELETE
    msg.match.dl_type = 0x800 # IPv4 message
    msg.match.nw_proto = 6 # TCP rules
    msg.match.nw_src = IPAddr( ruleData[IP_SRC] )
    msg.match.tp_src = int( ruleData[TP_SRC] )
    msg.match.nw_dst = IPAddr( ruleData[IP_DST] )
    msg.match.tp_dst = int( ruleData[TP_DST] )

    localEvent.connection.send( msg )


def _handle_occup_packetIn(event):

    #print("MARKOV MODULE: Packet in.")
   
    switchIndex = -1

    try:
        switchIndex = switchList.index( str(event.connection.dpid) )
    except:
        print("MARKOV MODULE: Table empty.")

    if switchIndex != -1:

        #print("MARKOV MODULE: Switch " + str(event.connection.dpid) + " Table occupancy " + \
        #      str( len(flowTableList[switchIndex]) ) + " Table size: " + str(PARAM_tableSize))

        if( len(flowTableList[switchIndex]) >= PARAM_tableSize ):

            #Apply full table operation mode
            #print("MARKOV MODULE: Will apply full table mode.")
            applyFullTableMode( switchIndex, event )
            applyFullTableMode( switchIndex, event )


def launch(markovChainName, deletionInterval, tableSize):
    #print("Apply the Markov deletion model")

    global PARAM_deletionInterval
    global PARAM_tableSize
    PARAM_deletionInterval = deletionInterval
    PARAM_tableSize = int(tableSize)

    #Read the Markov chain
    readMarkovChain( str(markovChainName) )
    random.seed()

    #Attach handlers to listeners
    core.openflow.addListenerByName("FlowStatsReceived",
      _handle_delstats_received)

    core.openflow.addListenerByName("PacketIn",
      _handle_occup_packetIn)
