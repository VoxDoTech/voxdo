import type { CapacitorConfig } from "@capacitor/cli";

// Cleartext HTTP is only for local development (dev machine / emulator).
// Enable it explicitly for dev builds, e.g.:
//   CAPACITOR_CLEAR_TEXT=1 bun cap:sync
// Release builds must stay on https — the API bearer token would otherwise
// be exposed to network observers.
const cleartext = process.env.CAPACITOR_CLEAR_TEXT === "1";

const config: CapacitorConfig = {
  appId: "com.voxdo.app",
  appName: "VoxDo",
  webDir: "dist",
  server: {
    // The WebView origin; CORS on the API allow-lists https://localhost.
    androidScheme: "https",
    cleartext,
  },
  android: {
    allowMixedContent: cleartext,
  },
};

export default config;
