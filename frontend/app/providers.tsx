"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({ defaultOptions: {
    queries: { staleTime: 0, retry: false, refetchOnWindowFocus: true, networkMode: "always" },
    mutations: { retry: false, networkMode: "always" },
  } }));
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
