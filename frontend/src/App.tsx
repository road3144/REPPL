import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { LandingPageSimple } from './pages/LandingPageSimple';
import { LandingPage } from './pages/LandingPage';
import { WorkspacePage } from './pages/WorkspacePage';
import { GlobalJobCompletionToast } from './components/GlobalJobCompletionToast';

export function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<LandingPageSimple />} />
        <Route path="/landing" element={<LandingPage />} />
        <Route path="/studio" element={<WorkspacePage />} />
      </Routes>
      <GlobalJobCompletionToast />
    </BrowserRouter>
  );
}
