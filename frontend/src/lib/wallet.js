import { isConnected, requestAccess, signTransaction } from "@stellar/freighter-api";

export async function connectFreighter() {
  const c = await isConnected();
  if (!c?.isConnected) throw new Error("Freighter wallet extension not detected. Install Freighter and switch it to Testnet.");
  const { address, error } = await requestAccess();
  if (error || !address) throw new Error(error?.message || "Wallet access was not granted");
  return address;
}

export async function signWithFreighter(xdr, networkPassphrase, address) {
  const { signedTxXdr, error } = await signTransaction(xdr, { networkPassphrase, address });
  if (error || !signedTxXdr) throw new Error(error?.message || "Signing was cancelled");
  return signedTxXdr;
}
