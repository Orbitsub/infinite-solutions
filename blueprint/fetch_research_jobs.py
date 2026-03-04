"""
Fetch currently researching blueprints from ESI.
"""
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(PROJECT_DIR / 'config'))

from token_manager import get_token, CHARACTER_ID
import requests
import sqlite3
from datetime import datetime

DB_PATH = str(PROJECT_DIR / 'mydatabase.db')
ESI_VERIFY_URL = 'https://esi.evetech.net/verify/'


def resolve_character_id(access_token, fallback_character_id=CHARACTER_ID):
    """Resolve character ID from ESI token verify endpoint with fallback."""
    headers = {'Authorization': f'Bearer {access_token}'}

    try:
        response = requests.get(ESI_VERIFY_URL, headers=headers, timeout=15)
        if response.status_code == 200:
            payload = response.json()
            return payload.get('CharacterID')
        raise Exception(f"ESI verify failed: {response.status_code} - {response.text}")
    except Exception as verify_error:
        if fallback_character_id:
            print(f"[WARN] Could not verify token with ESI ({verify_error}); using fallback character ID from token_manager")
            return fallback_character_id
        raise RuntimeError(
            f"Could not determine character ID: {verify_error}. "
            "Set CHARACTER_ID in config/token_manager.py or ensure ESI /verify is reachable."
        )

def get_research_jobs():
    """Get active ME/TE research jobs from ESI."""

    # Get access token and resolve character identity
    access_token = get_token()
    character_id = resolve_character_id(access_token)

    # Fetch industry jobs
    url = f'https://esi.evetech.net/latest/characters/{character_id}/industry/jobs/'
    headers = {'Authorization': f'Bearer {access_token}'}

    response = requests.get(url, headers=headers, timeout=30)

    if response.status_code != 200:
        print(f"ESI error: {response.status_code}")
        return []

    jobs = response.json()

    # Filter for active research jobs (activity_id 3=TE, 4=ME)
    research_jobs = [j for j in jobs if j.get('status') == 'active' and j.get('activity_id') in [3, 4]]

    # Get blueprint names from database
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    enriched_jobs = []
    for job in research_jobs:
        type_id = job['blueprint_type_id']

        # Get blueprint name
        cursor.execute('SELECT type_name FROM inv_types WHERE type_id = ?', (type_id,))
        result = cursor.fetchone()
        blueprint_name = result[0] if result else f"Unknown Blueprint ({type_id})"

        # Get current ME/TE from character_blueprints
        cursor.execute('''
            SELECT material_efficiency, time_efficiency
            FROM character_blueprints
            WHERE type_id = ? AND item_id = ?
        ''', (type_id, job['blueprint_id']))

        bp_result = cursor.fetchone()
        current_me = bp_result[0] if bp_result else 0
        current_te = bp_result[1] if bp_result else 0

        # Determine research type and target level
        research_type = "TE" if job['activity_id'] == 3 else "ME"
        if research_type == "ME":
            target_level = current_me + 1
            current_level = current_me
        else:
            target_level = current_te + 2  # TE increases by 2
            current_level = current_te

        # Parse end date
        end_date = datetime.fromisoformat(job['end_date'].replace('Z', '+00:00'))

        enriched_jobs.append({
            'name': blueprint_name,
            'research_type': research_type,
            'current_level': current_level,
            'target_level': target_level,
            'end_date': end_date.isoformat(),
            'job_id': job['job_id']
        })

    conn.close()

    return enriched_jobs

if __name__ == '__main__':
    jobs = get_research_jobs()

    print(f"Found {len(jobs)} active research jobs:")
    print()

    for job in jobs:
        print(f"  {job['name']}")
        print(f"    Researching: {job['research_type']} ({job['current_level']} -> {job['target_level']})")
        print(f"    Completes: {job['end_date']}")
        print()
