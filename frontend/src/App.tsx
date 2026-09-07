import { Routes, Route } from 'react-router-dom';
import { MainLayout } from './layouts/MainLayout';
import { HomePage } from './pages/HomePage';
import { AboutPage } from './pages/AboutPage';
import { ArchivePage } from './pages/ArchivePage';
import { ExplorePage } from './pages/ExplorePage';
import { EnterPage } from './pages/EnterPage';
import { SessionPage } from './pages/SessionPage';

function App() {
  return (
    <MainLayout>
      <Routes>
        <Route path="/" element={<HomePage />} />
        <Route path="/about" element={<AboutPage />} />
        <Route path="/archive" element={<ArchivePage />} />
        <Route path="/explore" element={<ExplorePage />} />
        <Route path="/enter" element={<EnterPage />} />
        <Route path="/session" element={<SessionPage />} />

        {/* Hidden route — a subtle easter egg for curious inspectors */}
        <Route
          path="/passage"
          element={
            <main className="min-h-screen flex items-center justify-center px-6">
              <div className="text-center animate-fade-in" style={{ animationDuration: '3s' }}>
                <p className="text-[var(--gold-muted)] text-sm tracking-widest uppercase mb-4 font-semibold">
                  YOU FOUND THE PASSAGE
                </p>
                <p className="text-[var(--sandstone)]/70 text-base max-w-md mx-auto leading-relaxed">
                  "The monument is only the surface. When the reflection disappears, look where the water used to be."
                </p>
                <p className="text-[var(--sandstone)]/40 text-xs tracking-wider mt-8 font-mono">
                  TARGET GATEWAY: 10.42.0.0/24 — ACTIVE THRESHOLD
                </p>
              </div>
            </main>
          }
        />

        {/* Thematic 404 Page */}
        <Route
          path="*"
          element={
            <main className="min-h-screen flex items-center justify-center px-6">
              <div className="text-center">
                <h1 className="font-display text-6xl text-[var(--sandstone-light)]/40 mb-4">
                  404
                </h1>
                <p className="text-base text-[var(--sandstone)]/70 tracking-wide">
                  This path leads only to wind and sand.
                </p>
              </div>
            </main>
          }
        />
      </Routes>
    </MainLayout>
  );
}

export default App;
