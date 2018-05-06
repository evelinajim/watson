


from ws4py.client.threadedclient import WebSocketClient
import base64, json, ssl, subprocess, threading, time
import requests
import subprocess

# These are from the Audio Example
import pyaudio
import time
import wave

# open stream
FORMAT = pyaudio.paInt16
CHANNELS = 1
RATE = 16000
RATE = 48000
CHUNK = 24000  # this was 2048 but made this 2000 to divide evenly into 16000, smoothed out the playback !!
# this was 2048 but for smoother playback and to divide evenly into 16000 made it 24000

# https://2001archive.org/
wf_greeting = wave.open('Greeting.wav', 'rb')
wf_goodbye =  wave.open('goodbye.wav', 'rb')
wf_ignore = wave.open('sure.wav' ,'rb')


'''
Port Audio seems to have some known issues.
'''

# Plays back the wave files
def play_uncompressed_wave(wave_object):
    # define callback (2)
    def callback(in_data, frame_count, time_info, status):
        data = wave_object.readframes(frame_count)
        return data, pyaudio.paContinue

    # instantiate PyAudio (1)
    p_out = pyaudio.PyAudio()
    # Open a new audio out channel
    stream_out = p_out.open(format=p_out.get_format_from_width(wave_object.getsampwidth()),
                            channels=wave_object.getnchannels(),
                            rate=wave_object.getframerate(),
                            output=True,
                            stream_callback=callback)

    # start the stream (4)
    stream_out.start_stream()

    # wait for stream to finish (5)
    while stream_out.is_active():
        time.sleep(0.1)

    # stop stream (6)
    stream_out.stop_stream()
    stream_out.close()
    wave_object.close()
    p_out.terminate()
    pass


class SpeechToTextClient(WebSocketClient):
    def __init__(self):
        ws_url = "wss://stream.watsonplatform.net/speech-to-text/api/v1/recognize" # Secure WebSocket / Speech to Text URI

        username = "144d8f62-b646-4672-9e92-19006badd7b8"
        password = "7UiZiDpNQcJU"

        authstring = "{0}:{1}".format(username, password)
        # Encodes base64 as there is enough symbols to convert to base64
        # Independent of word size problems
        base64string = base64.b64encode(authstring.encode('utf-8')).decode('utf-8')

        # Variables
        self.Command_State = None
        self.listening = False
        self.empty_count = 0
        self.Gathered_String = ''
        self.stream_audio_thread = threading.Thread(target=self.stream_audio)

        # Attempt to connect to server
        try:
            WebSocketClient.__init__(self, ws_url,
                                     headers=[("Authorization", "Basic %s" % base64string)])
            self.connect()
        except:
            print("Failed to open WebSocket.")

    # Websocket is opened
    # Watson is waiting for a command

    # JSON -- Java Script Object Notation

    def opened(self):
        # self.send('{"action": "start", "content-type": "audio/l16;rate=44100;channels=1" }')
        # Create data (dictionary)
        data = {"action": "start",
                "content-type": "audio/l16;rate=44100;channels=1", # Sends 16 bit rate audio on channel 1
                'max_alternatives': 3,
                "keywords": ["hello" ,"quit", "go", "ignore"], # Keywords that watson will be looking for. Words that are said.
                "keywordsThreshold" :0.5,     #Say hello. and say something. these are the key words
                'timestamps': True,
                'word_confidence': True}

        print("sendMessage(init)")
        # send the initialization parameters
        print(json.dumps(data).encode('utf8')) # Takes a dictionary and dumps it into a JSON
        self.send(json.dumps(data).encode('utf8'))
        self.stream_audio_thread.start()

    def received_message(self, message):

        # Receives the message and checks what was received
        message = json.loads(str(message))

        # ----------START OF MESSAGE FEEDBACK LOOP--------------------------
                        #each one is a different command. you look for
        if "state" in message: # Looks for 'state' to see if it's listening
            if message["state"] == "listening" and self.Command_State is None: # if it is listening, play the wf_greeting audio
                play_uncompressed_wave(wf_greeting)
                self.listening = True
        if "results" in message: # If watson reveives results (results) : speech from user
            print(self.Command_State)
            if message["results"]: # Check the message
                x = message['results']
                print(x)
                if x[0]['alternatives'][0]['transcript'] == 'hello ' and self.Command_State is None:  # If Watson is in the first alternative, then stop looking for alternatives
                    print("found a command")
                    self.Command_State = 'Started' # Watson goes into the command state
                if x[0]['alternatives'][0]['transcript'] == 'ignore ' and self.Command_State is 'Started':
                    play_uncompressed_wave(wf_ignore)
                    self.Command_State = None # Watson returns to it's default command state
                    self.listening = True
                if x[0]['alternatives'][0]['transcript'] == 'go ' and self.Command_State is 'Started': # Goes into a new state called 'Gather'
                    self.Command_State = 'Gather' # Will build of a string of what you are talking about/sticks alternatives together
                    self.Gathered_String = '' # If watson get's emtpy strings X3 (the user has stopped talking) / Use this to send up speech to translate it
                    self.listening = True
                    self.empty_count = 0

                if x[0]['alternatives'][0]['transcript'] == 'open ' and self.Command_State is 'Started':
                    self.listening = True
                    self.Command_State = None
                    subprocess.Popen('C:\Program Files\internet explorer\iexplore.exe')   #if used on firefox might need \\ but chrome should work fine

                if x[0]['alternatives'][0]['transcript'] == 'quit ' and self.Command_State is 'Started':
                    self.listening = False
                    play_uncompressed_wave(wf_goodbye)
                    self.Command_State = 'Exit'
                    self.stream_audio_thread.join()

                if self.Command_State == 'Gather':
                    self.Gathered_String = self.Gathered_String + x[0]['alternatives'][0]['transcript']
                    self.empty_count = 0
            else:
                if self.Command_State == 'Gather':
                    self.empty_count = self.empty_count + 1
                    if self.empty_count >= 3:
                        self.Command_State = None
                        self.listening = True
                        # HERE IS WHERE YOU WILL SEND THE Gathered_String
                        headers = {'content-type': 'text/plain'}
                        audioFeedback = {'content-type': 'audio/wav'}

                        response = requests.get('https://gateway.watsonplatform.net/language-translator/api/v2/translate?model_id=en-fr&text={0}'.format(self.Gathered_String), headers=headers, auth=('ceece798-fbae-4536-bd3c-4388251f9887', '7Be7b3KRsVxb'))  #username password for both. 166 language translator.
                        audioResponse = requests.get('https://stream.watsonplatform.net/text-to-speech/api/v1/synthesize?accept=audio/wav&text={0}&voice=fr-FR_ReneeVoice'.format(response.text), headers=audioFeedback, auth=('660a9d64-9754-4bea-8569-6f9613baf07a', 'nfiq687QRPLA'))  #167 text to speech.

                        with open('audio.wav', 'wb') as f:
                            f.write(audioResponse.content)

                            audio = wave.open('audio.wav', 'rb')

                            play_uncompressed_wave(audio)

                            self.empty_count = 0

        # ----------START OF MESSAGE FEEDBACK LOOP--------------------------


    # Waits for watson to be listening / Hooked up to the microphone
    def stream_audio(self):
        print("Waiting for Watson")
        while not self.listening:
            time.sleep(0.1)
        print("Hello Watson")
        p_in = pyaudio.PyAudio()
        iChunk = 4410
        iSec = 1 # Can add to class and change to a higher number in the 'go' block to improve translation
        stream_in = p_in.open(format=pyaudio.paInt16, channels=1, rate=44100, input=True, frames_per_buffer=iChunk)
        #rate microphone 44100 turn the microphone all the way up so it works.

        # While the microphone is listening to data / This is where you play around with rate and chunk send up size
        while self.listening:
            for i in range(0, int(44100 / iChunk * iSec)): # Reading 10 seconds of audio
                data = stream_in.read(CHUNK, exception_on_overflow=False) # Send data up to watson
                if data:
                    try:
                        self.send(bytearray(data), binary=True)
                    except ssl.SSLError:
                        pass
                    except ConnectionAbortedError:
                        pass
            if self.listening:
                try:
                    self.send \
                        ('{"action": "stop"}') # Watson won't do anything until this is command 'stop' has been receieved
                except ssl.SSLError:
                    pass
                except ConnectionAbortedError:
                    pass
            time.sleep \
                (0.5) # Sends audio up half a second at a time / Ajust to make the program work best for your system

        stream_in.stop_stream()
        stream_in.close()
        p_in.terminate()
        self.close()

    def close(self ,code=1000, reason=''):

        self.listening = False # Stops listening to the microphone
        WebSocketClient.close(self) # Close the WebSocket


if __name__ == "__main__":

    stt_client = SpeechToTextClient()

    while not stt_client.terminated:
        pass