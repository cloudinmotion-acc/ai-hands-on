import fs from 'fs'
import path from 'path'

const RESULTS_DIR = path.resolve(process.cwd(), '..', '..', 'p3-rag-eval', 'results')

export async function GET(request: Request) {
  const { searchParams } = new URL(request.url)
  const report = searchParams.get('report')

  try {
    if (report) {
      const filePath = path.resolve(RESULTS_DIR, report)
      const rel = path.relative(RESULTS_DIR, filePath)
      if (rel.startsWith('..') || path.isAbsolute(rel)) {
        return Response.json({ error: 'Invalid report path' }, { status: 400 })
      }
      const data = JSON.parse(fs.readFileSync(filePath, 'utf-8'))
      return Response.json(data)
    }

    const files = fs
      .readdirSync(RESULTS_DIR)
      .filter(f => f.startsWith('report_') && f.endsWith('.json'))
      .sort()
      .reverse()

    return Response.json({ reports: files })
  } catch {
    return Response.json({ error: 'No reports found' }, { status: 404 })
  }
}
