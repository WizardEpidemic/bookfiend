// Provides BookFiend's bookshelf scanning, Goodreads import, preference summary, and personalized recommendation interface.

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
    metadata_cache?: {
      hits: number;
      misses: number;
    };
  } | null;
  error_message: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
};

type GoodreadsImportResponse = {
  imported_count: number;
  rated_count: number;
  shelf_count: number;
  favorite_authors: string[];
  favorite_shelves: string[];
};

type RecommendationItem = {
  title: string;
  author: string;
  genres: string[];
  score: number;
  similarity_score: number;
  reasons: string[];
};

type RecommendationResponse = {
  profile_book_count: number;
  candidate_count: number;
  recommendations: RecommendationItem[];
};

const apiUrl =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

function formatStatus(status: string) {
  return status
    .replaceAll("_", " ")
    .replace(/\b\w/g, (character) => character.toUpperCase());
}

function percentage(value: number) {
  return `${Math.round(value * 100)}%`;
}

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);

  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);

  const [job, setJob] = useState<ScanJob | null>(null);
  const [jobError, setJobError] = useState<string | null>(null);
  const [creatingJob, setCreatingJob] = useState(false);

  const [goodreadsFile, setGoodreadsFile] = useState<File | null>(null);
  const [importingGoodreads, setImportingGoodreads] = useState(false);
  const [goodreadsError, setGoodreadsError] = useState<string | null>(null);
  const [goodreadsResult, setGoodreadsResult] =
    useState<GoodreadsImportResponse | null>(null);

  const [recommendations, setRecommendations] =
    useState<RecommendationResponse | null>(null);
  const [recommendationError, setRecommendationError] =
    useState<string | null>(null);
  const [loadingRecommendations, setLoadingRecommendations] =
    useState(false);

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

  function handleShelfFileChange(
    event: ChangeEvent<HTMLInputElement>,
  ) {
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

  function handleGoodreadsFileChange(
    event: ChangeEvent<HTMLInputElement>,
  ) {
    const file = event.target.files?.[0] ?? null;

    setGoodreadsFile(file);
    setGoodreadsError(null);
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

  async function fetchRecommendations() {
    setLoadingRecommendations(true);
    setRecommendationError(null);

    try {
      const response = await fetch(
        `${apiUrl}/recommendations?limit=8`,
      );

      if (!response.ok) {
        throw new Error("Could not retrieve recommendations.");
      }

      const data: RecommendationResponse = await response.json();

      setRecommendations(data);
    } catch {
      setRecommendationError(
        "Could not generate BookFiend recommendations.",
      );
    } finally {
      setLoadingRecommendations(false);
    }
  }

  async function importGoodreads() {
    if (!goodreadsFile) {
      setGoodreadsError("Choose a Goodreads CSV file first.");
      return;
    }

    setImportingGoodreads(true);
    setGoodreadsError(null);
    setGoodreadsResult(null);
    setRecommendations(null);
    setRecommendationError(null);

    const formData = new FormData();
    formData.append("csv_file", goodreadsFile);

    try {
      const response = await fetch(`${apiUrl}/goodreads/import`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorPayload = await response.json().catch(() => null);

        throw new Error(
          errorPayload?.detail ?? "Could not import Goodreads CSV.",
        );
      }

      const result: GoodreadsImportResponse = await response.json();

      setGoodreadsResult(result);

      await fetchRecommendations();
    } catch (error) {
      if (error instanceof Error) {
        setGoodreadsError(error.message);
      } else {
        setGoodreadsError("Could not import Goodreads CSV.");
      }
    } finally {
      setImportingGoodreads(false);
    }
  }

  const identifiedBooks = job?.result_json?.books ?? [];
  const ocrResult = job?.result_json?.ocr;

  return (
    <main className="flex min-h-screen justify-center p-8">
      <div className="w-full max-w-4xl py-12">
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
            onChange={handleShelfFileChange}
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
                                {percentage(book.match_score)}
                              </p>

                              <p>
                                OCR confidence:{" "}
                                {percentage(book.ocr_confidence)}
                              </p>

                              <p>
                                Author evidence:{" "}
                                {percentage(book.author_support)}
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
                    <details className="mt-10 border-t pt-8">
                      <summary className="cursor-pointer text-xl font-semibold">
                        Raw OCR Results
                      </summary>

                      <p className="mt-3 text-sm opacity-70">
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
                              {percentage(line.confidence)}
                            </span>
                          </div>
                        ))}
                      </div>
                    </details>
                  )}
                </>
              )}
            </div>
          )}
        </section>

        <section className="mt-6 rounded-xl border p-6">
          <h2 className="text-xl font-semibold">
            Personalize with Goodreads
          </h2>

          <p className="mt-2 text-sm opacity-70">
            Import your Goodreads library export to build a preference profile
            from your ratings and shelves.
          </p>

          <input
            accept=".csv,text/csv"
            className="mt-5 block w-full"
            onChange={handleGoodreadsFileChange}
            type="file"
          />

          <button
            className="mt-5 rounded-lg border px-5 py-2 font-medium disabled:opacity-50"
            disabled={!goodreadsFile || importingGoodreads}
            onClick={importGoodreads}
          >
            {importingGoodreads
              ? "Importing..."
              : "Import Goodreads & Recommend"}
          </button>

          {goodreadsError && (
            <p className="mt-4 rounded-lg border p-3">
              {goodreadsError}
            </p>
          )}

          {goodreadsResult && (
            <div className="mt-7">
              <h3 className="text-lg font-semibold">
                Reading Profile
              </h3>

              <div className="mt-4 grid gap-4 sm:grid-cols-3">
                <div className="rounded-lg border p-4">
                  <p className="text-2xl font-semibold">
                    {goodreadsResult.imported_count}
                  </p>

                  <p className="mt-1 text-sm opacity-70">
                    Imported books
                  </p>
                </div>

                <div className="rounded-lg border p-4">
                  <p className="text-2xl font-semibold">
                    {goodreadsResult.rated_count}
                  </p>

                  <p className="mt-1 text-sm opacity-70">
                    Rated books
                  </p>
                </div>

                <div className="rounded-lg border p-4">
                  <p className="text-2xl font-semibold">
                    {goodreadsResult.shelf_count}
                  </p>

                  <p className="mt-1 text-sm opacity-70">
                    Reading shelves
                  </p>
                </div>
              </div>

              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                <div className="rounded-lg border p-4">
                  <h4 className="font-semibold">
                    Favorite Authors
                  </h4>

                  <div className="mt-3 flex flex-wrap gap-2">
                    {goodreadsResult.favorite_authors.map((author) => (
                      <span
                        className="rounded-full border px-3 py-1 text-sm"
                        key={author}
                      >
                        {author}
                      </span>
                    ))}
                  </div>
                </div>

                <div className="rounded-lg border p-4">
                  <h4 className="font-semibold">
                    Favorite Shelves
                  </h4>

                  <div className="mt-3 flex flex-wrap gap-2">
                    {goodreadsResult.favorite_shelves.map((shelf) => (
                      <span
                        className="rounded-full border px-3 py-1 text-sm"
                        key={shelf}
                      >
                        {shelf}
                      </span>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}

          {loadingRecommendations && (
            <p className="mt-6">Ranking recommendations...</p>
          )}

          {recommendationError && (
            <p className="mt-6 rounded-lg border p-3">
              {recommendationError}
            </p>
          )}

          {recommendations && (
            <div className="mt-8 border-t pt-8">
              <h3 className="text-2xl font-semibold">
                Recommendations
              </h3>

              <p className="mt-2 text-sm opacity-70">
                Ranked {recommendations.candidate_count} candidate books from a
                seeded catalog using your {recommendations.profile_book_count}{" "}
                imported Goodreads books.
              </p>

              <div className="mt-5 grid gap-4 sm:grid-cols-2">
                {recommendations.recommendations.map(
                  (recommendation, index) => (
                    <article
                      className="rounded-xl border p-5"
                      key={`${recommendation.title}-${recommendation.author}`}
                    >
                      <div className="flex items-start justify-between gap-4">
                        <div>
                          <p className="text-sm opacity-60">
                            #{index + 1}
                          </p>

                          <h4 className="mt-1 text-lg font-semibold">
                            {recommendation.title}
                          </h4>

                          <p className="mt-1 opacity-80">
                            {recommendation.author}
                          </p>
                        </div>

                        <span className="shrink-0 rounded-full border px-3 py-1 text-sm">
                          {percentage(recommendation.score)}
                        </span>
                      </div>

                      <div className="mt-4 flex flex-wrap gap-2">
                        {recommendation.genres.map((genre) => (
                          <span
                            className="rounded-full border px-2 py-1 text-xs opacity-80"
                            key={genre}
                          >
                            {genre}
                          </span>
                        ))}
                      </div>

                      <div className="mt-4 space-y-2 text-sm opacity-75">
                        {recommendation.reasons.map((reason) => (
                          <p key={reason}>{reason}</p>
                        ))}
                      </div>

                      <p className="mt-4 text-xs opacity-50">
                        TF-IDF similarity:{" "}
                        {percentage(recommendation.similarity_score)}
                      </p>
                    </article>
                  ),
                )}
              </div>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}