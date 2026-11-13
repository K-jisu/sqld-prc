import os
from pathlib import Path
import sys

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'server'))
os.environ['QUESTION_ASSETS_DIR'] = str(root / 'question-assets')
os.environ['STUDY_MATERIALS_DIR'] = str(root / 'study-materials')
if not os.environ.get('APP_ORIGIN') and os.environ.get('VERCEL_PROJECT_PRODUCTION_URL'):
    os.environ['APP_ORIGIN'] = 'https://' + os.environ['VERCEL_PROJECT_PRODUCTION_URL']

from backend.main import app  # noqa: E402, F401
