// Resumable upload to YouTube via the Data API v3 (googleapis).
// Stubbed for the step-1 scaffold; implemented in the publish step.
import type { ShortsMetadata } from '../generate/shorts-metadata';

export type PublishInput = {
  localPath: string;
  metadata: ShortsMetadata;
  privacyStatus?: 'private' | 'unlisted' | 'public';
};

export type PublishResult = {
  youtubeVideoId: string;
  watchUrl: string;
};

export async function publishToYouTube(_input: PublishInput): Promise<PublishResult> {
  throw new Error(
    'upload.ts is a step-1 stub. The googleapis resumable upload is implemented in the publish step.',
  );
}
