import { useEffect, useMemo, useState, type FormEvent } from 'react';
import { Link } from 'react-router-dom';
import { Icon } from '../components/Icon';
import { Badge, Button, Card, ConfirmDialog, EmptyState, ProgressBar, StatusBadge } from '../components/ui';
import { useApp } from '../state/AppState';

type SessionFilter = 'all' | 'active' | 'history';

export function SessionsPage() {
  const { sessions, challenges, startSession, stopSession, reconnectSession, appendTerminalOutput } = useApp();
  const [filter, setFilter] = useState<SessionFilter>('all');
  const [selectedId, setSelectedId] = useState(sessions.find((session) => ['starting', 'ready'].includes(session.status))?.id ?? sessions[0]?.id ?? null);
  const [startChallenge, setStartChallenge] = useState(challenges[0]?.id ?? '');
  const [startBusy, setStartBusy] = useState(false);
  const [stopBusy, setStopBusy] = useState(false);
  const [stopTarget, setStopTarget] = useState<string | null>(null);
  const [command, setCommand] = useState('');
  const [notice, setNotice] = useState('');
  const visible = useMemo(() => sessions.filter((session) => filter === 'all' ? true : filter === 'active' ? ['starting', 'ready', 'stopping'].includes(session.status) : ['stopped', 'expired', 'error'].includes(session.status)), [filter, sessions]);
  const selected = sessions.find((session) => session.id === selectedId) ?? visible[0];
  const active = sessions.some((session) => ['starting', 'ready'].includes(session.status));

  useEffect(() => { if (selected && selected.id !== selectedId) setSelectedId(selected.id); }, [selected, selectedId]);

  const handleStart = async (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); setNotice(''); setStartBusy(true); const result = await startSession(startChallenge); setStartBusy(false); setNotice(result.ok ? 'Session provisioning started. Select it below to watch the simulated lifecycle.' : result.message ?? 'Unable to start a session.'); };
  const confirmStop = async () => { if (!stopTarget) return; setStopBusy(true); const result = await stopSession(stopTarget); setStopBusy(false); setStopTarget(null); setNotice(result.ok ? 'Session stopped and moved to history.' : result.message ?? 'Unable to stop session.'); };
  const handleReconnect = async () => { if (!selected) return; setNotice(''); const result = await reconnectSession(selected.id); setNotice(result.ok ? 'A fresh simulated environment is provisioning.' : result.message ?? 'Unable to reconnect.'); };
  const submitCommand = (event: FormEvent<HTMLFormElement>) => { event.preventDefault(); if (!selected) return; appendTerminalOutput(selected.id, command); setCommand(''); };

  return <div className="platform-page sessions-page"><div className="platform-page-header"><div><span className="platform-eyebrow">03 / isolated environments</span><h1>Sessions</h1><p>Start a private lab, inspect its simulated terminal, and keep the lifecycle visible from provision to shutdown.</p></div><Badge tone="orange" dot>All environments simulated</Badge></div>
    <div className="session-start-bar"><form onSubmit={handleStart}><label htmlFor="session-target">Start a new environment</label><select disabled={active || startBusy} id="session-target" onChange={(event) => setStartChallenge(event.target.value)} value={startChallenge}>{challenges.map((challenge) => <option key={challenge.id} value={challenge.id}>{challenge.title} · {challenge.category}</option>)}</select><Button disabled={active} loading={startBusy} type="submit" variant="primary" icon="plus">Start session</Button></form><div className="session-start-note"><Icon name="info" size={15} /><span>One active lab at a time in the demo. Startup takes about five seconds.</span></div></div>
    <div className="session-tabs" role="tablist">{(['all', 'active', 'history'] as SessionFilter[]).map((item) => <button aria-selected={filter === item} className={filter === item ? 'is-active' : ''} key={item} onClick={() => setFilter(item)} role="tab" type="button">{item === 'all' ? 'All sessions' : item === 'active' ? 'Active now' : 'History'} <span>{item === 'all' ? sessions.length : item === 'active' ? sessions.filter((session) => ['starting', 'ready', 'stopping'].includes(session.status)).length : sessions.filter((session) => ['stopped', 'expired', 'error'].includes(session.status)).length}</span></button>)}</div>
    {notice ? <div className="platform-inline-notice"><Icon name="activity" size={15} /> {notice}</div> : null}
    <div className="sessions-layout"><div className="session-list">{visible.length ? visible.map((session) => <SessionListItem isSelected={session.id === selected?.id} key={session.id} onSelect={() => setSelectedId(session.id)} session={session} />) : <Card><EmptyState icon="server" title="No sessions here" message={filter === 'active' ? 'Start an environment to see it move through the lifecycle.' : 'Stopped and expired environments will stay here for inspection.'} /></Card>}</div><div className="session-inspector">{selected ? <SessionInspector command={command} onCommandChange={setCommand} onReconnect={handleReconnect} onSubmitCommand={submitCommand} onStop={() => setStopTarget(selected.id)} session={selected} /> : <Card><EmptyState icon="terminal" title="Select an environment" message="Choose a session from the list to inspect its simulated terminal." /></Card>}</div></div>
    <ConfirmDialog confirmLabel="Stop environment" danger message="This will end the simulated lab and move it into session history. Any active terminal state will be retained as mock output." onCancel={() => setStopTarget(null)} onConfirm={confirmStop} open={Boolean(stopTarget)} title="Stop this session?" loading={stopBusy} />
  </div>;
}

function SessionListItem({ session, isSelected, onSelect }: { session: ReturnType<typeof useApp>['sessions'][number]; isSelected: boolean; onSelect: () => void }) {
  return <button className={`session-list-item ${isSelected ? 'is-selected' : ''}`} onClick={onSelect} type="button"><span className="session-list-icon"><Icon name={session.status === 'ready' || session.status === 'starting' ? 'server' : 'terminal'} size={17} /></span><span className="session-list-copy"><strong>{session.title}</strong><small>{session.target} · {session.ip}</small><span className="session-list-meta"><StatusBadge status={session.status} /><time>{session.startedAt}</time></span></span><Icon name="chevron-right" size={15} /></button>;
}

function SessionInspector({ session, onStop, onReconnect, command, onCommandChange, onSubmitCommand }: { session: ReturnType<typeof useApp>['sessions'][number]; onStop: () => void; onReconnect: () => void; command: string; onCommandChange: (value: string) => void; onSubmitCommand: (event: FormEvent<HTMLFormElement>) => void }) {
  const remaining = useRemaining(session.expiresAt, session.status === 'ready');
  const isActive = ['starting', 'ready'].includes(session.status);
  return <Card className="session-inspector-card" padding="none"><div className="session-inspector-header"><div><span className="platform-card-kicker">Environment / simulated</span><h2>{session.title}</h2><p>{session.target} · {session.ip}</p></div><div className="session-inspector-actions">{isActive ? <Button onClick={onStop} size="small" variant="danger" icon="stop">Stop</Button> : <Button onClick={onReconnect} size="small" variant="secondary" icon="refresh">Reconnect</Button>}</div></div><div className="session-telemetry"><span><small>Status</small><strong><StatusBadge status={session.status} /></strong></span><span><small>Started</small><strong>{session.startedAt}</strong></span><span><small>Time remaining</small><strong>{session.status === 'ready' ? remaining : session.status === 'starting' ? 'Provisioning' : '—'}</strong></span><span><small>Target IP</small><strong>{session.ip}</strong></span></div>{session.status === 'starting' ? <div className="session-starting"><span className="session-spinner"><Icon className="ui-spin" name="loader" size={22} /></span><div><h3>Building the observation layer.</h3><p>Allocating an isolated network and loading mock telemetry.</p></div><ProgressBar label="Startup progress" value={session.progress} tone="blue" /></div> : <div className="terminal-panel"><div className="terminal-header"><span><i /> <i /> <i /></span><span>terminal / read-only simulation</span><Badge tone="orange">No execution</Badge></div><div aria-label="Simulated terminal output" className="terminal-output">{session.output.map((line, index) => <div className={index === 0 ? 'terminal-muted' : ''} key={`${line}-${index}`}><span className="terminal-prompt">{index > 0 ? '›' : '#'}</span>{line}</div>)}</div>{session.status === 'ready' ? <form className="terminal-command" onSubmit={onSubmitCommand}><span>simulated@mirrage:~$</span><input aria-label="Simulated terminal command" autoComplete="off" onChange={(event) => onCommandChange(event.target.value)} placeholder="type help to see available commands" value={command} /><button aria-label="Send simulated command" type="submit"><Icon name="send" size={15} /></button></form> : <div className="terminal-closed"><Icon name="info" size={14} /> This environment is not active. Reconnect to open a fresh simulation.</div>}</div>}<div className="session-inspector-foot"><span><Icon name="info" size={13} /> Terminal output is mock data. No command runs on your machine or a remote server.</span><Link className="inline-link" to={`/challenges/${relatedChallengeId(session.title)}`}>Open related target <Icon name="arrow-up-right" size={14} /></Link></div></Card>;
}

function relatedChallengeId(title: string) {
  const ids: Record<string, string> = { 'Ghost in the Subnet': 'ghost-subnet', 'The Quiet Proxy': 'quiet-proxy', 'Glasshouse Protocol': 'glasshouse-protocol', Afterimage: 'afterimage', 'Paper Cipher': 'paper-cipher', 'Warm Cache': 'warm-cache' };
  return ids[title] ?? 'quiet-proxy';
}

function useRemaining(expiresAt: number | null, active: boolean) {
  const [now, setNow] = useState(Date.now());
  useEffect(() => { if (!active) return undefined; const timer = window.setInterval(() => setNow(Date.now()), 1000); return () => window.clearInterval(timer); }, [active]);
  if (!active || !expiresAt) return '—';
  const seconds = Math.max(0, Math.floor((expiresAt - now) / 1000));
  return `${Math.floor(seconds / 60).toString().padStart(2, '0')}:${(seconds % 60).toString().padStart(2, '0')}`;
}
