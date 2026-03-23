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
    const url = new URL(API_BASE_URL);
    const protocol = url.protocol === 'https:' ? 'wss:' : 'ws:';
    return `${protocol}//${url.host}/ws/websocket`;
  }
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
  return `${protocol}//${window.location.host}/ws/websocket`;
}

let client: Client | null = null;

// 연결 후 복구해야 할 구독 목록
const pendingSubscriptions = new Map<string, (client: Client) => void>();

type Unsubscribe = () => void;

export function connectWs(): Client {
  if (client?.connected) return client;
  if (client?.active) return client;

  client = new Client({
    brokerURL: buildWsUrl(),
    reconnectDelay: 3000,
    heartbeatIncoming: 10000,
    heartbeatOutgoing: 10000,
    onConnect: () => {
      // 재연결 시 모든 pending 구독 복구
      for (const setup of pendingSubscriptions.values()) {
        setup(client!);
      }
    },
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
  const subKey = `job-${jobId}`;

  let sub: { unsubscribe: () => void } | null = null;

  const doSubscribe = (c: Client) => {
    sub = c.subscribe(destination, (msg: IMessage) => {
      onMessage(JSON.parse(msg.body) as WsJobProgress);
    });
  };

  // 구독 setup 함수를 등록 (재연결 시 복구용)
  pendingSubscriptions.set(subKey, doSubscribe);

  // 이미 연결되어 있으면 바로 구독
  if (stompClient.connected) {
    doSubscribe(stompClient);
  }

  return () => {
    sub?.unsubscribe();
    pendingSubscriptions.delete(subKey);
  };
}

export function disconnectWs(): void {
  pendingSubscriptions.clear();
  client?.deactivate();
  client = null;
}
