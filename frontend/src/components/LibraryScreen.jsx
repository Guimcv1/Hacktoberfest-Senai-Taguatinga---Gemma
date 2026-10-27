import { useEffect, useState } from 'react'

export const initialCourses = []

export default function LibraryScreen({ courses, onOpenStudy, onNewStudy, onDelete, onAbandon, onUpdate, initialEditId }) {
  const [editing, setEditing] = useState(initialEditId || null)
  const [draft, setDraft] = useState(null)

  useEffect(() => {
    if (initialEditId) {
      const course = courses.find((item) => item.id === initialEditId)
      if (course) {
        setEditing(course.id)
        setDraft({ ...course })
      }
    }
  }, [initialEditId, courses])

  function startEditing(course) {
    setEditing(course.id)
    setDraft({ ...course })
  }

  function saveEditing() {
    if (draft?.title.trim()) onUpdate({ ...draft, title: draft.title.trim() })
    setEditing(null)
  }

  return <section className="library-screen">
    <div className="library-heading"><div><small>MINHA BIBLIOTECA</small><h1>Todos os seus estudos</h1><p>Ativos, antigos e abandonados ficam organizados nesta área.</p></div><button className="primary-button library-new" onClick={onNewStudy}>Novo estudo</button></div>
    <div className="library-toolbar"><span>{courses.length} estudos salvos</span><span>O progresso fica em cada estudo</span></div>
    <div className="library-grid">{courses.map((course) => <article className={`library-course ${course.color}`} key={course.id}>
      <div className="course-head"><span className="goal-symbol">{course.title.slice(0, 2).toUpperCase()}</span><div><span className="course-status">{course.status || 'Ativo'}</span><button className="edit-course" onClick={() => startEditing(course)}>Editar dados</button></div></div>
      {editing === course.id ? <EditModal draft={draft} setDraft={setDraft} onSave={saveEditing} onCancel={() => setEditing(null)} /> : <h2>{course.title}</h2>}
      <p>{course.detail}</p><div className="course-method"><span>Método</span><b>{course.method}</b></div><div className="course-progress"><div><small>Progresso</small><b>{course.progress}%</b></div><i><em style={{ width: `${course.progress}%` }} /></i></div>
      <div className="course-actions"><button className="study-button" onClick={() => onOpenStudy(course)}>{course.status === 'Abandonado' ? 'Retomar estudo' : 'Abrir estudo'} <span>→</span></button>{course.status !== 'Abandonado' && <button className="text-danger" onClick={() => onAbandon(course)}>Desistir</button>}<button className="text-danger" onClick={() => onDelete(course)}>Excluir</button></div>
    </article>)}</div>
  </section>
}

function EditModal({ draft, setDraft, onSave, onCancel }) {
  if (!draft) return null
  return <div className="modal-backdrop" onMouseDown={(event) => event.target === event.currentTarget && onCancel()}><div className="edit-modal" role="dialog" aria-modal="true"><div className="modal-heading"><div><small>EDITAR ESTUDO</small><h2>Dados da jornada</h2></div><button onClick={onCancel} aria-label="Fechar">Fechar</button></div><label>Nome do estudo<input value={draft.title} onChange={(event) => setDraft({ ...draft, title: event.target.value })} autoFocus /></label><label>Meta<input value={draft.detail} onChange={(event) => setDraft({ ...draft, detail: event.target.value })} /></label><label>Método<select value={draft.method} onChange={(event) => setDraft({ ...draft, method: event.target.value })}><option>Sessões focadas</option><option>Revisão espaçada</option><option>Aprender fazendo</option><option>Leitura e resumo</option></select></label><label>Adicionar PDFs<input type="file" accept=".pdf,application/pdf" multiple onChange={(event) => setDraft({ ...draft, files: [...(draft.files || []), ...Array.from(event.target.files || []).map((file) => file.name)] })} /></label>{draft.files?.length > 0 && <div className="file-list">{draft.files.map((file, index) => <div className="file-row" key={`${file}-${index}`}><small className="file-selected">{file}</small><button type="button" className="remove-file" onClick={() => setDraft({ ...draft, files: draft.files.filter((_, fileIndex) => fileIndex !== index) })}>Remover</button></div>)}</div>}<div className="modal-actions"><button className="outline-button" onClick={onCancel}>Cancelar</button><button className="primary-button" onClick={onSave}>Salvar alterações</button></div></div></div>
}
