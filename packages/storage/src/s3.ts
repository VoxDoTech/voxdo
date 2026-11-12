import { env, logger } from "@acme/config";
import {
  DeleteObjectCommand,
  GetObjectCommand,
  PutObjectCommand,
  S3Client,
} from "@aws-sdk/client-s3";
import { getSignedUrl } from "@aws-sdk/s3-request-presigner";

const s3Endpoint = env.AWS_S3_ENDPOINT;
const s3ForcePathStyle = env.AWS_S3_FORCE_PATH_STYLE !== "false";
const BUCKET_NAME = env.AWS_S3_BUCKET;

// The client is created lazily so importing this module never throws —
// credentials are only required once an actual S3 operation runs.
let s3Client: S3Client | undefined;

function getS3Client(): S3Client {
  if (s3Client) return s3Client;

  const accessKeyId = env.AWS_ACCESS_KEY_ID;
  const secretAccessKey = env.AWS_SECRET_ACCESS_KEY;
  if (!accessKeyId || !secretAccessKey) {
    throw new Error(
      "AWS credentials (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY) are required",
    );
  }

  s3Client = new S3Client({
    region: env.AWS_REGION,
    credentials: {
      accessKeyId,
      secretAccessKey,
    },
    ...(s3Endpoint
      ? {
          endpoint: s3Endpoint,
          forcePathStyle: s3ForcePathStyle, // MinIO-friendly by default when endpoint provided
        }
      : {}),
  });
  return s3Client;
}

export async function createPresignedUrl(key: string): Promise<string> {
  const command = new PutObjectCommand({
    Bucket: BUCKET_NAME,
    Key: key,
    ContentType: "application/octet-stream",
  });

  return getSignedUrl(getS3Client(), command, { expiresIn: 3600 }); // 1 hour
}

export function generateS3Key(originalKey: string, temporary = false): string {
  const timestamp = Date.now();
  const randomId = Math.random().toString(36).substring(2, 15);
  const prefix = temporary ? "temp" : "uploads";

  return `${prefix}/${timestamp}-${randomId}-${originalKey}`;
}

export async function uploadBufferToS3(
  key: string,
  body: Buffer | Uint8Array,
  contentType?: string,
): Promise<{ key: string; bucket: string; etag?: string }> {
  const command = new PutObjectCommand({
    Bucket: BUCKET_NAME,
    Key: key,
    Body: body,
    ContentType: contentType ?? "application/octet-stream",
  });
  try {
    const res = await getS3Client().send(command);
    return { key, bucket: BUCKET_NAME, etag: res.ETag };
  } catch (err) {
    const e = err as Error;
    logger.error("storage.s3_upload_failed", err, {
      bucket: BUCKET_NAME,
      key,
      error: e?.message ?? String(err),
    });
    throw new Error(
      `Failed to upload to S3 bucket '${BUCKET_NAME}' key '${key}': ${e?.message ?? String(err)}`,
    );
  }
}

export async function getDownloadUrl(key: string): Promise<string> {
  const command = new GetObjectCommand({
    Bucket: BUCKET_NAME,
    Key: key,
  });

  return getSignedUrl(getS3Client(), command, { expiresIn: 3600 }); // 1 hour
}

/** Deletes an S3 object — used when a note (or an orphaned upload) is removed. */
export async function deleteFromS3(key: string): Promise<void> {
  await getS3Client().send(
    new DeleteObjectCommand({ Bucket: BUCKET_NAME, Key: key }),
  );
}

/** Downloads an S3 object into memory — used by background jobs. */
export async function downloadFromS3(key: string): Promise<Buffer> {
  const res = await getS3Client().send(
    new GetObjectCommand({ Bucket: BUCKET_NAME, Key: key }),
  );
  if (!res.Body) {
    throw new Error(`S3 object '${key}' has no body`);
  }
  const chunks: Uint8Array[] = [];
  for await (const chunk of res.Body as AsyncIterable<Uint8Array>) {
    chunks.push(chunk);
  }
  return Buffer.concat(chunks);
}
