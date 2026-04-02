// Provides BookFiend's bookshelf upload, scan progress, identified-book results, and raw OCR interface.

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

type MatchedBook = {
  open_library_key: string | null;
  title: string;
  author: string | null;
  isbn: string | null;
  candidate_text: string;
  ocr_confidence: number;
  match_score: number;
  author_support: number;
  candidate_source: string;
  metadata_source: string;
  query_used?: string | null;
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
      scale?: number;
      brightness?: number;
      blur_variance?: number;
    };
    ocr?: OcrResult;
    candidate_count?: number;
    books?: MatchedBook[];
    unmatched_candidates?: unknown[];
  } | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
};

const apiUrl =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function formatStatus(status: string) {
  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

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

  const identifiedBooks = job?.result_json?.books ?? [];
  const ocrResult = job?.result_json?.ocr;

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
            <div className="mt-4 flex flex-wrap gap-6 text-sm">
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

          {jobError && (
            <p className="mt-4 rounded-lg border p-3">{jobError}</p>
          )}

          {job && (
            <div className="mt-6">
              <div className="flex justify-between gap-4">
                <p>
                  <strong>Status:</strong> {formatStatus(job.status)}
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
                <p className="mt-4 rounded-lg border p-3">
                  Scan failed: {job.error_message ?? "Unknown error"}
                </p>
              )}

              {job.status === "completed" && (
                <>
                  <div className="mt-8">
                    <h3 className="text-2xl font-semibold">
                      Identified Books
                    </h3>

                    <p className="mt-2 text-sm opacity-70">
                      Matched {identifiedBooks.length}{" "}
                      {identifiedBooks.length === 1 ? "book" : "books"} using
                      OCR and Open Library metadata.
                    </p>

                    {identifiedBooks.length > 0 ? (
                      <div className="mt-5 grid gap-4 sm:grid-cols-2">
                        {identifiedBooks.map((book) => (
                          <article
                            className="rounded-xl border p-5"
                            key={
                              book.open_library_key ??
                              `${book.title}-${book.author}`
                            }
                          >
                            <h4 className="text-lg font-semibold">
                              {book.title}
                            </h4>

                            <p className="mt-1 opacity-80">
                              {book.author ?? "Unknown author"}
                            </p>

                            <div className="mt-4 space-y-1 text-sm opacity-70">
                              <p>
                                Metadata match:{" "}
                                {Math.round(book.match_score * 100)}%
                              </p>

                              <p>
                                OCR confidence:{" "}
                                {Math.round(book.ocr_confidence * 100)}%
                              </p>

                              <p>
                                Author evidence:{" "}
                                {Math.round(book.author_support * 100)}%
                              </p>

                              {book.isbn && <p>ISBN: {book.isbn}</p>}
                            </div>
                          </article>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-4 rounded-lg border p-4 opacity-70">
                        No confident book matches were found for this image.
                      </p>
                    )}
                  </div>

                  {ocrResult && (
                    <div className="mt-10">
                      <div className="border-t pt-8">
                        <h3 className="text-xl font-semibold">
                          Raw OCR Results
                        </h3>

                        <p className="mt-2 text-sm opacity-70">
                          Detected {ocrResult.text_regions} text regions in{" "}
                          {ocrResult.elapsed_seconds.toFixed(2)} seconds.
                        </p>

                        <div className="mt-4 space-y-2">
                          {ocrResult.lines.map((line, index) => (
                            <div
                              className="flex items-center justify-between gap-4 rounded-lg border p-3"
                              key={`${line.text}-${index}`}
                            >
                              <span>{line.text}</span>

                              <span className="shrink-0 text-sm opacity-70">
                                {Math.round(line.confidence * 100)}%
                              </span>
                            </div>
                          ))}
                        </div>
                      </div>
                    </div>
                  )}
                </>
              )}
            </div>
          )}
        </section>
      </div>
    </main>
  );
}