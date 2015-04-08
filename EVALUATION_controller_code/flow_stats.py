
from pox.core import core
import pox.openflow.libopenflow_01 as of

from pox.openflow.of_json import *
import time
import threading

startTime = time.time()

switchList = []
flowTableSizeLog = []
logTimesList = []

tableSizeLock = threading.Lock()

log = core.getLogger()


def writeFlowTableSizeLog( switch, switchIndex ):
    global switchList
    global flowTableSizeLog
    global logTimesList

    file = open( "ext/CMP182_project_logs/flow_table_size/switch"+switch+".txt", "a" )

    #Write all elements in the log list except the last
    for iterator in range(0, len(flowTableSizeLog[switchIndex])-1 ):
        file.write( str(logTimesList[switchIndex][iterator])+"	"+
          str(flowTableSizeLog[switchIndex][iterator])+"\n" )

    iterator = len( flowTableSizeLog[switchIndex] ) - 2

    while(iterator >= 0):
        flowTableSizeLog[switchIndex][iterator] = -1
        flowTableSizeLog[switchIndex].remove( -1 )

        logTimesList[switchIndex][iterator] = -1
        logTimesList[switchIndex].remove( -1 )

        iterator -= 1

    file.close()


#Get flow statistics from each switch in the network
def _get_stat():
    for connection in core.openflow._connections.values():
        connection.send(of.ofp_stats_request( body=of.ofp_flow_stats_request() ))    
    
    #log.debug("Sent %i flow stats request(s)", len(core.openflow._connections))


#Handler to display flow statistics received in JSON format
def _handle_flowstats_received(event):

    global switchList
    global flowTableSizeLog
    global logTimesList
    global startTime

    stats = flow_stats_to_list(event.stats)

    #log.debug("FlowStatsReceived from %s: %s", 
    #  str(event.connection.dpid), stats)

    log.debug("Flow stats received from %s", str(event.connection.dpid))
    #log.debug("Number of rules: %s", str( len(stats) ))

    #Update the respective list for each stat received
    try:
        switch = str( event.connection.dpid )
        switchIndex = switchList.index( switch )

        #file = open( "ext/CMP182_project_logs/flow_table_size/table_"+switch+"_log.txt", "a" )
        #file.write( str(stats) )
        #file.write( "\n-------------------------------------------------------------\n\n\n" )
        #file.write( str(len(stats)) )
        #file.close()

        flowTableSizeLog[switchIndex].append( int( len(stats) ) )

        currentTime = time.time() - startTime
        logTimesList[switchIndex].append( currentTime )

        #Write part of the list in the log file
        if( len( flowTableSizeLog[switchIndex] ) > 10 ):
            #print("----- Will write logs -----")
            writeFlowTableSizeLog( switch, switchIndex )

    except:
        #Initialize log structures for new switches
        switchList.append( switch )
        flowTableSizeLog.append( [] )
        logTimesList.append( [] )



#Main function to launch the module
def launch(getStatInterval=5):
    from pox.lib.recoco import Timer

    global startTime
    startTime = time.time()

    #Attach handlers to listeners
    core.openflow.addListenerByName("FlowStatsReceived", 
      _handle_flowstats_received)

    #Timer
    Timer( int(getStatInterval), _get_stat, recurring=True )
