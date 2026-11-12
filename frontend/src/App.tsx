import { useAuth } from "./auth.tsx";
import { useRoute } from "./hooks.ts";
import { Layout } from "./components/Layout.tsx";
import { Spinner } from "./components/ui.tsx";
import { Login } from "./pages/Login.tsx";
import { Dashboard } from "./pages/Dashboard.tsx";
import { Documents } from "./pages/Documents.tsx";
import { Ask } from "./pages/Ask.tsx";
import { Graph } from "./pages/Graph.tsx";
import { People } from "./pages/People.tsx";
import { Audit } from "./pages/Audit.tsx";

export default function App() {
  const { user, loading } = useAuth();
  const route = useRoute();
  if (loading) return <div className="boot"><Spinner label="Restoring your session…" /></div>;
  if (!user) return <Login />;
  return (
    <Layout route={route}>
      {route === "/" && <Dashboard />}
      {route === "/ask" && <Ask />}
      {route === "/documents" && <Documents />}
      {route === "/graph" && <Graph />}
      {route === "/people" && <People />}
      {route === "/audit" && <Audit />}
    </Layout>
  );
}
