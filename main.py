# This is my simple script to grab the manifest from a BlackVue dash cam and then grab the files.
# DPC 220922

# Imports
import os
import shutil
import urllib3
import logging
from ping3 import ping
from datetime import datetime
from urllib3.util import Retry
from urllib3.util import Timeout
from urllib3.exceptions import MaxRetryError

# vars

blackvueHost = '10.100.0.121'
blackvueBase = 'http://' + blackvueHost + '/'
blackvueVOD = 'blackvue_vod.cgi'
recordingFolder = 'Recordings'
runfilesdir = 'run_files'
pidfile = 'pidfile.pid'
logfile = 'blackvuegrab.log'
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

expLogFile = CreatePath(runfilesdir, logfile)
expPidFile = CreatePath(runfilesdir, pidfile)

# Log defs

logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', filename=expLogFile, level=logging.INFO)
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', filename=expLogFile, level=logging.DEBUG)
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', filename=expLogFile, level=logging.ERROR)
logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', datefmt='%m/%d/%Y %I:%M:%S %p', filename=expLogFile, level=logging.WARNING)

# We need to store the manifest of the files, as the server is slow and unrelliable

def IsNo5Alive(host):
    resp = ping(host)
    LogFunc("Checking if host {} is alive".format(host), 'info')
    if resp == False:
        LogFunc("{} is dead jim. Exit.".format(host), 'error')
        return False
    else:
        LogFunc("{} is alive! continuing".format(host), 'info')
        return True

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

def ManifestToNiceList():
    global workingmanifest, manifest
    string = workingmanifest
    LogFunc("working on the manifest..", 'info')
    step1 = list(string.split(","))
    step2 = [elem.replace('v:1.00\r\nn:', '') for elem in step1]
    step3 = [elem.replace('s:1000000\r\nn:', '') for elem in step2]
    step3.pop()
    manifest = step3
    LogFunc("manifest tidy up complete", 'info')

def GetFilesFromBlackVue():
    global manifest
    retry = Retry(10, status=10, connect=30, read=30, other=30, backoff_factor=2)
    timeout = Timeout(connect=10, read=30)
    http = urllib3.PoolManager(timeout=timeout, retries=retry)
    LogFunc("Starting grab loop of files", 'info')
    counter = 0
    for file in manifest:
        curfile = os.path.basename(file)
        LogFunc("Loop start for {}".format(curfile), 'info')
        LogFunc("Calling Directory Checker for {}".format(curfile), 'info')
        CreatePathFolder(recordingFolder, curfile)
        curfilepath = CreateFilePath(recordingFolder, curfile)
        if not os.path.isfile(curfilepath):
            currenturl = blackvueBase + file
            LogFunc("Downloading..{}".format(currenturl), 'info')
            geturldata = http.urlopen('GET', currenturl, preload_content=False)
            tmpfile = open(curfilepath, 'wb')
            shutil.copyfileobj(geturldata, tmpfile)
            LogFunc("Download of {} done!".format(currenturl), 'info')
            addcounter = counter + 1
        else:
            LogFunc("Failed after {} files".format(counter), 'error')
            LogFunc("{} exists".format(curfile), 'error')
    LogFunc("Successfully downloaded {} files".format(counter), 'info')
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

def RunTheProg():
    for i in range (5):
        try:
            if IsNo5Alive(blackvueHost) == True:
                LogFunc("Successful host check after {} attempts. Continuing".format(i), 'info')
                GetManifest()
                ManifestToNiceList()
                GetFilesFromBlackVue()
        finally:
            LogFunc("Host check failed after {} attempts. Exiting".format(i), 'error')
            break

RunTheProg()
