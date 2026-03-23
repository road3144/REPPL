import { Client, IMessage } from '@stomp/stompjs';

export type WsJobProgress = {
  jobId: string;
  status: string;
  progress: number;
  message: string;
  stage?: string;
  previewKeys?: string[];
};

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? '';

function buildWsUrl(): string {
  if (API_BASE_URL) {
    // 절대 URL인 경우 (https://domain.com → wss://domain.com/ws/websocket)
    const url = new URL(API_BASE_URL);
    const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${url.host}/ws/websocket`;
  }
  // 상대 경로 (Vite proxy 또는 같은 도메인)
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/websocket`;
}

let client: Client | null = null;

type Unsubscribe = () => void;

export function connectWs(): Client {
  if (client?.connected) return client;

  client = new Client({
    brokerURL: buildWsUrl(),
    reconnectDelay: 3000,
    heartbeatIncoming: 10000,
    heartbeatOutgoing: 10000,
  });

  client.activate();
  return client;
}

export function subscribeJobProgress(
  jobId: string,
  onMessage: (data: WsJobProgress) => void,
): Unsubscribe {
  const stompClient = connectWs();

  const destination = `/topic/jobs/${jobId}`;

  // 이미 연결되어 있으면 바로 구독
  if (stompClient.connected) {
    const sub = stompClient.subscribe(destination, (msg: IMessage) => {
      onMessage(JSON.parse(msg.body) as WsJobProgress);
    });
    return () => sub.unsubscribe();
  }

  // 아직 연결 중이면 onConnect에서 구독
  let subId: { unsubscribe: () => void } | null = null;
  const prevOnConnect = stompClient.onConnect;

  stompClient.onConnect = (frame) => {
    prevOnConnect?.(frame);
    subId = stompClient.subscribe(destination, (msg: IMessage) => {
      onMessage(JSON.parse(msg.body) as WsJobProgress);
    });
  };

  return () => {
    subId?.unsubscribe();
  };
}

export function disconnectWs(): void {
  client?.deactivate();
  client = null;
}
