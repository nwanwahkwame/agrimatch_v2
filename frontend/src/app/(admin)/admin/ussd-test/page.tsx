'use client'

import { useState, useRef, useEffect } from 'react'
import Link from 'next/link'
import { ArrowLeft, Send, RefreshCw, Phone, Terminal } from 'lucide-react'
import axios from 'axios'

// ─── Types ─────────────────────────────────────────────────────────────────────

interface HistoryEntry {
  seq: number
  input: string
  response: string
  type: 'CON' | 'END'
  ts: string
}

// ─── Helpers ───────────────────────────────────────────────────────────────────

function newSessionId(): string {
  return `sim-${Math.random().toString(36).slice(2, 10)}-${Date.now()}`
}

function parseResponse(raw: string): { type: 'CON' | 'END'; body: string } {
  if (raw.startsWith('CON ')) return { type: 'CON', body: raw.slice(4) }
  if (raw.startsWith('END ')) return { type: 'END', body: raw.slice(4) }
  return { type: 'CON', body: raw }
}

function parseMenuOptions(body: string): Array<{ label: string; value: string }> {
  return body
    .split('\n')
    .map(line => line.match(/^(\d+)\.\s+(.+)/))
    .filter(Boolean)
    .map(m => ({ label: m![2], value: m![1] }))
}

function nowStr(): string {
  return new Date().toLocaleTimeString('en-GB', { hour: '2-digit', minute: '2-digit', second: '2-digit' })
}

// ─── Page ──────────────────────────────────────────────────────────────────────

export default function UssdTestPage() {
  const [phone,     setPhone]     = useState('+233244999888')
  const [sessionId, setSessionId] = useState(newSessionId)
  const [inputText, setInputText] = useState('')
  const [loading,   setLoading]   = useState(false)
  const [history,   setHistory]   = useState<HistoryEntry[]>([])
  const [lastResp,  setLastResp]  = useState<{ type: 'CON' | 'END'; body: string } | null>(null)
  const histRef = useRef<HTMLDivElement>(null)
  const seq = useRef(0)

  useEffect(() => {
    if (histRef.current) {
      histRef.current.scrollTop = histRef.current.scrollHeight
    }
  }, [history])

  async function send() {
    if (loading) return
    setLoading(true)
    const currentInput = inputText
    try {
      const params = new URLSearchParams({
        sessionId,
        serviceCode: '*384#',
        phoneNumber: phone,
        text: currentInput,
      })
      const resp = await axios.post(
        'http://localhost:8000/api/ussd',
        params.toString(),
        { headers: { 'Content-Type': 'application/x-www-form-urlencoded' }, timeout: 15_000 },
      )
      const raw = String(resp.data)
      const parsed = parseResponse(raw)
      setLastResp(parsed)
      setHistory(h => [...h, {
        seq: ++seq.current,
        input: currentInput,
        response: raw,
        type: parsed.type,
        ts: nowStr(),
      }])
      if (parsed.type === 'END') {
        setInputText('')
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : 'Request failed'
      setLastResp({ type: 'END', body: `Error: ${msg}` })
      setHistory(h => [...h, {
        seq: ++seq.current,
        input: currentInput,
        response: `END Error: ${msg}`,
        type: 'END',
        ts: nowStr(),
      }])
    } finally {
      setLoading(false)
    }
  }

  function appendChoice(value: string) {
    setInputText(prev => prev ? `${prev}*${value}` : value)
  }

  function resetSession() {
    setSessionId(newSessionId())
    setInputText('')
    setLastResp(null)
    setHistory([])
    seq.current = 0
  }

  const menuOptions = lastResp?.type === 'CON' ? parseMenuOptions(lastResp.body) : []
  const isEnded = lastResp?.type === 'END'

  return (
    <div className="min-h-screen bg-[#F7FAF8]">

      {/* Header */}
      <section
        className="px-6 py-6"
        style={{
          background: '#145228',
          backgroundImage: 'radial-gradient(circle, rgba(255,255,255,0.04) 1px, transparent 1px)',
          backgroundSize: '20px 20px',
        }}
      >
        <div className="mx-auto max-w-screen-xl">
          <Link
            href="/admin"
            className="mb-3 inline-flex items-center gap-1.5 text-sm text-[#7DCFA0] hover:text-white transition-colors"
          >
            <ArrowLeft className="h-3.5 w-3.5" />
            Admin dashboard
          </Link>
          <div className="flex items-center gap-3">
            <Terminal className="h-6 w-6 text-[#4DB876]" />
            <div>
              <h1 className="font-display text-2xl font-bold text-white">USSD Simulator</h1>
              <p className="mt-0.5 text-sm text-[#7DCFA0]">Test the *384# flow without a real handset</p>
            </div>
          </div>
        </div>
      </section>

      <div className="mx-auto max-w-screen-xl px-6 py-8">
        <div className="grid gap-6 lg:grid-cols-2">

          {/* ── Left: Phone simulator ────────────────────────────── */}
          <div className="flex flex-col gap-4">
            <div className="rounded-xl border border-[#C8D8D2] bg-white shadow-sm p-5">
              <h2 className="font-display mb-4 text-base font-bold text-[#0F1613]">Session config</h2>

              <div className="flex flex-col gap-3">
                <div>
                  <label className="mb-1 block text-xs font-medium text-[#445E54]">
                    <Phone className="inline h-3.5 w-3.5 mr-1" />
                    Phone number
                  </label>
                  <input
                    type="text"
                    value={phone}
                    onChange={e => setPhone(e.target.value)}
                    className="w-full rounded-lg border border-[#C8D8D2] px-3 py-2 text-sm text-[#0F1613] focus:outline-none focus:ring-2 focus:ring-[#1D6B3A]/30"
                    placeholder="+233244999888"
                  />
                </div>

                <div>
                  <label className="mb-1 block text-xs font-medium text-[#445E54]">Session ID</label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={sessionId}
                      readOnly
                      className="flex-1 rounded-lg border border-[#C8D8D2] bg-[#F7FAF8] px-3 py-2 font-mono text-xs text-[#445E54]"
                    />
                    <button
                      onClick={resetSession}
                      title="Start new session"
                      className="flex items-center gap-1.5 rounded-lg border border-[#C8D8D2] px-3 py-2 text-xs text-[#445E54] hover:bg-[#EEF4F1] transition-colors"
                    >
                      <RefreshCw className="h-3.5 w-3.5" />
                      New
                    </button>
                  </div>
                </div>

                <div>
                  <label className="mb-1 block text-xs font-medium text-[#445E54]">
                    Input text <span className="text-[#7A9088]">(keypresses joined with *)</span>
                  </label>
                  <div className="flex gap-2">
                    <input
                      type="text"
                      value={inputText}
                      onChange={e => setInputText(e.target.value)}
                      onKeyDown={e => e.key === 'Enter' && !isEnded && send()}
                      className="flex-1 rounded-lg border border-[#C8D8D2] px-3 py-2 font-mono text-sm text-[#0F1613] focus:outline-none focus:ring-2 focus:ring-[#1D6B3A]/30"
                      placeholder="e.g. 1*1*50*3*1"
                      disabled={isEnded}
                    />
                    <button
                      onClick={send}
                      disabled={loading || isEnded}
                      className={`flex items-center gap-1.5 rounded-lg px-4 py-2 text-sm font-medium transition-colors ${
                        isEnded
                          ? 'bg-[#EEF4F1] text-[#7A9088] cursor-default'
                          : 'bg-[#1D6B3A] text-white hover:bg-[#145228]'
                      }`}
                    >
                      {loading ? (
                        <RefreshCw className="h-4 w-4 animate-spin" />
                      ) : (
                        <Send className="h-4 w-4" />
                      )}
                      Send
                    </button>
                  </div>
                </div>
              </div>
            </div>

            {/* Response panel */}
            <div className="rounded-xl border border-[#C8D8D2] bg-white shadow-sm overflow-hidden">
              <div className={`px-5 py-3 text-sm font-semibold ${
                !lastResp            ? 'bg-[#F7FAF8] text-[#7A9088]' :
                lastResp.type === 'CON' ? 'bg-[#E8F5EE] text-[#1D6B3A]' :
                                         'bg-red-50 text-red-700'
              }`}>
                {!lastResp ? 'No response yet — send an empty input to dial *384#' :
                 lastResp.type === 'CON' ? 'CON — session continues' :
                                           'END — session closed'}
              </div>

              {lastResp && (
                <div className="px-5 py-4">
                  <pre className="whitespace-pre-wrap font-mono text-sm text-[#2D3F38] leading-relaxed">
                    {lastResp.body}
                  </pre>

                  {/* Clickable menu buttons */}
                  {menuOptions.length > 0 && (
                    <div className="mt-4 border-t border-[#EEF4F1] pt-4">
                      <p className="mb-2 text-xs font-medium text-[#7A9088]">Quick-select (appends to input):</p>
                      <div className="flex flex-wrap gap-2">
                        {menuOptions.map(opt => (
                          <button
                            key={opt.value}
                            onClick={() => appendChoice(opt.value)}
                            className="rounded-lg border border-[#1D6B3A] px-3 py-1.5 text-xs font-medium text-[#1D6B3A] hover:bg-[#E8F5EE] transition-colors"
                          >
                            {opt.value}. {opt.label}
                          </button>
                        ))}
                      </div>
                    </div>
                  )}

                  {isEnded && (
                    <div className="mt-4 border-t border-[#EEF4F1] pt-4">
                      <button
                        onClick={resetSession}
                        className="flex items-center gap-1.5 rounded-lg bg-[#1D6B3A] px-4 py-2 text-sm font-medium text-white hover:bg-[#145228] transition-colors"
                      >
                        <RefreshCw className="h-4 w-4" />
                        Start new session
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* ── Right: Session history ────────────────────────────── */}
          <div className="rounded-xl border border-[#C8D8D2] bg-white shadow-sm overflow-hidden flex flex-col">
            <div className="border-b border-[#EEF4F1] px-5 py-3 flex items-center justify-between">
              <h2 className="font-display text-base font-bold text-[#0F1613]">Session history</h2>
              {history.length > 0 && (
                <span className="rounded-full bg-[#EEF4F1] px-2.5 py-0.5 text-xs text-[#445E54]">
                  {history.length} request{history.length !== 1 ? 's' : ''}
                </span>
              )}
            </div>

            <div
              ref={histRef}
              className="flex-1 overflow-y-auto p-4 space-y-3"
              style={{ maxHeight: '520px' }}
            >
              {history.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-16 text-center">
                  <Terminal className="mb-3 h-10 w-10 text-[#C8D8D2]" />
                  <p className="text-sm text-[#7A9088]">History will appear here as you send requests</p>
                  <p className="mt-1 text-xs text-[#7A9088]">Tip: send empty input to start the flow</p>
                </div>
              ) : (
                history.map(entry => (
                  <div
                    key={entry.seq}
                    className="rounded-lg border border-[#EEF4F1] bg-[#F7FAF8] overflow-hidden"
                  >
                    {/* Request line */}
                    <div className="flex items-center justify-between border-b border-[#EEF4F1] px-3 py-2 bg-[#EEF4F1]">
                      <span className="font-mono text-xs text-[#445E54]">
                        text=&quot;{entry.input || '(empty)'}&quot;
                      </span>
                      <span className="text-xs text-[#7A9088]">{entry.ts}</span>
                    </div>
                    {/* Response */}
                    <div className="px-3 py-2">
                      <span className={`mr-2 rounded px-1.5 py-0.5 text-xs font-bold ${
                        entry.type === 'CON' ? 'bg-[#E8F5EE] text-[#1D6B3A]' : 'bg-red-100 text-red-700'
                      }`}>
                        {entry.type}
                      </span>
                      <span className="font-mono text-xs text-[#2D3F38]">
                        {entry.response.slice(4, 80)}{entry.response.length > 84 ? '...' : ''}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        </div>

        {/* Usage guide */}
        <div className="mt-6 rounded-xl border border-[#C8D8D2] bg-white p-5 shadow-sm">
          <h3 className="font-display mb-3 text-sm font-bold text-[#0F1613]">Test flow cheatsheet</h3>
          <div className="grid gap-3 text-xs text-[#445E54] sm:grid-cols-2 lg:grid-cols-4">
            {[
              { step: '1', label: 'Dial',         input: '(empty)',       desc: 'Welcome screen' },
              { step: '2', label: 'Name',          input: 'Ama',           desc: 'Enter name' },
              { step: '3', label: 'Region',        input: 'Ama*1',         desc: 'Pick Ashanti' },
              { step: '4', label: 'Confirm reg',   input: 'Ama*1*1',       desc: 'Confirm registration' },
              { step: '5', label: 'List produce',  input: '1',             desc: 'Go to produce menu (new session)' },
              { step: '6', label: 'Select crop',   input: '1*1',           desc: 'Choose Maize' },
              { step: '7', label: 'Enter qty',     input: '1*1*50',        desc: '50 bags' },
              { step: '8', label: 'Harvest time',  input: '1*1*50*3',      desc: '3 weeks' },
            ].map(({ step, label, input, desc }) => (
              <div key={step} className="rounded-lg bg-[#F7FAF8] px-3 py-2.5">
                <span className="mr-1.5 inline-flex h-4 w-4 items-center justify-center rounded-full bg-[#1D6B3A] text-[10px] font-bold text-white">{step}</span>
                <span className="font-medium text-[#2D3F38]">{label}</span>
                <code className="mt-1 block rounded bg-[#EEF4F1] px-2 py-0.5 font-mono text-[11px]">{input}</code>
                <span className="mt-0.5 block text-[#7A9088]">{desc}</span>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  )
}
