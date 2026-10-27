import { useState } from 'react'

function LoginScreen({ onLogin, onRegister, error }) {
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [showPassword, setShowPassword] = useState(false)

  function submit(event) {
    event.preventDefault()
    onLogin({ email, password })
  }

  return <main className="login-page">
    <section className="login-art">
      <div className="login-logo"><span>✦</span> study<strong>buddy</strong></div>
      <div><p className="login-quote">Seu próximo passo começa<br /><b>com uma boa pergunta.</b></p><small>Estude no seu ritmo. Evolua todos os dias.</small></div>
    </section>
    <section className="login-form-wrap">
      <form className="login-form" onSubmit={submit}>
        <div className="mobile-login-logo"><span>✦</span> study<strong>buddy</strong></div>
        <small className="form-kicker">BEM-VINDO DE VOLTA</small>
        <h1>Entre na sua<br /><span>jornada de estudos.</span></h1>
        <p>Acompanhe suas metas e continue aprendendo com seu professor.</p>{error && <p className="auth-error">{error}</p>}
        <label>E-mail<input type="email" placeholder="voce@email.com" value={email} onChange={(event) => setEmail(event.target.value)} required /></label>
        <label>Senha<div className="password-field"><input type={showPassword ? 'text' : 'password'} placeholder="Digite sua senha" value={password} onChange={(event) => setPassword(event.target.value)} required /><button type="button" onClick={() => setShowPassword((visible) => !visible)}>{showPassword ? 'Ocultar' : 'Mostrar'}</button></div></label>
        <div className="form-options"><label className="remember"><input type="checkbox" /> Lembrar de mim</label></div>
        <button className="primary-button" type="submit">Entrar na minha conta <span>→</span></button>
        <small className="signup">Ainda não tem uma conta? <button type="button" className="inline-link" onClick={onRegister}>Criar conta</button></small>
      </form>
    </section>
  </main>
}

export default LoginScreen
