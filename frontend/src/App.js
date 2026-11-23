import { useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route, Navigate, Outlet } from "react-router-dom";
import { Show, SignIn, SignUp, useAuth } from "@clerk/react";
import ClerkAuthProvider from "@/components/auth/ClerkAuthProvider";
import { Toaster } from "@/components/ui/sonner";
import { setTokenGetter } from "@/lib/api";
import { WorkspaceProvider } from "@/context/WorkspaceContext";
import AppShell from "@/components/agos/AppShell";
import PublicLayout from "@/pages/public/PublicLayout";
import Landing from "@/pages/public/Landing";
import Roadmap from "@/pages/public/Roadmap";
import Waitlist from "@/pages/public/Waitlist";
import Privacy from "@/pages/public/Privacy";
import AuthPage from "@/pages/public/AuthPage";
import Onboarding from "@/pages/app/Onboarding";
import Overview from "@/pages/app/Overview";
import Expenses from "@/pages/app/Expenses";
import Budgets from "@/pages/app/Budgets";
import Approvals from "@/pages/app/Approvals";
import Cards from "@/pages/app/Cards";
import Payments from "@/pages/app/Payments";
import StellarPage from "@/pages/app/StellarPage";
import Reports from "@/pages/app/Reports";
import Team from "@/pages/app/Team";
import Settings from "@/pages/app/Settings";
import AdminPanel from "@/pages/app/AdminPanel";

function TokenBridge() {
  const { getToken } = useAuth();
  useEffect(() => { setTokenGetter(() => getToken()); }, [getToken]);
  return null;
}

function Protected() {
  return (
    <>
      <Show when="signed-in">
        <WorkspaceProvider><Outlet /></WorkspaceProvider>
      </Show>
      <Show when="signed-out"><Navigate to="/sign-in" replace /></Show>
    </>
  );
}

function App() {
  return (
    <BrowserRouter>
      <ClerkAuthProvider>
        <TokenBridge />
        <Toaster position="bottom-right" richColors />
        <Routes>
          <Route element={<PublicLayout />}>
            <Route path="/" element={<Landing />} />
            <Route path="/roadmap" element={<Roadmap />} />
            <Route path="/waitlist" element={<Waitlist />} />
            <Route path="/privacy" element={<Privacy />} />
          </Route>
          <Route path="/sign-in/*" element={<AuthPage><SignIn routing="path" path="/sign-in" signUpUrl="/sign-up" withSignUp /></AuthPage>} />
          <Route path="/sign-up/*" element={<AuthPage><SignUp routing="path" path="/sign-up" signInUrl="/sign-in" /></AuthPage>} />
          <Route element={<Protected />}>
            <Route path="/app/onboarding" element={<Onboarding />} />
            <Route path="/app" element={<AppShell />}>
              <Route index element={<Navigate to="/app/overview" replace />} />
              <Route path="overview" element={<Overview />} />
              <Route path="expenses" element={<Expenses />} />
              <Route path="budgets" element={<Budgets />} />
              <Route path="approvals" element={<Approvals />} />
              <Route path="cards" element={<Cards />} />
              <Route path="payments" element={<Payments />} />
              <Route path="stellar" element={<StellarPage />} />
              <Route path="reports" element={<Reports />} />
              <Route path="team" element={<Team />} />
              <Route path="settings" element={<Settings />} />
              <Route path="roadmap" element={<Roadmap inApp />} />
              <Route path="admin" element={<AdminPanel />} />
            </Route>
          </Route>
          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </ClerkAuthProvider>
    </BrowserRouter>
  );
}

export default App;
