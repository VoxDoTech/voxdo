import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "com.voxdo.app",
  appName: "VoxDo",
  webDir: "dist",
  server: {
    // The WebView origin; CORS on the API allow-lists https://localhost.
    androidScheme: "https",
    // Dev only: `bun dev` + `cap run android --livereload` needs cleartext
    // to reach the dev machine over http://<lan-ip>:5173.
    cleartext: true,
  },
  android: {
    allowMixedContent: true,
  },
};

export default config;
