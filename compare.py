from ntpath import join
import os
import re
from subprocess import Popen
import time
import json
import sys

from pyrsistent import thaw

# This file has been tested on Linux and DCS(not batch)
# Operation on windows and macOS is unknown
#
# A file for the batch compute may be provided whenever I can be bothered
#
# Operation with the batch compute system is unknown
#
# This is provided with no guarantees of accuracy. Always verify data for yourself
# 
# Note past runs may be on different circumstances e.g (battery/wall power or number of chrome tabs open) 
# so historic results may not be reliable.
#
# I hope this helps you and good luck with the CW



# Configuration values

SAVETO = "./Past"                       #File to save JSON calculations to
PROGRAM_DIRECTORY="./main"              #Directory of the files (make, acacgs.....)

MAKE = True                             # Should the make command be run (clean then make)
RUNNING_PROGRAM=True                    # Should the program run acacgs
RUN_COUNT=5                             # Number of times to run the program
ARGS= ["100","100","100"]                  # program args

FILES_TO_AVERAGE = 1                    # If not running program how many files are there
REMOVE_OUTLIERS=True                    # Should outliers be removed (largest+smallest) this is how the submissions will be marked
                                        # NOTE the number of files being compared must be >= 3 if set

TIME_FOCUS="time-total"                 # When removing outliers how should largest/smallest be judged
#TIME_FOCUS="time-ddot"
#TIME_FOCUS="time-waxpy"
#TIME_FOCUS="time-sparsemv"


#Are there any other files that should be included in the results
OTHER_FILES=[]
# OF the previous runs (stored as dates) how many should be shown (dated files are ordered and last n shown)
DISPLAY_LAST=2




# Given a string from the file get data as a string
def getDataStr(row):
    row=row.rstrip()
    data= row.split(":")[1]
    data= data.lstrip()
    data= data.replace(" ","-")
    return data

# Given a string from the file get data as a float
def getDataFloat(row):
    row=row.rstrip()
    data= row.split(":")[1]
    data= data.lstrip()
    data=data.split(" ")[0]
    return float(data)

def getDataFloatEq(row):
    row=row.rstrip()
    data= row.split("=")[1]
    data= data.lstrip()
    data=data.split(" ")[0]
    return float(data)


#given an array of file paths return a dictionary of the average times
#and config values
# The dimension for all the files must be the same
# The final-residual for all files must be the same

# If REMOVE_OUTLIERS is true the smallest and larget will be removed
def calcAverage(files):
    dicts=list(map(lambda x:fileToDict(x),files))
    dicts.sort(key = lambda x:x[TIME_FOCUS])

    if REMOVE_OUTLIERS:
        dicts= dicts[1:]
        dicts= dicts[:-1]
    if len(dicts) ==0:
        raise ValueError(" There were not enough files to compare")
    
    average={}
    for i in dicts[0]:
        average[i]=dicts[0][i]
    for i in dicts[1:]:
        if i["dimensions"] != average["dimensions"]:            # Sanity check
            raise ValueError("Dimensions must match")
        if i["difference"] != average["difference"]:    # Check there is no random number generator
            raise ValueError("differences must match (identical runs produce identical results)")

        average["time-total"] += i["time-total"]
        average["time-ddot"] += i["time-ddot"]
        average["time-waxpy"] += i["time-waxpy"]
        average["time-sparsemv"] += i["time-sparsemv"]

    average["time-total"] = round(average["time-total"] / len(dicts),6)
    average["time-ddot"] = round(average["time-ddot"] / len(dicts),6)
    average["time-waxpy"] = round(average["time-waxpy"] / len(dicts),6)
    average["time-sparsemv"] = round(average["time-sparsemv"] / len(dicts),6)

    if average["difference"] > 1e-14:
        print("##################################################################")
        print("##################################################################")
        print("WARNING: difference between solution and exact is > 1e-14")
        print("##################################################################")
        print("##################################################################")

    return(average)
    

# Runs acacgs in directory RUN_COUNT times
# Returns the files produces
# Note directory ./ 
def runMany(directory):
    if REMOVE_OUTLIERS and RUN_COUNT <=2:
        raise ValueError("cannot find the mean of 0 values")
    if MAKE:
        os.system(f"cd {directory} && make clean")
        os.system(f"cd {directory} && make")
    for _ in range(0,RUN_COUNT):
        start=time.time()
        p1=Popen([f"{directory}/acacgs"]+ARGS)
        p1.wait()
        end=time.time()
        totalTime=end-start
        if totalTime<1.2: #Hacky solution to prevent two files having the same name
            time.sleep(1.2-totalTime)
    files =findDated("./",RUN_COUNT,"txt")
    return files


# Finds all files adhering to the date format with extention (.txt /.json)
# count-> get the last n files by date order
def findDated(directory,count,extention):
    regexp=f"[0-9]{{4}}(_[0-9]{{2}}){{5}}.{extention}"
    all_files = os.listdir(directory)
    txt_files= list(filter(lambda x:x.endswith(f".{extention}"),all_files))
    dated_files= list(filter(lambda x:re.fullmatch(regexp,x),txt_files))
    dated_files.sort()
    dated_files=dated_files[-count:]
    if count<=0:
        dated_files=[]
    return dated_files

#gets the last json files, reads all files then sorts them by the internal date
def findLastJSON(directory,count):
    all_files = os.listdir(directory)
    JSON_files= list(filter(lambda x:x.endswith(f".json"),all_files))
    files=[]
    for i in JSON_files:
        with open(f"{directory}/{i}") as file:
            values = json.load(file)
            files.append( (i,values["date"]) )
    files.sort(key= lambda x:x[1])
    files=files[-count:]
    if count<=0:
        files=[]
    return list(map(lambda x:x[0],files))

# Converts an output file provided by the acags to a dictionary 
def fileToDict(filePath):
    values={}
    with open(filePath) as file:
        data=file.readlines()

        values["title"] = filePath.replace(".txt","").replace(".",".")
        values["date"] = filePath.replace(".txt","").replace(".",".")
        values["alt"]= ""
        values["dimensions"] = getDataStr(data[3])
        values["difference"] = getDataFloatEq(data[25])
        values["time-total"] = getDataFloat(data[8])
        values["time-ddot"] = getDataFloat(data[9])
        values["time-waxpy"] = getDataFloat(data[10])
        values["time-sparsemv"] = getDataFloat(data[11])
    return values

# Takes a dictioary and creates a json dump with the file name
def createSaveFile(values):
    data = json.dumps(values)
    filename= f"{SAVETO}/{values['title']}.json"
    with open(filename,"w+") as file:
        file.write(data)

# Remove temporary files
def removeFiles(files):
    for i in files:
        os.remove(i)

# Read the first line from BRANCH.txt
def getBranchName(path):
    try:
        with open(f"{path}/BRANCH.txt") as file:
            line=file.readline()
            line=line.rstrip()
        return line
    except FileNotFoundError:
        return ""

# Display Data to the terminals
def showFiles():
    all_files = os.listdir(SAVETO)
    json_files= list(filter(lambda x:x.endswith(".json"),all_files))
    dated_files=findLastJSON(SAVETO,DISPLAY_LAST)
    selected_files= list(filter(lambda x:x in OTHER_FILES,json_files))
    selected_files.sort(key=lambda x:OTHER_FILES.index(x))

    filesData={}
    for i in selected_files+dated_files:
        with open(f"{SAVETO}/{i}") as file:
            values = json.load(file)
            if values["dimensions"] in filesData: 
                filesData[values["dimensions"]].append(values)
            else:
                filesData[values["dimensions"]]=[values]

    for i in filesData:
        print(f"Data on dimensions: {i}")
        rows=["            ","            ","difference:","Total      :","ddot       :","wxapy      :","sparsemv   :"]
        c=0
        b=[]
        for j in filesData[i]:
            if c==0:
                rows[0] += "{:<25}".format(j["alt"]) 
                rows[1] += "{:<25}".format(j["title"]) 
                rows[2] += "{:<25}".format(j["difference"]) 
                rows[3] += "{:<25}".format(j["time-total"])
                rows[4] += "{:<25}".format(j["time-ddot"])
                rows[5] += "{:<25}".format(j["time-waxpy"])
                rows[6] += "{:<25}".format(j["time-sparsemv"])
                b=j
            else:
                rows[0] += "{:<25}".format(j["alt"]) 
                rows[1] += "{:<25}".format(j["title"]) 
                identical="Y" if b['difference']==j['difference'] else "N"
                rows[2] += '{:<25}'.format(f"{j['difference']}({ identical})")
                speedup=(b['time-total']/j['time-total'])
                rows[3] += '{:<25}'.format(f"{j['time-total']}({ speedup:5.3f}x)")
                speedup=(b['time-ddot']/j['time-ddot'])
                rows[4] += '{:<25}'.format(f"{j['time-ddot']}({ speedup:5.3f}x)")
                speedup=(b['time-waxpy']/j['time-waxpy'])
                rows[5] += '{:<25}'.format(f"{j['time-waxpy']}({ speedup:5.3f}x)")
                speedup=(b['time-sparsemv']/j['time-sparsemv'])
                rows[6] += '{:<25}'.format(f"{j['time-sparsemv']}({ speedup:5.3f}x)")
            c+=1


        for i in rows:
            print(i)

def combine():
    all_files = os.listdir(SAVETO)
    txt_files= list(filter(lambda x:x.endswith(f".json"),all_files))
    data=[]
    for i in txt_files:
        with open(f"{SAVETO}/{i}") as file:
            values = json.load(file)
            data.append(values)
    with open(f"combined.json","w+") as file:
        values=json.dump(data,file)

def pHelp():
    print("This is the help page")
    print("""
    ==================================================
    Arguments
    -h -help --help The help page
    -com            Runs a standard benchmark un-altered 
    -n <name>       Adds a name to the run for easier comparison, default: time
    -c              Combines all the existing json files into one, IDK maybe usefull
    ==================================================
    For other settings see the constants at the top of the python file
    """)

if "-c" in sys.argv:
    combine()
if "-h" in sys.argv or "-help" in sys.argv or "--help" in sys.argv:
    pHelp()
    exit()
else:
    title=""
    if "-n" in sys.argv:
        loc=sys.argv.index("-n")
        if len(sys.argv) > loc+1:
            title=sys.argv[loc+1]
        else:
            pHelp()
            exit()
    #Paramaters for the agreed comparision benchmark
    if "-com" in sys.argv:
        print("Cult Of Matt standard benchmark")
        RUNNING_PROGRAM=True                    # Should the program run acacgs
        RUN_COUNT=5                             # Number of times to run the program
        ARGS= ["200","200","200"]                  # program args
        FILES_TO_AVERAGE = 5                    # If not running program how many files are there
        REMOVE_OUTLIERS=True                    # Should outliers be removed (largest+smallest) this is how the submissions will be marked
                                                # NOTE the number of files being compared must be >= 3 if set
        TIME_FOCUS="time-total"  

    if RUNNING_PROGRAM:
        files=runMany(PROGRAM_DIRECTORY)
        average=calcAverage(files)
        brachName=getBranchName(PROGRAM_DIRECTORY)
        average["alt"]=brachName
        average["title"] = title if title !="" else average["title"]
        print(f"title :{ average['title'] }")
        createSaveFile(average)
        removeFiles(files)
        showFiles()
    else:
        files =findDated(PROGRAM_DIRECTORY,FILES_TO_AVERAGE,"txt")
        average=calcAverage(files)
        brachName=getBranchName(PROGRAM_DIRECTORY)
        average["alt"]=brachName
        average["title"] = title if title !="" else average["title"]
        createSaveFile(average)
        showFiles()
