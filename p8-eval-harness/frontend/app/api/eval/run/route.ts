import { NextRequest } from "next/server";

export const dynamic = "force-dynamic";

export async function POST(req: NextRequest) {
  const body = await req.json();
  const backendUrl = process.env.BACKEND_URL || "http://localhost:8001";

  let backendResp: Response;
  try {
    backendResp = await fetch(`${backendUrl}/eval/run`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
  } catch (err) {
    const msg = err instanceof Error ? err.message : String(err);
    return new Response(
      JSON.stringify({ detail: `Cannot reach P8 backend at ${backendUrl}: ${msg}` }),
      { status: 503, headers: { "Content-Type": "application/json" } }
    );
  }

  if (!backendResp.ok) {
    const text = await backendResp.text();
    return new Response(text, { status: backendResp.status });
  }

  return new Response(backendResp.body, {
    headers: {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      "X-Accel-Buffering": "no",
    },
  });
}
