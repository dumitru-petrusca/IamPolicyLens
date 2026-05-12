import ast
import os
import jedi
from gapic import GapicCall, clean_gapic_fullname
from typing import List

imports = ["google.cloud", "google.genai", "vertexai", "google.adk"]

def isRelevantImport(importName: str) -> bool:
    return any(imp in importName for imp in imports)

def find_gapic_calls(sources_path: str, python_env: str = None) -> List[GapicCall]:
    """
    Analyzes a Python project using Jedi and returns a list of GapicCall objects.
    """
    all_calls = []
    
    env = None
    if python_env:
        try:
            # Remove Nuitka environment variables that might break subprocesses
            old_path = os.environ.pop('PYTHONPATH', None)
            old_home = os.environ.pop('PYTHONHOME', None)
            
            try:
                env = jedi.create_environment(python_env)
                print(f"Using Jedi environment: {python_env}")
            finally:
                # Restore them
                if old_path is not None: os.environ['PYTHONPATH'] = old_path
                if old_home is not None: os.environ['PYTHONHOME'] = old_home
        except Exception as e:
            print(f"Error creating Jedi environment for {python_env}: {e}")
            print("Falling back to default environment.")
            
    project = jedi.Project(sources_path)
    
    exclude_dirs = {".venv", "venv", ".git", ".mypy_cache", "__pycache__", "build", "dist", "node_modules"}
    
    for root, dirs, files in os.walk(sources_path):
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        for file in files:
            if file.endswith(".py"):
                file_path = os.path.join(root, file)
                all_calls.extend(scan_file(file_path, project, sources_path, env))
                
    return all_calls

def scan_file(file_path: str, project: jedi.Project, sources_path: str, env) -> List[GapicCall]:
    calls = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.splitlines()
            
        tree = ast.parse(content)
        script = jedi.Script(content, path=file_path, project=project, environment=env)
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if hasattr(node.func, 'end_lineno') and hasattr(node.func, 'end_col_offset'):
                    # Point Jedi to the end of the callee name to resolve the method
                    line = node.func.end_lineno
                    col = node.func.end_col_offset - 1
                    
                    inferences = script.infer(line, col)
                    
                    for inf in inferences:
                        full_name = inf.full_name
                        if full_name:
                            full_name = clean_gapic_fullname(full_name)
                        if full_name and isRelevantImport(full_name):
                            calls.append(GapicCall(
                                fullname=full_name,
                                file_path=file_path,
                                line=node.lineno,
                                source_line=lines[node.lineno - 1].strip(),
                                resolution="jedi"
                            ))
                            break # Found one valid inference, skip to next call
                            
    except Exception as e:
        print(f"Error scanning {file_path}: {e}")
        
    return calls
