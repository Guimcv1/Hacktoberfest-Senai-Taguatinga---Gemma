import { useState } from 'react'

export default function GoalCards({ goals, onOpenStudy, onNewStudy, onEditStudy, onAbandonStudy }) {
  const [menuId, setMenuId] = useState(null)
  return <section className="goals-section">
    <div className="section-title"><div><small>SUAS JORNADAS</small><h2>Estudos em andamento</h2></div><button className="outline-button" onClick={onNewStudy}>Novo estudo</button></div>
    {goals.length === 0 ? <div className="empty-goals"><p>Você ainda não tem estudos criados.</p><button className="primary-button" onClick={onNewStudy}>Criar primeiro estudo <span>→</span></button></div> : <div className="goal-grid">{goals.map((goal) => <article className={`goal-card ${goal.color}`} key={goal.id || goal.title}><div className="goal-top"><span className="goal-symbol">{goal.color === 'green' ? '⌘' : goal.color === 'purple' ? 'JS' : '文'}</span><div className="goal-menu"><button type="button" aria-label={`Opções de ${goal.title}`} onClick={() => setMenuId(menuId === goal.id ? null : goal.id)}>•••</button>{menuId === goal.id && <div className="goal-menu-popover"><button type="button" onClick={() => { onEditStudy(goal); setMenuId(null) }}>Editar</button><button type="button" onClick={() => { onAbandonStudy(goal); setMenuId(null) }}>Desistir</button></div>}</div></div><h3>{goal.title}</h3><span className="goal-type">{goal.type}</span><div className="goal-progress"><div><small>Progresso</small><b>{goal.progress}%</b></div><i><em style={{ width: `${goal.progress}%` }} /></i></div><p>Próximo: <strong>{goal.next}</strong></p><button className="study-button" onClick={() => onOpenStudy(goal)}>Continuar estudo <span>→</span></button></article>)}</div>}
  </section>
}
