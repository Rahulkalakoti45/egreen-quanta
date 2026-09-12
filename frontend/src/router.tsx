import { createBrowserRouter } from "react-router-dom";

import { RequireAuth } from "@/components/RequireAuth";
import { AppShell } from "@/components/layout/AppShell";
import { AdminPage } from "@/features/admin/AdminPage";
import { AuditPage } from "@/features/audit/AuditPage";
import { LoginPage } from "@/features/auth/LoginPage";
import { CertificatesPage } from "@/features/certificates/CertificatesPage";
import { DashboardPage } from "@/features/dashboard/DashboardPage";
import { NotFoundPage } from "@/features/NotFoundPage";
import { QuantumPage } from "@/features/quantum/QuantumPage";
import { SignaturesPage } from "@/features/signatures/SignaturesPage";
import { ThreatsPage } from "@/features/threats/ThreatsPage";

export const router = createBrowserRouter([
  { path: "/login", element: <LoginPage /> },
  {
    path: "/",
    element: (
      <RequireAuth>
        <AppShell />
      </RequireAuth>
    ),
    children: [
      { index: true, element: <DashboardPage /> },
      { path: "signatures", element: <SignaturesPage /> },
      { path: "certificates", element: <CertificatesPage /> },
      { path: "threats", element: <ThreatsPage /> },
      { path: "quantum", element: <QuantumPage /> },
      { path: "audit", element: <AuditPage /> },
      { path: "admin", element: <AdminPage /> },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
]);
