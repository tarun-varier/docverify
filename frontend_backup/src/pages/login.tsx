import { useState, useCallback } from 'react'
import { Lock, User, KeyRound, ShieldAlert } from 'lucide-react'

export default function Login() {
  const [officerId, setOfficerId] = useState('')
  const [password, setPassword] = useState('')
  const [otp, setOtp] = useState('')
  const [error, setError] = useState('')
  const [isVerifying, setIsVerifying] = useState(false)
  const [verificationStep, setVerificationStep] = useState('')

  const handleLogin = useCallback((e: React.FormEvent) => {
    e.preventDefault()
    setError('')

    if (!officerId.trim()) {
      setError('Officer ID is required.')
      return
    }
    if (!password.trim()) {
      setError('Security Password is required.')
      return
    }
    if (!otp.trim() || otp.length !== 4) {
      setError('Please enter a valid 4-digit security PIN.')
      return
    }

    setIsVerifying(true)
    setVerificationStep('Establishing SSL Session...')
    
    setTimeout(() => {
      setVerificationStep('Authenticating with Canara SSO Registry...')
      setTimeout(() => {
        setVerificationStep('Syncing risk credentials...')
        setTimeout(() => {
          window.location.href = '/upload'
        }, 800)
      }, 800)
    }, 800)
  }, [officerId, password, otp])

  return (
    <div className="min-h-screen bg-slate-50 flex flex-col justify-between">
      {/* Top Banner strip */}
      <div className="bg-white border-b-2 border-yellow-500 py-3 px-6 shadow-sm">
        <div className="max-w-6xl mx-auto flex items-center justify-between">
          <div className="flex items-center gap-4">
            <div className="canara-logo flex-shrink-0" />
            <div className="border-l border-slate-300 pl-4">
              <h1 className="text-lg font-bold text-blue-700 flex items-center gap-2 mb-0.5">
                कैनरा बैंक <span className="text-slate-400">|</span> Canara Bank
              </h1>
              <p className="text-[10px] text-amber-900 font-semibold tracking-wider italic">
                Together we can
              </p>
            </div>
          </div>
          <span className="px-2.5 py-1 bg-blue-100 border border-blue-200 text-blue-700 text-[10px] font-bold uppercase rounded-md tracking-wider">
            Risk Gateway v2.4
          </span>
        </div>
      </div>

      <div className="login-container flex-1">
        <div className="login-card animate-fade-in">
          <div className="text-center mb-6">
            <div className="w-12 h-12 bg-blue-100 rounded-full flex items-center justify-center mx-auto mb-3">
              <Lock className="w-6 h-6 text-blue-600" />
            </div>
            <h2 className="text-xl font-bold text-slate-900">
              Risk Officer Single-Sign-On
            </h2>
            <p className="text-xs text-slate-500 mt-1">
              Enter your credentials to access the DocVerify AI audit portal.
            </p>
          </div>

          {error && (
            <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-xs font-semibold text-red-700 flex items-center gap-2 mb-4">
              <ShieldAlert className="w-4 h-4 flex-shrink-0" />
              <span>{error}</span>
            </div>
          )}

          {isVerifying ? (
            <div className="py-8 text-center space-y-4">
              <div className="w-10 h-10 border-4 border-blue-600 border-t-transparent animate-spin rounded-full mx-auto" />
              <div>
                <p className="text-sm font-bold text-blue-700">{verificationStep}</p>
                <p className="text-xs text-slate-400 mt-1">Securing connection to sandboxed workspace...</p>
              </div>
            </div>
          ) : (
            <form onSubmit={handleLogin} className="space-y-4">
              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase mb-1.5">
                  Officer ID (Username)
                </label>
                <div className="relative">
                  <span className="absolute left-3.5 top-3 text-slate-400">
                    <User className="w-4 h-4" />
                  </span>
                  <input
                    type="text"
                    value={officerId}
                    onChange={(e) => setOfficerId(e.target.value)}
                    placeholder="e.g. CNB-9024"
                    className="form-input pl-10"
                    autoComplete="username"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase mb-1.5">
                  Security Password
                </label>
                <div className="relative">
                  <span className="absolute left-3.5 top-3 text-slate-400">
                    <KeyRound className="w-4 h-4" />
                  </span>
                  <input
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder="••••••••"
                    className="form-input pl-10"
                    autoComplete="current-password"
                  />
                </div>
              </div>

              <div>
                <label className="block text-xs font-bold text-slate-500 uppercase mb-1.5">
                  Single Use Transaction PIN (OTP)
                </label>
                <input
                  type="text"
                  maxLength={4}
                  value={otp}
                  onChange={(e) => setOtp(e.target.value.replace(/\D/g, ''))}
                  placeholder="Enter 4-digit PIN"
                  className="form-input text-center font-mono text-lg tracking-widest"
                />
                <p className="text-[10px] text-slate-500 mt-1 text-center">
                  PIN is generated on your Canara Authenticator app.
                </p>
              </div>

              <button
                type="submit"
                className="login-button mt-2"
              >
                Verify & Secure Login
              </button>
            </form>
          )}
        </div>
      </div>

      {/* Footer warning strip */}
      <div className="bg-slate-900 border-t border-slate-200 py-4 px-6 text-center">
        <p className="text-[10px] text-slate-500 max-w-2xl mx-auto leading-relaxed">
          <strong>WARNING:</strong> This is a secure computer system owned by Canara Bank. Unauthorized access is strictly prohibited and subject to legal prosecution under the Information Technology Act, 2000 and other applicable laws.
        </p>
      </div>
    </div>
  )
}
