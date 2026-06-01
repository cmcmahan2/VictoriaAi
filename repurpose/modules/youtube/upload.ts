// Resumable upload to YouTube via the Data API v3 (googleapis).
import { google } from 'googleapis';
import fs from 'node:fs';
import { authorizedClient } from './oauth';
import type { ShortsMetadata } from '../generate/shorts-metadata';

export type PublishInput = {
  localPath: string;
  metadata: ShortsMetadata;
  privacyStatus?: 'private' | 'unlisted' | 'public';
  // YouTube category id; 22 = "People & Blogs" is a safe default.
  categoryId?: string;
};

export type PublishResult = {
  youtubeVideoId: string;
  watchUrl: string;
};

// Compose the final description: Claude's description, then hashtags on their
// own line. Including #Shorts in the description reinforces Shorts detection.
function buildDescription(metadata: ShortsMetadata): string {
  const tags = metadata.hashtags.join(' ').trim();
  return tags ? `${metadata.description}\n\n${tags}` : metadata.description;
}

export async function publishToYouTube(input: PublishInput): Promise<PublishResult> {
  if (!fs.existsSync(input.localPath)) {
    throw new Error(`Video file not found at ${input.localPath}`);
  }

  const auth = authorizedClient();
  const youtube = google.youtube({ version: 'v3', auth });

  const res = await youtube.videos.insert({
    part: ['snippet', 'status'],
    requestBody: {
      snippet: {
        title: input.metadata.title.slice(0, 100), // hard API limit
        description: buildDescription(input.metadata),
        tags: input.metadata.tags,
        categoryId: input.categoryId || '22',
      },
      status: {
        privacyStatus: input.privacyStatus || 'private',
        selfDeclaredMadeForKids: false,
      },
    },
    media: {
      body: fs.createReadStream(input.localPath),
    },
  });

  const id = res.data.id;
  if (!id) throw new Error('YouTube upload returned no video id');

  return {
    youtubeVideoId: id,
    watchUrl: `https://www.youtube.com/shorts/${id}`,
  };
}
