import { useState } from 'react'
import { unloadModel as unloadModelRequest } from '../services/api'

export const UNLOAD_CONFIRM_TEXT =
  'Isso descarrega o modelo da memória do servidor para todos que compartilham este Ollama. Conversas, PDFs e questões não são apagados. A próxima pergunta pode carregar o modelo de novo. Continuar?'

export default function UnloadModelCard({
  token,
  unloadModel = unloadModelRequest,
  confirmUnload = (message) => window.confirm(message),
}) {
  const [busy, setBusy] = useState(false)
  const [status, setStatus] = useState('')
  const [tone, setTone] = useState('')

  async function unload() {
    if (busy) return
    setStatus('')
    setTone('')
    if (!confirmUnload(UNLOAD_CONFIRM_TEXT)) {
      return
    }
    setBusy(true)
    try {
      const response = await unloadModel(token)
      setTone('ok')
      setStatus(
        response?.message
        || 'O modelo foi descarregado da memória. A próxima pergunta pode carregá-lo de novo.'
      )
    } catch (error) {
      setTone('error')
      setStatus(error?.message || 'Não foi possível descarregar o modelo. Tente novamente em instantes.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="account-card">
      <h2>Professor virtual</h2>
      <p className="unload-note">
        Descarrega o Gemma 4 E4B da memória deste Ollama. O efeito é compartilhado.
        Não apaga o modelo, conversas ou arquivos, e não mede a RAM liberada.
      </p>
      <div className="account-actions">
        <button className="outline-button" type="button" onClick={unload} disabled={busy || !token}>
          {busy ? 'Descarregando…' : 'Descarregar modelo da memória'}
        </button>
      </div>
      {status && (
        <small className={`unload-status ${tone === 'error' ? 'error' : 'saved-message'}`} role="status">
          {status}
        </small>
      )}
    </div>
  )
}
