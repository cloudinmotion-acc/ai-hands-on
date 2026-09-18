import { spawn, type ChildProcess } from 'child_process'
import fs from 'fs'
import path from 'path'

export const dynamic = 'force-dynamic'
export const maxDuration = 3600

const REPO_ROOT = path.resolve(process.cwd(), '..', '..')
const EVAL_DIR = path.join(REPO_ROOT, 'p3-rag-eval')

/** Prefer the repo-root .venv interpreter; fall back to whatever `python` resolves to. */
function resolvePython(): string {
  const candidates = [
    path.join(REPO_ROOT, '.venv', 'Scripts', 'python.exe'),
    path.join(REPO_ROOT, '.venv', 'bin', 'python'),
  ]
  return candidates.find(p => fs.existsSync(p)) ?? 'python'
}

// One eval at a time — run_eval.py writes checkpoint and report files, so a
// second run would race the first on the same paths. The lock is held by the
// child process, not by the HTTP stream: a client that disconnects stops
// watching, but the run keeps going and the lock stays until the process exits.
let activeChild: ChildProcess | null = null

export async function POST(request: Request) {
  if (activeChild) {
    return Response.json(
      { error: 'An evaluation is already running. Wait for it to finish.' },
      { status: 409 },
    )
  }
  if (!fs.existsSync(path.join(EVAL_DIR, 'run_eval.py'))) {
    return Response.json({ error: `run_eval.py not found in ${EVAL_DIR}` }, { status: 404 })
  }

  // Settings from the dashboard are handed to the script through a config file
  // rather than argv, so a plain `python run_eval.py` in a terminal picks up the
  // same knobs the UI last used.
  let config: unknown = null
  try {
    const body = await request.json()
    if (body && typeof body === 'object' && body.config) config = body.config
  } catch {
    // No body — the script falls back to eval_config.json or its own defaults.
  }
  if (config) {
    try {
      fs.writeFileSync(
        path.join(EVAL_DIR, 'eval_config.json'),
        JSON.stringify(config, null, 2),
        'utf-8',
      )
    } catch (e) {
      return Response.json(
        { error: `Could not write eval_config.json: ${(e as Error).message}` },
        { status: 500 },
      )
    }
  }

  const encoder = new TextEncoder()

  const stream = new ReadableStream({
    start(controller) {
      let watching = true

      const send = (event: string, data: unknown) => {
        if (!watching) return
        try {
          controller.enqueue(encoder.encode(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`))
        } catch {
          watching = false
        }
      }

      const closeStream = () => {
        if (!watching) return
        watching = false
        try { controller.close() } catch {}
      }

      const python = resolvePython()
      send('line', { text: `$ ${python} -u run_eval.py`, stream: 'meta' })
      send('line', { text: `  cwd: ${EVAL_DIR}`, stream: 'meta' })

      const child = spawn(python, ['-u', 'run_eval.py'], {
        cwd: EVAL_DIR,
        env: { ...process.env, PYTHONUNBUFFERED: '1', PYTHONIOENCODING: 'utf-8' },
      })
      activeChild = child

      // stdout and stderr each need their own line buffer so a partial line on
      // one pipe is not flushed by a newline arriving on the other.
      const pump = (source: NodeJS.ReadableStream, streamName: 'stdout' | 'stderr') => {
        let buffer = ''
        source.on('data', (chunk: Buffer) => {
          buffer += chunk.toString('utf-8')
          const lines = buffer.split(/\r?\n/)
          buffer = lines.pop() ?? ''
          for (const text of lines) send('line', { text, stream: streamName })
        })
        source.on('end', () => {
          if (buffer.length) send('line', { text: buffer, stream: streamName })
        })
      }

      pump(child.stdout!, 'stdout')
      pump(child.stderr!, 'stderr')

      child.on('error', err => {
        send('line', { text: `spawn failed: ${err.message}`, stream: 'stderr' })
        send('done', { code: 1 })
        activeChild = null
        closeStream()
      })

      child.on('close', code => {
        send('done', { code })
        activeChild = null
        closeStream()
      })
    },

    cancel() {
      // The client stopped watching. Leave the child running — run_eval.py
      // checkpoints between phases, and killing it mid-phase throws away work.
      // `activeChild` is cleared by the child's own close handler.
    },
  })

  return new Response(stream, {
    headers: {
      'Content-Type': 'text/event-stream; charset=utf-8',
      'Cache-Control': 'no-cache, no-transform',
      Connection: 'keep-alive',
      'X-Accel-Buffering': 'no',
    },
  })
}

/** Lets the dashboard tell "idle" from "a run is in flight I'm not watching". */
export async function GET() {
  return Response.json({ running: activeChild !== null })
}

/**
 * Force-stop the running evaluation.
 *
 * On Windows child.kill() only signals the python process itself; taskkill /T
 * takes the whole tree so nothing is left holding the NVIDIA connections.
 * run_eval.py checkpoints between phases, so a killed run resumes from the last
 * completed phase rather than starting over.
 */
export async function DELETE() {
  const child = activeChild
  if (!child || child.pid === undefined) {
    return Response.json({ stopped: false, reason: 'No evaluation is running.' }, { status: 409 })
  }

  if (process.platform === 'win32') {
    await new Promise<void>(resolve => {
      const killer = spawn('taskkill', ['/pid', String(child.pid), '/T', '/F'])
      killer.on('close', () => resolve())
      killer.on('error', () => { child.kill(); resolve() })
    })
  } else {
    child.kill('SIGTERM')
    // Escalate if it ignores the polite signal.
    setTimeout(() => { if (activeChild === child) child.kill('SIGKILL') }, 5000)
  }

  return Response.json({ stopped: true })
}
