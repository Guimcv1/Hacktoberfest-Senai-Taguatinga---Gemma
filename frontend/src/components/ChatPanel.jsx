import { useState } from 'react'
import TeacherAvatar from './TeacherAvatar'

const initialMessages = [
  { role: 'teacher', text: 'Olá, Arthur! Eu li seu material e estou pronto para estudar com você.', time: '09:41' },
  { role: 'student', text: 'Pode me explicar de forma simples o que é o modelo OSI?', time: '09:42' },
  { role: 'teacher', text: 'Claro! O modelo OSI é como uma receita em sete etapas que organiza a comunicação entre dispositivos.', time: '09:42', source: 'Página 12 · Fundamentos de redes' },
]

export default function ChatPanel() {
  const [text, setText] = useState('')
  const [chatMessages, setChatMessages] = useState(initialMessages)

  function send(event) {
    event.preventDefault()
    if (!text.trim()) return
    setChatMessages([...chatMessages, { role: 'student', text: text.trim(), time: 'agora' }])
    setText('')
  }

  return <section className="chat-panel">
    <div className="panel-heading"><div><small>SALA DE ESTUDO</small><h2>Converse com seu professor</h2></div><span className="available">● Disponível</span></div>
    <div className="active-document"><span>▤</span><div><b>fundamentos-de-redes.pdf</b><small>Documento ativo · 48 páginas</small></div><button>Trocar material</button></div>
    <div className="messages">{chatMessages.map((message, index) => <div className={`message ${message.role}`} key={`${message.time}-${index}`}><TeacherAvatar student={message.role === 'student'} /><div><div className="message-label"><b>{message.role === 'student' ? 'Você' : 'Professor Buddy'}</b><small>{message.time}</small></div><p>{message.text}</p>{message.source && <button className="source">↗ {message.source}</button>}</div></div>)}</div>
    <div className="suggestions"><small>Tente perguntar:</small><button onClick={() => setText('O que é uma rede LAN?')}>O que é uma rede LAN?</button><button onClick={() => setText('Resuma a página 12')}>Resuma a página 12</button></div>
    <form className="composer" onSubmit={send}><input value={text} onChange={(event) => setText(event.target.value)} placeholder="Digite sua dúvida sobre o material..." /><button aria-label="Enviar">➤</button></form>
    <small className="simulation">✦ As respostas estão simuladas neste protótipo visual.</small>
  </section>
}
