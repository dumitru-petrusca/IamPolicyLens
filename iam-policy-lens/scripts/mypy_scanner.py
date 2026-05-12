from mypy import build
from mypy.options import Options
from mypy.main import create_source_list
from mypy.nodes import Node, Import, ImportFrom, AssignmentStmt, CallExpr, NameExpr, MemberExpr, MypyFile, Expression, TypeInfo
import os
from typing import Dict, List, Tuple, Optional, Set, Any, Callable, Union
from gapic import GapicCall, clean_gapic_fullname

def walk_mypy_tree(tree_node: Node, visitor_func: Callable[[Node], bool]) -> None:
    """Walks the AST. visitor_func should return True to continue, False to stop."""
    seen: Set[int] = set()
    
    def _walk(n: Node) -> bool:
        if id(n) in seen: return True
        seen.add(id(n))
        if not visitor_func(n):
            return False
        for attr in dir(n):
            if attr.startswith('_') or attr in ('accept', 'node', 'type', 'analyzed', 'info', 'defn'): 
                continue
            try:
                val = getattr(n, attr)
                if isinstance(val, Node) or (hasattr(val, 'accept') and hasattr(val, 'line')):
                    if not _walk(val): return False
                elif isinstance(val, list):
                    for item in val:
                        if isinstance(item, Node) or (hasattr(item, 'accept') and hasattr(item, 'line')):
                            if not _walk(item): return False
            except Exception:
                pass
        return True
                
    _walk(tree_node)

def find_all_function_calls(node: Node) -> List[CallExpr]:
    """Finds all function calls in the AST."""
    calls: List[CallExpr] = []
    def visitor(node: Node) -> bool:
        if isinstance(node, CallExpr) and isinstance(node.callee, (NameExpr, MemberExpr)):
            # Skip statically known constructors
            if isinstance(getattr(node.callee, 'node', None), TypeInfo):
                return True
            # Heuristic: if mypy cannot resolve the node, assume capitalized names are constructors
            if node.callee.name and node.callee.name[0].isupper():
                return True
            calls.append(node)
        return True
    walk_mypy_tree(node, visitor)
    return calls

def _get_name_or_member_type(expr: Expression) -> Optional[str]:
    if isinstance(expr, NameExpr):
        return expr.name
    elif isinstance(expr, MemberExpr):
        if isinstance(expr.expr, NameExpr):
            return f"{expr.expr.name}.{expr.name}"
        return expr.name
    return None

def extract_type_from_expr(expr: Expression) -> Optional[str]:
    """Extracts the type from an expression."""
    if isinstance(expr, CallExpr):
        expr = expr.callee
    assigned_type = _get_name_or_member_type(expr)
    if assigned_type:
        return assigned_type
    if hasattr(expr, 'fullname'):
        return expr.fullname
    return None

def find_var_assignment(tree: MypyFile, var_name: str) -> Optional[str]:
    assigned_type: Optional[str] = None
    
    def visitor(n: Node) -> bool:
        nonlocal assigned_type
        if isinstance(n, AssignmentStmt):
            for lvalue in n.lvalues:
                if isinstance(lvalue, NameExpr) and lvalue.name == var_name:
                    if isinstance(n.rvalue, CallExpr):
                        assigned_type = extract_type_from_expr(n.rvalue)
                        if assigned_type:
                            return False
        return True
                
    walk_mypy_tree(tree, visitor)
    return assigned_type

def find_attr_assignment(tree: MypyFile, attr_name: str) -> Optional[str]:
    assigned_type: Optional[str] = None
    
    def visitor(n: Node) -> bool:
        nonlocal assigned_type
        if isinstance(n, AssignmentStmt):
            for lvalue in n.lvalues:
                if isinstance(lvalue, MemberExpr) and lvalue.name == attr_name:
                    if isinstance(n.rvalue, (CallExpr, MemberExpr)):
                        assigned_type = extract_type_from_expr(n.rvalue)
                        if assigned_type:
                            return False
        return True
                
    walk_mypy_tree(tree, visitor)
    return assigned_type

def find_symbol_origin(tree: MypyFile, symbol: str, depth: int = 0) -> Optional[str]:
    """Finds the import origin of a symbol, with recursion for variable assignments."""
    if depth > 5: return None
    
    # 1. Check imports
    for node in tree.defs:
        if isinstance(node, Import):
            for name, as_name in node.ids:
                if as_name:
                    if as_name == symbol: return name
                    if symbol.startswith(f"{as_name}."): return f"{name}{symbol[len(as_name):]}"
                else:
                    last_part = name.split('.')[-1]
                    if name == symbol or last_part == symbol: return name
                    if symbol.startswith(f"{name}."): return symbol
                    if symbol.startswith(f"{last_part}."): return f"{name}{symbol[len(last_part):]}"
        elif isinstance(node, ImportFrom):
            for name, as_name in node.names:
                match_name = as_name or name
                if match_name == symbol: return f"{node.id}.{name}"
                if symbol.startswith(f"{match_name}."): return f"{node.id}.{name}{symbol[len(match_name):]}"
    
    # 2. Check variable assignments if we have dots
    parts = symbol.split('.')
    if len(parts) > 1:
        base = parts[0]
        assigned_base = find_var_assignment(tree, base)
        if assigned_base:
            resolved_base = find_symbol_origin(tree, assigned_base, depth + 1) or assigned_base
            return f"{resolved_base}.{'.'.join(parts[1:])}"
            
    return None

def _get_fullname(node: Optional[Node]) -> Optional[str]:
    """Helper to safely extract the fully qualified name (fullname) from various MyPy node types."""
    if not node: return None
    t = getattr(node, 'type', None)
    if t:
        inner_t = getattr(t, 'type', None)
        if hasattr(inner_t, 'fullname'): return inner_t.fullname
        if hasattr(t, 'fullname'): return t.fullname
    return None

def getImport(callee: Expression, tree: MypyFile) -> Tuple[Optional[str], str]:
    """Gets the import origin of a function call and the resolution method."""
    if isinstance(callee, (MemberExpr, CallExpr)):
        currentExpr: Expression = callee
        suffix_parts: List[str] = []
        
        while isinstance(currentExpr, (MemberExpr, CallExpr)):
            if isinstance(currentExpr, CallExpr):
                currentExpr = currentExpr.callee
                continue

            fullname = _get_fullname(currentExpr.node)
            if fullname and fullname != "Any":
                res_name = f"{fullname}.{'.'.join(suffix_parts)}" if suffix_parts else fullname
                return res_name, "mypy"
                
            assigned_type = find_attr_assignment(tree, currentExpr.name)
            if assigned_type:
                resolved = find_symbol_origin(tree, assigned_type) or assigned_type
                res_name = f"{resolved}.{'.'.join(suffix_parts)}" if suffix_parts else resolved
                return res_name, "fallback"
            
            suffix_parts.insert(0, currentExpr.name)
            currentExpr = currentExpr.expr
            
        if isinstance(currentExpr, NameExpr):
            origin = find_symbol_origin(tree, currentExpr.name)
            curr_node = currentExpr.node
            
            resolved_type: Optional[str] = _get_fullname(curr_node)
            
            if resolved_type and resolved_type != "Any":
                res_name = f"{resolved_type}.{'.'.join(suffix_parts)}" if suffix_parts else resolved_type
                return res_name, "mypy"
                
            assigned_type = find_var_assignment(tree, currentExpr.name)
            if assigned_type:
                resolved_type = find_symbol_origin(tree, assigned_type) or assigned_type
                res_name = f"{resolved_type}.{'.'.join(suffix_parts)}" if suffix_parts else resolved_type
                return res_name, "fallback"
            
            if origin:
                res_name = f"{origin}.{'.'.join(suffix_parts)}" if suffix_parts else origin
                return res_name, "fallback"
            
            base = curr_node.fullname if curr_node and hasattr(curr_node, 'fullname') else currentExpr.name
            res_name = f"{base}.{'.'.join(suffix_parts)}" if suffix_parts else base
            return res_name, "fallback"
    elif isinstance(callee, NameExpr):
        origin = find_symbol_origin(tree, callee.name)
        if origin:
            return origin, "fallback"
        res_name = callee.fullname if hasattr(callee, 'fullname') else callee.name
        return res_name, "mypy" if hasattr(callee, 'fullname') else "fallback"

    return None, "fallback"

def isSourceFile(tree: MypyFile, sources_path: str) -> bool:
    tree_p = tree.path
    if not tree_p: return False
    tree_abs_p = os.path.abspath(tree_p)
    if not os.path.isfile(tree_abs_p): return False
    abs_p = os.path.abspath(sources_path)
    if tree_abs_p == abs_p or tree_abs_p.startswith(abs_p + os.sep):
        return True
    return False

imports: List[str] = ["google.cloud", "google.genai", "vertexai", "google.adk"]

def isRelevantImport(importName: Optional[str]) -> bool:
    return bool(importName and any(imp in importName for imp in imports))


def find_gapic_calls(sources_path: str, python_env: str = None) -> List[GapicCall]:
    """
    Analyzes a Python project and returns a list of GapicCall objects.
    """
    options: Options = Options()
    options.show_traceback = True
    options.ignore_missing_imports = True
    options.preserve_asts = True
    options.export_types = True
    options.cache_dir = os.devnull
    options.namespace_packages = True
    options.explicit_package_bases = True
    
    if python_env:
        options.python_executable = python_env
        print(f"Mypy Scanner: Using Python environment: {python_env}")

    try:
        sources: List[build.BuildSource] = create_source_list([sources_path], options)
        exclude_dirs = {".venv", "venv", ".git", ".mypy_cache", "__pycache__", "build", "dist", "node_modules"}
        seen_modules = set()
        dedup_sources = []
        for src in sources:
            path_parts = src.path.replace("\\", "/").split("/")
            if not any(part in exclude_dirs for part in path_parts):
                if src.module not in seen_modules:
                    seen_modules.add(src.module)
                    dedup_sources.append(src)
        sources = dedup_sources
    except Exception:
        py_files = []
        exclude_dirs = {".venv", "venv", ".git", ".mypy_cache", "__pycache__", "build", "dist", "node_modules"}
        for root, dirs, files in os.walk(sources_path):
            # Filter dirs in-place to avoid traversing excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            for file in files:
                if file.endswith(".py"):
                    py_files.append(os.path.join(root, file))
                    
        sources = [
            build.BuildSource(path=p, module=f"scan_mod_{i}", text=None)
            for i, p in enumerate(py_files)
        ]

    print(f"Mypy Scanner: Found {len(sources)} sources to scan.")
    if not sources:
        return []
        
    try:
        print("Mypy Scanner: Running build.build...")
        result: build.BuildResult = build.build(sources=sources, options=options)
        typed_trees: Dict[str, MypyFile] = result.files
    except Exception as e:
        print(f"Mypy Scanner: build.build failed: {e}")
        typed_trees = {}
        print("Mypy Scanner: Falling back to per-file build...")
        for source in sources:
            try:
                res = build.build(sources=[source], options=options)
                typed_trees.update(res.files)
            except Exception as e2:
                print(f"Mypy Scanner: Per-file build failed for {source.path}: {e2}")
                pass
    
    all_calls = []
    print(f"Mypy Scanner: Found {len(typed_trees)} typed trees.")
    for file_path, tree in typed_trees.items():
        print(f"Mypy Scanner: Checking file: {file_path}")
        if isSourceFile(tree, sources_path):
            print(f"Mypy Scanner: {file_path} is source file.")
            if not tree.path: continue
            with open(tree.path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
            calls = find_all_function_calls(tree)
            print(f"Mypy Scanner: Found {len(calls)} calls in {file_path}")
            for call in calls:
                fullname, resolution = getImport(call.callee, tree)
                print(f"Mypy Scanner: Call at line {call.line}: {fullname} (resolution: {resolution})")
                if fullname:
                    fullname = clean_gapic_fullname(fullname)
                if fullname and isRelevantImport(fullname):
                    print(f"Mypy Scanner: Relevant call found: {fullname}")
                    all_calls.append(GapicCall(
                        fullname=fullname,
                        file_path=tree.path,
                        line=call.line,
                        source_line=lines[call.line - 1].strip(),
                        resolution=resolution
                    ))
    return all_calls
