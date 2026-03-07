import { BrowserRouter, Routes, Route } from "react-router-dom";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { Layout } from "./components/Layout";
import { Dashboard } from "./pages/Dashboard";
import { Compliance } from "./pages/Compliance";
import { Servers } from "./pages/Servers";
import { RegionDetail } from "./pages/RegionDetail";
import { HostDetail } from "./pages/HostDetail";

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 2,
      staleTime: 10_000,
      refetchOnWindowFocus: true,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="compliance" element={<Compliance />} />
            <Route path="servers" element={<Servers />} />
            <Route path="region/:region" element={<RegionDetail />} />
            <Route path="host/:serverId" element={<HostDetail />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
