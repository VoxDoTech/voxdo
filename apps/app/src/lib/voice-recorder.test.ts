import { afterEach, beforeEach, expect, mock, test } from "bun:test";
import { VoiceRecorder } from "./voice-recorder";

const originalRecorder = globalThis.MediaRecorder;
const originalReader = globalThis.FileReader;
const originalMediaDevices = Object.getOwnPropertyDescriptor(
  navigator,
  "mediaDevices",
);
const stopTrack = mock(() => {});
let failStart = false;
let failStop = false;
let failRead = false;
let instance: FakeRecorder;
class FakeRecorder {
  static isTypeSupported() {
    return true;
  }
  state = "inactive";
  mimeType = "audio/webm";
  ondataavailable: ((event: { data: Blob }) => void) | null = null;
  onstop: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public stream: MediaStream) {
    instance = this;
  }
  start() {
    if (failStart) throw new Error("start failed");
    this.state = "recording";
  }
  stop() {
    if (failStop) throw new Error("stop failed");
    if (this.state === "inactive") throw new Error("inactive");
    this.state = "inactive";
    queueMicrotask(() => {
      this.ondataavailable?.({ data: new Blob(["audio"]) });
      this.onstop?.();
    });
  }
}
beforeEach(() => {
  failStart = failStop = failRead = false;
  stopTrack.mockClear();
  Object.defineProperty(navigator, "mediaDevices", {
    configurable: true,
    value: {
      getUserMedia: async () => ({ getTracks: () => [{ stop: stopTrack }] }),
    },
  });
  globalThis.MediaRecorder = FakeRecorder as unknown as typeof MediaRecorder;
  globalThis.FileReader = class {
    result = "data:audio/webm;base64,YXVkaW8=";
    error = new Error("read failed");
    onload: (() => void) | null = null;
    onerror: (() => void) | null = null;
    readAsDataURL() {
      queueMicrotask(() => (failRead ? this.onerror?.() : this.onload?.()));
    }
  } as unknown as typeof FileReader;
});
afterEach(() => {
  globalThis.MediaRecorder = originalRecorder;
  globalThis.FileReader = originalReader;
  if (originalMediaDevices)
    Object.defineProperty(navigator, "mediaDevices", originalMediaDevices);
  else Reflect.deleteProperty(navigator, "mediaDevices");
});
test("start failure releases microphone and permits retry", async () => {
  const recorder = new VoiceRecorder();
  failStart = true;
  await expect(recorder.start()).rejects.toThrow("start failed");
  expect(stopTrack).toHaveBeenCalled();
  failStart = false;
  await recorder.start();
  expect((await recorder.stop()).base64).toBe("YXVkaW8=");
});
test("conversion failure rejects stop and releases microphone", async () => {
  const recorder = new VoiceRecorder();
  await recorder.start();
  failRead = true;
  await expect(recorder.stop()).rejects.toThrow("read failed");
  expect(stopTrack).toHaveBeenCalled();
});
test("inactive recorder is finalized without calling stop again", async () => {
  const recorder = new VoiceRecorder();
  await recorder.start();
  instance.state = "inactive";
  await expect(recorder.stop()).resolves.toMatchObject({
    mimeType: "audio/webm",
  });
  expect(stopTrack).toHaveBeenCalled();
});
test("synchronous stop failure cleans up and permits retry", async () => {
  const recorder = new VoiceRecorder();
  await recorder.start();
  failStop = true;
  await expect(recorder.stop()).rejects.toThrow("stop failed");
  expect(stopTrack).toHaveBeenCalled();
  failStop = false;
  await recorder.start();
  await recorder.stop();
});
test("cancel during stopping preserves final audio", async () => {
  const recorder = new VoiceRecorder();
  await recorder.start();
  const audio = recorder.stop();
  recorder.cancel();
  expect((await audio).base64).toBe("YXVkaW8=");
});
