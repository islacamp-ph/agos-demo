import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2 } from "lucide-react";
import http, { errMsg } from "@/lib/api";
import { useWorkspace } from "@/context/WorkspaceContext";
import { Wordmark } from "@/components/agos/ui";

export default function TourStart() {
  const { me, reloadMe, setWsId } = useWorkspace();
  const nav = useNavigate();
  const [error, setError] = useState(null);
  const started = useRef(false);

  useEffect(() => {
    if (!me || started.current) return;
    started.current = true;
    (async () => {
      try {
        let demo = me.workspaces.find((w) => w.is_demo && w.role === "owner");
        if (!demo) {
          const { data } = await http.post("/workspaces/demo");
          await reloadMe();
          demo = { id: data.id };
        }
        localStorage.removeItem(`agos_actas_${demo.id}`);
        setWsId(demo.id);
        nav("/app/overview?tour=1", { replace: true });
      } catch (e) {
        setError(errMsg(e));
      }
    })();
  }, [me, reloadMe, setWsId, nav]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-6 bg-[#f7f9fb]" data-testid="tour-start-page">
      <Wordmark />
      {error ? <p className="text-sm text-red-700" data-testid="tour-start-error">{error}</p> : (
        <div className="flex items-center gap-2 text-sm text-slate-600"><Loader2 className="h-4 w-4 animate-spin" />Preparing your private demo and investor tour…</div>
      )}
    </div>
  );
}
