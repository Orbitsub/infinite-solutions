"""
Update research_jobs.js with current research jobs data.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(__file__))

from fetch_research_jobs import get_research_jobs
import json

print("Fetching active research jobs...")
jobs = get_research_jobs()

print(f"Found {len(jobs)} active research jobs")

# Write to research_jobs.js
output_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'assets', 'research_jobs.js')
with open(output_path, 'w', encoding='utf-8') as f:
    f.write('// Auto-generated research jobs data\n')
    f.write('// Updated automatically - do not edit manually\n')
    f.write('RESEARCH_JOBS = ')
    f.write(json.dumps(jobs, indent=2))
    f.write(';')

print(f"\n[OK] {output_path} updated successfully")

if jobs:
    print("\nCurrent research jobs:")
    for job in jobs:
        print(f"  - {job['name']} ({job['research_type']} {job['current_level']} -> {job['target_level']})")
else:
    print("\nNo active research jobs")
