export function ConfigRequired() {
  return (
    <section className="mx-auto flex max-w-lg flex-col gap-4 px-6 text-center">
      <h1 className="text-xl font-semibold text-zinc-100">Connect your Game Guide agent</h1>
      <p className="text-sm leading-relaxed text-zinc-400">
        This app must use <strong className="text-zinc-200">your</strong> LiveKit project and the
        Python agent in <code className="text-zinc-300">agent/</code> — not the public LiveKit demo
        agent.
      </p>
      <ol className="list-decimal space-y-2 pl-5 text-left text-sm text-zinc-400">
        <li>
          Copy LiveKit vars from the repo root <code className="text-zinc-300">.env.local</code>{' '}
          into <code className="text-zinc-300">web/.env.local</code>, or keep only one file at the
          repo root (loaded automatically).
        </li>
        <li>
          Set <code className="text-zinc-300">AGENT_NAME=agent</code>
        </li>
        <li>
          Run <code className="text-zinc-300">lk agent dev</code> in{' '}
          <code className="text-zinc-300">agent/</code>
        </li>
        <li>
          Restart <code className="text-zinc-300">npm run dev</code> in web/
        </li>
      </ol>
    </section>
  );
}
