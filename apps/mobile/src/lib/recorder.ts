/**
 * MediaRecorder wrapper for voice memos: records, exposes a live input
 * level for the waveform, supports pause/resume, and returns base64 audio
 * for `note.createVoice`.
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

type AudioContextCtor = typeof AudioContext;

function getAudioContextCtor(): AudioContextCtor | null {
  const w = window as typeof window & {
    webkitAudioContext?: AudioContextCtor;
  };
  return w.AudioContext ?? w.webkitAudioContext ?? null;
}

export class VoiceRecorder {
  private recorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private chunks: Blob[] = [];
  private startedAt = 0;
  private pausedAt: number | null = null;
  private pausedTotal = 0;
  private context: AudioContext | null = null;
  private source: MediaStreamAudioSourceNode | null = null;
  private analyser: AnalyserNode | null = null;
  private levelData: Uint8Array<ArrayBuffer> | null = null;
  /** Smoothed level so the meter doesn't twitch on silent frames. */
  private smoothedLevel = 0;

  async start(): Promise<void> {
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        autoGainControl: true,
      },
    });
    this.stream = stream;
    this.attachAnalyser(stream);

    const mimeType = pickMimeType();
    this.recorder = new MediaRecorder(
      stream,
      mimeType ? { mimeType } : undefined,
    );
    this.chunks = [];
    this.recorder.ondataavailable = (event) => {
      if (event.data.size > 0) this.chunks.push(event.data);
    };
    this.startedAt = Date.now();
    this.pausedAt = null;
    this.pausedTotal = 0;
    this.recorder.start(250);
  }

  get isPaused(): boolean {
    return this.pausedAt !== null;
  }

  /** Elapsed recording time, excluding paused stretches. */
  elapsedMs(): number {
    if (!this.recorder) return 0;
    const now = this.pausedAt ?? Date.now();
    return Math.max(0, now - this.startedAt - this.pausedTotal);
  }

  pause(): void {
    if (this.recorder?.state !== "recording") return;
    this.recorder.pause();
    this.pausedAt = Date.now();
  }

  resume(): void {
    if (this.recorder?.state !== "paused") return;
    this.recorder.resume();
    if (this.pausedAt !== null) {
      this.pausedTotal += Date.now() - this.pausedAt;
      this.pausedAt = null;
    }
  }

  /** Current microphone level in 0..1 (RMS of the live stream). */
  getLevel(): number {
    const analyser = this.analyser;
    const data = this.levelData;
    if (!analyser || !data || this.isPaused) return 0;
    analyser.getByteTimeDomainData(data);
    let sum = 0;
    for (let i = 0; i < data.length; i += 1) {
      const sample = ((data[i] ?? 128) - 128) / 128;
      sum += sample * sample;
    }
    const rms = Math.sqrt(sum / data.length);
    const target = Math.min(1, rms * 3.4);
    this.smoothedLevel = this.smoothedLevel * 0.7 + target * 0.3;
    return this.smoothedLevel;
  }

  /** Stops recording and resolves with the encoded audio. */
  stop(): Promise<RecordedAudio> {
    return new Promise((resolve, reject) => {
      const recorder = this.recorder;
      if (!recorder) {
        reject(new Error("Recorder is not started"));
        return;
      }
      const durationSec = Math.max(0, Math.round(this.elapsedMs() / 1000));
      recorder.onstop = async () => {
        const blob = new Blob(this.chunks, { type: recorder.mimeType });
        this.cleanup();
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
      recorder.onerror = () => {
        this.cleanup();
        reject(new Error("Recording failed"));
      };
      recorder.stop();
      this.recorder = null;
    });
  }

  cancel(): void {
    const recorder = this.recorder;
    if (recorder) {
      recorder.onstop = null;
      if (recorder.state !== "inactive") recorder.stop();
    }
    this.recorder = null;
    this.chunks = [];
    this.cleanup();
  }

  private attachAnalyser(stream: MediaStream): void {
    const Ctor = getAudioContextCtor();
    if (!Ctor) return;
    try {
      const context = new Ctor();
      const source = context.createMediaStreamSource(stream);
      const analyser = context.createAnalyser();
      analyser.fftSize = 1024;
      analyser.smoothingTimeConstant = 0.75;
      source.connect(analyser);
      this.context = context;
      this.source = source;
      this.analyser = analyser;
      this.levelData = new Uint8Array(analyser.fftSize);
    } catch {
      // Level metering is decorative — recording keeps working without it.
      this.context = null;
      this.analyser = null;
      this.levelData = null;
    }
  }

  private cleanup(): void {
    this.stream?.getTracks().forEach((track) => {
      track.stop();
    });
    this.stream = null;
    this.source?.disconnect();
    this.source = null;
    this.analyser = null;
    this.levelData = null;
    const context = this.context;
    this.context = null;
    if (context && context.state !== "closed") {
      void context.close().catch(() => undefined);
    }
    this.smoothedLevel = 0;
  }
}
