#!/usr/bin/env python3
"""
Comprehensive Script & Query Analyzer
Analyzes all Python scripts and SQL queries in your project.
Provides recommendations for cleanup, organization, and optimization.
"""

import os
import re
from collections import defaultdict
from pathlib import Path

# Configuration
PROJECT_DIR = r'E:\Python Project'
SCRIPTS_DIR = os.path.join(PROJECT_DIR, 'scripts')
QUERIES_DIR = os.path.join(PROJECT_DIR, 'queries')
ARCHIVE_DIR = os.path.join(SCRIPTS_DIR, 'Archive')


def analyze_python_script(filepath):
    """Analyze a Python script and extract key information"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    analysis = {
        'filepath': filepath,
        'filename': os.path.basename(filepath),
        'lines': len(content.split('\n')),
        'size_kb': os.path.getsize(filepath) / 1024,
        'has_main': '__main__' in content,
        'imports': [],
        'tables_used': set(),
        'views_used': set(),
        'api_endpoints': [],
        'description': '',
        'is_orchestrator': False,
        'is_update_script': False,
        'is_utility': False,
        'calls_other_scripts': []
    }
    
    # Extract docstring
    docstring_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
    if docstring_match:
        analysis['description'] = docstring_match.group(1).strip()[:200]
    
    # Find imports
    import_pattern = r'^(?:from|import)\s+(\w+)'
    analysis['imports'] = list(set(re.findall(import_pattern, content, re.MULTILINE)))
    
    # Find table references
    table_patterns = [
        r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        r'JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        r'INTO\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        r'TABLE\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        r'UPDATE\s+([a-zA-Z_][a-zA-Z0-9_]*)',
    ]
    for pattern in table_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            if not match.upper() in ['IF', 'NOT', 'EXISTS', 'OR', 'REPLACE']:
                analysis['tables_used'].add(match.lower())
    
    # Find view references (views often start with v_)
    view_pattern = r'\b(v_[a-zA-Z_][a-zA-Z0-9_]*)'
    analysis['views_used'] = set(re.findall(view_pattern, content, re.IGNORECASE))
    
    # Find ESI API endpoints
    api_pattern = r'/v\d+/([a-zA-Z_/{}]+)'
    analysis['api_endpoints'] = list(set(re.findall(api_pattern, content)))
    
    # Classify script type
    filename_lower = analysis['filename'].lower()
    if 'run_' in filename_lower or 'orchestrat' in content.lower():
        analysis['is_orchestrator'] = True
    if 'update_' in filename_lower or 'fetch_' in filename_lower:
        analysis['is_update_script'] = True
    if 'util' in filename_lower or 'helper' in filename_lower or 'token_manager' in filename_lower:
        analysis['is_utility'] = True
    
    # Find calls to other scripts
    script_call_pattern = r'(?:import|from)\s+([a-zA-Z_][a-zA-Z0-9_]*)'
    potential_scripts = re.findall(script_call_pattern, content)
    for script in potential_scripts:
        if script not in ['os', 'sys', 'json', 'sqlite3', 'requests', 'time', 'datetime']:
            analysis['calls_other_scripts'].append(script)
    
    return analysis


def analyze_sql_query(filepath):
    """Analyze a SQL query file"""
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    analysis = {
        'filepath': filepath,
        'filename': os.path.basename(filepath),
        'lines': len(content.split('\n')),
        'size_kb': os.path.getsize(filepath) / 1024,
        'tables_used': set(),
        'views_used': set(),
        'description': '',
        'has_cte': 'WITH' in content.upper(),
        'complexity': 'simple'
    }
    
    # Extract comment description (first few lines)
    lines = content.split('\n')
    comment_lines = []
    for line in lines[:10]:
        if line.strip().startswith('--'):
            comment_lines.append(line.strip()[2:].strip())
    analysis['description'] = ' '.join(comment_lines)[:200]
    
    # Find table references
    table_patterns = [
        r'FROM\s+([a-zA-Z_][a-zA-Z0-9_]*)',
        r'JOIN\s+([a-zA-Z_][a-zA-Z0-9_]*)',
    ]
    for pattern in table_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        for match in matches:
            if match.lower().startswith('v_'):
                analysis['views_used'].add(match.lower())
            else:
                analysis['tables_used'].add(match.lower())
    
    # Determine complexity
    cte_count = content.upper().count('WITH')
    join_count = content.upper().count('JOIN')
    subquery_count = content.count('SELECT', 1)  # Exclude first SELECT
    
    if cte_count > 3 or join_count > 5 or subquery_count > 5:
        analysis['complexity'] = 'complex'
    elif cte_count > 1 or join_count > 2 or subquery_count > 2:
        analysis['complexity'] = 'medium'
    
    return analysis


def scan_directory(directory, file_extension, analyzer_func):
    """Scan directory for files and analyze them"""
    results = []
    
    if not os.path.exists(directory):
        print(f"[WARNING] Directory not found: {directory}")
        return results
    
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith(file_extension):
                filepath = os.path.join(root, file)
                try:
                    analysis = analyzer_func(filepath)
                    analysis['is_archived'] = 'Archive' in filepath or 'archive' in filepath
                    results.append(analysis)
                except Exception as e:
                    print(f"[ERROR] Failed to analyze {file}: {e}")
    
    return results


def categorize_scripts(scripts):
    """Categorize scripts by purpose"""
    categories = {
        'orchestration': [],
        'market_updates': [],
        'character_updates': [],
        'static_updates': [],
        'utilities': [],
        'analysis': [],
        'archived': [],
        'other': []
    }
    
    for script in scripts:
        if script['is_archived']:
            categories['archived'].append(script)
        elif script['is_orchestrator']:
            categories['orchestration'].append(script)
        elif script['is_utility']:
            categories['utilities'].append(script)
        elif 'market' in script['filename'].lower():
            categories['market_updates'].append(script)
        elif 'character' in script['filename'].lower():
            categories['character_updates'].append(script)
        elif 'inv_' in script['filename'].lower() or 'sde' in script['filename'].lower():
            categories['static_updates'].append(script)
        elif 'generate' in script['filename'].lower() or 'analyze' in script['filename'].lower():
            categories['analysis'].append(script)
        else:
            categories['other'].append(script)
    
    return categories


def print_script_report(scripts):
    """Print comprehensive script analysis report"""
    print("\n" + "=" * 80)
    print("PYTHON SCRIPTS ANALYSIS")
    print("=" * 80)
    
    # Categorize
    categories = categorize_scripts(scripts)
    
    # Overall stats
    active_scripts = [s for s in scripts if not s['is_archived']]
    total_lines = sum(s['lines'] for s in active_scripts)
    total_size = sum(s['size_kb'] for s in active_scripts)
    
    print(f"\nTotal Scripts: {len(scripts)}")
    print(f"  • Active: {len(active_scripts)}")
    print(f"  • Archived: {len(categories['archived'])}")
    print(f"  • Total Lines: {total_lines:,}")
    print(f"  • Total Size: {total_size:.1f} KB")
    
    # By category
    print("\n" + "=" * 80)
    print("SCRIPTS BY CATEGORY")
    print("=" * 80)
    
    for category_name, category_scripts in categories.items():
        if not category_scripts or category_name == 'archived':
            continue
        
        print(f"\n📂 {category_name.upper().replace('_', ' ')} ({len(category_scripts)} scripts)")
        print("-" * 80)
        
        for script in sorted(category_scripts, key=lambda x: x['filename']):
            print(f"\n  📄 {script['filename']}")
            print(f"     Lines: {script['lines']}, Size: {script['size_kb']:.1f} KB")
            
            if script['description']:
                desc = script['description'][:100]
                print(f"     Description: {desc}...")
            
            if script['tables_used']:
                tables = sorted(script['tables_used'])[:5]
                print(f"     Tables: {', '.join(tables)}")
                if len(script['tables_used']) > 5:
                    print(f"             ... and {len(script['tables_used']) - 5} more")
            
            if script['api_endpoints']:
                endpoints = script['api_endpoints'][:3]
                print(f"     API Endpoints: {', '.join(endpoints)}")
    
    # Archived scripts
    if categories['archived']:
        print("\n" + "=" * 80)
        print("ARCHIVED SCRIPTS (in Archive/ folder)")
        print("=" * 80)
        print(f"\nFound {len(categories['archived'])} archived scripts")
        for script in sorted(categories['archived'], key=lambda x: x['filename']):
            print(f"  • {script['filename']} ({script['lines']} lines)")


def print_query_report(queries):
    """Print SQL query analysis report"""
    print("\n" + "=" * 80)
    print("SQL QUERIES ANALYSIS")
    print("=" * 80)
    
    if not queries:
        print("\nNo SQL query files found in queries/ directory")
        return
    
    # Overall stats
    total_lines = sum(q['lines'] for q in queries)
    total_size = sum(q['size_kb'] for q in queries)
    
    print(f"\nTotal Queries: {len(queries)}")
    print(f"  • Total Lines: {total_lines:,}")
    print(f"  • Total Size: {total_size:.1f} KB")
    
    # By complexity
    by_complexity = defaultdict(list)
    for query in queries:
        by_complexity[query['complexity']].append(query)
    
    print("\n" + "=" * 80)
    print("QUERIES BY COMPLEXITY")
    print("=" * 80)
    
    for complexity in ['simple', 'medium', 'complex']:
        if complexity in by_complexity:
            print(f"\n📊 {complexity.upper()} ({len(by_complexity[complexity])} queries)")
            print("-" * 80)
            
            for query in sorted(by_complexity[complexity], key=lambda x: x['filename']):
                print(f"\n  📄 {query['filename']}")
                print(f"     Lines: {query['lines']}, Size: {query['size_kb']:.1f} KB")
                print(f"     Has CTEs: {'Yes' if query['has_cte'] else 'No'}")
                
                if query['description']:
                    desc = query['description'][:100]
                    print(f"     Description: {desc}")
                
                if query['tables_used']:
                    tables = sorted(query['tables_used'])[:5]
                    print(f"     Tables: {', '.join(tables)}")
                
                if query['views_used']:
                    views = sorted(query['views_used'])[:5]
                    print(f"     Views: {', '.join(views)}")


def print_dependency_summary(scripts, queries):
    """Print summary of what depends on what"""
    print("\n" + "=" * 80)
    print("DEPENDENCY SUMMARY")
    print("=" * 80)
    
    # Most used tables
    table_usage = defaultdict(int)
    for script in scripts:
        if not script['is_archived']:
            for table in script['tables_used']:
                table_usage[table] += 1
    for query in queries:
        for table in query['tables_used']:
            table_usage[table] += 1
    
    print("\n📊 MOST USED TABLES:")
    for table, count in sorted(table_usage.items(), key=lambda x: x[1], reverse=True)[:10]:
        print(f"   • {table:<30} used by {count} files")
    
    # Most used views
    view_usage = defaultdict(int)
    for query in queries:
        for view in query['views_used']:
            view_usage[view] += 1
    
    if view_usage:
        print("\n📊 MOST USED VIEWS:")
        for view, count in sorted(view_usage.items(), key=lambda x: x[1], reverse=True)[:10]:
            print(f"   • {view:<30} used by {count} queries")


def print_recommendations(scripts, queries):
    """Print cleanup and optimization recommendations"""
    print("\n" + "=" * 80)
    print("RECOMMENDATIONS")
    print("=" * 80)
    
    active_scripts = [s for s in scripts if not s['is_archived']]
    
    # Large scripts
    large_scripts = [s for s in active_scripts if s['lines'] > 500]
    if large_scripts:
        print("\n⚠️  LARGE SCRIPTS (>500 lines) - Consider splitting:")
        for script in sorted(large_scripts, key=lambda x: x['lines'], reverse=True):
            print(f"   • {script['filename']}: {script['lines']} lines")
    
    # Duplicate functionality
    update_market = [s for s in active_scripts if 'market' in s['filename'].lower() and 'update' in s['filename'].lower()]
    if len(update_market) > 3:
        print("\n⚠️  MULTIPLE MARKET UPDATE SCRIPTS:")
        for script in update_market:
            print(f"   • {script['filename']}")
        print("   Consider consolidating or archiving obsolete versions")
    
    # Complex queries
    complex_queries = [q for q in queries if q['complexity'] == 'complex']
    if len(complex_queries) > 5:
        print("\n💡 COMPLEX QUERIES - Consider creating views:")
        for query in complex_queries[:5]:
            print(f"   • {query['filename']}")
    
    # Queries that could be views
    frequently_used = [q for q in queries if len(q['tables_used']) > 3 and q['has_cte']]
    if frequently_used:
        print("\n💡 QUERIES THAT COULD BE VIEWS:")
        for query in frequently_used[:5]:
            print(f"   • {query['filename']} - uses {len(q['tables_used'])} tables")
    
    print("\n✅ KEEP DOING:")
    print("   • Scripts organized in categories (market, character, static)")
    print("   • Archived folder for old versions")
    print("   • Clear naming conventions (update_*, run_*, generate_*)")


def main():
    print("=" * 80)
    print("EVE ONLINE - COMPREHENSIVE SCRIPT & QUERY ANALYZER")
    print("=" * 80)
    print("\nAnalyzing all Python scripts and SQL queries...")
    print(f"Project Directory: {PROJECT_DIR}")
    print("=" * 80)
    
    # Scan scripts
    print("\n[1/2] Scanning Python scripts...")
    scripts = scan_directory(SCRIPTS_DIR, '.py', analyze_python_script)
    print(f"      Found {len(scripts)} Python scripts")
    
    # Scan queries
    print("\n[2/2] Scanning SQL queries...")
    queries = scan_directory(QUERIES_DIR, '.sql', analyze_sql_query)
    print(f"      Found {len(queries)} SQL queries")
    
    # Print reports
    print_script_report(scripts)
    print_query_report(queries)
    print_dependency_summary(scripts, queries)
    print_recommendations(scripts, queries)
    
    print("\n" + "=" * 80)
    print("✅ Analysis complete!")
    print("=" * 80)


if __name__ == '__main__':
    main()