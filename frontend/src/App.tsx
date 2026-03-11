import { FormEvent, useState } from "react";
import "./styles.css";

const API_BASE =
  import.meta.env.VITE_API_BASE_URL || "http://localhost:8000";

export const App = () => {
  const [weeks, setWeeks] = useState(10);
  const [recipient, setRecipient] = useState("");
  const [recipientName, setRecipientName] = useState("");
  const [sendEmail, setSendEmail] = useState(false);
  const [runMode, setRunMode] = useState<"quick" | "full">("quick");
  const [isRunning, setIsRunning] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setIsRunning(true);
    setStatus(null);

    try {
      const res = await fetch(`${API_BASE}/api/run`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          phase: "all",
          weeks,
          max_reviews: runMode === "quick" ? 100 : 400,
          recipient: recipient || null,
          recipient_name: recipientName || null,
          send: sendEmail
        })
      });

      if (!res.ok) {
        const text = await res.text();
        throw new Error(text || `Request failed with status ${res.status}`);
      }

      const data = await res.json();
      const jobId = data.job_id;
      if (!jobId) {
        setStatus("Unexpected response: no job_id.");
        setIsRunning(false);
        return;
      }

      setStatus(
        runMode === "quick"
          ? "Pipeline running (quick run, ~3–5 min). Keep this tab open…"
          : "Pipeline running (full run can take 10–15 min). Keep this tab open…"
      );

      const pollInterval = 2500;
      let timeoutId: ReturnType<typeof setTimeout> | null = null;

      const poll = async (): Promise<boolean> => {
        try {
          const statusRes = await fetch(`${API_BASE}/api/run/status/${jobId}`);
          if (statusRes.status === 404) {
            const data = await statusRes.json().catch(() => ({}));
            const msg =
              (data?.detail as string) ||
              "Run status was lost (server may have restarted). Please try again.";
            setStatus(`Error: ${msg}`);
            return true;
          }
          if (!statusRes.ok) {
            setStatus(`Error: failed to get status (${statusRes.status})`);
            return true;
          }
          const statusData = await statusRes.json();
          if (statusData.status === "completed") {
            setStatus(
              sendEmail
                ? "Pipeline completed. Check your email."
                : "Pipeline completed successfully."
            );
            return true;
          }
          if (statusData.status === "failed") {
            setStatus(`Error: ${statusData.error ?? "Pipeline failed."}`);
            return true;
          }
          return false;
        } catch (err: unknown) {
          setStatus(`Error: ${err instanceof Error ? err.message : String(err)}`);
          return true;
        }
      };

      const runPoll = () => {
        poll().then((done) => {
          if (done) {
            setIsRunning(false);
            return;
          }
          timeoutId = window.setTimeout(runPoll, pollInterval);
        });
      };

      timeoutId = window.setTimeout(runPoll, pollInterval);
    } catch (err: unknown) {
      setStatus(`Error: ${err instanceof Error ? err.message : String(err)}`);
      setIsRunning(false);
    }
  }

  return (
    <div className="app-root">
      <div className="glass-card">
        <header className="header">
          <div className="logo-mark">
            <span className="logo-g">G</span>
          </div>
          <div className="logo-text">
            <span className="logo-name">GROWW</span>
            <span className="logo-tagline">Weekly Review Pulse</span>
          </div>
        </header>

        <p className="subtitle">
          Turn the latest Play Store reviews into a sharp, weekly email pulse
          for product, support, and leadership.
        </p>

        <form className="form" onSubmit={handleSubmit}>
          <div className="field">
            <label>Review window (weeks)</label>
            <input
              type="number"
              min={8}
              max={12}
              value={weeks}
              onChange={(e) => setWeeks(Number(e.target.value))}
            />
            <span className="hint">Must be between 8 and 12 weeks.</span>
          </div>

          <div className="field">
            <label>Run mode</label>
            <select
              value={runMode}
              onChange={(e) => setRunMode(e.target.value as "quick" | "full")}
            >
              <option value="quick">Quick — 100 reviews (~3–5 min)</option>
              <option value="full">Full — 400 reviews (~10–15 min)</option>
            </select>
            <span className="hint">
              Quick runs finish faster and are more reliable on free hosting.
            </span>
          </div>

          <div className="field">
            <label>Recipient email</label>
            <input
              type="email"
              value={recipient}
              onChange={(e) => setRecipient(e.target.value)}
              placeholder="you@example.com"
            />
          </div>

          <div className="field">
            <label>Recipient name</label>
            <input
              type="text"
              value={recipientName}
              onChange={(e) => setRecipientName(e.target.value)}
              placeholder="Ansh"
            />
            <span className="hint">
              Used as the greeting in the email: &quot;Hi {'{name}'},&quot;.
            </span>
          </div>

          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={sendEmail}
              onChange={(e) => setSendEmail(e.target.checked)}
            />
            <span>Actually send email (otherwise only draft .eml is written)</span>
          </label>

          <button type="submit" disabled={isRunning || !recipient}>
            {isRunning ? "Running pipeline..." : "Run Weekly Pulse"}
          </button>
        </form>

        {status && <p className="status">{status}</p>}
      </div>
    </div>
  );
};

