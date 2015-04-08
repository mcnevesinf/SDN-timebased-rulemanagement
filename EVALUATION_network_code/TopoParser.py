
def parseTopo(fileName, hosts, switches, links):
    
    filePointer = open( "topo/"+fileName, "r" )

    line = filePointer.readline()
   
    while len(line) != 0:
        if line.find("START_HOST") != -1:
            
            #Read hosts
            line = filePointer.readline()
            
            while line.find("END_HOST") == -1:
                line = line[:-1]
                hosts.append( line )
                line = filePointer.readline()

        else:
            if line.find("START_SWITCH") != -1:
                
                #Read switches
                line = filePointer.readline()

                while line.find("END_SWITCH") == -1:
                    line = line[:-1]
                    switches.append( line )
                    line = filePointer.readline()
            
            else:
                if line.find("START_LINK") != -1:
                
                    #Read links
                    line = filePointer.readline()

                    while line.find("END_LINK") == -1:
                        line = line[:-1]
                        links.append( line.split(" ") )
                        line = filePointer.readline() 

        line = filePointer.readline()

    filePointer.close()
