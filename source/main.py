from OpenSSL.crypto import X509,FILETYPE_ASN1,load_certificate
import subprocess
import argparse
import plistlib
import os
import datetime
import sys
import re

VERSION='1.5'
_PPF_INSTALL_DIR = os.path.expanduser("~/Library/MobileDevice/Provisioning Profiles/")

def removeIdxs(array:[object], idxes:[int]):
    tmp = array
    descIdxs = list(reversed(sorted(idxes, key=lambda item: item)))
    descIdxs = filter(lambda item: item >=0 and item < len(tmp), descIdxs)
    for i in descIdxs:
        del tmp[i]
    return tmp

def redText(text):
    return "\033[31m" + format(text) + "\033[0m"

def greenText(text):
    return "\033[32m" + format(text) + "\033[0m"

def yellowText(text):
    return "\033[33m" + format(text) + "\033[0m"

def exitWithError(errorMsg):
    print(redText("Error: ") + errorMsg)
    exit(1)

class ExecuteResult():
    returncode = 0
    outputs = None
    def __init__(self, returncode: int, outputs: str):
        self.returncode = returncode
        self.outputs = outputs

def executeCMD(args: [str],
               isRealTimeOutput = True,
               outPutPrefix = "",
               isCollectOutput = False,
               cwd = None,
               env = None
               ):
    p = subprocess.Popen(args,
                         shell=False,
                         stdout=subprocess.PIPE,
                         stderr=subprocess.STDOUT,
                         cwd=cwd,
                         env = env
                         )
    outputs = []
    while p.poll() is None:
        out = str(p.stdout.readline(), encoding="utf-8").strip()
        if len(out) > 0:
            if isCollectOutput is True:
                outputs.append(out)
            if isRealTimeOutput is True:
                print('%s%s' % (outPutPrefix, out))
    remainOut = str(p.stdout.read(), encoding="utf-8").strip()
    if len(remainOut) > 0:
        if isCollectOutput:
            outputs.append(remainOut)
        if isRealTimeOutput:
            print('%s%s' % (outPutPrefix, remainOut))
    outputString = None
    if len(outputs) > 0:
        outputString =  "\n".join(outputs)
    return ExecuteResult(returncode=p.returncode, outputs=outputString)

class Entitlements(object):
    def __init__(self, dic):
        self.keychainAccessGroups = dic.get("keychain-access-groups", [])
        self.getTaskAllow = dic.get("get-task-allow")
        self.applicationIdentifier = dic.get("application-identifier")
        self.comAppleDeveloperTeamIdentifier = dic.get("com.apple.developer.team-identifier")
        self.apsEnvironment = dic.get("aps-environment")
        self.betaReportsActive = dic.get("beta-reports-active")

class PPFEntity:
    def __init__(self, filePath):
        if not os.path.exists(filePath):
            exitWithError("file path at %s does not exist" % (filePath))
        rs = executeCMD(["security", "cms", "-D",
                         "-u", "certUsageObjectSigner",
                         "-i", filePath],
                        isCollectOutput=True,
                        isRealTimeOutput=False)
        if rs.returncode != 0:
            exitWithError("Provisioning profile parsing failed")

        ppfStr = rs.outputs
        ppfDic = plistlib.loads(ppfStr.encode("utf-8"))
        self.rawPPFString = ppfStr
        self.appIDName = ppfDic.get("AppIDName")
        self.applicationIdentifierPrefix = ppfDic.get("ApplicationIdentifierPrefix", [])
        self.creationDate = ppfDic.get("CreationDate")
        self.platform = ppfDic.get("Platform")
        self.expirationDate = ppfDic.get("ExpirationDate")
        self.name = ppfDic.get("Name")
        self.teamIdentifier = ppfDic.get("TeamIdentifier")
        self.teamName = ppfDic.get("TeamName")
        self.timeToLive = ppfDic.get("TimeToLive")
        self.UUID= ppfDic.get("UUID")
        self.version = ppfDic.get("Version")
        self.entitlements = Entitlements(dic=ppfDic.get("Entitlements"))
        self.developerCertificates: [X509] = []
        cerbytesArr = ppfDic.get("DeveloperCertificates")
        for cerByte in cerbytesArr:
            cer = load_certificate(type=FILETYPE_ASN1, buffer=cerByte)
            self.developerCertificates.append(cer)

    def formatedXML(self):
        return plistlib.dumps(plistlib.loads(self.rawPPFString.encode("utf-8"))).decode('utf-8')

def exec():
    parser = argparse.ArgumentParser(description='', epilog='')
    parser.add_argument('-v','--version', action='version', version=("%(prog)s "+VERSION))
    subparsers = parser.add_subparsers(dest='subCmd')

    # clean
    clean = subparsers.add_parser('clean', help='Clean up locally installed configuration files based on your specified parameters')
    clean.add_argument('-e', action='store_true', help="Remove all expired provisioning profiles.")
    clean.add_argument('-p', dest="pattern", help="Remove any provisioning profiles that matches the regular expression.")
    clean.add_argument('-r', action='store_true', help="Remove files with duplicate names(This name refers to the 'Name' key in the provisioning profile). In all provisioning profiles with the same name, the one with the latest creation date will be retained.")

    # list
    list = subparsers.add_parser('list', help='List locally installed provisioning profiles')

    # info
    info = subparsers.add_parser('info', help='Output information about a provisioning profile')
    info.add_argument('-cer', action='store_true')
    info.add_argument('filePath')

    rs = parser.parse_args(sys.argv[1:])
    argsDic = vars(rs)
    subCmd = argsDic['subCmd']
    if subCmd == 'clean':
        if not argsDic.get('e', False) and not argsDic.get('pattern', False) and  not argsDic.get('r', False):
            clean.print_help()
            exit(1)
        print("Loading Provisioning profiles from %s" % _PPF_INSTALL_DIR)
        ppfs = []
        for fname in os.listdir(_PPF_INSTALL_DIR):
            if not fname.lower().endswith(".mobileprovision"):
                continue
            ppfPath = os.path.join(_PPF_INSTALL_DIR, fname)
            ppfEntity = PPFEntity(filePath=ppfPath)
            ppfEntity.fpath = ppfPath
            ppfs.append(ppfEntity)

        toDelIdxs = []

        toDelExpiredPPFs = []
        if argsDic.get('e', False):
            now = datetime.datetime.now()
            for idx, ppfEntity in enumerate(ppfs):
                if ppfEntity.expirationDate < now:
                    toDelIdxs.append(idx)
                    toDelExpiredPPFs.append(ppfEntity)
        ppfs = removeIdxs(ppfs, toDelIdxs)

        toDelMatchedPPFs = []
        if argsDic.get('pattern', False):
            pattern = argsDic['pattern']
            for idx, ppfEntity in enumerate(ppfs):
                if re.match(pattern, ppfEntity.name) or pattern in ppfEntity.name:
                    toDelIdxs.append(idx)
                    toDelMatchedPPFs.append(ppfEntity)
        ppfs = removeIdxs(ppfs, toDelIdxs)

        toDelRepeatPPFs = []
        if argsDic.get('r', False):
            name2ppfs = {}
            for ppfEntity in ppfs:
                if not name2ppfs.get(ppfEntity.name):
                    name2ppfs[ppfEntity.name] = []
                name2ppfs[ppfEntity.name].append(ppfEntity)

            for name in name2ppfs.keys():
                ppfs = name2ppfs[name]
                if len(ppfs) <= 1:
                    continue
                ppfs = sorted(ppfs, key=lambda item: item.creationDate)
                for ppf in ppfs:
                    toDelRepeatPPFs.append(ppf)

        if len(toDelExpiredPPFs):
            print("Expired files to be deleted")
            for ppf in toDelExpiredPPFs:
                print("\t ",redText(ppf.name))

        if len(toDelMatchedPPFs):
            print("Matched files to be deleted")
            for ppf in toDelMatchedPPFs:
                print("\t ",redText(ppf.name))

        if len(toDelRepeatPPFs):
            print("Repeat files to be deleted (The file with the latest creation date will be retained)")
            for ppf in toDelRepeatPPFs:
                print("\t ",redText(ppf.name))
        totalCount = len(toDelExpiredPPFs) + len(toDelMatchedPPFs) + len(toDelRepeatPPFs)
        if totalCount <= 0:
            print(greenText("No files to be deleted"))
            exit(0)
        prompt = yellowText("Delete these provisioning profiles %s?" % (totalCount)) + " (y/n)\n"
        i = input(prompt)
        while not i in ['y', 'n']:
            i = input(prompt)
        if i == 'y':
            for ppf in toDelExpiredPPFs + toDelMatchedPPFs + toDelRepeatPPFs:
                os.remove(ppf.fpath)
            print(greenText("Deleted %s profiles" % totalCount))
        else:
            exit(0)
    elif subCmd == 'list':
        print("Loading Provisioning profiles from %s" % _PPF_INSTALL_DIR)
        varlidPPFs = []
        expiredPPFs = []
        now = datetime.datetime.now()
        for fname in os.listdir(_PPF_INSTALL_DIR):
            if not fname.lower().endswith(".mobileprovision"):
                continue
            ppfPath = os.path.join(_PPF_INSTALL_DIR, fname)
            ppfEntity = PPFEntity(filePath=ppfPath)
            expirationDate = ppfEntity.expirationDate
            if expirationDate > now:
                varlidPPFs.append(ppfEntity)
            else:
                expiredPPFs.append(ppfEntity)

        varlidPPFs = sorted(varlidPPFs, key=lambda item: item.name.lower())
        expiredPPFs = sorted(expiredPPFs, key=lambda item: item.name.lower())
        print("Loading Provisioning profiles from: ", _PPF_INSTALL_DIR)
        print("Valid:")
        for ppf in varlidPPFs:
            print(greenText("\t " + ppf.name))
        print("Expired:")
        for ppf in expiredPPFs:
            print(redText("\t " + ppf.name))
        print("Summary:")
        print("\t{installed}, {valid}, {expired}".format(
            installed = str(len(varlidPPFs)+len(expiredPPFs)) + " installed",
            valid = greenText(str(len(varlidPPFs)) + " valid"),
            expired = redText(str(len(expiredPPFs)) + " expired")
        ))
    elif subCmd == 'info':
        filePath = argsDic['filePath']
        ppfEntity = PPFEntity(filePath=filePath)
        if not argsDic.get('cer', False):
            print(ppfEntity.formatedXML())
        else:
            print("Included certificate information:")
            for x in ppfEntity.developerCertificates:
                name = x.get_subject().get_components()[1][1].decode('utf-8')
                print(name, "(SerialNumber: %s)" % x.get_serial_number(), redText("Expired") if x.has_expired() else "")
    else:
        parser.print_help()


if __name__ == '__main__':
    # sys.argv = ['mppf','-v']
    # sys.argv = ['mppf', 'list']
    sys.argv = ['mppf', 'clean','-p','x']
    exec()
