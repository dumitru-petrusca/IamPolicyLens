import * as ts from "typescript";

export enum CredentialProvenance {
  SA_DEFAULT = "SA_DEFAULT",
  SA_EXPLICIT = "SA_EXPLICIT",
  OAUTH_USER = "OAUTH_USER",
  OAUTH_FLOW = "OAUTH_FLOW",
  DWD = "DWD",
  IMPERSONATION = "IMPERSONATION",
  IMPLICIT = "IMPLICIT",
  UNKNOWN = "UNKNOWN"
}

export enum IdentityContext {
  APP = "APP",
  USER = "USER",
  IMPERSONATED = "IMPERSONATED",
  UNKNOWN = "UNKNOWN"
}

export function toIdentityContext(prov: CredentialProvenance): IdentityContext {
  switch (prov) {
    case CredentialProvenance.SA_DEFAULT:
    case CredentialProvenance.SA_EXPLICIT:
    case CredentialProvenance.IMPLICIT:
      return IdentityContext.APP;
    case CredentialProvenance.OAUTH_USER:
    case CredentialProvenance.OAUTH_FLOW:
      return IdentityContext.USER;
    case CredentialProvenance.DWD:
    case CredentialProvenance.IMPERSONATION:
      return IdentityContext.IMPERSONATED;
    default:
      return IdentityContext.UNKNOWN;
  }
}

export interface CredentialsInfo {
  source: string;
  provenance: CredentialProvenance;
  identity: IdentityContext;
}

export function classifyProvenance(sourceCode: string, fqn: string): CredentialProvenance {
  if (fqn.includes("GoogleAuth") || sourceCode.includes("new GoogleAuth")) {
    if (sourceCode.includes("keyFilename") || sourceCode.includes("credentials")) {
      return CredentialProvenance.SA_EXPLICIT;
    }
    if (sourceCode.includes("clientOptions") && sourceCode.includes("authClient")) {
      return CredentialProvenance.OAUTH_USER;
    }
    return CredentialProvenance.SA_DEFAULT;
  }

  if (sourceCode.includes("keyFilename") || sourceCode.includes("keyFile")) {
    return CredentialProvenance.SA_EXPLICIT;
  }
  if (sourceCode.includes("credentials")) {
    return CredentialProvenance.SA_EXPLICIT;
  }
  if (sourceCode.includes("OAuth2Client") || sourceCode.includes("oauth2")) {
    return CredentialProvenance.OAUTH_USER;
  }
  if (sourceCode.includes("Impersonated") || sourceCode.includes("impersonated")) {
    return CredentialProvenance.IMPERSONATION;
  }

  return CredentialProvenance.SA_DEFAULT;
}

export function extractCredentialsFromObject(node: ts.ObjectLiteralExpression, sourceFile: ts.SourceFile): CredentialsInfo {
  const text = node.getText(sourceFile);
  let prov = CredentialProvenance.SA_DEFAULT;

  for (const prop of node.properties) {
    if (ts.isPropertyAssignment(prop)) {
      const name = prop.name.getText(sourceFile);
      if (name === "keyFilename" || name === "keyFile" || name === "credentials") {
        prov = CredentialProvenance.SA_EXPLICIT;
        break;
      }
      if (name === "authClient" || name === "auth") {
        const val = prop.initializer.getText(sourceFile);
        if (val.includes("OAuth2") || val.includes("oauth2")) {
          prov = CredentialProvenance.OAUTH_USER;
          break;
        }
        if (val.includes("Impersonated")) {
          prov = CredentialProvenance.IMPERSONATION;
          break;
        }
      }
    }
  }

  return {
    source: text,
    provenance: prov,
    identity: toIdentityContext(prov)
  };
}

export function traceCredentials(
  clientNode: ts.Expression,
  sourceFile: ts.SourceFile,
  typeChecker: ts.TypeChecker
): CredentialsInfo | undefined {
  if (ts.isNewExpression(clientNode) || ts.isCallExpression(clientNode)) {
    const args = clientNode.arguments;
    if (args && args.length > 0) {
      const firstArg = args[0];
      if (ts.isObjectLiteralExpression(firstArg)) {
        return extractCredentialsFromObject(firstArg, sourceFile);
      }
      const text = firstArg.getText(sourceFile);
      const prov = classifyProvenance(text, "");
      return {
        source: text,
        provenance: prov,
        identity: toIdentityContext(prov)
      };
    }
    return {
      source: "default/implicit",
      provenance: CredentialProvenance.IMPLICIT,
      identity: IdentityContext.APP
    };
  }

  if (ts.isIdentifier(clientNode)) {
    const symbol = typeChecker.getSymbolAtLocation(clientNode);
    if (symbol) {
      const decls = symbol.getDeclarations();
      if (decls && decls.length > 0) {
        const decl = decls[0];
        if (ts.isVariableDeclaration(decl) && decl.initializer) {
          return traceCredentials(decl.initializer, sourceFile, typeChecker);
        }
      }
    }
  }

  const text = clientNode.getText(sourceFile);
  const prov = classifyProvenance(text, "");
  return {
    source: text,
    provenance: prov,
    identity: toIdentityContext(prov)
  };
}
