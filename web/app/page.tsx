"use client";

import { useState } from "react";

export default function HomePage() {
  const [weeks, setWeeks] = useState(10);
  const [recipient, setRecipient] = useState("");
  const [recipientName, setRecipientName] = useState("");
  const [sendEmail, setSendEmail] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [status, setStatus] = useState<string | null>(null);

  async function handleRun(e: React.FormEvent) {
    e.preventDefault();
    setIsRunning(true);
    setStatus(null);

    try {
      const res = await fetch("http://localhost:8000/api/run", {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        body: JSON.stringify({
          phase: "all",
          weeks,
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
      setStatus(`Pipeline completed (phase=${data.phase}).`);
    } catch (err: any) {
      setStatus(`Error: ${err.message ?? String(err)}`);
    } finally {
      setIsRunning(false);
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-slate-50 flex items-center justify-center p-6">
      <div className="w-full max-w-xl rounded-2xl bg-slate-900/70 border border-slate-800 p-6 shadow-xl">
        <h1 className="text-2xl font-semibold mb-4">
          GROWW Weekly Review Pulse
        </h1>
        <p className="text-sm text-slate-300 mb-6">
          Run the end-to-end pipeline: scrape reviews, discover themes,
          generate the weekly pulse note, and (optionally) send a personalised
          email.
        </p>

        <form onSubmit={handleRun} className="space-y-4">
          <div>
            <label className="block text-sm font-medium mb-1">
              Review window (weeks)
            </label>
            <input
              type="number"
              min={8}
              max={12}
              value={weeks}
              onChange={(e) => setWeeks(Number(e.target.value))}
              className="w-24 rounded-md border border-slate-700 bg-slate-900 px-2 py-1 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
            <p className="text-xs text-slate-400 mt-1">
              Must be between 8 and 12 weeks.
            </p>
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              Recipient email (for pulse)
            </label>
            <input
              type="email"
              value={recipient}
              onChange={(e) => setRecipient(e.target.value)}
              placeholder="you@example.com"
              className="w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
          </div>

          <div>
            <label className="block text-sm font-medium mb-1">
              Recipient name (for greeting)
            </label>
            <input
              type="text"
              value={recipientName}
              onChange={(e) => setRecipientName(e.target.value)}
              placeholder="Ansh"
              className="w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500"
            />
            <p className="text-xs text-slate-400 mt-1">
              Used in the email as &quot;Hi {'{name}'},&quot;.
            </p>
          </div>

          <div className="flex items-center gap-2">
            <input
              id="sendEmail"
              type="checkbox"
              checked={sendEmail}
              onChange={(e) => setSendEmail(e.target.checked)}
              className="h-4 w-4 rounded border-slate-700 bg-slate-900 text-emerald-500 focus:ring-emerald-500"
            />
            <label htmlFor="sendEmail" className="text-sm">
              Actually send email (otherwise only draft .eml is written)
            </label>
          </div>

          <button
            type="submit"
            disabled={isRunning}
            className="mt-2 inline-flex items-center justify-center rounded-md bg-emerald-500 px-4 py-2 text-sm font-medium text-slate-950 hover:bg-emerald-400 disabled:opacity-60"
          >
            {isRunning ? "Running..." : "Run Weekly Pulse"}
          </button>
        </form>

        {status && (
          <p className="mt-4 text-sm text-slate-200 whitespace-pre-line">
            {status}
          </p>
        )}
      </div>
    </main>
  );
}

