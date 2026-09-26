'use client';

import { useState } from 'react';
import {
  useAgent,
  useSessionContext,
  useSessionMessages,
  useVoiceAssistant,
} from '@livekit/components-react';
import { AgentAudioVisualizerWave } from '@/components/agents-ui/agent-audio-visualizer-wave';
import { AgentChatTranscript } from '@/components/agents-ui/agent-chat-transcript';
import {
  AgentControlBar,
  type AgentControlBarControls,
} from '@/components/agents-ui/agent-control-bar';
import { cn } from '@/lib/shadcn/utils';

const WAVE_COLOR = '#34d399';

interface GameGuideSessionViewProps {
  preConnectMessage?: string;
  className?: string;
}

export function GameGuideSessionView({
  preConnectMessage = 'You may start speaking',
  className,
}: GameGuideSessionViewProps) {
  const session = useSessionContext();
  const agent = useAgent();
  const { messages } = useSessionMessages(session);
  const { state, audioTrack } = useVoiceAssistant();
  const [isChatOpen, setIsChatOpen] = useState(false);

  const status =
    agent.state === 'listening'
      ? preConnectMessage
      : agent.state === 'thinking'
        ? 'Thinking…'
        : agent.state === 'speaking'
          ? 'Game Guide is speaking'
          : agent.isConnected
            ? preConnectMessage
            : 'Connecting to Game Guide…';

  const controls: AgentControlBarControls = {
    leave: true,
    microphone: true,
    chat: true,
    camera: false,
    screenShare: false,
  };

  return (
    <section
      className={cn('relative flex h-full min-h-[calc(100svh-0px)] w-full flex-col', className)}
    >
      {isChatOpen && (
        <div className="absolute inset-x-0 top-14 bottom-36 z-20 overflow-hidden px-4 md:px-8">
          <AgentChatTranscript
            agentState={agent.state}
            messages={messages}
            className="mx-auto h-full max-w-2xl"
          />
        </div>
      )}

      <div className="flex flex-1 flex-col items-center justify-center gap-5 px-6 pt-16 pb-36">
        <div className="flex size-56 items-center justify-center md:size-72">
          <AgentAudioVisualizerWave
            state={state}
            audioTrack={audioTrack}
            color={WAVE_COLOR}
            lineWidth={3}
            className="size-full max-h-72 max-w-full"
          />
        </div>
        <p className="max-w-md text-center text-sm font-medium text-zinc-300">{status}</p>
        <p className="text-xs text-zinc-500">Tap End call below when you are done.</p>
      </div>

      <div className="absolute inset-x-4 bottom-6 z-30 mx-auto max-w-xl md:inset-x-8">
        <AgentControlBar
          variant="livekit"
          controls={controls}
          isChatOpen={isChatOpen}
          isConnected={session.isConnected}
          onDisconnect={session.end}
          onIsChatOpenChange={setIsChatOpen}
          className="border-zinc-800 bg-zinc-950/90 backdrop-blur-md"
        />
      </div>
    </section>
  );
}
