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
		fmt.Fprintln(os.Stderr, "  go run scripts/go/analyzer.go <path_to_project>")
		os.Exit(1)
	}

	projectPath, err := filepath.Abs(os.Args[1])
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error resolving project path: %v\n", err)
		os.Exit(1)
	}

	fmt.Fprintf(os.Stderr, "Scanning: %s for Google Cloud Go API calls\n", projectPath)

	startTime := time.Now()

	calls, err := ScanProject(projectPath)
	if err != nil {
		fmt.Fprintf(os.Stderr, "Error scanning project: %v\n", err)
		os.Exit(1)
	}

	elapsed := time.Since(startTime)

	if len(calls) > 0 {
		sort.Slice(calls, func(i, j int) bool {
			if calls[i].FilePath == calls[j].FilePath {
				return calls[i].Line < calls[j].Line
			}
			return calls[i].FilePath < calls[j].FilePath
		})

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
