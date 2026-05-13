/**
 * TypeScript Cloud Access Scanner
 * ===============================
 *
 * Problem Statement:
 * ------------------
 * This script performs static analysis on a TypeScript/Node.js codebase to identify Google Cloud, Vertex AI, GenAI, and Google API client library invocations.
 * The primary goal is to locate and extract these high-level method calls (e.g., `@google-cloud/storage.Bucket.file`), resolve their fully qualified names using the TypeScript TypeChecker, and determine credential provenance.
 *
 * How It Works:
 * -------------
 * 1. Project Loading: Automatically detects `tsconfig.json` or walks the target directory to load all TypeScript/JavaScript source files.
 * 2. AST & Type Checking: Uses `ts.createProgram` and `program.getTypeChecker()` to inspect CallExpressions and resolve symbols to fully qualified import paths.
 * 3. Credential Tracing: Traces client instantiation (e.g., `new Storage({ keyFilename: '...' })`) and variable declarations to classify credential provenance.
 * 4. JSON Output: Emits a structured JSON array conforming to `schema.json` to `stdout`, while logging progress to `stderr`.
 *
 * How to Run (from /Users/petrusca/Google/skills/iam-policy-lens):
 * ----------------------------------------------------------------
 * 1. Compile the TypeScript analyzer first (if not already built):
 *     npm --prefix scripts/ts run build
 *
 * 2. Run the analyzer passing the target project path as the first argument:
 *     node scripts/ts/dist/analyzer.js <path_to_project>
 *
 * 3. End-to-End Pipeline (Piping to Policy Generator):
 *     node scripts/ts/dist/analyzer.js /path/to/project | ./.venv/bin/python3 scripts/policy/policy.py
 * 
 * node scripts/ts/dist/analyzer.js ./../gcp_cost_optimizer_agent/ts
 */
import * as path from "path";
import { scanProject } from "./scanner.js";

function main() {
  const args = process.argv.slice(2);
  if (args.length < 1) {
    console.error("Usage:");
    console.error("  node scripts/ts/dist/analyzer.js <path_to_project>");
    process.exit(1);
  }

  const projectPath = path.resolve(args[0]);
  console.error(`Scanning: ${projectPath} for TypeScript/Node.js GAPIC calls`);

  const startTime = Date.now();
  const calls = scanProject(projectPath);
  const elapsed = (Date.now() - startTime) / 1000;

  if (calls.length > 0) {
    calls.sort((a, b) => {
      if (a.file_path === b.file_path) {
        return a.line - b.line;
      }
      return a.file_path.localeCompare(b.file_path);
    });

    console.log(JSON.stringify(calls, null, 2));
  } else {
    console.log("[]");
  }

  console.error(`\nScan completed in ${elapsed.toFixed(2)} seconds.`);
  console.error("====================================================");
}

main();
