import { VoiceClient } from '@/components/app/voice-client';
import { getAgentName, getTokenServerId } from '@/lib/env';

export const dynamic = 'force-dynamic';

export default function VoicePage() {
  return <VoiceClient tokenServerId={getTokenServerId()} agentName={getAgentName()} />;
}
