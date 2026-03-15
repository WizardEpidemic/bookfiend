// Provides BookFiend's bookshelf upload, scan-job polling, and raw OCR results interface.

"use client";

import { ChangeEvent, useEffect, useState } from "react";

type HealthResponse = {
  api: string;
  database: string;
  redis: string;
};

type OcrLine = {
  text: string;
  confidence: number;
  box: number[][];
};

type OcrResult = {
  text_regions: number;
  elapsed_seconds: number;
  lines: OcrLine[];
};

type ScanJob = {
  id: string;
  status: string;
  progress: number;
  result_json: {
    simulated?: boolean;
    pipeline_stage?: string;
    image_metrics?: {
      original_width?: number;
      original_height?: number;
      processed_width?: number;
      processed_height?: number;
      brightness?: number;
      blur_variance?: number;
    };
    ocr?: OcrResult;
    books?: unknown[];
    unmatched_candidates?: unknown[];
  } | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
};

const apiUrl =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

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

  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0] ?? null;

    if (previewUrl) {
      URL.revokeObjectURL(previewUrl);
    }

    setSelectedFile(file);
    setJob(null);
    setJobError(null);

    if (file) {
      setPreviewUrl(URL.createObjectURL(file));
    } else {
      setPreviewUrl(null);
    }
  }

  async function startScan() {
    if (!selectedFile) {
      setJobError("Choose a bookshelf image first.");
      return;
    }

    setCreatingJob(true);
    setJobError(null);
    setJob(null);

    const formData = new FormData();
    formData.append("image", selectedFile);

    try {
      const response = await fetch(`${apiUrl}/jobs`, {
        method: "POST",
        body: formData,
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
      <div className="w-full max-w-3xl py-12">
        <header className="text-center">
          <h1 className="text-5xl font-bold">BookFiend</h1>

          <p className="mt-4 text-lg">
            Turn bookshelf photos into a structured library and personalized
            recommendations.
          </p>
        </header>

        <section className="mt-10 rounded-xl border p-6">
          <h2 className="text-xl font-semibold">System Status</h2>

          {healthError && <p className="mt-4">{healthError}</p>}

          {!health && !healthError && (
            <p className="mt-4">Checking services...</p>
          )}

          {health && (
            <div className="mt-4 flex gap-6 text-sm">
              <span>API: {health.api}</span>
              <span>PostgreSQL: {health.database}</span>
              <span>Redis: {health.redis}</span>
            </div>
          )}
        </section>

        <section className="mt-6 rounded-xl border p-6">
          <h2 className="text-xl font-semibold">Scan a Bookshelf</h2>

          <p className="mt-2 text-sm opacity-70">
            Upload a clear JPEG, PNG, or WebP bookshelf image.
          </p>

          <input
            accept="image/jpeg,image/png,image/webp"
            className="mt-5 block w-full"
            onChange={handleFileChange}
            type="file"
          />

          {previewUrl && (
            <img
              alt="Bookshelf preview"
              className="mt-5 max-h-96 rounded-lg border object-contain"
              src={previewUrl}
            />
          )}

          <button
            className="mt-5 rounded-lg border px-5 py-2 font-medium disabled:opacity-50"
            disabled={!selectedFile || creatingJob}
            onClick={startScan}
          >
            {creatingJob ? "Starting scan..." : "Scan Bookshelf"}
          </button>

          {jobError && <p className="mt-4">{jobError}</p>}

          {job && (
            <div className="mt-6">
              <div className="flex justify-between">
                <p>
                  <strong>Status:</strong> {job.status}
                </p>

                <p>{job.progress}%</p>
              </div>

              <div className="mt-2 h-3 overflow-hidden rounded-full border">
                <div
                  className="h-full bg-white transition-all duration-500"
                  style={{ width: `${job.progress}%` }}
                />
              </div>

              {job.status === "failed" && (
                <p className="mt-4">
                  Scan failed: {job.error_message ?? "Unknown error"}
                </p>
              )}

              {job.status === "completed" && job.result_json?.ocr && (
                <div className="mt-8">
                  <h3 className="text-lg font-semibold">
                    Raw OCR Results
                  </h3>

                  <p className="mt-2 text-sm opacity-70">
                    Detected {job.result_json.ocr.text_regions} text regions in{" "}
                    {job.result_json.ocr.elapsed_seconds.toFixed(2)} seconds.
                  </p>

                  <div className="mt-4 space-y-2">
                    {job.result_json.ocr.lines.map((line, index) => (
                      <div
                        className="flex justify-between rounded-lg border p-3"
                        key={`${line.text}-${index}`}
                      >
                        <span>{line.text}</span>

                        <span className="ml-4 text-sm opacity-70">
                          {Math.round(line.confidence * 100)}%
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}