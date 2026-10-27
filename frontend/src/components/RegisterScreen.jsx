import { useState } from 'react'

export default function RegisterScreen({ onRegister, onBack, error }) {
  const [name, setName] = useState('')
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')

  function submit(event) {
    event.preventDefault()
    onRegister({ name, email, password })
  }

  return <main className="login-page">
    <section className="login-art register-art">
      <div className="login-logo"><span>SB</span> study<strong>buddy</strong></div>
      <div className="register-message"><small>NOVA JORNADA</small><h2>Crie seu espaço<br /><b>para aprender.</b></h2><p>Organize seus materiais e estude com mais clareza, no seu ritmo.</p></div>
    </section>
    <section className="login-form-wrap">
      <form className="login-form" onSubmit={submit}>
        <button className="back-button login-back" type="button" onClick={onBack}>Voltar para entrar</button>
        <div className="mobile-login-logo"><span>SB</span> study<strong>buddy</strong></div>
        <small className="form-kicker">CRIAR CONTA</small>
        <h1>Comece sua<br /><span>jornada de estudos.</span></h1>
        <p>Preencha seus dados para criar sua conta.</p>
        {error && <p className="auth-error">{error}</p>}
        <label>Nome<input type="text" placeholder="Seu nome" value={name} onChange={(event) => setName(event.target.value)} required /></label>
        <label>E-mail<input type="email" placeholder="voce@email.com" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
        <label>Senha<input type="password" minLength="8" placeholder="Mínimo de 8 caracteres" value={password} onChange={(event) => setPassword(event.target.value)} required /></label>
        <button className="primary-button" type="submit">Criar minha conta <span>→</span></button>
        <small className="signup">Já tem uma conta? <button type="button" className="inline-link" onClick={onBack}>Entrar</button></small>
      </form>
    </section>
  </main>
}
