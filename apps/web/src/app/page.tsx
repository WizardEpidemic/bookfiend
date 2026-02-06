// Provides BookFiend's local demo controls, dependency health status, and scan-job polling UI.

"use client";

import { useEffect, useState } from "react";

type HealthResponse = {
  api: string;
  database: string;
  redis: string;
};

type BookResult = {
  title: string;
  author: string;
  confidence: number;
  source: string;
};

type ScanJob = {
  id: string;
  status: string;
  progress: number;
  result_json: {
    simulated?: boolean;
    books?: BookResult[];
    unmatched_candidates?: unknown[];
  } | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
};

const apiUrl = process.env.NEXT_PUBLIC_API_URL;

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  const [job, setJob] = useState<ScanJob | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [creatingJob, setCreatingJob] = useState(false);

  useEffect(() => {
    fetch(`${apiUrl}/health`)
      .then((response) => {
        if (!response.ok) {
          throw new Error("API health check failed.");
        }

        return response.json();
      })
      .then((data: HealthResponse) => {
        setHealth(data);
      })
      .catch(() => {
        setHealthError("Could not connect to the BookFiend API.");
      });
  }, []);

  useEffect(() => {
    if (!job || job.status === "completed" || job.status === "failed") {
      return;
    }

    const timeout = setTimeout(async () => {
      try {
        const response = await fetch(`${apiUrl}/jobs/${job.id}`);

        if (!response.ok) {
          throw new Error("Could not retrieve scan job.");
        }

        const updatedJob: ScanJob = await response.json();
        setJob(updatedJob);
      } catch {
        setJobError("Could not retrieve scan progress.");
      }
    }, 750);

    return () => clearTimeout(timeout);
  }, [job]);

  async function createDemoJob() {
    setCreatingJob(true);
    setJobError(null);
    setJob(null);

    try {
      const response = await fetch(`${apiUrl}/jobs`, {
        method: "POST",
      });

      if (!response.ok) {
        throw new Error("Could not create scan job.");
      }

      const createdJob: ScanJob = await response.json();
      setJob(createdJob);
    } catch {
      setJobError("Could not start the BookFiend scan.");
    } finally {
      setCreatingJob(false);
    }
  }

  return (
    <main className="flex min-h-screen justify-center p-8">
      <div className="w-full max-w-2xl py-16">
        <div className="text-center">
          <h1 className="text-5xl font-bold">BookFiend</h1>

          <p className="mt-4 text-lg">
            Turn bookshelf photos into a structured library and personalized
            recommendations.
          </p>
        </div>

        <section className="mt-10 rounded-xl border p-6">
          <h2 className="text-xl font-semibold">System Status</h2>

          {healthError && <p className="mt-4">{healthError}</p>}

          {!health && !healthError && (
            <p className="mt-4">Checking services...</p>
          )}

          {health && (
            <div className="mt-4 space-y-2">
              <p>API: {health.api}</p>
              <p>PostgreSQL: {health.database}</p>
              <p>Redis: {health.redis}</p>
            </div>
          )}
        </section>

        <section className="mt-6 rounded-xl border p-6">
          <h2 className="text-xl font-semibold">Scan Pipeline</h2>

          <p className="mt-2 text-sm opacity-70">
            Phase-2 demo of the asynchronous BookFiend job pipeline.
          </p>

          <button
            className="mt-5 rounded-lg border px-4 py-2 font-medium disabled:opacity-50"
            disabled={creatingJob}
            onClick={createDemoJob}
          >
            {creatingJob ? "Creating job..." : "Run Demo Scan"}
          </button>

          {jobError && <p className="mt-4">{jobError}</p>}

          {job && (
            <div className="mt-6 space-y-3">
              <p>
                <strong>Status:</strong> {job.status}
              </p>

              <p>
                <strong>Progress:</strong> {job.progress}%
              </p>

              <div className="h-3 overflow-hidden rounded-full border">
                <div
                  className="h-full bg-white transition-all duration-500"
                  style={{ width: `${job.progress}%` }}
                />
              </div>

              {job.status === "completed" &&
                job.result_json?.books?.map((book) => (
                  <div
                    className="mt-5 rounded-lg border p-4"
                    key={`${book.title}-${book.author}`}
                  >
                    <p className="text-lg font-semibold">{book.title}</p>
                    <p>{book.author}</p>
                    <p className="mt-2 text-sm opacity-70">
                      Confidence: {Math.round(book.confidence * 100)}%
                    </p>
                  </div>
                ))}

              {job.status === "failed" && (
                <p>Scan failed: {job.error_message ?? "Unknown error"}</p>
              )}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}