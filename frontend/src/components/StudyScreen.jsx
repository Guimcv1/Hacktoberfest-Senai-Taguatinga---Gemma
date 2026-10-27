import { useState } from 'react'
import TeacherAvatar from './TeacherAvatar'
import { askQuestion, deleteDocument, uploadDocument } from '../services/api'

export default function StudyScreen({ study, token, onBack, onDelete, onAbandon, onEdit }) {
  const [question, setQuestion] = useState('')
  const [attachments, setAttachments] = useState(study?.files || [])
  const [documentIds, setDocumentIds] = useState(study?.documentIds || [])
  const [answer, setAnswer] = useState('')
  const [currentStep, setCurrentStep] = useState(study?.currentStep || 1)
  const [quizActive, setQuizActive] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const [isListening, setIsListening] = useState(false)
  const [chatMessages, setChatMessages] = useState([])
  const [conversationId, setConversationId] = useState(study?.conversationId || null)

  function toggleMicrophone() {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      setAnswer('Seu navegador não oferece entrada por voz.')
      return
    }
    if (isListening) return
    const recognition = new SpeechRecognition()
    recognition.lang = 'pt-BR'
    recognition.interimResults = false
    recognition.onstart = () => setIsListening(true)
    recognition.onresult = (event) => setQuestion((current) => `${current} ${event.results[0][0].transcript}`.trim())
    recognition.onerror = () => setAnswer('Não foi possível captar sua voz. Tente novamente.')
    recognition.onend = () => setIsListening(false)
    recognition.start()
  }

  function speakAnswer(text) {
    if ('speechSynthesis' in window && text) {
      window.speechSynthesis.cancel()
      window.speechSynthesis.speak(new SpeechSynthesisUtterance(text))
    }
  }

  async function ask(event) {
    event.preventDefault()
    const text = question.trim()
    if (!text || isLoading) return
    setChatMessages((current) => [...current, { role: 'student', text }])
    setQuestion('')
    setAnswer('')
    setIsLoading(true)
    try {
      const payload = { message: text }
      if (conversationId) payload.conversation_id = conversationId
      if (documentIds[0]) payload.document_id = documentIds[0]
      const response = await askQuestion(token, payload)
      if (response?.conversation_id) setConversationId(response.conversation_id)
      const answerText = response?.answer || 'Não consegui gerar uma resposta agora.'
      setAnswer(answerText)
      setChatMessages((current) => [...current, { role: 'tutor', text: answerText }])
    } catch (error) {
      const errorMessage = error instanceof Error ? error.message : 'Ocorreu um erro ao comunicar com a IA. Tente novamente.'
      setAnswer(errorMessage)
      setChatMessages((current) => [...current, { role: 'tutor', text: errorMessage }])
    } finally {
      setIsLoading(false)
    }
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

  if (quizActive) {
    return <QuizPanel study={study} onBack={() => setQuizActive(false)} onComplete={() => { setCurrentStep(2); setQuizActive(false) }} />
  }

  return <section className="study-screen">
    <button className="back-button" onClick={onBack}>Voltar para a biblioteca</button>
    <div className="study-hero"><div><span className="goal-symbol">{study?.title?.slice(0, 2).toUpperCase() || 'ES'}</span><small>JORNADA DE ESTUDO</small><h1>{study?.title || 'Estudo'}</h1><p>Próximo passo: <b>{study?.next || 'Começar seu primeiro conteúdo'}</b></p></div><div className="study-score"><b>{study?.progress || 0}%</b><small>concluído</small></div></div>
    <div className="study-actions"><button className="outline-button" onClick={() => onEdit(study)}>Editar dados</button><button className="danger-button" onClick={() => onAbandon(study)}>Desistir do estudo</button><button className="danger-button" onClick={() => onDelete(study)}>Excluir estudo</button></div>
    <div className="study-columns"><div className="question-card"><div className="question-teacher"><TeacherAvatar /><div><small>TUTOR DESTE ESTUDO</small><b>Estou pronto para ajudar</b></div></div><small>PERGUNTA SOBRE O ESTUDO</small><h2>O que você quer entender?</h2><p>Faça perguntas sobre este estudo. O PDF é opcional.</p>{chatMessages.length > 0 && <div className="study-chat">{chatMessages.map((message, index) => <div className={`study-chat-message ${message.role}`} key={`${message.role}-${index}`}><TeacherAvatar student={message.role === 'student'} /><div><small>{message.role === 'student' ? 'Você' : 'Tutor IA'}</small><p>{message.text}</p>{message.role === 'tutor' && <button type="button" className="speak-button" onClick={() => speakAnswer(message.text)}>🔊 Ouvir resposta</button>}</div></div>)}{isLoading && <div className="study-chat-message tutor"><TeacherAvatar /><div><small>Tutor IA</small><p className="typing-feedback"><i /><i /><i /> Analisando seu estudo...</p></div></div>}</div>}<form className="question-form" onSubmit={ask}><div className="question-input-wrap"><textarea value={question} onChange={(event) => setQuestion(event.target.value)} placeholder="Ex.: Explique este assunto de forma simples." required /><button type="button" className={`mic-button ${isListening ? 'listening' : ''}`} onClick={toggleMicrophone} aria-label="Falar pergunta">🎙️</button></div><label className="attach-button">Anexar PDFs (opcional)<input type="file" accept=".pdf,application/pdf" multiple onChange={attachFiles} /></label>{attachments.length > 0 && <div className="file-list">{attachments.map((file, index) => <div className="file-row" key={`${file}-${index}`}><small className="file-selected">{file}</small><button type="button" className="remove-file" onClick={() => removeAttachment(index)}>Remover</button></div>)}</div>}<button className="primary-button" type="submit" disabled={isLoading}>{isLoading ? 'Aguardando resposta...' : 'Enviar pergunta'} <span>→</span></button></form>{answer && !chatMessages.length && <p className="answer-box">{answer}</p>}</div><div className="checklist"><h3>Seu caminho até a meta</h3>{['Introdução', 'Exercícios', 'Revisão final'].map((item, index) => <button type="button" className={`check-item ${index < currentStep ? 'done' : ''} ${index === currentStep ? 'current' : ''}`} key={item} onClick={() => index === 1 ? setQuizActive(true) : setCurrentStep(Math.min(index + 1, 2))}><span>{index < currentStep ? 'Concluído' : index + 1}</span><b>{item}</b>{index === 1 && <small>Fazer quiz</small>}{index !== 1 && index === currentStep && <small>Próximo · avançar</small>}</button>)}</div></div>
  </section>
}

function QuizPanel({ study, onBack, onComplete }) {
  const questions = [
    { question: `Qual é o principal objetivo do estudo "${study?.title || 'atual'}"?`, options: ['Compreender e aplicar o conteúdo', 'Apenas memorizar títulos', 'Ignorar os exercícios', 'Concluir sem revisar'], correct: 0 },
    { question: 'Qual atitude ajuda a fixar melhor o que foi estudado?', options: ['Revisar e praticar', 'Pular as dúvidas', 'Estudar sem pausas', 'Ler apenas uma vez'], correct: 0 },
    { question: 'O que fazer quando uma parte do conteúdo não ficou clara?', options: ['Perguntar ao tutor e revisar', 'Desistir do estudo', 'Avançar sem entender', 'Excluir o material'], correct: 0 },
    { question: 'Qual é uma boa forma de conferir seu aprendizado?', options: ['Responder perguntas sobre o conteúdo', 'Evitar exemplos', 'Não fazer anotações', 'Memorizar sem praticar'], correct: 0 },
  ]
  const [current, setCurrent] = useState(0)
  const [selected, setSelected] = useState(null)
  const [score, setScore] = useState(0)
  const [finished, setFinished] = useState(false)

  function answerQuestion() {
    if (selected === null) return
    const nextScore = score + (selected === questions[current].correct ? 1 : 0)
    if (current === questions.length - 1) {
      setScore(nextScore)
      setFinished(true)
      return
    }
    setScore(nextScore)
    setCurrent((value) => value + 1)
    setSelected(null)
  }

  return <section className="study-screen quiz-screen">
    <button className="back-button" onClick={onBack}>Voltar para o tutor</button>
    <div className="quiz-heading"><small>EXERCÍCIOS DO ESTUDO</small><h1>Quiz de revisão</h1><p>Responda às perguntas e veja uma revisão geral no final.</p></div>
    {!finished ? <div className="quiz-card"><div className="quiz-progress">Pergunta {current + 1} de {questions.length}</div><h2>{questions[current].question}</h2><div className="quiz-options">{questions[current].options.map((option, index) => <button type="button" className={selected === index ? 'selected' : ''} key={option} onClick={() => setSelected(index)}>{option}</button>)}</div><button className="primary-button" type="button" onClick={answerQuestion}>{current === questions.length - 1 ? 'Ver revisão geral' : 'Próxima pergunta'} <span>→</span></button></div> : <div className="quiz-card quiz-review"><span className="quiz-result">REVISÃO GERAL</span><h2>Você concluiu o quiz</h2><strong>{score} de {questions.length} respostas corretas</strong><p>{score === questions.length ? 'Excelente! Você demonstrou domínio do conteúdo.' : 'Revise os pontos principais e tente novamente para reforçar seu aprendizado.'}</p><button className="primary-button" type="button" onClick={onComplete}>Voltar para o estudo <span>→</span></button></div>}
  </section>
}
