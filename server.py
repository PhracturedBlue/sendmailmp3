#!/usr/bin/env python3
"""
Very simple HTTP server in python for logging requests
Usage::
    ./server.py [<port>]
"""
from http.server import BaseHTTPRequestHandler, HTTPServer
import logging
from deepspeech import Model
import argparse
from timeit import default_timer as timer
import json
import numpy as np
import io
import wave
import subprocess
import concurrent.futures

from urllib.parse import urlencode
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError

class UnknownValueError(Exception): pass
class RequestError(Exception): pass

def convert_samplerate(data, desired_sample_rate):
    sox_cmd = ['sox', '--type', 'wav', '-', '--type', 'raw', '--bits', '16',
               '--channels', '1', '--rate', f'{desired_sample_rate}',
               '--encoding', 'signed-integer', '--endian', 'little',
               '--compression', '0.0', '--no-dither', '-']
    try:
        output = subprocess.check_output(sox_cmd, input=data, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        raise RuntimeError('SoX returned non-zero status: {}'.format(e.stderr))
    except OSError as e:
        raise OSError(e.errno, 'SoX not found, use {}hz files or install it: {}'.format(desired_sample_rate, e.strerror))

    return np.frombuffer(output, np.int16)

def convert_flac(data):
    sox_cmd = ['sox', '--type', 'wav', '-', '--type', 'flac', '-']
    try:
        output = subprocess.check_output(sox_cmd, input=data, stderr=subprocess.PIPE)
    except subprocess.CalledProcessError as e:
        raise RuntimeError('SoX returned non-zero status: {}'.format(e.stderr))
    except OSError as e:
        raise OSError(e.errno, 'SoX not found: {}'.format(e.strerror))

    return output

def load_ds_audio(wav, data, desired_sample_rate):
    fs_orig = wav.getframerate()
    if fs_orig != desired_sample_rate:
        #logging.warning('original sample rate (%s) is different than %shz. Resampling might produce erratic speech recognition.',
        #                fs_orig, desired_sample_rate)
        audio = convert_samplerate(data, desired_sample_rate)
    else:
        audio = np.frombuffer(wav.readframes(wav.getnframes()), np.int16)

    return audio

def google_tts(data, wav, key):
    start = timer()
    data = convert_flac(data)
    url = "http://www.google.com/speech-api/v2/recognize?{}".format(urlencode({
        "client": "chromium",
        "lang": "en-US",
        "key": key,
    }))
    request = Request(url, data=data, headers={"Content-Type": f"audio/x-flac; rate={wav.getframerate()}"})

    # obtain audio transcription results
    try:
        response = urlopen(request, timeout=90)
    except HTTPError as e:
        raise RequestError("recognition request failed: {}".format(e.reason))
    except URLError as e:
        raise RequestError("recognition connection failed: {}".format(e.reason))
    response_text = response.read().decode("utf-8")
    # ignore any blank blocks
    actual_result = []
    for line in response_text.split("\n"):
        if not line: continue
        result = json.loads(line)["result"]
        if len(result) != 0:
            actual_result = result[0]
            break

    # return results
    if not isinstance(actual_result, dict) or len(actual_result.get("alternative", [])) == 0: raise UnknownValueError()
    end = timer()

    result = [{'confidence': _x.get('confidence', -1), 'text': _x['transcript']} for _x in actual_result["alternative"]]
    return sorted(result, reverse=True, key=lambda item: item["confidence"]), end - start

def deepspeech_tts(ds, wav, data):
    audio = load_ds_audio(wav, data, ds.sampleRate())
    inference_start = timer()
    metadata = ds.sttWithMetadata(audio, 1)
    return [{
            "confidence": transcript.confidence,
            "text": ''.join([_x.text for _x in transcript.tokens])
            } for transcript in metadata.transcripts], timer() - inference_start

def transcribe(ds, data, google_key):
    buf = io.BytesIO(data)
    wav = wave.open(buf, 'rb')
    audio_length = wav.getnframes() / wav.getframerate()
    result = {
        "origsize": len(data),
        "audiolen": audio_length,
         }
    with concurrent.futures.ThreadPoolExecutor() as executor:
        future = executor.submit(google_tts, data, wav, google_key)
        try:
            ds_trans, ds_runtime = deepspeech_tts(ds, wav, data)
            result.update({'ds_runtime': ds_runtime, 'ds_transcript': ds_trans})
        except Exception as _e:
            result['ds_error'] = f'DeepSpeech failed to parse audio: {str(_e)}'
        try:
            trans, runtime = future.result()
            result.update({'google_runtime': runtime, 'google_transcript': trans})
        except UnknownValueError:
            result['google_error'] = "Google Speech Recognition could not understand audio"
        except Exception as _e:
            result['google_error'] = f"Google Speech Recognition failed to parse audio: {str(_e)}"
    wav.close()
    return result

def ReqHandlerFactory(ds, google_key):
    class CustomHandler(BaseHTTPRequestHandler):
        def _set_response(self):
            self.send_response(200)
            self.send_header('Content-type', 'text/html')
            self.end_headers()

        def do_POST(self):
            content_length = int(self.headers['Content-Length']) # <--- Gets the size of data
            post_data = self.rfile.read(content_length) # <--- Gets the data itself
            result = transcribe(ds, post_data, google_key)
            logging.info("POST request Path: %s Response: %s\n",
                         str(self.path), json.dumps(result))
            self._set_response()
            if 'text' in self.path:
                txt = ''
                txt += 'Google:\n'
                if 'google_error' in result:
                    txt += result['google_error'] + '\n'
                else:
                    txt += result['google_transcript'][0]['text'] + '\n'
                txt += '\n'
                txt += 'DeepSpeech:\n'
                if 'ds_error' in result:
                    txt += result['ds_error'] + "\n"
                else:
                    txt += result['ds_transcript'][0]['text'] + '\n'
                self.wfile.write(txt.encode('utf8'))
            else:
                self.wfile.write(json.dumps(result).encode('utf8'))
    return CustomHandler


def run():
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description='DeepSpeech Server')
    parser.add_argument('--port', default=3337, type=int,
                        help='Port to listen on')
    parser.add_argument('--model', required=True,
                        help='Path to the model (protocol buffer binary file)')
    parser.add_argument('--scorer', required=False,
                        help='Path to the external scorer file')
    parser.add_argument('--beam_width', type=int,
                        help='Beam width for the CTC decoder')
    parser.add_argument('--lm_alpha', type=float,
                        help='Language model weight (lm_alpha). If not specified, use default from the scorer package.')
    parser.add_argument('--lm_beta', type=float,
                        help='Word insertion bonus (lm_beta). If not specified, use default from the scorer package.')
    parser.add_argument('--google_key',
                        help="Google Speech-Recognition API key.")
    args = parser.parse_args()

    ds = Model(args.model)
    if args.beam_width:
        ds.setBeamWidth(args.beam_width)
    ds.enableExternalScorer(args.scorer)
    if args.lm_alpha and args.lm_beta:
        ds.setScorerAlphaBeta(args.lm_alpha, args.lm_beta)
    handler_class = ReqHandlerFactory(ds, args.google_key)

    server_address = ('', args.port)
    httpd = HTTPServer(server_address, handler_class)
    logging.info('Starting httpd...\n')
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    httpd.server_close()
    logging.info('Stopping httpd...\n')

if __name__ == '__main__':
    run()
