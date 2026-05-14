/*
Go Cloud Access Scanner
=======================

Problem Statement:
------------------
This script performs static analysis on a Go codebase to identify Google Cloud, Vertex AI, GenAI, and Google API client library invocations.
The primary goal is to locate and extract these high-level method calls (e.g., `cloud.google.com/go/storage.Client.Bucket`), resolve their fully qualified names using the Go TypeChecker, and determine credential provenance.

How It Works:
-------------
1. Project Loading: Uses `golang.org/x/tools/go/packages` to load all Go packages, syntax trees, and type information for the target directory.
2. AST & Type Checking: Inspects AST CallExpressions and resolves symbols to fully qualified import paths using `types.Info`.
3. Credential Tracing: Traces client instantiation (e.g., `storage.NewClient`) and variable declarations to classify credential provenance.
4. JSON Output: Emits a structured JSON array conforming to `schema.json` to `stdout`, while logging progress to `stderr`.

How to Run (from /Users/petrusca/Google/skills/iam-policy-lens):
----------------------------------------------------------------
1. Run the analyzer passing the target project path as the first argument:
    go run scripts/go/*.go <path_to_project>

2. End-to-End Pipeline (Piping to Policy Generator):
    go run scripts/go/*.go /path/to/project | ./.venv/bin/python3 scripts/policy/policy.py

go run scripts/go/*.go ./../gcp_cost_optimizer_agent/go
*/
package main

import (
	"encoding/json"
	"fmt"
	"os"
	"path/filepath"
	"sort"
	"time"
)

func main() {
	if len(os.Args) < 2 {
		fmt.Fprintln(os.Stderr, "Usage:")
		fmt.Fprintln(os.Stderr, "  go run scripts/go/*.go <path_to_project>")
		os.Exit(1)
	}

	projectPath, err := filepath.Abs(os.Args[1])
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error resolving project path: %v\n", err)
		os.Exit(1)
	}

	fmt.Fprintf(os.Stderr, "Scanning: %s for Google Cloud Go API calls\n", projectPath)

	startTime := time.Now()

	callsChan, err := ScanProject(projectPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error scanning project: %v\n", err)
		os.Exit(1)
	}
	elapsed := time.Since(startTime)

	calls := collect(callsChan)
	if len(calls) > 0 {
		data, err := json.MarshalIndent(calls, "", "  ")
		if err != nil {
			fmt.Fprintf(os.Stderr, "Error marshaling JSON: %v\n", err)
			os.Exit(1)
		}
		fmt.Println(string(data))
	} else {
		fmt.Println("[]")
	}

	fmt.Fprintf(os.Stderr, "\nScan completed in %.2f seconds.\n", elapsed.Seconds())
	fmt.Fprintln(os.Stderr, "====================================================")
}

func collect(ch <-chan GapicCall) []GapicCall {
	var calls []GapicCall
	for v := range ch {
		calls = append(calls, v)
	}
	sort.Slice(calls, func(i, j int) bool {
		if calls[i].FilePath == calls[j].FilePath {
			return calls[i].Line < calls[j].Line
		}
		return calls[i].FilePath < calls[j].FilePath
	})
	return calls
}
