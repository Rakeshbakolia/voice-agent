'use client';

import { AnimatePresence, motion } from 'motion/react';
import { useAgent, useSessionContext } from '@livekit/components-react';
import { GameGuideSessionView } from '@/components/app/game-guide-session-view';
import { WelcomeView } from '@/components/app/welcome-view';

const MotionWelcomeView = motion.create(WelcomeView);
const MotionSessionView = motion.create(GameGuideSessionView);

const VIEW_MOTION_PROPS = {
  variants: {
    visible: {
      opacity: 1,
    },
    hidden: {
      opacity: 0,
    },
  },
  initial: 'hidden',
  animate: 'visible',
  exit: 'hidden',
  transition: {
    duration: 0.5,
    ease: 'linear' as const,
  },
};

interface ViewControllerProps {
  isVideoInputSupported: boolean;
}

export function ViewController({
  isVideoInputSupported: _isVideoInputSupported,
}: ViewControllerProps) {
  const { isConnected, start } = useSessionContext();
  const agent = useAgent();

  return (
    <div className="relative h-full min-h-[calc(100svh-0px)] w-full">
      <AnimatePresence mode="wait">
        {/* Welcome view */}
        {!isConnected && (
          <MotionWelcomeView
            key="welcome"
            {...VIEW_MOTION_PROPS}
            startButtonText="Start voice chat"
            onStartCall={start}
          />
        )}
        {/* Session view */}
        {isConnected && (
          <MotionSessionView
            key="session-view"
            {...VIEW_MOTION_PROPS}
            preConnectMessage={
              agent.isConnected ? 'You may start speaking' : 'Connecting to Game Guide…'
            }
            className="h-full w-full"
          />
        )}
      </AnimatePresence>
    </div>
  );
}
