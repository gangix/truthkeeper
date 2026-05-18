"use client";

import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";

const BACKEND_URL =
  process.env.NEXT_PUBLIC_BACKEND_URL ?? "http://localhost:8080";

export default function Home() {
  const [status, setStatus] = useState<string>("not checked");
  const [pinging, setPinging] = useState(false);

  const pingBackend = async () => {
    setPinging(true);
    setStatus("pinging…");
    try {
      const res = await fetch(`${BACKEND_URL}/health`);
      const json = (await res.json()) as { status: string; service: string };
      setStatus(`${json.service}: ${json.status}`);
    } catch (err) {
      setStatus(`error: ${(err as Error).message}`);
    } finally {
      setPinging(false);
    }
  };

  useEffect(() => {
    pingBackend();
  }, []);

  return (
    <main className="flex min-h-screen flex-col items-center justify-center gap-8 p-8">
      <h1 className="text-5xl font-bold tracking-tight">TruthKeeper</h1>
      <p className="text-xl text-muted-foreground">
        Your stack is lying to itself.
      </p>
      <div className="rounded-lg border bg-card p-6 text-card-foreground">
        <p className="text-sm uppercase tracking-wider text-muted-foreground">
          Backend status
        </p>
        <p className="mt-2 font-mono text-lg">{status}</p>
        <Button
          onClick={pingBackend}
          disabled={pinging}
          className="mt-4"
          variant="outline"
        >
          {pinging ? "Pinging…" : "Ping backend"}
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Backend URL: <code>{BACKEND_URL}</code>
      </p>
    </main>
  );
}
