import { CredentialsInfo } from "./credentials.js";

export interface GapicCall {
  fullname: string;
  file_path: string;
  line: number;
  source_line: string;
  resolution: string;
  credentials?: CredentialsInfo;
}

const RELEVANT_PACKAGES = [
  "@google-cloud/",
  "@google/genai",
  "@google/adk",
  "googleapis",
  "@google-cloud/vertexai"
];

export function isRelevantPackage(pkgPath: string): boolean {
  return RELEVANT_PACKAGES.some(p => pkgPath.includes(p));
}
