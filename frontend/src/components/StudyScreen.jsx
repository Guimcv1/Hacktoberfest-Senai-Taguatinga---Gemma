import { useState } from 'react'
import TeacherAvatar from './TeacherAvatar'
import { askQuestion, deleteDocument, uploadDocument } from '../services/api'

export default function StudyScreen({ study, token, onBack, onDelete, onAbandon, onEdit }) {
  const [tab, setTab] = useState('visao')
  const [question, setQuestion] = useState('')
  const [attachments, setAttachments] = useState(study?.files || [])
  const [documentIds, setDocumentIds] = useState(study?.documentIds || [])
  const [answer, setAnswer] = useState('')
  const [currentStep, setCurrentStep] = useState(study?.currentStep || 1)

  async function ask(event) {
    event.preventDefault()
    if (!question.trim()) return
    if (!documentIds[0]) {
      setAnswer(attachments.length ? 'Este material ainda não está disponível para perguntas. Anexe-o novamente para sincronizar com o professor.' : 'Adicione um PDF antes de enviar sua pergunta.')
      return
    }
    try {
      const response = await askQuestion(token, { document_id: documentIds[0], message: question })
      setAnswer(response.answer)
    } catch (error) {
      setAnswer('Ocorreu um erro da nossa parte. Tente novamente em alguns instantes.')
    }
    setQuestion('')
  }

  async function attachFiles(event) {
    const files = Array.from(event.target.files || [])
    for (const file of files) {
      try {
        const response = await uploadDocument(token, file)
        setAttachments((current) => [...current, response.filename || file.name])
        setDocumentIds((current) => [...current, response.document_id])
      } catch (error) {
        setAnswer('Ocorreu um erro ao adicionar um PDF. Tente novamente.')
      }
    }
    event.target.value = ''
  }

  async function removeAttachment(index) {
    const documentId = documentIds[index]
    if (documentId) {
      try {
        await deleteDocument(token, documentId)
      } catch (error) {
        setAnswer('Ocorreu um erro ao remover o PDF. Tente novamente.')
        return
      }
    }
    setAttachments((current) => current.filter((_, itemIndex) => itemIndex !== index))
    setDocumentIds((current) => current.filter((_, itemIndex) => itemIndex !== index))
  }

  return <section className="study-screen">
    <button className="back-button" onClick={onBack}>Voltar para a biblioteca</button>
    <div className="study-hero"><div><span className="goal-symbol">{study?.title?.slice(0, 2).toUpperCase() || 'ES'}</span><small>JORNADA DE ESTUDO</small><h1>{study?.title || 'Estudo'}</h1><p>Próximo passo: <b>{study?.next || 'Começar seu primeiro conteúdo'}</b></p></div><div className="study-score"><b>{study?.progress || 0}%</b><small>concluído</small></div></div>
    <div className="study-actions"><button className="outline-button" onClick={() => onEdit(study)}>Editar dados</button><button className="danger-button" onClick={() => onAbandon(study)}>Desistir do estudo</button><button className="danger-button" onClick={() => onDelete(study)}>Excluir estudo</button></div>
    <div className="study-tabs">{[['visao', 'Perguntar ao professor'], ['metodo', 'Meu método'], ['material', 'Materiais'], ['historico', 'Histórico']].map(([value, label]) => <button className={tab === value ? 'active' : ''} onClick={() => setTab(value)} key={value}>{label}</button>)}</div>
    {tab === 'visao' && <div className="study-columns"><div className="question-card"><div className="question-teacher"><TeacherAvatar /><div><small>PROFESSOR BUDDY</small><b>Estou pronto para ajudar</b></div></div><small>PERGUNTA SOBRE O ESTUDO</small><h2>O que você quer entender?</h2><p>Escreva sua dúvida sobre o assunto deste estudo.</p><form className="question-form" onSubmit={ask}><textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ex.: Explique este assunto de forma simples." required /><label className="attach-button">Anexar PDFs<input type="file" accept=".pdf,application/pdf" multiple onChange={attachFiles} /></label>{attachments.length > 0 && <div className="file-list">{attachments.map((file, index) => <div className="file-row" key={`${file}-${index}`}><small className="file-selected">{file}</small><button type="button" className="remove-file" onClick={() => removeAttachment(index)}>Remover</button></div>)}</div>}<button className="primary-button" type="submit">Enviar pergunta <span>→</span></button></form>{answer && <p className="answer-box">{answer}</p>}</div><div className="checklist"><h3>Seu caminho até a meta</h3>{['Introdução', 'Conteúdo principal', 'Exercícios', 'Revisão final'].map((item, index) => <button type="button" className={`check-item ${index < currentStep ? 'done' : ''} ${index === currentStep ? 'current' : ''}`} key={item} onClick={() => setCurrentStep(Math.min(index + 1, 3))}><span>{index < currentStep ? 'Concluído' : index + 1}</span><b>{item}</b>{index === currentStep && <small>Próximo · avançar</small>}</button>)}</div></div>}
    {tab === 'metodo' && <div className="method-detail"><div><small>SEU MÉTODO ATUAL</small><h2>{study?.method || 'Sessões focadas'}</h2><p>Este método organiza sua rotina de acordo com o objetivo deste estudo.</p></div><button className="outline-button" onClick={() => onEdit(study)}>Editar método</button></div>}
    {tab === 'material' && <div className="empty-study-tab"><span>PDF</span><h2>Materiais deste estudo</h2>{attachments.length > 0 ? <div className="file-list">{attachments.map((file, index) => <div className="file-row" key={`${file}-${index}`}><p className="file-selected">{file}</p><button type="button" className="remove-file" onClick={() => removeAttachment(index)}>Remover</button></div>)}</div> : <p>Nenhum PDF anexado ainda.</p>}<label className="attach-button">Anexar PDFs<input type="file" accept=".pdf,application/pdf" multiple onChange={attachFiles} /></label></div>}
    {tab === 'historico' && <div className="empty-study-tab"><span>H</span><h2>Histórico do estudo</h2><p>Seu progresso e as sessões concluídas aparecerão aqui.</p></div>}
  </section>
}
