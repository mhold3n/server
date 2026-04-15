import os
import re

def analyze_ts_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return None
        
    lines = content.split('\n')
    total_lines = len(lines)
    if total_lines == 0:
        return None
                    
    defs = len(re.findall(r'\b(function|class|interface|type)\b', content))
    jsdocs = len(re.findall(r'/\*\*[\s\S]*?\*/', content))
    
    return {
        'file': filepath,
        'docstring_count': jsdocs,
        'total_defs': defs,
        'total_lines': total_lines
    }

ts_stats = []
skip_dirs = ['node_modules', '.git', 'vendor', 'docs', 'dist', 'build', 'assets', '.svelte-kit']

for root, dirs, files in os.walk('.'):
    dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
    
    for file in files:
        filepath = os.path.join(root, file)
        # Skip generated, test files, and config files
        if 'test' in file.lower() or 'spec' in file.lower() or '.generated.' in file.lower() or file.startswith('.') or file.endswith('config.js') or file.endswith('config.ts') or file.endswith('.js') or file.endswith('.d.ts'):
            continue
            
        if file.endswith('.ts') or file.endswith('.tsx') or file.endswith('.svelte'):
            stat = analyze_ts_file(filepath)
            if stat: ts_stats.append(stat)

ts_low_docs = [s for s in ts_stats if s['total_defs'] > 0 and (s['docstring_count'] / s['total_defs']) < 0.2]
ts_low_docs.sort(key=lambda x: x['total_defs'] - x['docstring_count'], reverse=True)

print("Top 15 TypeScript source files needing comments:")
for s in ts_low_docs[:15]:
    print(f"  {s['file']}: {s['docstring_count']}/{s['total_defs']} documented ({s['total_lines']} lines)")
