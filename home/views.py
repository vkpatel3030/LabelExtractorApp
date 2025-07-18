from django.shortcuts import render
from django.core.files.storage import default_storage
import fitz  # PyMuPDF
import pandas as pd
import re
import os
from datetime import datetime

def index(request):
    return render(request, "index.html",{})

