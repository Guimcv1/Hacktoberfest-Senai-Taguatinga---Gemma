export default function Header({ user }) {
  const firstName = user?.name?.trim().split(/\s+/)[0] || 'estudante'

  return <header className="header">
    <button className="mobile-menu" aria-label="Abrir menu"><span /><span /><span /></button>
    <div><small>TERÇA-FEIRA, 27 DE OUTUBRO</small><h1>Olá, {firstName}</h1></div>
  </header>
}
