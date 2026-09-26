import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { loadEnvConfig } from '@next/env';

let loaded = false;

const webDir = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');
const repoRoot = path.resolve(webDir, '..');

export function readEnvVar(key: string): string | undefined {
  const raw = process.env[key];
  if (raw == null || raw === '') {
    return undefined;
  }
  return raw.trim().replace(/^["']|["']$/g, '');
}

/** Load repo-root then `web/` env files (same pattern as agent/ and catalog/). */
export function loadMonorepoEnv(): void {
  if (loaded) {
    return;
  }
  const dev = process.env.NODE_ENV !== 'production';
  loadEnvConfig(repoRoot, dev);
  loadEnvConfig(webDir, dev);
  loaded = true;
}

export function isLiveKitConfigured(): boolean {
  loadMonorepoEnv();
  if (readEnvVar('LIVEKIT_TOKEN_SERVER_ID')) {
    return true;
  }
  return Boolean(
    readEnvVar('LIVEKIT_URL') && readEnvVar('LIVEKIT_API_KEY') && readEnvVar('LIVEKIT_API_SECRET')
  );
}

export function getAgentName(): string {
  loadMonorepoEnv();
  return readEnvVar('AGENT_NAME') || 'agent';
}

export function getTokenServerId(): string | undefined {
  loadMonorepoEnv();
  return readEnvVar('LIVEKIT_TOKEN_SERVER_ID');
}

export function getLiveKitServerConfig(): {
  url: string;
  apiKey: string;
  apiSecret: string;
} {
  loadMonorepoEnv();
  const url = readEnvVar('LIVEKIT_URL');
  const apiKey = readEnvVar('LIVEKIT_API_KEY');
  const apiSecret = readEnvVar('LIVEKIT_API_SECRET');
  if (!url || !apiKey || !apiSecret) {
    throw new Error(
      'Missing LIVEKIT_URL, LIVEKIT_API_KEY, or LIVEKIT_API_SECRET. Add them to the repo root .env.local.'
    );
  }
  return { url, apiKey, apiSecret };
}
