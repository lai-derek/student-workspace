import { useEffect, useState } from "react";
import { Navigate, NavLink, Route, Routes } from "react-router";
import { api, type Section } from "./api";
import { ErrorNote } from "./kit";
import Applications from "./pages/Applications";
import Home from "./pages/Home";
import InfoPage from "./pages/InfoPage";
import Studio from "./pages/Studio";
import WorkspaceView from "./pages/WorkspaceView";

export default function App() {
  const [sections, setSections] = useState<Section[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.sections().then(setSections, (e: Error) => setError(e.message));
  }, []);

  const has = (id: string) => sections.some((s) => s.id === id);

  return (
    <div className="layout">
      <nav className="nav" aria-label="Sections">
        <div className="nav-title">Student Workspace</div>
        {sections.map((s) => (
          <NavLink key={s.id} to={s.path}>
            {s.label}
          </NavLink>
        ))}
      </nav>
      <main className="main">
        <ErrorNote error={error} />
        <Routes>
          <Route path="/" element={<Navigate to="/home" replace />} />
          <Route path="/home" element={<Home />} />
          <Route path="/applications" element={<Applications />} />
          <Route path="/applications/:versionId" element={<Studio />} />
          <Route path="/workspace" element={<WorkspaceView />} />
          {has("opportunities") && (
            <Route
              path="/opportunities"
              element={
                <InfoPage title="Opportunities">
                  On Windows, double-click <b>Open Dashboard.cmd</b> in your workspace folder to review leads and
                  track applications.
                </InfoPage>
              }
            />
          )}
          {has("courses") && (
            <Route
              path="/courses"
              element={
                <InfoPage title="Courses">
                  Open your workspace folder in your AI agent and ask it to plan your next term. Academic Planning
                  saves your planner and advising files in <code>artifacts/academic-planning/</code>.
                </InfoPage>
              }
            />
          )}
          <Route path="*" element={<InfoPage title="Page not found">Choose a section from the sidebar.</InfoPage>} />
        </Routes>
      </main>
    </div>
  );
}
