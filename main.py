# This is my simple script to grab the manifest from a BlackVue dash cam and then grab the files.

# Imports
import os, shutil, urllib3, logging, platform, subprocess, time, json, configparser
from datetime import datetime
from urllib3.util import Retry
from urllib3.util import Timeout
from urllib3.exceptions import MaxRetryError

# Config read, import and dec vars
config = configparser.ConfigParser()
config.read('config.ini')
blackvueHost = config['general']['blackvueHost']
recordingFolder = config['general']['recordingFolder']
pidfile = config['general']['pidfile']
logfile = config['general']['logfile']
enabled = bool(config['general']['enabled'])
attemptno = int(config['general']['attempts'])

# vars
blackvueBase = 'http://' + blackvueHost + '/'
blackvueVOD = 'blackvue_vod.cgi'
pid = os.getpid()
pingspacer = 5
attempts = 0
innerattempts = 0
loopcounter = 0
workingmanifest = []
manifest = []

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

# We need to store the manifest of the files, as the server is slow and unreliable

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
    step6 = []
    if len(workingmanifest) == 0:
        LogFunc('Empty Manifest - Some HTTP Error?, exiting.', 'error')
        exit()
    elif len(workingmanifest) != 0:
        FileTypes = ['EF', 'ER', 'IF', 'IR', 'NF', 'NR', 'OF', 'OR', 'AF', 'AR', 'TF', 'TR', 'BF', 'BR']
        LogFunc("working on the manifest..", 'info')
        step1 = workingmanifest.split(",")
        step2 = [elem.replace('v:1.00\r\nn:', '') for elem in step1]
        step3 = [elem.replace('s:1000000\r\nn:', '') for elem in step2]
        step4 = [elem.replace('s:1000000', '') for elem in step3]
        step5 = [elem.replace('\r\n', '') for elem in step4]
        step5.pop()
        LogFunc("The base manifest has {} items in it".format(len(step5)), 'info')
        if config['enabledFileTypes']['allFileTypes'] == 'True':
            LogFunc("Using all file types due to config option", 'info')
            for file in step5:
                curfile = os.path.basename(file)
                curfilepath = CreateFilePath(recordingFolder, curfile)
                if not os.path.isfile(curfilepath):
                    step6.append(file)
                else:
                    pass
        elif config['enabledFileTypes']['allFileTypes'] == 'False':
            LogFunc("Using trimmed file types due to config option", 'info')
            for filetype in FileTypes:
                filetypeCount = 0
                for index, file in enumerate(step5):
                    if filetype in file:
                        filetypeCount = filetypeCount + 1
                        step6.append(file)
                if filetypeCount > 0:
                    LogFunc("There was {} of filetype {} in the list.".format(str(filetypeCount), filetype), 'info')
                else:
                    pass
        LogFunc("Manifest tidy up complete", 'info')
        LogFunc("The trimmed manifest has a total of {} items to work on".format(len(step6)), 'info')
        manifest = step6

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
    PushOverRequest("Successfully downloaded {} files".format(loopcounter))
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

def PushOverRequest(message):
    pushoverbaseurl = 'https://api.pushover.net/1/messages.json'
    pushovertoken = 'agb75f1snt65npd3a19c76aqjgkn2m'
    pushoveruser = 'uxk9ryocsy959vuv8jte3xpyygk8wc'
    cert_reqs = 'CERT_NONE'
    http = urllib3.PoolManager()
    jsonbase = json.dumps({"token": pushovertoken, "user": pushoveruser, "message": message,})
    postrequest = http.request('POST', pushoverbaseurl, headers={'Content-Type': 'application/json'}, body=jsonbase)

def ProgLoop():
    if PingTest(blackvueHost, '100', '10') == False:
        LogFuncBreak('badtest')
        RigorousTesting()
    elif PingTest(blackvueHost, '100', '5') == True:
        LogFuncBreak('start')
        LogFunc("Successful host check - continuing", 'info')
        PushOverRequest("Successful host check - continuing")
        MainLoop()
        LogFunc("Deleting PID {}".format(pid), 'info')
        LogFuncBreak('end')
        os.remove(pidfile)
        exit()

def RigorousTesting():
    global pingspacer, attempts, innerattempts, attemptno
    LogFunc("Launching rigorous testing", 'info')
    LogFunc("Testing has been called {} times".format(attempts), 'info')
    LogFunc("Attempt number {}...".format(innerattempts), 'info')
    attempts = attempts +1
    if innerattempts == attemptno:
        LogFunc("Exhausted {} attempts, exiting.".format(innerattempts), 'error')
        PushOverRequest("Exhausted {} attempts, exiting.".format(innerattempts))
        LogFunc("Deleting PID {}".format(pid), 'info')
        LogFuncBreak('bad')
        os.remove(pidfile)
        exit()
    elif PingTest(blackvueHost, '100', '5') == True:
        LogFunc("...alive again - never mind!", 'info')
        ProgLoop()
    else:
        LogFunc("Initial test failed - launching loop test with back-off", 'error')
        LogFunc("Sleeping for {} seconds before next test...".format(pingspacer), 'info')
        time.sleep(pingspacer)
        pingspacer = pingspacer * 2
        innerattempts = innerattempts + 1
        ProgLoop()

def PidCheck():
    if os.path.exists(pidfile):
        with open(pidfile, 'r') as old:
            oldpid = old.read()
            LogString = f"PID file existis with PID {oldpid} Exiting"
            LogFunc(LogString, 'error')
            LogFuncBreak('bad')
            old.close()
        return True
    elif not os.path.exists(pidfile):
        with open(pidfile, 'w') as out:
            out.write(str(pid))
            out.close()
        LogFunc("Writing PID {} to file".format(pid), 'info')
        return False

def MainLoop():
    if enabled == 1:
        LogFunc("Script enabled, continuing", 'info')
        LogFunc("MainLoop Start", 'info')
        GetManifest()
        ManifestToNiceListv2()
        GetFilesFromBlackVue()
        LogFunc("MainLoop end", 'info')
        exit()
    elif enabled == 0:
        LogFunc("Exit, script disabled", 'info')
        exit()

if PidCheck() == False:
    ProgLoop()
else:
    exit()