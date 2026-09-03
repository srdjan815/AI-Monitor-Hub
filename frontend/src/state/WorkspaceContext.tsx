import {
  createContext,
  useContext,
  useMemo,
  useState,
  type ReactNode
} from "react";

interface Workspace {
  supplierId: string;
  sourceId: string;
  setSupplierId: (value: string) => void;
  setSourceId: (value: string) => void;
}

const WorkspaceContext = createContext<Workspace | null>(null);

export function WorkspaceProvider({ children }: { children: ReactNode }) {
  const [supplierId, setSupplier] = useState(
    localStorage.getItem("amh.supplier-id") ?? ""
  );
  const [sourceId, setSource] = useState(
    localStorage.getItem("amh.source-id") ?? ""
  );
  const value = useMemo(
    () => ({
      supplierId,
      sourceId,
      setSupplierId: (next: string) => {
        if (next) localStorage.setItem("amh.supplier-id", next);
        else localStorage.removeItem("amh.supplier-id");
        setSupplier(next);
        if (next !== supplierId) {
          localStorage.removeItem("amh.source-id");
          setSource("");
        }
      },
      setSourceId: (next: string) => {
        if (next) localStorage.setItem("amh.source-id", next);
        else localStorage.removeItem("amh.source-id");
        setSource(next);
      }
    }),
    [sourceId, supplierId]
  );
  return (
    <WorkspaceContext.Provider value={value}>
      {children}
    </WorkspaceContext.Provider>
  );
}

export function useWorkspace(): Workspace {
  const value = useContext(WorkspaceContext);
  if (!value) throw new Error("WorkspaceProvider nedostaje");
  return value;
}
