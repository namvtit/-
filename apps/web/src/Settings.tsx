import { type Config } from "./api";
import { ConnectionStatus } from "./components/ConnectionStatus";

type Props = {
  config: Config | null;
  configError: string;
  checkingConfig: boolean;
  refreshConfig: () => Promise<void>;
};
export function Settings({
  config,
  configError,
  checkingConfig,
  refreshConfig,
}: Props) {
  return (
    <>
      <div className="page-heading">
        <span className="eyebrow">THE ENGINES BEHIND YOUR STORIES</span>
        <h1>Settings</h1>
        <p>
          Provider configuration and live connection checks. API keys stay on
          the server.
        </p>
      </div>
      {configError && (
        <div className="alert error" role="alert">
          {configError}
        </div>
      )}
      <button
        className="secondary"
        disabled={checkingConfig}
        onClick={() => {
          void refreshConfig();
        }}
      >
        {checkingConfig ? "Checking connections…" : "Check connections"}
      </button>
      {config && (
        <>
          <div className="settings-grid">
            <section className="card settings-card">
              <h2>AI script provider</h2>
              <span
                className={`badge ${config.llm_connection.status === "connected" ? "ready" : "neutral"}`}
              >
                {config.llm_connection.status.replaceAll("_", " ")}
              </span>
              <dl>
                <dt>API base URL</dt>
                <dd>{config.llm_base_url || "Not configured"}</dd>
                <dt>Model</dt>
                <dd>{config.llm_model || "Not configured"}</dd>
              </dl>
              <p className="help">{config.llm_connection.detail}</p>
            </section>
            <section className="card settings-card">
              <h2>Video renderer</h2>
              <span
                className={`badge ${config.renderer_connection.status === "connected" ? "ready" : "failed"}`}
              >
                {config.renderer_connection.status}
              </span>
              <dl>
                <dt>Engine</dt>
                <dd>{config.renderer}</dd>
                <dt>Narration</dt>
                <dd>{config.tts}</dd>
              </dl>
              <p className="help">
                {config.renderer_connection.detail} Edge TTS connectivity is
                checked during generation.
              </p>
            </section>
            <section className="card settings-card">
              <h2>Stock footage providers</h2>
              {config.stock_providers.map((provider) => (
                <ConnectionStatus key={provider.id} name={`${provider.name} · ${provider.configured ? "key configured" : "key missing"}`} connection={provider.connection} />
              ))}
              <p className="help">Local footage needs no stock API key. Uploaded clips replace stock search for that video.</p>
            </section>
          </div>
          <section className="card setup-card">
            <h2>
              {config.setup_issues.length
                ? "Finish your setup"
                : "Configuration is ready"}
            </h2>
            {config.setup_issues.length > 0 && (
              <ul>
                {config.setup_issues.map((issue) => (
                  <li key={issue}>{issue}</li>
                ))}
              </ul>
            )}
            <p>
              Copy <code>.env.example</code> to <code>.env</code> in the project
              root and fill in your provider values. Apply changes with:
            </p>
            <pre>docker compose up -d --build</pre>
            <p className="help">
              OpenAI-compatible providers are supported. With your own script
              no LLM key is required. Local clips need no stock key. Internet access
              is still required for Edge TTS.
            </p>
          </section>
        </>
      )}
    </>
  );
}
