export type LogTone = 'info' | 'good' | 'warn' | 'bad'

export type Realm = {
  id: string
  name: string
  stage: number
  requiredQi: number
  successRate: number
  lifeSpan: number
}

export type CultivationEvent = {
  id: string
  title: string
  text: string
  weight: number
  qi?: number
  spiritStones?: number
  hp?: number
  insight?: number
  tone: LogTone
}

export type GameLog = {
  id: string
  day: number
  text: string
  tone: LogTone
}

export type Player = {
  name: string
  age: number
  day: number
  realmId: string
  qi: number
  hp: number
  maxHp: number
  insight: number
  spiritStones: number
}

export type GameState = {
  player: Player
  logs: GameLog[]
}
