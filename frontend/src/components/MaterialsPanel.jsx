import { useState } from 'react'

export default function MaterialsPanel() {
  const [file, setFile] = useState(null)
  return <section className="card" id="materiais">
    <div className="card-title"><h3>Seus materiais</h3><button>＋</button></div>
    <div className="material selected"><span>▤</span><div><b>{file || 'fundamentos-de-redes.pdf'}</b><small>{file ? 'Arquivo selecionado' : '2.4 MB · 48 páginas'}</small></div><strong>✓</strong></div>
    <div className="material"><span>▤</span><div><b>anotacoes-aula-03.pdf</b><small>890 KB · 12 páginas</small></div></div>
    <label className="upload">↑ Adicionar PDF<input type="file" accept=".pdf" onChange={(event) => setFile(event.target.files?.[0]?.name)} /></label>
  </section>
}
