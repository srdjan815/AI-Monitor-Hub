import React from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { BrowserRouter } from "react-router-dom";
import { Toaster } from "react-hot-toast";
import App from "./App";
import { AuthProvider } from "./state/AuthContext";
import { PreferencesProvider } from "./state/PreferencesContext";
import { WorkspaceProvider } from "./state/WorkspaceContext";
import { installGlobalTooltipDismissal } from "./tooltipBehavior";

installGlobalTooltipDismissal();

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 20_000,
      retry: (count, error) => {
        const status = (error as { status?: number }).status;
        return count < 2 && status !== 401 && status !== 403;
      },
      refetchOnWindowFocus: false
    },
    mutations: { retry: false }
  }
});

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <PreferencesProvider>
          <AuthProvider>
            <WorkspaceProvider>
              <App />
              <Toaster
                position="bottom-right"
                toastOptions={{ duration: 4500 }}
              />
            </WorkspaceProvider>
          </AuthProvider>
        </PreferencesProvider>
      </BrowserRouter>
    </QueryClientProvider>
  </React.StrictMode>
);
