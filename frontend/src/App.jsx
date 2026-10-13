import { useState } from 'react'
import './App.css'

const API_URL = import.meta.env.VITE_API_URL

function App() {
  const [view, setView] = useState('login')
  const [accountName, setAccountName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [user, setUser] = useState(null)
  const [message, setMessage] = useState(null)
  const [error, setError] = useState(null)

  async function handleSignup(e) {
    e.preventDefault()
    setError(null)
    try {
      const res = await fetch(`${API_URL}/auth/signup`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ account_name: accountName, email, password }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Signup failed')
      setMessage('Account created. Please log in.')
      setView('login')
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleLogin(e) {
    e.preventDefault()
    setError(null)
    try {
      const res = await fetch(`${API_URL}/auth/login`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Login failed')

      const meRes = await fetch(`${API_URL}/auth/me`, {
        headers: { Authorization: `Bearer ${data.access_token}` },
      })
      const meData = await meRes.json()
      setUser(meData)
    } catch (err) {
      setError(err.message)
    }
  }

  function handleLogout() {
    setUser(null)
    setMessage(null)
  }

  if (user) {
    return (
      <div style={{ maxWidth: 420, margin: '4rem auto', fontFamily: 'sans-serif' }}>
        <h1>GhostLine Dashboard</h1>
        <p>Account ID: {user.account_id}</p>
        <p>Role: {user.role}</p>
        <button onClick={handleLogout}>Log out</button>
      </div>
    )
  }

  return (
    <div style={{ maxWidth: 420, margin: '4rem auto', fontFamily: 'sans-serif' }}>
      <h1>GhostLine</h1>
      <div style={{ marginBottom: '1rem' }}>
        <button onClick={() => setView('login')} disabled={view === 'login'}>Log in</button>{' '}
        <button onClick={() => setView('signup')} disabled={view === 'signup'}>Sign up</button>
      </div>

      {message && <p style={{ color: 'green' }}>{message}</p>}
      {error && <p style={{ color: 'red' }}>{error}</p>}

      {view === 'signup' ? (
        <form onSubmit={handleSignup}>
          <input placeholder="Business name" value={accountName}
                 onChange={e => setAccountName(e.target.value)} required /><br /><br />
          <input placeholder="Email" type="email" value={email}
                 onChange={e => setEmail(e.target.value)} required /><br /><br />
          <input placeholder="Password" type="password" value={password}
                 onChange={e => setPassword(e.target.value)} required /><br /><br />
          <button type="submit">Create account</button>
        </form>
      ) : (
        <form onSubmit={handleLogin}>
          <input placeholder="Email" type="email" value={email}
                 onChange={e => setEmail(e.target.value)} required /><br /><br />
          <input placeholder="Password" type="password" value={password}
                 onChange={e => setPassword(e.target.value)} required /><br /><br />
          <button type="submit">Log in</button>
        </form>
      )}
    </div>
  )
}

export default App
