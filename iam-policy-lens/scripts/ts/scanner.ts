import * as ts from "typescript";
import * as fs from "fs";
import * as path from "path";
import { GapicCall, isRelevantPackage } from "./gapic.js";
import { traceCredentials, CredentialsInfo, CredentialProvenance, IdentityContext } from "./credentials.js";

export function scanProject(projectPath: string): GapicCall[] {
  const tsConfigPath = findTsConfig(projectPath);
  let rootFiles: string[] = [];
  let compilerOptions: ts.CompilerOptions = {
    target: ts.ScriptTarget.ES2022,
    module: ts.ModuleKind.CommonJS,
    allowJs: true
  };

  if (tsConfigPath) {
    const configFile = ts.readConfigFile(tsConfigPath, ts.sys.readFile);
    const parsed = ts.parseJsonConfigFileContent(configFile.config, ts.sys, path.dirname(tsConfigPath));
    rootFiles = parsed.fileNames;
    compilerOptions = parsed.options;
  } else {
    walkDir(projectPath, (filePath) => {
      rootFiles.push(filePath);
    });
  }

  const program = ts.createProgram(rootFiles, compilerOptions);
  const typeChecker = program.getTypeChecker();
  const calls: GapicCall[] = [];

  for (const sourceFile of program.getSourceFiles()) {
    if (sourceFile.isDeclarationFile || sourceFile.fileName.includes("node_modules")) {
      continue;
    }
    if (!sourceFile.fileName.startsWith(projectPath)) {
      continue;
    }

    ts.forEachChild(sourceFile, function visit(node: ts.Node) {
      if (ts.isCallExpression(node)) {
        const expr = node.expression;
        if (ts.isPropertyAccessExpression(expr)) {
          const methodName = expr.name.text;
          const clientExpr = expr.expression;

          const clientType = typeChecker.getTypeAtLocation(clientExpr);
          const clientSymbol = clientType.getSymbol() || typeChecker.getSymbolAtLocation(clientExpr);

          if (clientSymbol) {
            let fqn = typeChecker.getFullyQualifiedName(clientSymbol);
            const decls = clientSymbol.getDeclarations();
            if (decls && decls.length > 0) {
              const decl = decls[0];
              if (ts.isImportSpecifier(decl)) {
                const importDecl = decl.parent.parent.parent;
                if (ts.isImportDeclaration(importDecl)) {
                  const moduleName = importDecl.moduleSpecifier.getText(decl.getSourceFile()).replace(/['"]/g, "");
                  fqn = `${moduleName}.${clientSymbol.name}`;
                }
              } else if (decl.getSourceFile().fileName.includes("node_modules")) {
                const match = decl.getSourceFile().fileName.match(/node_modules\/(@[^\/]+\/[^\/]+|[^\/]+)/);
                if (match) {
                  fqn = `${match[1]}.${clientSymbol.name}`;
                }
              }
            }

            if (isRelevantPackage(fqn)) {
              const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart());
              const sourceLine = sourceFile.text.substring(node.getStart(), node.getEnd()).split("\n")[0].trim();

              let creds = traceCredentials(clientExpr, sourceFile, typeChecker);
              if (!creds) {
                creds = {
                  source: "default/implicit",
                  provenance: CredentialProvenance.IMPLICIT,
                  identity: IdentityContext.APP
                };
              }

              calls.push({
                fullname: `${fqn}.${methodName}`,
                file_path: sourceFile.fileName,
                line: line + 1,
                source_line: sourceLine,
                resolution: "typechecker",
                credentials: creds
              });
            }
          }
        } else if (ts.isIdentifier(expr)) {
          const symbol = typeChecker.getSymbolAtLocation(expr);
          if (symbol) {
            let fqn = typeChecker.getFullyQualifiedName(symbol);
            const decls = symbol.getDeclarations();
            if (decls && decls.length > 0) {
              const decl = decls[0];
              if (ts.isImportSpecifier(decl)) {
                const importDecl = decl.parent.parent.parent;
                if (ts.isImportDeclaration(importDecl)) {
                  const moduleName = importDecl.moduleSpecifier.getText(decl.getSourceFile()).replace(/['"]/g, "");
                  fqn = `${moduleName}.${symbol.name}`;
                }
              } else if (decl.getSourceFile().fileName.includes("node_modules")) {
                const match = decl.getSourceFile().fileName.match(/node_modules\/(@[^\/]+\/[^\/]+|[^\/]+)/);
                if (match) {
                  fqn = `${match[1]}.${symbol.name}`;
                }
              }
            }

            if (isRelevantPackage(fqn)) {
              const { line } = sourceFile.getLineAndCharacterOfPosition(node.getStart());
              const sourceLine = sourceFile.text.substring(node.getStart(), node.getEnd()).split("\n")[0].trim();

              calls.push({
                fullname: fqn,
                file_path: sourceFile.fileName,
                line: line + 1,
                source_line: sourceLine,
                resolution: "typechecker",
                credentials: {
                  source: "default/implicit",
                  provenance: CredentialProvenance.IMPLICIT,
                  identity: IdentityContext.APP
                }
              });
            }
          }
        }
      }
      ts.forEachChild(node, visit);
    });
  }

  return calls;
}

function walkDir(dir: string, callback: (filePath: string) => void) {
  const files = fs.readdirSync(dir);
  for (const file of files) {
    if (file === "node_modules" || file === "dist" || file === ".git" || file === "build") {
      continue;
    }
    const fullPath = path.join(dir, file);
    const stat = fs.statSync(fullPath);
    if (stat.isDirectory()) {
      walkDir(fullPath, callback);
    } else if (file.endsWith(".ts") || file.endsWith(".js")) {
      callback(fullPath);
    }
  }
}

function findTsConfig(baseDir: string): string | undefined {
  let current = baseDir;
  while (true) {
    const p = path.join(current, "tsconfig.json");
    if (fs.existsSync(p)) {
      return p;
    }
    const next = path.dirname(current);
    if (next === current) {
      break;
    }
    current = next;
  }
  return undefined;
}
