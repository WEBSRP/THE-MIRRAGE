import { SignalCore } from './visuals/SignalCore';
import { NetworkScene } from './visuals/NetworkScene';
import './visuals/visuals.css';

export function InteractiveSignalCore({ compact = false }: { compact?: boolean }) {
  return <SignalCore compact={compact} />;
}

export function InteractiveNetworkScene({ compact = false }: { compact?: boolean }) {
  return <NetworkScene compact={compact} />;
}

export function DesignStudioPreview() {
  return (
    <div className="mxv-studio-preview">
      <InteractiveSignalCore compact />
      <InteractiveNetworkScene compact />
    </div>
  );
}
