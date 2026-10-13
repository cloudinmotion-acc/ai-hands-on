# P7 - Requirement-to-Design Architect Bot · Demo Notes

---

## The Problem

Every senior engineer has seen this pattern: a product manager drops a paragraph of requirements into a Slack thread on Monday. By Friday there's a Confluence page that sort of looks like a design, written by whoever had time. Nobody checked whether the scope was accurate. Nobody reviewed whether the LLD matches the HLD. Nobody asked "did we miss any risks?"

Most AI portfolios show AI that answers questions. P7 shows AI that does design work - and then stops and asks you whether it got it right before moving to the next step.

That's a different category of system. It's not autocomplete. It's a collaborator.

---

## The Solution

A five-stage LangGraph pipeline where each stage is a specialist agent, and a human sits between every two stages.

```
Requirement
  → Scoping agent     (what are we building, what's out of scope, what are the risks)
  ↓ Human reviews + approves or edits
  → Solution agent    (approach, tech stack, NFRs)
  ↓ Human reviews + approves or edits
  → HLD agent         (components, data flow, interfaces)
  ↓ Human reviews + approves or edits
  → LLD agent         (schemas, DDL, API contracts)
  ↓ Human reviews + approves or edits
  → Doc assembler     (packages everything into a .docx)
```

The graph **pauses after every agent** and waits. If you approve, it resumes. If you edit, it uses your version as the input to the next stage - the edit propagates forward. If you close the tab and come back tomorrow, your session is exactly where you left it.

---

## What Makes This Different

**vs. one big LLM call that outputs a full design doc:**
You have no control. The LLM might miss half the requirements, hallucinate a constraint, or write an HLD that doesn't match the solution architecture - and you only notice when you read the whole output. P7 catches the error at stage 1, before it compounds through stages 2, 3, and 4.

**vs. a chatbot that answers design questions:**
A chatbot responds to what you ask. P7 proactively structures the work: scope first, then solution, then HLD, then LLD. It's opinionated about process. The output is always a complete design document, not a conversation transcript.

**vs. an AI that just runs all stages automatically:**
The human gate is the feature, not a limitation. In real engineering, scoping decisions have downstream consequences. If you let the LLM decide what's in scope, it will make confident, wrong assumptions that poison every subsequent stage. The interrupt pattern forces a checkpoint where a human can correct the trajectory before the next agent spends tokens going in the wrong direction.

**vs. Copilot or a code assistant:**
Those tools work at the implementation level. P7 works at the design level - before a single line of code is written. The output of P7 is the input you'd normally give to a development team.

---

## Test Requirement

Use this for the demo - it's complex enough to generate interesting multi-stage output:

```
Build a LinkedIn post scheduling assistant that lets content creators write post
drafts, schedule them for optimal engagement times, and get AI-suggested reactions.
It should support multiple social accounts and provide analytics on post performance.
```

---

## Test Scenarios

### Happy path - approve every stage

1. Paste the requirement above, click **Start Design**
2. Watch scoping stream live (Activity: "Agent: Scoping" → "Memory saved → scoping" → "Review: scoping")
3. Approve → Solution streams live
4. Approve → HLD streams live (this takes ~60s, it's detailed)
5. Approve → LLD streams live (schemas, DDL, API contracts)
6. Approve → doc assembles, .docx download appears

**What to narrate:** "Each stage only runs after you approve the previous one. The trace counter in the header shows every SSE event - node_start, tokens, checkpoint_saved, checkpoint_restored - the full picture of what the system did."

---

### Edit scoping before continuing

After scoping generates, click **Edit** instead of Approve. Add a constraint:

```
Add constraint: must integrate with existing company SSO (Azure AD). No new user database.
```

Click **Submit Edit**. Watch the solution agent pick this up and design around Azure AD instead of proposing a new auth system.

**What to narrate:** "The edit propagates forward. The solution agent receives my edited scope - with the Azure AD constraint - not the original. This is the difference between a human-in-the-loop system and a pipeline that just runs."

---

### Regenerate a stage

After HLD is approved, click the regenerate icon on **Solution** in the left sidebar. Confirm the dialog. Watch scoping stay intact (it was approved), solution re-generates, HLD and LLD are cleared.

**What to narrate:** "I can wind back to any stage and re-run from there. The graph uses the SQLite checkpoint to know what's approved and what needs to be cleared. I didn't have to start over from scratch."

---

### Page refresh - session survival

While a stage is generating (or after any approval), hit **F5**. The page reloads. Watch the session restore - requirement visible, approved stages back, current stage showing the review card exactly where you left it.

**What to narrate:** "This is the checkpoint system. LangGraph saved the state to SQLite on every interrupt. The thread_id is in localStorage. On reload, the frontend called GET /sessions/{id}/state, got everything back, and rebuilt the UI from the checkpoint. Close the tab, come back an hour later - it's still here."

---

### View the full trace

Click **Trace (N)** in the header at any point during or after the session.

The drawer shows:
- Blue `Cpu` icon → when each agent started
- Lightning → how many tokens that stage streamed
- Green checkmark → stage complete + char count
- Violet `Save` → SQLite checkpoint written (memory in)
- Violet `Refresh` → checkpoint restored (memory out)
- Amber clock → awaiting review (graph paused)

**What to narrate:** "This is the full SSE event log from the backend. Every time you see 'Memory saved' followed by 'Memory restored', that's the checkpoint cycle - graph paused, human approved, graph resumed from exactly that state. You can see the exact timestamps: how long each agent took, how long you spent reviewing, when tokens started flowing."

---

## Demo Tour

### Before you start

- [ ] Backend running: `uvicorn main:app --port 8000` from `p7-full-version/backend/`
- [ ] Frontend running: `npm run dev` from `p7-full-version/frontend/` (port 3002)
- [ ] `.env` has `NVIDIA_API_KEY` and `AGENT_MODEL` set
- [ ] Have the test requirement copied and ready to paste
- [ ] Open `http://localhost:3002` in a clean tab

---

### Step 1 - Start the session

**Do:** Paste the requirement, click **Start Design**.

**Say:**
> "One paragraph. That's the entire input. Five agents are about to read this and produce a complete system design - but they're going to stop and ask me before they compound anything."

**Watch:** The Activity feed in the sidebar updates in real time: "Agent: Scoping", then tokens start streaming in the main panel.

**Say:**
> "This is the scoping agent running. It's figuring out what's in scope, what's explicitly excluded, what the success criteria are, and what the risks are. I can watch it think."

---

### Step 2 - First interrupt - approve or edit

When scoping completes, the amber "Review required" card appears.

**Say:**
> "The graph paused. LangGraph's interrupt_after fired after the scoping node completed - it saved a checkpoint to SQLite and stopped. I have to make a decision before solution can run."

**Point to the sidebar Activity:**
> "See: 'Memory saved → scoping'. That's the SQLite checkpoint. If I close this tab right now, that state is persisted. I come back tomorrow, same session."

**Do:** Scroll through the scope output. Then click **Approve & Continue**.

**Say:**
> "Approve. Watch the trace counter tick up - checkpoint_restored event fires as the graph reads the saved state and resumes. Then node_start for solution."

---

### Step 3 - Watch the trace drawer

**Do:** While solution is streaming, click **Trace (N)** in the header.

**Say:**
> "This is the full SSE event log. Every message the backend sent. You can see: agent started, tokens streamed, stage complete, memory saved, awaiting review, memory restored, next agent started. This is the actual execution graph, visible in the browser."

**Point to the violet memory events:**
> "Every violet icon is a memory event - the checkpoint system working. Memory saved means the graph paused and wrote state to SQLite. Memory restored means it read that state back and resumed. That's how the session survives refresh."

---

### Step 4 - Edit a stage (optional, if time allows)

When HLD appears, click **Edit** instead of Approve.

**Do:** Add one sentence to the HLD: "All services must be deployable as Docker containers on AWS ECS."

**Say:**
> "I don't agree with this component boundary. I'm editing the HLD directly - my version will be what the LLD agent receives. The LLD will design schemas and APIs that match my architecture, not the one the AI initially proposed."

---

### Step 5 - Show page refresh survival

After at least one stage is approved, hit **F5**.

**Say:**
> "Page reload. Watch the session come back."

**Wait for restore:** The approved stages reappear, the current review card shows.

**Say:**
> "That's localStorage holding the thread_id, and GET /sessions/{id}/state pulling the full state from the SQLite checkpoint. No re-running anything. The graph is exactly where I left it."

---

### Step 6 - Final document

After approving LLD, the doc assembler runs (no human gate here - it's just assembly). When complete, the document preview appears.

**Do:** Click **Download .docx**.

**Say:**
> "A complete system design document. Scope, solution architecture, HLD, LLD - assembled from four approved stage outputs into a Word file. This is what you'd hand to a development team. One paragraph in, production-ready design doc out - with a human checking every step."

---

## Code Walkthrough

### `graph/builder.py` - the interrupt mechanism

**Key line:**
```python
return g.compile(
    checkpointer=checkpointer,
    interrupt_after=["scoping", "solution", "hld", "lld"],
)
```

`interrupt_after` tells LangGraph to pause the graph after each of these nodes completes. The graph saves its full state to the checkpointer (SQLite), then stops. The `astream_events` generator terminates. The backend detects `state.next` is non-empty and emits `awaiting_review`. Nothing continues until `/resume` is called.

**Why not just use a flag in state?**
You could poll a flag. But `interrupt_after` is atomic - the graph cannot proceed past the interrupt without an explicit `aupdate_state + astream_events(None, config)` call. There's no race condition. The human gate is enforced at the graph level, not the application level.

---

### `main.py` - the resume and regenerate logic

**Resume (approve path):**
```python
# Mark the stage as approved in state
await graph.aupdate_state(config, {state_key: {"approved": True, ...}})

# Resume - pass None as input (graph reads from checkpoint)
return StreamingResponse(_stream_graph(session_id, None, is_resume=True), ...)
```

Passing `None` as input to `astream_events` tells LangGraph: "read the last checkpoint and continue from there." The checkpoint has `next = ["solution"]` so it picks up at the solution node.

**Regenerate (ripple-forward):**
```python
if idx == 0:
    # Restart from scratch with fresh initial state
    return StreamingResponse(_stream_graph(session_id, {**state.values, **clear_update}), ...)
else:
    # Wind graph back to after the previous stage, then resume
    prev_stage = STAGE_ORDER[idx - 1]
    await graph.aupdate_state(config, clear_update, as_node=prev_stage)
    return StreamingResponse(_stream_graph(session_id, None), ...)
```

`as_node=prev_stage` is the key: it tells LangGraph "pretend the previous stage just finished" - so `state.next` becomes the current stage, and the graph resumes from there. No manual graph rewinding needed.

---

### `agents/base.py` - safe_format()

```python
def safe_format(template: str, **kwargs: str) -> str:
    for key, value in kwargs.items():
        template = template.replace("{" + key + "}", value)
    return template
```

**Why not `str.format()`?**
The HLD and LLD agents receive prior stage outputs as context. Those outputs often contain `{field_name}` patterns - JSON schemas, API contracts, database column names like `{items, userId}`. Python's `str.format()` tries to interpolate those as format variables and raises `KeyError`. `safe_format()` only replaces the exact placeholder keys you pass in - any other `{...}` in the content is untouched.

---

### `agents/lld.py` - context compaction

```python
_SUMMARY_LIMIT = 800

async def run(requirement, scope, solution, hld):
    scope_summary = scope[:_SUMMARY_LIMIT]
    solution_summary = solution[:_SUMMARY_LIMIT]
    msg = safe_format(PROMPT,
        scope_summary=scope_summary,
        solution_summary=solution_summary,
        hld=hld,       # full HLD - this is what LLD builds from
    )
```

By stage 4, the accumulated context (requirement + scope + solution + HLD) can be 15,000+ characters. Passing everything in full to every agent risks hitting context limits and adds token cost. LLD only needs the HLD in detail - scope and solution are summarised to 800 chars each (enough to stay grounded without repeating everything).

---

### `frontend/components/TraceDrawer.tsx` - collapse()

```typescript
function collapse(entries) {
    // Collapse consecutive token events into one "N tokens streamed" row
    while (i < entries.length) {
        if (e.event.type === "token") {
            // count them all
            out.push({ type: "token_batch", count, ts });
        } else {
            out.push(e);
        }
    }
}
```

A 2000-token stage generates 2000 individual SSE events. Showing 2000 rows in the trace drawer is useless. The collapse function groups consecutive token events into a single "2049 tokens streamed" row. All other event types (node_start, checkpoint_saved, awaiting_review) are shown individually because they represent meaningful state transitions.

---

### Session persistence - the full cycle

```
1. User opens page → useEffect reads thread_id from localStorage
2. If found → GET /sessions/{id}/state → rebuild UI from checkpoint
3. User approves → POST /resume → graph.aupdate_state + astream_events(None)
4. Stage completes → backend emits checkpoint_saved + awaiting_review
5. Frontend shows review card
6. User closes tab → state is in SQLite, thread_id is in localStorage
7. User reopens tab → step 1 again
```

The thread_id is the only thing in localStorage. Everything else - the full conversation, all stage outputs, the graph position, what's approved and what isn't - lives in the SQLite checkpoint. The browser is stateless between visits. The checkpoint is the single source of truth.

---

## New Concepts to Stress

### LangGraph interrupt_after

LangGraph's mechanism for pausing a stateful graph at a specific node. After the node's function returns, LangGraph saves the full graph state to the checkpointer and stops execution. The `state.next` field tells you which node would run next when resumed. Resuming requires explicitly calling `aupdate_state` (to apply any human edits) followed by `astream_events(None, config)` with the same thread_id. The graph reads the checkpoint and continues from the exact point it stopped.

### HITL (Human-in-the-Loop)

A design pattern where a human provides input or approval at specific points in an automated pipeline. The alternative is fully automated - but fully automated design systems either produce generic output (no context about what you actually want) or require extensive prompt engineering to constrain the output. HITL externalises the constraint: the human is the constraint. The AI produces the best output it can; the human corrects the direction before the next stage amplifies any errors.

### SQLite Checkpointing

LangGraph's `AsyncSqliteSaver` writes a snapshot of the full graph state after every node completes. The snapshot includes all state values (scoping output, solution output, etc.), the graph's current position (which node just ran), and the interrupt metadata (which node is next). This makes sessions durable: a server restart, a browser close, or a network blip doesn't lose progress. The thread_id is the key - if you know the thread_id, you can restore any session on any server that shares the same SQLite file.

### Context Compaction

The problem of managing long context as a multi-stage pipeline accumulates outputs. Each stage's output becomes context for the next stage. By stage 4, you're potentially passing 15,000+ characters to every LLM call. Compaction strategies: truncation (P7's approach - first 800 chars of early stages), summarisation (ask an LLM to write a 200-word summary of the scope), selective passing (only pass the most recent stage in full, summarise everything before it). P7 uses truncation because the critical information in scope and solution is usually in the first 800 characters.

### SSE Streaming with State Machines

The frontend treats the SSE event stream as a state machine: `node_start` → streaming mode; `stage_complete` → update sessionState; `checkpoint_saved` → activity feed; `awaiting_review` → show review card; `checkpoint_restored` → resume started; `session_complete` → show download. Each event transitions the UI to a new state. The frontend never polls - it reacts to events. This means the UI is always consistent with the backend's actual state, not an estimate of it.

---

## Conclusion

P7 is the most architecturally complex project in the portfolio. Every previous project shows a single capability: extract structured data, retrieve context, evaluate quality, call tools, add guardrails. P7 combines all of them into a system that's genuinely useful - it does something you'd otherwise spend four hours doing manually, and it lets you stay in control at every step.

The key ideas to leave the interviewer with:

1. **Stateful AI is different from stateless AI.** Every project before P7 is stateless - one request in, one response out. P7 maintains state across multiple turns, across page refreshes, across time. This is what production AI systems look like.

2. **HITL is not a workaround for bad AI.** It's the correct architecture for high-stakes tasks. The human gate exists because design decisions have downstream consequences - a scoping error compounds through solution, HLD, and LLD. Catching it at stage 1 costs one review. Catching it at stage 4 costs a complete restart.

3. **The checkpoint is the memory.** LangGraph's SQLite checkpointer is what makes the session durable. Understanding the checkpoint cycle - when state is written, when it's read, what it contains - is what separates "I used LangGraph" from "I understand LangGraph."
