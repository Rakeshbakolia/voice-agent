'use client';

import { App } from '@/components/app/app';

const tokenEndpoint = '/api/token';

interface VoiceClientProps {
  tokenServerId?: string;
  agentName: string;
}

export function VoiceClient({ tokenServerId, agentName }: VoiceClientProps) {
  return (
    <App
      tokenServerId={tokenServerId}
      tokenEndpoint={tokenEndpoint}
      agentName={agentName}
      isVideoInputSupported={false}
    />
  );
}
