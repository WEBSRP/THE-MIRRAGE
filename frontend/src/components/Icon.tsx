import { LogoMark } from './LogoMark';

export type IconName =
  | 'activity'
  | 'arrow-left'
  | 'arrow-right'
  | 'arrow-up-right'
  | 'bell'
  | 'check'
  | 'chevron-down'
  | 'chevron-left'
  | 'chevron-right'
  | 'circle'
  | 'columns'
  | 'cloud'
  | 'code'
  | 'command'
  | 'download'
  | 'external'
  | 'eye'
  | 'eye-off'
  | 'filter'
  | 'help'
  | 'home'
  | 'info'
  | 'key'
  | 'link'
  | 'loader'
  | 'lock'
  | 'logout'
  | 'menu'
  | 'moon'
  | 'network'
  | 'play'
  | 'plus'
  | 'refresh'
  | 'search'
  | 'send'
  | 'server'
  | 'settings'
  | 'shield'
  | 'sliders'
  | 'spark'
  | 'star'
  | 'stop'
  | 'sun'
  | 'terminal'
  | 'trash'
  | 'user'
  | 'vpn'
  | 'x';

const paths: Record<IconName, string> = {
  activity: 'M3 12h4l2-8 4 16 2-8h6',
  'arrow-left': 'M20 12H4m7-7-7 7 7 7',
  'arrow-right': 'M4 12h16m-7-7 7 7-7 7',
  'arrow-up-right': 'M5 19 19 5M9 5h10v10',
  bell: 'M18 8a6 6 0 0 0-12 0c0 7-3 7-3 9h18c0-2-3-2-3-9M10 21h4',
  check: 'm5 12 4 4L19 6',
  'chevron-down': 'm6 9 6 6 6-6',
  'chevron-left': 'm15 18-6-6 6-6',
  'chevron-right': 'm9 18 6-6-6-6',
  circle: 'M12 12h.01',
  columns: 'M4 5h6v14H4zM14 5h6v14h-6z',
  cloud: 'M7 18h10a4 4 0 0 0 .8-7.92A6 6 0 0 0 6.2 8.9 4.5 4.5 0 0 0 7 18Z',
  code: 'm8 9-4 3 4 3m8-6 4 3-4 3m-3-8-2 10',
  command: 'M18 4a3 3 0 1 0-3 3v10a3 3 0 1 0 3-3H8a3 3 0 1 0 3 3V7a3 3 0 1 0-3-3',
  download: 'M12 3v12m0 0 4-4m-4 4-4-4M5 21h14',
  external: 'M14 5h5v5m0-5-8 8M19 14v5H5V5h5',
  eye: 'M2.5 12s3.5-6 9.5-6 9.5 6 9.5 6-3.5 6-9.5 6-9.5-6-9.5-6Z M12 15a3 3 0 1 0 0-6 3 3 0 0 0 0 6Z',
  'eye-off': 'm3 3 18 18M10.6 10.6a2 2 0 0 0 2.8 2.8M9.9 5.2A10.8 10.8 0 0 1 12 5c6 0 9.5 7 9.5 7a17.8 17.8 0 0 1-3.1 3.9M6.1 6.1C3.6 7.7 2.5 12 2.5 12a17.6 17.6 0 0 0 6.2 5.5',
  filter: 'M4 5h16M7 12h10m-7 7h4',
  help: 'M9.1 9a3 3 0 1 1 5.6 1.5c-.7 1-2.7 1.6-2.7 3.5M12 18h.01M5 21h14a2 2 0 0 0 2-2V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2Z',
  home: 'm3 10 9-7 9 7v10a1 1 0 0 1-1 1H4a1 1 0 0 1-1-1V10Zm6 11v-6h6v6',
  info: 'M12 16v-4m0-4h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z',
  key: 'm15.5 8.5 5 5m-2-2-2 2m-1-1-2 2M14 10a4 4 0 1 1-5.7-3.6A4 4 0 0 1 14 10Z',
  link: 'M10 13a5 5 0 0 0 7.5.5l2-2a5 5 0 0 0-7-7l-1 1m2.5 5.5A5 5 0 0 0 6.5 10l-2 2a5 5 0 0 0 7 7l1-1',
  loader: 'M12 3a9 9 0 1 0 9 9',
  lock: 'M6 10h12v10H6zM9 10V7a3 3 0 0 1 6 0v3',
  logout: 'M10 17l5-5-5-5m5 5H3m9-9V4a2 2 0 0 1 2-2h6v20h-6a2 2 0 0 1-2-2v-1',
  menu: 'M4 7h16M4 12h16M4 17h16',
  moon: 'M20 15.3A8.5 8.5 0 0 1 8.7 4a8.5 8.5 0 1 0 11.3 11.3Z',
  network: 'M12 5v5m0 4v5M5 12h5m4 0h5M7 7l3 3m4 4 3 3m0-10-3 3m-4 4-3 3',
  play: 'm8 5 11 7-11 7V5Z',
  plus: 'M12 5v14M5 12h14',
  refresh: 'M20 11a8 8 0 1 0 1 5m-1-9v4h-4',
  search: 'm20 20-4.5-4.5M10.5 17a6.5 6.5 0 1 0 0-13 6.5 6.5 0 0 0 0 13Z',
  send: 'm22 2-7 20-4-9-9-4 20-7ZM22 2 11 13',
  server: 'M4 4h16v6H4zM4 14h16v6H4zM8 7h.01M8 17h.01',
  settings: 'M12 15.5a3.5 3.5 0 1 0 0-7 3.5 3.5 0 0 0 0 7Zm0-12v2m0 13v2M4.2 6.2l1.4 1.4m12.8 8.8 1.4 1.4M2 12h2m16 0h2M4.2 17.8l1.4-1.4m12.8-8.8 1.4-1.4',
  shield: 'M12 3 19 6v5c0 4.5-2.9 8.4-7 10-4.1-1.6-7-5.5-7-10V6l7-3Z',
  sliders: 'M4 6h16M4 12h16M4 18h16M8 4v4m8-4v4m-5 6v4m6-4v4',
  spark: 'm12 3 1.5 6.5L20 11l-6.5 1.5L12 19l-1.5-6.5L4 11l6.5-1.5L12 3Z',
  star: 'm12 3 2.8 5.7 6.2.9-4.5 4.4 1.1 6.2-5.6-3-5.6 3 1.1-6.2L3 9.6l6.2-.9L12 3Z',
  stop: 'M6 6h12v12H6z',
  sun: 'M12 3v2m0 14v2M5.6 5.6 7 7m10 10 1.4 1.4M3 12h2m14 0h2M5.6 18.4 7 17m10-10 1.4-1.4M16 12a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z',
  terminal: 'm5 7 5 5-5 5m7 0h7',
  trash: 'M5 7h14m-9 4v6m4-6v6M9 7V4h6v3m4 0-1 14H6L5 7',
  user: 'M20 21a8 8 0 0 0-16 0m12-13a4 4 0 1 1-8 0 4 4 0 0 1 8 0Z',
  vpn: 'M4 6h16v12H4zM8 18v3m8-3v3M7 10h.01M11 10h.01M15 10h.01',
  x: 'm6 6 12 12M18 6 6 18',
};

export function Icon({ name, size = 18, className = '' }: { name: IconName; size?: number; className?: string }) {
  return (
    <svg aria-hidden="true" className={`icon ${className}`} fill="none" height={size} stroke="currentColor" strokeLinecap="round" strokeLinejoin="round" strokeWidth="1.6" viewBox="0 0 24 24" width={size}>
      <path d={paths[name]} />
    </svg>
  );
}

export function Mark() {
  return <LogoMark />;
}

export function Wordmark({ link = true }: { link?: boolean }) {
  const content = <><Mark /><span>MIRRAGE</span></>;
  return link ? <a className="wordmark" href="/">{content}</a> : <span className="wordmark">{content}</span>;
}
