from fastapi import APIRouter, HTTPException, Query, Request
import os
import json

router = APIRouter()

I18N_DIR = os.path.join(os.path.dirname(__file__), '..', 'i18n')

@router.get('/')
async def get_faq(locale: str = Query('en'), request: Request = None):
    filename = f'faq_{locale}.json'
    file_path = os.path.join(I18N_DIR, filename)
    if not os.path.exists(file_path):
        # Fallback to English
        file_path = os.path.join(I18N_DIR, 'faq_en.json')
        if not os.path.exists(file_path):
            raise HTTPException(status_code=404, detail='FAQ not found')
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data 