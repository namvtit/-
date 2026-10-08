import { useEffect, useRef, useState, type FormEvent } from "react";
import {
  api,
  type Config,
  type Job,
  type Material,
  type VideoInput,
} from "./api";
import { JobCard, StatusBadge } from "./components/JobCard";
import { ConnectionStatus } from "./components/ConnectionStatus";

const defaults: VideoInput = {
  topic: "",
  language: "vi",
  duration: 45,
  aspect_ratio: "9:16",
  local_materials: [],
  footage_source: "pixabay",
};
const messageOf = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";
const time = (value: string) =>
  new Date(value).toLocaleString(undefined, {
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });

type Props = {
  config: Config | null;
  configError: string;
  checkingConfig: boolean;
  refreshConfig: () => Promise<void>;
  jobs: Job[];
  activeJob?: Job;
  loading: boolean;
  onCreated: (job: Job) => void;
  onShowSettings: () => void;
  onShowJobs: (jobId?: string) => void;
};

export function Dashboard({
  config,
  configError,
  checkingConfig,
  refreshConfig,
  jobs,
  activeJob,
  loading,
  onCreated,
  onShowSettings,
  onShowJobs,
}: Props) {
  const [input, setInput] = useState<VideoInput>(defaults);
  const [materials, setMaterials] = useState<Material[]>([]);
  const [submitting, setSubmitting] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState("");
  const submitLock = useRef(false);
  const uploadLock = useRef(false);
  const sourceChosen = useRef(false);
  useEffect(() => {
    if (config && !sourceChosen.current) {
      setInput((previous) => ({ ...previous, footage_source: config.default_footage_source }));
    }
  }, [config]);
  const needsLLM = !input.script?.trim();
  const provider = config?.stock_providers.find((item) => item.id === input.footage_source);
  const missingConfiguration = [
    ...(config && needsLLM && !config.llm_configured ? [config.llm_connection.detail] : []),
    ...(!materials.length && provider && !provider.configured ? [provider.connection.detail] : []),
  ];
  async function generate(event: FormEvent) {
    event.preventDefault();
    if (submitLock.current) return;
    if (!input.topic.trim()) {
      setError("Topic/Prompt is required. Enter the idea for your video.");
      return;
    }
    if (input.footage_source === "local" && !materials.length) {
      setError("Local footage is selected; upload at least one MP4 clip or select a stock provider.");
      return;
    }
    submitLock.current = true;
    setSubmitting(true);
    setError("");
    try {
      const job = await api<Job>("/api/videos", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...input,
          topic: input.topic.trim(),
          script: input.script?.trim() || undefined,
          local_materials: materials.map((item) => item.id),
        }),
      });
      onCreated(job);
    } catch (error) {
      setError(messageOf(error));
    } finally {
      submitLock.current = false;
      setSubmitting(false);
    }
  }
  async function upload(files: FileList | null) {
    if (!files || uploadLock.current) return;
    if (files.length + materials.length > 12) {
      setError("Select up to 12 clips per video.");
      return;
    }
    uploadLock.current = true;
    setUploading(true);
    setError("");
    try {
      for (const file of Array.from(files)) {
        const form = new FormData();
        form.append("file", file);
        const result = await api<Material>("/api/materials", {
          method: "POST",
          body: form,
        });
        setMaterials((previous) => [...previous, result]);
      }
    } catch (error) {
      setError(messageOf(error));
    } finally {
      uploadLock.current = false;
      setUploading(false);
    }
  }

  return (
    <>
      <div className="page-heading">
        <span className="eyebrow">YOUR NEXT STORY STARTS HERE</span>
        <h1>A topic. A finished video.</h1>
        <p>Turn an idea into a narrated video, ready to share.</p>
      </div>
      {configError && <div className="alert error" role="alert">Could not check configuration: {configError}</div>}
      <div className="creation-grid">
        <section className="card create-card">
          <div className="card-header">
            <span className="step">01</span>
            <div>
              <h2>Make something worth watching</h2>
              <p>We’ll handle the script, voice, footage, and edit.</p>
            </div>
          </div>
          <form onSubmit={generate} onChange={() => setError("")} noValidate>
            <label htmlFor="topic">Topic/Prompt <span className="muted">· Required</span></label>
            <textarea
              id="topic"
              className="topic-input"
              placeholder="e.g. Three small habits for a calmer morning"
              value={input.topic}
              maxLength={500}
              aria-required="true"
              aria-describedby="topic-hint"
              onChange={(event) =>
                setInput({ ...input, topic: event.target.value })
              }
            />
            <div className="field-hint" id="topic-hint">
              Describe the idea, not the narration. We’ll write the script if you leave it empty.
              <span>{input.topic.length}/500</span>
            </div>
            <label htmlFor="script">Narration Script <span className="muted">· Optional</span></label>
            <textarea
              id="script"
              rows={3}
              placeholder="Leave empty to generate narration from your topic using the configured LLM."
              maxLength={8000}
              value={input.script ?? ""}
              aria-describedby="script-hint"
              onChange={(event) => setInput({ ...input, script: event.target.value })}
            />
            <p className="help script-hint" id="script-hint">
              Supplied narration is used as written and skips the LLM. With stock footage, your topic supplies the search phrase.
            </p>
            <div className="form-row">
              <div>
                <label htmlFor="language">Narration language</label>
                <select
                  id="language"
                  value={input.language}
                  onChange={(event) =>
                    setInput({
                      ...input,
                      language: event.target.value as VideoInput["language"],
                    })
                  }
                >
                  <option value="vi">Vietnamese</option>
                  <option value="en">English</option>
                  <option value="zh">Chinese</option>
                </select>
              </div>
              <div>
                <label htmlFor="duration">Video length</label>
                <select
                  id="duration"
                  value={input.duration}
                  onChange={(event) =>
                    setInput({ ...input, duration: Number(event.target.value) })
                  }
                >
                  <option value={30}>30 seconds</option>
                  <option value={45}>45 seconds</option>
                  <option value={60}>60 seconds</option>
                </select>
              </div>
            </div>
            <fieldset>
              <legend>Video format</legend>
              <div className="format-options">
                {(["9:16", "16:9"] as const).map((ratio) => (
                  <label
                    key={ratio}
                    className={`format-option ${input.aspect_ratio === ratio ? "chosen" : ""}`}
                  >
                    <input
                      type="radio"
                      name="aspect"
                      checked={input.aspect_ratio === ratio}
                      value={ratio}
                      onChange={() =>
                        setInput({ ...input, aspect_ratio: ratio })
                      }
                    />
                    <span
                      className={`ratio-icon ${ratio === "9:16" ? "portrait" : "landscape"}`}
                    />
                    <span>
                      <strong>
                        {ratio === "9:16" ? "Portrait" : "Landscape"}
                      </strong>
                      <small>
                        {ratio} ·{" "}
                        {ratio === "9:16" ? "Shorts & Reels" : "YouTube"}
                      </small>
                    </span>
                  </label>
                ))}
              </div>
            </fieldset>
            <label htmlFor="footage-source">Footage source</label>
            <select
              id="footage-source"
              value={input.footage_source}
              onChange={(event) => {
                sourceChosen.current = true;
                setInput({ ...input, footage_source: event.target.value as VideoInput["footage_source"] });
              }}
            >
              <option value="pixabay">Pixabay</option>
              <option value="pexels">Pexels</option>
              <option value="coverr">Coverr</option>
              <option value="local">Local</option>
            </select>
            <p className="help footage-hint">
              {materials.length
                ? `${materials.length} local clip(s) will be used instead of stock footage.`
                : input.footage_source === "local"
                  ? "Upload at least one MP4 clip, or choose a stock provider."
                  : `No local clips: footage will be searched and downloaded from ${provider?.name ?? input.footage_source}.`}
            </p>
            <details className="optional" open={input.footage_source === "local" || materials.length > 0}>
              <summary>
                Local Footage <span>{input.footage_source === "local" ? "Required" : "Optional"}</span>
              </summary>
              <div className="optional-body">
                <label htmlFor="materials">Local footage</label>
                <input
                  id="materials"
                  type="file"
                  accept="video/mp4,.mp4"
                  multiple
                  disabled={uploading || materials.length >= 12}
                  onChange={(event) => {
                    void upload(event.target.files);
                    event.target.value = "";
                  }}
                />
                <p className="help">
                  MP4 · max 100 MB each · at least 480 × 480 · up to 12 clips.
                  Local footage replaces stock search.
                </p>
                {uploading && (
                  <p role="status">Uploading and validating clips…</p>
                )}
                {materials.map((item) => (
                  <div className="material" key={item.id}>
                    <span>{item.name}</span>
                    <button
                      type="button"
                      onClick={() =>
                        setMaterials((previous) =>
                          previous.filter(
                            (material) => material.id !== item.id,
                          ),
                        )
                      }
                      aria-label={`Remove ${item.name}`}
                    >
                      ×
                    </button>
                  </div>
                ))}
              </div>
            </details>
            <div className="provider-connections" aria-label="Provider connections">
              <div className="section-heading">
                <strong>Provider connections</strong>
                <button type="button" disabled={checkingConfig} onClick={() => void refreshConfig()}>
                  {checkingConfig ? "Checking…" : "Check connections"}
                </button>
              </div>
              {config ? <>
                <ConnectionStatus name={needsLLM ? "LLM · generates narration" : "LLM · skipped for supplied script"} connection={config.llm_connection} />
                {materials.length || input.footage_source === "local"
                  ? <p className="help">Local footage · no stock API key required.</p>
                  : provider && <ConnectionStatus name={provider.name} connection={provider.connection} />}
                <ConnectionStatus name={config.renderer} connection={config.renderer_connection} />
              </> : <p className="help">{configError ? "Configuration check failed; submitting will validate on the server." : "Checking provider configuration…"}</p>}
              <button className="settings-link" type="button" onClick={onShowSettings}>View all providers →</button>
            </div>
            {missingConfiguration.length > 0 && <div className="alert error" role="alert">{missingConfiguration.join(" ")} Add the missing values in .env and apply them, or supply the script/local clips.</div>}
            {error && (
              <div className="alert error" role="alert">
                {error}
              </div>
            )}
            <button
              className="primary generate"
              disabled={
                submitting || uploading || missingConfiguration.length > 0
              }
            >
              {submitting ? "Adding to queue…" : "Generate video"}
              <span aria-hidden="true">↗</span>
            </button>
            <p className="generate-note">
              Real processing takes a few minutes. You can leave this page.
            </p>
          </form>
        </section>
        <div className="right-column">
          <section className="card output-card">
            <div className="card-header">
              <span className="step">02</span>
              <div>
                <h2>Your output</h2>
                <p>Watch your idea come together.</p>
              </div>
            </div>
            {activeJob ? (
              <JobCard job={activeJob} featured />
            ) : (
              <div className="output-empty">
                <div className="empty-video">
                  <span aria-hidden="true">▶</span>
                </div>
                <h3>A little idea goes a long way.</h3>
                <p>
                  Your video will appear here.
                  <br />
                  Start with a topic on the left.
                </p>
                <span className="output-spec">MP4 · NARRATION · SUBTITLES</span>
              </div>
            )}
          </section>
          <div className="pipeline-note">
            <strong>From idea to final cut</strong>
            <p>Script → footage & voice → render → ready</p>
            <small>
              One video renders at a time. The rest wait in your queue.
            </small>
          </div>
        </div>
      </div>
      <section className="recent-section">
        <div className="section-heading">
          <h2>Recent videos</h2>
          <button onClick={() => onShowJobs()}>View all →</button>
        </div>
        {loading ? (
          <p className="muted" role="status">
            Loading your videos…
          </p>
        ) : jobs.length ? (
          <div className="recent-list">
            {jobs.slice(0, 3).map((job) => (
              <button
                className="recent-row"
                key={job.id}
                onClick={() => onShowJobs(job.id)}
              >
                <span className="recent-icon" aria-hidden="true">
                  ▷
                </span>
                <span className="recent-topic">
                  {job.input.topic}
                  <small>
                    {job.input.duration}s · {job.input.aspect_ratio} ·{" "}
                    {time(job.created_at)}
                  </small>
                </span>
                <StatusBadge job={job} />
                <span aria-hidden="true">→</span>
              </button>
            ))}
          </div>
        ) : (
          <p className="muted">No videos yet. Your first one starts above.</p>
        )}
      </section>
    </>
  );
}
