"""
Python Cloud Access Scanner
===========================

Problem Statement:
------------------
This script performs static analysis on a Python codebase to identify Google Cloud, Vertex AI, and Google GenAI client library invocations.
The primary goal is to locate and extract these high-level, Pythonic method calls (e.g., `google.cloud.storage.Client.create_bucket`).

How It Works:
-------------
1. GAPIC Call Extraction (gapic.py): 
    The scanner uses `mypy.build` to generate an Abstract Syntax Tree (AST) of the target project, which handles tricky type-resolution paths.
    It walks the AST looking for `CallExpr` nodes and traces back nested `MemberExpr` chains to resolve fully qualified import names.

How to Run:
-----------
Run the script passing the target repository source path as the first argument:
    .venv/bin/python3 scripts/python/analyzer.py <path_to_project>
#    .venv/bin/python3  scripts/python/analyzer.py /path/to/your/project
    .venv/bin/python3 scripts/python/analyzer.py ./../gcp_cost_optimizer_agent/python
"""
import os
import sys
import time
import json
from dataclasses import asdict

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:", file=sys.stderr)
        print("  python scripts/python/analyzer.py <path_to_project> [python_env_path]", file=sys.stderr)
        sys.exit(1)
        
    project_path = sys.argv[1]
    python_env = sys.argv[2] if len(sys.argv) >= 3 else None
    
    print(f"Scanning: {project_path} for GAPIC calls", file=sys.stderr)
    if python_env:
        print(f"Using Python environment: {python_env}", file=sys.stderr)
        
    start_time = time.time()
    import scanner
    raw_calls = scanner.find_gapic_calls(project_path, python_env)
    elapsed_time = time.time() - start_time
    
    if raw_calls:
        sorted_calls = sorted(raw_calls, key=lambda x: (x.file_path, x.line))
        call_list = []
        for call in sorted_calls:
            d = asdict(call)
            cleaned_d = {k: v for k, v in d.items() if v is not None}
            if 'credentials' in cleaned_d and cleaned_d['credentials'] is not None:
                cred = cleaned_d['credentials']
                if hasattr(cred['provenance'], 'value'):
                    cred['provenance'] = cred['provenance'].value
                if cred.get('identity') and hasattr(cred['identity'], 'value'):
                    cred['identity'] = cred['identity'].value
            call_list.append(cleaned_d)
            
        print(json.dumps(call_list, indent=2))
    else:
        print("[]")
        
    print(f"\nScan completed in {elapsed_time:.2f} seconds.", file=sys.stderr)
    print("====================================================", file=sys.stderr)
