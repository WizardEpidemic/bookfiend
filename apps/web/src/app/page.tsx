"use client";

import { useEffect, useState } from "react";

type HealthResponse = {
  api: string;
  database: string;
  redis: string;
};

export default function Home() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const apiUrl = process.env.NEXT_PUBLIC_API_URL;

    fetch(`${apiUrl}/health`)
      .then((response) => {
        if (!response.ok) {
          throw new Error("API health check failed");
        }

        return response.json();
      })
      .then((data: HealthResponse) => {
        setHealth(data);
      })
      .catch(() => {
        setError("Could not connect to the BookFiend API.");
      });
  }, []);

  return (
    <main className="flex min-h-screen items-center justify-center p-8">
      <div className="max-w-xl text-center">
        <h1 className="text-5xl font-bold">BookFiend</h1>

        <p className="mt-4 text-lg">
          Turn bookshelf photos into a structured library and personalized
          recommendations.
        </p>

        <div className="mt-8 rounded-xl border p-6 text-left">
          <h2 className="text-xl font-semibold">System Status</h2>

          {error && <p className="mt-4">{error}</p>}

          {!health && !error && <p className="mt-4">Checking services...</p>}

          {health && (
            <div className="mt-4 space-y-2">
              <p>API: {health.api}</p>
              <p>PostgreSQL: {health.database}</p>
              <p>Redis: {health.redis}</p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}