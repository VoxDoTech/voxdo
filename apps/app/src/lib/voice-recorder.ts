/**
 * MediaRecorder wrapper: records a voice memo and returns it base64-encoded
 * for `note.createVoice`. Browser counterpart of the mobile recorder.
 */

export interface RecordedAudio {
  base64: string;
  mimeType: string;
  durationSec: number;
}

function pickMimeType(): string {
  const candidates = [
    "audio/webm;codecs=opus",
    "audio/webm",
    "audio/mp4",
    "audio/ogg;codecs=opus",
  ];
  for (const type of candidates) {
    if (MediaRecorder.isTypeSupported(type)) return type;
  }
  return "";
}

function blobToBase64(blob: Blob): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = String(reader.result ?? "");
      resolve(result.slice(result.indexOf(",") + 1));
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(blob);
  });
}

export class VoiceRecorder {
  private recorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private chunks: Blob[] = [];
  private startedAt = 0;

  async start(): Promise<void> {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.stream = stream;
    const mimeType = pickMimeType();
    this.recorder = new MediaRecorder(
      stream,
      mimeType ? { mimeType } : undefined,
    );
    this.chunks = [];
    this.recorder.ondataavailable = (e) => {
      if (e.data.size > 0) this.chunks.push(e.data);
    };
    this.startedAt = Date.now();
    this.recorder.start(250);
  }

  /** Stops recording and resolves with the encoded audio. */
  stop(): Promise<RecordedAudio> {
    return new Promise((resolve, reject) => {
      const recorder = this.recorder;
      if (!recorder) {
        reject(new Error("Recorder is not started"));
        return;
      }
      recorder.onstop = async () => {
        recorder.stream.getTracks().forEach((t) => {
          t.stop();
        });
        this.stream = null;
        const blob = new Blob(this.chunks, { type: recorder.mimeType });
        const base64 = await blobToBase64(blob);
        resolve({
          base64,
          mimeType: recorder.mimeType || "audio/webm",
          durationSec: Math.round((Date.now() - this.startedAt) / 1000),
        });
      };
      recorder.onerror = () => reject(new Error("Recording failed"));
      recorder.stop();
      this.recorder = null;
    });
  }

  cancel(): void {
    const recorder = this.recorder;
    if (recorder) {
      recorder.onstop = null;
      recorder.stop();
    }
    // Covers a start() that is still acquiring the microphone.
    this.stream?.getTracks().forEach((t) => {
      t.stop();
    });
    this.stream = null;
    this.recorder = null;
    this.chunks = [];
  }
}
