import { useState } from 'react'

export default function GoalSetup({ onBack, onCreate }) {
  const [title, setTitle] = useState('')
  const [detail, setDetail] = useState('')
  const [files, setFiles] = useState([])
  const [method, setMethod] = useState('Sessões focadas')
  const [dailyMinutes, setDailyMinutes] = useState(45)
  const methods = ['Sessões focadas', 'Revisão espaçada', 'Aprender fazendo', 'Leitura e resumo']

  function submit(event) {
    event.preventDefault()
    if (!title.trim()) return
    onCreate({ title: title.trim(), detail: detail.trim() || 'Meta pessoal', progress: 0, method, dailyMinutes, color: 'green', files, status: 'Ativo' })
  }

  return <form className="setup-page" onSubmit={submit}>
    <button className="back-button" type="button" onClick={onBack}>Voltar para a biblioteca</button>
    <div className="setup-heading"><small>CONFIGURE SUA JORNADA</small><h1>Como você quer estudar?</h1><p>Defina os dados do estudo, escolha um método e anexe o material.</p></div>
    <div className="setup-grid">
      <div className="setup-card"><span className="setup-number">01</span><h2>Dados do estudo</h2><label>Nome do estudo<input value={title} onChange={(event) => setTitle(event.target.value)} placeholder="Ex.: Preparação para prova de redes" required /></label><label>Meta do estudo<textarea value={detail} onChange={(event) => setDetail(event.target.value)} placeholder="Ex.: Entender os principais protocolos." /></label><label>Materiais em PDF<input type="file" accept=".pdf,application/pdf" multiple onChange={(event) => setFiles(Array.from(event.target.files || []).map((file) => file.name))} /></label>{files.length > 0 && <div className="file-list">{files.map((file, index) => <small className="file-selected" key={`${file}-${index}`}>{file}</small>)}</div>}</div>
      <div className="setup-card"><span className="setup-number">02</span><h2>Escolha seu método</h2><div className="method-list">{methods.map((item) => <button type="button" className={method === item ? 'chosen' : ''} onClick={() => setMethod(item)} key={item}><span>{method === item ? 'Selecionado' : 'Escolher'}</span><div><b>{item}</b><small>{item === 'Sessões focadas' ? 'Blocos de 25 minutos com pausas.' : item === 'Revisão espaçada' ? 'Revise o conteúdo no momento certo.' : item === 'Aprender fazendo' ? 'Exercícios e desafios práticos.' : 'Transforme conteúdo em notas simples.'}</small></div></button>)}</div><div className="method-setting"><b>Tempo por dia</b><span>{dailyMinutes} min</span><input type="range" min="15" max="120" step="5" value={dailyMinutes} onChange={(event) => setDailyMinutes(Number(event.target.value))} /></div></div>
    </div>
    <button className="primary-button setup-submit" type="submit">Criar minha jornada <span>→</span></button>
  </form>
}
