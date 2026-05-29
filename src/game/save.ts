import { createInitialState } from './engine'
import type { GameState } from './types'

const saveKey = 'local-cultivation-save-v1'

export function loadGame(): GameState {
  const raw = localStorage.getItem(saveKey)

  if (!raw) {
    return createInitialState()
  }

  try {
    return JSON.parse(raw) as GameState
  } catch {
    return createInitialState()
  }
}

export function saveGame(state: GameState) {
  localStorage.setItem(saveKey, JSON.stringify(state))
}

export function clearGame() {
  localStorage.removeItem(saveKey)
}
