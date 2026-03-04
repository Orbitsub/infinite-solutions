import requests
import sqlite3
import time
import os
from datetime import datetime, timezone, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB_PATH = os.path.join(SCRIPT_DIR, 'mydatabase.db')
ESI_BASE_URL = 'https://esi.evetech.net/latest'
THE_FORGE_REGION = 10000002


# CONFIG
DEEP_SCAN = False
ANALYZE_COUNT = 20 if not DEEP_SCAN else 100
MIN_VALUE = 5000000
MIN_ITEMS = 1
SKIP_BLUEPRINTS = True  # Skip all blueprint contracts
SKIP_CONTRACTS_WITH_RIGS = True  # Skip any contract containing rigs (safest)

def get_all_public_contracts(region_id):
    """Get ALL public contracts from all pages."""
    all_contracts = []
    page = 1
    
    while True:
        url = f'{ESI_BASE_URL}/contracts/public/{region_id}/'
        params = {'page': page}
        
        print(f"Fetching page {page}...")
        response = requests.get(url, params=params)
        
        if response.status_code == 200:
            contracts = response.json()
            
            if not contracts:
                break
            
            all_contracts.extend(contracts)
            print(f"  Got {len(contracts)} contracts (total so far: {len(all_contracts)})")
            
            x_pages = response.headers.get('x-pages')
            if x_pages and page >= int(x_pages):
                break
            
            page += 1
            time.sleep(0.2)
        else:
            print(f"Error on page {page}: {response.status_code}")
            break
    
    return all_contracts

def get_contract_items(contract_id):
    """Get items in a specific contract."""
    url = f'{ESI_BASE_URL}/contracts/public/items/{contract_id}/'
    
    response = requests.get(url)
    
    if response.status_code == 200:
        return response.json()
    elif response.status_code == 404:
        return []
    else:
        time.sleep(1)
        return []

def get_item_info(type_id):
    """Get item name and group from local database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT t.type_name, g.group_name
        FROM inv_types t
        LEFT JOIN inv_groups g ON t.group_id = g.group_id
        WHERE t.type_id = ?
    ''', (type_id,))
    result = cursor.fetchone()
    conn.close()
    if result:
        return {'name': result[0], 'group': result[1] or 'Unknown'}
    return {'name': f"Unknown Item {type_id}", 'group': 'Unknown'}

def get_market_price(type_id):
    """Get Jita sell price from local database."""
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        SELECT MIN(price) 
        FROM market_orders 
        WHERE type_id = ? 
        AND is_buy_order = 0 
        AND location_id = 60003760
    ''', (type_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result and result[0] else 0

def is_rig(item_name, item_group):
    """Check if item is a rig."""
    # Check both name and group for rig indicators
    rig_indicators = ['Rig ', ' Rig', 'Calibration', 'Astronautic', 'Anchor', 
                      'Capacitor Control Circuit', 'Core Defense', 'Semiconductor',
                      'Engine Thermal', 'Auxiliary Thrusters', 'Dynamic Fuel Valve']
    
    return any(indicator in item_name for indicator in rig_indicators) or \
           any(indicator in item_group for indicator in rig_indicators)

def analyze_contract(contract):
    """Analyze a single contract for profitability."""
    contract_id = contract['contract_id']
    date_issued = contract.get('date_issued')
    title = contract.get('title', 'No title')
    
    print(f"  Contract {contract_id}")
    print(f"    Title: '{title}'")
    print(f"    Date: {date_issued}")
    
    items = get_contract_items(contract_id)
    
    if not items:
        print(f"    No items found")
        return None
    
    print(f"    Items: {len(items)}")
    
    if len(items) < MIN_ITEMS:
        print(f"    Skipping (less than {MIN_ITEMS} items)")
        return None
    
    # Check for problematic items
    has_blueprints = False
    has_bpc = False
    has_rigs = False
    total_market_value = 0
    item_details = []
    
    for item in items:
        type_id = item['type_id']
        quantity = item['quantity']
        is_blueprint_copy = item.get('is_blueprint_copy', False)
        is_included = item.get('is_included', True)
        
        item_info = get_item_info(type_id)
        item_name = item_info['name']
        item_group = item_info['group']
        
        # Check item type
        is_blueprint_item = 'Blueprint' in item_group or 'Blueprint' in item_name
        is_rig_item = is_rig(item_name, item_group)
        
        # Track what's in the contract
        if is_blueprint_item:
            has_blueprints = True
            if is_blueprint_copy:
                has_bpc = True
                item_name += ' (COPY)'
            else:
                item_name += ' (ORIGINAL)'
        
        if is_rig_item:
            has_rigs = True
            item_name += ' [RIG]'
        
        # Mark if item is fitted
        if not is_included:
            item_name += ' [FITTED]'
        
        market_price = get_market_price(type_id)
        
        # Adjust price for BPCs
        if is_blueprint_copy:
            market_price = market_price * 0.05
        
        # Rigs have ZERO value if fitted
        if is_rig_item and not is_included:
            market_price = 0
        
        item_value = market_price * quantity
        
        total_market_value += item_value
        item_details.append({
            'name': item_name,
            'quantity': quantity,
            'unit_price': market_price,
            'total_value': item_value,
            'is_bpc': is_blueprint_copy,
            'is_rig': is_rig_item,
            'is_fitted': not is_included,
            'group': item_group
        })
        
        time.sleep(0.05)
    
    print(f"    Market value: {total_market_value:,.0f} ISK")
    
    # Skip if configured to skip blueprints
    if SKIP_BLUEPRINTS and has_blueprints:
        print(f"    Skipping (contains blueprints)")
        return None
    
    # Skip if contract contains ANY rigs (almost always fitted to ships)
    if SKIP_CONTRACTS_WITH_RIGS and has_rigs:
        print(f"    Skipping (contains rigs - likely fitted ship)")
        return None
    
    # Warnings
    if has_bpc:
        print(f"    ⚠️  WARNING: Contains Blueprint Copies (low value)")
    
    return {
        'contract_id': contract_id,
        'date_issued': date_issued,
        'title': title,
        'issuer_id': contract.get('issuer_id'),
        'total_items': len(items),
        'market_value': total_market_value,
        'items': item_details,
        'has_blueprints': has_blueprints,
        'has_bpc': has_bpc,
        'has_rigs': has_rigs
    }

def format_date_for_search(date_str):
    """Convert ISO date to human-readable format."""
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m-%d %H:%M UTC')
    except:
        return date_str

def main():
    print("=" * 60)
    print("CONTRACT SCANNER")
    print("Mode: DEEP SCAN" if DEEP_SCAN else "Mode: QUICK SCAN")
    print(f"Skip Blueprints: {SKIP_BLUEPRINTS}")
    print(f"Skip Contracts with Rigs: {SKIP_CONTRACTS_WITH_RIGS}")
    print("=" * 60)
    
    contracts = get_all_public_contracts(THE_FORGE_REGION)
    print(f"\nTotal contracts found: {len(contracts)}")
    
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
    
    recent_contracts = []
    for c in contracts:
        if c['type'] == 'item_exchange':
            issued_date = datetime.fromisoformat(c.get('date_issued', '').replace('Z', '+00:00'))
            if issued_date > cutoff_time:
                recent_contracts.append(c)
    
    print(f"Item exchange contracts from last 24h: {len(recent_contracts)}")
    
    opportunities = []
    
    analyze_count = min(ANALYZE_COUNT, len(recent_contracts))
    
    if analyze_count > 0:
        print(f"\nAnalyzing {analyze_count} contracts...")
        print("=" * 60)
        
        for i, contract in enumerate(recent_contracts[:analyze_count], 1):
            print(f"\n[{i}/{analyze_count}]")
            
            analysis = analyze_contract(contract)
            
            if analysis and analysis['market_value'] >= MIN_VALUE:
                opportunities.append(analysis)
                print(f"    *** WORTH CHECKING ***")
    
    print("\n" + "=" * 60)
    print(f"FOUND {len(opportunities)} CONTRACTS WORTH CHECKING")
    print("=" * 60)
    
    if opportunities:
        for opp in sorted(opportunities, key=lambda x: x['market_value'], reverse=True):
            print(f"\n" + "=" * 60)
            print(f"CONTRACT ID: {opp['contract_id']}")
            print("=" * 60)
            print(f"Title: '{opp.get('title', 'No title')}'")
            print(f"Date: {format_date_for_search(opp['date_issued'])}")
            print(f"Market Value: {opp['market_value']:,.0f} ISK")
            print(f"Total Items: {opp['total_items']}")
            
            # Warnings
            if opp.get('has_bpc'):
                print(f"\n⚠️  WARNING: Contains Blueprint Copies (typically low value)")
            if opp.get('has_blueprints') and not opp.get('has_bpc'):
                print(f"\nℹ️  Note: Contains Blueprint Originals (verify value carefully)")
            
            print(f"\nItems in contract:")
            for idx, item in enumerate(opp['items'][:10], 1):
                bpc_indicator = " [BPC]" if item.get('is_bpc') else ""
                fitted_indicator = " [FITTED]" if item.get('is_fitted') else ""
                rig_indicator = " [RIG]" if item.get('is_rig') else ""
                print(f"  {idx}. {item['name']}{bpc_indicator}{rig_indicator}{fitted_indicator} x{item['quantity']}")
                if item['total_value'] > 0:
                    print(f"     Estimated value: {item['total_value']:,.0f} ISK")
            
            if len(opp['items']) > 10:
                print(f"  ... and {len(opp['items']) - 10} more items")
            
            print(f"\nTO FIND IN-GAME:")
            print(f"1. Open Contracts (Alt+N)")
            print(f"2. Filter: The Forge > Jita > Item Exchange")
            print(f"3. Look for contract with:")
            print(f"   - Title: '{opp.get('title', 'No title')}'")
            print(f"   - Date: {format_date_for_search(opp['date_issued'])}")
            print(f"   - Contains: {opp['items'][0]['name']}")
            print(f"4. Check asking price vs estimated value: {opp['market_value']:,.0f} ISK")
    else:
        print("\nNo high-value contracts found in sample.")
        print(f"Minimum value filter: {MIN_VALUE:,.0f} ISK")
        print(f"Minimum items filter: {MIN_ITEMS} items")
        print(f"Skip blueprints: {SKIP_BLUEPRINTS}")
        print(f"Skip contracts with rigs: {SKIP_CONTRACTS_WITH_RIGS}")
        print("\nTips:")
        print("- Try again later (new contracts posted constantly)")
        print("- Set DEEP_SCAN = True for more thorough analysis")
        print("- Set SKIP_CONTRACTS_WITH_RIGS = False to include rigged ships")
        print("- Lower MIN_VALUE to see smaller opportunities")

if __name__ == '__main__':
    main()