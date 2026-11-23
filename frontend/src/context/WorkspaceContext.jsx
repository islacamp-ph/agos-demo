import { createContext, useCallback, useContext, useEffect, useState } from "react";
import http, { wsState, errMsg } from "@/lib/api";

const Ctx = createContext(null);
export const useWorkspace = () => useContext(Ctx);

export function WorkspaceProvider({ children }) {
  const [me, setMe] = useState(null);
  const [info, setInfo] = useState(null);
  const [wsId, setWsIdState] = useState(null);
  const [error, setError] = useState(null);
  const [version, setVersion] = useState(0);

  const loadMe = useCallback(async () => {
    try {
      const { data } = await http.get("/me");
      setMe(data);
      const saved = localStorage.getItem("agos_ws");
      const pick = data.workspaces.find((w) => w.id === saved) || data.workspaces[0];
      if (pick) {
        wsState.wsId = pick.id;
        wsState.actAs = localStorage.getItem(`agos_actas_${pick.id}`) || null;
        setWsIdState(pick.id);
      }
      return data;
    } catch (e) {
      setError(errMsg(e));
      return null;
    }
  }, []);

  const loadInfo = useCallback(async () => {
    if (!wsState.wsId) return;
    try {
      const { data } = await http.get("/workspace");
      setInfo(data);
    } catch (e) {
      setError(errMsg(e));
    }
  }, []);

  useEffect(() => { loadMe(); }, [loadMe]);
  useEffect(() => { if (wsId) loadInfo(); }, [wsId, version, loadInfo]);

  const setWsId = (id) => {
    localStorage.setItem("agos_ws", id);
    wsState.wsId = id;
    wsState.actAs = localStorage.getItem(`agos_actas_${id}`) || null;
    setInfo(null);
    setWsIdState(id);
    setVersion((v) => v + 1);
  };

  const setActAs = (memberId) => {
    const value = memberId && memberId !== info?.real_member_id ? memberId : null;
    if (value) localStorage.setItem(`agos_actas_${wsId}`, value);
    else localStorage.removeItem(`agos_actas_${wsId}`);
    wsState.actAs = value;
    setInfo(null);
    setVersion((v) => v + 1);
  };

  const role = info?.role;
  const value = {
    me, info, wsId, error, role, setWsId, setActAs, reloadMe: loadMe, reloadInfo: loadInfo, version,
    bump: () => setVersion((v) => v + 1),
    isManager: role === "owner" || role === "finance_manager", isOwner: role === "owner",
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}
