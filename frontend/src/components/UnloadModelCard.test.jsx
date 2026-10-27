import { afterEach, describe, expect, test, vi } from 'vitest'
import { cleanup, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import UnloadModelCard, { UNLOAD_CONFIRM_TEXT } from './UnloadModelCard'

afterEach(() => {
  cleanup()
})

function setup({ confirmUnload, unloadModel } = {}) {
  const user = userEvent.setup()
  const confirm = confirmUnload ?? vi.fn(() => true)
  const unload = unloadModel ?? vi.fn(async () => ({
    status: 'unloaded',
    model: 'gemma4:e4b',
    message: 'O Ollama aceitou o pedido para descarregar o modelo da memória.',
  }))
  render(<UnloadModelCard token="token-teste" confirmUnload={confirm} unloadModel={unload} />)
  return { user, confirm, unload }
}

describe('UnloadModelCard', () => {
  test('pede confirmação antes de chamar a API', async () => {
    const { user, confirm, unload } = setup({ confirmUnload: vi.fn(() => false) })

    await user.click(screen.getByRole('button', { name: 'Descarregar modelo da memória' }))

    expect(confirm).toHaveBeenCalledWith(UNLOAD_CONFIRM_TEXT)
    expect(unload).not.toHaveBeenCalled()
    expect(screen.queryByRole('status')).toBeNull()
  })

  test('mostra carregamento, bloqueia cliques repetidos e só confirma após sucesso', async () => {
    let finish
    const unload = vi.fn(
      () => new Promise((resolve) => {
        finish = () => resolve({
          status: 'unloaded',
          message: 'O Ollama aceitou o pedido para descarregar o modelo da memória.',
        })
      })
    )
    const { user } = setup({ unloadModel: unload })
    const button = screen.getByRole('button', { name: 'Descarregar modelo da memória' })

    const pendingClick = user.click(button)
    await vi.waitFor(() => expect(button.disabled).toBe(true))
    expect(button.textContent).toMatch(/Descarregando/)
    await user.click(button)
    expect(unload).toHaveBeenCalledTimes(1)

    finish()
    await pendingClick
    await vi.waitFor(() => {
      expect(screen.getByRole('status').textContent).toMatch(/aceitou o pedido/)
    })
    expect(button.disabled).toBe(false)
    expect(button.textContent).toBe('Descarregar modelo da memória')
  })

  test('mostra erro útil e não afirma sucesso quando a API falha', async () => {
    const { user } = setup({
      unloadModel: vi.fn(async () => {
        throw new Error('Há uma resposta da IA em andamento. Aguarde terminar antes de descarregar o modelo.')
      }),
    })

    await user.click(screen.getByRole('button', { name: 'Descarregar modelo da memória' }))

    expect(screen.getByRole('status').textContent).toMatch(/andamento/)
    expect(screen.getByRole('status').textContent).not.toMatch(/aceitou o pedido/)
  })
})
