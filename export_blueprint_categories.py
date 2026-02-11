"""
Export current blueprint categories to CSV for bulk editing.
Opens in Excel/Google Sheets for easy editing of 100+ blueprints.
"""
import sqlite3
import csv
from generate_corrected_html import categorize_blueprint, get_subcategory

DB_PATH = 'mydatabase.db'
OUTPUT_CSV = 'blueprint_categories.csv'

def export_categories():
    print("=" * 70)
    print("EXPORTING BLUEPRINT CATEGORIES TO CSV")
    print("=" * 70)
    print()

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Get all blueprints with their current auto-categorization
    cursor.execute("""
        SELECT
            cb.type_id,
            cb.type_name,
            COALESCE(g.group_name, 'Unknown') as group_name,
            cb.material_efficiency,
            cb.time_efficiency,
            cb.runs,
            it.market_group_id
        FROM character_blueprints cb
        LEFT JOIN inv_types it ON cb.type_id = it.type_id
        LEFT JOIN inv_groups g ON it.group_id = g.group_id
        WHERE cb.runs = -1
        ORDER BY cb.type_name
    """)

    blueprints = []
    for row in cursor.fetchall():
        type_id, type_name, group_name, me, te, runs, market_group_id = row

        # Get current categorization (includes overrides if they exist)
        category = categorize_blueprint(group_name or 'Unknown', type_name, type_id=type_id, market_group_id=market_group_id, cursor=cursor)
        subcategory = get_subcategory(group_name or 'Unknown', type_name, type_id=type_id)

        blueprints.append({
            'type_id': type_id,
            'blueprint_name': type_name,
            'group_name': group_name or 'Unknown',
            'me': me,
            'te': te,
            'current_category': category,
            'current_subcategory': subcategory,
            'new_category': category,  # Start with current
            'new_subcategory': subcategory  # Start with current
        })

    conn.close()

    # Write to CSV
    print(f"Writing {len(blueprints)} blueprints to {OUTPUT_CSV}...")

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'type_id', 'blueprint_name', 'group_name', 'me', 'te',
            'current_category', 'current_subcategory',
            'new_category', 'new_subcategory'
        ])
        writer.writeheader()
        writer.writerows(blueprints)

    print()
    print("=" * 70)
    print("EXPORT COMPLETE!")
    print("=" * 70)
    print()
    print(f"[OK] Exported {len(blueprints)} blueprints to: {OUTPUT_CSV}")
    print()
    print("NEXT STEPS:")
    print("1. Open blueprint_categories.csv in Excel or Google Sheets")
    print("2. Edit 'new_category' and 'new_subcategory' columns")
    print("3. Use Excel features:")
    print("   - Sort by current_category to group similar items")
    print("   - Filter to find specific types")
    print("   - Copy/paste for bulk changes")
    print("   - Fill-down for repetitive updates")
    print("4. Save the file (keep as CSV)")
    print("5. Run: python import_blueprint_categories.py")
    print()
    print("TIPS:")
    print("- Leave 'current_category' and 'current_subcategory' alone (reference only)")
    print("- Only edit 'new_category' and 'new_subcategory'")
    print("- Blank new_category = use auto-categorization")
    print()

if __name__ == '__main__':
    export_categories()
