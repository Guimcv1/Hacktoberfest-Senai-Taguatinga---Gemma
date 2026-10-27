import Icon from './Icon'

export default function Sidebar({ active, onNavigate, onLogout }) {
  return <aside className="sidebar">
    <div className="logo"><span>SB</span> study<strong>buddy</strong></div>
    <nav>
      <a className={active === 'dashboard' ? 'active' : ''} href="#dashboard" onClick={() => onNavigate('dashboard')}><Icon><path d="m3 10 9-7 9 7v10H5V9m4 11v-6h6v6" /></Icon> Visão geral</a>
      <a className={active === 'library' ? 'active' : ''} href="#biblioteca" onClick={() => onNavigate('library')}><Icon><path d="M5 4h14v17H5zM8 8h8M8 12h8M8 16h5" /></Icon> Minha biblioteca</a>
      <a className={active === 'account' ? 'active' : ''} href="#conta" onClick={() => onNavigate('account')}><Icon><circle cx="12" cy="8" r="3" /><path d="M5 21c.7-3.4 3-5 7-5s6.3 1.6 7 5" /></Icon> Minha conta</a>
    </nav>
    <button className="logout-link" onClick={onLogout}>Sair da conta</button>
  </aside>
}
