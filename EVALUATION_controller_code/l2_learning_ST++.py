# Copyright 2011 James McCauley
#
# This file is part of POX.
#
# POX is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# POX is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with POX.  If not, see <http://www.gnu.org/licenses/>.

"""
This is an L2 learning switch written directly against the OpenFlow library.
It is derived from one written live for an SDN crash course.
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.revent import *
from pox.lib.util import dpidToStr
from pox.lib.util import str_to_bool
import pox.lib.packet as pkt
from pox.lib.addresses import IPAddr

from pox.openflow.of_json import *
import time
import random

import threading

log = core.getLogger()

# We don't want to flood immediately when a switch connects.
FLOOD_DELAY = 5

startTime = time.time()
switchList = []
flowTableList = []
flowTableOccupancyList = []

PARAM_idleTime = 0
PARAM_getStatInterval = 0
PARAM_simulationTime = 0
PARAM_tableSize = 0


#-----------------------------------------------------------
#	SMART_TIME parameters
#-----------------------------------------------------------
PARAM_smartTimeModule = ""
PARAM_smartTimeMinIdleTimeout = 0 
PARAM_smartTimeMaxIdleTimeout = 0
PARAM_smartTimeTableUtilization = 0.0
PARAM_smartTimeIncreaseFunction = ""


#-----------------------------------------------------------
#       FLOW_MASTER parameters
#-----------------------------------------------------------
PARAM_markovModule = ""

class LearningSwitch (EventMixin):
  """
  The learning switch "brain" associated with a single OpenFlow switch.

  When we see a packet, we'd like to output it on a port which will
  eventually lead to the destination.  To accomplish this, we build a
  table that maps addresses to ports.

  We populate the table by observing traffic.  When we see a packet
  from some source coming from some port, we know that source is out
  that port.

  When we want to forward traffic, we look up the desintation in our
  table.  If we don't know the port, we simply send the message out
  all ports except the one it came in on.  (In the presence of loops,
  this is bad!).

  In short, our algorithm looks like this:

  For each new flow:
  1) Use source address and port to update address/port table
  2) Is destination address a Bridge Filtered address, or is Ethertpe LLDP?
     * This step is ignored if transparent = True *
     Yes:
        2a) Drop packet to avoid forwarding link-local traffic (LLDP, 802.1x)
            DONE
  3) Is destination multicast?
     Yes:
        3a) Flood the packet
            DONE
  4) Port for destination address in our address/port table?
     No:
        4a) Flood the packet
            DONE
  5) Is output port the same as input port?
     Yes:
        5a) Drop packet and similar ones for a while
  6) Install flow table entry in the switch so that this
     flow goes out the appopriate port
     6a) Send buffered packet out appopriate port
  """
  def __init__ (self, connection, transparent):

    # Switch we'll be adding L2 learning switch capabilities to
    self.connection = connection
    self.transparent = transparent

    # Our table
    self.macToPort = {}

    self.knownFlows = [] #Control flows that have already been sent
    self.reinstalledRules = []
    self.reinstalledRulesWriten = False


    #-------------------------------------------------------------
    #        SMART_TIME - Control structures
    #-------------------------------------------------------------
    self.SMART_TIME_controlStruct = []


    # We want to hear PacketIn messages, so we listen
    self.listenTo(connection)

    #log.debug("Initializing LearningSwitch, transparent=%s",
    #          str(self.transparent))



  #---------------------------------------------------------------
  #          SMART_TIME - Update control structure
  #---------------------------------------------------------------
  def _handle_FlowRemoved(self, event):
    #print("Flow removed from switch " + str(event.dpid) + str(self.connection.dpid))
    #print("Live time: " + str(event.ofp.duration_sec))
    #print("Flow match: " + str(event.ofp.match))

    #if event.ofp.reason == 0:
    #    print("MAIN MODULE: Timeout.")
    #elif event.ofp.reason == 2:
    #    print("MAIN MODULE: Deleted.")


    #Extract the flow data from the switch message
    messageData = []
    messageData.append( str(event.ofp.match.nw_src) )
    messageData.append( str(event.ofp.match.tp_src) )
    messageData.append( str(event.ofp.match.nw_dst) )
    messageData.append( str(event.ofp.match.tp_dst) )

    #Look for the flow in the SmartTime control structure
    flowIndex = -1

    if len(self.SMART_TIME_controlStruct) > 0:
        iterator = 0
        indexNotFound = True
        #print(self.knownFlows[0])
        while iterator < len(self.SMART_TIME_controlStruct) and indexNotFound:
            if messageData[0] == self.SMART_TIME_controlStruct[iterator][0] and \
               messageData[1] == self.SMART_TIME_controlStruct[iterator][1] and \
               messageData[2] == self.SMART_TIME_controlStruct[iterator][2] and \
               messageData[3] == self.SMART_TIME_controlStruct[iterator][3]:
                flowIndex = iterator
                indexNotFound = False

            iterator += 1

    #print("FLOW REMOVAL: " + str(flowIndex))
  
    #Update the average hold time
    if flowIndex != -1:
        liveTime = float(event.ofp.duration_sec)

        if(liveTime == 0.0):
            liveTime = 0.1

        idleTime = self.SMART_TIME_controlStruct[flowIndex][6]

        newAvgHoldTime = float( (liveTime + idleTime) ) / float(liveTime)

        self.SMART_TIME_controlStruct[flowIndex][5] = newAvgHoldTime
   

  def _handle_PacketIn (self, event):
    """
    Handles packet in messages from the switch to implement above algorithm.
    """

    packet = event.parse()

    def flood ():
      """ Floods the packet """
      if event.ofp.buffer_id == -1:
        log.warning("Not flooding unbuffered packet on %s",
                    dpidToStr(event.dpid))
        return
      msg = of.ofp_packet_out()
      if time.time() - self.connection.connect_time > FLOOD_DELAY:
        # Only flood if we've been connected for a little while...
        #log.debug("%i: flood %s -> %s", event.dpid, packet.src, packet.dst)
        msg.actions.append(of.ofp_action_output(port = of.OFPP_FLOOD))
      else:
        pass
        #log.info("Holding down flood for %s", dpidToStr(event.dpid))
      msg.buffer_id = event.ofp.buffer_id
      msg.in_port = event.port
      self.connection.send(msg)

    def drop (duration = None):
      """
      Drops this packet and optionally installs a flow to continue
      dropping similar ones for a while
      """
      if duration is not None:
        if not isinstance(duration, tuple):
          duration = (duration,duration)
        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet)
        msg.idle_timeout = duration[0]
        msg.hard_timeout = duration[1]
        msg.buffer_id = event.ofp.buffer_id
        self.connection.send(msg)
      elif event.ofp.buffer_id != -1:
        msg = of.ofp_packet_out()
        msg.buffer_id = event.ofp.buffer_id
        msg.in_port = event.port
        self.connection.send(msg)


    def getFlowData( packet ):
        flowData = []

        IPpacket = packet.find("ipv4")
        TCPpacket = packet.find("tcp")

        if IPpacket is None or TCPpacket is None:
            return None #This packet is not TCP over IP

        flowData.append( str(IPpacket.srcip) )
        flowData.append( str(TCPpacket.srcport) )
        flowData.append( str(IPpacket.dstip) )
        flowData.append( str(TCPpacket.dstport) )

        return flowData


    def writeReinstalledRules( switchID ):
        fileName = "ext/CMP182_project_logs/reinstallations/switch"+switchID+".txt"

        file = open( fileName, "w" )

        iterator = 0

        #time.sleep(3)

        while iterator < len( self.knownFlows ):
            file.write( self.knownFlows[iterator][0]+"	"+
                        self.knownFlows[iterator][1]+"	"+
                        self.knownFlows[iterator][2]+"	"+
                        self.knownFlows[iterator][3]+"	"+
                        str(self.reinstalledRules[iterator])+"\n" )

            iterator += 1

        file.close()


    def getFlowIndex( flowData ):
        flowIndex = -1

        #print("==================="+str(len(self.knownFlows)))

        if len(self.knownFlows) > 0:
            iterator = 0
            indexNotFound = True
            #print(self.knownFlows[0])
            while iterator < len(self.knownFlows) and indexNotFound:
                if flowData[0] == self.knownFlows[iterator][0] and \
                   flowData[1] == self.knownFlows[iterator][1] and \
                   flowData[2] == self.knownFlows[iterator][2] and \
                   flowData[3] == self.knownFlows[iterator][3]:
                    flowIndex = iterator
                    indexNotFound = False

                iterator += 1

        return flowIndex



    def SMART_TIME_getFlowIndex( SMART_TIME_flowData ):
        flowIndex = -1

        if len(self.SMART_TIME_controlStruct) > 0:
            iterator = 0
            indexNotFound = True
            #print(self.knownFlows[0])
            while iterator < len(self.SMART_TIME_controlStruct) and indexNotFound:
                if SMART_TIME_flowData[0] == self.SMART_TIME_controlStruct[iterator][0] and \
                   SMART_TIME_flowData[1] == self.SMART_TIME_controlStruct[iterator][1] and \
                   SMART_TIME_flowData[2] == self.SMART_TIME_controlStruct[iterator][2] and \
                   SMART_TIME_flowData[3] == self.SMART_TIME_controlStruct[iterator][3]:
                    flowIndex = iterator
                    indexNotFound = False

                iterator += 1

        return flowIndex



    def SMART_TIME_getIdleTime( SMART_TIME_flowData, localEvent ):
        
        REPEAT_COUNT_POS = 4
        HOLD_FACTOR_POS = 5
        PREVIOUS_TIMEOUT_POS = 6

        idleTime = 0

        #Identify the flow in the SmartTime control structure
        SMART_TIME_flowIndex = SMART_TIME_getFlowIndex( SMART_TIME_flowData )

        #IF the flow was never installed THEN insert it into the SmartTime control structure
        if SMART_TIME_flowIndex == -1:
            #print("SMART_TIME: Flow never installed.")

            SMART_TIME_flowData.append( 0 ) #Initial repeat count
            SMART_TIME_flowData.append( 1.0 )  #Initial hold factor
            SMART_TIME_flowData.append( 1 ) #Initial previous idle timeout

            self.SMART_TIME_controlStruct.append( SMART_TIME_flowData )
            SMART_TIME_flowIndex = len( self.SMART_TIME_controlStruct ) - 1
        
            idleTime = PARAM_smartTimeMinIdleTimeout 

        #ELSE apply the timeout increasing function
        else:
            previousRepeatCount = self.SMART_TIME_controlStruct[SMART_TIME_flowIndex][REPEAT_COUNT_POS]
            self.SMART_TIME_controlStruct[SMART_TIME_flowIndex][REPEAT_COUNT_POS] += 1

            if PARAM_smartTimeIncreaseFunction == "EXPONENTIAL":
                previousIdleTimeout = PARAM_smartTimeMinIdleTimeout * pow(2, previousRepeatCount)
            elif PARAM_smartTimeIncreaseFunction == "QUADRATIC":
                previousIdleTimeout = PARAM_smartTimeMinIdleTimeout * pow(previousRepeatCount, 2)
            elif PARAM_smartTimeIncreaseFunction == "LINEAR":
                previousIdleTimeout = PARAM_smartTimeMinIdleTimeout * previousRepeatCount

            if previousIdleTimeout >= PARAM_smartTimeMaxIdleTimeout and \
               self.SMART_TIME_controlStruct[SMART_TIME_flowIndex][HOLD_FACTOR_POS] > 3.0:
                idleTime = PARAM_smartTimeMinIdleTimeout
            elif previousIdleTimeout >= PARAM_smartTimeMaxIdleTimeout:
                idleTime = PARAM_smartTimeMaxIdleTimeout
            else:
              
                if PARAM_smartTimeIncreaseFunction == "EXPONENTIAL":
                    #print("SMART TIME MODULE: Timeout exponential increase.")
                    idleTime = PARAM_smartTimeMinIdleTimeout * pow(2, self.SMART_TIME_controlStruct[SMART_TIME_flowIndex][REPEAT_COUNT_POS])
                elif PARAM_smartTimeIncreaseFunction == "QUADRATIC":
                    #print("SMART TIME MODULE: Timeout quadratic increase.")
                    idleTime = PARAM_smartTimeMinIdleTimeout * pow( self.SMART_TIME_controlStruct[SMART_TIME_flowIndex][REPEAT_COUNT_POS], 2 )
                elif PARAM_smartTimeIncreaseFunction == "LINEAR":
                    #print("SMART TIME MODULE: Timeout linear increase.")
                    idleTime = PARAM_smartTimeMinIdleTimeout * self.SMART_TIME_controlStruct[SMART_TIME_flowIndex][REPEAT_COUNT_POS]


            #IF the table utilization is greater than the established limit THEN randomly remove an entry
            SMART_TIME_switchIndex = -1

            try:
                SMART_TIME_switchIndex = switchList.index( str(localEvent.connection.dpid) )
            except:
                print("SMART TIME MODULE: Error - Switch not found.")

            #print("SMART_TIME MODULE: Switch " + str(localEvent.connection.dpid) + " Table occupancy " + \
              #str(flowTableOccupancyList[SMART_TIME_switchIndex]) + " Table size: " + str(PARAM_tableSize))

            if ( (flowTableOccupancyList[SMART_TIME_switchIndex] / PARAM_tableSize)*100 ) >= PARAM_smartTimeTableUtilization:
                #print("SMART TIME MODULE: Will limit the table utilization.")
                applyFullTableMode( "RANDOM", SMART_TIME_switchIndex, localEvent )

            #The new idle timeout will be the previous one in the next time
            self.SMART_TIME_controlStruct[SMART_TIME_flowIndex][PREVIOUS_TIMEOUT_POS] = idleTime

        return idleTime




    def applyFullTableMode( mode, switchIndex, localEvent ):

        selectedRule = -1
        ruleData = []

        IP_SRC = 0
        TP_SRC = 1
        IP_DST = 2
        TP_DST = 3

        REPEAT_COUNT_POS = 4

        while len(ruleData) != 4:

            if mode == "RANDOM":

                #Select a rule to be deleted
                selectedRule = random.randrange(0, len(flowTableList[switchIndex]))


            #Get the rule data
            try:
                ruleData.append( str(flowTableList[switchIndex][selectedRule]['match']['nw_src']) )
                ruleData.append( str(flowTableList[switchIndex][selectedRule]['match']['tp_src']) )
                ruleData.append( str(flowTableList[switchIndex][selectedRule]['match']['nw_dst']) )
                ruleData.append( str(flowTableList[switchIndex][selectedRule]['match']['tp_dst']) )
            except:
                #Not a flow rule
                ruleData = []


        #IF applying SMART_TIME THEN do not increase the idle time when deleting a rule (done just when the timeout expires)
        if PARAM_smartTimeModule == "True":

            #print("SMART TIME MODULE: Table full. Exclude a flow but does not increase its reinstallation counter.")

            SMART_TIME_flowIndex = SMART_TIME_getFlowIndex( ruleData )
            #print("Flow: " + str(SMART_TIME_flowIndex) + " Counter before: " + str(self.SMART_TIME_controlStruct[SMART_TIME_flowIndex][REPEAT_COUNT_POS]))

            #IF the flow timeout is not the minimum possible yet THEN reduce the flow reinstallation counter to update it when reinstalling the flow
            if self.SMART_TIME_controlStruct[SMART_TIME_flowIndex][REPEAT_COUNT_POS] > 0:
                self.SMART_TIME_controlStruct[SMART_TIME_flowIndex][REPEAT_COUNT_POS] -= 1

            #print("Flow: " + str(SMART_TIME_flowIndex) + " Counter then: " + str(self.SMART_TIME_controlStruct[SMART_TIME_flowIndex][REPEAT_COUNT_POS]))

        #print("FULL TABLE MODE: Selected rule " + str(selectedRule))
        #print("FULL TABLE MODE: Rule data " + str(ruleData))
        
        #Create and send OF message to delete the rule
        msg = of.ofp_flow_mod()
        msg.command = of.OFPFC_DELETE
        msg.match.dl_type = 0x800 # IPv4 message
        msg.match.nw_proto = 6 # TCP rules
        msg.match.nw_src = IPAddr( ruleData[IP_SRC] )
        msg.match.tp_src = int( ruleData[TP_SRC] )
        msg.match.nw_dst = IPAddr( ruleData[IP_DST] )
        msg.match.tp_dst = int( ruleData[TP_DST] )

        #print(str(msg.match))

        localEvent.connection.send( msg )



    self.macToPort[packet.src] = event.port # 1

    if not self.transparent:
      if packet.type == packet.LLDP_TYPE or packet.dst.isBridgeFiltered(): # 2
        drop()
        return

    if packet.dst.isMulticast():
      flood() # 3a
    else:
      if packet.dst not in self.macToPort: # 4
        log.debug("Port for %s unknown -- flooding" % (packet.dst,))
        flood() # 4a
      else:
        port = self.macToPort[packet.dst]
        if port == event.port: # 5
          # 5a
          log.warning("Same port for packet from %s -> %s on %s.  Drop." %
                      (packet.src, packet.dst, port), dpidToStr(event.dpid))
          drop(10)
          return
        # 6
        #log.debug("installing flow for %s.%i -> %s.%i" %
        #          (packet.src, event.port, packet.dst, port))

        msg = of.ofp_flow_mod()
        msg.match = of.ofp_match.from_packet(packet)

        #print(str(of.ofp_match.from_packet(packet)))

        #IF applying SMART_TIME THEN calculate specific idle timeout
        if PARAM_smartTimeModule == "True":
            #print("Calculate SmartTime idle time...")

            SMART_TIME_flowData = getFlowData( packet )

            if SMART_TIME_flowData is not None:            
                msg.idle_timeout = SMART_TIME_getIdleTime( SMART_TIME_flowData, event )
            else:
                msg.idle_timeout = int(PARAM_idleTime) #The rule does not represent a flow
        
            #APPLY FULL TABLE MODE
            switchIndex = -1

            try:
                switchIndex = switchList.index( str(event.connection.dpid) )
            except:
                print("MAIN MODULE: Error - Switch not found.")

            #print("SMART_TIME MODULE: Switch " + str(event.connection.dpid) + " Table occupancy " + \
              #str(flowTableOccupancyList[switchIndex]) + " Table size: " + str(PARAM_tableSize))

            #print(flowTableOccupancyList[switchIndex])
            #print(PARAM_tableSize)

            if flowTableOccupancyList[switchIndex] >= PARAM_tableSize:
                #print("SMART TIME MODULE: Will apply full table operation mode.")
                applyFullTableMode( "RANDOM", switchIndex, event )
                applyFullTableMode( "RANDOM", switchIndex, event )


        #ELSE use parameter timeout
        else:
            if PARAM_markovModule == "False":

                #Apply StaticTimeout full table mode deletion scheme
                switchIndex = -1

                try:
                    switchIndex = switchList.index( str(event.connection.dpid) )
                except:
                    print("MAIN MODULE: Error - Switch not found.")


                if flowTableOccupancyList[switchIndex] >= PARAM_tableSize:
                    #print("MAIN MODULE: Will apply full table mode.")
                    applyFullTableMode( "RANDOM", switchIndex, event )
                    applyFullTableMode( "RANDOM", switchIndex, event )

            msg.idle_timeout = int(PARAM_idleTime)


        #print("Timeout: " + str(msg.idle_timeout))
        #msg.hard_timeout = 30
        msg.hard_timeout = of.OFP_FLOW_PERMANENT
        msg.flags = of.OFPFF_SEND_FLOW_REM
        msg.actions.append(of.ofp_action_output(port = port))
        msg.buffer_id = event.ofp.buffer_id # 6a
        self.connection.send(msg)

        #---------------------------------------------------
        # Update the structure controlling reinstalled rules
        #---------------------------------------------------        

        #Get flow data
        flowData = getFlowData( packet )

        if flowData is not None and not self.reinstalledRulesWriten:
            #print("Flow data: "+ str(flowData))

            #flowIndex = self.knownFlows.index( flowData )
            flowIndex = getFlowIndex( flowData )

            if flowIndex != -1:
                #print("Will increment reinstalled rules")
                #print("Flow index: "+str(flowIndex))

                self.reinstalledRules[flowIndex] += 1
            else:
                self.knownFlows.append( flowData )
                self.reinstalledRules.append( 0 )


            elapsedTime = time.time() - startTime

            if not self.reinstalledRulesWriten and elapsedTime > float(PARAM_simulationTime):
                self.reinstalledRulesWriten = True
                writeReinstalledRules( str(event.dpid) )



class l2_learning (EventMixin):
  """
  Waits for OpenFlow switches to connect and makes them learning switches.
  """
  def __init__ (self, transparent):
    self.listenTo(core.openflow)

    self.transparent = transparent

  def _handle_ConnectionUp (self, event):
    log.debug("Connection %s" % (event.connection,))
    LearningSwitch(event.connection, self.transparent)

    #Initialize the structures that control the flow table size
    global switchList
    global flowTableList
    global flowTableOccupancyList

    switchList.append( str(event.connection.dpid) )
    print("MAIN MODULE: Switch" + str(event.connection.dpid) + " appended")
    flowTableList.append( {} )
    flowTableOccupancyList.append( 0 )



def _handle_tableSizeStats_received(event):
  #print("-------------- FLOW STATS RECEIVED IN THE MAIN MODULE -------------")

  stats = flow_stats_to_list(event.stats) #'stats' is a list of dictionaries.$
  #print(stats)

  #Identify the switch
  switchIndex = -1

  try:
      switchIndex = switchList.index( str(event.connection.dpid) )
  except:
      print("MAIN MODULE: Error - Switch not found.")

  #UPDATE THE FLOW TABLE SIZE OCCUPANCY STRUCTURE
  #print("MAIN MODULE: Switch index in table stats message - " + str(switchIndex))
  global flowTableList
  global flowTableOccupancyList

#  tableOccupancyLock.acquire()    
  flowTableList[switchIndex] = stats
  flowTableOccupancyList[switchIndex] = len( stats )
#  tableOccupancyLock.release()
  




def launch (transparent=False, idleTime = 10, getStatInterval = 2, simulationTime=60, tableSize=50, 
            markovModule="True", markovChain="defaultChain.txt", deletionInterval=2.0, smartTimeModule="False",
            smartTimeMinIdleTimeout=1, smartTimeMaxIdleTimeout=60, smartTimeTableUtilization=95, smartTimeIncreaseFunction="EXPONENTIAL"):
  """
  Starts an L2 learning switch.
  """

  random.seed()

  #print("Idle time: " + str(idleTime))
  global PARAM_idleTime
  global PARAM_getStatInterval
  global PARAM_simulationTime
  global PARAM_tableSize

  PARAM_idleTime = idleTime
  PARAM_getStatInterval = getStatInterval
  PARAM_simulationTime = simulationTime
  PARAM_tableSize = int(tableSize)

  print("MAIN MODULE: Table size = " + str(PARAM_tableSize))

  #Module to collect stats and update metrics
  from flow_stats import launch
  launch(getStatInterval)

  #Module to apply rule deletion according to a Markov model
  global PARAM_markovModule

  PARAM_markovModule = markovModule

  if PARAM_markovModule == "True":
      from markov_deletion import launch
      launch(markovChain, float(deletionInterval), int(tableSize))
      print("Markov deletion module is ON")
  else:
      print("Markov deletion module is OFF")


  #--------------------------------------------
  #               SMART_TIME
  #--------------------------------------------
  global PARAM_smartTimeModule
  global PARAM_smartTimeMinIdleTimeout
  global PARAM_smartTimeMaxIdleTimeout
  global PARAM_smartTimeTableUtilization
  global PARAM_smartTimeIncreaseFunction

  PARAM_smartTimeModule = smartTimeModule

  if PARAM_smartTimeModule == "True":
      PARAM_smartTimeMinIdleTimeout = int(smartTimeMinIdleTimeout)
      PARAM_smartTimeMaxIdleTimeout = int(smartTimeMaxIdleTimeout)
      PARAM_smartTimeTableUtilization = float(smartTimeTableUtilization)
      PARAM_smartTimeIncreaseFunction = smartTimeIncreaseFunction

      print("SmartTime module is ON")
      print("SmartTime - Min idle timeout: " + str(PARAM_smartTimeMinIdleTimeout))
      print("SmartTime - Max idle timeout: " + str(PARAM_smartTimeMaxIdleTimeout))
      print("SmartTime - Table utilization: " + str(PARAM_smartTimeTableUtilization))
      print("SmartTime - Increase function: " + str(PARAM_smartTimeIncreaseFunction))
  else:
      print("SmartTime module is OFF")

  core.registerNew(l2_learning, str_to_bool(transparent))

  #Attach handlers to listeners
  core.openflow.addListenerByName("FlowStatsReceived",
    _handle_tableSizeStats_received)
