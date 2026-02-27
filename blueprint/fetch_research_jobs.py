"""
Fetch currently researching blueprints from ESI.
"""
import sys
import os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_DIR = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, os.path.join(PROJECT_DIR, 'config'))

from token_manager import TokenManager
import requests
import sqlite3
from datetime import datetime, timezone

DB_PATH = os.path.join(PROJECT_DIR, 'mydatabase.db')

def get_research_jobs():
    """Get active ME/TE research jobs from ESI."""

    # Get access token
    tm = TokenManager()
    access_token = tm.get_access_token()

    character_id = 97153110

    # Fetch industry jobs
    url = f'https://esi.evetech.net/latest/characters/{character_id}/industry/jobs/'
    headers = {'Authorization': f'Bearer {access_token}'}

    response = requests.get(url, headers=headers)

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
