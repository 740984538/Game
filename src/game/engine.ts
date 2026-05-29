import eventsData from '../data/events.json'
import realmsData from '../data/realms.json'
import type { CultivationEvent, GameLog, GameState, Realm } from './types'

export const realms = realmsData as Realm[]
export const cultivationEvents = eventsData as CultivationEvent[]

const logLimit = 12

export function createInitialState(name = '无名散修'): GameState {
  return {
    player: {
      name,
      age: 16,
      day: 1,
      realmId: realms[0].id,
      qi: 0,
      hp: 100,
      maxHp: 100,
      insight: 0,
      spiritStones: 12,
    },
    logs: [
      {
        id: crypto.randomUUID(),
        day: 1,
        text: '你在青梧山脚开辟一间简陋洞府，修行从此开始。',
        tone: 'info',
      },
    ],
  }
}

export function getRealm(state: GameState): Realm {
  return realms.find((realm) => realm.id === state.player.realmId) ?? realms[0]
}

export function getNextRealm(state: GameState): Realm | undefined {
  const current = getRealm(state)
  return realms.find((realm) => realm.stage === current.stage + 1)
}

export function cultivate(state: GameState): GameState {
  const event = pickWeightedEvent(cultivationEvents)
  const nextDay = state.player.day + 1
  const nextAge = 16 + Math.floor(nextDay / 36)
  const player = {
    ...state.player,
    day: nextDay,
    age: nextAge,
    qi: Math.max(0, state.player.qi + (event.qi ?? 0)),
    hp: clamp(state.player.hp + (event.hp ?? 0), 1, state.player.maxHp),
    insight: Math.max(0, state.player.insight + (event.insight ?? 0)),
    spiritStones: Math.max(0, state.player.spiritStones + (event.spiritStones ?? 0)),
  }

  return addLog(
    { ...state, player },
    `${event.title}：${event.text}`,
    event.tone,
  )
}

export function meditate(state: GameState): GameState {
  const gain = 10 + Math.floor(getRealm(state).stage * 3 + state.player.insight * 0.4)
  return addLog(
    {
      ...state,
      player: {
        ...state.player,
        day: state.player.day + 1,
        age: 16 + Math.floor((state.player.day + 1) / 36),
        qi: state.player.qi + gain,
      },
    },
    `静室吐纳一日，灵气增长 ${gain} 点。`,
    'good',
  )
}

export function heal(state: GameState): GameState {
  if (state.player.spiritStones < 5) {
    return addLog(state, '灵石不足，无法购买疗伤丹。', 'warn')
  }

  return addLog(
    {
      ...state,
      player: {
        ...state.player,
        hp: Math.min(state.player.maxHp, state.player.hp + 28),
        spiritStones: state.player.spiritStones - 5,
      },
    },
    '服下一枚温养丹，伤势明显好转。',
    'good',
  )
}

export function breakthrough(state: GameState): GameState {
  const currentRealm = getRealm(state)
  const nextRealm = getNextRealm(state)

  if (!nextRealm) {
    return addLog(state, '此界灵机已尽，你暂时触及了当前版本的修行尽头。', 'info')
  }

  if (state.player.qi < currentRealm.requiredQi) {
    return addLog(
      state,
      `灵气不足，还需 ${currentRealm.requiredQi - state.player.qi} 点才能尝试突破。`,
      'warn',
    )
  }

  const bonus = Math.min(0.22, state.player.insight * 0.01)
  const success = Math.random() < currentRealm.successRate + bonus

  if (success) {
    return addLog(
      {
        ...state,
        player: {
          ...state.player,
          realmId: nextRealm.id,
          qi: Math.floor(state.player.qi * 0.2),
          hp: state.player.maxHp,
          maxHp: state.player.maxHp + 18,
          insight: Math.max(0, state.player.insight - 2),
        },
      },
      `灵台一震，瓶颈破开！你踏入${nextRealm.name}。`,
      'good',
    )
  }

  return addLog(
    {
      ...state,
      player: {
        ...state.player,
        qi: Math.floor(state.player.qi * 0.55),
        hp: Math.max(1, state.player.hp - 24),
      },
    },
    '冲关失败，气海震荡，修为折损不少。',
    'bad',
  )
}

function pickWeightedEvent(events: CultivationEvent[]) {
  const total = events.reduce((sum, event) => sum + event.weight, 0)
  let roll = Math.random() * total

  for (const event of events) {
    roll -= event.weight
    if (roll <= 0) {
      return event
    }
  }

  return events[0]
}

function addLog(state: GameState, text: string, tone: GameLog['tone']): GameState {
  return {
    ...state,
    logs: [
      {
        id: crypto.randomUUID(),
        day: state.player.day,
        text,
        tone,
      },
      ...state.logs,
    ].slice(0, logLimit),
  }
}

function clamp(value: number, min: number, max: number) {
  return Math.min(max, Math.max(min, value))
}
