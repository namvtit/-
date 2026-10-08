import { type Connection } from "../api";

export function ConnectionStatus({ name, connection }: { name: string; connection: Connection }) {
  return (
    <div className="provider-status">
      <span>
        <strong>{name}</strong>{" "}
        <span className={`badge ${connection.status === "connected" ? "ready" : connection.status === "unreachable" ? "failed" : "neutral"}`}>
          {connection.status.replaceAll("_", " ")}
        </span>
      </span>
      <p className="help">{connection.detail}</p>
    </div>
  );
}
