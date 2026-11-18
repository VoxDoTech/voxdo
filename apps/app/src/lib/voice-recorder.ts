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
  private stopping = false;

  async start(): Promise<void> {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.stream = stream;
    try {
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
    } catch (error) {
      stream.getTracks().forEach((track) => {
        track.stop();
      });
      this.recorder = null;
      this.stream = null;
      this.chunks = [];
      this.startedAt = 0;
      throw error;
    }
  }

  /** Stops recording and resolves with the encoded audio. */
  stop(): Promise<RecordedAudio> {
    return new Promise((resolve, reject) => {
      const recorder = this.recorder;
      if (!recorder || this.stopping) {
        reject(new Error("Recorder is not started"));
        return;
      }
      this.stopping = true;
      const durationSec = Math.round((Date.now() - this.startedAt) / 1000);
      const cleanup = () => {
        recorder.stream.getTracks().forEach((track) => {
          track.stop();
        });
        recorder.ondataavailable = null;
        recorder.onstop = null;
        recorder.onerror = null;
        this.stream = null;
        this.recorder = null;
        this.chunks = [];
        this.startedAt = 0;
        this.stopping = false;
      };
      const finish = async () => {
        const blob = new Blob(this.chunks, { type: recorder.mimeType });
        cleanup();
        try {
          const base64 = await blobToBase64(blob);
          resolve({
            base64,
            mimeType: recorder.mimeType || "audio/webm",
            durationSec,
          });
        } catch (error) {
          reject(error);
        }
      };
      recorder.onstop = () => void finish();
      recorder.onerror = () => {
        cleanup();
        reject(new Error("Recording failed"));
      };
      try {
        if (recorder.state !== "inactive") recorder.stop();
        else void finish();
      } catch (error) {
        cleanup();
        reject(error);
      } finally {
        recorder.stream.getTracks().forEach((track) => {
          track.stop();
        });
      }
    });
  }

  cancel(): void {
    // A stop already in progress owns the final data event and cleanup.
    if (this.stopping) return;
    const recorder = this.recorder;
    try {
      if (recorder) {
        recorder.onstop = null;
        recorder.ondataavailable = null;
        recorder.onerror = null;
        if (recorder.state !== "inactive") recorder.stop();
      }
    } finally {
      this.stream?.getTracks().forEach((track) => {
        track.stop();
      });
      this.stream = null;
      this.recorder = null;
      this.chunks = [];
      this.startedAt = 0;
    }
  }
}
