# This is my simple script to grab the manifest from a BlackVue dash cam and then grab the files.
# DPC 220922
# DPC 280922 - Added looped checking for liveliness, improved manifest to create summary list

# Imports
import os
import shutil
import urllib3
import logging
import platform
import subprocess
import time
from datetime import datetime
from urllib3.util import Retry
from urllib3.util import Timeout
from urllib3.exceptions import MaxRetryError

# vars

blackvueHost = '10.100.0.121'
blackvueBase = 'http://' + blackvueHost + '/'
blackvueVOD = 'blackvue_vod.cgi'
recordingFolder = 'Recordings'
pidfile = 'pidfile.pid'
logfile = 'blackvuegrab.log'
pid = os.getpid()
pingspacer = 5
attempts = 0
innerattempts = 0
loopcounter = 0
timeoutspacer = 20
workingmanifest = []
manifest = []

# var expansion

def CreatePath(basefolder, file):
    CreatePathStep1 = os.path.join(basefolder, file)
    CreatePathStep2 = os.path.abspath(CreatePathStep1)
    return CreatePathStep2

def CreatePathFolder(basefolder, filenametofolder):
    CreatePathFolderStep1 = os.path.abspath(basefolder)
    CreatePathFolderStep2 = filenametofolder.replace('/Record/', '')
    ConvDate = datetime.strptime(CreatePathFolderStep2[0:8], '%Y%m%d').strftime('%Y_%m_%d')
    CreatePathFolderStep3 = os.path.join(CreatePathFolderStep1, ConvDate)
    if not os.path.exists(CreatePathFolderStep3):
        os.makedirs(CreatePathFolderStep3)
        LogFunc("Creating directory {}".format(CreatePathFolderStep3), 'info')
    elif os.path.exists(CreatePathFolderStep3):
        LogFunc("Directory exists {} using that".format(CreatePathFolderStep3), 'info')
    else:
        LogFunc("Hmm.. something went wrong", 'error')

def CreateFilePath(foldervar, filename):
    CreateFilePathStep1 = os.path.abspath(foldervar)
    CreateFilePathStep2 = filename.replace('/Record/', '')
    ConvDate = datetime.strptime(CreateFilePathStep2[0:8], '%Y%m%d').strftime('%Y_%m_%d')
    CreateFilePathStep3 = os.path.join(CreateFilePathStep1, ConvDate, CreateFilePathStep2)
    return CreateFilePathStep3

# Log defs

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', filename=logfile, level=logging.INFO)
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', filename=logfile, level=logging.DEBUG)
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', filename=logfile, level=logging.ERROR)
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', filename=logfile, level=logging.WARNING)

# We need to store the manifest of the files, as the server is slow and unrelliable

def PingTest(host, timeout, count):
    param1 = '-n' if platform.system().lower() == 'windows' else '-c'
    param2 = '-w' if platform.system().lower() == 'windows' else '-W'
    command = ['ping', param1, str(count), param2, str(timeout), host]
    return subprocess.call(command, stdout=subprocess.DEVNULL) == 0

def GetManifest():
    global workingmanifest
    http = urllib3.PoolManager()
    retry = Retry(5, raise_on_status=True, status_forcelist=(500, 600))
    urlparts = blackvueBase + blackvueVOD
    url = urlparts
    try:
        LogFunc("trying to get manifest from {}".format(url), 'info')
        geturldata = http.request('GET', url, retries=retry, timeout=20.00)
        workingmanifest = geturldata.data.decode('utf-8')
        LogFunc("I got the base manifest! from {}".format(url), 'info')
    except MaxRetryError as m_err:
        LogFunc("Couldn't get the manifest from {}".format(url), 'error')
        LogFunc("Failed due to {}".format(m_err.reason), 'error')

def ManifestToNiceListv2():
    global manifest
    step4 = []
    LogFunc("working on the manifest..", 'info')
    step1 = list(workingmanifest.split(","))
    step2 = [elem.replace('v:1.00\r\nn:', '') for elem in step1]
    step3 = [elem.replace('s:1000000\r\nn:', '') for elem in step2]
    step3.pop()
    LogFunc("The base manifest has {} items in it".format(len(step3)), 'info')
    for file in step3:
        curfile = os.path.basename(file)
        curfilepath = CreateFilePath(recordingFolder, curfile)
        if not os.path.isfile(curfilepath):
            step4.append(file)
        else:
            pass
    LogFunc("Manifest tidy up complete", 'info')
    LogFunc("The trimmed manifest has {} items to work on".format(len(step4)), 'info')
    manifest = step4

def GetFilesFromBlackVue():
    global manifest, loopcounter
    retry = Retry(10, status=10, connect=30, read=30, other=30, backoff_factor=2)
    timeout = Timeout(connect=10, read=30)
    http = urllib3.PoolManager(timeout=timeout, retries=retry)
    LogFunc("Starting grab loop of files", 'info')
    for file in manifest:
        curfile = os.path.basename(file)
        LogFunc("Loop start for {}".format(curfile), 'info')
        LogFunc("Calling Directory Checker for {}".format(curfile), 'info')
        CreatePathFolder(recordingFolder, curfile)
        curfilepath = CreateFilePath(recordingFolder, curfile)
        if not os.path.isfile(curfilepath):
            currenturl = blackvueBase + file
            LogFunc("Downloading..{}".format(currenturl), 'info')
            try:
                geturldata = http.urlopen('GET', currenturl, preload_content=False)
                tmpfile = open(curfilepath, 'wb')
                shutil.copyfileobj(geturldata, tmpfile)
                LogFunc("Download of {} done!".format(currenturl), 'info')
            except Exception as e:
                LogFunc("Uh-oh there's an issue {}".format(e), 'error')
                LogFunc("Calling rigorous testing..", 'error')
                RigorousTesting()
            loopcounter = loopcounter + 1
        elif os.path.isfile(curfilepath):
            LogFunc("File {} exists.. not downloading".format(curfilepath), 'info')
        else:
            LogFunc("Failed after {} files".format(loopcounter), 'error')
    LogFunc("Successfully downloaded {} files".format(loopcounter), 'info')
    LogFunc("I'm finished here! see ya later..", 'info')

def LogFunc(messagetolog, level):
    if level == 'info':
        logging.info(messagetolog)
    elif level == 'debug':
        logging.debug(messagetolog)
    elif level == 'error':
        logging.error(messagetolog)
    else:
        logging.warning("Not sure? Wrong log level!")
        logging.warning(messagetolog)

def LogFuncBreak(opt):
    if opt == 'start':
        LogFunc("", 'info')
        LogFunc("************** SCRIPT START **************", 'info')
        LogFunc("*                                        *", 'info')
        LogFunc("******************************************", 'info')
        LogFunc("", 'info')
    elif opt == 'end':
        LogFunc("", 'info')
        LogFunc("**************  SCRIPT END  **************", 'info')
        LogFunc("*                                        *", 'info')
        LogFunc("******************************************", 'info')
        LogFunc("", 'info')
    elif opt == 'bad':
        LogFunc("", 'error')
        LogFunc("**************  ERROR! END  **************", 'error')
        LogFunc("*                                        *", 'error')
        LogFunc("******************************************", 'error')
        LogFunc("", 'error')
    elif opt == 'badtest':
        LogFunc("", 'error')
        LogFunc("*********** INITIAL TEST FAILED **********", 'error')
        LogFunc("", 'error')

def ProgLoop():
    global innerattempts
    if innerattempts == 5:
        LogFunc("Exhausted {} attempts, exiting.".format(innerattempts), 'error')
        LogFunc("Deleting PID {}".format(pid), 'info')
        LogFuncBreak('bad')
        os.remove(pidfile)
    elif PingTest(blackvueHost, '100', '10') == False:
        LogFuncBreak('badtest')
        RigorousTesting()
    elif PingTest(blackvueHost, '100', '5') == True:
        LogFuncBreak('start')
        LogFunc("Successful host check - continuing", 'info')
        MainLoop()
        LogFunc("Deleting PID {}".format(pid), 'info')
        LogFuncBreak('end')
        os.remove(pidfile)

def RigorousTesting():
    global pingspacer, attempts, innerattempts, timeoutspacer
    LogFunc("Launching rigorous testing", 'info')
    LogFunc("Testing has been called {} times".format(attempts), 'info')
    LogFunc("Attempt number {}...".format(innerattempts), 'info')
    attempts = attempts +1
    if PingTest(blackvueHost, timeoutspacer, '5') == True:
        LogFunc("...alive again - never mind!", 'info')
        ProgLoop()
    elif PingTest(blackvueHost, '500', '5') == False:
        LogFunc("Initial test failed - launching loop test with back-off", 'error')
        timeoutspacer = timeoutspacer * 2
        LogFunc("Sleeping for {} seconds before next test...".format(pingspacer), 'info')
        time.sleep(pingspacer)
        pingspacer = pingspacer + 5
        innerattempts = innerattempts + 1
        ProgLoop()

def PidCheck():
    if os.path.exists(pidfile):
        LogFunc("a PID file exists! Exiting", 'error')
        LogFuncBreak('bad')
        return True
    elif not os.path.exists(pidfile):
        with open(pidfile, 'w') as out:
            out.write(str(pid))
        LogFunc("Writing PID {} to file".format(pid), 'info')
        return False

def MainLoop():
    LogFunc("MainLoop Start", 'info')
    GetManifest()
    ManifestToNiceListv2()
    GetFilesFromBlackVue()
    LogFunc("MainLoop end", 'info')

if PidCheck() == False:
    ProgLoop()
