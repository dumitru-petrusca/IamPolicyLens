import { CredentialsInfo } from "./credentials.js";

const RELEVANT_PACKAGES = [
  "@google-cloud/",
  "@google/genai",
  "@google/adk",
  "googleapis",
  "@google-cloud/vertexai"
];

export interface GapicCall {
  fullname: string;
  file_path: string;
  line: number;
  source_line: string;
  resolution: string;
  credentials?: CredentialsInfo;
}

export function isRelevantPackage(pkgPath: string): boolean {
  return RELEVANT_PACKAGES.some(p => pkgPath.includes(p));
}
