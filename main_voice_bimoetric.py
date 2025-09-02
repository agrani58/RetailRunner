import os  #file operations
import re #regular expressions
import numpy as np 
from pathlib import Path #file path operations
from fastapi import FastAPI, File, UploadFile, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import torch #pytorch
import torchaudio #audio operations
from speechbrain.pretrained import EncoderClassifier #speechbrain library for speaker recognition
import whisper #openai whisper for speech to text

app= FastAPI(title="Voice Biometrics Authentication")

#---Cashing these models so we can load them once and reusing them---
_WHISPER_MODEL = None 
_ENCODER = None 
