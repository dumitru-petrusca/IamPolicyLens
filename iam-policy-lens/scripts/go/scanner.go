package main

import (
	"fmt"
	"go/ast"
	"go/types"
	"os"
	"strings"

	"golang.org/x/tools/go/packages"
)

type fileCache struct {
	cache map[string][]string
}

func (c *fileCache) getLine(path string, lineNum int) string {
	if c.cache == nil {
		c.cache = make(map[string][]string)
	}
	lines, ok := c.cache[path]
	if !ok {
		content, err := os.ReadFile(path)
		if err != nil {
			return ""
		}
		lines = strings.Split(string(content), "\n")
		c.cache[path] = lines
	}
	if lineNum > 0 && lineNum <= len(lines) {
		return strings.TrimSpace(lines[lineNum-1])
	}
	return ""
}

func ScanProject(projectPath string) (<-chan GapicCall, error) {
	// Set up packages config
	cfg := &packages.Config{
		Mode: packages.NeedName | packages.NeedFiles | packages.NeedCompiledGoFiles |
			packages.NeedImports | packages.NeedTypes | packages.NeedTypesInfo | packages.NeedSyntax,
		Dir: projectPath,
	}
	pkgs, err := packages.Load(cfg, "./...")
	if err != nil {
		return nil, err
	}
	cache := &fileCache{}
	callsChan := make(chan GapicCall)

	go func() {
		for _, pkg := range pkgs {
			if len(pkg.Errors) > 0 {
				// Continue scanning despite package compilation errors in target project
				for _, err := range pkg.Errors {
					fmt.Fprintf(os.Stderr, "Package load warning: %v\n", err)
				}
			}
			for _, fileNode := range pkg.Syntax {
				ast.Inspect(fileNode, inspectNode(fileNode, pkg, cache, callsChan))
			}
		}
		close(callsChan)
	}()

	return callsChan, nil
}

func inspectNode(fileNode *ast.File, pkg *packages.Package, cache *fileCache, calls chan<- GapicCall) func(ast.Node) bool {
	return func(n ast.Node) bool {
		callExpr, ok := n.(*ast.CallExpr)
		if !ok {
			return true
		}

		resolvedName, isGCP := resolveCall(callExpr, pkg.TypesInfo)
		if isGCP {
			pos := pkg.Fset.Position(callExpr.Pos())
			var credsInfo *CredentialsInfo
			if isConstructorCall(resolvedName) {
				credsInfo = extractCredentialsFromCall(callExpr, fileNode, pkg.TypesInfo)
			} else {
				recvIdent := getReceiverIdent(callExpr)
				if recvIdent != nil {
					credsInfo = traceCredentials(recvIdent, fileNode, pkg.TypesInfo)
				}
			}

			calls <- GapicCall{
				FullName:    resolvedName,
				FilePath:    pos.Filename,
				Line:        pos.Line,
				Source:      cache.getLine(pos.Filename, pos.Line),
				Resolution:  "typechecker",
				Credentials: credsInfo,
			}
		}
		return true
	}
}

func isConstructorCall(resolvedName string) bool {
	return strings.Contains(resolvedName, ".New") || strings.Contains(resolvedName, "NewClient")
}

func getReceiverIdent(call *ast.CallExpr) *ast.Ident {
	if sel, ok := call.Fun.(*ast.SelectorExpr); ok {
		if ident, ok := sel.X.(*ast.Ident); ok {
			return ident
		}
	}
	return nil
}

func resolveCall(call *ast.CallExpr, info *types.Info) (string, bool) {
	if info == nil {
		return "", false
	}

	switch fun := call.Fun.(type) {
	case *ast.Ident:
		if obj, ok := info.Uses[fun]; ok {
			if fn, ok := obj.(*types.Func); ok {
				if fn.Pkg() != nil && isRelevantPackage(fn.Pkg().Path()) {
					return fmt.Sprintf("%s.%s", fn.Pkg().Path(), fn.Name()), true
				}
			}
		}

	case *ast.SelectorExpr:
		if sel, ok := info.Selections[fun]; ok {
			if fn, ok := sel.Obj().(*types.Func); ok {
				if fn.Pkg() != nil && isRelevantPackage(fn.Pkg().Path()) {
					recvType := sel.Recv()
					if ptr, ok := recvType.(*types.Pointer); ok {
						recvType = ptr.Elem()
					}
					receiverName := ""
					if named, ok := recvType.(*types.Named); ok {
						receiverName = named.Obj().Name()
					}
					if receiverName != "" {
						return fmt.Sprintf("%s.%s.%s", fn.Pkg().Path(), receiverName, fn.Name()), true
					}
					return fmt.Sprintf("%s.%s", fn.Pkg().Path(), fn.Name()), true
				}
			}
		}

		if obj, ok := info.Uses[fun.Sel]; ok {
			if fn, ok := obj.(*types.Func); ok {
				if fn.Pkg() != nil && isRelevantPackage(fn.Pkg().Path()) {
					return fmt.Sprintf("%s.%s", fn.Pkg().Path(), fn.Name()), true
				}
			}
		}
	}

	return "", false
}
