import { useMemo, useRef, useState, useEffect, useCallback } from 'react'

import {
  ArrowRight, BadgeCheck, Bell, ChevronRight, CircleDollarSign, FileCheck2,
  Fingerprint, Landmark, LockKeyhole, Menu, MessageSquareText, Paperclip,
  Send, ShieldCheck, Sparkles, TrendingUp, UploadCloud, UserRound, WalletCards,
  Zap,
} from 'lucide-react'
import './App.css'

// Pointing to your Flask Backend port (commonly 5000)
const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:5000'

// --- CUSTOM STREAMING HOOK ---
// Models a smooth, length-aware word-by-word reveal effect.
// Instead of a fixed 60ms/word (which made long answers crawl for 20-30s),
// the per-word delay scales down for longer messages so every answer
// finishes revealing in roughly the same, pleasant amount of time.
function useStreamingText(rawText, speedMs) {
  const [displayedText, setDisplayedText] = useState('')

  useEffect(() => {
    if (!rawText) {
      setDisplayedText('')
      return
    }

    const words = rawText.split(' ')
    let currentWordIndex = 0
    setDisplayedText('')

    const perWord = speedMs ?? Math.max(9, Math.min(45, 1800 / words.length))

    const interval = setInterval(() => {
      if (currentWordIndex < words.length) {
        setDisplayedText((prev) => (prev ? prev + ' ' : '') + words[currentWordIndex])
        currentWordIndex++
      } else {
        clearInterval(interval)
      }
    }, perWord)

    return () => clearInterval(interval)
  }, [rawText, speedMs])

  return displayedText
}

// --- INLINE HIGHLIGHTING ---
// Wraps currency (INR ...), percentages, and "Tier N" mentions in
// colour-coded spans so figures pop out of dense analytical text.
function highlightNumbers(text, keyPrefix) {
  if (!text) return null
  const regex = /(INR\s?[\d,]+(?:\.\d+)?|\d+(?:\.\d+)?%|Tier\s?\d+)/gi
  const out = []
  let lastIndex = 0
  let match
  let i = 0

  while ((match = regex.exec(text)) !== null) {
    if (match.index > lastIndex) out.push(text.slice(lastIndex, match.index))
    const val = match[0]
    let cls = 'hl-number'
    if (/^INR/i.test(val)) cls = 'hl-money'
    else if (val.endsWith('%')) cls = 'hl-percent'
    else if (/^Tier/i.test(val)) cls = 'hl-tier'
    out.push(<span className={cls} key={`${keyPrefix}-n${i++}`}>{val}</span>)
    lastIndex = regex.lastIndex
  }
  if (lastIndex < text.length) out.push(text.slice(lastIndex))
  return out
}

function renderInlineText(text, keyPrefix = 'inline') {
  const parts = String(text).split(/(\*\*[^*]+\*\*|__[^_]+__)/g).filter(Boolean)

  return parts.map((part, index) => {
    const boldMatch = part.match(/^\*\*(.+)\*\*$/) || part.match(/^__(.+)__$/)
    if (boldMatch) {
      return (
        <strong className="hl-key" key={`${keyPrefix}-b-${index}`}>
          {highlightNumbers(boldMatch[1], `${keyPrefix}-b-${index}`)}
        </strong>
      )
    }
    return <span key={`${keyPrefix}-p-${index}`}>{highlightNumbers(part, `${keyPrefix}-p-${index}`)}</span>
  })
}

// --- STRUCTURED MESSAGE RENDERER ---
// Parses the analyst-style responses (numbered steps with indented
// sub-bullets, standalone bold section labels, plain bullets/paragraphs)
// into distinct visual blocks instead of one flat bulleted list.
function MessageContent({ text }) {
  const blocks = []
  const rawLines = String(text || '').split('\n')
  let paragraphLines = []
  let listItems = []
  let currentStep = null

  const flushParagraph = () => {
    if (!paragraphLines.length) return
    blocks.push(
      <div className="analysis-paragraph" key={`p-${blocks.length}`}>
        {renderInlineText(paragraphLines.join(' '), `p-${blocks.length}`)}
      </div>
    )
    paragraphLines = []
  }

  const flushList = () => {
    if (!listItems.length) return
    blocks.push(
      <ul key={`ul-${blocks.length}`}>
        {listItems.map((item, index) => (
          <li key={`li-${index}`}>{renderInlineText(item, `li-${blocks.length}-${index}`)}</li>
        ))}
      </ul>
    )
    listItems = []
  }

  const flushStep = () => {
    if (!currentStep) return
    const step = currentStep
    blocks.push(
      <div className="step-block" key={`step-${step.number}-${blocks.length}`}>
        <div className="step-num">{step.number}</div>
        <div className="step-body">
          <div className="step-title">{renderInlineText(step.title, `st-${step.number}`)}</div>
          {step.subItems.length > 0 && (
            <ul className="step-sublist">
              {step.subItems.map((sub, si) => {
                const colonIdx = sub.indexOf(':')
                const label = colonIdx > 0 ? sub.slice(0, colonIdx) : null
                const isCleanLabel = label && colonIdx < 60 && !label.includes('**')
                if (isCleanLabel) {
                  const value = sub.slice(colonIdx + 1).trim()
                  return (
                    <li key={`sub-${si}`} className="kv-row">
                      <span className="kv-label">{renderInlineText(label, `subl-${step.number}-${si}`)}</span>
                      <span className="kv-value">{renderInlineText(value, `subv-${step.number}-${si}`)}</span>
                    </li>
                  )
                }
                return <li key={`sub-${si}`}>{renderInlineText(sub, `sub-${step.number}-${si}`)}</li>
              })}
            </ul>
          )}
        </div>
      </div>
    )
    currentStep = null
  }

  rawLines.forEach((line) => {
    const indent = line.length - line.trimStart().length
    const trimmed = line.trim()

    if (!trimmed) {
      flushParagraph()
      flushList()
      return
    }

    const headingMatch = trimmed.match(/^(#{1,3})\s+(.*)$/)
    if (headingMatch) {
      flushParagraph(); flushList(); flushStep()
      const level = Math.min(headingMatch[1].length, 3)
      const HeadingTag = `h${level}`
      blocks.push(
        <HeadingTag key={`h-${blocks.length}`}>
          {renderInlineText(headingMatch[2], `h-${blocks.length}`)}
        </HeadingTag>
      )
      return
    }

    // A line that is *only* a bold label (e.g. "**Definitive Compliance Ruling Code:**")
    // reads as a section header, not body text.
    const boldLineMatch = trimmed.match(/^\*\*([^*]+?)\*\*:?$/)
    if (boldLineMatch) {
      flushParagraph(); flushList(); flushStep()
      const label = boldLineMatch[1].replace(/:$/, '')
      blocks.push(
        <div className="section-label" key={`sl-${blocks.length}`}>
          {renderInlineText(`${label}:`, `sl-${blocks.length}`)}
        </div>
      )
      return
    }

    const numberedMatch = trimmed.match(/^(\d+)\.\s+(.*)$/)
    if (numberedMatch && indent < 4) {
      flushParagraph(); flushList(); flushStep()
      currentStep = { number: numberedMatch[1], title: numberedMatch[2], subItems: [] }
      return
    }

    const bulletMatch = trimmed.match(/^[-*]\s+(.*)$/)
    if (bulletMatch) {
      flushParagraph()
      if (currentStep && indent >= 4) {
        currentStep.subItems.push(bulletMatch[1])
      } else {
        flushStep()
        listItems.push(bulletMatch[1])
      }
      return
    }

    // Plain text line: nests under the active step if indented, else a normal paragraph.
    if (currentStep && indent >= 4) {
      currentStep.subItems.push(trimmed)
    } else {
      flushStep()
      paragraphLines.push(trimmed)
    }
  })

  flushParagraph()
  flushList()
  flushStep()

  return <div className="message-content">{blocks}</div>
}

// Sub-component to isolate the streaming effect per message block
function ChatMessage({ message, isLatestAi, onStreaming }) {
  const streamedText = useStreamingText(message.ai && isLatestAi ? message.text : null)

  useEffect(() => {
    if (isLatestAi) {
      onStreaming?.()
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [streamedText, isLatestAi])

  const content = (message.ai && isLatestAi) ? streamedText : message.text

  return (
    <div className="message-row">
      <div className={`message ${message.ai ? 'ai' : 'user'}`}>
        {message.ai && <div className="ai-mark"><Sparkles /></div>}
        <div className="message-body">
          <MessageContent text={content} />
        </div>
      </div>
    </div>
  )
}

function Brand({ compact = false }) {
  return <div className="brand"><div className="brand-mark"><span>T</span></div>{!compact && <div><b>TEJAS</b><small>FINANCE</small></div>}</div>
}

function Login({ onDemo, onContinue }) {
  const [mode, setMode] = useState('login')
  return <main className="auth-shell">
    <section className="auth-visual">
      <div className="top-brand"><Brand /></div>
      <div className="orbital orbital-a"/><div className="orbital orbital-b"/>
      <div className="auth-copy"><div className="eyebrow"><span/> PRIVATE WEALTH INTELLIGENCE</div><h1>Capital, engineered<br/><em>around you.</em></h1><p>A new standard in intelligent banking—where institutional-grade insight meets deeply personal service.</p><div className="trust-row"><span><ShieldCheck/>256-bit secure</span><span><Zap/>AI-native</span><span><Landmark/>RBI compliant</span></div></div>
      <div className="visual-foot">TEJAS FINANCIAL TECHNOLOGIES · 2026</div>
    </section>
    <section className="auth-form-wrap">
      <div className="mobile-brand"><Brand/></div>
      <div className="auth-form">
        <div className="auth-kicker">SECURE CLIENT ACCESS</div>
        <h2>{mode === 'login' ? 'Welcome back.' : 'Begin your journey.'}</h2>
        <p>{mode === 'login' ? 'Enter your credentials to access your private banking workspace.' : 'Create a secure account for your Tejas experience.'}</p>
        <div className="mode-tabs"><button className={mode==='login'?'active':''} onClick={()=>setMode('login')}>Sign in</button><button className={mode==='signup'?'active':''} onClick={()=>setMode('signup')}>Create account</button></div>
        {mode==='signup' && <label>Full legal name<div className="field"><UserRound/><input placeholder="As per government ID"/></div></label>}
        <label>Email address<div className="field"><MessageSquareText/><input type="email" placeholder="name@company.com"/></div></label>
        <label>Password <a>Forgot password?</a><div className="field"><LockKeyhole/><input type="password" placeholder="Enter your password"/></div></label>
        <button className="primary-btn" onClick={onContinue}>{mode==='login'?'Access workspace':'Create secure account'} <ArrowRight/></button>
        <div className="or"><span/>OR EXPLORE INSTANTLY<span/></div>
        <button className="demo-btn" onClick={onDemo}><Sparkles/><span><b>Enter demo workspace</b><small>Pre-filled with a secure sample profile</small></span><ChevronRight/></button>
        <div className="privacy"><ShieldCheck/> Your information is encrypted and never shared.</div>
      </div>
    </section>
  </main>
}

function VectorCanvas() {
  return <div className="vector-canvas">
    <svg viewBox="0 0 700 760" aria-hidden="true">
      <defs><radialGradient id="glow"><stop stopColor="#d9795f" stopOpacity=".35"/><stop offset="1" stopColor="#241d1a" stopOpacity="0"/></radialGradient><marker id="arrow" markerWidth="8" markerHeight="8" refX="4" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="#e39177"/></marker></defs>
      <circle cx="350" cy="380" r="300" fill="url(#glow)"/><g className="grid-lines">{[170,230,290,350,410,470,530].map(x=><line key={x} x1={x} y1="90" x2={x} y2="670"/>)}{[200,260,320,380,440,500,560].map(y=><line key={y} x1="70" y1={y} x2="630" y2={y}/>)}</g>
      <g className="rings"><ellipse cx="350" cy="380" rx="232" ry="88"/><ellipse cx="350" cy="380" rx="88" ry="232" transform="rotate(38 350 380)"/><ellipse cx="350" cy="380" rx="88" ry="232" transform="rotate(-38 350 380)"/></g>
      <g className="axes"><line x1="115" y1="525" x2="585" y2="235" markerEnd="url(#arrow)"/><line x1="165" y1="255" x2="540" y2="545" markerEnd="url(#arrow)"/><line x1="350" y1="620" x2="350" y2="135" markerEnd="url(#arrow)"/></g><circle className="core" cx="350" cy="380" r="13"/><circle className="pulse" cx="350" cy="380" r="26"/>
    </svg>
    <div className="vector-caption"><span>IDENTITY VECTOR</span><b>Establishing your<br/>financial coordinates.</b><p>Every verified detail sharpens the intelligence behind your Tejas profile.</p></div>
  </div>
}

function Onboarding({ onComplete }) {
  const [file, setFile] = useState(null), [loading,setLoading]=useState(false), [data,setData]=useState(null)
  const input = useRef()
  async function upload(selected){ if(!selected)return; setFile(selected); setLoading(true); const form=new FormData(); form.append('file',selected); try { const res=await fetch(`${API_BASE}/api/onboarding/upload`,{method:'POST',body:form}); if(!res.ok) throw Error(); setData(await res.json()) } catch { setTimeout(()=>setData({full_name:'Arjun Mehta',document_type:selected.name.toLowerCase().includes('pan')?'PAN':'Aadhaar',masked_identifier:'•••• •••• 4821',date_of_birth:'14 Aug 1994',confidence:98.6}),450) } finally {setTimeout(()=>setLoading(false),450)} }
  return <main className="onboarding">
    <header><Brand/><div className="secure-label"><ShieldCheck/> SECURE ONBOARDING</div><div className="step-label">STEP 01 OF 02</div></header>
    <div className="onboard-grid"><section className="identity-panel"><VectorCanvas/></section><section className="upload-panel"><div className="upload-content"><div className="eyebrow blue"><span/> IDENTITY VERIFICATION</div><h2>Let’s verify<br/>who you are.</h2><p className="lead">Upload one government-issued identity document. We extract only what is needed and redact sensitive identifiers automatically.</p>
      {!data ? <><div className={`dropzone ${loading?'loading':''}`} onClick={()=>input.current.click()} onDragOver={e=>e.preventDefault()} onDrop={e=>{e.preventDefault();upload(e.dataTransfer.files[0])}}><input ref={input} type="file" accept=".pdf,.jpg,.jpeg,.png" hidden onChange={e=>upload(e.target.files[0])}/>{loading?<><div className="scanner"/><Fingerprint className="drop-icon"/><h3>Reading secure document…</h3><p>{file?.name}</p></>:<><UploadCloud className="drop-icon"/><h3>Drop your document here</h3><p>or <u>browse from your device</u></p><small>PDF, JPG or PNG · Maximum 10 MB</small></>}</div><div className="doc-options"><span><FileCheck2/> PAN card</span><span><Fingerprint/> Aadhaar card</span></div></> : <div className="extracted-card"><div className="extract-head"><span><BadgeCheck/> Document verified</span><b>{data.confidence}% confidence</b></div><label>Full legal name<input value={data.full_name} onChange={e=>setData({...data,full_name:e.target.value})}/></label><div className="two-fields"><label>Document type<input value={data.document_type} readOnly/></label><label>Identifier<input value={data.masked_identifier} readOnly/></label></div><label>Date of birth<input value={data.date_of_birth} onChange={e=>setData({...data,date_of_birth:e.target.value})}/></label><p className="redaction"><ShieldCheck/> Sensitive digits are redacted before they leave the verification layer.</p></div>}
      <button className="primary-btn" disabled={!data} onClick={onComplete}>Confirm & enter Tejas <ArrowRight/></button><p className="microcopy">By continuing, you consent to secure identity verification for this demo.</p></div></section></div>
  </main>
}

const money = value => new Intl.NumberFormat('en-IN').format(value)

function CommandCenter({ user, onLogout }) {
  const profile = user.financial_profile
  const firstName = user.name.split(' ')[0]
  const initials = user.name.split(' ').map(part=>part[0]).join('').slice(0,2)
  const messagesRef = useRef(null)
  const isAtBottomRef = useRef(true)
  const rafRef = useRef(null)
  const [amount, setAmount] = useState(1200000)
  const [income, setIncome] = useState(profile.estimated_monthly_net_income)
  const [scenario, setScenario] = useState(null)
  const [text, setText] = useState('')
  const [sending, setSending] = useState(false)

  const [messages, setMessages] = useState([
    { ai: true, text: `Good morning, ${firstName}. I’ve reviewed your ₹${money(profile.current_savings_balance)} liquidity position, ${profile.current_cibil_score} CIBIL score, and credit history.` },
    { ai: true, text: 'To model this accurately, I need two details: your Target Loan Amount and Capital Allocation Purpose.' }
  ])

  const localScore = useMemo(()=>Math.max(20,Math.min(96,Math.round(100-(amount/(income*12))*35))),[amount,income])
  const score = scenario?.score ?? localScore

  // Smoothly scroll to the latest message, but only when the reader is
  // already near the bottom (or the new message is their own). This stops
  // the chat from yanking someone back down while they're scrolled up
  // reading earlier answers.
  const scrollToBottom = useCallback((smooth = true) => {
    const el = messagesRef.current
    if (!el) return
    el.scrollTo({ top: el.scrollHeight, behavior: smooth ? 'smooth' : 'auto' })
  }, [])

  const handleMessagesScroll = useCallback((e) => {
    const el = e.currentTarget
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight
    isAtBottomRef.current = distanceFromBottom < 96
  }, [])

  useEffect(() => {
    const last = messages[messages.length - 1]
    if (isAtBottomRef.current || (last && !last.ai)) {
      scrollToBottom(true)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.length])

  // Called on every word reveal while the latest AI message streams in.
  // Throttled to one scroll per animation frame so it stays smooth even
  // on long answers instead of fighting the layout every 10-15ms.
  const handleStreaming = useCallback(() => {
    if (!isAtBottomRef.current) return
    if (rafRef.current) cancelAnimationFrame(rafRef.current)
    rafRef.current = requestAnimationFrame(() => {
      if (messagesRef.current) {
        messagesRef.current.scrollTop = messagesRef.current.scrollHeight
      }
    })
  }, [])

  useEffect(() => () => { if (rafRef.current) cancelAnimationFrame(rafRef.current) }, [])

  async function refreshScenario(nextAmount=amount, nextIncome=income) {
    try {
      const res = await fetch(`${API_BASE}/api/scenario`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uid: user.uid, loan_amount: nextAmount, monthly_income: nextIncome })
      })
      if(res.ok) setScenario(await res.json())
    } catch {
      setScenario(null)
    }
  }

  // --- CONNECTED TO FLASK BACKEND CORRESPONDING TO `handle_user_request` ---
  async function send() {
    if (!text.trim() || sending) return
    const prompt = text

    // Add user's query block to history
    setMessages(m => [...m, { text: prompt }])
    setText('')
    setSending(true)

    try {
      const res = await fetch(`${API_BASE}/api/request`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ uid: user.uid, prompt: prompt })
      })

      const data = await res.json()

      if (!res.ok) {
        // Triggers backend fallback configuration handling status code failure
        setMessages(m => [...m, { ai: true, text: data.error || 'Server error or servers are down' }])
      } else {
        // Appends new AI message which automatically captures streaming view state
        setMessages(m => [...m, { ai: true, text: data.message }])
      }
    } catch {
      setMessages(m => [...m, { ai: true, text: 'Server error or servers are down' }])
    } finally {
      setSending(false)
    }
  }

  return <main className="dashboard"><aside className="sidebar"><Brand compact/><nav><button className="active"><Sparkles/></button><button><WalletCards/></button><button><TrendingUp/></button><button><UserRound/></button></nav><button onClick={onLogout}><Menu/></button></aside>
    <section className="workspace"><header className="dash-header"><div><span>TEJAS /</span> COMMAND CENTER</div><div className="header-actions"><span className="live"><i/> API CONNECTED</span><button><Bell/></button><div className="avatar">{initials}</div></div></header>
      <div className="command-grid"><section className="chat-column"><div className="chat-title"><div><div className="eyebrow blue"><span/> PRIVATE CREDIT INTELLIGENCE</div><h1>Good morning, <em>{firstName}.</em></h1><p>Let’s engineer your next move.</p></div><div className="session"><ShieldCheck/> {user.uid} · CIBIL {profile.current_cibil_score}</div></div>

        {/* Render chat message feed with selective streaming */}
        <div className="messages" ref={messagesRef} onScroll={handleMessagesScroll}>
          {messages.map((m, i) => (
            <ChatMessage
                key={i}
                message={m}
                isLatestAi={m.ai && i===messages.length-1}
                onStreaming={handleStreaming}
            />
          ))}
          {sending && (
            <div className="message-row">
              <div className="message ai typing">
                <div className="ai-mark"><Sparkles/></div>
                <div className="message-body"><span className="typing-dots"><i/><i/><i/></span></div>
              </div>
            </div>
          )}
        </div>

        <div className="quick-prompts"><button onClick={()=>setText('I’m considering a new car around ₹12 lakh.')}><CircleDollarSign/> Finance a vehicle</button><button onClick={()=>setText('What are the current personal loan policies?')}><FileCheck2/> Ask about policy</button></div>
        <div className="composer"><button><Paperclip/></button><textarea value={text} onChange={e=>setText(e.target.value)} onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();send()}}} placeholder="Ask Tejas about a loan, policy, or purchase…"/><button className="send" disabled={sending} onClick={send}><Send/></button></div><small className="composer-note">{sending?'Consulting policy intelligence…':'Tejas may make mistakes. Financial decisions remain yours.'}</small>
      </section><aside className="finance-column"><div className="panel-head"><span>FINANCIAL PULSE</span><button>LIVE</button></div>
        <div className="liquidity card"><div className="card-label"><WalletCards/> ACCOUNT LIQUIDITY</div><p>Available savings balance</p><h2>₹{money(profile.current_savings_balance)}<span>.00</span></h2><div className="portfolio"><span>Active monthly obligations</span><b>₹{money(user.purchasing_history.filter(x=>x.status==='active').reduce((sum,x)=>sum+x.monthly_emi,0))}</b></div></div>
        <div className="scenario card"><div className="card-label"><TrendingUp/> WHAT-IF SCENARIO</div><label>Target loan amount <b>₹{(amount/100000).toFixed(1)}L</b></label><input type="range" min="200000" max="5000000" step="50000" value={amount} onChange={e=>{const v=+e.target.value;setAmount(v);refreshScenario(v,income)}}/><div className="range-labels"><span>₹2L</span><span>₹50L</span></div><label>Monthly income <b>₹{(income/100000).toFixed(2)}L</b></label><input type="range" min="20000" max="500000" step="5000" value={income} onChange={e=>{const v=+e.target.value;setIncome(v);refreshScenario(amount,v)}}/><div className="eligibility"><div className="meter" style={{'--score':`${score*3.6}deg`}}><div><b>{score}</b><small>/ 100</small></div></div><div><span>ELIGIBILITY SIGNAL</span><b>{scenario?.signal ?? (score>=78?'Strong fit':score>=60?'Moderate fit':'Needs review')}</b><p>{scenario?`${scenario.foir_percent}% estimated FOIR`:'Move a slider to query Flask'}</p></div></div></div>
        <div className="stream card"><div className="stream-title"><div className="card-label"><Zap/> CREDIT HISTORY</div><span><i/> JSON SYNCED</span></div>{user.purchasing_history.map((t,i)=><div className="transaction" key={`${t.year}-${t.type}`}><div className={`tx-icon t${i}`}><ArrowRight/></div><div><b>{t.type.toUpperCase()}</b><span>{t.year} · {t.status}</span></div><div><b>₹{money(t.monthly_emi)}</b><span>{t.delinquent_count} late</span></div></div>)}</div>
      </aside></div></section></main>
}

// --- CONNECTED TO FLASK BACKEND PATH `/api/user/<uid>` ---
export default function App() {
  const [screen, setScreen] = useState('login')
  const [user, setUser] = useState(null)

  async function enter(uid = 'U009') {
    try {
      const res = await fetch(`${API_BASE}/api/user/${uid}`)
      if (!res.ok) throw Error()

      const data = await res.json()
      setUser(data.user) // Accesses mapped user data directly from flask json template
      setScreen('dashboard')
    } catch {
      globalThis.alert('Tejas Flask API is offline. Start the Python server on port 5000 and try again.')
    }
  }

  return screen === 'login' ? (
    <Login onDemo={() => enter('U009')} onContinue={() => setScreen('onboarding')} />
  ) : screen === 'onboarding' ? (
    <Onboarding onComplete={() => enter('U009')} />
  ) : user ? (
    <CommandCenter user={user} onLogout={() => setScreen('login')} />
  ) : null
}