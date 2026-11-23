import { isConnected, requestAccess, signTransaction } from "@stellar/freighter-api";

export async function ensureFreighter() {
  const c = await isConnected();
  if (!c?.isConnected) throw new Error("Freighter wallet extension not detected. Install Freighter and switch it to Testnet.");
}

export async function connectFreighter() {
  await ensureFreighter();
  const { address, error } = await requestAccess();
  if (error || !address) throw new Error(error?.message || "Wallet access was not granted");
  return address;
}

export async function signWithFreighter(xdr, networkPassphrase, address) {
  // freighter-api's signTransaction never resolves when the extension is absent, so check first.
  const c = await isConnected();
  if (!c?.isConnected) throw new Error("Freighter wallet extension not detected. Install Freighter and switch it to Testnet.");
  const { signedTxXdr, error } = await signTransaction(xdr, { networkPassphrase, address });
  if (error || !signedTxXdr) throw new Error(error?.message || "Signing was cancelled");
  return signedTxXdr;
}
