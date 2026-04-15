import os
import ast
import glob
import re

def analyze_python_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except:
        return None
    
    lines = content.split('\n')
    total_lines = len(lines)
    if total_lines == 0:
        return None
        
    code_lines = 0
    comment_lines = 0
    blank_lines = 0
    
    in_multiline_string = False
    
    try:
        tree = ast.parse(content)
        # count docstrings
        docstrings = [node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef, ast.Module)) and ast.get_docstring(node)]
        docstring_count = len(docstrings)
        total_defs = len([node for node in ast.walk(tree) if isinstance(node, (ast.FunctionDef, ast.ClassDef, ast.AsyncFunctionDef))])
    except SyntaxError:
        docstring_count = 0
        total_defs = 0

    return {
        'file': filepath,
        'docstring_count': docstring_count,
        'total_defs': total_defs,
        'total_lines': total_lines
    }

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
        
    # very rough typescript comment counter
    comment_lines = 0
    in_block = False
    for line in lines:
        l = line.strip()
        if in_block:
            comment_lines += 1
            if '*/' in l:
                in_block = False
        else:
            if l.startswith('//'):
                comment_lines += 1
            elif l.startswith('/*'):
                comment_lines += 1
                if '*/' not in l:
                    in_block = True
                    
    # functions roughly
    defs = len(re.findall(r'\b(function|class|interface|type)\b', content))
    jsdocs = len(re.findall(r'/\*\*[\s\S]*?\*/', content))
    
    return {
        'file': filepath,
        'docstring_count': jsdocs, # mapping jsdoc to docstring
        'total_defs': defs,
        'total_lines': total_lines,
        'comment_lines': comment_lines
    }

def main():
    skip_dirs = ['node_modules', '.git', 'vendor', 'docs', 'venv', 'env', '.venv']
    
    py_stats = []
    ts_stats = []
    
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in skip_dirs and not d.startswith('.')]
        
        for file in files:
            filepath = os.path.join(root, file)
            # Skip test files and config files
            if 'test' in file.lower() or file.startswith('.') or file.endswith('config.js') or file.endswith('config.ts'):
                continue
                
            if file.endswith('.py'):
                stat = analyze_python_file(filepath)
                if stat: py_stats.append(stat)
            elif file.endswith('.ts') or file.endswith('.tsx') or file.endswith('.js'):
                stat = analyze_ts_file(filepath)
                if stat: ts_stats.append(stat)

    print("=== Python Files ===")
    py_low_docs = [s for s in py_stats if s['total_defs'] > 0 and (s['docstring_count'] / s['total_defs']) < 0.5]
    py_high_docs = [s for s in py_stats if s['total_defs'] > 0 and (s['docstring_count'] / s['total_defs']) >= 0.5]
    
    print(f"Total Python files analyzing: {len(py_stats)}")
    print(f"Files with good docstring coverage (>= 50%): {len(py_high_docs)}")
    print(f"Files with poor docstring coverage (< 50%): {len(py_low_docs)}")
    
    print("\nTop 5 Python files needing comments:")
    py_low_docs.sort(key=lambda x: x['total_defs'] - x['docstring_count'], reverse=True)
    for s in py_low_docs[:5]:
        print(f"  {s['file']}: {s['docstring_count']}/{s['total_defs']} documented ({s['total_lines']} lines)")

    print("\n=== TypeScript/JavaScript Files ===")
    ts_low_docs = [s for s in ts_stats if s['total_defs'] > 0 and (s['docstring_count'] / s['total_defs']) < 0.2]
    ts_high_docs = [s for s in ts_stats if s['total_defs'] > 0 and (s['docstring_count'] / s['total_defs']) >= 0.2]
    
    print(f"Total TS/JS files analyzing: {len(ts_stats)}")
    print(f"Files with good JSDoc coverage: {len(ts_high_docs)}")
    print(f"Files with poor JSDoc coverage: {len(ts_low_docs)}")
    
    print("\nTop 5 TS/JS files needing comments:")
    ts_low_docs.sort(key=lambda x: x['total_defs'] - x['docstring_count'], reverse=True)
    for s in ts_low_docs[:5]:
        print(f"  {s['file']}: {s['docstring_count']}/{s['total_defs']} documented ({s['total_lines']} lines)")

if __name__ == '__main__':
    main()
