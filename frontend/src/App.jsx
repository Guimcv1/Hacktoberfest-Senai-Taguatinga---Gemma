import { useState } from 'react'
import Sidebar from './components/Sidebar'
import LoginScreen from './components/LoginScreen'
import Dashboard from './components/Dashboard'
import GoalSetup from './components/GoalSetup'
import StudyScreen from './components/StudyScreen'
import LibraryScreen from './components/LibraryScreen'
import { initialCourses } from './components/LibraryScreen'
import RegisterScreen from './components/RegisterScreen'
import AccountScreen from './components/AccountScreen'
import { login, logout, register } from './services/api'

export default function App() {
  const [loggedIn, setLoggedIn] = useState(false)
  const [authMode, setAuthMode] = useState('login')
  const [token, setToken] = useState(() => localStorage.getItem('studybuddy_token'))
  const [authError, setAuthError] = useState('')
  const [screen, setScreen] = useState('dashboard')
  const [study, setStudy] = useState(null)
  const [courses, setCourses] = useState(initialCourses)
  const [editId, setEditId] = useState(null)
  const [user, setUser] = useState(() => JSON.parse(localStorage.getItem('studybuddy_user') || 'null'))
  async function handleLogin(credentials) {
    setAuthError('')
    try {
      const response = await login(credentials)
      if (!response?.access_token) throw new Error('Resposta de autenticação inválida.')
      localStorage.setItem('studybuddy_token', response.access_token)
      setToken(response.access_token)
      setUser(response.user)
      localStorage.setItem('studybuddy_user', JSON.stringify(response.user))
      setLoggedIn(true)
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : 'Não foi possível criar sua conta.')
    }
  }
  async function handleRegister(user) {
    setAuthError('')
    try {
      const response = await register(user)
      if (!response?.access_token) throw new Error('Resposta de autenticação inválida.')
      localStorage.setItem('studybuddy_token', response.access_token)
      setToken(response.access_token)
      setUser(response.user)
      localStorage.setItem('studybuddy_user', JSON.stringify(response.user))
      setLoggedIn(true)
    } catch (error) {
      setAuthError(error instanceof Error ? error.message : 'Ocorreu um erro ao cadastrar.')
    }
  }
  function handleLogout() {
    if (token) logout(token).catch(() => {})
    localStorage.removeItem('studybuddy_token')
    setToken(null)
    setLoggedIn(false)
    setAuthMode('login')
    localStorage.removeItem('studybuddy_user')
  }
  if (!loggedIn && authMode === 'register') return <RegisterScreen onRegister={handleRegister} onBack={() => { setAuthError(''); setAuthMode('login') }} error={authError} />
  if (!loggedIn) return <LoginScreen onLogin={handleLogin} onRegister={() => { setAuthError(''); setAuthMode('register') }} error={authError} />
  function openStudy(selected) { setStudy(selected); setScreen('study') }
  function removeStudy(selected) { if (window.confirm(`Excluir o estudo "${selected.title}"?`)) { setCourses((items) => items.filter((item) => item.id !== selected.id)); setScreen('library') } }
  function abandonStudy(selected) { setCourses((items) => items.map((item) => item.id === selected.id ? { ...item, status: 'Abandonado' } : item)); setScreen('library') }
  function resumeStudy(selected) { setCourses((items) => items.map((item) => item.id === selected.id ? { ...item, status: 'Ativo' } : item)); openStudy({ ...selected, status: 'Ativo' }) }
  function createStudy(newStudy) { const created = { ...newStudy, id: Date.now() }; setCourses((items) => [...items, created]); setStudy(created); setScreen('study') }
  function updateStudy(updated) { setCourses((items) => items.map((item) => item.id === updated.id ? updated : item)); setStudy(updated) }
  function editStudy(selected) { setStudy(selected); setEditId(selected.id); setScreen('library') }
<<<<<<< HEAD
  return <div className="app"><Sidebar active={screen} onNavigate={setScreen} onLogout={handleLogout} /><main>{screen === 'dashboard' && <Dashboard user={user} goals={courses.filter((item) => item.status !== 'Abandonado')} onOpenStudy={openStudy} onNewStudy={() => setScreen('setup')} onEditStudy={editStudy} onAbandonStudy={abandonStudy} />}{screen === 'library' && <LibraryScreen courses={courses} onOpenStudy={(selected) => selected.status === 'Abandonado' ? resumeStudy(selected) : openStudy(selected)} onNewStudy={() => setScreen('setup')} onDelete={removeStudy} onAbandon={abandonStudy} onUpdate={(updated) => { updateStudy(updated); setEditId(null) }} initialEditId={editId} />}{screen === 'setup' && <GoalSetup onBack={() => setScreen('library')} onCreate={createStudy} />}{screen === 'study' && <StudyScreen study={study} token={token} onBack={() => setScreen('library')} onDelete={removeStudy} onAbandon={abandonStudy} onEdit={editStudy} />}{screen === 'account' && <AccountScreen user={user} onSave={(updated) => { setUser(updated); localStorage.setItem('studybuddy_user', JSON.stringify(updated)) }} onChangePassword={() => {}} onLogout={handleLogout} />}</main></div>
=======
  return <div className="app"><Sidebar active={screen} onNavigate={setScreen} onLogout={handleLogout} /><main>{screen === 'dashboard' && <Dashboard goals={courses.filter((item) => item.status !== 'Abandonado')} onOpenStudy={openStudy} onNewStudy={() => setScreen('setup')} onEditStudy={editStudy} onAbandonStudy={abandonStudy} />}{screen === 'library' && <LibraryScreen courses={courses} onOpenStudy={(selected) => selected.status === 'Abandonado' ? resumeStudy(selected) : openStudy(selected)} onNewStudy={() => setScreen('setup')} onDelete={removeStudy} onAbandon={abandonStudy} onUpdate={(updated) => { updateStudy(updated); setEditId(null) }} initialEditId={editId} />}{screen === 'setup' && <GoalSetup onBack={() => setScreen('library')} onCreate={createStudy} />}{screen === 'study' && <StudyScreen study={study} token={token} onBack={() => setScreen('library')} onDelete={removeStudy} onAbandon={abandonStudy} onEdit={editStudy} />}{screen === 'account' && <AccountScreen user={user} token={token} onSave={(updated) => { setUser(updated); localStorage.setItem('studybuddy_user', JSON.stringify(updated)) }} onChangePassword={() => {}} onLogout={handleLogout} />}</main></div>
>>>>>>> e10bbaba10e3d0af0f7636072277845496b3bb03
}
