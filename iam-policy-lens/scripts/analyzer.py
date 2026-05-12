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
    python scripts/analyzer.py <path_to_project>
    python scripts/analyzer.py /Users/petrusca/Google/adk-samples/python/agents/data-science
"""
import os
import sys
import time

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import mypy_scanner

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python scripts/analyzer.py <path_to_project> [jedi|mypy] [python_env_path]")
        sys.exit(1)
        
    project_path = sys.argv[1]
    engine = sys.argv[2] if len(sys.argv) >= 3 else "jedi"
    python_env = sys.argv[3] if len(sys.argv) >= 4 else None
    
    print(f"Scanning: {project_path} for GAPIC calls using {engine}")
    if python_env:
        print(f"Using Python environment: {python_env}")
        
    start_time = time.time()
    if engine == "jedi":
        import jedi_scanner
        raw_calls = jedi_scanner.find_gapic_calls(project_path, python_env)
    else:
        raw_calls = mypy_scanner.find_gapic_calls(project_path, python_env)
    elapsed_time = time.time() - start_time
    
    if raw_calls:
        from collections import defaultdict
        grouped_calls = defaultdict(list)
        for call in raw_calls:
            full_path = os.path.abspath(call.file_path)
            grouped_calls[full_path].append((call.fullname, call.line, call.source_line, call.resolution))
            
        for full_path, calls in sorted(grouped_calls.items()):
            print(f"\n📄 File: {full_path}")
            rel_path = os.path.relpath(full_path, project_path) if os.path.isabs(full_path) else full_path
            for i, (fullname, line, source_line, resolution) in enumerate(sorted(calls, key=lambda x: x[1])):
                if i > 0:
                    print()
                print(f"     {rel_path}:{line}: `{source_line}`")
                print(f"     Method: {fullname} [{resolution}]")
    else:
        print("No relevant GAPIC calls found.")
        
    print(f"\nScan completed in {elapsed_time:.2f} seconds.")
    print("====================================================")
