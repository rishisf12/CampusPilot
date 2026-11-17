import { useState } from "react"
import { useNavigate } from "react-router-dom"
import { accountsApi, PROVIDER_PRESETS, type MailAccountCreate } from "@/lib/accounts"

type Step = "preset" | "credentials" | "test" | "done"

export default function AddAccount() {
  const [step, setStep] = useState<Step>("preset")
  const [provider, setProvider] = useState("")
  const [host, setHost] = useState("")
  const [imapPort, setImapPort] = useState("993")
  const [smtpPort, setSmtpPort] = useState("465")
  const [imapSecurity, setImapSecurity] = useState("ssl")
  const [smtpSecurity, setSmtpSecurity] = useState("ssl")
  const [username, setUsername] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [testing, setTesting] = useState(false)
  const [result, setResult] = useState<TestResult | null>(null)
  const navigate = useNavigate()

  const preset = PROVIDER_PRESETS[provider]

  const handlePresetSelect = (p: string) => {
    setProvider(p)
    setError("")
    const pre = PROVIDER_PRESETS[p]
    setHost(pre.host || "")
    setImapPort(String(pre.imap_port ?? 993))
    setSmtpPort(String(pre.smtp_port ?? 465))
    setImapSecurity(pre.imap_security || "ssl")
    setSmtpSecurity(pre.smtp_security || "ssl")
    setStep("credentials")
  }

  const handleTest = async () => {
    setError("")
    setTesting(true)
    setResult(null)
    try {
      const res = await accountsApi.test({
        host,
        port: parseInt(imapPort, 10),
        username,
        password,
        security: imap_security,
      })
      setResult(res)
      if (res.ok) {
        setStep("test")
      } else {
        setError(res.message)
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : "Test failed")
    } finally {
      setTesting(false)
    }
  }

  const handleSave = async () => {
    setError("")
    const data: MailAccountCreate = {
      provider,
      host,
      imap_port: parseInt(imapPort, 10),
      smtp_port: parseInt(smtpPort, 10),
      imap_security: imap_security,
      smtp_security: smtp_security,
      username,
      password,
      is_enabled: true,
      sync_enabled: true,
    }
    try {
      await accountsApi.create(data)
      setStep("done")
    } catch (err) {
      setError(err instanceof Error ? err.message : "Save failed")
    }
  }

  if (step === "done") {
    return (
      <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
        <div className="max-w-md w-full text-center">
          <div className="bg-green-100 p-6 rounded-xl border border-green-200">
            <h2 className="text-2xl font-bold text-green-900 mb-2">Account connected</h2>
            <p className="text-green-700 mb-4">Your mail account has been added and sync is starting.</p>
            <button
              onClick={() => navigate("/health")}
              className="px-4 py-2 bg-slate-900 text-white rounded hover:bg-slate-800"
            >
            Go to inbox
            </button>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 px-4">
      <div className="max-w-md w-full space-y-6">
        <div>
          <h2 className="text-2xl font-bold text-slate-900">Add mail account</h2>
          <p className="mt-1 text-slate-600">Connect your IMAP/SMTP account</p>
        </div>

        {error && (
          <div className="rounded-md bg-red-50 p-3 text-sm text-red-700">{error}</div>
        )}

        {step === "preset" && (
          <div>
            <p className="text-sm text-slate-600 mb-3">Choose a provider</p>
            <div className="grid grid-cols-2 gap-2">
              {Object.entries(PROVIDER_PRESETS).map(([name, pre]) => (
                <button
                  key={name}
                  onClick={() => handlePresetSelect(name)}
                  className={`flex flex-col items-center p-3 rounded border ${
                    provider === name ? "bg-blue-50 border-blue-200 text-blue-900" : "bg-white border-slate-200 text-slate-700 hover:border-slate-300"
                  }`}
                >
                  <span className="font-medium">{name}</span>
                  {pre.host && <span className="text-xs text-slate-500 mt-1">{pre.host}</span>}
                </button>
              ))}
              <button
                onClick={() => {
                  setProvider("custom")
                  setHost("")
                  setImapPort("993")
                  setSmtpPort("465")
                  setImapSecurity("ssl")
                  setSmtpSecurity("ssl")
                  setError("")
                  setStep("credentials")
                }}
                className="flex flex-col items-center p-3 rounded border border-dashed border-slate-300 bg-white text-slate-500 hover:border-slate-400"
              >
                <span className="font-medium">Custom</span>
              </button>
            </div>
          </div>
        )}

        {step === "credentials" && (
          <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); handleTest() }}>
            <div>
              <label className="block text-sm font-medium text-slate-700">Provider</label>
              <input
                disabled
                className="mt-1 block w-full rounded-md border border-slate-300 bg-slate-100 p-2 text-slate-900"
                value={provider || "custom"}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">IMAP host</label>
              <input
                type="text"
                required
                className="mt-1 block w-full rounded-md border border-slate-300 bg-white p-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                value={host}
                onChange={(e) => setHost(e.target.value)}
              />
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700">IMAP port</label>
                <input
                  type="number"
                  required
                  className="mt-1 block w-full rounded-md border border-slate-300 bg-white p-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  value={imapPort}
                  onChange={(e) => setImapPort(e.target.value)}
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700">SMTP port</label>
                <input
                  type="number"
                  required
                  className="mt-1 block w-full rounded-md border border-slate-300 bg-white p-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  value={smtpPort}
                  onChange={(e) => setSmtpPort(e.target.value)}
                />
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-sm font-medium text-slate-700">IMAP security</label>
                <select
                  className="mt-1 block w-full rounded-md border border-slate-300 bg-white p-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  value={imap_security}
                  onChange={(e) => setImapSecurity(e.target.value)}
                >
                  <option value="ssl">SSL/TLS</option>
                  <option value="starttls">STARTTLS</option>
                  <option value="none">None</option>
                </select>
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-700">SMTP security</label>
                <select
                  className="mt-1 block w-full rounded-md border border-slate-300 bg-white p-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                  value={smtp_security}
                  onChange={(e) => setSmtpSecurity(e.target.value)}
                >
                  <option value="ssl">SSL/TLS</option>
                  <option value="starttls">STARTTLS</option>
                  <option value="none">None</option>
                </select>
              </div>
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Username (email)</label>
              <input
                type="email"
                required
                className="mt-1 block w-full rounded-md border border-slate-300 bg-white p-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-slate-700">Password</label>
              <input
                type="password"
                required
                className="mt-1 block w-full rounded-md border border-slate-300 bg-white p-2 text-slate-900 focus:ring-2 focus:ring-blue-500 focus:border-blue-500 outline-none"
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            <div className="flex gap-2">
              <button
                type="button"
                onClick={() => setStep("preset")}
                className="flex-1 py-2 px-4 border border-slate-300 rounded-md text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                Back
              </button>
              <button
                type="submit"
                disabled={testing}
                className="flex-1 py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-slate-900 hover:bg-slate-800 disabled:opacity-50"
              >
                {testing ? "Testing…" : "Test connection"}
              </button>
            </div>
          </form>
        )}

        {step === "test" && (
          <div className="space-y-4">
            <div className="p-3 rounded bg-green-50 border border-green-200">
              <h3 className="text-sm font-bold text-green-900">Connection test passed</h3>
              <p className="text-xs text-green-700 mt-1">{result?.message}</p>
              {result?.imap_capabilities && (
                <p className="text-xs text-green-700 mt-1">Capabilities: {result.imap_capabilities.join(", ")}</p>
              )}
            </div>
            <div className="flex gap-2">
              <button
                onClick={() => setStep("credentials")}
                className="flex-1 py-2 px-4 border border-slate-300 rounded-md text-sm font-medium text-slate-700 hover:bg-slate-100"
              >
                Edit details
              </button>
              <button
                onClick={handleSave}
                className="flex-1 py-2 px-4 border border-transparent rounded-md shadow-sm text-sm font-medium text-white bg-slate-900 hover:bg-slate-800"
              >
                Save account
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

interface TestResult {
  ok: boolean
  imap_capabilities?: string[]
  message: string
}
