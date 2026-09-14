"use client"

import { Settings } from "@/lib/api"
import { Label } from "@/components/ui/label"
import { Slider } from "@/components/ui/slider"
import { Switch } from "@/components/ui/switch"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"

const PROMPT_VERSIONS = ["v1 - Very Strict", "v2 - Moderate"]

type Props = {
  settings: Settings
  onChange: (s: Settings) => void
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="space-y-2">
      <Label className="text-xs text-muted-foreground">{label}</Label>
      {children}
    </div>
  )
}

export function SettingsPanel({ settings, onChange }: Props) {
  const p = settings.llm_params
  const set = (patch: Partial<typeof p>) =>
    onChange({ ...settings, llm_params: { ...p, ...patch } })

  return (
    <div className="flex flex-col gap-6 p-5 overflow-y-auto">
      <section className="space-y-4">
        <h3 className="font-heading text-[10px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
          Model & Retrieval
        </h3>

        <Row label="Model">
          <Input
            value={settings.model}
            onChange={e => onChange({ ...settings, model: e.target.value })}
            className="text-xs h-8"
          />
        </Row>

        <Row label="Prompt version">
          <Select
            value={settings.prompt_version}
            onValueChange={v => onChange({ ...settings, prompt_version: v })}
          >
            <SelectTrigger className="h-8 text-xs">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {PROMPT_VERSIONS.map(v => (
                <SelectItem key={v} value={v}>{v}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </Row>

        <Row label={`Top-K chunks — ${settings.top_k_chunks}`}>
          <Slider
            min={1} max={10} step={1}
            value={[settings.top_k_chunks]}
            onValueChange={([v]) => onChange({ ...settings, top_k_chunks: v })}
          />
        </Row>
      </section>

      <Separator />

      <section className="space-y-4">
        <h3 className="font-heading text-[10px] font-semibold uppercase tracking-[0.1em] text-muted-foreground">
          LLM Parameters
        </h3>

        <Row label={`Temperature — ${p.temperature}`}>
          <Slider min={0} max={2} step={0.05} value={[p.temperature]}
            onValueChange={([v]) => set({ temperature: v })} />
        </Row>

        <Row label={`Top-P — ${p.top_p}`}>
          <Slider min={0} max={1} step={0.05} value={[p.top_p]}
            onValueChange={([v]) => set({ top_p: v })} />
        </Row>

        <Row label={`Top-K — ${p.top_k}`}>
          <Slider min={1} max={200} step={1} value={[p.top_k]}
            onValueChange={([v]) => set({ top_k: v })} />
        </Row>

        <Row label={`Freq penalty — ${p.frequency_penalty}`}>
          <Slider min={0} max={2} step={0.1} value={[p.frequency_penalty]}
            onValueChange={([v]) => set({ frequency_penalty: v })} />
        </Row>

        <Row label={`Max tokens — ${p.max_tokens}`}>
          <Slider min={256} max={16384} step={256} value={[p.max_tokens]}
            onValueChange={([v]) => set({ max_tokens: v })} />
        </Row>

        <div className="flex items-center justify-between py-0.5">
          <Label className="text-xs text-muted-foreground">Enable thinking</Label>
          <Switch
            checked={p.enable_thinking}
            onCheckedChange={v => set({ enable_thinking: v })}
          />
        </div>
      </section>
    </div>
  )
}
