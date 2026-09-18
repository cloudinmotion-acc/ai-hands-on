export async function GET() {
  const res = await fetch("http://127.0.0.1:8000/sources")
  const data = await res.json()
  return Response.json(data, { status: res.status })
}

export async function DELETE() {
  const res = await fetch("http://127.0.0.1:8000/sources", { method: "DELETE" })
  const data = await res.json()
  return Response.json(data, { status: res.status })
}
