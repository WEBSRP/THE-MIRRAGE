import { StrictMode } from 'react';
import { createRoot } from 'react-dom/client';
import App from './App';
import './index.css';
import { AppProvider, ThemeProvider } from './state/AppState';
import { DesignProvider } from './design-system/DesignProvider';

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <ThemeProvider>
      <DesignProvider>
        <AppProvider>
          <App />
        </AppProvider>
      </DesignProvider>
    </ThemeProvider>
  </StrictMode>,
);
