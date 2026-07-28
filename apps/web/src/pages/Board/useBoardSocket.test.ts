import { act, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { setAccessToken } from "../../api/client";
import { useBoardSocket, type BoardEnvelope } from "./useBoardSocket";

class FakeWebSocket {
  static instances: FakeWebSocket[] = [];
  url: string;
  onopen: (() => void) | null = null;
  onmessage: ((message: MessageEvent<string>) => void) | null = null;
  onclose: (() => void) | null = null;
  closed = false;

  constructor(url: string) {
    this.url = url;
    FakeWebSocket.instances.push(this);
  }

  emitOpen(): void {
    this.onopen?.();
  }

  emitMessage(event: Partial<BoardEnvelope> & { stream: BoardEnvelope["stream"] }): void {
    this.onmessage?.({ data: JSON.stringify(event) } as MessageEvent<string>);
  }

  close(): void {
    this.closed = true;
    this.onclose?.();
  }
}

describe("useBoardSocket", () => {
  beforeEach(() => {
    vi.useFakeTimers();
    FakeWebSocket.instances = [];
    vi.stubGlobal("WebSocket", FakeWebSocket);
    setAccessToken("test-board-token");
  });

  afterEach(() => {
    vi.useRealTimers();
    vi.unstubAllGlobals();
    setAccessToken(null);
  });

  it("connects with the access token as a query param", () => {
    renderHook(() => useBoardSocket(() => {}));

    expect(FakeWebSocket.instances).toHaveLength(1);
    expect(FakeWebSocket.instances[0].url).toContain("token=test-board-token");
    expect(FakeWebSocket.instances[0].url).toContain("/ws/board/");
  });

  it("reports connected once the socket opens, and applies incoming events", () => {
    const onEvent = vi.fn();
    const { result } = renderHook(() => useBoardSocket(onEvent));

    const socket = FakeWebSocket.instances[0];
    act(() => socket.emitOpen());
    expect(result.current.connected).toBe(true);

    act(() =>
      socket.emitMessage({
        event_type: "order.ready",
        stream: "events:order",
        stream_id: "1700000000000-0",
      }),
    );

    expect(onEvent).toHaveBeenCalledWith(
      expect.objectContaining({ event_type: "order.ready", stream_id: "1700000000000-0" }),
    );
  });

  it("tracks last_event_id independently per stream and resends them on reconnect", () => {
    renderHook(() => useBoardSocket(() => {}));
    const first = FakeWebSocket.instances[0];

    act(() => {
      first.emitMessage({ stream: "events:order", stream_id: "1-0" });
      first.emitMessage({ stream: "events:oven", stream_id: "2-0" });
    });

    act(() => {
      first.close();
      vi.advanceTimersByTime(2000);
    });

    expect(FakeWebSocket.instances).toHaveLength(2);
    const second = FakeWebSocket.instances[1];
    expect(second.url).toContain("last_event_id_order=1-0");
    expect(second.url).toContain("last_event_id_oven=2-0");
    expect(second.url).not.toContain("last_event_id_courier=");
  });

  it("stops reconnecting after unmount", () => {
    const { unmount } = renderHook(() => useBoardSocket(() => {}));
    const socket = FakeWebSocket.instances[0];

    unmount();
    act(() => {
      socket.close();
      vi.advanceTimersByTime(5000);
    });

    expect(FakeWebSocket.instances).toHaveLength(1);
  });
});
