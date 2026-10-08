import { useCallback, useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import { api, type Config, type Job } from "./api";
import { Dashboard } from "./Dashboard";
import { Settings } from "./Settings";
import { JobCard } from "./components/JobCard";
import "./styles.css";

type Page = "dashboard" | "jobs" | "settings";
const messageOf = (error: unknown) =>
  error instanceof Error
    ? error.message
    : "Something went wrong. Please try again.";

function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [jobs, setJobs] = useState<Job[]>([]);
  const [config, setConfig] = useState<Config | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [connectionError, setConnectionError] = useState("");
  const [configError, setConfigError] = useState("");
  const [checkingConfig, setCheckingConfig] = useState(false);
  const refreshJobs = useCallback(async () => {
    try {
      setJobs(await api<Job[]>("/api/videos"));
      setConnectionError("");
    } catch (error) {
      setConnectionError(messageOf(error));
    } finally {
      setLoading(false);
    }
  }, []);
  const refreshConfig = useCallback(async () => {
    setCheckingConfig(true);
    try {
      setConfig(await api<Config>("/api/config/public"));
      setConfigError("");
    } catch (error) {
      setConfigError(messageOf(error));
    } finally {
      setCheckingConfig(false);
    }
  }, []);
  useEffect(() => {
    void refreshJobs();
    void refreshConfig();
    const interval = setInterval(() => {
      void refreshJobs();
    }, 3000);
    return () => clearInterval(interval);
  }, [refreshJobs, refreshConfig]);
  const activeJob =
    jobs.find((job) => job.id === activeId) ??
    jobs.find((job) => !["COMPLETED", "FAILED"].includes(job.status));
  const running = jobs.filter(
    (job) => !["COMPLETED", "FAILED"].includes(job.status),
  ).length;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <a
          className="brand"
          href="#"
          onClick={(event) => {
            event.preventDefault();
            setPage("dashboard");
          }}
        >
          <span className="brand-mark" aria-hidden="true">
            ▶
          </span>
          <span>
            Video Factory<span className="brand-caption">IDEA TO VIDEO</span>
          </span>
        </a>
        <nav aria-label="Main navigation">
          {(["dashboard", "jobs", "settings"] as Page[]).map((item, index) => (
            <button
              key={item}
              className={`nav-item ${page === item ? "selected" : ""}`}
              onClick={() => setPage(item)}
              aria-current={page === item ? "page" : undefined}
            >
              <span aria-hidden="true">{["▦", "▷", "⚙"][index]}</span>
              {item === "dashboard"
                ? "Create video"
                : item === "jobs"
                  ? "Your videos"
                  : "Settings"}
              {item === "jobs" && running > 0 && (
                <span className="nav-count" aria-hidden="true">
                  {running}
                </span>
              )}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <span
            className={`dot ${config?.renderer_connection.status === "connected" ? "green" : ""}`}
          />
          {config
            ? config.renderer_connection.status === "connected"
              ? "Renderer connected"
              : "Renderer offline"
            : "Checking renderer…"}
          <small>Powered by MoneyPrinterTurbo</small>
        </div>
      </aside>
      <main>
        <header className="topbar">
          <span>
            Workspace <span className="slash">/</span>{" "}
            {page === "dashboard"
              ? "Create video"
              : page === "jobs"
                ? "Your videos"
                : "Settings"}
          </span>
          <span className="version">MVP · 01</span>
        </header>
        <div className="page-content">
          {connectionError && (
            <div className="alert error" role="alert">
              Could not refresh jobs: {connectionError} Reconnecting…
            </div>
          )}
          {page === "dashboard" && (
            <Dashboard
              config={config}
              configError={configError}
              checkingConfig={checkingConfig}
              refreshConfig={refreshConfig}
              jobs={jobs}
              activeJob={activeJob}
              loading={loading}
              onCreated={(job) => {
                setActiveId(job.id);
                setJobs((previous) => [job, ...previous]);
              }}
              onShowSettings={() => setPage("settings")}
              onShowJobs={(jobId) => {
                if (jobId) setActiveId(jobId);
                setPage("jobs");
              }}
            />
          )}
          {page === "jobs" && (
            <>
              <div className="page-heading">
                <span className="eyebrow">YOUR CREATIVE LIBRARY</span>
                <h1>Your videos</h1>
                <p>
                  Follow the queue, preview the results, and take them with you.
                </p>
              </div>
              {loading ? (
                <p role="status">Loading your videos…</p>
              ) : jobs.length ? (
                <div className="jobs-grid">
                  {jobs.map((job) => (
                    <JobCard job={job} key={job.id} />
                  ))}
                </div>
              ) : (
                <div className="card empty-library">
                  <h2>Your first story is waiting.</h2>
                  <p>Create a video to start your library.</p>
                  <button
                    className="primary"
                    onClick={() => setPage("dashboard")}
                  >
                    Create video ↗
                  </button>
                </div>
              )}
            </>
          )}
          {page === "settings" && (
            <Settings
              config={config}
              configError={configError}
              checkingConfig={checkingConfig}
              refreshConfig={refreshConfig}
            />
          )}
          <footer>
            AI Video Factory
            <span>Built for the stories you haven’t told yet.</span>
          </footer>
        </div>
      </main>
    </div>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
