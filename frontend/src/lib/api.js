import { useCallback, useEffect, useState } from "react";
import axios from "axios";

export const API = `${process.env.REACT_APP_BACKEND_URL}/api`;
export const wsState = { wsId: null, actAs: null };
let tokenGetter = null;
export const setTokenGetter = (fn) => { tokenGetter = fn; };

const http = axios.create({ baseURL: API, timeout: 60000 });
http.interceptors.request.use(async (cfg) => {
  const t = tokenGetter ? await tokenGetter() : null;
  if (t) cfg.headers.Authorization = `Bearer ${t}`;
  if (wsState.wsId) cfg.headers["X-Workspace-Id"] = wsState.wsId;
  if (wsState.actAs) cfg.headers["X-Act-As"] = wsState.actAs;
  return cfg;
});
export default http;

export const errMsg = (e) => {
  const d = e?.response?.data?.detail;
  if (Array.isArray(d)) return d.map((x) => x.msg.replace("Value error, ", "")).join(", ");
  return d || e?.message || "Request failed";
};

export async function downloadFile(path, params, filename) {
  const res = await http.get(path, { params, responseType: "blob" });
  const url = URL.createObjectURL(res.data);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

export function useData(path, params) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(true);
  const key = JSON.stringify(params || {});
  const reload = useCallback(async () => {
    if (!path) return;
    setLoading(true);
    try {
      const res = await http.get(path, { params: JSON.parse(key) });
      setData(res.data);
      setError(null);
    } catch (e) {
      setError(errMsg(e));
    } finally {
      setLoading(false);
    }
  }, [path, key]);
  useEffect(() => { reload(); }, [reload]);
  return { data, error, loading, reload, setData };
}
