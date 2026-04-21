import { useState, useRef, useEffect } from "react";

const API = "http://localhost:8000/api/v1";

// ── Palette ───────────────────────────────────────────────────────────────────
const C = {
  bg:      "#0a0d14",
  surface: "#111520",
  card:    "#161b28",
  border:  "#1e2535",
  accent:  "#3b82f6",
  accentD: "#2563eb",
  green:   "#22c55e",
  red:     "#ef4444",
  amber:   "#f59e0b",
  text:    "#e2e8f0",
  muted:   "#64748b",
  purple:  "#8b5cf6",
};

// ── Small UI helpers ──────────────────────────────────────────────────────────
function Badge({ color, children }) {
  return (
    <span style={{
      background: color + "22", color, border: `1px solid ${color}44`,
      borderRadius: 6, padding: "2px 8px", fontSize: 11, fontWeight: 600,
      letterSpacing: "0.04em", textTransform: "uppercase",
    }}>{children}</span>
  );
}

function Card({ children, style }) {
  return (
    <div style={{
      background: C.card, border: `1px solid ${C.border}`,
      borderRadius: 12, padding: 20, ...style,
    }}>{children}</div>
  );
}

function Btn({ children, onClick, disabled, color = C.accent, style }) {
  const [hover, setHover] = useState(false);
  return (
    <button
      onClick={onClick} disabled={disabled}
      onMouseEnter={() => setHover(true)} onMouseLeave={() => setHover(false)}
      style={{
        background: disabled ? C.border : hover ? color + "dd" : color,
        color: "#fff", border: "none", borderRadius: 8,
        padding: "9px 18px", cursor: disabled ? "not-allowed" : "pointer",
        fontWeight: 600, fontSize: 13, transition: "all .15s",
        opacity: disabled ? 0.5 : 1, ...style,
      }}>{children}</button>
  );
}

// ── Status badge ──────────────────────────────────────────────────────────────
function StatusBadge({ status }) {
  const map = {
    pending:               [C.muted,  "Pending"],
    running:               [C.accent, "Running"],
    awaiting_confirmation: [C.amber,  "Awaiting Confirmation"],
    completed:             [C.green,  "Completed"],
    failed:                [C.red,    "Failed"],
  };
  const [color, label] = map[status] || [C.muted, status];
  return <Badge color={color}>{label}</Badge>;
}

// ── Animated mic button ───────────────────────────────────────────────────────
function MicButton({ recording, onClick }) {
  return (
    <button onClick={onClick} style={{
      width: 64, height: 64, borderRadius: "50%",
      background: recording ? C.red : C.accent,
      border: "none", cursor: "pointer",
      display: "flex", alignItems: "center", justifyContent: "center",
      boxShadow: recording
        ? `0 0 0 8px ${C.red}33, 0 0 0 16px ${C.red}11`
        : `0 0 0 0 transparent`,
      transition: "all .25s",
      animation: recording ? "pulse 1.2s infinite" : "none",
    }}>
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2" strokeLinecap="round">
        <rect x="9" y="2" width="6" height="11" rx="3"/>
        <path d="M5 10a7 7 0 0 0 14 0M12 19v3M8 22h8"/>
      </svg>
    </button>
  );
}

// ── Step result card ──────────────────────────────────────────────────────────
function StepCard({ step, onConfirm, onDeny, taskId, planSteps }) {
  const planStep = planSteps?.find(s => s.step_id === step.step_id);
  const needsConfirm = step.error?.includes("confirmation");

  return (
    <div style={{
      background: C.surface, border: `1px solid ${C.border}`,
      borderRadius: 8, padding: 12, marginBottom: 8,
      borderLeft: `3px solid ${step.success ? C.green : needsConfirm ? C.amber : C.red}`,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 6 }}>
        <Badge color={step.success ? C.green : needsConfirm ? C.amber : C.red}>
          {step.success ? "✓ OK" : needsConfirm ? "⏳ Confirm" : "✗ Failed"}
        </Badge>
        {planStep && (
          <span style={{ color: C.muted, fontSize: 12 }}>
            {planStep.tool}.{planStep.action}
          </span>
        )}
        <span style={{ color: C.muted, fontSize: 11, marginLeft: "auto" }}>
          {step.step_id}
        </span>
      </div>

      {step.error && !needsConfirm && (
        <div style={{ color: C.red, fontSize: 12, marginTop: 4 }}>{step.error}</div>
      )}

      {step.success && step.output && (
        <pre style={{
          color: C.text, fontSize: 11, background: C.bg,
          borderRadius: 6, padding: 8, margin: "6px 0 0",
          overflowX: "auto", maxHeight: 120, whiteSpace: "pre-wrap",
        }}>{JSON.stringify(step.output, null, 2).slice(0, 500)}</pre>
      )}

      {needsConfirm && (
        <div style={{ display: "flex", gap: 8, marginTop: 8 }}>
          <Btn color={C.green} onClick={() => onConfirm(step.step_id)}>✓ Approve</Btn>
          <Btn color={C.red}   onClick={() => onDeny(step.step_id)}>✗ Deny</Btn>
        </div>
      )}
    </div>
  );
}

// ── Main App ──────────────────────────────────────────────────────────────────
export default function App() {
  const [tab, setTab] = useState("voice"); // voice | text | history
  const [recording, setRecording]     = useState(false);
  const [textInput, setTextInput]     = useState("");
  const [loading, setLoading]         = useState(false);
  const [taskId, setTaskId]           = useState(null);
  const [plan, setPlan]               = useState(null);
  const [result, setResult]           = useState(null);
  const [transcript, setTranscript]   = useState("");
  const [audioUrl, setAudioUrl]       = useState(null);
  const [history, setHistory]         = useState([]);
  const [error, setError]             = useState(null);

  const mediaRef   = useRef(null);
  const chunksRef  = useRef([]);
  const audioRef   = useRef(null);

  // ── Recording ───────────────────────────────────────────────────────────────
  async function startRecording() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream);
      chunksRef.current = [];
      mr.ondataavailable = e => chunksRef.current.push(e.data);
      mr.onstop = () => handleAudioReady(new Blob(chunksRef.current, { type: "audio/webm" }));
      mr.start();
      mediaRef.current = mr;
      setRecording(true);
    } catch {
      setError("Microphone access denied. Use text input instead.");
    }
  }

  function stopRecording() {
    mediaRef.current?.stop();
    setRecording(false);
  }

  async function handleAudioReady(blob) {
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append("audio", blob, "recording.webm");
      const res = await fetch(`${API}/voice-input`, { method: "POST", body: fd });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setTranscript(data.transcript);
      await processTask(data.task_id);
    } catch (e) {
      setError(`Voice processing failed: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  // ── Text input ──────────────────────────────────────────────────────────────
  async function handleTextSubmit() {
    if (!textInput.trim()) return;
    setLoading(true); setError(null); setResult(null); setPlan(null);
    try {
      const fd = new FormData();
      fd.append("text", textInput);
      const res = await fetch(`${API}/text-input`, { method: "POST", body: fd });
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      setPlan(data.plan);
      setTaskId(data.task_id);
      await executeTask(data.task_id, data.plan);
    } catch (e) {
      setError(`Error: ${e.message}`);
    } finally {
      setLoading(false);
    }
  }

  // ── Process task (after voice) ──────────────────────────────────────────────
  async function processTask(tid) {
    const fd = new FormData();
    fd.append("task_id", tid);
    fd.append("text_input", "");
    const res = await fetch(`${API}/process-task`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    setPlan(data.plan);
    setTaskId(tid);
    await executeTask(tid, data.plan);
  }

  // ── Execute & get response ──────────────────────────────────────────────────
  async function executeTask(tid, currentPlan) {
    const fd = new FormData();
    fd.append("task_id", tid);
    const res = await fetch(`${API}/get-response`, { method: "POST", body: fd });
    if (!res.ok) throw new Error(await res.text());
    const data = await res.json();
    setResult(data);
    if (data.audio_url) setAudioUrl(`http://localhost:8000${data.audio_url}`);

    // Add to history
    setHistory(h => [{
      id: tid,
      request: currentPlan?.original_request || textInput,
      response: data.text_response,
      status: data.status,
      steps: data.step_results?.length || 0,
      time: new Date().toLocaleTimeString(),
    }, ...h.slice(0, 9)]);
  }

  // ── Confirmation ────────────────────────────────────────────────────────────
  async function handleConfirm(stepId) {
    await fetch(`${API}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: taskId, step_id: stepId, confirmed: true }),
    });
    await executeTask(taskId, plan);
  }

  async function handleDeny(stepId) {
    await fetch(`${API}/confirm`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: taskId, step_id: stepId, confirmed: false }),
    });
    await executeTask(taskId, plan);
  }

  // ── Reset ────────────────────────────────────────────────────────────────────
  function reset() {
    setTaskId(null); setPlan(null); setResult(null);
    setTranscript(""); setAudioUrl(null); setError(null); setTextInput("");
  }

  // ── Render ───────────────────────────────────────────────────────────────────
  return (
    <div style={{
      minHeight: "100vh", background: C.bg, color: C.text,
      fontFamily: "'IBM Plex Mono', 'Fira Code', monospace",
    }}>
      <style>{`
        @keyframes pulse { 0%,100%{box-shadow:0 0 0 8px #ef444433,0 0 0 16px #ef444411} 50%{box-shadow:0 0 0 14px #ef444433,0 0 0 24px #ef444411} }
        * { box-sizing: border-box; }
        ::-webkit-scrollbar { width: 6px; } ::-webkit-scrollbar-track { background: #0a0d14; }
        ::-webkit-scrollbar-thumb { background: #1e2535; border-radius: 3px; }
        textarea, input { font-family: inherit; }
      `}</style>

      {/* Header */}
      <div style={{
        borderBottom: `1px solid ${C.border}`, padding: "16px 32px",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        background: C.surface,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
          <div style={{
            width: 36, height: 36, borderRadius: 10,
            background: `linear-gradient(135deg, ${C.accent}, ${C.purple})`,
            display: "flex", alignItems: "center", justifyContent: "center",
          }}>
            <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#fff" strokeWidth="2">
              <path d="M12 2a3 3 0 0 1 3 3v7a3 3 0 0 1-6 0V5a3 3 0 0 1 3-3z"/>
              <path d="M19 10v2a7 7 0 0 1-14 0v-2M12 19v3"/>
            </svg>
          </div>
          <div>
            <div style={{ fontWeight: 700, fontSize: 14, color: C.text }}>VoiceAgent AI</div>
            <div style={{ fontSize: 11, color: C.muted }}>Enterprise Workflow Automation</div>
          </div>
        </div>

        <div style={{ display: "flex", gap: 4 }}>
          {["voice", "text", "history"].map(t => (
            <button key={t} onClick={() => setTab(t)} style={{
              background: tab === t ? C.accent + "22" : "transparent",
              color: tab === t ? C.accent : C.muted,
              border: `1px solid ${tab === t ? C.accent + "44" : "transparent"}`,
              borderRadius: 6, padding: "6px 14px", cursor: "pointer",
              fontSize: 12, fontWeight: 600, textTransform: "capitalize",
              fontFamily: "inherit",
            }}>{t}</button>
          ))}
        </div>
      </div>

      <div style={{ maxWidth: 900, margin: "0 auto", padding: "32px 24px" }}>

        {/* Error banner */}
        {error && (
          <div style={{
            background: C.red + "22", border: `1px solid ${C.red}44`,
            borderRadius: 8, padding: "10px 14px", marginBottom: 20,
            color: C.red, fontSize: 13, display: "flex", justifyContent: "space-between",
          }}>
            <span>{error}</span>
            <span style={{ cursor: "pointer" }} onClick={() => setError(null)}>✕</span>
          </div>
        )}

        {/* ── Voice tab ─────────────────────────────────────────────────── */}
        {tab === "voice" && (
          <div>
            <Card style={{ textAlign: "center", marginBottom: 24 }}>
              <div style={{ marginBottom: 16, color: C.muted, fontSize: 13 }}>
                {recording ? "Recording… click to stop" : "Click to start recording"}
              </div>
              <div style={{ display: "flex", justifyContent: "center", marginBottom: 16 }}>
                <MicButton recording={recording}
                  onClick={recording ? stopRecording : startRecording} />
              </div>
              {loading && !recording && (
                <div style={{ color: C.accent, fontSize: 13 }}>⟳ Processing…</div>
              )}
              {transcript && (
                <div style={{
                  marginTop: 16, background: C.bg, borderRadius: 8,
                  padding: "10px 14px", textAlign: "left",
                }}>
                  <div style={{ color: C.muted, fontSize: 11, marginBottom: 4 }}>TRANSCRIPT</div>
                  <div style={{ fontSize: 13, color: C.text }}>{transcript}</div>
                </div>
              )}
            </Card>
            {renderResult()}
          </div>
        )}

        {/* ── Text tab ──────────────────────────────────────────────────── */}
        {tab === "text" && (
          <div>
            <Card style={{ marginBottom: 24 }}>
              <div style={{ color: C.muted, fontSize: 11, marginBottom: 8 }}>YOUR REQUEST</div>
              <textarea
                value={textInput}
                onChange={e => setTextInput(e.target.value)}
                onKeyDown={e => { if (e.key === "Enter" && e.ctrlKey) handleTextSubmit(); }}
                placeholder="e.g. Schedule a meeting with the team tomorrow at 2 PM and send a confirmation email"
                style={{
                  width: "100%", minHeight: 100, background: C.bg,
                  border: `1px solid ${C.border}`, borderRadius: 8,
                  color: C.text, padding: 12, fontSize: 13, resize: "vertical",
                  outline: "none",
                }}
              />
              <div style={{ display: "flex", gap: 10, marginTop: 12 }}>
                <Btn onClick={handleTextSubmit} disabled={loading || !textInput.trim()}>
                  {loading ? "⟳ Processing…" : "▶ Run Agent"}
                </Btn>
                <Btn color={C.muted} onClick={reset}>↺ Reset</Btn>
              </div>
              <div style={{ color: C.muted, fontSize: 11, marginTop: 8 }}>
                Ctrl+Enter to submit • Try: "Read my emails" / "Check calendar" / "Summarize report"
              </div>
            </Card>
            {renderResult()}
          </div>
        )}

        {/* ── History tab ───────────────────────────────────────────────── */}
        {tab === "history" && (
          <div>
            <div style={{ color: C.muted, fontSize: 12, marginBottom: 16 }}>
              Last {history.length} interactions this session
            </div>
            {history.length === 0 && (
              <Card style={{ textAlign: "center", color: C.muted, fontSize: 13, padding: 40 }}>
                No history yet. Run a voice or text task to see results here.
              </Card>
            )}
            {history.map(h => (
              <Card key={h.id} style={{ marginBottom: 12 }}>
                <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 8 }}>
                  <StatusBadge status={h.status} />
                  <span style={{ color: C.muted, fontSize: 11 }}>{h.time} · {h.steps} steps</span>
                </div>
                <div style={{ fontSize: 13, color: C.muted, marginBottom: 4 }}>
                  <span style={{ color: C.accent }}>Q:</span> {h.request}
                </div>
                <div style={{ fontSize: 13, color: C.text }}>
                  <span style={{ color: C.green }}>A:</span> {h.response}
                </div>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );

  function renderResult() {
    if (!plan && !result) return null;
    return (
      <div>
        {/* Plan */}
        {plan && (
          <Card style={{ marginBottom: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
              <div style={{ fontWeight: 700, fontSize: 13 }}>Task Plan</div>
              <Badge color={C.purple}>{plan.steps.length} steps</Badge>
            </div>
            {plan.steps.map((s, i) => (
              <div key={s.step_id} style={{
                display: "flex", alignItems: "center", gap: 10,
                padding: "6px 0",
                borderBottom: i < plan.steps.length - 1 ? `1px solid ${C.border}` : "none",
              }}>
                <div style={{
                  width: 22, height: 22, borderRadius: "50%",
                  background: C.accent + "22", color: C.accent,
                  display: "flex", alignItems: "center", justifyContent: "center",
                  fontSize: 11, fontWeight: 700, flexShrink: 0,
                }}>{i + 1}</div>
                <span style={{ color: C.accent, fontSize: 12 }}>{s.tool}</span>
                <span style={{ color: C.muted, fontSize: 12 }}>›</span>
                <span style={{ fontSize: 12 }}>{s.action}</span>
                {s.requires_confirmation && (
                  <Badge color={C.amber}>needs approval</Badge>
                )}
              </div>
            ))}
          </Card>
        )}

        {/* Result */}
        {result && (
          <Card style={{ marginBottom: 16 }}>
            <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 12 }}>
              <div style={{ fontWeight: 700, fontSize: 13 }}>Agent Response</div>
              <StatusBadge status={result.status} />
            </div>

            <div style={{
              background: C.bg, borderRadius: 8, padding: 14,
              fontSize: 13, lineHeight: 1.6, marginBottom: 12, color: C.text,
            }}>
              {result.text_response}
            </div>

            {audioUrl && (
              <div style={{ marginBottom: 12 }}>
                <div style={{ color: C.muted, fontSize: 11, marginBottom: 6 }}>VOICE RESPONSE</div>
                <audio ref={audioRef} src={audioUrl} controls
                  style={{ width: "100%", borderRadius: 6, accentColor: C.accent }} />
              </div>
            )}

            {result.step_results?.length > 0 && (
              <div>
                <div style={{ color: C.muted, fontSize: 11, marginBottom: 8 }}>STEP RESULTS</div>
                {result.step_results.map(sr => (
                  <StepCard key={sr.step_id} step={sr}
                    onConfirm={handleConfirm} onDeny={handleDeny}
                    taskId={taskId} planSteps={plan?.steps} />
                ))}
              </div>
            )}

            <div style={{ marginTop: 12 }}>
              <Btn color={C.muted} onClick={reset} style={{ fontSize: 12 }}>
                ↺ New Request
              </Btn>
            </div>
          </Card>
        )}
      </div>
    );
  }
}
