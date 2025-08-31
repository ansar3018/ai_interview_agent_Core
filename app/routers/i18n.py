from fastapi import APIRouter, HTTPException
import os
import json

router = APIRouter()

I18N_DIR = os.path.join(os.path.dirname(__file__), '..', 'i18n')

@router.get('/{lang_code}')
async def get_translation(lang_code: str):
    file_path = os.path.join(I18N_DIR, f'{lang_code}.json')
    if not os.path.exists(file_path):
        raise HTTPException(status_code=404, detail='Translation file not found')
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data 