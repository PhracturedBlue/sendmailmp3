# sendmailmp3
Script to help asterisk send an MP3 voice recording via email

This code is designed to work with asterisk to transcribe a voicemail using
various transcription services.  The code takes an input WAV file, transcribes
it, and sends an email containing the transcription as well as a converted MP3
attachment of the message.


There are 2 independent transcription solutions provided:
  * wav\_transcribe.py uses stdin/stdout to send a WAV file to send the WAV
    file to multiple providers (Google, IBM, Bing) using the
    `speech_recognition` module.
  * server.py is a standalone server that accepts HTTP requests containing
    the WAV file, and transcribes using both Google and DeepSpeech.
    I currently use this running on a RPi4, and it has reasonable performance
    for voicemail transcription.

All future development will be done on server.py.

The `Dockerfile.server` can be used to ease the installation of DeepSpeech.
