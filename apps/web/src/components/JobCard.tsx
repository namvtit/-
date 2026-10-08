import { labels, type Job } from "../api";

export function StatusBadge({ job }: { job: Job }) {
  return (
    <span
      className={`badge ${job.status === "COMPLETED" ? "ready" : job.status === "FAILED" ? "failed" : "working"}`}
    >
      <span className="dot" />
      {labels[job.status]}
    </span>
  );
}
export function JobCard({
  job,
  featured = false,
}: {
  job: Job;
  featured?: boolean;
}) {
  const active = !["COMPLETED", "FAILED"].includes(job.status);
  return (
    <article className={featured ? "featured-job" : "card job-card"}>
      <div className="job-top">
        <StatusBadge job={job} />
        <span className="job-time">
          {new Date(job.created_at).toLocaleString(undefined, {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          })}
        </span>
      </div>
      <h3>{job.input.topic}</h3>
      <p className="job-spec">
        {job.input.language.toUpperCase()} · {job.input.duration} seconds ·{" "}
        {job.input.aspect_ratio}
      </p>
      {active && (
        <div className="progress-area" role="status">
          <div className="progress-label">
            <span>{labels[job.status]}</span>
            <span>{job.progress}%</span>
          </div>
          <progress
            max={100}
            value={job.progress}
            aria-label="Video generation progress"
          />
          <p>
            {job.status === "RECEIVED"
              ? "Your video is in the queue."
              : "Processing your video. This can take a few minutes."}
          </p>
        </div>
      )}
      {job.error && (
        <div className="alert error" role="alert">
          {job.error}
        </div>
      )}
      {job.status === "COMPLETED" && job.preview_url && (
        <>
          <video
            className={`video-preview ${job.input.aspect_ratio === "9:16" ? "vertical" : ""}`}
            controls
            preload="metadata"
            src={job.preview_url}
            playsInline
            aria-label={`Preview: ${job.input.topic}`}
          />
          {job.metadata && (
            <p className="help">
              {job.metadata.width} × {job.metadata.height} ·{" "}
              {job.metadata.duration.toFixed(1)}s ·{" "}
              {(job.metadata.size_bytes / 1024 / 1024).toFixed(1)} MB
            </p>
          )}
          <a
            className="primary download"
            href={job.download_url ?? "#"}
            download
          >
            Download MP4 <span aria-hidden="true">↓</span>
          </a>
        </>
      )}
      {job.status === "FAILED" && (
        <p className="help">
          Review the error, then create a new video when it’s resolved.
        </p>
      )}
    </article>
  );
}
