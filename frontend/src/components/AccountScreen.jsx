import { useState } from 'react'

export default function AccountScreen({ user, onSave, onLogout }) {
  const [name, setName] = useState(user?.name || 'Arthur')
  const [email, setEmail] = useState(user?.email || '')
  const [saved, setSaved] = useState(false)

  function submit(event) {
    event.preventDefault()
    onSave({ name: name.trim(), email: email.trim() })
    setSaved(true)
  }

  return <section className="account-screen">
    <div className="account-heading"><small>MINHA CONTA</small><h1>Gerenciar conta</h1><p>Atualize seus dados pessoais e o acesso ao StudyBuddy.</p></div>
    <form className="account-card" onSubmit={submit}>
      <h2>Dados pessoais</h2>
      <label>Nome<input value={name} onChange={(event) => { setName(event.target.value); setSaved(false) }} required /></label>
      <label>E-mail<input type="email" value={email} onChange={(event) => { setEmail(event.target.value); setSaved(false) }} required /></label>
      <div className="account-actions"><button className="primary-button" type="submit">Salvar alterações</button>{saved && <small className="saved-message">Dados salvos.</small>}</div>
    </form>
    <div className="account-card account-danger"><h2>Sessão</h2><p>Encerre o acesso nesta sessão neste dispositivo.</p><button className="danger-button" type="button" onClick={onLogout}>Sair da conta</button></div>
  </section>
}
