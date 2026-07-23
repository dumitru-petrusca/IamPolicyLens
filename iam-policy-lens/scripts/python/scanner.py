import ast
import os
import sys
import jedi
import pathlib
import traceback
import jedi.parser_utils

# Monkeypatch jedi.parser_utils.get_parso_cache_node to prevent KeyError with PosixPath on Python 3.14
_orig_get_parso_cache_node = jedi.parser_utils.get_parso_cache_node

def _patched_get_parso_cache_node(grammar, path):
    try:
        return _orig_get_parso_cache_node(grammar, path)
    except KeyError:
        if isinstance(path, pathlib.Path):
            try:
                return _orig_get_parso_cache_node(grammar, str(path))
            except KeyError:
                pass
        elif isinstance(path, str):
            try:
                return _orig_get_parso_cache_node(grammar, pathlib.Path(path))
            except KeyError:
                pass
        raise

jedi.parser_utils.get_parso_cache_node = _patched_get_parso_cache_node

import concurrent.futures
import multiprocessing

from gapic import GapicCall, clean_gapic_fqn, isRelevantImport
from typing import List, Optional, Tuple
from credentials import trace_credentials, extract_credentials_from_call


EXCLUDE_DIRS = {".venv", "venv", ".git", ".mypy_cache", "__pycache__", "build", "dist", "node_modules"}

# Worker-local storage
_worker_project = None
_worker_env = None

def _init_worker(sources_path: str, python_env: Optional[str]):
    global _worker_project, _worker_env
    import jedi
    _worker_project = jedi.Project(sources_path)
    _worker_env = None
    if python_env:
        try:
            _worker_env = jedi.create_environment(python_env, safe=False)
        except Exception:
            pass

def _scan_file_wrapper(file_path: str) -> List[GapicCall]:
    global _worker_project, _worker_env
    return scan_file(file_path, _worker_project, _worker_project.path, _worker_env)


def find_gapic_calls(sources_path: str, python_env: str = None, verbose: bool = False) -> List[GapicCall]:
    """
    Analyzes a Python project using Jedi and returns a list of GapicCall objects.
    Uses multi-processing to parallelize the scan across multiple CPU cores.
    """
    
    # 1. Collect all scannable python files first
    python_files = []
    for root, dirs, files in os.walk(sources_path):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for file in files:
            if file.endswith(".py"):
                python_files.append(os.path.join(root, file))
                
    total_files = len(python_files)
    print(f"Found {total_files} Python files to analyze.", file=sys.stderr)
    
    num_workers = min(multiprocessing.cpu_count(), 8)
    print(f"Analyzing in parallel using {num_workers} worker processes...", file=sys.stderr)
    
    all_calls = []
    
    # 2. Execute in parallel using ProcessPoolExecutor
    with concurrent.futures.ProcessPoolExecutor(
        max_workers=num_workers,
        initializer=_init_worker,
        initargs=(sources_path, python_env)
    ) as executor:
        future_to_file = {executor.submit(_scan_file_wrapper, f): f for f in python_files}
        
        completed = 0
        for future in concurrent.futures.as_completed(future_to_file):
            completed += 1
            if verbose:
                percentage = (completed / total_files) * 100
                sys.stderr.write(f"\rAnalyzing file {completed}/{total_files} ({percentage:.1f}%) ...")
                sys.stderr.flush()
            
            try:
                calls = future.result()
                if calls:
                    all_calls.extend(calls)
            except Exception as e:
                file_path = future_to_file[future]
                if verbose:
                    print(f"\nError in worker scanning {file_path}: {e}", file=sys.stderr)
                
    if verbose:
        sys.stderr.write("\n")
        sys.stderr.flush()
    return all_calls


def scan_file(file_path: str, project: jedi.Project, sources_path: str, env) -> List[GapicCall]:
    calls = []
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
            lines = content.splitlines()
        tree = ast.parse(content)
        script = jedi.Script(path=file_path, project=project, environment=env)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                call = _resolve_gapic_call(node, script, file_path, lines, tree)
                if call:
                    calls.append(call)
    except Exception as e:
        print(f"Error scanning {file_path}: {e}", file=sys.stderr)
        traceback.print_exc(file=sys.stderr)
    return calls



def _resolve_gapic_call(node: ast.Call, script: jedi.Script, file_path: str, lines: List[str], tree: ast.AST) -> Optional[GapicCall]:
    if not (hasattr(node.func, 'end_lineno') and hasattr(node.func, 'end_col_offset')):
        return None
        
    # Point Jedi to the end of the callee name to resolve the method
    line = node.func.end_lineno
    col = node.func.end_col_offset - 1
    try:
        inferences = script.infer(line, col)
    except Exception:
        return None
    
    for inf in inferences:
        fqn = inf.full_name
        if fqn:
            fqn = clean_gapic_fqn(fqn)
        if fqn and isRelevantImport(fqn):
            parent_context = inf.parent()
            client_fqn = clean_gapic_fqn(parent_context.full_name) if parent_context else None
            
            # Trace the credentials used for the client depending on if it's a class instantiation or method call
            credentials_info = None
            if inf.type == 'class':
                credentials_info = extract_credentials_from_call(node, script, tree)
            elif isinstance(node.func, ast.Attribute):
                credentials_info = trace_credentials(node.func.value, script, tree)
                
            return GapicCall(
                fullname=fqn,
                file_path=file_path,
                line=node.lineno,
                source_line=lines[node.lineno - 1].strip(),
                resolution="jedi",
                client_fullname=client_fqn,
                credentials=credentials_info
            )
            
    return None
