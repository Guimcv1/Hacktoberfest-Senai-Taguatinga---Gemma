export default function GoalCards({ goals, onOpenStudy, onNewStudy }) {
  return <section className="goals-section">
    <div className="section-title"><div><small>SUAS JORNADAS</small><h2>Estudos em andamento</h2></div><button className="outline-button" onClick={onNewStudy}>Novo estudo</button></div>
    <div className="goal-grid">{goals.map((goal) => <article className={`goal-card ${goal.color}`} key={goal.title}><div className="goal-top"><span className="goal-symbol">{goal.color === 'green' ? '⌘' : goal.color === 'purple' ? 'JS' : '文'}</span><button>•••</button></div><h3>{goal.title}</h3><span className="goal-type">{goal.type}</span><div className="goal-progress"><div><small>Progresso</small><b>{goal.progress}%</b></div><i><em style={{ width: `${goal.progress}%` }} /></i></div><p>Próximo: <strong>{goal.next}</strong></p><button className="study-button" onClick={() => onOpenStudy(goal)}>Continuar estudo <span>→</span></button></article>)}</div>
  </section>
}
