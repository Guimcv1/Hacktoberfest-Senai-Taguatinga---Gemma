export default function WelcomeCard({ study }) {
  if (!study) {
    return <section className="welcome-card"><div><label>SEU ESPAÇO DE ESTUDOS</label><h2>Crie seu primeiro estudo.</h2><p>Adicione um estudo para começar sua jornada de aprendizagem.</p></div><div className="completion empty-completion">+</div></section>
  }

  return <section className="welcome-card">
    <div><label>SEU ESTUDO ATUAL</label><h2>Continue de onde parou.</h2><p>Seu professor está pronto para revisar <b>{study.title}</b> com você.</p></div>
    <div className="completion"><b>{study.progress || 0}%</b><small>concluído</small></div>
  </section>
}
