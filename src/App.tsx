import { useEffect, useMemo, useState } from 'react'
import './App.css'
import {
  breakthrough,
  createInitialState,
  cultivate,
  getNextRealm,
  getRealm,
  heal,
  meditate,
} from './game/engine'
import { clearGame, loadGame, saveGame } from './game/save'
import type { GameState } from './game/types'

function App() {
  const [state, setState] = useState<GameState>(() => loadGame())
  const [name, setName] = useState(state.player.name)
  const realm = getRealm(state)
  const nextRealm = getNextRealm(state)
  const qiPercent = Math.min(100, Math.round((state.player.qi / realm.requiredQi) * 100))
  const hpPercent = Math.round((state.player.hp / state.player.maxHp) * 100)
  const successRate = useMemo(() => {
    const rate = Math.min(0.95, realm.successRate + state.player.insight * 0.01)
    return Math.round(rate * 100)
  }, [realm.successRate, state.player.insight])

  useEffect(() => {
    saveGame(state)
  }, [state])

  function rename() {
    const nextName = name.trim() || '无名散修'
    setState((current) => ({
      ...current,
      player: { ...current.player, name: nextName },
    }))
  }

  function restart() {
    clearGame()
    const fresh = createInitialState(name.trim() || '无名散修')
    setState(fresh)
  }

  return (
    <main className="game-shell">
      <section className="hero-card reveal">
        <div>
          <p className="eyebrow">Local text idle RPG</p>
          <h1>青梧修真录</h1>
          <p className="intro">
            一卷洞府手札，一盏残灯清修。无需后端和数据库，所有功法、事件与存档都在本地流转。
          </p>
        </div>
        <div className="name-card">
          <label htmlFor="name">道号</label>
          <div className="name-row">
            <input
              id="name"
              value={name}
              onChange={(event) => setName(event.target.value)}
              onBlur={rename}
              maxLength={8}
            />
            <button type="button" onClick={rename}>刻名</button>
          </div>
        </div>
      </section>

      <section className="dashboard reveal delay-one">
        <article className="panel profile-panel">
          <div className="avatar-mark">{state.player.name.slice(0, 1)}</div>
          <div>
            <p className="muted">{state.player.age} 岁 · 第 {state.player.day} 日</p>
            <h2>{state.player.name}</h2>
            <p className="realm">{realm.name}</p>
          </div>
        </article>

        <article className="panel stats-panel">
          <Stat label="气血" value={`${state.player.hp}/${state.player.maxHp}`} percent={hpPercent} />
          <Stat label="灵气" value={`${state.player.qi}/${realm.requiredQi}`} percent={qiPercent} />
          <div className="resource-grid">
            <Resource label="悟性" value={state.player.insight} />
            <Resource label="灵石" value={state.player.spiritStones} />
            <Resource label="破境率" value={`${successRate}%`} />
          </div>
        </article>

        <article className="panel action-panel">
          <button type="button" onClick={() => setState((current) => meditate(current))}>
            静室吐纳
          </button>
          <button type="button" onClick={() => setState((current) => cultivate(current))}>
            外出历练
          </button>
          <button type="button" onClick={() => setState((current) => breakthrough(current))}>
            尝试突破
          </button>
          <button type="button" className="secondary" onClick={() => setState((current) => heal(current))}>
            购丹疗伤
          </button>
          <button type="button" className="ghost" onClick={restart}>
            重开一世
          </button>
        </article>
      </section>

      <section className="lower-grid reveal delay-two">
        <article className="panel realm-panel">
          <p className="eyebrow">Next bottleneck</p>
          <h2>{nextRealm ? nextRealm.name : '飞升未开'}</h2>
          <p>
            当前境界需要积蓄 {realm.requiredQi} 点灵气后冲关。悟性越高，突破时越容易避开岔路。
          </p>
        </article>

        <article className="panel log-panel">
          <div className="panel-title">
            <p className="eyebrow">Cave notes</p>
            <h2>修行札记</h2>
          </div>
          <div className="logs">
            {state.logs.map((log) => (
              <div className={`log-line ${log.tone}`} key={log.id}>
                <span>第 {log.day} 日</span>
                <p>{log.text}</p>
              </div>
            ))}
          </div>
        </article>
      </section>
    </main>
  )
}

function Stat({ label, value, percent }: { label: string; value: string; percent: number }) {
  return (
    <div className="stat-block">
      <div className="stat-label">
        <span>{label}</span>
        <strong>{value}</strong>
      </div>
      <div className="bar">
        <span style={{ width: `${percent}%` }} />
      </div>
    </div>
  )
}

function Resource({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="resource">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  )
}

export default App
