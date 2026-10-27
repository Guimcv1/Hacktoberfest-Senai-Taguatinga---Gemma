import { useState } from 'react'

export default function AccountScreen({ user, onSave, onChangePassword, onLogout }) {
  const [name, setName] = useState(user?.name || 'Arthur')
  const [email, setEmail] = useState(user?.email || '')
  const [saved, setSaved] = useState(false)
  const [currentPassword, setCurrentPassword] = useState('')
  const [newPassword, setNewPassword] = useState('')
  const [confirmPassword, setConfirmPassword] = useState('')
  const [passwordMessage, setPasswordMessage] = useState('')

  function submit(event) {
    event.preventDefault()
    onSave({ name: name.trim(), email: email.trim() })
    setSaved(true)
  }

  function changePassword(event) {
    event.preventDefault()
    if (newPassword.length < 8) {
      setPasswordMessage('A nova senha precisa ter pelo menos 8 caracteres.')
      return
    }
    if (newPassword !== confirmPassword) {
      setPasswordMessage('A confirmação da senha não confere.')
      return
    }
    onChangePassword({ currentPassword, newPassword })
    setCurrentPassword('')
    setNewPassword('')
    setConfirmPassword('')
    setPasswordMessage('Senha alterada nesta sessão.')
  }

  return <section className="account-screen">
    <div className="account-heading"><small>MINHA CONTA</small><h1>Gerenciar conta</h1><p>Atualize seus dados pessoais e o acesso ao StudyBuddy.</p></div>
    <form className="account-card" onSubmit={submit}>
      <h2>Dados pessoais</h2>
      <label>Nome<input value={name} onChange={(event) => { setName(event.target.value); setSaved(false) }} required /></label>
      <label>E-mail<input type="email" value={email} onChange={(event) => { setEmail(event.target.value); setSaved(false) }} required /></label>
      <div className="account-actions"><button className="primary-button" type="submit">Salvar alterações</button>{saved && <small className="saved-message">Dados salvos.</small>}</div>
    </form>
    <form className="account-card" onSubmit={changePassword}>
      <h2>Trocar senha</h2>
      <label>Senha atual<input type="password" value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} required /></label>
      <label>Nova senha<input type="password" minLength="8" value={newPassword} onChange={(event) => setNewPassword(event.target.value)} required /></label>
      <label>Confirmar nova senha<input type="password" minLength="8" value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} required /></label>
      <div className="account-actions"><button className="primary-button" type="submit">Trocar senha</button>{passwordMessage && <small className="saved-message">{passwordMessage}</small>}</div>
    </form>
    <div className="account-card account-danger"><h2>Sessão</h2><p>Encerre o acesso nesta sessão neste dispositivo.</p><button className="danger-button" type="button" onClick={onLogout}>Sair da conta</button></div>
  </section>
}
