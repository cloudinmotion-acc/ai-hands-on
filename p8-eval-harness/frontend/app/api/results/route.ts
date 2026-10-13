import { NextResponse } from "next/server";
import fs from "fs";
import path from "path";

export const dynamic = "force-dynamic";

export async function GET() {
  const resultsDir = process.env.RESULTS_DIR || path.join(process.cwd(), "..", "results");
  const latest = path.join(resultsDir, "latest.json");

  if (!fs.existsSync(latest)) {
    return NextResponse.json(
      { error: "No results yet. Run an evaluation first." },
      { status: 404 }
    );
  }

  try {
    const data = JSON.parse(fs.readFileSync(latest, "utf-8"));
    return NextResponse.json(data);
  } catch {
    return NextResponse.json({ error: "Failed to read results file" }, { status: 500 });
  }
}
