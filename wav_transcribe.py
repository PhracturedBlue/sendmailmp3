#!/srv/asterisk_mbox/bin/python3.6

import speech_recognition as sr
import sys
import threading

# obtain path to "test.wav" in the same folder as this script
#from os import path
#WAV_FILE = path.join(path.dirname(path.realpath(__file__)), "test.wav")
WAV_FILE = sys.argv[1]

GOOGLE_KEY = "XXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXXX"
BING_KEY   = "YYYYYYYYYYYYYYYYYYYYYYYYYYYYYYYY"
# set credentials for IBM Bluemix Speech-to-Text API
# Obtain Bluemix credentials here: https://www.ibm.com/watson/developercloud/doc/common/getting-started-credentials.html
# 1. Create Bluemix account here: https://console.ng.bluemix.net/registration/?target=/catalog/%3fcategory=watson
# 2, Confirm registration by replying to email
# 3. Login to Bluemix: https://console.ng.bluemix.net/login?state=/catalog/?category=watson
# 4. Agree to T&C, name your organization, and name your space (STT)
# 5. Choose Watson Speech to Text service and click Create
# 6. When Speech to Text-kb opens, click Service Credentials tab
# 7. In Actions column, click View Credentials and copy your username and password
# 8. Insert deciphered Bluemix API username and password below:
# 9. Logout by clicking on image icon in upper right corner of dialog window
#10. Store key below as [API_KEY, PASSWORD]
IBM_KEY    = ["ZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZZ", "ZZZZZZZZZZZZ"]

#########################################################################################################
def get_google(q, r, audio):
    global GOOGLE_KEY

    # recognize speech using Google Speech Recognition
    str="Google:\n"
    try:
        str += r.recognize_google(audio, key=GOOGLE_KEY)
    except sr.UnknownValueError:
        str += "Google Speech Recognition could not understand audio"
    except sr.RequestError as e:
        str += "Could not request results from Google Speech Recognition service; {0}".format(e)
    q[0] = str

def get_bing(q, r, audio):
    global BING_KEY

    str = "Bing:\n"
    try:
        str += r.recognize_bing(audio, key=BING_KEY)
    except sr.UnknownValueError:
        str += "Microsoft Bing Voice Recognition could not understand audio"
    except sr.RequestError as e:
        str += "Could not request results from Microsoft Bing Voice Recognition service; {0}".format(e)
    q[1] = str

def get_ibm(q, r, audio):
    global IBM_KEY

    str = "Watson:\n"
    try:
        str += r.recognize_ibm(audio, username=IBM_KEY[0], password=IBM_KEY[1])
    except sr.UnknownValueError:
        str += "IBM Speech to Text could not understand audio"
    except sr.RequestError as e:
        str += "Could not request results from IBM Speech to Text service; {0}".format(e)
    q[2] = str


r = sr.Recognizer()
with sr.WavFile(WAV_FILE) as source:
    audio = r.record(source) # read the entire WAV file

results = ["", "", ""]
txt = []
txt.append("-------------------------------------------------------------------")
try:
    t1 = threading.Thread(target = get_google, args = (results, r, audio))
    t1.start()
    t2 = threading.Thread(target = get_bing,   args = (results, r, audio))
    t2.start()
    t3 = threading.Thread(target = get_ibm,    args = (results, r, audio))
    t3.start()
    t1.join()
    t2.join()
    t3.join()
except:
    print("Translation Failed")

if results[0] is not "":
    txt.extend(["", results[0], ""])
if results[1] is not "":
    txt.extend(["", results[1], ""])
if results[2] is not "":
    txt.extend(["", results[2], ""])
txt.append("-------------------------------------------------------------------")
print("\r\n".join(txt))
