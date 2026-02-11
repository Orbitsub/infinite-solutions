"""
Reduce all font sizes in index.html by 30% to match 67% zoom viewing.
This script scales down fonts proportionally for better readability at 100% zoom.
"""
import re

# Font size mappings (old size -> new size in px)
FONT_SIZE_MAP = {
    '72px': '50px',   # Main title
    '48px': '34px',   # Mobile large headers
    '45px': '32px',   # Large headers
    '42px': '29px',   # Total price
    '39px': '27px',   # Section headers
    '38px': '27px',   # Headers
    '36px': '25px',   # Modal title
    '33px': '23px',   # Table headers, section titles
    '32px': '22px',   # Modal close, contact
    '30px': '21px',   # Table cells, body text
    '28px': '20px',   # Input fields
    '27px': '19px',   # Research details
    '26px': '18px',   # Calc values
    '24px': '17px',   # Labels
    '20px': '14px',   # Buttons
    '18px': '13px',   # Small text
    '16px': '12px',   # Tiny text
    '14px': '11px',   # Minimum readable
}

def reduce_font_sizes(html_content):
    """Replace all font-size values with scaled-down versions."""

    for old_size, new_size in FONT_SIZE_MAP.items():
        # Match font-size: XXpx; or font-size:XXpx;
        pattern = rf'(font-size:\s*){re.escape(old_size)}'
        replacement = rf'\g<1>{new_size}'
        html_content = re.sub(pattern, replacement, html_content)

    return html_content

def main():
    import sys

    # Accept file path as command line argument
    if len(sys.argv) > 1:
        input_file = sys.argv[1]
        output_file = sys.argv[1]
        backup_file = f'{sys.argv[1]}.backup.fontsize'
    else:
        input_file = 'index.html'
        output_file = 'index.html'
        backup_file = 'index.html.backup.fontsize'

    print("=" * 60)
    print("FONT SIZE REDUCTION SCRIPT")
    print("=" * 60)
    print()
    print(f"Reading {input_file}...")

    with open(input_file, 'r', encoding='utf-8') as f:
        html_content = f.read()

    print(f"Original file size: {len(html_content)} characters")
    print()

    # Create backup
    print(f"Creating backup: {backup_file}")
    with open(backup_file, 'w', encoding='utf-8') as f:
        f.write(html_content)

    # Apply font size reductions
    print()
    print("Applying font size reductions...")
    updated_content = reduce_font_sizes(html_content)

    # Count changes
    changes_made = 0
    for old_size, new_size in FONT_SIZE_MAP.items():
        old_count = html_content.count(f'font-size: {old_size}') + html_content.count(f'font-size:{old_size}')
        new_count = updated_content.count(f'font-size: {new_size}') + updated_content.count(f'font-size:{new_size}')
        if new_count > 0:
            print(f"  {old_size} -> {new_size}: {new_count} occurrences")
            changes_made += new_count

    print()
    print(f"Total changes: {changes_made}")

    # Write updated file
    print()
    print(f"Writing updated file: {output_file}")
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(updated_content)

    print()
    print("=" * 60)
    print("[OK] Font sizes reduced successfully!")
    print("=" * 60)
    print()
    print("Changes applied:")
    print("  - Table headers: 33px -> 23px")
    print("  - Table cells: 30px -> 21px")
    print("  - Modal title: 36px -> 25px")
    print("  - Calculator inputs: 28px -> 20px")
    print("  - Total price: 42px -> 29px")
    print("  - Buttons: 20px -> 14px")
    print()
    print(f"Backup saved to: {backup_file}")
    print(f"To revert: copy backup file over {output_file}")
    print()

if __name__ == '__main__':
    main()
